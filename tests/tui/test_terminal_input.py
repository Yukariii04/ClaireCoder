"""Tests for TerminalInput, InputDecoder, KeyEvents, Double Ctrl+C, Clipboard, and Slash Suggestions.

Authorities: CC-PRD-011, CC-ADR-007.
"""
import time
import pytest
from unittest.mock import Mock

from clairecoder.tui.terminal import InputDecoder, KeyEvent, TerminalInput
from clairecoder.tui.app import TuiApplication, InputState
from clairecoder.tui.clipboard import normalize_clipboard_text


def test_input_decoder_vt_sequences():
    """Prove VT/ANSI input sequences decode deterministically to KeyEvents."""
    assert InputDecoder.decode("\x1b[A") == "up"
    assert InputDecoder.decode("\x1bOA") == "up"
    assert InputDecoder.decode("\x1b[B") == "down"
    assert InputDecoder.decode("\x1bOB") == "down"
    assert InputDecoder.decode("\x1b[C") == "right"
    assert InputDecoder.decode("\x1bOC") == "right"
    assert InputDecoder.decode("\x1b[D") == "left"
    assert InputDecoder.decode("\x1bOD") == "left"
    assert InputDecoder.decode("\x1b[5~") == "pageup"
    assert InputDecoder.decode("\x1b[6~") == "pagedown"
    assert InputDecoder.decode("\x1b[H") == "home"
    assert InputDecoder.decode("\x1b[F") == "end"
    assert InputDecoder.decode("\x1b") == "escape"
    assert InputDecoder.decode("\r") == "enter"
    assert InputDecoder.decode("\n") == "enter"
    assert InputDecoder.decode("\t") == "tab"
    assert InputDecoder.decode("\x08") == "backspace"
    assert InputDecoder.decode("\x7f") == "backspace"


def test_input_decoder_windows_scan_codes():
    """Prove Windows scan codes (e.g. 0xE0 prefix) decode accurately."""
    assert InputDecoder.decode("\xe0H") == "up"
    assert InputDecoder.decode("\xe0P") == "down"
    assert InputDecoder.decode("\xe0K") == "left"
    assert InputDecoder.decode("\xe0M") == "right"
    assert InputDecoder.decode("\xe0I") == "pageup"
    assert InputDecoder.decode("\xe0Q") == "pagedown"
    assert InputDecoder.decode("\xe0G") == "home"
    assert InputDecoder.decode("\xe0O") == "end"


def test_ctrl_c_double_press_exit_confirmation():
    """Verify double Ctrl+C within timeout window triggers clean exit."""
    app = TuiApplication()
    app.start()

    # First Ctrl+C: arms confirmation window without exiting
    exited1 = app.handle_ctrl_c()
    assert exited1 is False
    assert app.running is True

    # Second Ctrl+C within window: exits
    exited2 = app.handle_ctrl_c()
    assert exited2 is True
    assert app.running is False
    assert app.state == InputState.EXITING


def test_ctrl_c_timeout_expiration():
    """Verify single Ctrl+C times out and resets."""
    app = TuiApplication()
    app.exit_confirmation_timeout = 0.05  # fast test timeout
    app.start()

    app.handle_ctrl_c()
    time.sleep(0.06)

    # After timeout, next Ctrl+C does not immediately exit, but rearms
    exited = app.handle_ctrl_c()
    assert exited is False
    assert app.running is True


def test_ctrl_c_keystroke_reset():
    """Verify any keystroke after first Ctrl+C resets the confirmation window."""
    app = TuiApplication()
    app.start()

    app.handle_ctrl_c()

    # User types something -> resets interrupt pending
    app.handle_key("a")
    # Next Ctrl+C does not exit
    exited = app.handle_ctrl_c()
    assert exited is False
    assert app.running is True


def test_clipboard_paste_decoding():
    """Test multi-line and single-line clipboard text normalization."""
    raw = "line 1\r\nline 2\nline 3"
    single = normalize_clipboard_text(raw, single_line=True)
    assert single == "line 1 line 2 line 3"

    multi = normalize_clipboard_text(raw, single_line=False)
    assert len(multi.splitlines()) == 3


def test_slash_command_suggestions_triggering_and_navigation():
    """Test slash suggestions appear on '/' and filter commands."""
    app = TuiApplication()
    app.prompt.set_text("/")
    matches = app.get_slash_suggestions()
    assert len(matches) > 0
    assert "/help" in matches
    assert "/model" in matches
    assert "/session" in matches

    app.prompt.set_text("/mod")
    filtered = app.get_slash_suggestions()
    assert "/model" in filtered
    assert "/mode" in filtered
    assert "/help" not in filtered

    # Prose or spaces do not trigger suggestions
    app.prompt.set_text("/ help")
    assert app.get_slash_suggestions() == []
    app.prompt.set_text("/model test")
    assert app.get_slash_suggestions() == []
    app.prompt.set_text("What about /help?")
    assert app.get_slash_suggestions() == []


def test_question_mark_is_ordinary_prompt_text():
    """Verify '?' is treated as ordinary prompt text and does not intercept navigation."""
    app = TuiApplication()
    app.handle_key("?")
    assert app.prompt.get_text() == "?"
    assert app.state == InputState.NORMAL
    assert app.active_overlay is None
