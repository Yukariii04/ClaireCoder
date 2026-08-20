"""Comprehensive tests for Fixed Main Transcript Viewport, Internal Scrolling, and Stable Frame Height.

AUTHORITY:
  CC-PRD-011 FINAL
  CC-ADR-007 FINAL
  TUI-DESIGN.md FINAL
  CLI-TUI-DESKTOP-ROADMAP.md FINAL
"""
import io
import pytest
from unittest.mock import Mock

from clairecoder.tui.app import TuiApplication
from clairecoder.tui.activity import ActivityModel, ActivityState, ActivityType, DiffInfo, DiffLine
from clairecoder.tui.states import InputState, TerminalMode
from clairecoder.tui.terminal import TerminalCapability, TerminalRenderer, TerminalInput
from clairecoder.tui.preview import create_preview_app


class TestViewportHeightAndPadding:
    """Verifies that transcript viewport has configured height, pads short content, and clips long content."""

    def test_transcript_viewport_configured_height(self):
        """TranscriptView resize sets exact height and calculates visible lines within boundary."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        assert app.get_viewport_height() == 22
        assert app.transcript.height == 22

    def test_short_transcript_padded_to_viewport_height(self):
        """Short transcript (fewer rows than viewport) is padded so body takes exactly viewport_height."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        # Add 1 short activity
        app.transcript.append_activity(ActivityModel(title="Initial start"))
        visible = app.transcript.get_visible_lines(padded=True)
        assert len(visible) == 22
        
        # Frame render
        frame = app.render()
        assert len(frame) == 30

    def test_long_transcript_clipped_to_viewport_height(self):
        """Long transcript (more rows than viewport) only emits visible slice of exact viewport_height."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        for i in range(100):
            app.transcript.append_activity(ActivityModel(title=f"Activity item #{i}"))
        
        visible = app.transcript.get_visible_lines()
        assert len(visible) == 22
        assert visible[-1].endswith("Activity item #99") or "99" in visible[-1]
        
        frame = app.render()
        assert len(frame) == 30


class TestOuterFrameInvariants:
    """Verifies that outer frame height, prompt position, and footer position NEVER change as history grows."""

    def test_outer_frame_height_invariant_under_transcript_growth(self):
        """Outer frame height remains invariant when adding 1, 10, 100, 1000 messages."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        
        frame_0 = app.render()
        height_0 = len(frame_0)
        assert height_0 == 30

        # Add 1 activity
        app.transcript.append_activity(ActivityModel(title="First message"))
        frame_1 = app.render()
        assert len(frame_1) == height_0

        # Add 50 activities
        for i in range(50):
            app.transcript.append_activity(ActivityModel(title=f"Message {i}"))
        frame_50 = app.render()
        assert len(frame_50) == height_0

        # Add 500 activities
        for i in range(500):
            app.transcript.append_activity(ActivityModel(title=f"Bulk message {i}"))
        frame_500 = app.render()
        assert len(frame_500) == height_0

    def test_prompt_and_footer_fixed_anchoring(self):
        """Prompt and footer rows remain at the exact same row indices regardless of transcript content."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        
        frame_before = app.render()
        prompt_idx_before = next(i for i, line in enumerate(frame_before) if line.startswith("│ >"))
        footer_idx_before = next(i for i, line in enumerate(frame_before) if "ctrl+c interrupt" in line)

        # Add 100 activities
        for i in range(100):
            app.transcript.append_activity(ActivityModel(title=f"Event {i}", detail=f"Details for event {i}"))

        frame_after = app.render()
        prompt_idx_after = next(i for i, line in enumerate(frame_after) if line.startswith("│ >"))
        footer_idx_after = next(i for i, line in enumerate(frame_after) if "ctrl+c interrupt" in line)

        assert prompt_idx_before == prompt_idx_after == 27
        assert footer_idx_before == footer_idx_after == 28
        assert len(frame_before) == len(frame_after) == 30


class TestTranscriptInternalScrolling:
    """Verifies scrolling mechanisms: up, down, page up, page down, home, end, and follow-tail behavior."""

    def test_scroll_up_exposes_older_messages(self):
        """Scrolling up reveals older transcript activities and changes visible slice."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        for i in range(40):
            app.transcript.append_activity(ActivityModel(title=f"Line {i:02d}"))

        # At bottom initially
        bottom_frame = "\n".join(app.render())
        assert "Line 39" in bottom_frame
        assert "Line 00" not in bottom_frame

        # Scroll up
        app.handle_key("pageup")
        scrolled_frame = "\n".join(app.render())
        assert "Line 39" not in scrolled_frame
        assert "Line 00" in scrolled_frame or "Line 10" in scrolled_frame

    def test_scroll_down_exposes_newer_messages(self):
        """Scrolling down after scrolling up reveals newer activities."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        for i in range(40):
            app.transcript.append_activity(ActivityModel(title=f"Line {i:02d}"))

        app.handle_key("pageup")
        # Scroll down
        app.handle_key("pagedown")
        scrolled_frame = "\n".join(app.render())
        assert "Line 39" in scrolled_frame

    def test_follow_tail_behavior_on_new_activity(self):
        """New activities auto-scroll when at bottom, but preserve position if user scrolled up."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        for i in range(30):
            app.transcript.append_activity(ActivityModel(title=f"Item {i}"))

        # At bottom
        assert "Item 29" in "\n".join(app.render())

        # Scroll up to inspect older history
        app.handle_key("home")
        top_view = "\n".join(app.render())
        assert "Item 0" in top_view
        assert "Item 29" not in top_view

        # Add new activity while scrolled up
        app.transcript.append_activity(ActivityModel(title="New Arrival while scrolled"))
        still_top_view = "\n".join(app.render())
        assert "Item 0" in still_top_view
        assert "New Arrival while scrolled" not in still_top_view

        # Scroll to bottom restores follow-tail
        app.handle_key("end")
        bottom_view = "\n".join(app.render())
        assert "New Arrival while scrolled" in bottom_view

    def test_scroll_does_not_mutate_frame_geometry(self):
        """Scrolling does not change outer frame height or move header/prompt/footer."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        for i in range(50):
            app.transcript.append_activity(ActivityModel(title=f"Activity {i}"))

        for key in ("up", "down", "pageup", "pagedown", "home", "end"):
            app.handle_key(key)
            frame = app.render()
            assert len(frame) == 30
            assert "╭─ ClaireCoder" in frame[0]
            assert frame[27].startswith("│ >")
            assert "ctrl+c interrupt" in frame[28]
            assert "╰" in frame[29]


class TestTerminalResizeBehavior:
    """Verifies that terminal resize recomputes viewport height and reflows without frame duplication."""

    def test_resize_updates_viewport_height(self):
        """Resizing terminal height dynamically changes viewport height and frame size."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        assert app.get_viewport_height() == 22

        app.resize(104, 40)
        assert app.get_viewport_height() == 32
        assert app.transcript.height == 32
        assert len(app.render()) == 40

        app.resize(104, 20)
        assert app.get_viewport_height() == 12
        assert app.transcript.height == 12
        assert len(app.render()) == 20

    def test_resize_in_compact_and_minimal_modes(self):
        """Resize correctly calculates viewport in COMPACT and MINIMAL modes."""
        app = TuiApplication(terminal=TerminalCapability(width=80, height=24))
        assert app.terminal.determine_mode() == TerminalMode.COMPACT
        frame = app.render()
        assert len(frame) == 24

        app.resize(60, 20)
        assert app.terminal.determine_mode() == TerminalMode.MINIMAL
        frame_min = app.render()
        assert len(frame_min) == 20


