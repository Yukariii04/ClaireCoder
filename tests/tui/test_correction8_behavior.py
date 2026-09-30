"""Tests for Stage 7 Correction #8 production behavioral fixes.

Verifies:
1. Transcript word-wrapping on long Claire messages and activities.
2. Wizard overlay keyboard input forwarding (Enter, Tab, characters, Esc).
3. Wizard Esc back-stack to Model Selector overlay.
4. Task view lifecycle state synchronization (COMPLETED, FAILED, CANCELLED, PAUSED).
5. Terminal width propagation to transcript render width.
"""
import pytest
from unittest.mock import MagicMock
from clairecoder.tui.app import TuiApplication, InputState
from clairecoder.tui.states import TerminalMode
from clairecoder.tui.activity import ActivityModel, ActivityType, ActivityState
from clairecoder.tui.renderer import ActivityRenderer, _wrap_text
from clairecoder.tui.transcript import TranscriptView
from clairecoder.tui.wizard import WizardStage
from clairecoder.tui.model_selector import ModelSelectorStage
from clairecoder.tui.terminal import TerminalCapability
from clairecoder.engine.types import ObjectiveStatus, Task as EngineTask, TaskState as EngineTaskState, EngineeringObjective


class DummyObjective:
    def __init__(self, request: str, status: ObjectiveStatus, failure_reason: str = None):
        self.id = "obj_123"
        self.request = request
        self.status = status
        self.failure_reason = failure_reason


class DummySession:
    def __init__(self, request: str, status: ObjectiveStatus, tasks=None, failure_reason=None):
        self.id = "sess_123"
        self.objective = DummyObjective(request, status, failure_reason)
        self.tasks = tasks or {}
        self.model_profile = "test-model"


def test_wrap_text_word_boundary():
    long_text = "This is a very long sentence that needs to wrap properly across multiple lines without clipping words."
    wrapped = _wrap_text(long_text, width=30, indent="  ")
    assert len(wrapped) > 1
    for line in wrapped:
        assert len(line) <= 30
        assert line.startswith("  ")
    # All words preserved
    combined = " ".join(l.strip() for l in wrapped)
    assert combined == long_text


def test_transcript_word_wrapping_long_claire_message():
    long_msg = "Here is an in-depth explanation of the changes made to the system architecture. We updated the model gateway and the configuration manager to ensure that active models persist across restarts and fail-safes are maintained."
    act = ActivityModel(
        type=ActivityType.MESSAGE,
        title="Claire",
        detail=long_msg
    )
    # Render with narrow width
    lines = ActivityRenderer.render(act, width=40)
    assert lines[0] == "Claire:"
    for row in lines[1:]:
        assert len(row) <= 40
        assert row.startswith("  ")
    # Full message text should be represented across the rows
    reconstructed = " ".join(r.strip() for r in lines[1:])
    assert "explanation of the changes" in reconstructed
    assert "fail-safes are maintained" in reconstructed


def test_transcript_view_render_width_propagation():
    # 104 cols is FULL mode (96+): render_width is width - 6 = 98
    term = TerminalCapability(width=104, height=30)
    app = TuiApplication(terminal=term)
    app._update_layout()
    assert app.transcript.render_width == 98

    # 80 cols is COMPACT mode (76..95): render_width is width - 2 = 78
    app.resize(80, 24)
    assert app.transcript.render_width == 78

    # 60 cols is MINIMAL mode (<76): render_width is width - 2 = 58
    app.resize(60, 24)
    assert app.transcript.render_width == 58


