"""Native Anthropic adapter using the Messages API.

Anthropic uses its own request/response format distinct from OpenAI:
  - Auth: x-api-key header
  - Endpoint: POST /v1/messages
  - Streaming: SSE with event types (message_start, content_block_delta, message_stop)
"""
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from clairecoder.gateway.interfaces import ProviderAdapterInterface
from clairecoder.gateway.types import (
    Model, ModelRequest, ModelResponse, Capability, ModelError, ErrorCategory,
)


class AnthropicAdapter(ProviderAdapterInterface):
    """Native adapter for Anthropic's Messages API (Claude models)."""

    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(self, auth_token: Optional[str] = None, http_client: Any = None):
        self._auth_token = auth_token
        self._http_client = http_client

    @property
    def provider_id(self) -> str:
        return "anthropic"

    def _make_request(self, url: str, headers: Dict[str, str], data: bytes) -> Dict[str, Any]:
        """Execute POST request to Anthropic API."""
        try:
            if self._http_client:
                return self._http_client.post(url, headers=headers, data=data)
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            with e:
                body = e.read().decode("utf-8")
                if e.code in (401, 403):
                    raise ModelError(ErrorCategory.AUTHENTICATION, f"Anthropic auth failed: {body}")
                elif e.code == 429:
                    raise ModelError(ErrorCategory.RATE_LIMITING, f"Rate limited: {body}", is_recoverable=True)
                elif e.code == 529:
                    raise ModelError(ErrorCategory.ENDPOINT_FAILURE, f"Anthropic overloaded: {body}", is_recoverable=True)
                else:
                    raise ModelError(ErrorCategory.ENDPOINT_FAILURE, f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ModelError(ErrorCategory.NETWORK_FAILURE, f"Network error: {e}", is_recoverable=True)

    def _make_stream_request(self, url: str, headers: Dict[str, str], data: bytes) -> Any:
        """Execute streaming POST request."""
        try:
            if self._http_client and hasattr(self._http_client, "post_stream"):
                return self._http_client.post_stream(url, headers=headers, data=data)
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            return urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            with e:
                body = e.read().decode("utf-8")
                if e.code in (401, 403):
                    raise ModelError(ErrorCategory.AUTHENTICATION, f"Anthropic auth failed: {body}")
                elif e.code == 429:
                    raise ModelError(ErrorCategory.RATE_LIMITING, f"Rate limited: {body}", is_recoverable=True)
                else:
                    raise ModelError(ErrorCategory.ENDPOINT_FAILURE, f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ModelError(ErrorCategory.NETWORK_FAILURE, f"Network error: {e}", is_recoverable=True)

    def _convert_messages(self, messages: List[Dict[str, Any]]) -> tuple:
        """Convert OpenAI-style messages to Anthropic format.

        Returns (system_prompt, messages_list).
        Anthropic requires system prompt separate from messages.
        """
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
        url = model.endpoint.url.rstrip("/")
        if not url.endswith("/v1/messages"):
            url = f"{url}/v1/messages"

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
            try:
                response_stream = self._make_stream_request(url, headers, data)
            except ModelError as me:
                me.provider_id = self.provider_id
                me.model_id = request.model_id
                raise

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
                                yield ModelResponse(text=delta.get("text"))
                            elif delta.get("type") == "input_json_delta":
                                yield ModelResponse(text=delta.get("partial_json"))
                    except (json.JSONDecodeError, KeyError):
                        pass

            return ModelResponse(stream_generator=stream_generator())

        # Non-streaming execution
        try:
            response_data = self._make_request(url, headers, data)
        except ModelError as me:
            me.provider_id = self.provider_id
            me.model_id = request.model_id
            raise

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
                    "prompt_tokens": usage_data.get("input_tokens", 0),
                    "completion_tokens": usage_data.get("output_tokens", 0),
                },
                provider_specific={
                    "stop_reason": response_data.get("stop_reason"),
                    "model": response_data.get("model"),
                },
            )
        except (KeyError, IndexError, TypeError) as e:
            raise ModelError(
                category=ErrorCategory.ENDPOINT_FAILURE,
                message=f"Invalid Anthropic response: {e}",
                provider_id=self.provider_id,
                model_id=request.model_id,
            )
