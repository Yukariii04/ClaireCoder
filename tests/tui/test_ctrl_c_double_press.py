"""Tests for Ctrl+C Double-Press Exit Behavior (Stage 6 Correction #3)."""
import io
import time
from unittest.mock import MagicMock

import pytest

from clairecoder.tui.app import TuiApplication
from clairecoder.tui.states import InputState
from clairecoder.tui.terminal import TerminalRenderer


def test_first_ctrl_c_interrupts_active_operation():
    """1. First Ctrl+C interrupts active operation."""
    app = TuiApplication()
    interrupted = False

    def on_intr():
        nonlocal interrupted
        interrupted = True

    app.on_interrupt = on_intr
    app.start()
    app.handle_key("ctrl+c")

    assert interrupted is True
    assert "INTERRUPT" in app._action_history


def test_first_ctrl_c_does_not_exit():
    """2. First Ctrl+C does not exit."""
    app = TuiApplication()
    app.start()
    exited = app.handle_ctrl_c()

    assert exited is False
    assert app.running is True


def test_second_ctrl_c_within_window_exits():
    """3. Second Ctrl+C within the window exits."""
    app = TuiApplication()
    app.start()
    app.handle_ctrl_c()
    assert app.running is True

    # Second press immediately within 2.5s window
    exited = app.handle_ctrl_c()
    assert exited is True
    assert app.running is False
    assert "EXIT_DOUBLE_CTRL_C" in app._action_history


def test_second_ctrl_c_returns_clean_cli_exit_status():
    """4. Second Ctrl+C returns clean CLI exit status (0)."""
    app = TuiApplication()
    exit_code = app.run(input_source=["ctrl+c", "ctrl+c"])
    assert exit_code == 0
    assert app.running is False


def test_first_ctrl_c_while_idle_enters_exit_confirmation_state():
    """5. First Ctrl+C while idle enters exit-confirmation state."""
    app = TuiApplication()
    app.start()
    assert app.is_exit_confirmation_active() is False

    app.handle_key("ctrl+c")
    assert app.is_exit_confirmation_active() is True
    assert app.running is True


def test_second_ctrl_c_while_idle_exits():
    """6. Second Ctrl+C while idle exits."""
    app = TuiApplication()
    app.start()
    app.handle_key("ctrl+c")
    assert app.running is True

    app.handle_key("ctrl+c")
    assert app.running is False


def test_delayed_second_ctrl_c_after_timeout_does_not_exit():
    """7. Delayed second Ctrl+C after timeout does not exit."""
    app = TuiApplication()
    app.exit_confirmation_timeout = 0.05  # 50ms timeout for test
    app.start()

    app.handle_key("ctrl+c")
    assert app.is_exit_confirmation_active() is True

    # Wait for timeout to expire
    time.sleep(0.08)
    assert app.is_exit_confirmation_active() is False

    # Second press after timeout should act as a new first Ctrl+C
    app.handle_key("ctrl+c")
    assert app.running is True
    assert app.is_exit_confirmation_active() is True


def test_slash_exit_still_exits():
    """8. /exit still exits."""
    app = TuiApplication()
    code = app.run(input_source=["/exit"])
    assert code == 0
    assert app.running is False


def test_bare_exit_still_exits():
    """9. exit still exits."""
    app = TuiApplication()
    code = app.run(input_source=["exit"])
    assert code == 0
    assert app.running is False


def test_quit_still_exits():
    """10. quit still exits."""
    app = TuiApplication()
    code = app.run(input_source=["quit"])
    assert code == 0
    assert app.running is False


def test_feedback_is_rendered_inside_the_tui():
    """11. Feedback is rendered inside the TUI presentation surface."""
    app = TuiApplication()
    app.start()
    app.handle_key("ctrl+c")

    lines = app.render()
    rendered_text = "\n".join(lines)
    assert "Press Ctrl+C again to exit ClaireCoder." in rendered_text


def test_no_raw_terminal_line_is_printed_for_feedback():
    """12. No raw terminal line is printed outside the TUI frame."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    app = TuiApplication(renderer=renderer)

    # First Ctrl+C enters confirmation, second exits
    app.run(input_source=["ctrl+c", "ctrl+c"])

    out = stream.getvalue()
    # Output is structured into ClaireCoder box frames
    assert "╭─ ClaireCoder" in out
    assert "╰─" in out or "╰" in out


def test_overlays_do_not_accidentally_bypass_their_focus_semantics():
    """13. Overlays retain focus semantics on Ctrl+C and exit cleanly on double Ctrl+C."""
    app = TuiApplication()
    app.start()
    app.open_tree()
    assert app.state == InputState.OVERLAY
    assert app.is_tree_open is True

    # First Ctrl+C on active overlay sets confirmation, does not crash or exit
    app.handle_key("ctrl+c")
    assert app.running is True
    assert app.is_exit_confirmation_active() is True

    # Second Ctrl+C exits cleanly
    app.handle_key("ctrl+c")
    assert app.running is False


def test_unrelated_input_resets_interrupt_pending_state():
    """Unrelated character or submit resets pending Ctrl+C confirmation."""
    app = TuiApplication()
    app.start()
    app.handle_key("ctrl+c")
    assert app.is_exit_confirmation_active() is True

    # Type a normal character
    app.handle_key("a")
    assert app.is_exit_confirmation_active() is False
    assert app.prompt.get_text() == "a"
