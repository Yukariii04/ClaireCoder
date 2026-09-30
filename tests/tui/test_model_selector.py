"""Tests for ModelSelectorOverlay interactive Provider -> Model selection."""
import pytest
from unittest.mock import MagicMock
from clairecoder.tui.model_selector import ModelSelectorOverlay, ModelSelectorStage
from clairecoder.gateway.config import ProviderProfile, AdapterType, ProviderCategory


def test_model_selector_initialization():
    cfg = MagicMock()
    prof = ProviderProfile(
        id="ollama",
        provider_id="ollama",
        name="Ollama",
        adapter_type=AdapterType.OLLAMA.value,
        endpoint="http://localhost:11434",
        category=ProviderCategory.LOCAL.value,
        available_models=["qwen2.5-coder:3b", "llama3.2"],
        enabled=True,
    )
    cfg.list_provider_profiles.return_value = [prof]
    cfg.get_active.return_value = {"provider_profile_id": "ollama", "model_id": "qwen2.5-coder:3b"}

    overlay = ModelSelectorOverlay(config_manager=cfg)
    assert overlay.stage == ModelSelectorStage.PROVIDER_LIST
    assert len(overlay.providers) > 0

    # Find ollama provider item
    ollama_item = next(p for p in overlay.providers if p["id"] == "ollama")
    assert ollama_item["status"] == "[ACTIVE]"
    assert ollama_item["is_configured"] is True


def test_model_selector_navigation_and_selection():
    cfg = MagicMock()
    prof = ProviderProfile(
        id="ollama",
        provider_id="ollama",
        name="Ollama",
        adapter_type=AdapterType.OLLAMA.value,
        endpoint="http://localhost:11434",
        category=ProviderCategory.LOCAL.value,
        available_models=["qwen2.5-coder:3b", "llama3.2"],
        enabled=True,
    )
    cfg.list_provider_profiles.return_value = [prof]
    cfg.get_active.return_value = {"provider_profile_id": "ollama", "model_id": "qwen2.5-coder:3b"}

    overlay = ModelSelectorOverlay(config_manager=cfg)
    selected_switches = []
    overlay.on_select_model = lambda p, m: selected_switches.append((p, m))

    # Move to ollama
    ollama_idx = next(i for i, p in enumerate(overlay.providers) if p["id"] == "ollama")
    overlay.selected_provider_index = ollama_idx

    # Enter -> opens model list
    overlay.handle_key("enter")
    assert overlay.stage == ModelSelectorStage.MODEL_LIST
    assert len(overlay.models) == 2
    assert overlay.models[0]["id"] == "qwen2.5-coder:3b"
    assert overlay.models[1]["id"] == "llama3.2"

    # Select second model (llama3.2)
    overlay.handle_key("down")
    overlay.handle_key("enter")

    assert selected_switches == [("ollama", "llama3.2")]


def test_model_selector_unconfigured_provider_prompt():
    cfg = MagicMock()
    cfg.list_provider_profiles.return_value = []
    cfg.get_active.return_value = {}

    overlay = ModelSelectorOverlay(config_manager=cfg)
    configured_launches = []
    overlay.on_configure_provider = lambda p: configured_launches.append(p)

    # Pick groq (unconfigured)
    groq_idx = next(i for i, p in enumerate(overlay.providers) if p["id"] == "groq")
    overlay.selected_provider_index = groq_idx

    # Enter -> unconfigured prompt
    overlay.handle_key("enter")
    assert overlay.stage == ModelSelectorStage.UNCONFIGURED_PROMPT

    # Enter on prompt -> launches setup callback
    overlay.handle_key("enter")
    assert len(configured_launches) == 1
    assert configured_launches[0]["name"] == "Groq"


def test_model_selector_render_fixed_dimensions():
    cfg = MagicMock()
    prof = ProviderProfile(
        id="ollama",
        provider_id="ollama",
        name="Ollama",
        adapter_type=AdapterType.OLLAMA.value,
        endpoint="http://localhost:11434",
        category=ProviderCategory.LOCAL.value,
        available_models=["qwen2.5-coder:3b"],
        enabled=True,
    )
    cfg.list_provider_profiles.return_value = [prof]
    cfg.get_active.return_value = {"provider_profile_id": "ollama", "model_id": "qwen2.5-coder:3b"}

    overlay = ModelSelectorOverlay(config_manager=cfg)
    rendered = overlay.render(width=58)
    assert len(rendered) > 5
    assert "Select Provider" in rendered[0]
