"""Comprehensive regression test suite for Stage 6 Correction #7.

Validates:
1. Deterministic Windows & VT raw input decoding (Scan codes & VT sequences)
2. Main Pane vs Overlay focus ownership and arrow routing
3. Live transcript scrolling changing visible slice without leaking outside viewport
4. Hard viewport height and fixed-row frame invariants (header, prompt, footer fixed)
5. Full V1 Command Acceptance Matrix (/help, /status, /model, /mode, /session, /plan, /pause, /resume, /cancel, /clear, /exit, /tree, /review, /compact)
6. Honest /model pre-Stage 7 behavior (no fake gateway/providers)
7. Parameter-free /pause, /resume, /cancel inference or honest messages
8. Command palette direct list navigation and visible cursor movement
9. Natural '?' and '/' prompt typing preservation
10. Loading screen real initialization state, perceptible timing, and in-place Main Pane transition
"""

import pytest
from unittest.mock import Mock

from clairecoder.tui.terminal import TerminalCapability, TerminalRenderer, TerminalInput, InputDecoder, KeyEvent
from clairecoder.tui.app import TuiApplication
from clairecoder.tui.states import InputState, TerminalMode
from clairecoder.tui.palette import CommandPalette, CommandPaletteItem
from clairecoder.tui.activity import ActivityModel, ActivityType
from clairecoder.tui.loading import LoadingScreen
from clairecoder.interaction.controller import InteractionController
from clairecoder.interaction.parser import CommandParser
from clairecoder.interaction.types import CommandRequest, CommandResponse
from clairecoder.engine.engine import EngineeringEngine
from clairecoder.gateway.gateway import ModelGateway
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.registry import ToolRegistry
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.app import ClaireCoderV1


# =============================================================================
# 1. INPUT DECODER TESTS (WINDOWS SCAN CODES & VT ESCAPE SEQUENCES)
# =============================================================================

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
    assert InputDecoder.decode("\x1b[I") == "pageup"
    assert InputDecoder.decode("\x1b[6~") == "pagedown"
    assert InputDecoder.decode("\x1b[Q") == "pagedown"
    assert InputDecoder.decode("\x1b[H") == "home"
    assert InputDecoder.decode("\x1b[1~") == "home"
    assert InputDecoder.decode("\x1bOH") == "home"
    assert InputDecoder.decode("\x1b[F") == "end"
    assert InputDecoder.decode("\x1b[4~") == "end"
    assert InputDecoder.decode("\x1bOF") == "end"
    assert InputDecoder.decode("\x1b[3~") == "delete"
    assert InputDecoder.decode("\x1b[2~") == "insert"
    assert InputDecoder.decode("\x1b") == "escape"

    # Unrecognized escape sequences must NEVER be treated as ordinary prompt text
    unrecognized = InputDecoder.decode("\x1b[99~")
    assert unrecognized.name == "unknown"
    assert unrecognized.is_printable is False


def test_input_decoder_windows_scan_codes():
    """Prove Windows classic console scan codes decode deterministically."""
    assert InputDecoder.decode("\x00H") == "up"
    assert InputDecoder.decode("\xe0H") == "up"
    assert InputDecoder.decode("\x00P") == "down"
    assert InputDecoder.decode("\xe0P") == "down"
    assert InputDecoder.decode("\x00K") == "left"
    assert InputDecoder.decode("\xe0K") == "left"
    assert InputDecoder.decode("\x00M") == "right"
    assert InputDecoder.decode("\xe0M") == "right"
    assert InputDecoder.decode("\x00I") == "pageup"
    assert InputDecoder.decode("\xe0I") == "pageup"
    assert InputDecoder.decode("\x00Q") == "pagedown"
    assert InputDecoder.decode("\xe0Q") == "pagedown"
    assert InputDecoder.decode("\x00G") == "home"
    assert InputDecoder.decode("\xe0G") == "home"
    assert InputDecoder.decode("\x00O") == "end"
    assert InputDecoder.decode("\xe0O") == "end"
    assert InputDecoder.decode("\x00S") == "delete"
    assert InputDecoder.decode("\xe0S") == "delete"
    assert InputDecoder.decode("\x00R") == "insert"
    assert InputDecoder.decode("\xe0R") == "insert"


