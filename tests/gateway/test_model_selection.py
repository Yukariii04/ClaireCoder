"""Tests for Model Selection, Header Synchronization, Active Model Propagation, and Fallback Removal.

Authorities: CC-PRD-002, CC-ADR-002, CC-PRD-011, CC-ADR-007.
"""
import pytest
from unittest.mock import Mock

from clairecoder.app import ClaireCoderV1
from clairecoder.tui.app import TuiApplication
from clairecoder.interaction.controller import InteractionController
from clairecoder.interaction.types import CommandRequest
from clairecoder.tui.states import InputState
from clairecoder.gateway.gateway import ModelGateway
from clairecoder.gateway.manager import ConfigurationManager
from clairecoder.gateway.config import ProviderProfile
from clairecoder.gateway.types import Model, Provider, Endpoint, Capability, ModelRequest, ModelResponse, ModelError
from clairecoder.engine.engine import EngineeringEngine
from clairecoder.engine.types import EngineeringObjective


def test_model_command_listing_and_switching():
    """Verify /model lists available registered models and switches active model."""
    mock_engine = Mock()
    mock_engine._event_subscribers = []
    mock_gw = Mock()

    provider = Provider(id="ollama", name="Ollama")
    ep = Endpoint(url="http://localhost:11434")

    model1 = Model(
        id="qwen2.5-coder:3b",
        display_name="Qwen 2.5 Coder 3B",
        provider=provider,
        endpoint=ep,
        capabilities=[Capability.TEXT, Capability.STREAMING, Capability.TOOL_CALLING],
        context_capacity=32768,
    )
    model2 = Model(
        id="llama3.2:3b",
        display_name="Llama 3.2 3B",
        provider=provider,
        endpoint=ep,
        capabilities=[Capability.TEXT, Capability.STREAMING],
        context_capacity=131072,
    )

    mock_gw._models = {
        "qwen2.5-coder:3b": model1,
        "llama3.2:3b": model2,
    }
    mock_engine._model_gateway = mock_gw
    mock_engine.get_session.return_value = Mock(model_profile=None)

    controller = InteractionController(engine=mock_engine)
    app = TuiApplication(workspace_root="/test/workspace")
    app.connect_controller(controller)
    app.header.session_id = "sess_model_test"

    # Controller command execution returns available models
    resp = controller.execute_command(CommandRequest(command="model", arguments={}, raw_input="/model"))
    assert resp.success is True
    assert "qwen2.5-coder:3b" in resp.message
    assert "llama3.2:3b" in resp.message

    # Bare /model in TUI opens interactive model selector overlay
    app.submit("/model")
    assert app.active_overlay == "model_selector"
    assert app.state == InputState.OVERLAY
    app.close_overlay()

    # Switch model to llama3.2:3b
    app.submit("/model llama3.2:3b")
    assert app.header.model == "llama3.2:3b"
    assert controller.context_capacity == 131072

    # Switch to unknown model produces error and does not change header
    app.submit("/model nonexistent-model")
    assert app.header.model == "llama3.2:3b"
    activities = app.transcript.get_activities()
    assert "Unknown model" in activities[-1].detail


