"""Focused tests for the TUI Activity Stream System (Correction #20).

Validates:
1. Activity mapping (all operations: reading, editing, creating, deleting, running, verifying, planning)
2. Running -> Completed lifecycle
3. Failed lifecycle & error presentation (concise error, no tracebacks)
4. ToolResult -> ActivityEvent mapping
5. Missing optional metadata / null safety
6. Long-path rendering and truncation
7. Change summary aggregation from ChangeSet
8. Additions / deletions display
9. Event ordering
10. No duplicate visible entries for same lifecycle event (in-place correlation update)
11. Verification success and failure rendering
"""

import pytest
from clairecoder.core.types import ToolResult
from clairecoder.changeset.types import ChangeSet, ChangedFile, FileOperation
from clairecoder.runtime.events import EventType, RuntimeEvent
from clairecoder.tui.activity import (
    ActivityEvent,
    ActivityModel,
    ActivityOperation,
    ActivityStatus,
    ChangeSummaryItem,
    ExecutionChangeSummary,
    truncate_path,
)
from clairecoder.tui.activity_mapper import (
    ActivityMapper,
    extract_command_summary,
    format_concise_error,
)
from clairecoder.tui.renderer import ActivityRenderer
from clairecoder.tui.transcript import TranscriptView


# =============================================================================
# 1. Activity Mapping
# =============================================================================

class TestActivityMapping:
    """Verify semantic mapping from RuntimeEvents to ActivityEvents."""

    def test_map_read_file(self):
        ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "read_file", "arguments": {"path": "src/foo.py"}},
            tool_call_id="call_read_1",
        )
        act = ActivityMapper.from_runtime_event(ev)
        assert act is not None
        assert act.status == ActivityStatus.RUNNING
        assert act.operation == ActivityOperation.READING
        assert act.target == "src/foo.py"
        assert act.file_path == "src/foo.py"
        lines = act.render_lines()
        assert lines == ["● Reading src/foo.py"]

    def test_map_write_file_edit(self):
        ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "write_file", "arguments": {"path": "src/foo.py", "is_new": False}},
            tool_call_id="call_write_1",
        )
        act = ActivityMapper.from_runtime_event(ev)
        assert act is not None
        assert act.status == ActivityStatus.RUNNING
        assert act.operation == ActivityOperation.EDITING
        assert act.target == "src/foo.py"
        lines = act.render_lines()
        assert lines == ["● Editing src/foo.py"]

    def test_map_write_file_create(self):
        ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "write_file", "arguments": {"path": "tests/test_foo.py", "is_new": True}},
            tool_call_id="call_create_1",
        )
        act = ActivityMapper.from_runtime_event(ev)
        assert act is not None
        assert act.status == ActivityStatus.RUNNING
        assert act.operation == ActivityOperation.CREATING
        assert act.target == "tests/test_foo.py"
        lines = act.render_lines()
        assert lines == ["● Creating tests/test_foo.py"]

    def test_map_delete_file(self):
        ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "delete_file", "arguments": {"path": "src/legacy.py"}},
            tool_call_id="call_del_1",
        )
        act = ActivityMapper.from_runtime_event(ev)
        assert act is not None
        assert act.status == ActivityStatus.RUNNING
        assert act.operation == ActivityOperation.DELETING
        assert act.target == "src/legacy.py"
        lines = act.render_lines()
        assert lines == ["● Deleting src/legacy.py"]

    def test_map_run_command(self):
        ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "run_command", "arguments": {"command": "pytest"}},
            tool_call_id="call_cmd_1",
        )
        act = ActivityMapper.from_runtime_event(ev)
        assert act is not None
        assert act.status == ActivityStatus.RUNNING
        assert act.operation == ActivityOperation.RUNNING
        assert act.target == "pytest"
        lines = act.render_lines()
        assert lines == ["● Running pytest"]

    def test_map_verification(self):
        start_ev = RuntimeEvent(
            event_type=EventType.VERIFICATION_STARTED,
            payload={"check": "pytest"},
            task_id="t_ver_1",
        )
        act = ActivityMapper.from_runtime_event(start_ev)
        assert act is not None
        assert act.operation == ActivityOperation.VERIFYING
        assert act.status == ActivityStatus.RUNNING
        assert "Verification running" in act.render_lines()[0]

    def test_map_planning(self):
        plan_ev = RuntimeEvent(
            event_type=EventType.PLAN_STARTED,
            payload={"task_count": 3},
            run_id="run_p1",
        )
        act = ActivityMapper.from_runtime_event(plan_ev)
        assert act is not None
        assert act.operation == ActivityOperation.PLANNING
        assert act.status == ActivityStatus.RUNNING
        assert act.render_lines() == ["● Planning changes"]


