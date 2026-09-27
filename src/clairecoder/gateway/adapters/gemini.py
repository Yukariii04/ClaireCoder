"""Native Google Gemini adapter using the generateContent API.

Gemini uses a distinct API format:
  - Auth: API key as query parameter
  - Endpoint: POST /v1beta/models/{model}:generateContent
  - Streaming: POST /v1beta/models/{model}:streamGenerateContent
"""
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from clairecoder.gateway.interfaces import ProviderAdapterInterface
from clairecoder.gateway.types import (
    Model, ModelRequest, ModelResponse, Capability, ModelError, ErrorCategory,
)


class GeminiAdapter(ProviderAdapterInterface):
    """Native adapter for Google Gemini's generateContent API."""

    def __init__(self, auth_token: Optional[str] = None, http_client: Any = None):
        self._auth_token = auth_token
        self._http_client = http_client

    @property
    def provider_id(self) -> str:
        return "gemini"

    def _make_request(self, url: str, headers: Dict[str, str], data: bytes) -> Dict[str, Any]:
        """Execute POST request to Gemini API."""
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
                    raise ModelError(ErrorCategory.AUTHENTICATION, f"Gemini auth failed: {body}")
                elif e.code == 429:
                    raise ModelError(ErrorCategory.RATE_LIMITING, f"Rate limited: {body}", is_recoverable=True)
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
                    raise ModelError(ErrorCategory.AUTHENTICATION, f"Gemini auth failed: {body}")
                elif e.code == 429:
                    raise ModelError(ErrorCategory.RATE_LIMITING, f"Rate limited: {body}", is_recoverable=True)
                else:
                    raise ModelError(ErrorCategory.ENDPOINT_FAILURE, f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ModelError(ErrorCategory.NETWORK_FAILURE, f"Network error: {e}", is_recoverable=True)

    def _convert_messages(self, messages: List[Dict[str, Any]]) -> tuple:
        """Convert OpenAI-style messages to Gemini format.

        Returns (system_instruction, contents_list).
        """
        system_parts: List[str] = []
        contents: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_parts.append(content if isinstance(content, str) else str(content))
            elif role == "assistant":
                contents.append({
                    "role": "model",
                    "parts": [{"text": content}],
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
        base_url = model.endpoint.url.rstrip("/")
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
            try:
                response_stream = self._make_stream_request(url, headers, data)
            except ModelError as me:
                me.provider_id = self.provider_id
                me.model_id = request.model_id
                raise

            def stream_generator():
                buffer = b""
                for chunk in response_stream:
                    buffer += chunk if isinstance(chunk, bytes) else chunk.encode()
                    # Gemini streams JSON array chunks
                    text = buffer.decode("utf-8", errors="replace")
                    # Try to parse complete JSON objects
                    try:
                        # Gemini returns a JSON array for streaming
                        parsed = json.loads(text.lstrip("[,").rstrip(",]"))
                        candidates = parsed.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    yield ModelResponse(text=part["text"])
                        buffer = b""
                    except (json.JSONDecodeError, ValueError):
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
            candidates = response_data.get("candidates", [])
            if not candidates:
                error_info = response_data.get("error", {})
                if error_info:
                    raise ModelError(
                        ErrorCategory.MODEL_FAILURE,
                        f"Gemini error: {error_info.get('message', 'Unknown')}",
                        provider_id=self.provider_id,
                        model_id=request.model_id,
                    )
                return ModelResponse(text="")

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
                    "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                    "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                },
                provider_specific={
                    "finish_reason": candidates[0].get("finishReason"),
                    "safety_ratings": candidates[0].get("safetyRatings"),
                },
            )
        except (KeyError, IndexError, TypeError) as e:
            raise ModelError(
                category=ErrorCategory.ENDPOINT_FAILURE,
                message=f"Invalid Gemini response: {e}",
                provider_id=self.provider_id,
                model_id=request.model_id,
            )
