"""Ollama adapter using the native /api/chat endpoint.

Ollama has its own chat API format distinct from OpenAI:
  - Endpoint: POST /api/chat
  - No authentication required
  - Streaming: NDJSON (newline-delimited JSON)
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


class OllamaAdapter(ProviderAdapterInterface):
    """Adapter for Ollama's native /api/chat endpoint."""

    # Local model cold starts and CPU inference can exceed the old 120-second limit.
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

    def _timeout_error(self, url: str, model_id: Optional[str] = None) -> ModelError:
        return ModelError(
            ErrorCategory.TIMEOUT,
            (
                f"Ollama did not respond for {self.timeout_seconds:g} seconds at {url}; "
                "the request timed out. The local model may still be loading or generating."
            ),
            provider_id=self.provider_id,
            model_id=model_id,
            is_recoverable=True,
        )

    @staticmethod
    def _is_timeout_url_error(error: urllib.error.URLError) -> bool:
        reason = getattr(error, "reason", None)
        return isinstance(reason, TimeoutError) or "timed out" in str(reason).lower()

    def _make_request(self, url: str, headers: Dict[str, str], data: bytes) -> Dict[str, Any]:
        """Execute POST request to Ollama."""
        try:
            if self._http_client:
                return self._http_client.post(url, headers=headers, data=data)
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            with e:
                body = e.read().decode("utf-8")
                raise ModelError(ErrorCategory.ENDPOINT_FAILURE, f"Ollama HTTP {e.code}: {body}")
        except TimeoutError as e:
            raise self._timeout_error(url) from e
        except urllib.error.URLError as e:
            if self._is_timeout_url_error(e):
                raise self._timeout_error(url) from e
            raise ModelError(
                ErrorCategory.NETWORK_FAILURE,
                f"Cannot connect to Ollama at {url}: {e}",
                is_recoverable=True,
            ) from e

    def _make_stream_request(self, url: str, headers: Dict[str, str], data: bytes) -> Any:
        """Execute streaming POST request to Ollama."""
        try:
            if self._http_client and hasattr(self._http_client, "post_stream"):
                return self._http_client.post_stream(url, headers=headers, data=data)
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            return urllib.request.urlopen(req, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as e:
            with e:
                body = e.read().decode("utf-8")
                raise ModelError(ErrorCategory.ENDPOINT_FAILURE, f"Ollama HTTP {e.code}: {body}")
        except TimeoutError as e:
            raise self._timeout_error(url) from e
        except urllib.error.URLError as e:
            if self._is_timeout_url_error(e):
                raise self._timeout_error(url) from e
            raise ModelError(
                ErrorCategory.NETWORK_FAILURE,
                f"Cannot connect to Ollama: {e}",
                is_recoverable=True,
            ) from e

    def execute(self, model: Model, request: ModelRequest) -> ModelResponse:
        url = model.endpoint.url.rstrip("/")
        if not url.endswith("/api/chat"):
            url = f"{url}/api/chat"

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

        # Convert OpenAI-style messages to Ollama format (same structure)
        messages = []
        for msg in request.messages:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        payload: Dict[str, Any] = {
            "model": request.model_id,
            "messages": messages,
            "stream": request.stream,
        }

        if request.tools:
            # Ollama supports OpenAI-style tool format
            payload["tools"] = request.tools

        data = json.dumps(payload).encode("utf-8")

        if request.stream:
            try:
                response_stream = self._make_stream_request(url, headers, data)
            except ModelError as me:
                me.provider_id = self.provider_id
                me.model_id = request.model_id
                raise

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
                                yield ModelResponse(text=text)
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            pass
                except TimeoutError as e:
                    raise self._timeout_error(url, request.model_id) from e
                except urllib.error.URLError as e:
                    if self._is_timeout_url_error(e):
                        raise self._timeout_error(url, request.model_id) from e
                    raise ModelError(
                        ErrorCategory.NETWORK_FAILURE,
                        f"Ollama stream disconnected: {e}",
                        provider_id=self.provider_id,
                        model_id=request.model_id,
                        is_recoverable=True,
                    ) from e
                finally:
                    close = getattr(response_stream, "close", None)
                    if callable(close):
                        close()

            return ModelResponse(stream_generator=stream_generator())

        # Non-streaming execution
        try:
            response_data = self._make_request(url, headers, data)
        except ModelError as me:
            me.provider_id = self.provider_id
            me.model_id = request.model_id
            raise

        try:
            msg = response_data.get("message", {})
            text = msg.get("content")
            tool_calls_raw = msg.get("tool_calls")

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
            )
        except (KeyError, IndexError, TypeError) as e:
            raise ModelError(
                category=ErrorCategory.ENDPOINT_FAILURE,
                message=f"Invalid Ollama response: {e}",
                provider_id=self.provider_id,
                model_id=request.model_id,
            )
