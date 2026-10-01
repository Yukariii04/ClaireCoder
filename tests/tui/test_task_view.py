"""Tests for TaskViewOverlay multiline word wrapping, fixed geometry, and vertical scrolling."""
import pytest
from clairecoder.tui.task import TaskViewOverlay, WorkflowTaskItem
from clairecoder.tui.canvas import visible_length


def test_task_view_empty_state():
    tv = TaskViewOverlay()
    rendered = tv.render(width=58)
    assert len(rendered) == 16  # Fixed height
    assert "No active workflow tasks." in "".join(rendered)
    assert "Objective: None" in "".join(rendered)


def test_task_view_multiline_objective_wrapping():
    tv = TaskViewOverlay(
        tasks=[WorkflowTaskItem(1, "Parse input", "✓"), WorkflowTaskItem(2, "Generate code", "▶")],
        progress_pct=50,
        objective="This is a very long objective description that should be wrapped cleanly across multiple rows and never hard-truncated.",
        status="Active",
    )
    rendered = tv.render(width=58)
    assert len(rendered) == 16  # Fixed height guaranteed
    full_text = "\n".join(rendered)
    assert "Objective:" in full_text
    assert "Parse input" in full_text
    assert "50%" in full_text
    # Check that each line stays within width
    for line in rendered:
        assert visible_length(line) <= 58


def test_task_view_vertical_scrolling():
    tv = TaskViewOverlay(
        tasks=[WorkflowTaskItem(i, f"Subtask number {i} doing work", "○") for i in range(1, 15)],
        progress_pct=20,
        objective="Long multi-stage workflow objective",
        status="Active",
    )
    rendered_initial = tv.render(width=58)
    assert len(rendered_initial) == 16
    assert "↑/↓ scroll" in rendered_initial[-2]  # Footer hint visible

    # Scroll down
    tv.handle_key("down")
    assert tv.viewport_offset == 1

    # Page down
    tv.handle_key("pagedown")
    assert tv.viewport_offset > 1

    # Home
    tv.handle_key("home")
    assert tv.viewport_offset == 0


def test_task_view_reset():
    tv = TaskViewOverlay(
        tasks=[WorkflowTaskItem(1, "Task 1", "✓")],
        progress_pct=100,
        objective="Finished task",
        status="Complete",
    )
    assert tv.objective == "Finished task"

    tv.reset()
    assert tv.objective == ""
    assert tv.tasks == []
    assert tv.progress_pct == 0
    assert tv.status == "Idle"
