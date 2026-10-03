"""Native Anthropic adapter using the Messages API with reliability hardening.

Anthropic uses its own request/response format distinct from OpenAI:
  - Auth: x-api-key header
  - Endpoint: POST /v1/messages
  - Streaming: SSE with event types (message_start, content_block_delta, message_stop)

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


class AnthropicAdapter(ProviderAdapterInterface):
    """Native adapter for Anthropic's Messages API (Claude models) with reliability hardening."""

    ANTHROPIC_VERSION = "2023-06-01"
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
            raise ValueError("Anthropic timeout_seconds must be a positive number") from e
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Anthropic timeout_seconds must be a finite positive number")

    @property
    def provider_id(self) -> str:
        return "anthropic"

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
                message="Anthropic endpoint URL is missing or empty",
                provider=self.provider_id,
            )
        endpoint = raw_endpoint.strip().rstrip("/")
        if endpoint.startswith("/"):
            raise ProviderConnectionError(
                message=f"Relative endpoint URL '{endpoint}' is invalid for Anthropic; must be an absolute URL",
                provider=self.provider_id,
            )
        if not self._http_client and not endpoint.startswith(("http://", "https://")):
            raise ProviderConnectionError(
                message=f"Invalid Anthropic endpoint URL '{endpoint}': must start with http:// or https://",
                provider=self.provider_id,
            )
        if not endpoint.endswith("/v1/messages"):
            endpoint = f"{endpoint}/v1/messages"
        return endpoint

    def _make_request(
        self, url: str, headers: Dict[str, str], data: bytes, model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute POST request to Anthropic API with normalized error mapping."""
        try:
            if self._http_client:
                return self._http_client.post(url, headers=headers, data=data)
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                body_bytes = response.read()
                if not body_bytes:
                    raise ProviderResponseError(
                        message="Anthropic returned an empty response body (0 bytes)",
                        provider=self.provider_id,
                        model=model_id,
                        status_code=getattr(response, "status", 200),
                    )
                try:
                    return json.loads(body_bytes.decode("utf-8"))
                except json.JSONDecodeError as jde:
                    raise ProviderResponseError(
                        message=f"Malformed JSON in Anthropic response: {jde}",
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
                    message=f"Anthropic auth failed (HTTP {status}): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
            elif status == 429:
                raise ProviderRateLimitError(
                    message=f"Anthropic rate limited (HTTP 429): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    retry_after=retry_after,
                ) from e
            elif status == 529 or status >= 500:
                raise ProviderUnavailableError(
                    message=f"Anthropic unavailable/overloaded (HTTP {status}): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                    retry_after=retry_after,
                ) from e
            else:
                raise ProviderResponseError(
                    message=f"Anthropic HTTP {status}: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
        except TimeoutError as e:
            raise ProviderTimeoutError(
                message=f"Anthropic request timed out after {self.timeout_seconds:g}s",
                provider=self.provider_id,
                model=model_id,
                timeout_seconds=self.timeout_seconds,
            ) from e
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise ProviderTimeoutError(
                    message=f"Anthropic request timed out after {self.timeout_seconds:g}s",
                    provider=self.provider_id,
                    model=model_id,
                    timeout_seconds=self.timeout_seconds,
                ) from e
            raise ProviderConnectionError(
                message=f"Network error connecting to Anthropic at {url}: {e}",
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
                    message=f"Anthropic auth failed (HTTP {status}): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
            elif status == 429:
                raise ProviderRateLimitError(
                    message=f"Rate limited: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    retry_after=retry_after,
                ) from e
            elif status >= 500:
                raise ProviderUnavailableError(
                    message=f"Anthropic server error (HTTP {status}): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                    retry_after=retry_after,
                ) from e
            else:
                raise ProviderResponseError(
                    message=f"HTTP {status}: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
        except TimeoutError as e:
            raise ProviderTimeoutError(
                message=f"Anthropic stream request timed out after {self.timeout_seconds:g}s",
                provider=self.provider_id,
                model=model_id,
                timeout_seconds=self.timeout_seconds,
            ) from e
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise ProviderTimeoutError(
                    message=f"Anthropic stream request timed out after {self.timeout_seconds:g}s",
                    provider=self.provider_id,
                    model=model_id,
                    timeout_seconds=self.timeout_seconds,
                ) from e
            raise ProviderConnectionError(
                message=f"Network error connecting to Anthropic stream: {e}",
                provider=self.provider_id,
                model=model_id,
            ) from e

    def _convert_messages(self, messages: List[Dict[str, Any]]) -> tuple:
        """Convert OpenAI-style messages to Anthropic format."""
        system_parts: List[str] = []
        anthropic_msgs: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_parts.append(content if isinstance(content, str) else str(content))
            elif role == "assistant":
                anthropic_msgs.append({"role": "assistant", "content": content})
            else:
                anthropic_msgs.append({"role": "user", "content": content})

        system_prompt = "\n\n".join(system_parts) if system_parts else None
        return system_prompt, anthropic_msgs

    def _convert_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """Convert OpenAI-style tool definitions to Anthropic format."""
        if not tools:
            return None
        anthropic_tools = []
        for tool in tools:
            fn = tool.get("function", tool)
            anthropic_tools.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {}),
            })
        return anthropic_tools

    def execute(self, model: Model, request: ModelRequest) -> ModelResponse:
        url = self._validate_endpoint(model.endpoint.url)

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": self.ANTHROPIC_VERSION,
        }
        headers.update(model.endpoint.headers)
        if self._auth_token:
            headers["x-api-key"] = self._auth_token

        system_prompt, msgs = self._convert_messages(request.messages)

        payload: Dict[str, Any] = {
            "model": request.model_id,
            "messages": msgs,
            "max_tokens": request.provider_specific.get("max_tokens", 8192),
        }
        if system_prompt:
            payload["system"] = system_prompt
        if request.stream:
            payload["stream"] = True

        tools = self._convert_tools(request.tools)
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")

        if request.stream:
            response_stream = self._make_stream_request(url, headers, data, model_id=request.model_id)

            def stream_generator():
                for line in response_stream:
                    line_str = line.decode("utf-8").strip()
                    if not line_str or not line_str.startswith("data: "):
                        continue
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        event_type = event.get("type", "")
                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield ModelResponse(
                                    text=delta.get("text"),
                                    provider=self.provider_id,
                                    model=request.model_id,
                                )
                            elif delta.get("type") == "input_json_delta":
                                yield ModelResponse(
                                    text=delta.get("partial_json"),
                                    provider=self.provider_id,
                                    model=request.model_id,
                                )
                    except (json.JSONDecodeError, KeyError):
                        pass

            return ModelResponse(
                stream_generator=stream_generator(),
                provider=self.provider_id,
                model=request.model_id,
            )

        # Non-streaming execution
        response_data = self._make_request(url, headers, data, model_id=request.model_id)

        try:
            content_blocks = response_data.get("content", [])
            text_parts = []
            tool_calls = []

            for block in content_blocks:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": json.dumps(block.get("input", {})),
                        },
                    })

            text = "\n".join(text_parts) if text_parts else None
            usage_data = response_data.get("usage", {})

            return ModelResponse(
                text=text,
                tool_calls=tool_calls if tool_calls else None,
                usage={
                    "prompt_tokens": usage_data.get("input_tokens", 0) if isinstance(usage_data, dict) else 0,
                    "completion_tokens": usage_data.get("output_tokens", 0) if isinstance(usage_data, dict) else 0,
                },
                provider_specific={
                    "stop_reason": response_data.get("stop_reason"),
                    "model": response_data.get("model"),
                },
                provider=self.provider_id,
                model=request.model_id,
            )
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderResponseError(
                message=f"Invalid Anthropic response: {e}",
                provider=self.provider_id,
                model=request.model_id,
            ) from e
