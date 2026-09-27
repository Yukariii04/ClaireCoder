"""Tests for Local Ollama Adapter (/api/chat, NDJSON streaming, tool mapping)."""
import json
import pytest
from unittest.mock import MagicMock
from clairecoder.gateway.adapters.ollama import OllamaAdapter
from clairecoder.gateway.types import (
    Model, Provider, Endpoint, ModelRequest, ModelResponse, Capability, ModelError, ErrorCategory
)


class MockOllamaHttpClient:
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


def test_ollama_adapter_execution():
    """Test Ollama /api/chat execution and response mapping."""
    mock_resp = {
        "model": "llama3.2:latest",
        "message": {"role": "assistant", "content": "Local model output"},
        "done": True,
        "eval_count": 12,
        "prompt_eval_count": 8,
        "total_duration": 500000000
    }
    http_mock = MockOllamaHttpClient(response_data=mock_resp)
    adapter = OllamaAdapter(http_client=http_mock)

    model = Model(
        id="llama3.2:latest",
        display_name="Llama 3.2",
        provider=Provider(id="ollama", name="Ollama"),
        endpoint=Endpoint(url="http://localhost:11434")
    )

    req = ModelRequest(model_id="llama3.2:latest", messages=[{"role": "user", "content": "hello"}])
    resp = adapter.execute(model, req)

    assert resp.text == "Local model output"
    assert resp.usage["prompt_tokens"] == 8
    assert resp.usage["completion_tokens"] == 12
    assert resp.provider_specific["model"] == "llama3.2:latest"

    # Verify no Authorization header sent to local Ollama
    assert "Authorization" not in http_mock.last_request["headers"]
    assert http_mock.last_request["url"] == "http://localhost:11434/api/chat"


def test_ollama_streaming():
    """Test Ollama streaming with NDJSON format chunks."""
    class MockOllamaStreamClient:
        def post_stream(self, url, headers, data):
            return [
                b'{"model":"llama3.2","message":{"content":"chunk 1"},"done":false}\n',
                b'{"model":"llama3.2","message":{"content":"chunk 2"},"done":false}\n',
                b'{"model":"llama3.2","message":{"content":""},"done":true}\n'
            ]

    adapter = OllamaAdapter(http_client=MockOllamaStreamClient())
    model = Model(id="llama3.2", display_name="Llama 3.2", provider=Provider(id="ollama", name="Ollama"), endpoint=Endpoint(url="http://localhost:11434"))
    req = ModelRequest(model_id="llama3.2", messages=[], stream=True)

    resp = adapter.execute(model, req)
    assert resp.stream_generator is not None
    chunks = list(resp.stream_generator)
    assert len(chunks) == 2
    assert chunks[0].text == "chunk 1"
    assert chunks[1].text == "chunk 2"
