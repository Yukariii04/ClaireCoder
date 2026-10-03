"""Comprehensive tests for ChangeSet and Diff Store (Correction #16).

Verifies:
1. Newly created file detection and unified diff
2. Modified file detection and unified diff
3. Deleted file detection and unified diff
4. Unchanged files are omitted from changesets
5. Multiple changed files tracking and aggregated statistics
6. Additions and deletions line count calculation
7. Deterministic unified diff generation (no timestamps or random headers)
8. Binary file handling (null bytes, invalid UTF-8, explicit binary diff note)
9. Missing and unreadable file handling
10. Deterministic alphabetical ordering of changed files
11. ChangeSetStore CRUD (create, record, get, list, task queries)
12. Task -> ChangeSet association in store
13. ExecutionResult exposes changeset_id and maintains compatibility
14. RuntimeEvents contain changeset correlation IDs and file statistics
15. Existing execution behavior remains fully compatible
"""

import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock

from clairecoder.changeset.types import (
    ChangeSet,
    ChangeSetStatus,
    ChangedFile,
    FileOperation,
)
from clairecoder.changeset.diff import (
    compute_unified_diff,
    generate_file_diff,
    is_binary_buffer,
)
from clairecoder.changeset.store import ChangeSetStore
from clairecoder.changeset.tracker import ChangeTracker, FileSnapshot, WorkspaceSnapshot
from clairecoder.execution.types import (
    ExecutionResult,
    ExecutionResultCategory,
)
from clairecoder.runtime.agent_runtime import AgentRuntime, RunResult
from clairecoder.runtime.events import EventType, RuntimeEvent
from clairecoder.runtime.emitter import EventEmitter
from clairecoder.workflow.types import Task, TaskState, TaskType, Plan, PlanningLevel
from clairecoder.workflow.task_graph import TaskGraph


# =============================================================================
# 1 & 7. NEWLY CREATED FILE & UNIFIED DIFF
# =============================================================================

def test_newly_created_file(tmp_path: Path):
    """Verify newly created file produces operation=created, correct line counts, and unified diff."""
    tracker = ChangeTracker(workspace_root=str(tmp_path))
    tracker.capture_before()

    # Create new file
    file_path = tmp_path / "hello.py"
    file_path.write_bytes(b"print('hello')\nprint('world')\n")

    changeset = tracker.capture_after(task_id="task_1", run_id="run_1")

    assert len(changeset.files) == 1
    cf = changeset.files[0]
    assert cf.path == "hello.py"
    assert cf.operation == FileOperation.CREATED
    assert cf.existed_before is False
    assert cf.old_content is None
    assert cf.new_content == "print('hello')\nprint('world')\n"
    assert cf.additions == 2
    assert cf.deletions == 0
    assert not cf.is_binary

    # Check diff format
    assert "--- /dev/null" in cf.diff
    assert "+++ b/hello.py" in cf.diff
    assert "+print('hello')" in cf.diff
    assert "+print('world')" in cf.diff


# =============================================================================
# 2. MODIFIED FILE
# =============================================================================

def test_modified_file(tmp_path: Path):
    """Verify modified file produces operation=modified, correct additions/deletions, and unified diff."""
    file_path = tmp_path / "app.py"
    file_path.write_bytes(b"line 1\nline 2\nline 3\n")

    tracker = ChangeTracker(workspace_root=str(tmp_path))
    tracker.capture_before()

    # Modify file: change line 2, delete line 3, add line 4 and 5
    file_path.write_bytes(b"line 1\nline 2 modified\nline 4\nline 5\n")

    changeset = tracker.capture_after(task_id="task_2")

    assert len(changeset.files) == 1
    cf = changeset.files[0]
    assert cf.path == "app.py"
    assert cf.operation == FileOperation.MODIFIED
    assert cf.existed_before is True
    assert cf.old_content == "line 1\nline 2\nline 3\n"
    assert cf.new_content == "line 1\nline 2 modified\nline 4\nline 5\n"
    # deleted 2 lines ('line 2', 'line 3'), added 3 lines ('line 2 modified', 'line 4', 'line 5')
    assert cf.deletions == 2
    assert cf.additions == 3
    assert "--- a/app.py" in cf.diff
    assert "+++ b/app.py" in cf.diff
    assert "-line 2" in cf.diff
    assert "+line 2 modified" in cf.diff


# =============================================================================
# 3. DELETED FILE
# =============================================================================