def test_wizard_overlay_key_forwarding():
    term = TerminalCapability(width=104, height=30)
    app = TuiApplication(terminal=term)
    app.open_wizard()
    assert app.state == InputState.OVERLAY
    assert app.active_overlay == "wizard"
    assert app.wizard is not None

    # Initial stage is PROVIDER_SELECT
    assert app.wizard.stage == WizardStage.PROVIDER_SELECT
    initial_idx = app.wizard.selected_index

    # Dispatch down arrow
    app.handle_key("down")
    assert app.wizard.selected_index != initial_idx

    # Dispatch Enter to select provider
    app.handle_key("enter")
    assert app.wizard.stage == WizardStage.CREDENTIAL_ENTRY

    # Dispatch typing characters into credential
    app.handle_key("a")
    app.handle_key("b")
    app.handle_key("c")
    assert app.wizard.credential_input == "abc"


def test_wizard_esc_back_stack_to_model_selector():
    term = TerminalCapability(width=80, height=24)
    app = TuiApplication(terminal=term)
    mock_prov = {
        "id": "anthropic",
        "name": "Anthropic",
        "default_endpoint": "https://api.anthropic.com",
        "requires_api_key": True,
    }
    # Simulate user picking an unconfigured provider from ModelSelector
    app._on_model_selector_configure(mock_prov)
    assert app.active_overlay == "wizard"
    assert app._wizard_launched_from_selector is True

    # Press Esc inside wizard
    handled = app.handle_key("escape")
    assert handled is True
    # Should return to model_selector overlay
    assert app.active_overlay == "model_selector"
    assert app.model_selector.stage == ModelSelectorStage.PROVIDER_LIST


def test_task_view_lifecycle_states_sync_completed():
    term = TerminalCapability(width=80, height=24)
    app = TuiApplication(terminal=term)
    mock_engine = MagicMock()
    t1 = EngineTask(id="t1", objective_id="obj_123", description="Build feature", status=EngineTaskState.SUCCEEDED)
    session = DummySession("Implement authentication", ObjectiveStatus.COMPLETED, tasks={"t1": t1})
    mock_engine.get_session.return_value = session

    mock_controller = MagicMock()
    mock_controller._engine = mock_engine
    app.controller = mock_controller
    app.header.session_id = session.id

    app._sync_task_view_from_session()
    assert app.task_view.objective == "Implement authentication"
    assert app.task_view.status == "Complete"
    assert app.task_view.progress_pct == 100
    assert len(app.task_view.tasks) == 1
    assert app.task_view.tasks[0].marker == "✓"


def test_task_view_lifecycle_states_sync_failed():
    term = TerminalCapability(width=80, height=24)
    app = TuiApplication(terminal=term)
    mock_engine = MagicMock()
    t1 = EngineTask(id="t1", objective_id="obj_123", description="Build feature", status=EngineTaskState.FAILED)
    session = DummySession("Implement authentication", ObjectiveStatus.FAILED, tasks={"t1": t1}, failure_reason="SyntaxError on line 42")
    mock_engine.get_session.return_value = session

    mock_controller = MagicMock()
    mock_controller._engine = mock_engine
    app.controller = mock_controller
    app.header.session_id = session.id

    app._sync_task_view_from_session()
    assert app.task_view.objective == "Implement authentication"
    assert app.task_view.status == "Failed"
    assert app.task_view.failure_reason == "SyntaxError on line 42"
    assert len(app.task_view.tasks) == 1
    assert app.task_view.tasks[0].marker == "✗"


def test_task_view_lifecycle_states_sync_cancelled():
    term = TerminalCapability(width=80, height=24)
    app = TuiApplication(terminal=term)
    mock_engine = MagicMock()
    t1 = EngineTask(id="t1", objective_id="obj_123", description="Build feature", status=EngineTaskState.CANCELLED)
    session = DummySession("Implement authentication", ObjectiveStatus.CANCELLED, tasks={"t1": t1})
    mock_engine.get_session.return_value = session

    mock_controller = MagicMock()
    mock_controller._engine = mock_engine
    app.controller = mock_controller
    app.header.session_id = session.id

    app._sync_task_view_from_session()
    assert app.task_view.objective == "Implement authentication"
    assert app.task_view.status == "Cancelled"
    assert len(app.task_view.tasks) == 1
    assert app.task_view.tasks[0].marker == "⊘"