class TestLongContentAndDiffsInsideViewport:
    """Verifies that long diffs, long wrapped activity, and long responses stay bounded."""

    def test_long_wrapped_activity_stays_inside_viewport(self):
        """Activity with many lines stays clipped to viewport without expanding outer frame."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        long_detail = "\n".join([f"Trace line {i}: function call payload data" for i in range(100)])
        app.transcript.append_activity(ActivityModel(title="Huge Output", detail=long_detail))

        frame = app.render()
        assert len(frame) == 30

    def test_long_expanded_diff_stays_inside_viewport(self):
        """Large multi-line diff does not expand outer frame."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        diff_lines = [DiffLine(type="add", content=f"def added_function_{i}(): pass") for i in range(80)]
        diff = DiffInfo(summary="+80 -0", lines=diff_lines)
        act = ActivityModel(
            type=ActivityType.EDITING,
            state=ActivityState.COMPLETED,
            title="Editing massive_file.py",
            diff_info=diff,
            expanded=True
        )
        app.transcript.append_activity(act)

        frame = app.render()
        assert len(frame) == 30

    def test_long_assistant_response_stays_inside_viewport(self):
        """Long Claire textual response stays inside fixed viewport."""
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30))
        long_claire = "\n".join([f"Paragraph {i}: Detailed explanation of the architectural subsystem." for i in range(50)])
        app.transcript.append_activity(ActivityModel(
            type=ActivityType.MESSAGE,
            state=ActivityState.COMPLETED,
            title="Claire",
            detail=long_claire
        ))

        frame = app.render()
        assert len(frame) == 30


class TestOverlayAndPermissionTransitions:
    """Verifies that opening and closing overlays preserves outer frame geometry."""

    def test_overlays_preserve_frame_geometry(self):
        """FileTree, Review, Task, CommandPalette, and Permission render with identical frame height."""
        app = create_preview_app(mode=TerminalMode.FULL)
        base_height = len(app.render())
        assert base_height == 30

        # Review overlay
        app.open_review()
        assert len(app.render()) == base_height
        app.close_overlay()
        assert len(app.render()) == base_height

        # Command palette
        app.open_palette()
        assert len(app.render()) == base_height
        app.close_overlay()
        assert len(app.render()) == base_height

        # File tree
        app.open_tree()
        assert len(app.render()) == base_height
        app.close_overlay()
        assert len(app.render()) == base_height

        # Task view
        app.open_task()
        assert len(app.render()) == base_height
        app.close_overlay()
        assert len(app.render()) == base_height

        # Permission confirmation
        app.permission_surface.request_confirmation(
            request_id="req_test_1",
            tool_id="rm",
            action="delete",
            resource="temp.txt"
        )
        app.set_state(InputState.CONFIRMATION)
        assert len(app.render()) == base_height


class TestRedrawIntegration:
    """Verifies that in-place redraw updates the same frame region without appending frames."""

    def test_in_place_redraw_maintains_line_count(self):
        """TerminalRenderer redraw updates frame without growing last_line_count."""
        stream = io.StringIO()
        renderer = TerminalRenderer(stream=stream, enable_ansi=True)
        app = TuiApplication(terminal=TerminalCapability(width=104, height=30), renderer=renderer)

        app.render_initial_frame()
        assert renderer.last_line_count == 30

        # Add multiple activities and redraw
        for i in range(20):
            app.transcript.append_activity(ActivityModel(title=f"Step {i}"))
            app.redraw()
            assert renderer.last_line_count == 30

        output = stream.getvalue()
        # Ensure ANSI reposition sequence moves from bottom row to top row (30 - 1 = 29 lines up)
        assert "\x1b[29A\r" in output