def test_deleted_file(tmp_path: Path):
    """Verify deleted file produces operation=deleted, correct deletions count, and unified diff."""
    file_path = tmp_path / "deprecated.py"
    file_path.write_bytes(b"alpha\nbeta\ngamma\n")

    tracker = ChangeTracker(workspace_root=str(tmp_path))
    tracker.capture_before()

    # Delete file
    file_path.unlink()

    changeset = tracker.capture_after(task_id="task_3")

    assert len(changeset.files) == 1
    cf = changeset.files[0]
    assert cf.path == "deprecated.py"
    assert cf.operation == FileOperation.DELETED
    assert cf.existed_before is True
    assert cf.old_content == "alpha\nbeta\ngamma\n"
    assert cf.new_content is None
    assert cf.additions == 0
    assert cf.deletions == 3
    assert "--- a/deprecated.py" in cf.diff
    assert "+++ /dev/null" in cf.diff
    assert "-alpha" in cf.diff
    assert "-beta" in cf.diff
    assert "-gamma" in cf.diff


# =============================================================================
# 4. UNCHANGED FILE
# =============================================================================

def test_unchanged_file(tmp_path: Path):
    """Verify files whose content remains unchanged are not counted as modifications."""
    file_path = tmp_path / "constant.py"
    file_path.write_bytes(b"CONST = 42\n")

    tracker = ChangeTracker(workspace_root=str(tmp_path))
    tracker.capture_before()

    # Touch the file or leave it alone
    file_path.touch()

    changeset = tracker.capture_after(task_id="task_4")

    assert len(changeset.files) == 0
    assert changeset.total_additions == 0
    assert changeset.total_deletions == 0


# =============================================================================
# 5 & 6. MULTIPLE CHANGED FILES & ADDITIONS/DELETIONS CALCULATION
# =============================================================================

def test_multiple_changed_files_and_statistics(tmp_path: Path):
    """Verify multiple changed files across nested directories with aggregated additions/deletions."""
    sub_dir = tmp_path / "pkg"
    sub_dir.mkdir()
    f_mod = sub_dir / "mod.py"
    f_mod.write_bytes(b"def old(): pass\n")
    f_del = sub_dir / "del.py"
    f_del.write_bytes(b"line1\nline2\n")

    tracker = ChangeTracker(workspace_root=str(tmp_path))
    tracker.capture_before()

    # 1. Modify mod.py
    f_mod.write_bytes(b"def new(): pass\n")
    # 2. Delete del.py
    f_del.unlink()
    # 3. Create new.py
    f_new = tmp_path / "new.py"
    f_new.write_bytes(b"val = 1\nval = 2\nval = 3\n")

    changeset = tracker.capture_after(task_id="task_multi")

    assert len(changeset.files) == 3
    # Check paths sorted deterministically
    paths = [cf.path for cf in changeset.files]
    assert paths == ["new.py", "pkg/del.py", "pkg/mod.py"]

    # del.py: deletions=2, additions=0
    # mod.py: deletions=1, additions=1
    # new.py: deletions=0, additions=3
    # total: additions=4, deletions=3
    assert changeset.total_additions == 4
    assert changeset.total_deletions == 3


# =============================================================================
# 7. UNIFIED DIFF DETERMINISM
# =============================================================================

def test_unified_diff_determinism():
    """Verify unified diff generation is strictly deterministic and free of timestamps."""
    old_content = "def add(a, b):\n    return a + b\n"
    new_content = "def add(a: int, b: int) -> int:\n    return a + b\n"

    diff1, adds1, dels1 = compute_unified_diff("math.py", old_content, new_content)
    diff2, adds2, dels2 = compute_unified_diff("math.py", old_content, new_content)

    assert diff1 == diff2
    assert adds1 == adds2 == 1
    assert dels1 == dels2 == 1

    # Header must NOT contain timestamp tab or date
    lines = diff1.splitlines()
    assert lines[0] == "--- a/math.py"
    assert lines[1] == "+++ b/math.py"
    assert lines[2].startswith("@@ -1,2 +1,2 @@")


# =============================================================================
# 8. BINARY FILE HANDLING
# =============================================================================