# =============================================================================
# 2. Running -> Completed Lifecycle
# =============================================================================

class TestRunningCompletedLifecycle:
    """Verify tool lifecycle transition from running to completed."""

    def test_read_lifecycle(self):
        # 1. Started
        start_ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "read_file", "arguments": {"path": "src/foo.py"}},
            tool_call_id="tc_read_1",
        )
        running_act = ActivityMapper.from_runtime_event(start_ev)
        assert running_act.render_lines() == ["● Reading src/foo.py"]

        # 2. Completed with line count
        done_ev = RuntimeEvent(
            event_type=EventType.TOOL_COMPLETED,
            payload={"tool": "read_file", "metadata": {"path": "src/foo.py", "lines": 213}},
            tool_call_id="tc_read_1",
        )
        completed_act = ActivityMapper.from_runtime_event(done_ev)
        assert completed_act.render_lines() == ["✓ Read 213 lines"]

    def test_edit_lifecycle(self):
        # 1. Started
        start_ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "write_file", "arguments": {"path": "src/foo.py"}},
            tool_call_id="tc_edit_1",
        )
        running_act = ActivityMapper.from_runtime_event(start_ev)
        assert running_act.render_lines() == ["● Editing src/foo.py"]

        # 2. Completed with diff additions/deletions
        done_ev = RuntimeEvent(
            event_type=EventType.TOOL_COMPLETED,
            payload={"tool": "write_file", "metadata": {"path": "src/foo.py", "additions": 12, "deletions": 4}},
            tool_call_id="tc_edit_1",
        )
        completed_act = ActivityMapper.from_runtime_event(done_ev)
        lines = completed_act.render_lines()
        assert lines[0] == "✓ Editing src/foo.py"
        assert lines[1] == "  +12 -4"

    def test_create_lifecycle(self):
        start_ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "write_file", "arguments": {"path": "tests/test_foo.py", "is_new": True}},
            tool_call_id="tc_create_1",
        )
        running_act = ActivityMapper.from_runtime_event(start_ev)
        assert running_act.render_lines() == ["● Creating tests/test_foo.py"]

        done_ev = RuntimeEvent(
            event_type=EventType.TOOL_COMPLETED,
            payload={"tool": "write_file", "metadata": {"path": "tests/test_foo.py", "created": True, "additions": 48}},
            tool_call_id="tc_create_1",
        )
        completed_act = ActivityMapper.from_runtime_event(done_ev)
        lines = completed_act.render_lines()
        assert lines[0] == "✓ Creating tests/test_foo.py"
        assert lines[1] == "  +48"

    def test_command_lifecycle(self):
        start_ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "run_command", "arguments": {"command": "pytest"}},
            tool_call_id="tc_cmd_1",
        )
        running_act = ActivityMapper.from_runtime_event(start_ev)
        assert running_act.render_lines() == ["● Running pytest"]

        done_ev = RuntimeEvent(
            event_type=EventType.TOOL_COMPLETED,
            payload={"tool": "run_command", "metadata": {"command": "pytest", "stdout": "14 passed in 0.18s"}},
            tool_call_id="tc_cmd_1",
        )
        completed_act = ActivityMapper.from_runtime_event(done_ev)
        lines = completed_act.render_lines()
        assert lines[0] == "✓ Running pytest"
        assert lines[1] == "  14 passed"


# =============================================================================
# 3. Failed Lifecycle & Error Presentation
# =============================================================================

