"""Tests for Native Google Gemini Adapter (generateContent API, Function declarations, Streaming)."""
import json
import pytest
from unittest.mock import MagicMock
from clairecoder.gateway.adapters.gemini import GeminiAdapter
from clairecoder.gateway.types import (
    Model, Provider, Endpoint, ModelRequest, ModelResponse, Capability, ModelError, ErrorCategory
)


class MockGeminiHttpClient:
    def __init__(self, response_data=None, error_code=None, error_body=None):
        self.response_data = response_data
        self.error_code = error_code
        self.error_body = error_body
        self.last_request = None

    def post(self, url, headers, data):
        self.last_request = {"url": url, "headers": headers, "data": json.loads(data.decode("utf-8"))}
        if self.error_code:
            import urllib.error
            from io import BytesIO
            raise urllib.error.HTTPError(url, self.error_code, "Error", headers, BytesIO(self.error_body.encode()))
        return self.response_data


def test_gemini_adapter_execution():
    """Test Gemini generateContent execution and message conversion."""
    mock_resp = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Gemini response text"}],
                    "role": "model"
                },
                "finishReason": "STOP"
            }
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 6}
    }
    http_mock = MockGeminiHttpClient(response_data=mock_resp)
    adapter = GeminiAdapter(auth_token="ai-key-test", http_client=http_mock)

    model = Model(
        id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider=Provider(id="gemini", name="Google Gemini"),
        endpoint=Endpoint(url="https://generativelanguage.googleapis.com")
    )

    req = ModelRequest(
        model_id="gemini-2.5-pro",
        messages=[
            {"role": "system", "content": "You are a software engineer."},
            {"role": "user", "content": "Hello!"}
        ]
    )

    resp = adapter.execute(model, req)

    assert resp.text == "Gemini response text"
    assert resp.usage["prompt_tokens"] == 10
    assert resp.usage["completion_tokens"] == 6

    # Verify request formatting: key in URL, systemInstruction separate
    assert http_mock.last_request is not None
    assert "key=ai-key-test" in http_mock.last_request["url"]
    assert "systemInstruction" in http_mock.last_request["data"]
    assert http_mock.last_request["data"]["systemInstruction"]["parts"][0]["text"] == "You are a software engineer."


def test_gemini_function_call_handling():
    """Test parsing Gemini functionCall in response candidates."""
    mock_resp = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {
                                "name": "read_file",
                                "args": {"path": "src/app.py"}
                            }
                        }
                    ],
                    "role": "model"
                },
                "finishReason": "STOP"
            }
        ],
        "usageMetadata": {}
    }
    http_mock = MockGeminiHttpClient(response_data=mock_resp)
    adapter = GeminiAdapter(auth_token="ai-key-test", http_client=http_mock)

    model = Model(
        id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider=Provider(id="gemini", name="Google Gemini"),
        endpoint=Endpoint(url="https://generativelanguage.googleapis.com")
    )

    req = ModelRequest(model_id="gemini-2.5-pro", messages=[{"role": "user", "content": "read app.py"}])
    resp = adapter.execute(model, req)

    assert resp.tool_calls is not None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0]["function"]["name"] == "read_file"
    assert "src/app.py" in resp.tool_calls[0]["function"]["arguments"]


def test_gemini_error_handling():
    """Verify Gemini 403 maps to AUTHENTICATION error."""
    http_mock = MockGeminiHttpClient(error_code=403, error_body='{"error": {"message": "API key not valid"}}')
    adapter = GeminiAdapter(auth_token="bad-key", http_client=http_mock)

    model = Model(
        id="gemini-2.5-pro",
        display_name="Gemini",
        provider=Provider(id="gemini", name="Google Gemini"),
        endpoint=Endpoint(url="https://generativelanguage.googleapis.com")
    )

    with pytest.raises(ModelError) as exc_info:
        adapter.execute(model, ModelRequest(model_id="gemini-2.5-pro", messages=[]))
    assert exc_info.value.category == ErrorCategory.AUTHENTICATION
