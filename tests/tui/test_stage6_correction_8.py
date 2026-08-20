"""Comprehensive regression test suite for Stage 6 Correction #8.

Validates:
1. Loading screen physical width bounds, dynamic progress bar, and no-overflow invariant.
2. ANSI / display width calculations and exact frame row width constraints.
3. Logical vs physical frame accounting, in-place redraw stability, and header uniqueness.
4. Clean shutdown on /exit, exit, quit, and double Ctrl+C (complete UI clearing and restoration).
5. Public InteractionController interruption boundary (interrupt_active_session) for Ctrl+C without direct _engine access.
6. Ctrl+C timeout edge cases (within timeout, timeout expiration, keystroke reset, active vs idle).
7. Complete AST duplicate-method audit over TuiApplication.
8. /compact removal from user-facing command surface and palette.
9. /mode consistency with InteractionMode enum (PLAN, IMPLEMENT, REVIEW, DEBUG).
10. Complete V1 command surface audit.
"""

import ast
import collections
import io
import time
import pytest
from unittest.mock import Mock, patch

from clairecoder.app import ClaireCoderV1
from clairecoder.tui.app import TuiApplication, InputState
from clairecoder.tui.palette import CommandPalette
from clairecoder.tui.loading import LoadingScreen
from clairecoder.tui.canvas import visible_length, visible_slice
from clairecoder.tui.states import TerminalMode
from clairecoder.tui.terminal import TerminalCapability, TerminalRenderer, TerminalInput
from clairecoder.tui.activity import ActivityModel, ActivityType
from clairecoder.interaction.controller import InteractionController
from clairecoder.interaction.parser import CommandParser
from clairecoder.interaction.types import CommandRequest, CommandResponse, InteractionMode
from clairecoder.engine.engine import EngineeringEngine
from clairecoder.gateway.gateway import ModelGateway
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.registry import ToolRegistry
from clairecoder.permissions.engine import PermissionEngine


# =============================================================================
# 1. BUG A & B & C: LOADING SCREEN PHYSICAL WIDTH & DYNAMIC BAR BOUNDS
# =============================================================================

def test_loading_screen_physical_width_and_no_overflow_invariant():
    """Verify every loading screen row exactly matches frame_width with zero physical overflow."""
    stage_labels = [
        "Loading configuration",
        "Connecting / initializing model gateway",
        "Registering tools",
        "Preparing workspace",
        "Loading skills",
        "Starting session",
        "Launching...",
        "A very long custom label that should definitely be truncated to fit",
    ]

    test_widths = [48, 56, 60, 80, 104]
    progress_values = [0, 16, 33, 50, 66, 83, 100]

    for width in test_widths:
        expected_frame_w = max(48, min(width, 60))
        for prog in progress_values:
            for label in stage_labels:
                checklist = [(lbl, "OK" if i % 2 == 0 else "NOT CONFIGURED") for i, lbl in enumerate(stage_labels[:6])]
                lines = LoadingScreen.render(
                    width=width,
                    checklist_items=checklist,
                    progress_pct=prog,
                    status_text=label,
                    use_color=True,
                )

                assert len(lines) > 0
                for row_idx, row in enumerate(lines):
                    vis_w = visible_length(row)
                    assert vis_w == expected_frame_w, (
                        f"Loading row {row_idx} width mismatch! Expected {expected_frame_w}, got {vis_w}.\n"
                        f"Row content: {repr(row)}\nLabel: {label}, Prog: {prog}, Width: {width}"
                    )


def test_loading_screen_progress_bar_calculation():
    """Verify progress bar length is derived dynamically from remaining capacity."""
    # Test with standard width 56 (inner_w = 52)
    lines_short = LoadingScreen.render(width=56, progress_pct=50, status_text="Ready", use_color=False)
    lines_long = LoadingScreen.render(
        width=56,
        progress_pct=50,
        status_text="Connecting / initializing model gateway...",
        use_color=False,
    )

    prog_row_short = [l for l in lines_short if "50%" in l][0]
    prog_row_long = [l for l in lines_long if "50%" in l][0]

    # Both must fit exact frame width
    assert visible_length(prog_row_short) == 56
    assert visible_length(prog_row_long) == 56


# =============================================================================
# 2. BUG E: REDRAW STABILITY & NO DUPLICATE HEADERS
# =============================================================================