class TestFailedLifecycleAndErrors:
    """Verify tool/runtime failure rendering and traceback stripping."""

    def test_command_failure_presentation(self):
        fail_ev = RuntimeEvent(
            event_type=EventType.TOOL_FAILED,
            payload={
                "tool": "run_command",
                "metadata": {"command": "pytest", "exit_code": 1},
                "error": "================ FAILURES ================\n2 tests failed, 12 passed",
            },
            tool_call_id="tc_fail_1",
        )
        act = ActivityMapper.from_runtime_event(fail_ev)
        assert act is not None
        assert act.status == ActivityStatus.FAILED
        lines = act.render_lines()
        assert lines[0] == "✗ Running pytest"
        assert any("exit code 1" in l for l in lines)
        assert any("2 tests failed" in l for l in lines)

    def test_strip_python_traceback(self):
        tb = (
            "Traceback (most recent call last):\n"
            "  File \"/app/main.py\", line 42, in execute\n"
            "    raise FileNotFoundError(\"No such file or directory: 'missing.txt'\")\n"
            "FileNotFoundError: No such file or directory: 'missing.txt'"
        )
        clean = format_concise_error(tb)
        assert "Traceback" not in clean
        assert "File \"/app/main.py\"" not in clean
        assert "missing.txt" in clean

    def test_command_summary_extractor(self):
        assert extract_command_summary("14 passed in 0.12s") == "14 passed"
        assert extract_command_summary("2 failed, 14 passed in 1.2s") == "2 failed, 14 passed"
        assert extract_command_summary("Ran 18 tests in 0.05s") == "Ran 18 tests"
        assert extract_command_summary("") is None


# =============================================================================
# 4. Tool -> Activity Mapping
# =============================================================================

class TestToolResultMapping:
    """Direct mapping from ToolResult to ActivityEvent."""

    def test_tool_result_success(self):
        tr = ToolResult(
            success=True,
            output="file content",
            metadata={"path": "src/agent.py", "lines": 120},
            duration=0.05,
        )
        act = ActivityMapper.from_tool_result(tr, tool_name="read_file", arguments={"path": "src/agent.py"})
        assert act.status == ActivityStatus.COMPLETED
        assert act.operation == ActivityOperation.READING
        assert act.details == "Read 120 lines"

    def test_tool_result_failure(self):
        tr = ToolResult(
            success=False,
            error="PermissionDenied: cannot write to /etc/hosts",
            metadata={"path": "/etc/hosts"},
        )
        act = ActivityMapper.from_tool_result(tr, tool_name="write_file", arguments={"path": "/etc/hosts"})
        assert act.status == ActivityStatus.FAILED
        assert act.operation == ActivityOperation.EDITING
        assert "PermissionDenied" in (act.details or "")


# =============================================================================
# 5. Missing Optional Metadata / Null Safety
# =============================================================================

class TestNullSafety:
    """Ensure the Activity mapper never crashes on sparse or empty events."""

    def test_empty_runtime_event(self):
        ev = RuntimeEvent(event_type=EventType.TOOL_STARTED, payload={})
        act = ActivityMapper.from_runtime_event(ev)
        assert act is not None
        assert act.status == ActivityStatus.RUNNING
        assert act.render_lines()  # Does not crash

    def test_none_event(self):
        assert ActivityMapper.from_runtime_event(None) is None

    def test_missing_metadata_in_tool_completed(self):
        ev = RuntimeEvent(
            event_type=EventType.TOOL_COMPLETED,
            payload={"tool": "write_file"},
        )
        act = ActivityMapper.from_runtime_event(ev)
        assert act is not None
        lines = act.render_lines()
        assert len(lines) >= 1
        assert "write_file" in lines[0] or "file" in lines[0]

    def test_null_error_in_format_concise_error(self):
        assert format_concise_error(None) == "Unknown error"
        assert format_concise_error("", {}) == "Unknown error"


# =============================================================================
# 6. Long-Path Rendering and Truncation
# =============================================================================

