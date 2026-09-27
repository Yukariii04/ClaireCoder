"""Tests for Stage 7 Model Discovery across OpenAI-compatible, Anthropic, Gemini, and Ollama."""
import pytest
from unittest.mock import patch, MagicMock
from clairecoder.gateway.discovery import (
    discover_models, discover_openai_compatible, discover_anthropic,
    discover_gemini, discover_ollama, _infer_capabilities
)
from clairecoder.gateway.types import Capability


def test_infer_capabilities_heuristics():
    """Verify capability inference logic detects tools, vision, reasoning, and streaming."""
    caps_gpt4 = _infer_capabilities({}, "gpt-4o")
    assert Capability.TEXT in caps_gpt4
    assert Capability.STREAMING in caps_gpt4
    assert Capability.TOOL_CALLING in caps_gpt4

    caps_o1 = _infer_capabilities({}, "o1-preview")
    assert Capability.REASONING in caps_o1

    caps_vision = _infer_capabilities({"vision": True}, "llava-1.5")
    assert Capability.VISION in caps_vision


def test_discover_openai_compatible():
    """Test discovery from OpenAI /v1/models response."""
    mock_payload = {
        "data": [
            {"id": "gpt-4o", "name": "GPT-4o", "context_length": 128000},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context_length": 128000},
        ]
    }

    with patch("clairecoder.gateway.discovery._http_get", return_value=mock_payload):
        models = discover_openai_compatible(
            endpoint="https://api.openai.com/v1",
            api_key="test-key",
            provider_id="openai",
            provider_name="OpenAI"
        )
        assert len(models) == 2
        assert models[0].id == "gpt-4o"
        assert models[0].provider.id == "openai"
        assert models[0].context_capacity == 128000
        assert Capability.TOOL_CALLING in models[0].capabilities


def test_discover_anthropic():
    """Test discovery from Anthropic API and fallback to curated list."""
    # 1. Successful API response
    mock_payload = {
        "data": [
            {"id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4", "context_window": 200000},
        ]
    }
    with patch("clairecoder.gateway.discovery._http_get", return_value=mock_payload):
        models = discover_anthropic(api_key="test-key")
        assert len(models) == 1
        assert models[0].id == "claude-sonnet-4-20250514"
        assert models[0].provider.id == "anthropic"

    # 2. Fallback when API returns error
    with patch("clairecoder.gateway.discovery._http_get", side_effect=Exception("API Error")):
        models = discover_anthropic(api_key="test-key")
        assert len(models) >= 3
        ids = [m.id for m in models]
        assert "claude-sonnet-4-20250514" in ids


def test_discover_gemini():
    """Test discovery from Google Gemini /v1beta/models response."""
    mock_payload = {
        "models": [
            {
                "name": "models/gemini-2.5-pro",
                "displayName": "Gemini 2.5 Pro",
                "supportedGenerationMethods": ["generateContent", "streamGenerateContent"],
                "inputTokenLimit": 1048576,
            },
            {
                "name": "models/embedding-001",
                "displayName": "Embedding 001",
                "supportedGenerationMethods": ["embedContent"],
            }
        ]
    }

    with patch("clairecoder.gateway.discovery._http_get", return_value=mock_payload):
        models = discover_gemini(api_key="test-key")
        assert len(models) == 1  # embedding model skipped
        assert models[0].id == "gemini-2.5-pro"
        assert models[0].display_name == "Gemini 2.5 Pro"
        assert models[0].provider.id == "gemini"
        assert Capability.STREAMING in models[0].capabilities


def test_discover_ollama():
    """Test discovery from local Ollama /api/tags response."""
    mock_payload = {
        "models": [
            {"name": "llama3.2:latest", "details": {"parameter_size": "3B", "families": ["llama"]}},
            {"name": "qwen2.5-coder:7b", "details": {"parameter_size": "7B", "families": ["qwen"]}},
        ]
    }

    with patch("clairecoder.gateway.discovery._http_get", return_value=mock_payload):
        models = discover_ollama()
        assert len(models) == 2
        assert models[0].id == "llama3.2:latest"
        assert models[0].provider.id == "ollama"