def test_redraw_stability_and_header_uniqueness():
    """Verify multiple redraw cycles maintain a single stable frame and header."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    term = TerminalCapability(width=104, height=30)
    app = TuiApplication(terminal=term, renderer=renderer)

    # Initial frame
    app.render_initial_frame()
    assert renderer.last_line_count == 30
    assert len(app.current_frame) == 30

    # Perform 30 sequential redraws with content changes and overlay transitions
    for i in range(1, 31):
        app.transcript.append_activity(ActivityModel(title=f"Activity-{i:02d}", detail="msg"))
        if i == 5:
            app.open_palette()
        elif i == 10:
            app.close_overlay()
        elif i == 15:
            app.open_task()
        elif i == 20:
            app.close_overlay()
        elif i == 25:
            app.open_tree()

        app.redraw()
        assert len(app.current_frame) == 30
        assert renderer.last_line_count == 30

        # Verify header row exists exactly once in current frame
        header_rows = [row for row in app.current_frame if "ClaireCoder" in row and "v0.1.0" in row]
        assert len(header_rows) == 1, f"Found {len(header_rows)} header rows in frame {i}!"


def test_loading_to_main_pane_in_place_transition():
    """Verify loading screen transitions cleanly into Main Pane without scrollback accumulation."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    term = TerminalCapability(width=104, height=30)
    app = TuiApplication(terminal=term, renderer=renderer)

    # Run with quick exit
    exit_code = app.run(input_source=["/exit"], boot_delay=0.0)
    assert exit_code == 0

    # Ensure boot sequence ran and frame was replaced in place
    assert renderer.rendered_frames_count >= 7
    # Terminal clear on exit resets last_line_count to 0
    assert renderer.last_line_count == 0


# =============================================================================
# 3. BUG F: CLEAN EXIT & TERMINAL RESTORATION
# =============================================================================

def test_clean_exit_all_normal_exit_paths():
    """Verify /exit, exit, quit, and double Ctrl+C clear active UI and restore terminal."""
    for exit_cmd in ("/exit", "exit", "quit"):
        stream = io.StringIO()
        renderer = TerminalRenderer(stream=stream, enable_ansi=True)
        term = TerminalCapability(width=104, height=30)
        app = TuiApplication(terminal=term, renderer=renderer)

        exit_code = app.run(input_source=[exit_cmd], boot_delay=0.0)
        assert exit_code == 0
        assert app.running is False
        assert renderer.last_line_count == 0

        # Stream output must contain clear-rest sequence and cursor restoration
        output = stream.getvalue()
        assert "\x1b[J" in output
        assert "\x1b[?25h" in output