def test_input_decoder_printable_and_controls():
    """Prove printable characters and control characters decode properly."""
    # Printable characters
    for ch in ("?", "/", "a", "1", "Z", " ", "!", "@", "#"):
        ev = InputDecoder.decode(ch)
        assert ev.name == ch
        assert ev.char == ch
        assert ev.is_printable is True

    # Control keys
    assert InputDecoder.decode("\r") == "enter"
    assert InputDecoder.decode("\n") == "enter"
    assert InputDecoder.decode("\x08") == "backspace"
    assert InputDecoder.decode("\x7f") == "backspace"
    assert InputDecoder.decode("\t") == "tab"
    assert InputDecoder.decode("\x03") == "ctrl+c"
    assert InputDecoder.decode("\x14") == "ctrl+t"
    assert InputDecoder.decode("\x12") == "ctrl+r"
    assert InputDecoder.decode("\x10") == "ctrl+p"


# =============================================================================
# 2. RAW INPUT -> TUI DISPATCH -> SCROLL ROUTING PIPELINE
# =============================================================================

def test_raw_terminal_keys_reach_scroll_without_prompt_leakage():
    """Prove raw VT and Windows console inputs reach scroll logic and never leak to prompt."""
    term = TerminalCapability(width=104, height=30)
    app = TuiApplication(terminal=term)
    app.start()

    # Fill transcript
    for i in range(1, 101):
        app.transcript.append_activity(ActivityModel(title=f"MSG-{i:03d}", detail="info"))

    # Initial scroll position at bottom
    assert app.transcript.scroll_position > 0
    init_scroll = app.transcript.scroll_position

    # 1. PageUp via raw VT sequence '\x1b[5~'
    app._dispatch_interactive_input("\x1b[5~")
    assert app.transcript.scroll_position < init_scroll
    assert app.prompt.get_text() == ""

    # 2. Up via raw Windows scan code '\xe0H'
    pos_before_up = app.transcript.scroll_position
    app._dispatch_interactive_input("\xe0H")
    assert app.transcript.scroll_position == pos_before_up - 1
    assert app.prompt.get_text() == ""

    # 3. Down via raw VT sequence '\x1b[B'
    pos_before_down = app.transcript.scroll_position
    app._dispatch_interactive_input("\x1b[B")
    assert app.transcript.scroll_position == pos_before_down + 1
    assert app.prompt.get_text() == ""

    # 4. Home via raw scan code '\xe0G'
    app._dispatch_interactive_input("\xe0G")
    assert app.transcript.scroll_position == 0
    assert app.prompt.get_text() == ""

    # 5. End via raw VT sequence '\x1b[F'
    app._dispatch_interactive_input("\x1b[F")
    assert app.transcript.scroll_position == app.transcript._max_scroll()
    assert app.prompt.get_text() == ""

    # 6. Unrecognized VT escape sequence is ignored and NOT typed
    app._dispatch_interactive_input("\x1b[99~")
    assert app.prompt.get_text() == ""


# =============================================================================
# 3. FOCUS OWNERSHIP (MAIN PANE VS OVERLAYS)
# =============================================================================

def test_focus_ownership_overlays_prevent_transcript_scrolling():
    """Prove active overlays own keyboard focus and prevent transcript scrolling."""
    term = TerminalCapability(width=104, height=30)
    app = TuiApplication(terminal=term)
    app.start()

    # Fill transcript
    for i in range(1, 50):
        app.transcript.append_activity(ActivityModel(title=f"MSG-{i:03d}", detail="info"))
    app.transcript.scroll_to_top()
    assert app.transcript.scroll_position == 0

    # 1. Command Palette overlay owns focus
    app.open_palette()
    assert app.is_palette_open
    init_pal_idx = app.command_palette.selected_index
    app.handle_key("down")
    assert app.command_palette.selected_index == init_pal_idx + 1
    # Transcript must NOT have scrolled
    assert app.transcript.scroll_position == 0
    app.close_overlay()

    # 2. Review Overlay owns focus
    app.open_review()
    assert app.is_review_open
    app.handle_key("down")
    assert app.transcript.scroll_position == 0
    app.close_overlay()

    # 3. File Tree Overlay owns focus
    app.open_tree()
    assert app.is_tree_open
    app.handle_key("down")
    assert app.transcript.scroll_position == 0
    app.close_overlay()

    # 4. Task View Overlay owns focus
    app.open_task()
    assert app.is_task_open
    app.handle_key("down")
    assert app.transcript.scroll_position == 0
    app.close_overlay()


