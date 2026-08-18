"""Tests for the TUI transcript and activity rendering."""
import pytest
from clairecoder.tui.activity import ActivityModel, ActivityState, ActivityType, DiffInfo, DiffLine
from clairecoder.tui.renderer import ActivityRenderer
from clairecoder.tui.transcript import TranscriptView

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
    assert lines[0].startswith(">")
    
    act.state = ActivityState.COMPLETED
    lines = ActivityRenderer.render(act)
    assert "✓" in lines[0] or "●" in lines[0]
    assert lines[0].startswith(">")
    
    act.state = ActivityState.FAILED
    lines = ActivityRenderer.render(act)
    assert "✗" in lines[0]
    assert lines[0].startswith(">")
    
    act.state = ActivityState.APPROVAL_REQUIRED
    lines = ActivityRenderer.render(act)
    assert "⚠" in lines[0]
    assert lines[0].startswith(">")

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
    # Should not show lines 1-3 when collapsed
    assert len(lines) == 1
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
    # Collapsed
    lines = ActivityRenderer.render(act)
    assert len(lines) == 1
    
    # Expanded
    act.expanded = True
    lines = ActivityRenderer.render(act)
    assert len(lines) == 3
    assert lines[1] == "  - print('hello')"
    assert lines[2] == "  + print('world')"

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
    assert view.scroll_position == 5 # 10 lines total - 5 visible
