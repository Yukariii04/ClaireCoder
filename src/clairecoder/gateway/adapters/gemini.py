"""Native Google Gemini adapter using the generateContent API with reliability hardening.

Gemini uses a distinct API format:
  - Auth: API key as query parameter
  - Endpoint: POST /v1beta/models/{model}:generateContent
  - Streaming: POST /v1beta/models/{model}:streamGenerateContent

Correction #22: Hardened against timeouts, Retry-After header support, malformed endpoints,
and normalized structured provider errors.
"""
import json
import math
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from clairecoder.gateway.interfaces import ProviderAdapterInterface
from clairecoder.gateway.types import (
    Model, ModelRequest, ModelResponse, Capability, ModelError, ErrorCategory,
)
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


class GeminiAdapter(ProviderAdapterInterface):
    """Native adapter for Google Gemini's generateContent API with reliability hardening."""

    DEFAULT_TIMEOUT_SECONDS = 60.0

    def __init__(
        self,
        auth_token: Optional[str] = None,
        http_client: Any = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._auth_token = auth_token
        self._http_client = http_client
        try:
            self.timeout_seconds = float(timeout_seconds)
        except (ValueError, TypeError) as e:
            raise ValueError("Gemini timeout_seconds must be a positive number") from e
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Gemini timeout_seconds must be a finite positive number")

    @property
    def provider_id(self) -> str:
        return "gemini"

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
                message="Gemini endpoint URL is missing or empty",
                provider=self.provider_id,
            )
        endpoint = raw_endpoint.strip().rstrip("/")
        if endpoint.startswith("/"):
            raise ProviderConnectionError(
                message=f"Relative endpoint URL '{endpoint}' is invalid for Gemini; must be an absolute URL",
                provider=self.provider_id,
            )
        if not self._http_client and not endpoint.startswith(("http://", "https://")):
            raise ProviderConnectionError(
                message=f"Invalid Gemini endpoint URL '{endpoint}': must start with http:// or https://",
                provider=self.provider_id,
            )
        return endpoint

    def _make_request(
        self, url: str, headers: Dict[str, str], data: bytes, model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute POST request to Gemini API with normalized error mapping."""
        try:
            if self._http_client:
                return self._http_client.post(url, headers=headers, data=data)
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                body_bytes = response.read()
                if not body_bytes:
                    raise ProviderResponseError(
                        message="Gemini returned an empty response body (0 bytes)",
                        provider=self.provider_id,
                        model=model_id,
                        status_code=getattr(response, "status", 200),
                    )
                try:
                    return json.loads(body_bytes.decode("utf-8"))
                except json.JSONDecodeError as jde:
                    raise ProviderResponseError(
                        message=f"Malformed JSON in Gemini response: {jde}",
                        provider=self.provider_id,
                        model=model_id,
                        status_code=200,
                    ) from jde
        except urllib.error.HTTPError as e:
            with e:
                body = e.read().decode("utf-8", errors="replace")
            status = e.code
            retry_after = self._parse_retry_after(e)
            if status in (401, 403):
                raise ProviderAuthenticationError(
                    message=f"Gemini auth failed (HTTP {status}): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
            elif status == 429:
                raise ProviderRateLimitError(
                    message=f"Gemini rate limited (HTTP 429): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    retry_after=retry_after,
                ) from e
            elif status >= 500:
                raise ProviderUnavailableError(
                    message=f"Gemini server error (HTTP {status}): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                    retry_after=retry_after,
                ) from e
            else:
                raise ProviderResponseError(
                    message=f"Gemini HTTP {status}: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
        except TimeoutError as e:
            raise ProviderTimeoutError(
                message=f"Gemini request timed out after {self.timeout_seconds:g}s",
                provider=self.provider_id,
                model=model_id,
                timeout_seconds=self.timeout_seconds,
            ) from e
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise ProviderTimeoutError(
                    message=f"Gemini request timed out after {self.timeout_seconds:g}s",
                    provider=self.provider_id,
                    model=model_id,
                    timeout_seconds=self.timeout_seconds,
                ) from e
            raise ProviderConnectionError(
                message=f"Network error connecting to Gemini: {e}",
                provider=self.provider_id,
                model=model_id,
            ) from e

    def _make_stream_request(
        self, url: str, headers: Dict[str, str], data: bytes, model_id: Optional[str] = None
    ) -> Any:
        """Execute streaming POST request."""
        try:
            if self._http_client and hasattr(self._http_client, "post_stream"):
                return self._http_client.post_stream(url, headers=headers, data=data)
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            return urllib.request.urlopen(req, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as e:
            with e:
                body = e.read().decode("utf-8", errors="replace")
            status = e.code
            retry_after = self._parse_retry_after(e)
            if status in (401, 403):
                raise ProviderAuthenticationError(
                    message=f"Gemini auth failed: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
            elif status == 429:
                raise ProviderRateLimitError(
                    message=f"Gemini rate limited: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    retry_after=retry_after,
                ) from e
            elif status >= 500:
                raise ProviderUnavailableError(
                    message=f"Gemini server error (HTTP {status}): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                    retry_after=retry_after,
                ) from e
            else:
                raise ProviderResponseError(
                    message=f"Gemini HTTP {status}: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
        except TimeoutError as e:
            raise ProviderTimeoutError(
                message=f"Gemini stream request timed out after {self.timeout_seconds:g}s",
                provider=self.provider_id,
                model=model_id,
                timeout_seconds=self.timeout_seconds,
            ) from e
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise ProviderTimeoutError(
                    message=f"Gemini stream request timed out after {self.timeout_seconds:g}s",
                    provider=self.provider_id,
                    model=model_id,
                    timeout_seconds=self.timeout_seconds,
                ) from e
            raise ProviderConnectionError(
                message=f"Network error connecting to Gemini stream: {e}",
                provider=self.provider_id,
                model=model_id,
            ) from e

    def _convert_messages(self, messages: List[Dict[str, Any]]) -> tuple:
        """Convert OpenAI-style messages to Gemini format."""
        system_parts: List[str] = []
        contents: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_parts.append(content if isinstance(content, str) else str(content))
            elif role == "assistant":
                parts = []
                if content:
                    parts.append({"text": str(content)})
                for call in msg.get("tool_calls", []) or []:
                    function = call.get("function", {})
                    raw_args = function.get("arguments", call.get("arguments", {}))
                    if isinstance(raw_args, str):
                        try:
                            input_args = json.loads(raw_args)
                        except json.JSONDecodeError:
                            input_args = {}
                    else:
                        input_args = raw_args if isinstance(raw_args, dict) else {}
                    parts.append({
                        "functionCall": {
                            "name": function.get("name") or call.get("name", ""),
                            "args": input_args,
                        }
                    })
                contents.append({
                    "role": "model",
                    "parts": parts or [{"text": ""}],
                })
            elif role == "tool":
                contents.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.get("name", ""),
                            "response": {"content": str(content)},
                        }
                    }],
                })
            else:
                contents.append({
                    "role": "user",
                    "parts": [{"text": content}],
                })

        system_instruction = None
        if system_parts:
            system_instruction = {"parts": [{"text": "\n\n".join(system_parts)}]}

        return system_instruction, contents

    def _convert_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """Convert OpenAI-style tool definitions to Gemini function declarations."""
        if not tools:
            return None
        declarations = []
        for tool in tools:
            fn = tool.get("function", tool)
            decl: Dict[str, Any] = {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
            }
            params = fn.get("parameters")
            if params:
                decl["parameters"] = params
            declarations.append(decl)
        return [{"functionDeclarations": declarations}]

    def execute(self, model: Model, request: ModelRequest) -> ModelResponse:
        base_url = self._validate_endpoint(model.endpoint.url)
        model_id = request.model_id

        if request.stream:
            endpoint_path = f"/v1beta/models/{model_id}:streamGenerateContent"
        else:
            endpoint_path = f"/v1beta/models/{model_id}:generateContent"

        url = f"{base_url}{endpoint_path}"
        if self._auth_token:
            url = f"{url}?key={self._auth_token}"

        headers = {"Content-Type": "application/json"}
        headers.update(model.endpoint.headers)

        system_instruction, contents = self._convert_messages(request.messages)

        payload: Dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        tools = self._convert_tools(request.tools)
        if tools:
            payload["tools"] = tools

        if request.structured_output_schema:
            payload["generationConfig"] = {
                "responseMimeType": "application/json",
                "responseSchema": request.structured_output_schema,
            }

        data = json.dumps(payload).encode("utf-8")

        if request.stream:
            response_stream = self._make_stream_request(url, headers, data, model_id=request.model_id)

            def stream_generator():
                buffer = b""
                for chunk in response_stream:
                    buffer += chunk if isinstance(chunk, bytes) else chunk.encode()
                    text = buffer.decode("utf-8", errors="replace")
                    try:
                        parsed = json.loads(text.lstrip("[,").rstrip(",]"))
                        candidates = parsed.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    yield ModelResponse(
                                        text=part["text"],
                                        provider=self.provider_id,
                                        model=request.model_id,
                                    )
                        buffer = b""
                    except (json.JSONDecodeError, ValueError):
                        pass

            return ModelResponse(
                stream_generator=stream_generator(),
                provider=self.provider_id,
                model=request.model_id,
            )

        # Non-streaming execution
        response_data = self._make_request(url, headers, data, model_id=request.model_id)

        try:
            candidates = response_data.get("candidates", [])
            if not candidates:
                error_info = response_data.get("error", {})
                if error_info:
                    raise ProviderResponseError(
                        message=f"Gemini error: {error_info.get('message', 'Unknown')}",
                        provider=self.provider_id,
                        model=request.model_id,
                    )
                return ModelResponse(
                    text="",
                    provider=self.provider_id,
                    model=request.model_id,
                )

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            text_parts = []
            tool_calls = []

            for part in parts:
                if "text" in part:
                    text_parts.append(part["text"])
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append({
                        "id": f"call_{fc.get('name', '')}",
                        "type": "function",
                        "function": {
                            "name": fc.get("name", ""),
                            "arguments": json.dumps(fc.get("args", {})),
                        },
                    })

            text = "\n".join(text_parts) if text_parts else None
            usage_meta = response_data.get("usageMetadata", {})

            structured_output = None
            if request.structured_output_schema and text:
                try:
                    structured_output = json.loads(text)
                except json.JSONDecodeError:
                    pass

            return ModelResponse(
                text=text,
                tool_calls=tool_calls if tool_calls else None,
                structured_output=structured_output,
                usage={
                    "prompt_tokens": usage_meta.get("promptTokenCount", 0) if isinstance(usage_meta, dict) else 0,
                    "completion_tokens": usage_meta.get("candidatesTokenCount", 0) if isinstance(usage_meta, dict) else 0,
                },
                provider_specific={
                    "finish_reason": candidates[0].get("finishReason"),
                    "safety_ratings": candidates[0].get("safetyRatings"),
                },
                provider=self.provider_id,
                model=request.model_id,
            )
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderResponseError(
                message=f"Invalid Gemini response: {e}",
                provider=self.provider_id,
                model=request.model_id,
            ) from e