class TestPathTruncation:
    """Verify safe path truncation keeping root context and filename."""

    def test_short_path_unchanged(self):
        assert truncate_path("src/foo.py", max_len=36) == "src/foo.py"

    def test_deeply_nested_path(self):
        path = "src/clairecoder/infrastructure/adapters/filesystem/storage_backend.py"
        truncated = truncate_path(path, max_len=36)
        assert len(truncated) <= 36
        assert truncated.startswith("src/...")
        assert truncated.endswith("storage_backend.py")

    def test_long_single_filename(self):
        long_name = "a" * 50
        truncated = truncate_path(long_name, max_len=36)
        assert len(truncated) <= 36
        assert truncated.endswith("...")

    def test_activity_event_renders_truncated_path(self):
        deep_path = "very/deeply/nested/directory/structure/and/subfolder/component.py"
        act = ActivityEvent(
            status=ActivityStatus.RUNNING,
            operation=ActivityOperation.READING,
            target=deep_path,
            file_path=deep_path,
        )
        lines = act.render_lines(width=60)
        assert len(lines[0]) <= 60
        assert "component.py" in lines[0]


# =============================================================================
# 7. Change Summary Aggregation
# =============================================================================

class TestChangeSummaryAggregation:
    """Verify compact aggregate summaries derived from ChangeSet."""

    def test_changeset_dataclass_aggregation(self):
        cs = ChangeSet(
            id="cs_1",
            task_id="t_1",
            files=[
                ChangedFile(path="src/engine.py", operation=FileOperation.MODIFIED, additions=32, deletions=11),
                ChangedFile(path="tests/test_engine.py", operation=FileOperation.CREATED, additions=52, deletions=0),
                ChangedFile(path="docs/spec.md", operation=FileOperation.DELETED, additions=0, deletions=10),
            ],
        )

        summary = ActivityMapper.from_changeset(cs)
        assert summary.file_count == 3
        assert summary.total_additions == 84
        assert summary.total_deletions == 21
        assert len(summary.files) == 3

        lines = summary.format_summary(width=68)
        assert lines[0] == "3 files changed  +84  -21   Review"
        assert any("src/engine.py" in l and "+32 -11" in l for l in lines)
        assert any("tests/test_engine.py" in l and "+52" in l for l in lines)

    def test_changeset_completed_event_renders_summary(self):
        payload = {
            "changeset_id": "cs_99",
            "file_count": 2,
            "total_additions": 14,
            "total_deletions": 3,
            "files": [
                {"path": "src/a.py", "additions": 10, "deletions": 2, "operation": "modified"},
                {"path": "src/b.py", "additions": 4, "deletions": 1, "operation": "modified"},
            ],
        }
        ev = RuntimeEvent(event_type=EventType.CHANGESET_COMPLETED, payload=payload)
        act = ActivityMapper.from_runtime_event(ev)
        assert act is not None
        assert act.change_summary is not None
        lines = act.render_lines()
        assert "2 files changed  +14  -3   Review" in lines[0]


# =============================================================================
# 8. Additions / Deletions Display
# =============================================================================

class TestAdditionsDeletionsDisplay:
    """Verify +N -M formatting matches reference UX."""

    def test_both_additions_and_deletions(self):
        act = ActivityEvent(
            status=ActivityStatus.COMPLETED,
            operation=ActivityOperation.EDITING,
            target="src/foo.py",
            additions=12,
            deletions=4,
        )
        lines = act.render_lines()
        assert lines[0] == "✓ Editing src/foo.py"
        assert lines[1] == "  +12 -4"

    def test_only_additions(self):
        act = ActivityEvent(
            status=ActivityStatus.COMPLETED,
            operation=ActivityOperation.CREATING,
            target="tests/test_foo.py",
            additions=48,
        )
        lines = act.render_lines()
        assert lines[0] == "✓ Creating tests/test_foo.py"
        assert lines[1] == "  +48"


# =============================================================================
# 9. Event Ordering
# =============================================================================

