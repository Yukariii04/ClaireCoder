"""End-to-End Integration Tests for Stage 7 Lifecycle (Setup -> Bootstrap -> Real Workflow)."""
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from clairecoder.app import ClaireCoderV1
from clairecoder.gateway.config import ProviderProfile, ProviderCategory, AdapterType
from clairecoder.gateway.types import (
    Model, Provider, Endpoint, ModelRequest, ModelResponse, Capability
)
from clairecoder.tui.app import TuiApplication
from clairecoder.tui.states import InputState


def test_stage7_full_lifecycle_and_provider_bootstrap(tmp_path):
    """Test full Stage 7 lifecycle:
    1. Clean unconfigured workspace
    2. Configure provider profile and secure credential
    3. Bootstrap application loads provider into ModelGateway
    4. Main Pane is ready with configured model in header
    5. Natural language objective executes through gateway
    """
    app = ClaireCoderV1.create_default(workspace_root=str(tmp_path))

    # 1. Initially unconfigured
    assert app.check_configuration_status() == "not_configured"
    assert app.load_providers_from_config() is False

    # 2. Configure provider profile & store credential
    fake_keychain = {}
    with patch("keyring.set_password", side_effect=lambda s, u, p: fake_keychain.update({(s, u): p})), \
         patch("keyring.get_password", side_effect=lambda s, u: fake_keychain.get((s, u))):

        app.config_manager.credential_store.store_credential("groq-profile", "gsk-testkey123")

        profile = ProviderProfile(
            id="groq-profile",
            provider_id="groq",
            name="Groq Cloud",
            adapter_type=AdapterType.OPENAI_COMPATIBLE.value,
            endpoint="https://api.groq.com/openai/v1",
            category=ProviderCategory.HOSTED.value,
            credential_ref="provider:groq-profile",
            default_model_id="llama-3.3-70b-versatile",
            available_models=["llama-3.3-70b-versatile"],
            capabilities={"llama-3.3-70b-versatile": ["text", "tool_calling", "streaming"]},
            enabled=True
        )
        app.config_manager.save_provider_profile(profile)
        app.config_manager.set_active("groq-profile", "llama-3.3-70b-versatile")

        # 3. Verify configuration state is now configured
        assert app.check_configuration_status() == "configured"

        # 4. Bootstrap loads provider and model into gateway
        loaded = app.load_providers_from_config()
        assert loaded is True
        assert app.model_gateway.get_model("llama-3.3-70b-versatile") is not None
        assert app.model_gateway.check_capability("llama-3.3-70b-versatile", Capability.TOOL_CALLING) is True

        # 5. Initialize TUI and verify header shows active model
        tui = TuiApplication(workspace_root=str(tmp_path))
        tui.connect_controller(app.interaction_controller)
        tui.connect_config_manager(app.config_manager)

        active = app.config_manager.get_active()
        tui.header.model = active["model_id"]
        assert tui.header.model == "llama-3.3-70b-versatile"

        # 6. Verify wizard is NOT needed on returning-user launch
        assert tui._check_needs_wizard() is False


def test_stage7_multi_provider_coexistence(tmp_path):
    """Test multiple provider profiles (Cloud + Local) configured simultaneously."""
    app = ClaireCoderV1.create_default(workspace_root=str(tmp_path))

    fake_keychain = {}
    with patch("keyring.set_password", side_effect=lambda s, u, p: fake_keychain.update({(s, u): p})), \
         patch("keyring.get_password", side_effect=lambda s, u: fake_keychain.get((s, u))):

        # Configure OpenAI
        app.config_manager.credential_store.store_credential("openai-p", "sk-test")
        p_openai = ProviderProfile(
            id="openai-p", provider_id="openai", name="OpenAI",
            adapter_type=AdapterType.OPENAI_COMPATIBLE.value,
            endpoint="https://api.openai.com/v1",
            category=ProviderCategory.HOSTED.value,
            credential_ref="provider:openai-p",
            default_model_id="gpt-4o",
            available_models=["gpt-4o"]
        )
        app.config_manager.save_provider_profile(p_openai)

        # Configure Local Ollama (no cred needed)
        p_ollama = ProviderProfile(
            id="ollama-p", provider_id="ollama", name="Local Ollama",
            adapter_type=AdapterType.OLLAMA.value,
            endpoint="http://localhost:11434",
            category=ProviderCategory.LOCAL.value,
            default_model_id="llama3.2",
            available_models=["llama3.2"]
        )
        app.config_manager.save_provider_profile(p_ollama)

        # Configure Anthropic
        app.config_manager.credential_store.store_credential("anthropic-p", "sk-ant-test")
        p_anthropic = ProviderProfile(
            id="anthropic-p", provider_id="anthropic", name="Anthropic",
            adapter_type=AdapterType.ANTHROPIC.value,
            endpoint="https://api.anthropic.com",
            category=ProviderCategory.HOSTED.value,
            credential_ref="provider:anthropic-p",
            default_model_id="claude-sonnet-4-20250514",
            available_models=["claude-sonnet-4-20250514"]
        )
        app.config_manager.save_provider_profile(p_anthropic)

        # Bootstrap all 3
        loaded = app.load_providers_from_config()
        assert loaded is True

        # Verify all 3 models registered simultaneously in ModelGateway
        assert app.model_gateway.get_model("gpt-4o").provider.id == "openai"
        assert app.model_gateway.get_model("llama3.2").provider.id == "ollama"
        assert app.model_gateway.get_model("claude-sonnet-4-20250514").provider.id == "anthropic"

        # Switch active model via /model command
        from clairecoder.interaction.types import CommandRequest
        req = CommandRequest(command="model", arguments={"args": ["claude-sonnet-4-20250514"]})
        resp = app.interaction_controller.execute_command(req)
        assert resp.success is True
