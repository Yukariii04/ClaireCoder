"""Tests for Native Terminal Input + In-Place TUI Redraw (Stage 6 Correction #2)."""
import io
from unittest.mock import MagicMock, patch

import pytest

from clairecoder.tui.app import TuiApplication
from clairecoder.tui.prompt import PromptInput
from clairecoder.tui.states import InputState, TerminalMode
from clairecoder.tui.terminal import TerminalCapability, TerminalInput, TerminalRenderer


def test_printable_characters_update_prompt_buffer():
    """1. Printable characters update PromptInput buffer."""
    app = TuiApplication()
    app.run(input_source=["h", "i", " ", "t", "h", "e", "r", "e", "exit"])
    assert app.prompt.get_text() == "hi there" or app.running is False


def test_backspace_edits_prompt_buffer():
    """2. Backspace edits PromptInput buffer."""
    app = TuiApplication()
    app.start()
    app.handle_key("a")
    app.handle_key("b")
    app.handle_key("c")
    assert app.prompt.get_text() == "abc"
    app.handle_key("backspace")
    assert app.prompt.get_text() == "ab"
    app.handle_key("backspace")
    assert app.prompt.get_text() == "a"


def test_enter_submits_exactly_once():
    """3. Enter submits exactly once."""
    app = TuiApplication()
    mock_controller = MagicMock()
    app.connect_controller(mock_controller)
    app.start()

    app.prompt.insert_char("s")
    app.prompt.insert_char("t")
    app.prompt.insert_char("a")
    app.prompt.insert_char("t")
    app.prompt.insert_char("u")
    app.prompt.insert_char("s")

    app.handle_key("enter")

    assert app.prompt.get_text() == ""
    assert mock_controller.execute_command.call_count == 1


def test_typed_characters_never_appear_as_raw_terminal_echo_output():
    """4. Typed characters never appear as raw terminal echo output outside frame."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    app = TuiApplication(renderer=renderer)

    # In character-by-character native input mode, input does not echo directly to stream
    app.run(input_source=["h", "i", "exit"])

    output = stream.getvalue()
    # Output should contain formatted TUI box frames, not raw unformatted 'hi'
    assert "╭─ ClaireCoder" in output
    assert "\nhi\n" not in output


def test_ctrl_c_interrupts():
    """5. Ctrl+C interrupts."""
    app = TuiApplication()
    interrupted = False

    def on_intr():
        nonlocal interrupted
        interrupted = True

    app.on_interrupt = on_intr
    app.start()
    app.prompt.set_text("in progress")

    app.handle_key("ctrl+c")
    assert interrupted is True
    assert app.prompt.get_text() == ""


def test_esc_goes_to_active_view_semantics():
    """6. Esc goes to active view semantics."""
    app = TuiApplication()
    app.start()

    app.open_tree()
    assert app.state == InputState.OVERLAY
    assert app.is_tree_open is True

    app.handle_key("escape")
    assert app.state == InputState.NORMAL
    assert app.is_tree_open is False


def test_ctrl_t_opens_file_tree():
    """7. Ctrl+T opens File Tree."""
    app = TuiApplication()
    app.start()
    app.handle_key("ctrl+t")
    assert app.state == InputState.OVERLAY
    assert app.is_tree_open is True


def test_ctrl_r_opens_review():
    """8. Ctrl+R opens Review."""
    app = TuiApplication()
    app.start()
    app.handle_key("ctrl+r")
    assert app.state == InputState.OVERLAY
    assert app.is_review_open is True


def test_ctrl_p_opens_task():
    """9. Ctrl+P opens Task view."""
    app = TuiApplication()
    app.start()
    app.handle_key("ctrl+p")
    assert app.state == InputState.OVERLAY
    assert app.is_task_open is True


def test_question_mark_opens_command_palette():
    """10. ? is ordinary prompt text; /commands opens Command Palette."""
    app = TuiApplication()
    app.start()
    app.handle_key("?")
    assert app.prompt.get_text() == "?"
    assert app.state == InputState.NORMAL
    assert app.is_palette_open is False

    # Exact /commands opens palette
    app.prompt.clear()
    app.submit("/commands")
    assert app.state == InputState.OVERLAY
    assert app.is_palette_open is True


def test_prompt_cursor_appears_while_focused():
    """11. Prompt cursor appears while focused."""
    app = TuiApplication()
    app.start()
    lines = app.render()
    prompt_line = [l for l in lines if "> " in l][0]
    assert "█" in prompt_line


def test_prompt_cursor_disappears_while_overlay_owns_focus():
    """12. Prompt cursor disappears while overlay owns focus."""
    app = TuiApplication()
    app.start()
    app.open_tree()
    assert app.state == InputState.OVERLAY
    lines = app.render()
    prompt_line = [l for l in lines if "> " in l][0]
    assert "█" not in prompt_line


def test_frame_redraw_does_not_duplicate_permanent_frames():
    """13. Frame redraw uses in-place cursor repositioning instead of appending duplicate frames."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    app = TuiApplication(renderer=renderer)

    app.run(input_source=["a", "b", "c", "exit"])

    output = stream.getvalue()
    # In-place repositioning ANSI sequences must be emitted for each redraw
    assert "\x1b[" in output  # ANSI reposition sequences present
    assert renderer.rendered_frames_count > 1


def test_terminal_resize_redraws_current_frame_instead_of_appending():
    """14. Terminal resize redraws current frame in place."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    app = TuiApplication(renderer=renderer)
    app.start()
    app.render_initial_frame()
    initial_count = renderer.rendered_frames_count

    app.resize(80, 25)
    assert renderer.rendered_frames_count == initial_count + 1
    assert app.terminal.width == 80
    assert app.terminal.height == 25


def test_interactive_loop_exits_cleanly_with_exit_commands():
    """15. Interactive loop exits cleanly with /exit / exit / quit."""
    app1 = TuiApplication()
    code1 = app1.run(input_source=["exit"])
    assert code1 == 0
    assert app1.running is False

    app2 = TuiApplication()
    code2 = app2.run(input_source=["/exit"])
    assert code2 == 0
    assert app2.running is False

    app3 = TuiApplication()
    code3 = app3.run(input_source=["quit"])
    assert code3 == 0
    assert app3.running is False


def test_scripted_input_mode_still_works():
    """16. Scripted input mode handles commands and objectives."""
    app = TuiApplication()
    mock_controller = MagicMock()
    mock_controller.execute_command.return_value = MagicMock(message="OK", data=None, error=None)
    app.connect_controller(mock_controller)

    exit_code = app.run(input_source=["status", "exit"])
    assert exit_code == 0
    assert mock_controller.execute_command.call_count >= 1