class TestEventOrdering:
    """Verify operations preserve strictly sequential ordering in transcript."""

    def test_sequential_execution_order(self):
        view = TranscriptView()
        e1 = ActivityEvent(status=ActivityStatus.COMPLETED, operation=ActivityOperation.READING, target="src/a.py")
        e2 = ActivityEvent(status=ActivityStatus.COMPLETED, operation=ActivityOperation.EDITING, target="src/b.py")
        e3 = ActivityEvent(status=ActivityStatus.COMPLETED, operation=ActivityOperation.RUNNING, target="pytest")

        m1 = e1.to_activity_model()
        m2 = e2.to_activity_model()
        m3 = e3.to_activity_model()

        view.append_activity(m1)
        view.append_activity(m2)
        view.append_activity(m3)

        assert [a.order_index for a in view.activities] == [0, 1, 2]
        assert view.activities[0].title == "✓ Read src/a.py"
        assert view.activities[1].title == "✓ Editing src/b.py"
        assert view.activities[2].title == "✓ Running pytest"


# =============================================================================
# 10. In-Place Updates & No Duplicate Lifecycle Entries
# =============================================================================

class TestInPlaceLifecycleCorrelation:
    """Verify started -> completed updates in place without duplicate entries."""

    def test_tool_start_and_complete_in_place(self):
        view = TranscriptView()

        # Step 1: Start read_file
        start_ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "read_file", "arguments": {"path": "src/foo.py"}},
            tool_call_id="call_123",
        )
        act1 = ActivityMapper.from_runtime_event(start_ev)
        model1 = act1.to_activity_model()
        view.append_activity(model1)

        assert len(view.activities) == 1
        rendered_1 = view.get_visible_lines()
        assert any("● Reading src/foo.py" in l for l in rendered_1)

        # Step 2: Complete read_file with line count
        done_ev = RuntimeEvent(
            event_type=EventType.TOOL_COMPLETED,
            payload={"tool": "read_file", "metadata": {"path": "src/foo.py", "lines": 213}},
            tool_call_id="call_123",
        )
        act2 = ActivityMapper.from_runtime_event(done_ev)
        model2 = act2.to_activity_model()
        view.update_activity(model2)

        # Still exactly 1 activity in transcript — NO duplicates!
        assert len(view.activities) == 1
        rendered_2 = view.get_visible_lines()
        assert not any("● Reading src/foo.py" in l for l in rendered_2)
        assert any("✓ Read 213 lines" in l for l in rendered_2)

    def test_command_start_and_complete_in_place(self):
        view = TranscriptView()

        start_ev = RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            payload={"tool": "run_command", "arguments": {"command": "pytest"}},
            tool_call_id="call_cmd_456",
        )
        model1 = ActivityMapper.from_runtime_event(start_ev).to_activity_model()
        view.append_activity(model1)

        done_ev = RuntimeEvent(
            event_type=EventType.TOOL_COMPLETED,
            payload={"tool": "run_command", "metadata": {"command": "pytest", "stdout": "14 passed"}},
            tool_call_id="call_cmd_456",
        )
        model2 = ActivityMapper.from_runtime_event(done_ev).to_activity_model()
        view.update_activity(model2)

        assert len(view.activities) == 1
        rendered = view.get_visible_lines()
        assert any("✓ Running pytest" in l for l in rendered)
        assert any("14 passed" in l for l in rendered)


# =============================================================================
# 11. Verification Success and Failure Rendering
# =============================================================================

class TestVerificationRendering:
    """Verify verification lifecycle rendering."""

    def test_verification_success(self):
        ev = RuntimeEvent(
            event_type=EventType.VERIFICATION_COMPLETED,
            payload={"check": "pytest", "passed": True},
        )
        act = ActivityMapper.from_runtime_event(ev)
        assert act is not None
        assert act.status == ActivityStatus.COMPLETED
        lines = act.render_lines()
        assert lines == ["✓ Verification passed"]

    def test_verification_failure(self):
        ev = RuntimeEvent(
            event_type=EventType.VERIFICATION_FAILED,
            payload={"check": "pytest", "error": "Exit code 1: 3 tests failed"},
        )
        act = ActivityMapper.from_runtime_event(ev)
        assert act is not None
        assert act.status == ActivityStatus.FAILED
        lines = act.render_lines()
        assert lines[0] == "✗ Verification failed"
        assert any("3 tests failed" in l for l in lines)