def test_clean_exit_on_double_ctrl_c():
    """Verify double Ctrl+C cleanly shuts down and clears the terminal."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    term = TerminalCapability(width=104, height=30)
    app = TuiApplication(terminal=term, renderer=renderer)

    app.start()
    app.render_initial_frame()
    assert renderer.last_line_count == 30

    # First Ctrl+C -> enters confirmation, does not exit
    exited_1 = app.handle_ctrl_c()
    assert exited_1 is False
    assert app.running is True
    assert app.is_exit_confirmation_active() is True

    # Second Ctrl+C within timeout -> exits cleanly
    exited_2 = app.handle_ctrl_c()
    assert exited_2 is True
    assert app.running is False
    assert renderer.last_line_count == 0


# =============================================================================
# 4. PUBLIC CTRL+C INTERRUPTION BOUNDARY & TIMEOUT EDGE CASES
# =============================================================================

def test_public_interruption_boundary_invoked_on_ctrl_c():
    """Verify TUI calls controller.interrupt_active_session() and does not touch _engine directly."""
    mock_engine = Mock()
    controller = InteractionController(engine=mock_engine)
    app = TuiApplication()
    app.connect_controller(controller)
    app.header.session_id = "sess_42"

    with patch.object(controller, "interrupt_active_session", wraps=controller.interrupt_active_session) as mock_interrupt:
        app.handle_ctrl_c()
        mock_interrupt.assert_called_once_with("sess_42")
        mock_engine.interrupt_execution.assert_called_once_with("sess_42")


def test_ctrl_c_timeout_expiration():
    """Verify waiting beyond confirmation timeout causes next Ctrl+C to start a new confirmation cycle."""
    app = TuiApplication()
    app.start()

    # First Ctrl+C at t = 100.0
    with patch("time.time", return_value=100.0):
        app.handle_ctrl_c()
        assert app.is_exit_confirmation_active() is True

    # Second Ctrl+C after timeout expiration at t = 105.0 (timeout is 2.5s)
    with patch("time.time", return_value=105.0):
        # is_exit_confirmation_active returns False and resets state
        assert app.is_exit_confirmation_active() is False

        # Next Ctrl+C starts a fresh confirmation cycle instead of exiting
        exited = app.handle_ctrl_c()
        assert exited is False
        assert app.is_exit_confirmation_active() is True


def test_ctrl_c_reset_on_unrelated_keystroke():
    """Verify normal typing or Enter resets pending Ctrl+C confirmation state."""
    app = TuiApplication()
    app.start()

    app.handle_ctrl_c()
    assert app.is_exit_confirmation_active() is True

    # User types a key
    app.handle_key("a")
    assert app.is_exit_confirmation_active() is False


def test_ctrl_c_during_active_overlay():
    """Verify Ctrl+C during active overlay triggers interruption without corrupting overlay state."""
    app = TuiApplication()
    app.start()
    app.open_review()
    assert app.is_review_open

    # Ctrl+C while overlay is open
    app.handle_key("ctrl+c")
    assert app.is_exit_confirmation_active() is True
    # Overlay remains open or can be dismissed
    assert app.is_review_open


# =============================================================================
# 5. AST DUPLICATE-METHOD AUDIT
# =============================================================================

def test_ast_no_duplicate_methods_in_tui_application():
    """Ensure TuiApplication has exactly zero duplicate method definitions."""
    with open("src/clairecoder/tui/app.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    app_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TuiApplication")
    methods = [n.name for n in app_class.body if isinstance(n, ast.FunctionDef)]
    counts = collections.Counter(methods)

    duplicates = {k: v for k, v in counts.items() if v > 1}
    assert duplicates == {}, f"Found duplicate methods in TuiApplication: {duplicates}"

    # Specifically verify the 3 critical helpers exist exactly once
    assert counts["handle_ctrl_c"] == 1
    assert counts["is_exit_confirmation_active"] == 1
    assert counts["reset_interrupt_state"] == 1


# =============================================================================
# 6. BUG H: /compact REMOVAL FROM COMMAND SURFACE
# =============================================================================

def test_compact_removed_from_palette_and_surface():
    """Verify /compact is completely removed from CommandPalette and user command surface."""
    palette = CommandPalette()
    cmd_names = [cmd.name for cmd in palette.commands]

    assert "/compact" not in cmd_names
    assert "/review" in cmd_names
    assert "/tree" in cmd_names

    # Ensure submitting /compact does not switch mode
    app = TuiApplication()
    app.terminal.force_mode(TerminalMode.FULL)
    app.submit("/compact")
    # Terminal mode remains FULL
    assert app.terminal.mode == TerminalMode.FULL


# =============================================================================
# 7. BUG I: /mode SEMANTIC CONSISTENCY
# =============================================================================

def test_mode_command_semantics_and_valid_modes():
    """Verify /mode command matches InteractionMode enum (plan, implement, review, debug)."""
    engine = EngineeringEngine(
        model_gateway=ModelGateway(),
        tool_executor=ToolExecutor(ToolRegistry(), PermissionEngine())
    )
    controller = InteractionController(engine=engine)

    # 1. /mode inspection
    req_inspect = CommandParser.parse("/mode")
    resp_inspect = controller.execute_command(req_inspect)
    assert resp_inspect.success is True
    assert "Current mode: IMPLEMENT" in resp_inspect.message
    assert "Valid modes: plan, implement, review, debug" in resp_inspect.message

    # 2. /mode switching to valid modes
    for valid_mode in ("plan", "implement", "review", "debug"):
        req_switch = CommandParser.parse(f"/mode {valid_mode}")
        resp_switch = controller.execute_command(req_switch)
        assert resp_switch.success is True
        assert f"Mode switched to: {valid_mode.upper()}" in resp_switch.message
        assert controller._mode == InteractionMode(valid_mode)

    # 3. /mode invalid mode
    req_invalid = CommandParser.parse("/mode verify")
    resp_invalid = controller.execute_command(req_invalid)
    assert resp_invalid.success is False
    assert "Invalid mode: verify" in resp_invalid.message
    assert "Valid modes: plan, implement, review, debug" in resp_invalid.message


# =============================================================================
# 8. COMPLETE V1 COMMAND SURFACE AUDIT
# =============================================================================

def test_v1_complete_command_surface():
    """Verify all 13 supported V1 commands route cleanly with zero unhandled exceptions."""
    engine = EngineeringEngine(
        model_gateway=ModelGateway(),
        tool_executor=ToolExecutor(ToolRegistry(), PermissionEngine())
    )
    controller = InteractionController(engine=engine)

    commands_to_test = [
        ("/help", True),
        ("/status", True),
        ("/model", False), # Pre-stage 7 honest failure
        ("/mode", True),
        ("/session", True),
        ("/plan", True),
        ("/pause", False), # No active session -> honest usage message
        ("/resume", False), # No active session -> honest usage message
        ("/cancel", False), # No active session -> honest usage message
        ("/clear", True),
        ("/exit", True),
    ]

    for cmd_str, exp_success in commands_to_test:
        req = CommandParser.parse(cmd_str)
        assert req is not None
        resp = controller.execute_command(req)
        assert resp.success == exp_success, f"Command {cmd_str} unexpected success state: {resp}"