def test_binary_file_handling(tmp_path: Path):
    """Verify binary files do not generate meaningless text diffs and are handled cleanly."""
    bin_file = tmp_path / "image.png"
    bin_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00")

    tracker = ChangeTracker(workspace_root=str(tmp_path))
    tracker.capture_before()

    # Modify binary file
    bin_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x01\x02\x03")

    changeset = tracker.capture_after(task_id="task_bin")

    assert len(changeset.files) == 1
    cf = changeset.files[0]
    assert cf.is_binary is True
    assert cf.operation == FileOperation.MODIFIED
    assert cf.additions == 0
    assert cf.deletions == 0
    assert "Binary files a/image.png and b/image.png differ" in cf.diff
    assert cf.old_content is None
    assert cf.new_content is None

    # Test buffer detector directly
    assert is_binary_buffer(b"hello world\x00null") is True
    assert is_binary_buffer(b"hello world UTF-8 text") is False


# =============================================================================
# 9. MISSING AND UNREADABLE FILE HANDLING
# =============================================================================

def test_missing_and_unreadable_file_handling(tmp_path: Path):
    """Verify missing files and unreadable paths do not cause crashes during capture."""
    tracker = ChangeTracker(workspace_root=str(tmp_path))
    tracker.capture_before()

    # Create and remove an inaccessible or non-existent scenario
    cf = generate_file_diff(
        path="non_existent.py",
        old_content=None,
        new_content=None,
        existed_before=False,
    )
    assert cf is None

    # Workspace scan with missing directory returns empty
    non_existent_tracker = ChangeTracker(workspace_root=str(tmp_path / "does_not_exist"))
    snapshot = non_existent_tracker.scan_workspace()
    assert len(snapshot.files) == 0


# =============================================================================
# 10. DETERMINISTIC ORDERING
# =============================================================================

def test_deterministic_ordering(tmp_path: Path):
    """Verify changed files in ChangeSet are deterministically sorted by path."""
    names = ["z_last.py", "b_second.py", "a_first.py", "m_middle.py"]
    tracker = ChangeTracker(workspace_root=str(tmp_path))
    tracker.capture_before()

    for name in names:
        (tmp_path / name).write_bytes(f"# {name}\n".encode("utf-8"))

    changeset = tracker.capture_after(task_id="task_sort")
    file_paths = [cf.path for cf in changeset.files]

    assert file_paths == sorted(names)


# =============================================================================
# 11 & 12. CHANGESET STORE CRUD & TASK ASSOCIATION
# =============================================================================

def test_changeset_store_crud_and_task_association():
    """Verify ChangeSetStore creation, recording, retrieval, listing, and task indexing."""
    store = ChangeSetStore()

    # 1. create_changeset
    cs1 = store.create_changeset(task_id="task_100", run_id="run_1")
    assert cs1.id.startswith("cs_")
    assert cs1.task_id == "task_100"
    assert cs1.status == ChangeSetStatus.PENDING

    # 2. record_file_change
    cf1 = ChangedFile(
        path="src/main.py",
        operation=FileOperation.CREATED,
        new_content="print(1)\n",
        additions=1,
        deletions=0,
        diff="--- /dev/null\n+++ b/src/main.py\n@@ -0,0 +1 @@\n+print(1)\n",
    )
    updated_cs1 = store.record_file_change(cs1.id, cf1)
    assert updated_cs1 is not None
    assert len(updated_cs1.files) == 1

    # 3. get_changeset
    retrieved = store.get_changeset(cs1.id)
    assert retrieved is not None
    assert retrieved.id == cs1.id
    assert len(retrieved.files) == 1

    # 4. Non-existent returns None
    assert store.get_changeset("non_existent_id") is None

    # 5. Add second changeset for same task
    cs2 = store.create_changeset(task_id="task_100", run_id="run_1")
    store.record_changeset(cs2)

    # Add third changeset for another task
    cs3 = store.create_changeset(task_id="task_200", run_id="run_2")
    store.record_changeset(cs3)

    # 6. list_changesets
    all_cs = store.list_changesets()
    assert len(all_cs) == 3

    # 7. get_task_changes
    task_100_changes = store.get_task_changes("task_100")
    assert len(task_100_changes) == 2
    task_200_changes = store.get_task_changes("task_200")
    assert len(task_200_changes) == 1
    assert task_200_changes[0].id == cs3.id


# =============================================================================
# 13. EXECUTION RESULT EXPOSES CHANGESET_ID
# =============================================================================