def test_unified_discover_dispatcher():
    """Verify discover_models routes correctly based on provider_id."""
    with patch("clairecoder.gateway.discovery.discover_anthropic", return_value=[]) as mock_ant, \
         patch("clairecoder.gateway.discovery.discover_gemini", return_value=[]) as mock_gem, \
         patch("clairecoder.gateway.discovery.discover_ollama", return_value=[]) as mock_oll, \
         patch("clairecoder.gateway.discovery.discover_openai_compatible", return_value=[]) as mock_oai:

        discover_models("anthropic", "https://api.anthropic.com")
        mock_ant.assert_called_once()

        discover_models("gemini", "https://generativelanguage.googleapis.com")
        mock_gem.assert_called_once()

        discover_models("ollama", "http://localhost:11434")
        mock_oll.assert_called_once()

        discover_models("groq", "https://api.groq.com/openai/v1")
        mock_oai.assert_called_once()


def test_normalize_credential_variants():
    """Verify credential normalization handles surrounding quotes, whitespace, and Bearer prefix."""
    from clairecoder.gateway.discovery import normalize_credential

    assert normalize_credential(None) is None
    assert normalize_credential("") is None
    assert normalize_credential("   ") is None
    assert normalize_credential("gsk_valid_key_12345") == "gsk_valid_key_12345"
    # Leading/trailing whitespace & newlines
    assert normalize_credential("  \r\ngsk_valid_key_12345 \n\t") == "gsk_valid_key_12345"
    # Surrounding double quotes
    assert normalize_credential('"gsk_valid_key_12345"') == "gsk_valid_key_12345"
    # Surrounding single quotes
    assert normalize_credential("'gsk_valid_key_12345'") == "gsk_valid_key_12345"
    # Redundant Bearer prefix
    assert normalize_credential("Bearer gsk_valid_key_12345") == "gsk_valid_key_12345"
    assert normalize_credential("bearer  'gsk_valid_key_12345' ") == "gsk_valid_key_12345"


def test_credential_fingerprint_safe_diagnostic():
    """Verify safe diagnostic fingerprinting produces hash without exposing raw secrets."""
    from clairecoder.gateway.discovery import get_credential_fingerprint

    diag_empty = get_credential_fingerprint(None)
    assert diag_empty["is_set"] is False
    assert diag_empty["fingerprint"] is None

    raw_key = "  gsk_my_secret_token_abc123 \n"
    diag = get_credential_fingerprint(raw_key)
    assert diag["is_set"] is True
    assert diag["has_leading_whitespace"] is True
    assert diag["has_trailing_whitespace"] is True
    assert diag["has_newline"] is True
    assert diag["length"] == len("gsk_my_secret_token_abc123")
    assert diag["fingerprint"] is not None
    # Secret itself is never in the returned diagnostic dictionary
    for k, v in diag.items():
        assert "gsk_my_secret" not in str(v)


def test_validation_vs_discovery_separation():
    """Verify validation performs reachability check while discovery parses models once."""
    from clairecoder.gateway.discovery import validate_provider, discover_models

    with patch("clairecoder.gateway.discovery._http_get") as mock_http:
        # 1. Validation check for Ollama
        mock_http.return_value = {"status": "ok"}
        is_valid = validate_provider("ollama", "http://localhost:11434")
        assert is_valid is True
        assert mock_http.call_count == 1
        call_url = mock_http.call_args[0][0]
        assert "/api/tags" in call_url

        # 2. Validation check for Groq
        mock_http.reset_mock()
        mock_http.return_value = {"object": "list", "data": []}
        is_valid_groq = validate_provider("groq", "https://api.groq.com/openai/v1", api_key="gsk_123")
        assert is_valid_groq is True
        assert mock_http.call_count == 1
        headers_passed = mock_http.call_args[1].get("headers", {})
        assert headers_passed.get("Authorization") == "Bearer gsk_123"

        # 3. Discovery happens exactly ONCE after validation
        mock_http.reset_mock()
        mock_http.return_value = {
            "data": [
                {"id": "llama-3.3-70b-versatile", "context_length": 131072},
                {"id": "mixtral-8x7b-32768", "context_length": 32768},
            ]
        }
        models = discover_models("groq", "https://api.groq.com/openai/v1", api_key="gsk_123")
        assert len(models) == 2
        assert mock_http.call_count == 1
        assert models[0].id in ("llama-3.3-70b-versatile", "mixtral-8x7b-32768")

