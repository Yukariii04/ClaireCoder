import hashlib
import json
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from .types import Model, Provider, Endpoint, Capability, ModelError, ErrorCategory
from .errors import (
    ProviderError,
    ProviderTimeoutError,
    ProviderConnectionError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    ProviderResponseError,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

DEFAULT_USER_AGENT = "ClaireCoder/1.0 (Windows; x64) curl/8.0"


def normalize_credential(api_key: Optional[str]) -> Optional[str]:
    """Normalize API keys: remove outer whitespace, enclosing quotes, and redundant 'Bearer '."""
    if api_key is None:
        return None
    key = str(api_key).strip()
    changed = True
    while changed and key:
        changed = False
        # Strip redundant Bearer prefix
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
            changed = True
        # Strip surrounding single or double quotes
        if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
            if len(key) >= 2:
                key = key[1:-1].strip()
                changed = True
    key = key.strip(" \t\r\n")
    return key if key else None


def get_credential_fingerprint(api_key: Optional[str]) -> Dict[str, Any]:
    """Safe diagnostic metadata about a credential for tests/debug without leaking secrets."""
    if not api_key:
        return {
            "is_set": False,
            "length": 0,
            "has_leading_whitespace": False,
            "has_trailing_whitespace": False,
            "has_newline": False,
            "has_surrounding_quotes": False,
            "fingerprint": None,
        }
    raw = str(api_key)
    has_leading = raw.startswith((" ", "\t", "\r", "\n"))
    has_trailing = raw.endswith((" ", "\t", "\r", "\n"))
    has_nl = "\n" in raw or "\r" in raw
    has_quotes = (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'"))
    normalized = normalize_credential(raw) or ""
    sha = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12] if normalized else None
    return {
        "is_set": bool(normalized),
        "length": len(normalized),
        "raw_length": len(raw),
        "has_leading_whitespace": has_leading,
        "has_trailing_whitespace": has_trailing,
        "has_newline": has_nl,
        "has_surrounding_quotes": has_quotes,
        "fingerprint": sha,
    }


def _parse_http_error_body(e: urllib.error.HTTPError, provider_name: str) -> str:
    """Safely extract error message from HTTPError response body without exposing secrets."""
    try:
        raw_body = e.read().decode("utf-8", errors="replace")
        data = json.loads(raw_body)
        if isinstance(data, dict):
            # OpenAI / Groq format: {"error": {"message": "...", "type": "...", "code": "..."}}
            if "error" in data:
                err = data["error"]
                if isinstance(err, dict) and "message" in err:
                    return str(err["message"])
                return str(err)
            # Anthropic format: {"type": "error", "error": {"type": "...", "message": "..."}}
            if "message" in data:
                return str(data["message"])
        return raw_body.strip()[:200]
    except Exception:
        return f"HTTP {e.code}: {e.reason}"
    finally:
        try:
            e.close()
        except Exception:
            pass


def _http_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> Dict[str, Any]:
    """Simple GET request returning parsed JSON with standard User-Agent and structured error mapping."""
    if not url or not url.strip().startswith(("http://", "https://")):
        raise ProviderConnectionError(
            message=f"Invalid URL '{url}': must be an absolute URL starting with http:// or https://"
        )
    hdrs = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = _parse_http_error_body(e, "Provider")
        try:
            e.close()
        except Exception:
            pass
        if e.code in (401, 403):
            raise ProviderAuthenticationError(
                message=f"Authentication failed (HTTP {e.code}): {err_msg}",
                status_code=e.code,
            ) from None
        elif e.code == 429:
            raise ProviderRateLimitError(
                message=f"Rate limited (HTTP 429): {err_msg}",
            ) from None
        elif e.code >= 500:
            raise ProviderUnavailableError(
                message=f"Provider unavailable (HTTP {e.code}): {err_msg}",
                status_code=e.code,
            ) from None
        else:
            raise ProviderResponseError(
                message=f"HTTP {e.code}: {err_msg}",
                status_code=e.code,
            ) from None
    except TimeoutError as te:
        raise ProviderTimeoutError(
            message=f"Request to {url} timed out after {timeout}s",
            timeout_seconds=float(timeout),
        ) from te
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            raise ProviderTimeoutError(
                message=f"Request to {url} timed out after {timeout}s",
                timeout_seconds=float(timeout),
            ) from e
        raise ProviderConnectionError(
            message=f"Network error connecting to {url}: {e.reason}",
        ) from None


def _infer_capabilities(model_data: Dict[str, Any], model_id: str) -> List[Capability]:
    """Best-effort capability inference from provider metadata."""
    caps: List[Capability] = [Capability.TEXT]
    mid = model_id.lower()

    # Streaming is universal for all modern providers
    caps.append(Capability.STREAMING)

    # Tool calling heuristic
    if model_data.get("tool_calling") or model_data.get("function_calling"):
        caps.append(Capability.TOOL_CALLING)
    elif any(kw in mid for kw in ("gpt-4", "gpt-3.5", "claude", "gemini", "llama-3", "mistral", "qwen")):
        caps.append(Capability.TOOL_CALLING)

    # Vision heuristic
    if model_data.get("vision") or "vision" in mid or model_data.get("image_input"):
        caps.append(Capability.VISION)

    # Reasoning heuristic
    if "reasoning" in mid or mid.startswith("o1") or mid.startswith("o3") or mid.startswith("o4"):
        caps.append(Capability.REASONING)

    # Structured output
    if model_data.get("structured_output") or model_data.get("response_format"):
        caps.append(Capability.STRUCTURED_OUTPUT)

    return list(set(caps))


def validate_provider(
    provider_id: str,
    endpoint: str,
    api_key: Optional[str] = None,
    provider_name: Optional[str] = None,
    timeout: int = 10,
) -> bool:
    """Lightweight validation of provider endpoint and credentials (without full model parsing).
    
    Answers: 'Can this Provider Profile authenticate/reach the configured endpoint?'
    """
    from .config import PROVIDER_REGISTRY, AdapterType

    reg = PROVIDER_REGISTRY.get(provider_id, {})
    adapter = reg.get("adapter", AdapterType.OPENAI_COMPATIBLE)
    norm_key = normalize_credential(api_key)
    raw_ep = (endpoint or reg.get("default_endpoint", "")).strip().rstrip("/")
    if not raw_ep:
        raise ProviderConnectionError(
            message=f"Endpoint URL cannot be empty for provider '{provider_id}'",
            provider=provider_id,
        )
    if not raw_ep.startswith(("http://", "https://")):
        raise ProviderConnectionError(
            message=f"Invalid endpoint URL '{raw_ep}' for provider '{provider_id}': must start with http:// or https://",
            provider=provider_id,
        )
    ep = raw_ep

    if adapter == AdapterType.OLLAMA or provider_id == "ollama":
        url = f"{ep}/api/tags"
        _http_get(url, timeout=timeout)
        return True
    elif adapter == AdapterType.GEMINI or provider_id == "gemini":
        url = f"{ep}/v1beta/models"
        if norm_key:
            url = f"{url}?key={norm_key}"
        _http_get(url, timeout=timeout)
        return True
    elif adapter == AdapterType.ANTHROPIC or provider_id == "anthropic":
        url = f"{ep}/v1/models"
        headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        if norm_key:
            headers["x-api-key"] = norm_key
        try:
            _http_get(url, headers=headers, timeout=timeout)
            return True
        except ModelError as me:
            if "HTTP 404" in me.message or "HTTP 400" in me.message:
                # Some Anthropic tiers reject /v1/models; key may still be valid
                return True
            raise
    else:
        # OpenAI-compatible (OpenAI, Groq, OpenRouter, LM Studio, vLLM, Custom, OmniRoute)
        url = ep if ep.endswith("/models") else f"{ep}/models"
        headers = {}
        if norm_key:
            headers["Authorization"] = f"Bearer {norm_key}"
        _http_get(url, headers=headers, timeout=timeout)
        return True


def discover_openai_compatible(
    endpoint: str,
    api_key: Optional[str] = None,
    provider_id: str = "openai",
    provider_name: str = "OpenAI",
    timeout: int = 15,
    extra_headers: Optional[Dict[str, str]] = None,
) -> List[Model]:
    """Discover models from an OpenAI-compatible /v1/models endpoint."""
    if not endpoint or not endpoint.strip():
        raise ProviderConnectionError(
            message=f"Endpoint URL cannot be empty for provider '{provider_id}'",
            provider=provider_id,
        )
    clean_ep = endpoint.strip().rstrip("/")
    if not clean_ep.startswith(("http://", "https://")):
        raise ProviderConnectionError(
            message=f"Invalid endpoint URL '{clean_ep}' for provider '{provider_id}': must start with http:// or https://",
            provider=provider_id,
        )
    url = clean_ep if clean_ep.endswith("/models") else f"{clean_ep}/models"

    norm_key = normalize_credential(api_key)
    headers: Dict[str, str] = {}
    if extra_headers:
        headers.update(extra_headers)
    if norm_key:
        headers["Authorization"] = f"Bearer {norm_key}"

    try:
        data = _http_get(url, headers=headers, timeout=timeout)
    except Exception as e:
        logger.debug("Model discovery failed for %s: %s", provider_id, e)
        raise

    provider = Provider(id=provider_id, name=provider_name)
    ep = Endpoint(url=endpoint.rstrip("/"))
    models: List[Model] = []

    for item in data.get("data", []):
        mid = item.get("id", "")
        display = item.get("name") or item.get("id", mid)
        ctx = item.get("context_length") or item.get("context_window")
        caps = _infer_capabilities(item, mid)
        models.append(Model(
            id=mid,
            display_name=display,
            provider=provider,
            endpoint=ep,
            capabilities=caps,
            context_capacity=ctx,
            metadata=item,
        ))

    return sorted(models, key=lambda m: m.id)


def discover_anthropic(
    endpoint: str = "https://api.anthropic.com",
    api_key: Optional[str] = None,
    timeout: int = 15,
) -> List[Model]:
    """Discover available Anthropic models via the /v1/models endpoint."""
    norm_key = normalize_credential(api_key)
    url = f"{endpoint.rstrip('/')}/v1/models"
    headers: Dict[str, str] = {
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    if norm_key:
        headers["x-api-key"] = norm_key

    try:
        data = _http_get(url, headers=headers, timeout=timeout)
    except Exception:
        # Fallback to curated list — Anthropic may restrict /v1/models for some plans
        logger.debug("Anthropic /v1/models unavailable, using curated model list")
        return _anthropic_curated_models(endpoint)

    provider = Provider(id="anthropic", name="Anthropic")
    ep = Endpoint(url=endpoint.rstrip("/"))
    models: List[Model] = []

    for item in data.get("data", []):
        mid = item.get("id", "")
        display = item.get("display_name") or item.get("name") or mid
        caps = [Capability.TEXT, Capability.STREAMING, Capability.TOOL_CALLING]
        if "vision" in mid.lower() or item.get("vision"):
            caps.append(Capability.VISION)
        ctx = item.get("context_window")
        models.append(Model(
            id=mid,
            display_name=display,
            provider=provider,
            endpoint=ep,
            capabilities=caps,
            context_capacity=ctx,
            metadata=item,
        ))

    return sorted(models, key=lambda m: m.id) if models else _anthropic_curated_models(endpoint)


def _anthropic_curated_models(endpoint: str) -> List[Model]:
    """Curated Anthropic model list when API discovery is unavailable."""
    provider = Provider(id="anthropic", name="Anthropic")
    ep = Endpoint(url=endpoint.rstrip("/"))
    base_caps = [Capability.TEXT, Capability.STREAMING, Capability.TOOL_CALLING, Capability.VISION]

    entries = [
        ("claude-sonnet-4-20250514", "Claude Sonnet 4", 200000, base_caps),
        ("claude-opus-4-20250514", "Claude Opus 4", 200000, base_caps),
        ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", 200000, base_caps),
    ]
    models = []
    for mid, display, ctx, caps in entries:
        models.append(Model(
            id=mid,
            display_name=display,
            provider=provider,
            endpoint=ep,
            capabilities=list(caps),
            context_capacity=ctx,
        ))
    return models


def discover_gemini(
    endpoint: str = "https://generativelanguage.googleapis.com",
    api_key: Optional[str] = None,
    timeout: int = 15,
) -> List[Model]:
    """Discover available Google Gemini models via the /v1beta/models endpoint."""
    norm_key = normalize_credential(api_key)
    url = f"{endpoint.rstrip('/')}/v1beta/models"
    if norm_key:
        url = f"{url}?key={norm_key}"

    try:
        data = _http_get(url, timeout=timeout)
    except Exception as e:
        logger.debug("Gemini model discovery failed: %s", e)
        raise

    provider = Provider(id="gemini", name="Google Gemini")
    ep = Endpoint(url=endpoint.rstrip("/"))
    models: List[Model] = []

    for item in data.get("models", []):
        # Gemini model names are like "models/gemini-2.5-pro"
        full_name = item.get("name", "")
        mid = full_name.replace("models/", "")
        display = item.get("displayName") or mid
        supported_methods = item.get("supportedGenerationMethods", [])

        if "generateContent" not in supported_methods:
            continue  # Skip models that can't generate content

        caps = [Capability.TEXT]
        if "streamGenerateContent" in supported_methods:
            caps.append(Capability.STREAMING)

        input_token_limit = item.get("inputTokenLimit")
        output_token_limit = item.get("outputTokenLimit")
        ctx = input_token_limit

        # Gemini 2.x generally supports tool calling and structured output
        if any(kw in mid.lower() for kw in ("gemini-2", "gemini-1.5")):
            caps.extend([Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT, Capability.VISION])

        models.append(Model(
            id=mid,
            display_name=display,
            provider=provider,
            endpoint=ep,
            capabilities=list(set(caps)),
            context_capacity=ctx,
            metadata=item,
        ))

    return sorted(models, key=lambda m: m.id)


def discover_ollama(
    endpoint: str = "http://localhost:11434",
    timeout: int = 10,
) -> List[Model]:
    """Discover available Ollama models via the /api/tags endpoint."""
    url = f"{endpoint.rstrip('/')}/api/tags"
    try:
        data = _http_get(url, timeout=timeout)
    except Exception as e:
        logger.debug("Ollama model discovery failed: %s", e)
        raise

    provider = Provider(id="ollama", name="Ollama")
    ep = Endpoint(url=endpoint.rstrip("/"))
    models: List[Model] = []

    for item in data.get("models", []):
        mid = item.get("name", "") or item.get("model", "")
        display = mid
        caps = [Capability.TEXT, Capability.STREAMING]
        details = item.get("details", {})
        families = details.get("families", []) or []
        # Large parameter counts hint at tool calling support
        param_size = details.get("parameter_size", "")

        if "clip" in families or "vision" in mid.lower():
            caps.append(Capability.VISION)

        models.append(Model(
            id=mid,
            display_name=display,
            provider=provider,
            endpoint=ep,
            capabilities=caps,
            metadata=item,
        ))

    return sorted(models, key=lambda m: m.id)


def discover_models(
    provider_id: str,
    endpoint: str,
    api_key: Optional[str] = None,
    provider_name: Optional[str] = None,
    timeout: int = 15,
) -> List[Model]:
    """Unified discovery dispatcher. Routes to provider-specific discovery."""
    from .config import PROVIDER_REGISTRY, AdapterType

    reg = PROVIDER_REGISTRY.get(provider_id, {})
    adapter = reg.get("adapter", AdapterType.OPENAI_COMPATIBLE)
    pname = provider_name or reg.get("name", provider_id)

    if adapter == AdapterType.ANTHROPIC or provider_id == "anthropic":
        return discover_anthropic(endpoint=endpoint, api_key=api_key, timeout=timeout)
    elif adapter == AdapterType.GEMINI or provider_id == "gemini":
        return discover_gemini(endpoint=endpoint, api_key=api_key, timeout=timeout)
    elif adapter == AdapterType.OLLAMA or provider_id == "ollama":
        return discover_ollama(endpoint=endpoint, timeout=timeout)
    else:
        # OpenAI-compatible: openai, groq, openrouter, omniroute, lmstudio, vllm, custom
        return discover_openai_compatible(
            endpoint=endpoint,
            api_key=api_key,
            provider_id=provider_id,
            provider_name=pname,
            timeout=timeout,
        )
