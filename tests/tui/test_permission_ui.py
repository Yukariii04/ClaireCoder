"""Unit and presentation tests for the TUI Permission Confirmation UI (CLI/TUI Stage 3)."""
import pytest
from unittest.mock import Mock, call

from clairecoder.core.events import Event
from clairecoder.tui.states import InputState, TerminalMode
from clairecoder.tui.app import TuiApplication
from clairecoder.tui.permission import (
    PermissionSurface,
    PermissionDecision,
    PermissionRequestViewModel,
    sanitize_display_text,
    format_permission_command
)
from clairecoder.tui.activity import ActivityType, ActivityState, DiffInfo, DiffLine
from clairecoder.tui.terminal import TerminalCapability

def test_sanitize_display_text():
    """Verify that passwords, tokens, and API keys are redacted for safe display."""
    assert sanitize_display_text("pytest tests/") == "pytest tests/"
    assert "token=***" in sanitize_display_text("connect --token=secret12345")
    assert "password=***" in sanitize_display_text("login password=my_secret_pass")
    assert "GITHUB_TOKEN=***" in sanitize_display_text("export GITHUB_TOKEN=ghp_123456789012345678901234567890")
    assert "[REDACTED_TOKEN]" in sanitize_display_text("curl -H 'Authorization: ghp_123456789012345678901234567890'")
    assert "OPENAI_API_KEY=***" in sanitize_display_text("OPENAI_API_KEY=sk-123456789012345678901234567890")
    assert "[REDACTED_KEY]" in sanitize_display_text("key: sk-123456789012345678901234567890")
    assert "[REDACTED]" in sanitize_display_text("Authorization: Bearer abcdef1234567890xyz")


def test_format_permission_command():
    """Verify safe and concise formatting of tool commands."""
    assert format_permission_command("rm", "delete", "src/decoder_v1.py") == "rm src/decoder_v1.py"
    assert format_permission_command("write_file", "write", "src/main.py") == "write src/main.py"
    assert format_permission_command("pytest", "execute", "tests/") == "pytest tests/"
    assert format_permission_command("terminal", "execute", "echo hello", command="rm -rf /tmp/test") == "rm -rf /tmp/test"

def test_permission_surface_render_full():
    """Verify full TUI rendering matches TUI-DESIGN.md reference."""
    surface = PermissionSurface()
    surface.request_confirmation(
        request_id="req_1",
        tool_id="rm",
        action="delete",
        resource="src/decoder_v1_deprecated.py",
        reason="This will permanently delete the file."
    )
    
    lines = surface.render(TerminalMode.FULL, width=80)
    full_text = "\n".join(lines)
    
    assert "Permission Required" in full_text
    assert "ClaireCoder wants to run:" in full_text
    assert "$ rm src/decoder_v1_deprecated.py" in full_text
    assert "[y] yes" in full_text
    assert "[n] no" in full_text
    assert "[a] yes, always this sess" in full_text
    assert "[d] diff" in full_text
    assert "Claire:" in full_text
    assert "This will permanently delete the file." in full_text
    assert "Are you sure?" in full_text
    assert "(Esc to cancel)" in full_text

def test_permission_surface_render_compact():
    """Verify compact TUI mode rendering."""
    surface = PermissionSurface()
    surface.request_confirmation(
        request_id="req_1",
        tool_id="pytest",
        action="execute",
        resource="tests/unit"
    )
    
    lines = surface.render(TerminalMode.COMPACT, width=80)
    full_text = "\n".join(lines)
    
    assert "Permission Required" in full_text
    assert "$ pytest tests/unit" in full_text
    assert "[y] yes" in full_text
    assert "[n] no" in full_text
    assert "[a] always" in full_text
    assert "[d] diff" in full_text

