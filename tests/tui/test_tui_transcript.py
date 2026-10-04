"""Tests for TUI TranscriptView, Activity Rendering, Scrolling, and Clipping Invariants.

Authorities: CC-PRD-011, CC-ADR-007, TUI-DESIGN.md.
"""
import pytest
from clairecoder.tui.activity import ActivityModel, ActivityState, ActivityType, DiffInfo, DiffLine
from clairecoder.tui.renderer import ActivityRenderer
from clairecoder.tui.transcript import TranscriptView
from clairecoder.tui.app import TuiApplication


def test_activity_model_creation():
    act = ActivityModel(
        title="Running pytest",
        type=ActivityType.TOOL,
        state=ActivityState.RUNNING
    )
    assert act.title == "Running pytest"
    assert act.state == ActivityState.RUNNING


def test_activity_status_transitions():
    act = ActivityModel(title="pytest", type=ActivityType.TOOL, state=ActivityState.RUNNING)
    lines = ActivityRenderer.render(act)
    assert "◌" in lines[0] or "●" in lines[0]
    
    act.state = ActivityState.COMPLETED
    lines = ActivityRenderer.render(act)
    assert "✓" in lines[0] or "●" in lines[0]
    
    act.state = ActivityState.FAILED
    lines = ActivityRenderer.render(act)
    assert "✗" in lines[0]
    
    act.state = ActivityState.APPROVAL_REQUIRED
    lines = ActivityRenderer.render(act)
    assert "⚠" in lines[0]


def test_transcript_append_and_update():
    view = TranscriptView()
    act = ActivityModel(title="Downloading", state=ActivityState.RUNNING)
    view.append_activity(act)
    assert view.activities[0].title == "Downloading"
    
    act.title = "Downloading 50%"
    view.update_activity(act)
    assert view.activities[0].title == "Downloading 50%"


def test_transcript_completion_and_failure():
    view = TranscriptView()
    act1 = ActivityModel(title="Task 1", state=ActivityState.RUNNING)
    act2 = ActivityModel(title="Task 2", state=ActivityState.RUNNING)
    view.append_activity(act1)
    view.append_activity(act2)
    
    view.complete_activity(act1.id, detail="Success")
    view.fail_activity(act2.id, detail="Error")
    
    assert view._activity_map[act1.id].state == ActivityState.COMPLETED
    assert view._activity_map[act1.id].detail == "Success"
    
    assert view._activity_map[act2.id].state == ActivityState.FAILED
    assert view._activity_map[act2.id].detail == "Error"


def test_expansion_and_long_output():
    act = ActivityModel(
        title="Summary",
        expandable_content="Line 1\nLine 2\nLine 3"
    )
    lines = ActivityRenderer.render(act)
    # Title + hidden output hint
    assert "Output hidden" in "\n".join(lines)
    assert "Line 1" not in "\n".join(lines)
    
    act.expanded = True
    lines = ActivityRenderer.render(act)
    assert len(lines) == 4
    assert "Line 1" in "\n".join(lines)


def test_diff_rendering():
    act = ActivityModel(
        title="src/main.py",
        diff_info=DiffInfo(
            summary="+1 -1",
            lines=[
                DiffLine("remove", "print('hello')"),
                DiffLine("add", "print('world')")
            ]
        )
    )
    lines = ActivityRenderer.render(act)
    assert len(lines) == 1
    
    act.expanded = True
    lines = ActivityRenderer.render(act)
    # Title + box_top + 2 diff lines + box_bot = 5 lines (bordered diff)
    assert len(lines) == 5
    rendered = "\n".join(lines)
    assert "┌" in rendered
    assert "└" in rendered
    assert "print('hello')" in rendered
    assert "print('world')" in rendered


def test_event_ordering():
    view = TranscriptView()
    act1 = ActivityModel(title="1")
    act2 = ActivityModel(title="2")
    view.append_activity(act1)
    view.append_activity(act2)
    
    assert view.activities[0].order_index == 0
    assert view.activities[1].order_index == 1


def test_terminal_resize_behavior():
    view = TranscriptView()
    for i in range(10):
        view.append_activity(ActivityModel(title=f"Line {i}"))
        
    view.resize(5)
    assert view.scroll_position == 5


def test_transcript_hard_clipping_and_frame_height_invariance():
    """Verify adding 100+ items does not expand frame height beyond terminal bounds."""
    app = TuiApplication()
    app.resize(100, 30)

    for i in range(150):
        app.transcript.append_activity(ActivityModel(
            type=ActivityType.MESSAGE,
            title="User",
            detail=f"Line {i}"
        ))

    frame = app.render()
    assert len(frame) == 30


def test_transcript_interactive_scrolling():
    """Test PageUp, PageDown, Home, End navigation in transcript."""
    app = TuiApplication()
    app.resize(100, 30)

    for i in range(100):
        app.transcript.append_activity(ActivityModel(
            title=f"Event {i}",
            detail=f"Detail {i}"
        ))

    # Home scrolls to top
    app.handle_key("home")
    assert app.transcript.scroll_position == 0

    # PageDown scrolls down by viewport height
    app.handle_key("pagedown")
    assert app.transcript.scroll_position > 0

    # End scrolls to bottom (follow tail)
    app.handle_key("end")
    assert app.transcript.is_at_bottom() is True


def test_scrollbar_indicator_full_mode():
    """Verify scrollbar indicator appears when transcript overflows viewport in Full mode."""
    app = TuiApplication()
    app.resize(100, 25)

    for i in range(50):
        app.transcript.append_activity(ActivityModel(
            title=f"Activity {i}"
        ))

    frame = app.render()
    rendered_text = "\n".join(frame)
    assert "░" in rendered_text or "▓" in rendered_text