def test_execution_result_exposes_changeset_id():
    """Verify ExecutionResult exposes changeset_id and retains backward compatibility."""
    # Default instantiation
    res_default = ExecutionResult(success=True)
    assert res_default.changeset_id is None
    assert res_default.changed_files == []

    # Explicit changeset_id instantiation
    res_with_cs = ExecutionResult(
        success=True,
        task_id="T1",
        changeset_id="cs_abc123",
        changed_files=["foo.py"],
    )
    assert res_with_cs.changeset_id == "cs_abc123"
    assert res_with_cs.changed_files == ["foo.py"]

    # Serialization compatibility
    data = res_with_cs.to_dict()
    assert data["changeset_id"] == "cs_abc123"
    assert data["changed_files"] == ["foo.py"]

    # Deserialization compatibility
    reconstructed = ExecutionResult.from_dict(data)
    assert reconstructed.changeset_id == "cs_abc123"
    assert reconstructed.changed_files == ["foo.py"]


# =============================================================================
# 14. RUNTIME EVENTS CONTAIN CHANGESET INFO
# =============================================================================

def test_runtime_events_contain_changeset_info(tmp_path: Path):
    """Verify AgentRuntime execution loop emits CHANGESET_CREATED, FILE_MODIFIED, and CHANGESET_COMPLETED."""
    emitter = EventEmitter()
    captured_events: list[RuntimeEvent] = []
    emitter.subscribe(captured_events.append)

    # Setup file before run
    target_file = tmp_path / "script.py"
    target_file.write_bytes(b"x = 10\n")

    def mock_executor(task: Task) -> ExecutionResult:
        # Mutate the file during task execution
        target_file.write_bytes(b"x = 20\ny = 30\n")
        return ExecutionResult(success=True, task_id=task.id)

    runtime = AgentRuntime(
        executor=mock_executor,
        event_emitter=emitter,
        workspace_root=str(tmp_path),
    )

    task = Task(
        id="T_edit",
        objective_id="OBJ_1",
        title="Update script",
        description="Update script.py",
        type=TaskType.IMPLEMENTATION,
    )
    graph = TaskGraph(event_emitter=emitter)
    graph.add_task(task)
    graph.finalize()

    run_result = runtime.run(
        objective="Update script",
        task_graph=graph,
        run_id="run_test_cs",
        objective_id="OBJ_1",
    )

    assert run_result.success is True

    # Check emitted events
    event_types = [e.event_type for e in captured_events]
    assert EventType.CHANGESET_CREATED in event_types
    assert EventType.FILE_MODIFIED in event_types
    assert EventType.CHANGESET_COMPLETED in event_types

    # Find the FILE_MODIFIED event
    file_mod_event = next(e for e in captured_events if e.event_type == EventType.FILE_MODIFIED)
    assert file_mod_event.task_id == "T_edit"
    assert file_mod_event.run_id == "run_test_cs"
    assert file_mod_event.changeset_id is not None
    assert file_mod_event.payload["path"] == "script.py"
    assert file_mod_event.payload["operation"] == "modified"
    assert file_mod_event.payload["additions"] == 2
    assert file_mod_event.payload["deletions"] == 1

    # Verify store captured the changeset
    changesets = runtime.changeset_store.get_task_changes("T_edit")
    assert len(changesets) == 1
    assert changesets[0].id == file_mod_event.changeset_id
    assert len(changesets[0].files) == 1
    assert changesets[0].files[0].path == "script.py"


# =============================================================================
# 15. EXISTING EXECUTION BEHAVIOR REMAINS COMPATIBLE
# =============================================================================

def test_existing_execution_behavior_remains_compatible(tmp_path: Path):
    """Verify execution with no file mutations still succeeds and returns valid changeset."""
    emitter = EventEmitter()
    captured_events: list[RuntimeEvent] = []
    emitter.subscribe(captured_events.append)

    def read_only_executor(task: Task) -> ExecutionResult:
        return ExecutionResult(success=True, task_id=task.id, outputs=["read-only completed"])

    runtime = AgentRuntime(
        executor=read_only_executor,
        event_emitter=emitter,
        workspace_root=str(tmp_path),
    )

    task = Task(
        id="T_readonly",
        objective_id="OBJ_RO",
        title="Read-only task",
        description="Check status",
        type=TaskType.ANALYSIS,
    )
    graph = TaskGraph(event_emitter=emitter)
    graph.add_task(task)
    graph.finalize()

    run_result = runtime.run(
        objective="Check status",
        task_graph=graph,
        run_id="run_ro",
        objective_id="OBJ_RO",
    )

    assert run_result.success is True
    # Changeset recorded even if 0 files changed
    changesets = runtime.changeset_store.get_task_changes("T_readonly")
    assert len(changesets) == 1
    assert len(changesets[0].files) == 0
    assert changesets[0].status == ChangeSetStatus.APPLIED
