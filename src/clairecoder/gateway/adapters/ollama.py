"""Ollama adapter using the native /api/chat endpoint with reliability hardening.

Ollama has its own chat API format distinct from OpenAI:
  - Endpoint: POST /api/chat
  - No authentication required
  - Streaming: NDJSON (newline-delimited JSON)

Correction #22: Hardened against timeouts, malformed endpoints, empty responses,
and normalized structured provider errors.
"""
import json
import math
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from clairecoder.gateway.discovery import DEFAULT_USER_AGENT
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


class OllamaAdapter(ProviderAdapterInterface):
    """Adapter for Ollama's native /api/chat endpoint with robust reliability handling."""

    # Local model cold starts and CPU inference can exceed standard limits.
    DEFAULT_TIMEOUT_SECONDS = 600.0

    def __init__(
        self,
        http_client: Any = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._http_client = http_client
        try:
            self.timeout_seconds = float(timeout_seconds)
        except (TypeError, ValueError) as e:
            raise ValueError("Ollama timeout_seconds must be a positive number") from e
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Ollama timeout_seconds must be a finite positive number")
        self.last_request_debug: Optional[Dict[str, Any]] = None

    @property
    def provider_id(self) -> str:
        return "ollama"

    def _timeout_error(self, url: str, model_id: Optional[str] = None) -> ProviderTimeoutError:
        return ProviderTimeoutError(
            message=(
                f"Ollama did not respond for {self.timeout_seconds:g} seconds at {url}; "
                "the request timed out. The local model may still be loading or generating."
            ),
            provider=self.provider_id,
            model=model_id,
            operation="chat",
            timeout_seconds=self.timeout_seconds,
        )

    @staticmethod
    def _is_timeout_url_error(error: urllib.error.URLError) -> bool:
        reason = getattr(error, "reason", None)
        return isinstance(reason, TimeoutError) or "timed out" in str(reason).lower()

    def _validate_endpoint(self, raw_endpoint: str) -> str:
        """Validate and normalize Ollama endpoint URL, preventing relative URLs."""
        if not raw_endpoint or not raw_endpoint.strip():
            raise ProviderConnectionError(
                message="Ollama endpoint URL is missing or empty",
                provider=self.provider_id,
            )
        endpoint = raw_endpoint.strip().rstrip("/")
        if endpoint.startswith("/"):
            raise ProviderConnectionError(
                message=f"Relative endpoint URL '{endpoint}' is invalid for Ollama; must be an absolute URL",
                provider=self.provider_id,
            )
        if not self._http_client and not endpoint.startswith(("http://", "https://")):
            raise ProviderConnectionError(
                message=f"Invalid Ollama endpoint URL '{endpoint}': must start with http:// or https://",
                provider=self.provider_id,
            )
        if not endpoint.endswith("/api/chat"):
            endpoint = f"{endpoint}/api/chat"
        return endpoint

    def _make_request(self, url: str, headers: Dict[str, str], data: bytes, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute POST request to Ollama with normalized error mapping."""
        try:
            if self._http_client:
                return self._http_client.post(url, headers=headers, data=data)
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                body_bytes = response.read()
                if not body_bytes:
                    raise ProviderResponseError(
                        message="Ollama returned an empty response body (0 bytes)",
                        provider=self.provider_id,
                        model=model_id,
                        status_code=response.status if hasattr(response, "status") else 200,
                    )
                try:
                    parsed = json.loads(body_bytes.decode("utf-8"))
                except json.JSONDecodeError as jde:
                    raise ProviderResponseError(
                        message=f"Malformed JSON in Ollama response: {jde}",
                        provider=self.provider_id,
                        model=model_id,
                        status_code=200,
                    ) from jde
                if not isinstance(parsed, dict):
                    raise ProviderResponseError(
                        message=f"Expected JSON object from Ollama, got {type(parsed).__name__}",
                        provider=self.provider_id,
                        model=model_id,
                    )
                return parsed
        except urllib.error.HTTPError as e:
            with e:
                body = e.read().decode("utf-8", errors="replace")
            status = e.code
            if status in (401, 403):
                raise ProviderAuthenticationError(
                    message=f"Ollama authentication failed: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
            elif status == 404:
                raise ProviderResponseError(
                    message=f"Ollama model '{model_id}' or endpoint not found (HTTP 404): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=404,
                    retryable=False,
                ) from e
            elif status == 429:
                raise ProviderRateLimitError(
                    message=f"Ollama rate limited (HTTP 429): {body}",
                    provider=self.provider_id,
                    model=model_id,
                ) from e
            elif status >= 500:
                raise ProviderUnavailableError(
                    message=f"Ollama server error (HTTP {status}): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
            else:
                raise ProviderResponseError(
                    message=f"Ollama HTTP {status}: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
        except TimeoutError as e:
            raise self._timeout_error(url, model_id) from e
        except urllib.error.URLError as e:
            if self._is_timeout_url_error(e):
                raise self._timeout_error(url, model_id) from e
            raise ProviderConnectionError(
                message=f"Cannot connect to Ollama at {url}: {e}",
                provider=self.provider_id,
                model=model_id,
            ) from e

    def _make_stream_request(self, url: str, headers: Dict[str, str], data: bytes, model_id: Optional[str] = None) -> Any:
        """Execute streaming POST request to Ollama with normalized error mapping."""
        try:
            if self._http_client and hasattr(self._http_client, "post_stream"):
                return self._http_client.post_stream(url, headers=headers, data=data)
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            return urllib.request.urlopen(req, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as e:
            with e:
                body = e.read().decode("utf-8", errors="replace")
            status = e.code
            if status in (401, 403):
                raise ProviderAuthenticationError(
                    message=f"Ollama authentication failed: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
            elif status == 429:
                raise ProviderRateLimitError(
                    message=f"Ollama rate limited: {body}",
                    provider=self.provider_id,
                    model=model_id,
                ) from e
            elif status >= 500:
                raise ProviderUnavailableError(
                    message=f"Ollama server error (HTTP {status}): {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
            else:
                raise ProviderResponseError(
                    message=f"Ollama HTTP {status}: {body}",
                    provider=self.provider_id,
                    model=model_id,
                    status_code=status,
                ) from e
        except TimeoutError as e:
            raise self._timeout_error(url, model_id) from e
        except urllib.error.URLError as e:
            if self._is_timeout_url_error(e):
                raise self._timeout_error(url, model_id) from e
            raise ProviderConnectionError(
                message=f"Cannot connect to Ollama: {e}",
                provider=self.provider_id,
                model=model_id,
            ) from e

    def execute(self, model: Model, request: ModelRequest) -> ModelResponse:
        url = self._validate_endpoint(model.endpoint.url)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        headers.update(model.endpoint.headers)

        # Record safe debug inspection hook
        self.last_request_debug = {
            "provider_id": self.provider_id,
            "endpoint": url,
            "model_id": request.model_id,
            "adapter": self.__class__.__name__,
        }

        # Convert OpenAI-style messages to Ollama format
        messages = []
        for msg in request.messages:
            converted = {
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            }
            if msg.get("tool_calls"):
                converted["tool_calls"] = msg["tool_calls"]
            if msg.get("tool_call_id"):
                converted["tool_call_id"] = msg["tool_call_id"]
            if msg.get("name"):
                converted["tool_name"] = msg["name"]
            messages.append(converted)

        payload: Dict[str, Any] = {
            "model": request.model_id,
            "messages": messages,
            "stream": request.stream,
        }

        if request.tools:
            payload["tools"] = request.tools

        data = json.dumps(payload).encode("utf-8")

        if request.stream:
            response_stream = self._make_stream_request(url, headers, data, model_id=request.model_id)

            def stream_generator():
                try:
                    for line in response_stream:
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue
                        try:
                            chunk = json.loads(line_str)
                            msg = chunk.get("message", {})
                            text = msg.get("content")
                            if text:
                                yield ModelResponse(
                                    text=text,
                                    provider=self.provider_id,
                                    model=request.model_id,
                                )
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            pass
                except TimeoutError as e:
                    raise self._timeout_error(url, request.model_id) from e
                except urllib.error.URLError as e:
                    if self._is_timeout_url_error(e):
                        raise self._timeout_error(url, request.model_id) from e
                    raise ProviderConnectionError(
                        message=f"Ollama stream disconnected: {e}",
                        provider=self.provider_id,
                        model=request.model_id,
                    ) from e
                finally:
                    close = getattr(response_stream, "close", None)
                    if callable(close):
                        close()

            return ModelResponse(
                stream_generator=stream_generator(),
                provider=self.provider_id,
                model=request.model_id,
            )

        # Non-streaming execution
        response_data = self._make_request(url, headers, data, model_id=request.model_id)

        try:
            msg = response_data.get("message")
            if not isinstance(msg, dict):
                raise ProviderResponseError(
                    message="Ollama response missing 'message' field in payload",
                    provider=self.provider_id,
                    model=request.model_id,
                    status_code=200,
                )

            text = msg.get("content")
            tool_calls_raw = msg.get("tool_calls")

            # Check for completely empty/missing model response
            if text is None and not tool_calls_raw:
                raise ProviderResponseError(
                    message="Ollama returned an empty model response (no content or tool calls)",
                    provider=self.provider_id,
                    model=request.model_id,
                    status_code=200,
                )

            tool_calls = None
            if tool_calls_raw:
                tool_calls = []
                for tc in tool_calls_raw:
                    fn = tc.get("function", {})
                    tool_calls.append({
                        "id": f"call_{fn.get('name', '')}",
                        "type": "function",
                        "function": {
                            "name": fn.get("name", ""),
                            "arguments": json.dumps(fn.get("arguments", {})),
                        },
                    })

            eval_data = response_data.get("eval_count", 0)
            prompt_data = response_data.get("prompt_eval_count", 0)

            return ModelResponse(
                text=text,
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": prompt_data,
                    "completion_tokens": eval_data,
                },
                provider_specific={
                    "model": response_data.get("model"),
                    "done": response_data.get("done"),
                    "total_duration": response_data.get("total_duration"),
                },
                provider=self.provider_id,
                model=request.model_id,
            )
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderResponseError(
                message=f"Invalid Ollama response structure: {e}",
                provider=self.provider_id,
                model=request.model_id,
            ) from e
