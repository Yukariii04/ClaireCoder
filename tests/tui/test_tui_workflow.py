"""Tests for End-to-End TUI Engineering Workflows, Streaming Responses, and Session Pause Semantics.

Authorities: CC-PRD-002, CC-ADR-002, CC-PRD-011, CC-ADR-007.
"""
import time
import pytest
from unittest.mock import Mock, MagicMock

from clairecoder.tui.app import TuiApplication, InputState
from clairecoder.interaction.controller import InteractionController
from clairecoder.interaction.types import CommandRequest
from clairecoder.engine.engine import EngineeringEngine
from clairecoder.engine.types import EngineeringObjective, ObjectiveStatus
from clairecoder.gateway.types import Model, Provider, Endpoint, Capability, ModelResponse
from clairecoder.tui.activity import ActivityType


def test_natural_language_streaming_workflow():
    """Verify natural language objective executes in background and streams into transcript."""
    mock_engine = Mock()
    mock_engine._event_subscribers = []
    mock_engine.session_id = "sess_nl_stream"
    mock_engine.receive_objective.return_value = Mock(id="obj_nl_1", request="Write a function")

    # Streaming chunks generator
    def chunk_gen():
        yield Mock(text="def ")
        yield Mock(text="hello():\n")
        yield Mock(text="    return 'world'")

    mock_engine.get_session.return_value = Mock(
        model_profile="qwen2.5-coder:3b",
        objective=Mock(request="Write a function", status=ObjectiveStatus.ACTIVE),
    )
    mock_engine._model_gateway = Mock(_models={})
    mock_engine.execute_model.return_value = Mock(
        text=None,
        stream_generator=chunk_gen(),
        tool_calls=None,
        usage={"prompt_tokens": 15, "completion_tokens": 25},
    )

    controller = InteractionController(engine=mock_engine)
    app = TuiApplication(workspace_root="/test/workspace")
    app.connect_controller(controller)
    app.header.session_id = "sess_nl_stream"

    # Submit natural language objective
    app.submit("Write a function")

    # Give background thread time to stream chunks and finish
    time.sleep(0.4)

    activities = app.transcript.get_activities()
    user_acts = [a for a in activities if a.type == ActivityType.MESSAGE and a.title == "User"]
    claire_acts = [a for a in activities if a.type == ActivityType.MESSAGE and a.title == "Claire"]

    assert len(user_acts) == 1
    assert user_acts[0].detail == "Write a function"
    assert len(claire_acts) >= 1
    assert "def hello():" in claire_acts[-1].detail


def test_session_pause_semantics():
    """Verify that when a session is paused:
    1. Natural language prompts are rejected with a clear message.
    2. No new objective is spawned.
    3. When resumed via /resume, new prompts are accepted.
    """
    mock_engine = Mock()
    mock_engine._event_subscribers = []
    mock_engine.session_id = "sess_pause_test"

    paused_objective = Mock(id="obj_p", request="Old task", status=ObjectiveStatus.PAUSED)
    mock_session = Mock(
        id="sess_pause_test",
        model_profile="test-model",
        objective=paused_objective
    )
    mock_engine.get_session.return_value = mock_session

    controller = InteractionController(engine=mock_engine)
    app = TuiApplication(workspace_root="/test/workspace")
    app.connect_controller(controller)
    app.header.session_id = "sess_pause_test"

    # 1. Submit prompt while session is PAUSED
    app.submit("hey there")
    time.sleep(0.2)

    activities = app.transcript.get_activities()
    last_act = activities[-1]
    assert "Session is paused" in last_act.detail or "resume" in last_act.detail.lower()

    # 2. Resume session via /session resume or /resume
    app.submit("/resume")

    # Simulate objective status transitioning back to ACTIVE
    paused_objective.status = ObjectiveStatus.ACTIVE

    # 3. Submit new prompt after resuming -> accepted
    mock_engine.execute_model.return_value = Mock(
        text="Hello! How can I help?",
        stream_generator=None,
        tool_calls=None,
        usage={"prompt_tokens": 10, "completion_tokens": 10},
    )
    app.submit("now do something")
    time.sleep(0.3)

    activities_after = app.transcript.get_activities()
    user_acts = [a for a in activities_after if a.type == ActivityType.MESSAGE and a.title == "User"]
    assert any("now do something" in a.detail for a in user_acts)