def test_permission_surface_render_minimal():
    """Verify minimal TUI mode rendering."""
    surface = PermissionSurface()
    surface.request_confirmation(
        request_id="req_1",
        tool_id="pytest",
        action="execute",
        resource="tests/unit"
    )
    
    lines = surface.render(TerminalMode.MINIMAL, width=80)
    full_text = "\n".join(lines)
    
    assert "[!] Permission Required:" in full_text
    assert "$ pytest tests/unit" in full_text
    assert "[y] yes" in full_text
    assert "[n] no" in full_text
    assert "[a] yes, always this sess" in full_text
    assert "[d] diff" in full_text
    assert "(Esc to cancel)" in full_text

def test_confirmation_focus_and_suspension():
    """Verify that permission request causes CONFIRMATION focus and suspends normal prompt."""
    app = TuiApplication()
    assert app.state == InputState.NORMAL
    assert not app.prompt.suspended
    
    # Event arrives requiring permission
    event = Event("PERMISSION_REQUESTED", {
        "request_id": "req_100",
        "tool_id": "rm",
        "action": "delete",
        "resource": "old_file.py"
    })
    app.handle_event(event)
    
    # UI state transitions to CONFIRMATION
    assert app.state == InputState.CONFIRMATION
    assert app.prompt.suspended
    assert app.permission_surface.has_pending()
    assert app.permission_surface.active_request.request_id == "req_100"

def test_keyboard_y_approval():
    """Verify 'y' / 'Y' approves request and routes response."""
    app = TuiApplication()
    mock_response_cb = Mock()
    app.on_permission_response = mock_response_cb
    
    event = Event("PERMISSION_REQUESTED", {
        "request_id": "req_1",
        "tool_id": "write_file",
        "action": "write",
        "resource": "src/app.py",
        "session_id": "sess_1"
    })
    app.handle_event(event)
    assert app.state == InputState.CONFIRMATION
    
    # User presses 'y'
    app.handle_key("y")
    
    # Verified: callback received decision APPROVE with correlation info
    mock_response_cb.assert_called_once_with(
        request_id="req_1",
        decision=PermissionDecision.APPROVE,
        session_id="sess_1",
        tool_id="write_file",
        action="write",
        resource="src/app.py",
        command=None,
        category=None
    )
    # UI state returned to NORMAL
    assert app.state == InputState.NORMAL
    assert not app.prompt.suspended

def test_keyboard_n_denial():
    """Verify 'n' / 'N' denies request and routes response."""
    app = TuiApplication()
    mock_response_cb = Mock()
    app.on_permission_response = mock_response_cb
    
    event = Event("PERMISSION_REQUESTED", {
        "request_id": "req_2",
        "tool_id": "rm",
        "action": "delete",
        "resource": "important.txt",
        "session_id": "sess_1"
    })
    app.handle_event(event)
    assert app.state == InputState.CONFIRMATION
    
    # User presses 'n'
    app.handle_key("n")
    
    mock_response_cb.assert_called_once_with(
        request_id="req_2",
        decision=PermissionDecision.DENY,
        session_id="sess_1",
        tool_id="rm",
        action="delete",
        resource="important.txt",
        command=None,
        category=None
    )
    assert app.state == InputState.NORMAL

def test_keyboard_a_session_always():
    """Verify 'a' / 'A' routes ALWAYS_SESSION decision."""
    app = TuiApplication()
    mock_response_cb = Mock()
    app.on_permission_response = mock_response_cb
    
    event = Event("PERMISSION_REQUESTED", {
        "request_id": "req_3",
        "tool_id": "pytest",
        "action": "execute",
        "resource": "tests/",
        "session_id": "sess_main"
    })
    app.handle_event(event)
    
    # User presses 'a'
    app.handle_key("a")
    
    mock_response_cb.assert_called_once_with(
        request_id="req_3",
        decision=PermissionDecision.ALWAYS_SESSION,
        session_id="sess_main",
        tool_id="pytest",
        action="execute",
        resource="tests/",
        command=None,
        category=None
    )
    assert app.state == InputState.NORMAL

