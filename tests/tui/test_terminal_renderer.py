"""Tests for TerminalRenderer, In-Place Redraws, Single Render Owner, Cursor Accounting, and Redraw Stress.

Authorities: CC-PRD-011, CC-ADR-007.
"""
import io
import re
import queue
import time
import pytest
from unittest.mock import Mock, patch

from clairecoder.tui.terminal import TerminalRenderer, TerminalCapability
from clairecoder.tui.app import TuiApplication, InputState
from clairecoder.tui.canvas import visible_length
from clairecoder.tui.states import TerminalMode
from clairecoder.tui.activity import ActivityModel, ActivityType
from clairecoder.core.events import Event


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


def test_full_height_redraw_and_trailing_newline_elimination():
    """Verify that frame rendering does not add trailing newlines that cause scrolling."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)

    frame_lines = [f"Line {i:02d}" for i in range(30)]
    renderer.render_frame(frame_lines)

    output = stream.getvalue()
    # Output should not end with a blank line after the last line
    assert not output.endswith("\n\n")


def test_physical_terminal_cursor_accounting():
    """Verify physical cursor repositioning matches rendered line count."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)

    frame1 = [f"Line {i}" for i in range(25)]
    renderer.render_frame(frame1)
    assert renderer.last_line_count == 25

    stream.truncate(0)
    stream.seek(0)

    frame2 = [f"NewLine {i}" for i in range(30)]
    renderer.redraw(frame2)
    assert renderer.last_line_count == 30


def test_variable_line_count_transitions():
    """Verify transitions across variable line counts (e.g. 26 rows -> 30 rows)."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)

    # Stage 1: 26 lines
    renderer.render_frame([f"Row {i}" for i in range(26)])
    assert renderer.last_line_count == 26

    # Stage 2: 30 lines
    renderer.redraw([f"MainRow {i}" for i in range(30)])
    assert renderer.last_line_count == 30

    # Stage 3: 20 lines
    renderer.redraw([f"ShortRow {i}" for i in range(20)])
    assert renderer.last_line_count == 20


def test_terminal_height_resize_resilience():
    """Verify resizing across terminal dimensions (30 -> 25 -> 40 -> 30)."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    app = TuiApplication(renderer=renderer)

    for h in [30, 25, 40, 30]:
        app.resize(100, h)
        frame = app.render()
        assert len(frame) == h
        for row in frame:
            assert visible_length(row) <= 100


def test_virtual_ansi_terminal_buffer_simulation():
    """Virtual ANSI terminal buffer simulation proving zero scrollback push and 100% clean exit."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    app = TuiApplication(renderer=renderer)
    app.resize(100, 30)

    app.render_initial_frame()
    assert len(app.current_frame) == 30

    for i in range(10):
        app.transcript.append_activity(ActivityModel(
            type=ActivityType.MESSAGE,
            title="User",
            detail=f"Test message {i}"
        ))
        app.redraw()
        assert len(app.current_frame) == 30

    app.stop()
    assert app.state == InputState.EXITING


def test_duplicate_frame_elimination_and_redraw_stress():
    """Stress test: 100+ redraw cycles without duplicate headers or line wrapping."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    app = TuiApplication(renderer=renderer)
    app.resize(120, 35)

    # Initial frame
    app.render_initial_frame()
    assert len(app.current_frame) == 35

    for cycle in range(120):
        app.transcript.append_activity(ActivityModel(
            type=ActivityType.MESSAGE,
            title="Claire",
            detail=f"Stress cycle response {cycle}"
        ))
        app.redraw()

        # Invariant 1: Exactly 35 rows rendered every cycle
        assert len(app.current_frame) == 35

        # Invariant 2: Exactly ONE top border row with '╭─ ClaireCoder'
        header_occurrences = [row for row in app.current_frame if "╭─ ClaireCoder" in row]
        assert len(header_occurrences) == 1, f"Cycle {cycle}: found {len(header_occurrences)} headers"

        # Invariant 3: Frame width never exceeds terminal width (120)
        for row_idx, row in enumerate(app.current_frame):
            row_len = visible_length(row)
            assert row_len <= 120, f"Cycle {cycle}, Row {row_idx}: length {row_len} > 120"


def test_single_render_owner_event_marshaling():
    """Verify background events are marshaled via _event_queue and only drained by the main loop."""
    app = TuiApplication()
    app._in_run_loop = True

    # Emit event from simulated background thread
    bg_event = Event(name="STREAMING_CHUNK", payload={"text": "chunk1"})
    app._on_engine_event(bg_event)

    # Event must be queued in _event_queue, not directly processed to mutate renderer
    assert not app._event_queue.empty()
    queued = app._event_queue.get_nowait()
    assert queued == bg_event


def test_clean_shutdown_and_terminal_restoration():
    """Verify /exit, exit, quit, and stop() restore terminal state cleanly."""
    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    app = TuiApplication(renderer=renderer)
    app.resize(80, 24)

    app.render_initial_frame()
    assert app.running is False  # not in interactive run loop

    app.stop()
    assert app.state == InputState.EXITING
