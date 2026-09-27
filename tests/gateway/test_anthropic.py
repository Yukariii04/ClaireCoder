"""Tests for Native Anthropic Adapter (Messages API, Tool conversion, Streaming)."""
import json
import pytest
from unittest.mock import MagicMock
from clairecoder.gateway.adapters.anthropic import AnthropicAdapter
from clairecoder.gateway.types import (
    Model, Provider, Endpoint, ModelRequest, ModelResponse, Capability, ModelError, ErrorCategory
)


class MockAnthropicHttpClient:
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


def test_anthropic_adapter_execution():
    """Test Anthropic Messages API execution and message conversion."""
    mock_resp = {
        "content": [{"type": "text", "text": "Claude response"}],
        "usage": {"input_tokens": 15, "output_tokens": 8},
        "stop_reason": "end_turn",
        "model": "claude-sonnet-4-20250514"
    }
    http_mock = MockAnthropicHttpClient(response_data=mock_resp)
    adapter = AnthropicAdapter(auth_token="sk-ant-test", http_client=http_mock)

    model = Model(
        id="claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        provider=Provider(id="anthropic", name="Anthropic"),
        endpoint=Endpoint(url="https://api.anthropic.com")
    )

    req = ModelRequest(
        model_id="claude-sonnet-4-20250514",
        messages=[
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": "Hello!"}
        ]
    )

    resp = adapter.execute(model, req)

    assert resp.text == "Claude response"
    assert resp.usage["prompt_tokens"] == 15
    assert resp.usage["completion_tokens"] == 8
    assert resp.provider_specific["stop_reason"] == "end_turn"

    # Verify request formatting: system prompt separated from messages
    assert http_mock.last_request is not None
    assert http_mock.last_request["data"]["system"] == "You are a helpful coding assistant."
    assert len(http_mock.last_request["data"]["messages"]) == 1
    assert http_mock.last_request["data"]["messages"][0]["role"] == "user"
    assert http_mock.last_request["headers"]["x-api-key"] == "sk-ant-test"


def test_anthropic_tool_conversion_and_execution():
    """Test converting OpenAI-style tools to Anthropic format and parsing tool_use response."""
    mock_resp = {
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_01A09q90tc1q09qlkj",
                "name": "run_command",
                "input": {"command": "pytest"}
            }
        ],
        "usage": {"input_tokens": 20, "output_tokens": 12},
        "stop_reason": "tool_use"
    }
    http_mock = MockAnthropicHttpClient(response_data=mock_resp)
    adapter = AnthropicAdapter(auth_token="sk-ant-test", http_client=http_mock)

    model = Model(
        id="claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        provider=Provider(id="anthropic", name="Anthropic"),
        endpoint=Endpoint(url="https://api.anthropic.com")
    )

    tools = [{
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute shell command",
            "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}
        }
    }]

    req = ModelRequest(model_id="claude-sonnet-4-20250514", messages=[{"role": "user", "content": "run tests"}], tools=tools)
    resp = adapter.execute(model, req)

    assert resp.tool_calls is not None
    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc["function"]["name"] == "run_command"
    assert "pytest" in tc["function"]["arguments"]


def test_anthropic_error_mapping():
    """Verify HTTP status codes map to correct ModelError categories."""
    http_mock = MockAnthropicHttpClient(error_code=401, error_body='{"error": {"type": "authentication_error"}}')
    adapter = AnthropicAdapter(auth_token="bad-key", http_client=http_mock)

    model = Model(
        id="claude-sonnet-4-20250514",
        display_name="Claude",
        provider=Provider(id="anthropic", name="Anthropic"),
        endpoint=Endpoint(url="https://api.anthropic.com")
    )

    with pytest.raises(ModelError) as exc_info:
        adapter.execute(model, ModelRequest(model_id="claude-sonnet-4-20250514", messages=[]))
    assert exc_info.value.category == ErrorCategory.AUTHENTICATION
