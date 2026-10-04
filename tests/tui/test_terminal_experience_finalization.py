"""Comprehensive tests for Stage 5 — Terminal Experience Finalization (CC-PRD-011, CC-ADR-007, TUI-DESIGN.md)."""
import os
import pytest
from unittest.mock import Mock, patch

from clairecoder.tui.app import TuiApplication
from clairecoder.tui.states import InputState, TerminalMode
from clairecoder.tui.terminal import TerminalCapability
from clairecoder.tui.loading import LoadingScreen
from clairecoder.tui.prompt import PromptInput
from clairecoder.tui.activity import ActivityModel, ActivityState, ActivityType, DiffInfo, DiffLine
from clairecoder.tui.renderer import ActivityRenderer
from clairecoder.tui.permission import PermissionSurface, PermissionDecision
from clairecoder.tui.review import ReviewOverlay
from clairecoder.tui.palette import CommandPalette
from clairecoder.tui.tree import FileTreeOverlay
from clairecoder.tui.task import TaskViewOverlay
from clairecoder.tui.preview import create_preview_app, render_preview
from clairecoder.core.events import Event


class TestMascotRemovalAndTextPersona:
    """Verifies that graphical mascot rendering is removed and Claire exists purely as a text persona."""

    def test_no_mascot_attribute_in_tui_application(self):
        """TuiApplication must not maintain mascot presentation state or attributes."""
        app = TuiApplication()
        assert not hasattr(app, "mascot")
        assert not hasattr(app, "mascot_presentation")
        assert not hasattr(app, "image_renderer")

    def test_claire_text_persona_rendering(self):
        """Claire message rendered as textual persona with indentation and no sprite artwork."""
        act = ActivityModel(
            type=ActivityType.MESSAGE,
            state=ActivityState.COMPLETED,
            title="Claire",
            detail="Streaming decode support added with a safe fallback.\nAll tests are passing."
        )
        lines = ActivityRenderer.render(act, width=68)
        rendered_str = "\n".join(lines)

        assert "Claire:" in rendered_str
        assert "  Streaming decode support added with a safe fallback." in rendered_str
        assert "  All tests are passing." in rendered_str
        # Verify no mascot state or unicode art
        assert "[Claire IDLE]" not in rendered_str
        assert "[Claire WORKING]" not in rendered_str
        assert "▄██" not in rendered_str

    def test_boot_loading_screen_wordmark_branding(self):
        """Boot screen presents CLAIRECODER wordmark branding without graphical hero artwork."""
        lines = LoadingScreen.render(width=56, height=38, use_color=False)
        rendered_str = "\n".join(lines)

        assert "CLAIRECODER" in rendered_str
        assert "Engineering. Automated." in rendered_str
        assert "Initializing ClaireCoder Engine..." in rendered_str
        assert "> Loading configuration" in rendered_str
        assert "> Connecting model gateway" in rendered_str
        assert "> Registering tools" in rendered_str
        assert "> Preparing workspace" in rendered_str
        assert "> Loading skills" in rendered_str
        assert "> Starting session" in rendered_str
        assert "Launching..." in rendered_str
        assert "100%" in rendered_str
        assert '"Let\'s build something amazing together."' in rendered_str
        assert "- Claire" in rendered_str

        # Must not contain chibi sprite characters
        assert "▄████▄" not in rendered_str
        assert "▀████▀" not in rendered_str

    def test_main_render_has_no_mascot_column(self):
        """Full TUI main render uses full-width transcript without right-side mascot split."""
        app = create_preview_app(mode=TerminalMode.FULL)
        lines = app.render()
        full_text = "\n".join(lines)

        assert "Claire:" in full_text
        assert "[Claire IDLE]" not in full_text
        assert "[Claire WORKING]" not in full_text
        assert "[Claire THINKING]" not in full_text
        assert "mascot" not in full_text.lower()


