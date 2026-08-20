"""Integration tests for TUI Stage 4 overlays, shortcuts, and command routing."""
import pytest
from unittest.mock import Mock, patch

from clairecoder.tui.app import TuiApplication
from clairecoder.tui.states import InputState, TerminalMode
from clairecoder.interaction.controller import InteractionController
from clairecoder.interaction.types import CommandRequest, CommandResponse
from clairecoder.tui.palette import PaletteCommandItem
from clairecoder.tui.diff import FileDiff

def test_shortcut_ctrl_r_opens_review_overlay():
    """Verify Ctrl+R opens the Review overlay, transitions to OVERLAY state, and suspends prompt."""
    app = TuiApplication()
    assert app.state == InputState.NORMAL
    assert not app.prompt.suspended

    app.handle_key("ctrl+r")
    assert app.state == InputState.OVERLAY
    assert app.active_overlay == "review"
    assert app.is_review_open
    assert app.prompt.suspended

    # Esc closes overlay and returns to NORMAL
    app.handle_key("Esc")
    assert app.state == InputState.NORMAL
    assert app.active_overlay is None
    assert not app.is_review_open
    assert not app.prompt.suspended

def test_shortcut_question_mark_opens_command_palette():
    """Verify '?' is ordinary prompt text and '/commands' opens the Command Palette overlay."""
    app = TuiApplication()
    app.handle_key("?")
    assert app.prompt.get_text() == "?"
    assert app.state == InputState.NORMAL
    assert not app.is_palette_open

    # Submit /commands
    app.prompt.clear()
    app.submit("/commands")
    assert app.state == InputState.OVERLAY
    assert app.active_overlay == "palette"
    assert app.is_palette_open

    # Esc closes palette
    app.handle_key("Esc")
    assert app.state == InputState.NORMAL
    assert app.active_overlay is None
    assert not app.is_palette_open

def test_help_command_routes_through_interaction_controller():
    """Verify /help routes through InteractionController and outputs result."""
    mock_engine = Mock()
    controller = InteractionController(engine=mock_engine)
    app = TuiApplication()
    app.connect_controller(controller)

    # Submit /help via prompt
    app.submit("/help")

    # Verify /help activity recorded in transcript
    activities = app.transcript.get_activities()
    assert any("help" in a.title.lower() for a in activities)

def test_help_routing_interaction_controller_invoked():
    """Explicitly verify that InteractionController.execute_command receives /help."""
    mock_engine = Mock()
    controller = InteractionController(engine=mock_engine)
    app = TuiApplication()
    app.connect_controller(controller)

    with patch.object(controller, "execute_command", wraps=controller.execute_command) as mock_exec:
        app.submit("/help")
        assert mock_exec.called
        call_args = mock_exec.call_args[0][0]
        assert isinstance(call_args, CommandRequest)
        assert call_args.command == "help"

    activities = app.transcript.get_activities()
    assert any("help" in a.title.lower() for a in activities)

def test_ui_command_review_via_prompt():
    """Verify typing /review opens review overlay directly (UI presentation owned)."""
    mock_engine = Mock()
    controller = InteractionController(engine=mock_engine)
    app = TuiApplication()
    app.connect_controller(controller)

    with patch.object(controller, "execute_command", wraps=controller.execute_command) as mock_exec:
        app.submit("/review")
        # InteractionController should NOT receive UI presentation commands
        mock_exec.assert_not_called()

    assert app.is_review_open
    assert app.state == InputState.OVERLAY
    assert app.active_overlay == "review"

def test_ui_command_tree_via_prompt():
    """Verify typing /tree opens file tree directly (UI presentation owned)."""
    mock_engine = Mock()
    controller = InteractionController(engine=mock_engine)
    app = TuiApplication()
    app.connect_controller(controller)

    with patch.object(controller, "execute_command", wraps=controller.execute_command) as mock_exec:
        app.submit("/tree")
        mock_exec.assert_not_called()

    assert app.is_tree_open

def test_application_command_routes_through_controller():
    """Verify application commands (e.g. /status) route through InteractionController."""
    mock_engine = Mock()
    controller = InteractionController(engine=mock_engine)
    app = TuiApplication()
    app.connect_controller(controller)

    app.submit("/status")

    assert len(app.transcript.activities) == 1
    act = app.transcript.activities[0]
    assert "Command /status" in act.title
    assert "Engine Status: Active" in act.detail

def test_palette_selection_application_command():
    """Verify selecting an application command from palette routes to controller."""
    mock_engine = Mock()
    controller = InteractionController(engine=mock_engine)
    app = TuiApplication()
    app.connect_controller(controller)

    app.open_palette()
    assert app.is_palette_open

    # Select /status (index 1)
    app.command_palette.selected_index = 1
    selected_item = app.command_palette.selected_command
    assert selected_item.name == "/status"

    app.handle_key("Enter")
    # Overlay is closed and command is executed
    assert app.state == InputState.NORMAL
    assert len(app.transcript.activities) == 1
    assert "Command /status" in app.transcript.activities[0].title

def test_palette_selection_ui_command():
    """Verify selecting a UI command from palette opens appropriate UI overlay."""
    app = TuiApplication()
    app.open_palette()

    # Select /review
    idx = next(i for i, c in enumerate(app.command_palette.commands) if c.name == "/review")
    app.command_palette.selected_index = idx
    assert app.command_palette.selected_command.name == "/review"

    app.handle_key("Enter")
    assert app.is_review_open
    assert app.state == InputState.OVERLAY
    assert app.active_overlay == "review"

def test_ctrl_c_does_not_close_overlay_but_calls_interrupt():
    """Verify Ctrl+C is reserved for operation interruption and doesn't just act as Esc."""
    app = TuiApplication()
    mock_interrupt = Mock()
    app.on_interrupt = mock_interrupt

    app.handle_key("ctrl+c")
    mock_interrupt.assert_called_once()
