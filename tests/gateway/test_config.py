"""Tests for Stage 7 Provider Profiles, Registry, and Configuration Types."""
import pytest
from clairecoder.gateway.config import (
    ProviderProfile, ProviderCategory, AdapterType, PROVIDER_REGISTRY,
)


def test_canonical_provider_registry():
    """Verify all 9+ required providers are present in PROVIDER_REGISTRY with correct metadata."""
    required = ["openai", "groq", "anthropic", "gemini", "openrouter", "omniroute", "ollama", "lmstudio", "vllm", "custom"]
    for pid in required:
        assert pid in PROVIDER_REGISTRY, f"Missing required provider {pid}"
        entry = PROVIDER_REGISTRY[pid]
        assert "name" in entry
        assert "adapter" in entry
        assert "category" in entry
        assert "description" in entry

    # Verify categories
    assert PROVIDER_REGISTRY["openai"]["category"] == ProviderCategory.HOSTED
    assert PROVIDER_REGISTRY["groq"]["category"] == ProviderCategory.HOSTED
    assert PROVIDER_REGISTRY["anthropic"]["category"] == ProviderCategory.HOSTED
    assert PROVIDER_REGISTRY["gemini"]["category"] == ProviderCategory.HOSTED
    assert PROVIDER_REGISTRY["openrouter"]["category"] == ProviderCategory.HOSTED
    assert PROVIDER_REGISTRY["omniroute"]["category"] == ProviderCategory.HOSTED
    assert PROVIDER_REGISTRY["ollama"]["category"] == ProviderCategory.LOCAL
    assert PROVIDER_REGISTRY["lmstudio"]["category"] == ProviderCategory.LOCAL
    assert PROVIDER_REGISTRY["vllm"]["category"] == ProviderCategory.LOCAL
    assert PROVIDER_REGISTRY["custom"]["category"] == ProviderCategory.CUSTOM

    # Verify adapter assignments
    assert PROVIDER_REGISTRY["openai"]["adapter"] == AdapterType.OPENAI_COMPATIBLE
    assert PROVIDER_REGISTRY["groq"]["adapter"] == AdapterType.OPENAI_COMPATIBLE
    assert PROVIDER_REGISTRY["anthropic"]["adapter"] == AdapterType.ANTHROPIC
    assert PROVIDER_REGISTRY["gemini"]["adapter"] == AdapterType.GEMINI
    assert PROVIDER_REGISTRY["ollama"]["adapter"] == AdapterType.OLLAMA


def test_provider_profile_serialization():
    """Verify ProviderProfile serialization and deserialization roundtrip."""
    profile = ProviderProfile(
        id="groq-main",
        provider_id="groq",
        name="Groq Cloud",
        adapter_type=AdapterType.OPENAI_COMPATIBLE.value,
        endpoint="https://api.groq.com/openai/v1",
        category=ProviderCategory.HOSTED.value,
        credential_ref="provider:groq-main",
        default_model_id="llama-3.3-70b-versatile",
        available_models=["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
        capabilities={
            "llama-3.3-70b-versatile": ["text", "tool_calling", "streaming"],
            "mixtral-8x7b-32768": ["text", "streaming"],
        },
        provider_specific={"temperature": 0.2},
        enabled=True,
    )

    data = profile.to_dict()
    assert data["id"] == "groq-main"
    assert data["provider_id"] == "groq"
    assert data["credential_ref"] == "provider:groq-main"
    assert len(data["available_models"]) == 2
    assert "llama-3.3-70b-versatile" in data["capabilities"]

    # Reconstruct
    loaded = ProviderProfile.from_dict(data)
    assert loaded.id == profile.id
    assert loaded.provider_id == profile.provider_id
    assert loaded.adapter_type == profile.adapter_type
    assert loaded.endpoint == profile.endpoint
    assert loaded.category == profile.category
    assert loaded.credential_ref == profile.credential_ref
    assert loaded.default_model_id == profile.default_model_id
    assert loaded.available_models == profile.available_models
    assert loaded.capabilities == profile.capabilities
    assert loaded.provider_specific == profile.provider_specific
    assert loaded.enabled == profile.enabled