def test_keyboard_d_diff_action_with_diff():
    """Verify 'd' / 'D' toggles inline diff display when diff exists."""
    app = TuiApplication()
    diff = DiffInfo(
        summary="src/decoder.py +1 -1",
        lines=[
            DiffLine(type="remove", content="return old_val"),
            DiffLine(type="add", content="return new_val")
        ]
    )
    event = Event("PERMISSION_REQUESTED", {
        "request_id": "req_4",
        "tool_id": "write_file",
        "action": "write",
        "resource": "src/decoder.py",
        "diff_info": diff
    })
    app.handle_event(event)
    
    assert not app.permission_surface.diff_expanded
    
    # User presses 'd' to toggle diff
    app.handle_key("d")
    assert app.permission_surface.diff_expanded
    assert app.permission_surface.diff_message is None
    
    rendered = "\n".join(app.permission_surface.render(TerminalMode.FULL))
    assert "return old_val" in rendered
    assert "return new_val" in rendered
    
    # Press 'd' again to collapse diff
    app.handle_key("d")
    assert not app.permission_surface.diff_expanded

def test_keyboard_d_diff_action_without_diff():
    """Verify 'd' / 'D' displays non-error notice when no diff is available."""
    app = TuiApplication()
    event = Event("PERMISSION_REQUESTED", {
        "request_id": "req_5",
        "tool_id": "pytest",
        "action": "execute",
        "resource": "tests/"
    })
    app.handle_event(event)
    
    # User presses 'd'
    app.handle_key("d")
    assert app.permission_surface.diff_expanded
    assert app.permission_surface.diff_message == "No diff is available for this request."
    
    rendered = "\n".join(app.permission_surface.render(TerminalMode.FULL))
    assert "No diff is available for this request." in rendered

def test_keyboard_esc_ui_cancellation():
    """Verify Esc performs UI-level cancellation without calling execution cancellation."""
    app = TuiApplication()
    mock_response_cb = Mock()
    mock_interrupt_cb = Mock()
    app.on_permission_response = mock_response_cb
    app.on_interrupt = mock_interrupt_cb
    
    event = Event("PERMISSION_REQUESTED", {
        "request_id": "req_6",
        "tool_id": "rm",
        "action": "delete",
        "resource": "file.py"
    })
    app.handle_event(event)
    assert app.state == InputState.CONFIRMATION
    
    # User presses Esc
    app.handle_escape()
    
    # Esc routed as UI CANCEL decision
    mock_response_cb.assert_called_once_with(
        request_id="req_6",
        decision=PermissionDecision.CANCEL,
        session_id=None,
        tool_id="rm",
        action="delete",
        resource="file.py",
        command=None,
        category=None
    )
    # Execution interrupt was NOT invoked
    mock_interrupt_cb.assert_not_called()
    assert app.state == InputState.NORMAL

def test_unknown_keys_during_confirmation_ignored():
    """Verify unknown keys during confirmation do not crash or alter state."""
    app = TuiApplication()
    event = Event("PERMISSION_REQUESTED", {
        "request_id": "req_7",
        "tool_id": "rm",
        "resource": "file.py"
    })
    app.handle_event(event)
    assert app.state == InputState.CONFIRMATION
    
    app.handle_key("x")
    app.handle_key("1")
    app.handle_key(" ")
    
    assert app.state == InputState.CONFIRMATION
    assert app.permission_surface.has_pending()

def test_transcript_activity_lifecycle_updates_in_place():
    """Verify transcript activity updates in-place across request -> approval/denial lifecycle."""
    app = TuiApplication()
    
    # 1. Initial tool request
    app.handle_event(Event("TOOL_REQUESTED", {"tool_name": "pytest", "request_id": "req_88"}))
    assert len(app.transcript.activities) == 1
    assert app.transcript.activities[0].title == "Running pytest"
    assert app.transcript.activities[0].state == ActivityState.RUNNING
    
    # 2. Permission requested for same tool request
    app.handle_event(Event("PERMISSION_REQUESTED", {
        "tool_name": "pytest",
        "request_id": "req_88",
        "action": "execute",
        "resource": "tests/"
    }))
    assert len(app.transcript.activities) == 1
    assert app.transcript.activities[0].title == "Approval required"
    assert app.transcript.activities[0].state == ActivityState.APPROVAL_REQUIRED
    
    # 3. Permission resolved (approved)
    app.handle_event(Event("PERMISSION_RESOLVED", {
        "tool_name": "pytest",
        "request_id": "req_88",
        "decision": "granted"
    }))
    assert len(app.transcript.activities) == 1
    assert app.transcript.activities[0].title == "Permission approved"
    assert app.transcript.activities[0].state == ActivityState.COMPLETED
    assert app.transcript.activities[0].detail == "Running pytest"