def test_model_switch_header_and_real_request_propagation(tmp_path):
    """Prove end-to-end active model propagation:
    1. Select model A -> Header displays A and next real engine execution sends model_id=A.
    2. Select model B -> Header displays B and next real engine execution sends model_id=B.
    """
    config_mgr = ConfigurationManager(workspace_root=str(tmp_path))

    # Configure two provider profiles
    prof_groq = ProviderProfile(
        id="groq",
        provider_id="groq",
        name="Groq",
        category="hosted",
        adapter_type="openai_compatible",
        endpoint="https://api.groq.com/openai/v1",
        default_model_id="llama-3.3-70b-versatile",
        available_models=["llama-3.3-70b-versatile"],
    )
    prof_ollama = ProviderProfile(
        id="ollama",
        provider_id="ollama",
        name="Ollama",
        category="local",
        adapter_type="ollama",
        endpoint="http://localhost:11434",
        default_model_id="qwen2.5-coder:7b",
        available_models=["qwen2.5-coder:7b"],
    )
    config_mgr.save_provider_profile(prof_groq)
    config_mgr.save_provider_profile(prof_ollama)

    # Initial selection: Groq / llama-3.3-70b-versatile
    config_mgr.set_active("groq", "llama-3.3-70b-versatile")

    # Create app and gateway
    app = ClaireCoderV1(workspace_root=str(tmp_path))
    app.config_manager = config_mgr
    app.load_providers_from_config()

    # Track executed requests
    executed_requests = []
    def spy_execute(req: ModelRequest) -> ModelResponse:
        executed_requests.append(req)
        return ModelResponse(text=f"Response from {req.model_id}", tool_calls=[])

    app.model_gateway.execute = spy_execute

    tui = TuiApplication(workspace_root=str(tmp_path))
    tui.connect_controller(app.interaction_controller)
    tui.connect_config_manager(app.config_manager)

    sid = app.create_session("sess_prop_test")
    tui.header.session_id = sid
    active = config_mgr.get_active()
    tui.header.model = active["model_id"]

    # 1. Verify model A in header
    assert tui.header.model == "llama-3.3-70b-versatile"

    # Submit request under Model A
    app.submit_objective(sid, "Task 1 under Groq", start_background=False)
    app.run(sid, max_cycles=1)

    assert len(executed_requests) > 0
    assert executed_requests[-1].model_id == "llama-3.3-70b-versatile"
    executed_requests.clear()

    # 2. Switch to Model B via /model
    tui.submit("/model qwen2.5-coder:7b")
    assert tui.header.model == "qwen2.5-coder:7b"

    # Submit request under Model B
    app.submit_objective(sid, "Task 2 under Ollama", start_background=False)
    app.run(sid, max_cycles=1)

    assert len(executed_requests) > 0
    assert executed_requests[-1].model_id == "qwen2.5-coder:7b"


def test_unconfigured_model_rejection_no_default_fallback():
    """Verify that if no active model or provider is configured, execution raises ModelError
    instead of silently falling back to 'default-model'.
    """
    app = ClaireCoderV1.create_default()
    sid = app.create_session("sess_no_model")

    app.submit_objective(sid, "Build something", start_background=False)

    with pytest.raises(ModelError) as exc_info:
        app.run(sid)

    assert "No active model configured" in str(exc_info.value)