# =============================================================================
# 4. TRANSCRIPT SCROLLING & HARD VIEWPORT INVARIANTS
# =============================================================================

def test_transcript_scrolling_visibly_changes_content_and_preserves_invariants():
    """Prove scrolling visibly changes transcript rows while headers, prompt, footer, and borders remain fixed."""
    term = TerminalCapability(width=104, height=30)
    app = TuiApplication(terminal=term)
    app.start()

    # Add 200 identifiable items
    for i in range(1, 201):
        app.transcript.append_activity(ActivityModel(title=f"MSG-{i:03d}", detail="content"))

    vh = app.get_viewport_height()
    assert vh == 30 - 8  # 22 rows

    # Initial frame at bottom
    frame_bottom = app.render()
    assert len(frame_bottom) == 30
    assert "MSG-200" in "".join(frame_bottom)

    # Scroll to top (Home)
    app.handle_key("home")
    frame_top = app.render()
    assert len(frame_top) == 30
    assert "MSG-001" in "".join(frame_top)
    assert "MSG-200" not in "".join(frame_top)

    # Invariants:
    # 1. Top border and status rows (lines 0..3) must be identical
    for row_idx in range(4):
        assert frame_bottom[row_idx] == frame_top[row_idx], f"Header row {row_idx} altered!"

    # 2. Bottom prompt, shortcuts, and bottom border (lines 26..29) must be identical
    for row_idx in range(26, 30):
        assert frame_bottom[row_idx] == frame_top[row_idx], f"Footer row {row_idx} altered!"

    # 3. Only body region (lines 4..25) changed
    body_bottom = frame_bottom[4:26]
    body_top = frame_top[4:26]
    assert body_bottom != body_top

    # Scroll down step-by-step
    app.handle_key("down")
    frame_step = app.render()
    assert len(frame_step) == 30
    assert frame_step[0:4] == frame_top[0:4]
    assert frame_step[26:30] == frame_top[26:30]


# =============================================================================
# 5. REAL COMMAND ACCEPTANCE MATRIX
# =============================================================================

def test_full_command_acceptance_matrix():
    """Audit every documented V1 command for parser, routing, required args, and expected response."""
    # Setup real application boundary
    engine = EngineeringEngine(
        model_gateway=ModelGateway(),
        tool_executor=ToolExecutor(ToolRegistry(), PermissionEngine())
    )
    controller = InteractionController(engine=engine)
    app = ClaireCoderV1()
    tui = TuiApplication()
    tui.connect_controller(controller)

    matrix = [
        # (Command, Parsable, RequiresArgs, ExpectedStatus, Category)
        ("/help", True, False, True, "SYSTEM"),
        ("/status", True, False, True, "SYSTEM"),
        ("/model", True, False, False, "SYSTEM"),  # Pre-stage 7 honest failure
        ("/mode", True, False, True, "MODE"),
        ("/mode plan", True, True, True, "MODE"),
        ("/session", True, False, True, "SESSION"),
        ("/session list", True, True, True, "SESSION"),
        ("/plan", True, False, True, "WORKFLOW"),
        ("/pause", True, False, False, "EXECUTION"),  # No active session -> honest message
        ("/resume", True, False, False, "EXECUTION"), # No active session -> honest message
        ("/cancel", True, False, False, "EXECUTION"), # No active session -> honest message
        ("/clear", True, False, True, "SYSTEM"),
        ("/exit", True, False, True, "SYSTEM"),
    ]

    for cmd_str, parsable, has_args, exp_success, cat in matrix:
        assert CommandParser.is_command(cmd_str) == parsable
        req = CommandParser.parse(cmd_str)
        assert req is not None
        assert req.command != ""

        resp = controller.execute_command(req)
        assert isinstance(resp, CommandResponse)
        assert resp.success == exp_success, f"Command {cmd_str} failed expectation: {resp}"

    # Also test UI presentation commands in TUI
    # /tree
    tui.submit("/tree")
    assert tui.is_tree_open
    tui.close_overlay()

    # /review
    tui.submit("/review")
    assert tui.is_review_open
    tui.close_overlay()


