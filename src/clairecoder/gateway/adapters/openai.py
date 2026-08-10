import json
from typing import List, Dict, Any, Optional
import urllib.request
import urllib.error

from clairecoder.gateway.interfaces import ProviderAdapterInterface
from clairecoder.gateway.types import Model, ModelRequest, ModelResponse, Capability, ModelError, ErrorCategory

class OpenAICompatibleAdapter(ProviderAdapterInterface):
    """
    Adapter for OpenAI-compatible APIs (OpenAI, Local Runtimes like vLLM/LMStudio).
    Supports injecting an optional `http_client` mock for testing.
    """
    def __init__(self, provider_id: str = "openai-compatible", auth_token: Optional[str] = None, http_client: Any = None):
        self._provider_id = provider_id
        self._auth_token = auth_token
        self._http_client = http_client

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def _make_http_request(self, url: str, headers: Dict[str, str], data: bytes) -> Dict[str, Any]:
        """Wrap urllib to allow easy testing isolation and mock injection."""
        try:
            if self._http_client:
                # If a test mock is provided, use it
                return self._http_client.post(url, headers=headers, data=data)
                
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            with e:
                error_body = e.read().decode("utf-8")
                if e.code in (401, 403):
                    raise ModelError(ErrorCategory.AUTHENTICATION, f"Authentication failed: {error_body}")
                elif e.code == 429:
                    raise ModelError(ErrorCategory.RATE_LIMITING, f"Rate limited: {error_body}", is_recoverable=True)
                else:
                    raise ModelError(ErrorCategory.ENDPOINT_FAILURE, f"HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise ModelError(ErrorCategory.NETWORK_FAILURE, f"Network error: {str(e)}", is_recoverable=True)

    def _make_http_stream(self, url: str, headers: Dict[str, str], data: bytes) -> Any:
        try:
            if self._http_client and hasattr(self._http_client, "post_stream"):
                return self._http_client.post_stream(url, headers=headers, data=data)
            
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            return urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            with e:
                error_body = e.read().decode("utf-8")
                if e.code in (401, 403):
                    raise ModelError(ErrorCategory.AUTHENTICATION, f"Authentication failed: {error_body}")
                elif e.code == 429:
                    raise ModelError(ErrorCategory.RATE_LIMITING, f"Rate limited: {error_body}", is_recoverable=True)
                else:
                    raise ModelError(ErrorCategory.ENDPOINT_FAILURE, f"HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise ModelError(ErrorCategory.NETWORK_FAILURE, f"Network error: {str(e)}", is_recoverable=True)

    def execute(self, model: Model, request: ModelRequest) -> ModelResponse:
        url = model.endpoint.url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"

        headers = {
            "Content-Type": "application/json"
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
            try:
                response_stream = self._make_http_stream(url, headers, data)
            except ModelError as me:
                me.provider_id = self.provider_id
                me.model_id = request.model_id
                raise
                
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
                            yield ModelResponse(text=text, tool_calls=tool_calls)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
            return ModelResponse(stream_generator=stream_generator())
        
        # Execute request
        try:
            response_data = self._make_http_request(url, headers, data)
        except ModelError as me:
            me.provider_id = self.provider_id
            me.model_id = request.model_id
            raise

        # Parse response
        try:
            choice = response_data["choices"][0]
            message = choice.get("message", {})
            
            text = message.get("content")
            tool_calls = message.get("tool_calls")
            
            structured_output = None
            if request.structured_output_schema and text:
                try:
                    structured_output = json.loads(text)
                except json.JSONDecodeError:
                    raise ModelError(
                        category=ErrorCategory.ENDPOINT_FAILURE,
                        message="Provider returned invalid JSON for structured output",
                        provider_id=self.provider_id,
                        model_id=request.model_id
                    )
            
            usage = response_data.get("usage", {})
            
            return ModelResponse(
                text=text,
                tool_calls=tool_calls,
                structured_output=structured_output,
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0)
                },
                provider_specific={"finish_reason": choice.get("finish_reason")}
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                category=ErrorCategory.ENDPOINT_FAILURE,
                message=f"Invalid response format from provider: {str(e)}",
                provider_id=self.provider_id,
                model_id=request.model_id
            )