def test_atomic_switching_matrix_and_capability_sync(tmp_path):
    """Verify full switching matrix across Ollama -> Groq -> Gemini -> Ollama with context and capability updates."""
    config_mgr = ConfigurationManager(workspace_root=str(tmp_path))

    # Profile 1: Ollama
    p_ollama = ProviderProfile(
        id="ollama",
        provider_id="ollama",
        name="Ollama Local",
        category="local",
        adapter_type="ollama",
        endpoint="http://localhost:11434",
        default_model_id="qwen2.5-coder:3b",
        available_models=["qwen2.5-coder:3b"],
        capabilities={"qwen2.5-coder:3b": ["text", "streaming", "tool_calling"]},
        provider_specific={"context_capacities": {"qwen2.5-coder:3b": 32768}},
    )
    # Profile 2: Groq
    p_groq = ProviderProfile(
        id="groq",
        provider_id="groq",
        name="Groq Cloud",
        category="hosted",
        adapter_type="openai_compatible",
        endpoint="https://api.groq.com/openai/v1",
        default_model_id="llama-3.3-70b-versatile",
        available_models=["llama-3.3-70b-versatile"],
        capabilities={"llama-3.3-70b-versatile": ["text", "streaming", "tool_calling", "reasoning"]},
        provider_specific={"context_capacities": {"llama-3.3-70b-versatile": 131072}},
    )
    # Profile 3: Gemini
    p_gemini = ProviderProfile(
        id="gemini",
        provider_id="gemini",
        name="Google Gemini",
        category="hosted",
        adapter_type="gemini",
        endpoint="https://generativelanguage.googleapis.com",
        default_model_id="gemini-2.5-flash",
        available_models=["gemini-2.5-flash"],
        capabilities={"gemini-2.5-flash": ["text", "streaming", "vision", "tool_calling"]},
        provider_specific={"context_capacities": {"gemini-2.5-flash": 1048576}},
    )

    config_mgr.save_provider_profile(p_ollama)
    config_mgr.save_provider_profile(p_groq)
    config_mgr.save_provider_profile(p_gemini)

    config_mgr.set_active("ollama", "qwen2.5-coder:3b")

    app = ClaireCoderV1(workspace_root=str(tmp_path))
    app.config_manager = config_mgr
    app.load_providers_from_config()

    executed_requests = []
    def spy_execute(req: ModelRequest) -> ModelResponse:
        executed_requests.append(req)
        return ModelResponse(text=f"Executed on {req.model_id}", tool_calls=[])

    app.model_gateway.execute = spy_execute

    tui = TuiApplication(workspace_root=str(tmp_path))
    tui.connect_controller(app.interaction_controller)
    tui.connect_config_manager(app.config_manager)

    sid = app.create_session("sess_matrix")
    tui.header.session_id = sid

    # Step 1: Initial state is Ollama
    assert app.get_active_model_id() == "qwen2.5-coder:3b"
    assert app.interaction_controller._context_capacity == 32768

    # Step 2: Switch Ollama -> Groq
    tui.submit("/model groq/llama-3.3-70b-versatile")
    assert app.get_active_model_id() == "llama-3.3-70b-versatile"
    assert tui.header.model == "llama-3.3-70b-versatile"
    assert app.interaction_controller._context_capacity == 131072
    app.submit_objective(sid, "Run under Groq", start_background=False)
    app.run(sid, max_cycles=1)
    assert executed_requests[-1].model_id == "llama-3.3-70b-versatile"

    # Step 3: Switch Groq -> Gemini
    tui.submit("/model gemini/gemini-2.5-flash")
    assert app.get_active_model_id() == "gemini-2.5-flash"
    assert tui.header.model == "gemini-2.5-flash"
    assert app.interaction_controller._context_capacity == 1048576
    app.submit_objective(sid, "Run under Gemini", start_background=False)
    app.run(sid, max_cycles=1)
    assert executed_requests[-1].model_id == "gemini-2.5-flash"

    # Step 4: Switch Gemini -> Ollama
    tui.submit("/model ollama/qwen2.5-coder:3b")
    assert app.get_active_model_id() == "qwen2.5-coder:3b"
    assert tui.header.model == "qwen2.5-coder:3b"
    assert app.interaction_controller._context_capacity == 32768
    app.submit_objective(sid, "Run under Ollama", start_background=False)
    app.run(sid, max_cycles=1)
    assert executed_requests[-1].model_id == "qwen2.5-coder:3b"


def test_failed_model_switch_atomicity_and_recovery(tmp_path):
    """Verify that failed model switch leaves active provider, model, header, and context intact."""
    config_mgr = ConfigurationManager(workspace_root=str(tmp_path))
    p = ProviderProfile(
        id="ollama",
        provider_id="ollama",
        name="Ollama",
        adapter_type="ollama",
        endpoint="http://localhost:11434",
        category="local",
        default_model_id="qwen2.5-coder:3b",
        available_models=["qwen2.5-coder:3b"],
        provider_specific={"context_capacities": {"qwen2.5-coder:3b": 32768}},
    )
    config_mgr.save_provider_profile(p)
    config_mgr.set_active("ollama", "qwen2.5-coder:3b")

    app = ClaireCoderV1(workspace_root=str(tmp_path))
    app.config_manager = config_mgr
    app.load_providers_from_config()

    tui = TuiApplication(workspace_root=str(tmp_path))
    tui.connect_controller(app.interaction_controller)
    tui.connect_config_manager(app.config_manager)
    tui.header.model = "qwen2.5-coder:3b"

    # Attempt invalid switch
    tui.submit("/model invalid_provider/nonexistent_model")

    # Assert old state remains 100% untouched
    assert app.get_active_model_id() == "qwen2.5-coder:3b"
    assert tui.header.model == "qwen2.5-coder:3b"
    assert app.interaction_controller._context_capacity == 32768
    activities = tui.transcript.get_activities()
    assert "Unknown model" in activities[-1].detail

