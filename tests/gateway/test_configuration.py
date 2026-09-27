"""Tests for ConfigurationManager, Provider Profiles, Persistence, and Multi-Provider Coexistence.

Authorities: CC-PRD-002, CC-ADR-002, CC-PRD-011, CC-ADR-007.
"""
import pytest
from pathlib import Path
from clairecoder.gateway.manager import ConfigurationManager
from clairecoder.gateway.config import ProviderProfile, ProviderCategory, AdapterType, PROVIDER_REGISTRY


def test_configuration_manager_crud(tmp_path):
    """Test full CRUD cycle for provider profiles on disk."""
    manager = ConfigurationManager(workspace_root=str(tmp_path))

    assert manager.list_provider_profiles() == []
    assert not manager.is_configured()

    profile1 = ProviderProfile(
        id="p1",
        provider_id="openai",
        name="OpenAI Main",
        adapter_type=AdapterType.OPENAI_COMPATIBLE.value,
        endpoint="https://api.openai.com/v1",
        category=ProviderCategory.HOSTED.value,
        default_model_id="gpt-4o",
        available_models=["gpt-4o", "gpt-4o-mini"]
    )
    profile2 = ProviderProfile(
        id="p2",
        provider_id="ollama",
        name="Local Ollama",
        adapter_type=AdapterType.OLLAMA.value,
        endpoint="http://localhost:11434",
        category=ProviderCategory.LOCAL.value,
        default_model_id="llama3.2",
        available_models=["llama3.2"]
    )

    # Save both profiles (multi-provider support)
    manager.save_provider_profile(profile1)
    manager.save_provider_profile(profile2)

    profiles = manager.list_provider_profiles()
    assert len(profiles) == 2
    ids = [p.id for p in profiles]
    assert "p1" in ids
    assert "p2" in ids

    # Load single profile
    loaded = manager.load_provider_profile("p1")
    assert loaded is not None
    assert loaded.name == "OpenAI Main"

    # Set active provider and model
    manager.set_active("p1", "gpt-4o")
    assert manager.is_configured() is True
    assert manager.needs_repair() is False

    active = manager.get_active()
    assert active["provider_profile_id"] == "p1"
    assert active["model_id"] == "gpt-4o"

    # Delete profile
    deleted = manager.delete_provider_profile("p2")
    assert deleted is True
    assert len(manager.list_provider_profiles()) == 1


def test_provider_registry_contains_all_v1_providers():
    """Verify registry contains Hosted, Local, and Custom providers per CC-PRD-002."""
    assert "openai" in PROVIDER_REGISTRY
    assert "anthropic" in PROVIDER_REGISTRY
    assert "gemini" in PROVIDER_REGISTRY
    assert "groq" in PROVIDER_REGISTRY
    assert "openrouter" in PROVIDER_REGISTRY
    assert "ollama" in PROVIDER_REGISTRY
    assert "lmstudio" in PROVIDER_REGISTRY
    assert "vllm" in PROVIDER_REGISTRY
    assert "custom" in PROVIDER_REGISTRY


def test_multi_provider_coexistence_and_credential_isolation(tmp_path):
    """Verify multiple provider profiles coexist simultaneously with isolated credentials."""
    from unittest.mock import MagicMock
    mock_cred = MagicMock()
    stored_creds = {}
    mock_cred.store_credential.side_effect = lambda pid, sec: stored_creds.update({pid: sec}) or f"provider:{pid}"
    mock_cred.get_credential.side_effect = lambda pid: stored_creds.get(pid)
    mock_cred.delete_credential.side_effect = lambda pid: stored_creds.pop(pid, None) is not None
    mock_cred.has_credential.side_effect = lambda pid: pid in stored_creds

    mgr = ConfigurationManager(workspace_root=str(tmp_path), credential_store=mock_cred)

    # 1. Configure Ollama (local, no auth)
    p_ollama = ProviderProfile(
        id="ollama-local",
        provider_id="ollama",
        name="Ollama Local",
        adapter_type="ollama",
        endpoint="http://localhost:11434",
        category="local",
        default_model_id="qwen2.5-coder:3b",
        available_models=["qwen2.5-coder:3b"],
    )
    # 2. Configure Groq (hosted, key A)
    p_groq = ProviderProfile(
        id="groq-fast",
        provider_id="groq",
        name="Groq Cloud",
        adapter_type="openai_compatible",
        endpoint="https://api.groq.com/openai/v1",
        category="hosted",
        credential_ref="provider:groq-fast",
        default_model_id="llama-3.3-70b-versatile",
        available_models=["llama-3.3-70b-versatile"],
    )
    mock_cred.store_credential("groq-fast", "gsk_groq_secret_key_AAA")

    # 3. Configure Gemini (hosted, key B)
    p_gemini = ProviderProfile(
        id="gemini-prod",
        provider_id="gemini",
        name="Google Gemini",
        adapter_type="gemini",
        endpoint="https://generativelanguage.googleapis.com",
        category="hosted",
        credential_ref="provider:gemini-prod",
        default_model_id="gemini-2.5-pro",
        available_models=["gemini-2.5-pro"],
    )
    mock_cred.store_credential("gemini-prod", "AIzaSy_gemini_secret_key_BBB")

    mgr.save_provider_profile(p_ollama)
    mgr.save_provider_profile(p_groq)
    mgr.save_provider_profile(p_gemini)

    # Assert all 3 profiles coexist
    profiles = mgr.list_provider_profiles()
    assert len(profiles) == 3
    p_ids = {p.id for p in profiles}
    assert p_ids == {"ollama-local", "groq-fast", "gemini-prod"}

    # Assert credentials remain completely isolated
    assert mock_cred.get_credential("groq-fast") == "gsk_groq_secret_key_AAA"
    assert mock_cred.get_credential("gemini-prod") == "AIzaSy_gemini_secret_key_BBB"
    assert mock_cred.get_credential("ollama-local") is None

    # Switch active between them repeatedly
    mgr.set_active("ollama-local", "qwen2.5-coder:3b")
    assert mgr.get_active() == {"provider_profile_id": "ollama-local", "model_id": "qwen2.5-coder:3b"}

    mgr.set_active("groq-fast", "llama-3.3-70b-versatile")
    assert mgr.get_active() == {"provider_profile_id": "groq-fast", "model_id": "llama-3.3-70b-versatile"}

    mgr.set_active("gemini-prod", "gemini-2.5-pro")
    assert mgr.get_active() == {"provider_profile_id": "gemini-prod", "model_id": "gemini-2.5-pro"}

    # Assert no profiles were overwritten during switching
    assert len(mgr.list_provider_profiles()) == 3