class TestPromptTreatmentAndSizing:
    """Verifies glass/cursor styling and terminal size adaptation across modes."""

    def test_prompt_rendering_with_cursor(self):
        """Prompt renders with cyan accent prefix and visible cursor block."""
        prompt = PromptInput()
        prompt.set_text("refactor decoder")

        rendered = prompt.render(mode=TerminalMode.FULL, width=80)
        assert len(rendered) == 1
        assert rendered[0] == "> refactor decoder█"

        # When suspended (e.g. during overlay), cursor is hidden
        prompt.suspend()
        rendered_suspended = prompt.render(mode=TerminalMode.FULL, width=80)
        assert rendered_suspended[0] == "> refactor decoder"

    def test_terminal_adaptation_thresholds(self):
        """Verifies adaptive thresholds (Full >= 96, Compact 76-95, Minimal < 76)."""
        term = TerminalCapability()

        # 1. 96+ columns -> FULL
        for w in (96, 100, 120, 160):
            term.resize(w, 30)
            assert term.determine_mode() == TerminalMode.FULL

        # 2. 76-95 columns -> COMPACT
        for w in (76, 80, 85, 95):
            term.resize(w, 24)
            assert term.determine_mode() == TerminalMode.COMPACT

        # 3. < 76 columns -> MINIMAL
        for w in (20, 50, 70, 75):
            term.resize(w, 20)
            assert term.determine_mode() == TerminalMode.MINIMAL

    def test_full_tui_mode_features(self):
        """Full TUI mode renders framed layout with header, transcript, prompt, footer."""
        app = create_preview_app(mode=TerminalMode.FULL)
        app.resize(100, 30)
        lines = app.render()
        full_text = "\n".join(lines)

        assert "╭─ ClaireCoder" in lines[0]
        assert "dir: ~/projects/claire-speech-engine" in full_text
        assert "✓ Reading src/decoder.py" in full_text
        assert "> add support for interrupting mid-stream█" in full_text
        assert "ctrl+c interrupt" in full_text
        assert "╰" in lines[-1]

    def test_compact_tui_mode_features(self):
        """Compact TUI mode renders header, full transcript, and prompt without frame chrome."""
        app = create_preview_app(mode=TerminalMode.COMPACT)
        app.resize(80, 40)  # Taller to accommodate inter-activity spacing
        lines = app.render()
        full_text = "\n".join(lines)

        assert "dir: ~/projects/claire-speech-engine" in full_text
        assert "Reading src/decoder.py" in full_text
        assert "> add support for interrupting mid-stream" in full_text

    def test_minimal_tui_mode_features(self):
        """Minimal TUI mode renders compact status, transcript, and prompt."""
        app = create_preview_app(mode=TerminalMode.MINIMAL)
        app.resize(60, 20)
        lines = app.render()
        full_text = "\n".join(lines)

        assert "--- ClaireCoder (v0.1.0) [IMPLEMENT] ---" in lines[0]
        assert "> add support for interrupting mid-stream" in full_text


class TestEscAndKeyboardSemantics:
    """Verifies keyboard shortcuts, Esc semantics, and Ctrl+C interruption."""

    def test_esc_closes_overlays_without_side_effects(self):
        """Esc closes all overlays (Review, Palette, Tree, Task) at UI level."""
        app = TuiApplication()
        mock_interrupt = Mock()
        app.on_interrupt = mock_interrupt

        for open_method, overlay_name in [
            (app.open_review, "review"),
            (app.open_palette, "palette"),
            (app.open_tree, "tree"),
            (app.open_task, "task"),
        ]:
            open_method()
            assert app.state == InputState.OVERLAY
            assert app.active_overlay == overlay_name
            assert app.prompt.suspended

            # Press Esc
            app.handle_key("Esc")
            assert app.state == InputState.NORMAL
            assert app.active_overlay is None
            assert not app.prompt.suspended
            mock_interrupt.assert_not_called()

    def test_ctrl_c_invokes_interruption_handler(self):
        """Ctrl+C invokes interruption handler and clears prompt."""
        app = TuiApplication()
        interrupted = [False]

        def on_interrupt():
            interrupted[0] = True

        app.on_interrupt = on_interrupt
        app.prompt.set_text("some text")

        app.handle_key("ctrl+c")
        assert interrupted[0]
        assert app.prompt.get_text() == ""


class TestArchitectureBoundaries:
    """Verifies that TUI adheres strictly to public interaction boundaries."""

    def test_tui_does_not_execute_tools(self):
        """TUI has no Tool execution methods or direct tool references."""
        app = TuiApplication()
        assert not hasattr(app, "execute_tool")
        assert not hasattr(app, "invoke_tool")
        assert not hasattr(app, "tool_executor")

    def test_tui_does_not_make_permission_decisions(self):
        """TUI delegates permission decisions to InteractionController / callback."""
        app = TuiApplication()
        mock_controller = Mock()
        app.connect_controller(mock_controller)

        app.handle_event(Event("PERMISSION_REQUESTED", {
            "request_id": "req_arch_1",
            "tool_id": "rm",
            "action": "delete",
            "resource": "test.txt",
            "session_id": "sess_arch"
        }))
        assert app.state == InputState.CONFIRMATION

        # User presses 'y'
        app.handle_key("y")
        assert app.state == InputState.NORMAL
        mock_controller.handle_permission_response.assert_called_once_with(
            request_id="req_arch_1",
            decision=PermissionDecision.APPROVE,
            session_id="sess_arch",
            tool_id="rm",
            action="delete",
            resource="test.txt",
            command=None,
            category=None
        )
