"""Tests for Stage 7 Configuration Manager (persistence, CRUD, active selection)."""
import pytest
from pathlib import Path
from clairecoder.gateway.manager import ConfigurationManager
from clairecoder.gateway.config import ProviderProfile, ProviderCategory, AdapterType
from clairecoder.gateway.credentials import CredentialStore


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

    # Switch active provider
    manager.set_active("p2", "llama3.2")
    active = manager.get_active()
    assert active["provider_profile_id"] == "p2"

    # Delete profile
    deleted = manager.delete_provider_profile("p2")
    assert deleted is True
    assert manager.load_provider_profile("p2") is None
    assert len(manager.list_provider_profiles()) == 1


def test_configuration_manager_needs_repair_states(tmp_path):
    """Test needs_repair detection when active profile points to missing config."""
    manager = ConfigurationManager(workspace_root=str(tmp_path))

    # Clean state -> not configured, does not need repair
    assert not manager.is_configured()
    assert not manager.needs_repair()

    # Save a profile but don't set active -> needs_repair
    p = ProviderProfile(
        id="p1",
        provider_id="openai",
        name="OpenAI",
        adapter_type=AdapterType.OPENAI_COMPATIBLE.value,
        endpoint="https://api.openai.com/v1",
        category=ProviderCategory.HOSTED.value
    )
    manager.save_provider_profile(p)
    assert manager.needs_repair() is True

    # Set active to a non-existent ID -> needs_repair
    manager.set_active("missing_id", "m1")
    assert manager.needs_repair() is True

    # Set active correctly -> healthy
    manager.set_active("p1", "m1")
    assert manager.needs_repair() is False
    assert manager.is_configured() is True
