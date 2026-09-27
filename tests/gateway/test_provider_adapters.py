"""Tests for Provider Adapters (OpenAI-compatible, Anthropic, Gemini, Ollama).

Authorities: CC-PRD-002, CC-ADR-002, CC-PRD-011.
"""
import pytest
from unittest.mock import Mock, patch

from clairecoder.gateway.adapters import (
    OpenAICompatibleAdapter, AnthropicAdapter, GeminiAdapter, OllamaAdapter,
)
from clairecoder.gateway.types import ModelRequest, ModelResponse, Capability, ErrorCategory, ModelError


def test_openai_compatible_adapter_initialization():
    """Verify OpenAICompatibleAdapter initializes for standard and hosted providers."""
    adapter = OpenAICompatibleAdapter(provider_id="groq", auth_token="gsk_test")
    assert adapter.provider_id == "groq"


def test_anthropic_adapter_initialization():
    """Verify AnthropicAdapter initialization."""
    adapter = AnthropicAdapter(auth_token="sk-ant-test")
    assert adapter.provider_id == "anthropic"


def test_gemini_adapter_initialization():
    """Verify GeminiAdapter initialization."""
    adapter = GeminiAdapter(auth_token="AIzaSyTest")
    assert adapter.provider_id == "gemini"


def test_ollama_adapter_initialization():
    """Verify OllamaAdapter initialization without requiring API key."""
    adapter = OllamaAdapter()
    assert adapter.provider_id == "ollama"


def test_ollama_adapter_request_inspection_hook():
    """Verify Ollama adapter records safe debug inspection hook without leaking secrets."""
    from clairecoder.gateway.types import Model, Provider, Endpoint

    mock_client = Mock()
    mock_client.post.return_value = {
        "message": {"role": "assistant", "content": "Hello from Qwen!"},
        "done": True,
    }

    adapter = OllamaAdapter(http_client=mock_client)
    provider = Provider(id="ollama", name="Ollama")
    ep = Endpoint(url="http://localhost:11434")
    model = Model(id="qwen2.5-coder:3b", display_name="Qwen 2.5 Coder 3B", provider=provider, endpoint=ep)
    req = ModelRequest(model_id="qwen2.5-coder:3b", messages=[{"role": "user", "content": "Hi"}])

    resp = adapter.execute(model, req)
    assert resp.text == "Hello from Qwen!"
    assert adapter.last_request_debug is not None
    assert adapter.last_request_debug["provider_id"] == "ollama"
    assert adapter.last_request_debug["endpoint"] == "http://localhost:11434/api/chat"
    assert adapter.last_request_debug["model_id"] == "qwen2.5-coder:3b"
    assert adapter.last_request_debug["adapter"] == "OllamaAdapter"


def test_openai_compatible_groq_request_format():
    """Verify Groq/OpenAI request carries correct User-Agent, normalized auth header, and exact model ID."""
    from clairecoder.gateway.types import Model, Provider, Endpoint
    from clairecoder.gateway.discovery import DEFAULT_USER_AGENT

    mock_client = Mock()
    mock_client.post.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Groq response"}}]
    }

    adapter = OpenAICompatibleAdapter(provider_id="groq", auth_token="  'gsk_secret_123' \n", http_client=mock_client)
    provider = Provider(id="groq", name="Groq")
    ep = Endpoint(url="https://api.groq.com/openai/v1")
    model = Model(id="llama-3.3-70b-versatile", display_name="Llama 3.3 70B", provider=provider, endpoint=ep)
    req = ModelRequest(model_id="llama-3.3-70b-versatile", messages=[{"role": "user", "content": "Build tool"}])

    resp = adapter.execute(model, req)
    assert resp.text == "Groq response"

    # Verify posted request headers and payload
    call_args = mock_client.post.call_args
    posted_url = call_args[0][0]
    posted_headers = call_args[1]["headers"]
    posted_payload = call_args[1]["data"]

    assert posted_url == "https://api.groq.com/openai/v1/chat/completions"
    assert posted_headers["User-Agent"] == DEFAULT_USER_AGENT
    assert posted_headers["Authorization"] == "Bearer gsk_secret_123"
    import json
    parsed_body = json.loads(posted_payload.decode("utf-8"))
    assert parsed_body["model"] == "llama-3.3-70b-versatile"