def test_transcript_activity_denied_lifecycle():
    """Verify transcript activity updates in-place when denied."""
    app = TuiApplication()
    app.handle_event(Event("PERMISSION_REQUESTED", {
        "tool_name": "rm",
        "request_id": "req_99",
        "action": "delete",
        "resource": "db.sqlite"
    }))
    assert len(app.transcript.activities) == 1
    assert app.transcript.activities[0].title == "Approval required"
    
    # Resolved denied
    app.handle_event(Event("PERMISSION_RESOLVED", {
        "tool_name": "rm",
        "request_id": "req_99",
        "decision": "denied"
    }))
    assert len(app.transcript.activities) == 1
    assert app.transcript.activities[0].title == "Permission denied"
    assert app.transcript.activities[0].state == ActivityState.FAILED

def test_transcript_activity_cancelled_lifecycle():
    """Verify transcript activity updates in-place when cancelled."""
    app = TuiApplication()
    app.handle_event(Event("PERMISSION_REQUESTED", {
        "tool_name": "rm",
        "request_id": "req_101",
        "action": "delete",
        "resource": "db.sqlite"
    }))
    
    app.handle_event(Event("PERMISSION_RESOLVED", {
        "tool_name": "rm",
        "request_id": "req_101",
        "decision": "cancelled"
    }))
    assert len(app.transcript.activities) == 1
    assert app.transcript.activities[0].title == "Permission cancelled"
    assert app.transcript.activities[0].state == ActivityState.BLOCKED

def test_multiple_queued_permission_requests():
    """Verify that multiple concurrent permission requests maintain stable order and focus."""
    app = TuiApplication()
    mock_cb = Mock()
    app.on_permission_response = mock_cb
    
    # Request 1 arrives
    app.handle_event(Event("PERMISSION_REQUESTED", {
        "request_id": "req_A",
        "tool_id": "write_file",
        "resource": "file_a.py"
    }))
    # Request 2 arrives
    app.handle_event(Event("PERMISSION_REQUESTED", {
        "request_id": "req_B",
        "tool_id": "rm",
        "resource": "file_b.py"
    }))
    
    assert app.state == InputState.CONFIRMATION
    assert app.permission_surface.active_request.request_id == "req_A"
    assert len(app.permission_surface.pending_requests) == 1
    assert app.permission_surface.pending_requests[0].request_id == "req_B"
    
    # Approve request 1
    app.handle_key("y")
    mock_cb.assert_called_once_with(
        request_id="req_A",
        decision=PermissionDecision.APPROVE,
        session_id=None,
        tool_id="write_file",
        action="",
        resource="file_a.py",
        command=None,
        category=None
    )
    
    # Now request 2 owns focus, state remains CONFIRMATION
    assert app.state == InputState.CONFIRMATION
    assert app.permission_surface.active_request.request_id == "req_B"
    assert len(app.permission_surface.pending_requests) == 0
    
    # Deny request 2
    mock_cb.reset_mock()
    app.handle_key("n")
    mock_cb.assert_called_once_with(
        request_id="req_B",
        decision=PermissionDecision.DENY,
        session_id=None,
        tool_id="rm",
        action="",
        resource="file_b.py",
        command=None,
        category=None
    )
    
    # Queue is now empty, returns to NORMAL
    assert app.state == InputState.NORMAL
    assert not app.permission_surface.has_pending()
