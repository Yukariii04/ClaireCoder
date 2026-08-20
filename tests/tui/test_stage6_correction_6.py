"""Comprehensive test suite for CLI/TUI Stage 6 Correction #6.

Covers:
1. Startup architecture, first-run setup hook & honest configuration status.
2. Loading screen in-place replacement (disappears completely, replaced by Main Pane).
3. Real boot initialization sequence with dynamic status badges & progress.
4. Hard transcript clipping & frame height invariance under any activity volume.
5. Live transcript scrolling (PageUp/PageDown/Home/End/Up/Down) with fixed header/prompt/footer.
6. Follow-tail auto-scroll behavior & position preservation.
7. Unobtrusive scrollbar indicator in Full mode when content overflows viewport.
8. Command Palette: direct selectable command list with no filter field, full navigation.
9. '?' as ordinary prompt text; '/commands' exact command trigger.
10. Single-line footer without obsolete help.
11. Real Task View objective tracking from application/workflow state.
12. Main Pane continuous conversational stream: User prompt + Claire response + activities.
13. Edge-case card width and border alignment invariants.
"""
import io
import pytest
from unittest.mock import Mock, MagicMock, patch

from clairecoder.app import ClaireCoderV1
from clairecoder.tui.app import TuiApplication, InputState
from clairecoder.tui.palette import CommandPalette, CommandPaletteItem
from clairecoder.tui.task import TaskViewOverlay
from clairecoder.tui.loading import LoadingScreen
from clairecoder.tui.canvas import visible_length, visible_slice
from clairecoder.tui.states import TerminalMode
from clairecoder.tui.terminal import TerminalRenderer
from clairecoder.tui.activity import ActivityModel, ActivityType, ActivityState
from clairecoder.interaction.controller import InteractionController
from clairecoder.engine.types import EngineeringObjective


def test_first_run_setup_hook_and_configuration_status():
    """Verify application configuration boundary returns 'not_configured' or 'configured'."""
    # 1. Unconfigured default instance (no providers registered in Stage 6)
    app = ClaireCoderV1.create_default()
    assert app.check_configuration_status() == "not_configured"

    # 2. Configured instance with mock provider
    mock_gw = Mock()
    mock_gw._providers = {"mock_prov": Mock()}
    app_configured = ClaireCoderV1(model_gateway=mock_gw)
    assert app_configured.check_configuration_status() == "configured"