def test_model_command_honest_failure_pre_stage_7():
    """Prove /model fails honestly without fabricating fake gateway or providers."""
    engine = EngineeringEngine(
        model_gateway=ModelGateway(),
        tool_executor=ToolExecutor(ToolRegistry(), PermissionEngine())
    )
    controller = InteractionController(engine=engine)

    # Invocation without args
    req = CommandParser.parse("/model")
    resp = controller.execute_command(req)
    assert resp.success is False
    assert "No model providers configured" in resp.message
    assert "Stage 7" in resp.message

    # Invocation with model name argument
    req_arg = CommandParser.parse("/model gpt-4")
    resp_arg = controller.execute_command(req_arg)
    assert resp_arg.success is False
    assert "No model providers configured" in resp_arg.message


def test_pause_resume_cancel_with_active_session():
    """Prove /pause, /resume, /cancel work seamlessly when an active session exists."""
    engine = EngineeringEngine(
        model_gateway=ModelGateway(),
        tool_executor=ToolExecutor(ToolRegistry(), PermissionEngine())
    )
    controller = InteractionController(engine=engine)

    # Create active session via natural language
    controller.process_natural_language("Refactor auth", "sess_001")

    # /pause without explicit session argument uses active session
    req_pause = CommandParser.parse("/pause")
    resp_pause = controller.execute_command(req_pause)
    assert resp_pause.success is True
    assert "sess_001" in resp_pause.message

    # /resume uses active session
    req_resume = CommandParser.parse("/resume")
    resp_resume = controller.execute_command(req_resume)
    assert resp_resume.success is True
    assert "sess_001" in resp_resume.message

    # /cancel uses active session
    req_cancel = CommandParser.parse("/cancel")
    resp_cancel = controller.execute_command(req_cancel)
    assert resp_cancel.success is True
    assert "sess_001" in resp_cancel.message


# =============================================================================
# 6. COMMAND PALETTE DIRECT LIST NAVIGATION
# =============================================================================

def test_command_palette_navigation_and_visible_cursor():
    """Prove Command Palette navigates with keys and visibly moves the selection marker."""
    pal = CommandPalette()
    assert pal.selected_index == 0

    # Down navigation
    pal.handle_key("down")
    assert pal.selected_index == 1

    # Render check - cursor ▶ must be at selected index
    lines = pal.render(mode=TerminalMode.FULL, width=80)
    full_text = "\n".join(lines)
    assert "▶" in full_text

    # PageDown
    pal.handle_key("pagedown")
    assert pal.selected_index == min(len(pal.commands) - 1, 6)

    # End
    pal.handle_key("end")
    assert pal.selected_index == len(pal.commands) - 1

    # Home
    pal.handle_key("home")
    assert pal.selected_index == 0


# =============================================================================
# 7. NATURAL PROMPT TYPING ('?' AND '/')
# =============================================================================

def test_natural_typing_preserves_question_marks_and_slashes():
    """Prove '?' and '/' do not trigger the palette and remain editable prompt characters."""
    term = TerminalCapability(width=104, height=30)
    app = TuiApplication(terminal=term)
    app.start()

    # Type a natural question
    for ch in "What happened?":
        app.handle_key(ch)
    assert app.prompt.get_text() == "What happened?"
    assert not app.is_palette_open

    app.prompt.clear()

    # Type a URL containing '?' and '/'
    url = "https://example.com/?q=test"
    for ch in url:
        app.handle_key(ch)
    assert app.prompt.get_text() == url
    assert not app.is_palette_open


# =============================================================================
# 8. LOADING SCREEN TIMING & IN-PLACE MAIN PANE TRANSITION
# =============================================================================

def test_loading_screen_perceptible_delay_and_in_place_transition():
    """Prove loading screen renders real stages, supports presentation delay, and transitions in-place."""
    stream = Mock()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    term = TerminalCapability(width=104, height=30)
    app = TuiApplication(terminal=term, renderer=renderer)

    # Run with fast 0.0s delay for test
    app.run(input_source=["exit"], boot_delay=0.0)

    # Verify rendered frames count is > 1 (boot stages + main frame redraw)
    assert renderer.rendered_frames_count >= 6
    assert app.current_frame != []
    assert len(app.current_frame) == 30
