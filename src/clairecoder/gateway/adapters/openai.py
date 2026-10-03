import json
import math
from typing import List, Dict, Any, Optional
import urllib.request
import urllib.error

from clairecoder.gateway.discovery import normalize_credential, DEFAULT_USER_AGENT, _parse_http_error_body
from clairecoder.gateway.interfaces import ProviderAdapterInterface
from clairecoder.gateway.types import Model, ModelRequest, ModelResponse, Capability, ModelError, ErrorCategory
from clairecoder.gateway.errors import (
    ProviderError,
    ProviderTimeoutError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    ProviderUnavailableError,
    ProviderResponseError,
    ProviderInvalidOutputError,
    sanitize_sensitive_data,
)


class OpenAICompatibleAdapter(ProviderAdapterInterface):
    """
    Adapter for OpenAI-compatible APIs (OpenAI, Groq, OpenRouter, vLLM/LMStudio, OmniRoute).
    Supports injecting an optional `http_client` mock for testing.
    
    Correction #22: Hardened with explicit timeouts, Retry-After parsing, endpoint validation,
    and structured error mapping.
    """
    DEFAULT_TIMEOUT_SECONDS = 60.0

    def __init__(
        self,
        provider_id: str = "openai-compatible",
        auth_token: Optional[str] = None,
        http_client: Any = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._provider_id = provider_id
        self._auth_token = normalize_credential(auth_token)
        self._http_client = http_client
        try:
            self.timeout_seconds = float(timeout_seconds)
        except (ValueError, TypeError) as e:
            raise ValueError(f"{self._provider_id} timeout_seconds must be a positive number") from e
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError(f"{self._provider_id} timeout_seconds must be a finite positive number")

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def _parse_retry_after(self, e: urllib.error.HTTPError) -> Optional[float]:
        """Extract Retry-After header in seconds if present."""
        if not hasattr(e, "headers") or not e.headers:
            return None
        ra = e.headers.get("Retry-After")
        if not ra:
            return None
        try:
            val = float(ra.strip())
            return val if val > 0 else None
        except (ValueError, TypeError):
            return None

    def _validate_endpoint(self, raw_endpoint: str) -> str:
        """Validate and normalize endpoint URL, preventing relative URLs."""
        if not raw_endpoint or not raw_endpoint.strip():
            raise ProviderConnectionError(
                message=f"Endpoint URL is required for provider '{self._provider_id}'",
                provider=self._provider_id,
            )
        endpoint = raw_endpoint.strip().rstrip("/")
        if endpoint.startswith("/"):
            raise ProviderConnectionError(
                message=f"Relative endpoint URL '{endpoint}' is invalid for provider '{self._provider_id}'; must be an absolute URL",
                provider=self._provider_id,
            )
        if not self._http_client and not endpoint.startswith(("http://", "https://")):
            raise ProviderConnectionError(
                message=f"Invalid endpoint URL '{endpoint}': must start with http:// or https://",
                provider=self._provider_id,
            )
        if not endpoint.endswith("/chat/completions"):
            endpoint = f"{endpoint}/chat/completions"
        return endpoint

    def _make_http_request(
        self, url: str, headers: Dict[str, str], data: bytes, model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Wrap urllib to allow easy testing isolation, timeout enforcement, and error mapping."""
        try:
            if self._http_client:
                # If a test mock is provided, use it
                return self._http_client.post(url, headers=headers, data=data)
                
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                body_bytes = response.read()
                if not body_bytes:
                    raise ProviderResponseError(
                        message="Provider returned an empty response body (0 bytes)",
                        provider=self._provider_id,
                        model=model_id,
                        status_code=getattr(response, "status", 200),
                    )
                try:
                    return json.loads(body_bytes.decode("utf-8"))
                except json.JSONDecodeError as jde:
                    raise ProviderResponseError(
                        message=f"Provider returned malformed JSON: {jde}",
                        provider=self._provider_id,
                        model=model_id,
                        status_code=200,
                    ) from jde
        except urllib.error.HTTPError as e:
            with e:
                err_msg = _parse_http_error_body(e, self._provider_id)
            status = e.code
            retry_after = self._parse_retry_after(e)
            if status in (401, 403):
                raise ProviderAuthenticationError(
                    message=f"Authentication failed (HTTP {status}): {err_msg}",
                    provider=self._provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
            elif status == 429:
                raise ProviderRateLimitError(
                    message=f"Rate limited (HTTP 429): {err_msg}",
                    provider=self._provider_id,
                    model=model_id,
                    retry_after=retry_after,
                ) from e
            elif status >= 500:
                raise ProviderUnavailableError(
                    message=f"Provider error (HTTP {status}): {err_msg}",
                    provider=self._provider_id,
                    model=model_id,
                    status_code=status,
                    retry_after=retry_after,
                ) from e
            else:
                raise ProviderResponseError(
                    message=f"HTTP {status}: {err_msg}",
                    provider=self._provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
        except TimeoutError as e:
            raise ProviderTimeoutError(
                message=f"Request to {url} timed out after {self.timeout_seconds:g}s",
                provider=self._provider_id,
                model=model_id,
                timeout_seconds=self.timeout_seconds,
            ) from e
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise ProviderTimeoutError(
                    message=f"Request to {url} timed out after {self.timeout_seconds:g}s",
                    provider=self._provider_id,
                    model=model_id,
                    timeout_seconds=self.timeout_seconds,
                ) from e
            raise ProviderConnectionError(
                message=f"Network error connecting to {url}: {str(e)}",
                provider=self._provider_id,
                model=model_id,
            ) from e

    def _make_http_stream(
        self, url: str, headers: Dict[str, str], data: bytes, model_id: Optional[str] = None
    ) -> Any:
        try:
            if self._http_client and hasattr(self._http_client, "post_stream"):
                return self._http_client.post_stream(url, headers=headers, data=data)
            
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            return urllib.request.urlopen(req, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as e:
            with e:
                err_msg = _parse_http_error_body(e, self._provider_id)
            status = e.code
            retry_after = self._parse_retry_after(e)
            if status in (401, 403):
                raise ProviderAuthenticationError(
                    message=f"Authentication failed (HTTP {status}): {err_msg}",
                    provider=self._provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
            elif status == 429:
                raise ProviderRateLimitError(
                    message=f"Rate limited: {err_msg}",
                    provider=self._provider_id,
                    model=model_id,
                    retry_after=retry_after,
                ) from e
            elif status >= 500:
                raise ProviderUnavailableError(
                    message=f"Provider error (HTTP {status}): {err_msg}",
                    provider=self._provider_id,
                    model=model_id,
                    status_code=status,
                    retry_after=retry_after,
                ) from e
            else:
                raise ProviderResponseError(
                    message=f"HTTP {status}: {err_msg}",
                    provider=self._provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
        except TimeoutError as e:
            raise ProviderTimeoutError(
                message=f"Stream request timed out after {self.timeout_seconds:g}s",
                provider=self._provider_id,
                model=model_id,
                timeout_seconds=self.timeout_seconds,
            ) from e
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise ProviderTimeoutError(
                    message=f"Stream request timed out after {self.timeout_seconds:g}s",
                    provider=self._provider_id,
                    model=model_id,
                    timeout_seconds=self.timeout_seconds,
                ) from e
            raise ProviderConnectionError(
                message=f"Network error connecting to stream: {str(e)}",
                provider=self._provider_id,
                model=model_id,
            ) from e

    def execute(self, model: Model, request: ModelRequest) -> ModelResponse:
        url = self._validate_endpoint(model.endpoint.url)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        # Merge model-specific headers
        headers.update(model.endpoint.headers)
        
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        payload: Dict[str, Any] = {
            "model": request.model_id,
            "messages": request.messages,
            "stream": request.stream
        }
        
        if request.tools:
            payload["tools"] = request.tools
        if request.structured_output_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": request.structured_output_schema}
            }

        data = json.dumps(payload).encode("utf-8")
        
        if request.stream:
            response_stream = self._make_http_stream(url, headers, data, model_id=request.model_id)
                
            def stream_generator():
                for line in response_stream:
                    line_str = line.decode('utf-8').strip()
                    if not line_str or not line_str.startswith("data: "):
                        continue
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content")
                        tool_calls = delta.get("tool_calls")
                        if text or tool_calls:
                            yield ModelResponse(
                                text=text,
                                tool_calls=tool_calls,
                                provider=self._provider_id,
                                model=request.model_id,
                            )
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
            return ModelResponse(
                stream_generator=stream_generator(),
                provider=self._provider_id,
                model=request.model_id,
            )
        
        # Execute request
        response_data = self._make_http_request(url, headers, data, model_id=request.model_id)

        # Parse response
        if not isinstance(response_data, dict):
            raise ProviderResponseError(
                message=f"Invalid response payload type: {type(response_data).__name__}",
                provider=self._provider_id,
                model=request.model_id,
            )

        choices = response_data.get("choices")
        if not choices or not isinstance(choices, list):
            raise ProviderResponseError(
                message="Provider response missing or empty 'choices' field",
                provider=self._provider_id,
                model=request.model_id,
            )

        try:
            choice = choices[0]
            message = choice.get("message", {})
            
            text = message.get("content")
            tool_calls = message.get("tool_calls")
            
            structured_output = None
            if request.structured_output_schema and text:
                try:
                    structured_output = json.loads(text)
                except json.JSONDecodeError:
                    raise ProviderInvalidOutputError(
                        message="Provider returned invalid JSON for structured output",
                        provider=self._provider_id,
                        model=request.model_id,
                        raw_output=text,
                    )
            
            usage = response_data.get("usage", {})
            
            return ModelResponse(
                text=text,
                tool_calls=tool_calls,
                structured_output=structured_output,
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0) if isinstance(usage, dict) else 0,
                    "completion_tokens": usage.get("completion_tokens", 0) if isinstance(usage, dict) else 0
                },
                provider_specific={"finish_reason": choice.get("finish_reason")},
                provider=self._provider_id,
                model=request.model_id,
            )
        except (KeyError, IndexError) as e:
            raise ProviderResponseError(
                message=f"Invalid response format from provider: {str(e)}",
                provider=self._provider_id,
                model=request.model_id,
            ) from e