def test_loading_screen_replaces_in_place_without_scrollback_leak():
    """Verify loading screen is completely replaced by Main Pane in-place during startup."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    app = TuiApplication(renderer=renderer)
    app.resize(110, 30)

    # Run with quick exit
    exit_code = app.run(input_source=["/exit"])
    assert exit_code == 0

    # Verify that in-place redraw was utilized to replace the boot screen
    assert renderer.rendered_frames_count > 1
    assert len(app.current_frame) == 30


def test_real_boot_sequence_and_checklist_badges():
    """Verify boot sequence progresses through stages with real checklist badges."""
    loading = LoadingScreen()
    checklist = [
        ("Loading configuration", "OK"),
        ("Connecting model gateway", "NOT CONFIGURED"),
        ("Registering tools", "OK"),
        ("Preparing workspace", "OK"),
        ("Loading skills", "OK"),
        ("Starting session", "OK"),
    ]
    lines = loading.render(
        checklist_items=checklist,
        progress_pct=100,
        status_text="Launching..."
    )
    full_text = "\n".join(lines)

    assert "> Loading configuration" in full_text
    assert "[ OK ]" in full_text
    assert "> Connecting model gateway" in full_text
    assert "[ NOT CONFIGURED ]" in full_text
    assert "100%" in full_text
    assert "Launching..." in full_text


def test_hard_transcript_clipping_and_frame_height_invariance():
    """Verify viewport height is strictly clipped and outer frame height never changes."""
    app = TuiApplication()
    app.resize(110, 30)

    # Initial frame
    initial_lines = app.render()
    assert len(initial_lines) == 30
    assert initial_lines[0].startswith("╭─ ClaireCoder")
    assert initial_lines[-1].startswith("╰")

    # Add 100 activities of varying lengths
    for i in range(100):
        app.transcript.append_activity(ActivityModel(
            id=f"act_{i}",
            type=ActivityType.TOOL,
            state=ActivityState.COMPLETED,
            title=f"Activity {i} with a very long descriptive title that exceeds standard width boundaries",
            detail=f"Detailed execution trace for activity number {i} with multiple arguments and output strings"
        ))

    # Render with 100 activities
    overflow_lines = app.render()
    assert len(overflow_lines) == 30
    assert overflow_lines[0].startswith("╭─ ClaireCoder")
    assert overflow_lines[-1].startswith("╰")

    # Verify every single row matches box_w exactly
    box_w = visible_length(overflow_lines[0])
    assert box_w >= 104
    for idx, row in enumerate(overflow_lines):
        assert visible_length(row) == box_w, f"Row {idx} length {visible_length(row)} != {box_w}"


def test_scrolling_does_not_move_header_prompt_or_footer():
    """Verify scrolling changes visible transcript slice while header, prompt, and footer remain invariant."""
    app = TuiApplication()
    app.resize(110, 30)

    for i in range(50):
        app.transcript.append_activity(ActivityModel(
            id=f"act_{i}",
            type=ActivityType.TOOL,
            state=ActivityState.COMPLETED,
            title=f"Task {i:02d}",
            detail=f"Result {i:02d}"
        ))

    # Bottom frame
    bottom_frame = app.render()
    header_bottom = bottom_frame[:4]
    prompt_bottom = bottom_frame[-3]
    footer_bottom = bottom_frame[-2]

    # Scroll up by page
    app.handle_key("pageup")
    scrolled_frame = app.render()
    assert len(scrolled_frame) == 30

    header_scrolled = scrolled_frame[:4]
    prompt_scrolled = scrolled_frame[-3]
    footer_scrolled = scrolled_frame[-2]

    assert header_bottom == header_scrolled
    assert prompt_bottom == prompt_scrolled
    assert footer_bottom == footer_scrolled
    # But transcript content is different!
    assert bottom_frame[4:26] != scrolled_frame[4:26]

    # Home / End
    app.handle_key("home")
    assert app.transcript.scroll_position == 0
    home_frame = app.render()
    assert home_frame[:4] == header_bottom

    app.handle_key("end")
    assert app.transcript.scroll_position == app.transcript._max_scroll()
    end_frame = app.render()
    assert end_frame == bottom_frame


def test_follow_tail_behavior():
    """Verify follow-tail auto-scrolls on new activity only when at bottom."""
    app = TuiApplication()
    app.resize(110, 30)

    for i in range(25):
        app.transcript.append_activity(ActivityModel(id=f"a_{i}", title=f"A {i}"))

    # Initial state: at bottom, follow-tail is True
    assert app.transcript._follow_tail is True
    assert app.transcript.scroll_position == app.transcript._max_scroll()

    # User scrolls up -> follow-tail disengages
    app.handle_key("up")
    assert app.transcript._follow_tail is False
    saved_pos = app.transcript.scroll_position

    # Append new activity -> scroll position preserved, does NOT forcibly yank to bottom
    app.transcript.append_activity(ActivityModel(id="a_new", title="A New"))
    assert app.transcript.scroll_position == saved_pos

    # Scroll back to bottom -> follow-tail re-engages
    app.handle_key("end")
    assert app.transcript._follow_tail is True
    assert app.transcript.scroll_position == app.transcript._max_scroll()


def test_scrollbar_indicator_renders_in_full_mode():
    """Verify scrollbar indicator renders when transcript exceeds viewport."""
    app = TuiApplication()
    app.resize(110, 30)

    # 1. No scrollbar when transcript fits inside viewport
    lines_empty = app.render()
    assert not any("▓" in line for line in lines_empty)

    # 2. Add 40 activities -> scrollbar thumb rendered on right edge
    for i in range(40):
        app.transcript.append_activity(ActivityModel(id=f"act_{i}", title=f"T {i}"))

    lines_full = app.render()
    body_lines = lines_full[4:26]
    assert any("▓" in line for line in body_lines)
    assert any("░" in line for line in body_lines)


def test_command_palette_no_filter_and_direct_navigation():
    """Verify command palette has NO filter field and supports complete keyboard navigation."""
    palette = CommandPalette()
    lines = palette.render(mode=TerminalMode.FULL, width=80)
    full_text = "\n".join(lines)

    # Verify no filter / search line
    assert "Filter:" not in full_text
    assert "Search:" not in full_text
    assert "↑/↓ select   Enter open   Esc back" in full_text

    # Verify categories and command items
    assert "APPLICATION / INTERACTION" in full_text
    assert "UI / PRESENTATION" in full_text
    assert "/help" in full_text
    assert "/exit" in full_text
    assert "/tree" in full_text
    assert "/review" in full_text

    # Selection cursor starts at 0
    assert palette.selected_index == 0
    assert palette.selected_command.name == "/help"
    assert any("▶ /help" in l for l in lines)

    # Down / Up navigation
    palette.handle_key("down")
    assert palette.selected_index == 1
    assert palette.selected_command.name == "/status"

    palette.handle_key("up")
    assert palette.selected_index == 0
    assert palette.selected_command.name == "/help"

    # End / Home
    palette.handle_key("end")
    assert palette.selected_index == len(palette.commands) - 1
    assert palette.selected_command.name == "/review"

    palette.handle_key("home")
    assert palette.selected_index == 0

    # Enter callback
    mock_select = Mock()
    palette.on_select = mock_select
    palette.handle_key("enter")
    mock_select.assert_called_once_with(palette.commands[0])

    # Esc callback
    mock_close = Mock()
    palette.on_close = mock_close
    palette.handle_key("escape")
    mock_close.assert_called_once()


def test_question_mark_is_normal_text_and_slash_commands_opens_palette():
    """Verify '?' is ordinary prompt text and '/commands' opens the palette."""
    app = TuiApplication()
    app.start()
    app.resize(110, 30)

    # Type 'What?'
    for ch in "What?":
        app.handle_key(ch)
    assert app.prompt.get_text() == "What?"
    assert app.state == InputState.NORMAL
    assert app.active_overlay is None

    app.prompt.clear()

    # Submit '/commands'
    app.submit("/commands")
    assert app.state == InputState.OVERLAY
    assert app.active_overlay == "palette"

    # Esc returns to Main Pane
    app.handle_key("escape")
    assert app.state == InputState.NORMAL
    assert app.active_overlay is None


def test_footer_is_single_line_without_obsolete_help():
    """Verify the footer is strictly one line without '? help'."""
    app = TuiApplication()
    app.resize(110, 30)
    lines = app.render()
    footer = lines[-2]

    assert "? help" not in footer
    assert "ctrl+c interrupt" in footer
    assert "ctrl+t file tree" in footer
    assert "ctrl+r review changes" in footer
    assert "ctrl+p task view" in footer
    assert "/commands" in footer


def test_task_view_displays_actual_objective():
    """Verify Task View overlay displays actual runtime objective."""
    task_view = TaskViewOverlay()
    
    # Default uninitialized
    lines_init = task_view.render(mode=TerminalMode.FULL, width=60)
    assert "Objective: None" in "\n".join(lines_init)

    # Real objective set
    task_view.objective = "Migrate database schema to v2"
    lines_set = task_view.render(mode=TerminalMode.FULL, width=60)
    text_set = "\n".join(lines_set)
    assert "Objective:" in text_set
    assert "Migrate database schema to v2" in text_set
    assert "Add streaming decode support" not in text_set


def test_main_pane_conversation_model():
    """Verify submitting a prompt records User prompt and Claire response in transcript."""
    mock_engine = Mock()
    mock_engine.session_id = "sess_conv"
    mock_engine.receive_objective.return_value = Mock(id="obj_c1", request="Create user dashboard")
    mock_engine.state.value = "ready"

    controller = InteractionController(engine=mock_engine)
    app = TuiApplication()
    app.connect_controller(controller)
    app.resize(110, 30)

    # Submit prompt
    app.submit("Create user dashboard")

    activities = app.transcript.get_activities()
    user_acts = [a for a in activities if a.type == ActivityType.MESSAGE and a.title == "User"]
    claire_acts = [a for a in activities if a.type == ActivityType.MESSAGE and a.title == "Claire"]

    assert len(user_acts) == 1
    assert user_acts[0].detail == "Create user dashboard"
    assert len(claire_acts) == 1
    assert "Objective accepted" in claire_acts[0].detail
    assert app.task_view.objective == "Create user dashboard"

    # Verify visual rendering in Main Pane
    rendered = "\n".join(app.render())
    assert "> Create user dashboard" in rendered
    assert "Claire:" in rendered


def test_card_width_and_border_alignment_invariants():
    """Verify card border alignment holds under long content across all modes."""
    # Palette overlay card
    palette = CommandPalette()
    for mode in (TerminalMode.FULL, TerminalMode.COMPACT):
        lines = palette.render(mode=mode, width=80)
        card_w = visible_length(lines[0])
        for l in lines:
            assert visible_length(l) == card_w

    # Task overlay card with long objective
    task = TaskViewOverlay(objective="A" * 120)
    for mode in (TerminalMode.FULL, TerminalMode.COMPACT):
        lines = task.render(mode=mode, width=70)
        card_w = visible_length(lines[0])
        for l in lines:
            assert visible_length(l) == card_w
