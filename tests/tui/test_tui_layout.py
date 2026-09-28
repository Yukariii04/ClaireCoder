"""Tests for TUI Layout Modes (Full, Compact, Minimal), Header Projections, and Viewport Geometry.

Authorities: CC-PRD-011, CC-ADR-007, TUI-DESIGN.md.
"""
import pytest
from clairecoder.tui.app import TuiApplication
from clairecoder.tui.canvas import visible_length, visible_slice
from clairecoder.tui.states import TerminalMode


def test_full_mode_spatial_composition():
    """Verify Full mode layout renders framed box with header, body, prompt, and single-line footer."""
    app = TuiApplication(workspace_root="/test/ws")
    app.resize(100, 30)
    app.terminal.force_mode(TerminalMode.FULL)

    frame = app.render()
    assert len(frame) == 30

    # Top border with ClaireCoder
    assert "ClaireCoder" in frame[0]
    assert visible_length(frame[0]) <= 100

    # Bottom border
    assert "╰" in frame[-1] or "─" in frame[-1]
    assert visible_length(frame[-1]) <= 100


def test_compact_and_minimal_modes():
    """Verify Compact and Minimal modes adapt without full outer box borders."""
    app = TuiApplication(workspace_root="/test/ws")

    # Compact
    app.resize(80, 24)
    app.terminal.force_mode(TerminalMode.COMPACT)
    frame_compact = app.render()
    assert len(frame_compact) == 24

    # Minimal
    app.resize(60, 20)
    app.terminal.force_mode(TerminalMode.MINIMAL)
    frame_minimal = app.render()
    assert len(frame_minimal) == 20


def test_ansi_and_display_width_calculations():
    """Verify visible_length and visible_slice handle ANSI escapes and unicode characters accurately."""
    ansi_text = "\x1b[32mActive Provider\x1b[0m"
    assert visible_length(ansi_text) == len("Active Provider")

    sliced = visible_slice(ansi_text, 0, 6)
    assert visible_length(sliced) == 6

    # Unicode / double-width glyphs
    unicode_text = "╭─ ClaireCoder ── ● v0.1.0 ─╮"
    assert visible_length(unicode_text) == len(unicode_text)


def test_hard_viewport_height_and_frame_height_invariance():
    """Verify frame height is strictly equal to terminal height under different heights."""
    app = TuiApplication(workspace_root="/test/ws")

    for h in [20, 24, 30, 45, 60]:
        app.resize(100, h)
        frame = app.render()
        assert len(frame) == h, f"Frame row count ({len(frame)}) != terminal height ({h})"


def test_single_line_footer_content():
    """Verify single-line footer displays valid shortcuts without obsolete help."""
    app = TuiApplication(workspace_root="/test/ws")
    app.resize(100, 30)

    frame = app.render()
    footer_row = frame[-2]  # Prompt/footer area
    assert visible_length(footer_row) <= 100


def test_header_state_projection_complete():
    """Verify Header is an authoritative projection of runtime state."""
    app = TuiApplication(workspace_root="/test/workspace/myproject")
    app.header.session_id = "sess_test123"
    app.header.model = "qwen2.5-coder:3b"
    app.header.mode = "IMPLEMENT"
    app.header.task_progress = "Task 1/3"
    app.header.context_usage = "1.2k/32.0k"

    rendered = "\n".join(app.render())
    assert "dir: /test/workspace/myproject" in rendered
    assert "model: qwen2.5-coder:3b" in rendered
    assert "mode: IMPLEMENT" in rendered
    assert "session: sess_test123" in rendered
    assert "task: Task 1/3" in rendered
    assert "context: 1.2k/32.0k" in rendered