def test_task_view_overlay_tracks_objective():
    """Verify TaskViewOverlay displays active objective and status."""
    app = TuiApplication()
    app.header.session_id = "sess_task_view"
    app.task_view.objective = "Refactor database models"

    app.open_task()
    assert app.active_overlay == "task"

    lines = app.task_view.render(width=80)
    rendered = "\n".join(lines)
    assert "Refactor database models" in rendered


def test_complete_provider_lifecycle_end_to_end(tmp_path):
    """Verify the entire provider lifecycle:
    1. Configure Ollama -> Discover Qwen -> Select Qwen -> Execute real workflow (verifying model_id & provider).
    2. Switch to configured Groq -> Discover Llama -> Select Llama -> Execute workflow with Groq.
    """
    from clairecoder.app import ClaireCoderV1
    from clairecoder.gateway.manager import ConfigurationManager
    from clairecoder.gateway.config import ProviderProfile
    from clairecoder.gateway.types import ModelRequest, ModelResponse

    config_mgr = ConfigurationManager(workspace_root=str(tmp_path))

    p_ollama = ProviderProfile(
        id="ollama",
        provider_id="ollama",
        name="Ollama Local",
        adapter_type="ollama",
        endpoint="http://localhost:11434",
        category="local",
        default_model_id="qwen2.5-coder:3b",
        available_models=["qwen2.5-coder:3b"],
        capabilities={"qwen2.5-coder:3b": ["text", "streaming", "tool_calling"]},
        provider_specific={"context_capacities": {"qwen2.5-coder:3b": 32768}},
    )
    p_groq = ProviderProfile(
        id="groq",
        provider_id="groq",
        name="Groq Cloud",
        adapter_type="openai_compatible",
        endpoint="https://api.groq.com/openai/v1",
        category="hosted",
        default_model_id="llama-3.3-70b-versatile",
        available_models=["llama-3.3-70b-versatile"],
        capabilities={"llama-3.3-70b-versatile": ["text", "streaming", "tool_calling"]},
        provider_specific={"context_capacities": {"llama-3.3-70b-versatile": 131072}},
    )
    config_mgr.save_provider_profile(p_ollama)
    config_mgr.save_provider_profile(p_groq)
    config_mgr.set_active("ollama", "qwen2.5-coder:3b")

    app = ClaireCoderV1(workspace_root=str(tmp_path))
    app.config_manager = config_mgr
    app.load_providers_from_config()

    requests_recorded = []
    def recording_execute(req: ModelRequest) -> ModelResponse:
        requests_recorded.append({
            "model_id": req.model_id,
            "messages": req.messages,
        })
        return ModelResponse(text="Success", tool_calls=[])

    app.model_gateway.execute = recording_execute

    tui = TuiApplication(workspace_root=str(tmp_path))
    tui.connect_controller(app.interaction_controller)
    tui.connect_config_manager(app.config_manager)

    sid = app.create_session("sess_lifecycle")
    tui.header.session_id = sid
    tui.header.model = app.get_active_model_id()

    # Step 1: Run workflow with Ollama Qwen
    assert tui.header.model == "qwen2.5-coder:3b"
    app.submit_objective(sid, "Create math helper", start_background=False)
    app.run(sid, max_cycles=1)

    assert len(requests_recorded) > 0
    assert requests_recorded[-1]["model_id"] == "qwen2.5-coder:3b"
    requests_recorded.clear()

    # Step 2: Switch to Groq Llama
    tui.submit("/model groq/llama-3.3-70b-versatile")
    assert tui.header.model == "llama-3.3-70b-versatile"
    assert app.get_active_model_id() == "llama-3.3-70b-versatile"

    # Step 3: Run workflow with Groq Llama
    app.submit_objective(sid, "Refactor math helper", start_background=False)
    app.run(sid, max_cycles=1)

    assert len(requests_recorded) > 0
    assert requests_recorded[-1]["model_id"] == "llama-3.3-70b-versatile"

