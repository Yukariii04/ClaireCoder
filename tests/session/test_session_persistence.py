"""Focused tests for Session and Persistence in ClaireCoder (Correction #21).

Tests:
1. Session creation
2. Serialization/deserialization round trip
3. Store save and load
4. List and delete
5. Atomic write behavior & corruption protection
6. Schema version handling
7. Corrupted session handling
8. Missing session handling
9. Runtime checkpoint persistence
10. Task graph restoration
11. Resume behavior
12. Completed tasks not blindly re-executed
13. Interrupted session handling
14. Session lifecycle events
15. Persistence failure handling
16. CLI session integration (--resume, --list-sessions, --inspect-session)
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from clairecoder.session import (
    CURRENT_SCHEMA_VERSION,
    ChangeSetReference,
    Session,
    SessionCorruptedError,
    SessionError,
    SessionMetadata,
    SessionNotFoundError,
    SessionRunState,
    SessionStatus,
    SessionStorageError,
    SessionStore,
    UnsupportedSchemaVersionError,
)
from clairecoder.runtime.agent_runtime import AgentRuntime, RunResult
from clairecoder.runtime.events import EventType, RuntimeEvent
from clairecoder.runtime.emitter import EventEmitter
from clairecoder.workflow.types import Task, TaskState, TaskType, Plan, PlanningLevel
from clairecoder.workflow.task_graph import TaskGraph
from clairecoder.execution.types import (
    ExecutionResult,
    ExecutionResultCategory,
    FailureCategory,
    FailureEvidence,
)
from clairecoder.changeset.types import ChangeSet, ChangedFile, FileOperation, ChangeSetStatus
from clairecoder.changeset.store import ChangeSetStore
from clairecoder.cli.main import run_cli


# =============================================================================
# MOCKS
# =============================================================================

class MockPlanner:
    """Mock planner producing deterministic tasks."""

    def __init__(self, tasks: Optional[List[Task]] = None) -> None:
        self._tasks = tasks or []
        self.create_plan_called = False

    def build_planning_request(self, **kwargs: Any) -> None:
        return None

    def create_plan(self, workflow_id: str, objective: str, **kwargs: Any) -> Plan:
        self.create_plan_called = True
        return Plan(
            id=f"plan_{workflow_id}",
            workflow_id=workflow_id,
            objective=objective,
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=[t.id for t in self._tasks],
        )

    def create_tasks_from_plan(self, plan: Plan, objective_id: str) -> List[Task]:
        return list(self._tasks)


class MockExecutor:
    """Mock executor tracking calls."""

    def __init__(self, handler: Optional[Any] = None) -> None:
        self.executed_task_ids: List[str] = []
        self._handler = handler

    def execute(self, task: Task, **kwargs: Any) -> ExecutionResult:
        self.executed_task_ids.append(task.id)
        if self._handler:
            return self._handler(task)
        return ExecutionResult(
            category=ExecutionResultCategory.SUCCESS,
            task_id=task.id,
            outputs=["success output"],
        )


class MockVerifier:
    """Mock verifier tracking calls and returning pass/fail."""

    def __init__(self, should_pass: bool = True) -> None:
        self.should_pass = should_pass
        self.verified_task_ids: List[str] = []

    def verify(self, task: Task, exec_result: ExecutionResult, **kwargs: Any) -> bool:
        self.verified_task_ids.append(task.id)
        return self.should_pass


# =============================================================================
# 1. SESSION CREATION
# =============================================================================

def test_session_creation(tmp_path: Path) -> None:
    """Session initializes with correct defaults, timestamps, and schema version."""
    session = Session(
        session_id="sess_123",
        workspace_root=str(tmp_path),
        original_objective="Implement auth subsystem",
    )

    assert session.session_id == "sess_123"
    assert session.workspace_root == str(tmp_path)
    assert session.original_objective == "Implement auth subsystem"
    assert session.schema_version == CURRENT_SCHEMA_VERSION
    assert session.status == SessionStatus.ACTIVE
    assert session.created_at is not None
    assert session.updated_at is not None
    assert session.turn_count == 0
    assert session.current_run_id is None
    assert session.current_task_id is None
    assert session.changeset_ids == []


# =============================================================================
# 2. SERIALIZATION / DESERIALIZATION ROUND TRIP
# =============================================================================

def test_session_serialization_deserialization_round_trip(tmp_path: Path) -> None:
    """Session serializes to a dictionary and deserializes without losing data."""
    graph = TaskGraph()
    t1 = Task(id="t1", objective_id="obj_1", description="Task 1", type=TaskType.IMPLEMENTATION, status=TaskState.SUCCEEDED)
    t2 = Task(id="t2", objective_id="obj_1", description="Task 2", dependencies=["t1"], status=TaskState.READY)
    graph.add_task(t1)
    graph.add_task(t2)
    graph.finalize()

    cs_ref = ChangeSetReference(
        changeset_id="cs_001",
        task_id="t1",
        status="applied",
        files_count=2,
        additions=45,
        deletions=10,
        created_at=1700000000.0,
    )

    original = Session(
        session_id="sess_roundtrip",
        workspace_root=str(tmp_path),
        original_objective="Roundtrip test",
        schema_version=CURRENT_SCHEMA_VERSION,
        status=SessionStatus.ACTIVE,
        created_at="2026-10-03T10:00:00+00:00",
        updated_at="2026-10-03T10:15:00+00:00",
        run_state=SessionRunState(
            current_run_id="run_abc",
            current_task_id="t2",
            turn_count=3,
            cycles=2,
            replan_count=1,
        ),
        task_graph_state=graph.to_dict(),
        execution_metadata={"executor": "mock", "attempt": 1},
        changesets=[cs_ref],
        verification_state={"t1": {"status": "passed"}},
        recovery_state={"t2": {"action": "retry"}},
        metadata=SessionMetadata(
            active_model="gpt-4o",
            provider_id="openai",
            tags=["auth", "backend"],
            custom={"env": "testing"},
        ),
    )

    data = original.to_dict()
    restored = Session.from_dict(data)

    assert restored.session_id == original.session_id
    assert restored.workspace_root == original.workspace_root
    assert restored.original_objective == original.original_objective
    assert restored.schema_version == original.schema_version
    assert restored.status == SessionStatus.ACTIVE
    assert restored.created_at == original.created_at
    assert restored.updated_at == original.updated_at
    assert restored.current_run_id == "run_abc"
    assert restored.current_task_id == "t2"
    assert restored.turn_count == 3
    assert restored.run_state.cycles == 2
    assert restored.run_state.replan_count == 1
    assert restored.task_graph_state == graph.to_dict()
    assert restored.execution_metadata == {"executor": "mock", "attempt": 1}
    assert len(restored.changesets) == 1
    assert restored.changesets[0].changeset_id == "cs_001"
    assert restored.changeset_ids == ["cs_001"]
    assert restored.verification_state == {"t1": {"status": "passed"}}
    assert restored.recovery_state == {"t2": {"action": "retry"}}
    assert restored.metadata.active_model == "gpt-4o"
    assert restored.metadata.provider_id == "openai"
    assert restored.metadata.tags == ["auth", "backend"]
    assert restored.metadata.custom == {"env": "testing"}


# =============================================================================
# 3. STORE SAVE AND LOAD
# =============================================================================

def test_session_store_save_and_load(tmp_path: Path) -> None:
    """SessionStore accurately writes and reads sessions from disk."""
    store = SessionStore(sessions_dir=tmp_path / "sessions")
    session = Session(
        session_id="sess_store_test",
        workspace_root=str(tmp_path),
        original_objective="Test save/load",
    )

    store.save(session)
    assert store.exists("sess_store_test")
    file_path = tmp_path / "sessions" / "sess_store_test.json"
    assert file_path.is_file()

    loaded = store.get("sess_store_test")
    assert loaded.session_id == "sess_store_test"
    assert loaded.original_objective == "Test save/load"
    assert loaded.status == SessionStatus.ACTIVE


# =============================================================================
# 4. LIST AND DELETE
# =============================================================================

def test_session_store_list_and_delete(tmp_path: Path) -> None:
    """SessionStore supports listing sessions by updated_at descending and deleting sessions."""
    store = SessionStore(sessions_dir=tmp_path / "sessions")

    s1 = Session(session_id="s1", workspace_root=str(tmp_path), original_objective="Obj 1")
    s1.updated_at = "2026-10-03T10:00:00+00:00"
    s2 = Session(session_id="s2", workspace_root=str(tmp_path), original_objective="Obj 2")
    s2.updated_at = "2026-10-03T12:00:00+00:00"

    store.save(s1)
    store.save(s2)

    sessions = store.list()
    assert len(sessions) == 2
    # s2 was updated later, so it should be first
    assert sessions[0].session_id == "s2"
    assert sessions[1].session_id == "s1"

    # Delete s1
    deleted = store.delete("s1")
    assert deleted is True
    assert not store.exists("s1")
    assert len(store.list()) == 1

    # Deleting non-existent returns False
    assert store.delete("non_existent") is False


# =============================================================================
# 5. ATOMIC WRITE BEHAVIOR
# =============================================================================

def test_atomic_write_behavior(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Atomic write ensures a failed write does not corrupt or destroy the existing session."""
    store = SessionStore(sessions_dir=tmp_path / "sessions")
    session = Session(
        session_id="sess_atomic",
        workspace_root=str(tmp_path),
        original_objective="Original valid objective",
    )
    store.save(session)

    # Verify original exists and is valid
    orig_loaded = store.get("sess_atomic")
    assert orig_loaded.original_objective == "Original valid objective"

    # Modify session objective and force an error during save
    session.original_objective = "Corrupted objective"

    def faulty_dump(*args: Any, **kwargs: Any) -> None:
        raise OSError("Disk write failed midway")

    monkeypatch.setattr("json.dump", faulty_dump)

    with pytest.raises(SessionStorageError) as exc_info:
        store.save(session)
    assert "Disk write failed midway" in str(exc_info.value)

    # Original file must still exist unharmed
    loaded_after = store.get("sess_atomic")
    assert loaded_after.original_objective == "Original valid objective"


# =============================================================================
# 6. SCHEMA VERSION HANDLING
# =============================================================================

def test_schema_version_handling(tmp_path: Path) -> None:
    """Loading a session with an unsupported schema version raises UnsupportedSchemaVersionError."""
    store = SessionStore(sessions_dir=tmp_path / "sessions")
    session = Session(
        session_id="sess_v99",
        workspace_root=str(tmp_path),
        original_objective="Future schema",
    )
    data = session.to_dict()
    data["schema_version"] = 99  # Future unsupported version

    target_file = tmp_path / "sessions" / "sess_v99.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(UnsupportedSchemaVersionError) as exc_info:
        store.get("sess_v99")
    assert exc_info.value.found_version == 99
    assert exc_info.value.supported_version == CURRENT_SCHEMA_VERSION


# =============================================================================
# 7. CORRUPTED SESSION HANDLING
# =============================================================================

def test_corrupted_session_handling(tmp_path: Path) -> None:
    """Malformed JSON or corrupted schema fields raise SessionCorruptedError without silently resetting."""
    store = SessionStore(sessions_dir=tmp_path / "sessions")
    target_file = tmp_path / "sessions" / "sess_corrupt.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Malformed JSON
    target_file.write_text("{ incomplete json ...", encoding="utf-8")
    with pytest.raises(SessionCorruptedError) as exc_info:
        store.get("sess_corrupt")
    assert "Malformed JSON" in str(exc_info.value)

    # 2. Valid JSON but missing required fields
    target_file.write_text(json.dumps({"not_a_session": True}), encoding="utf-8")
    with pytest.raises(SessionCorruptedError) as exc_info:
        store.get("sess_corrupt")
    assert "Missing or invalid session_id" in str(exc_info.value)


# =============================================================================
# 8. MISSING SESSION HANDLING
# =============================================================================

def test_missing_session_handling(tmp_path: Path) -> None:
    """Querying a non-existent session ID raises SessionNotFoundError."""
    store = SessionStore(sessions_dir=tmp_path / "sessions")
    with pytest.raises(SessionNotFoundError) as exc_info:
        store.get("non_existent_session_id")
    assert exc_info.value.session_id == "non_existent_session_id"


# =============================================================================
# 9. RUNTIME CHECKPOINT PERSISTENCE
# =============================================================================

def test_runtime_checkpoint_persistence(tmp_path: Path) -> None:
    """AgentRuntime checkpoints session state to disk at execution boundaries."""
    store = SessionStore(sessions_dir=tmp_path / ".clairecoder" / "sessions")
    events: List[RuntimeEvent] = []
    emitter = EventEmitter()
    emitter.subscribe(events.append)

    t1 = Task(id="task_1", objective_id="obj_1", description="Implement auth", type=TaskType.IMPLEMENTATION)
    t2 = Task(id="task_2", objective_id="obj_1", description="Verify auth", dependencies=["task_1"], type=TaskType.VERIFICATION)
    graph = TaskGraph()
    graph.add_task(t1)
    graph.add_task(t2)
    graph.finalize()

    planner = MockPlanner([t1, t2])
    executor = MockExecutor()
    verifier = MockVerifier(should_pass=True)

    runtime = AgentRuntime(
        planner=planner,
        executor=executor,
        verifier=verifier,
        event_emitter=emitter,
        workspace_root=str(tmp_path),
        session_store=store,
    )

    result = runtime.run(
        objective="Build authentication",
        session_id="sess_checkpoint_test",
        task_graph=graph,
    )

    assert result.success is True
    assert store.exists("sess_checkpoint_test")

    # Inspect persisted session from disk
    persisted = store.get("sess_checkpoint_test")
    assert persisted.session_id == "sess_checkpoint_test"
    assert persisted.status == SessionStatus.COMPLETED
    assert persisted.original_objective == "Build authentication"
    assert persisted.turn_count >= 1
    assert persisted.task_graph_state is not None

    tasks_data = persisted.task_graph_state["tasks"]
    assert len(tasks_data) == 2
    assert all(td["status"] == "succeeded" for td in tasks_data)


# =============================================================================
# 10. TASK GRAPH RESTORATION
# =============================================================================

def test_task_graph_restoration(tmp_path: Path) -> None:
    """TaskGraph round-trips through session state with all states, dependencies, and types preserved."""
    graph = TaskGraph()
    t1 = Task(id="step_1", objective_id="o1", description="Step 1", type=TaskType.ANALYSIS, status=TaskState.SUCCEEDED)
    t2 = Task(id="step_2", objective_id="o1", description="Step 2", dependencies=["step_1"], type=TaskType.IMPLEMENTATION, status=TaskState.PENDING)
    graph.add_task(t1)
    graph.add_task(t2)
    graph.finalize()

    # Calling get_ready_tasks evaluates dependencies and promotes step_2 to READY
    ready_tasks = graph.get_ready_tasks()
    assert len(ready_tasks) == 1
    assert ready_tasks[0].id == "step_2"
    assert t2.status == TaskState.READY

    session = Session(
        session_id="sess_graph_restore",
        workspace_root=str(tmp_path),
        original_objective="Restore graph",
        task_graph_state=graph.to_dict(),
    )

    restored_graph = TaskGraph.from_dict(session.task_graph_state)
    assert restored_graph.task_count == 2
    rt1 = restored_graph.get_task("step_1")
    rt2 = restored_graph.get_task("step_2")
    assert rt1 is not None and rt2 is not None
    assert rt1.status == TaskState.SUCCEEDED
    assert rt1.type == TaskType.ANALYSIS
    assert rt2.status == TaskState.READY
    assert rt2.dependencies == ["step_1"]


# =============================================================================
# 11. RESUME BEHAVIOR
# =============================================================================

def test_resume_behavior(tmp_path: Path) -> None:
    """AgentRuntime.resume_session reloads persisted session and completes execution."""
    store = SessionStore(sessions_dir=tmp_path / ".clairecoder" / "sessions")
    events: List[RuntimeEvent] = []
    emitter = EventEmitter()
    emitter.subscribe(events.append)

    # Create graph with t1 completed and t2 pending
    t1 = Task(id="task_1", objective_id="obj_1", description="Part 1", status=TaskState.SUCCEEDED)
    t2 = Task(id="task_2", objective_id="obj_1", description="Part 2", dependencies=["task_1"], status=TaskState.READY)
    graph = TaskGraph()
    graph.add_task(t1)
    graph.add_task(t2)
    graph.finalize()

    # Pre-populate session in store
    session = Session(
        session_id="sess_resume_test",
        workspace_root=str(tmp_path),
        original_objective="Multi-part objective",
        status=SessionStatus.INTERRUPTED,
        task_graph_state=graph.to_dict(),
    )
    store.save(session)

    executor = MockExecutor()
    verifier = MockVerifier(should_pass=True)
    runtime = AgentRuntime(
        executor=executor,
        verifier=verifier,
        event_emitter=emitter,
        workspace_root=str(tmp_path),
        session_store=store,
    )

    result = runtime.resume_session("sess_resume_test")
    assert result.success is True

    # Verify session status is now COMPLETED
    updated_session = store.get("sess_resume_test")
    assert updated_session.status == SessionStatus.COMPLETED

    # Verify SESSION_RESUMED event was emitted
    resumed_events = [e for e in events if e.event_type == EventType.SESSION_RESUMED]
    assert len(resumed_events) == 1
    assert resumed_events[0].session_id == "sess_resume_test"


# =============================================================================
# 12. COMPLETED TASKS NOT BLINDLY RE-EXECUTED
# =============================================================================

def test_completed_tasks_not_blindly_reexecuted(tmp_path: Path) -> None:
    """When resuming, tasks marked as SUCCEEDED in the persisted session are NOT executed again."""
    store = SessionStore(sessions_dir=tmp_path / ".clairecoder" / "sessions")

    # Task A is completed & verified. Task B was in-flight (RUNNING).
    tA = Task(id="task_A", objective_id="obj_1", description="Task A", status=TaskState.SUCCEEDED)
    tB = Task(id="task_B", objective_id="obj_1", description="Task B", dependencies=["task_A"], status=TaskState.RUNNING)
    graph = TaskGraph()
    graph.add_task(tA)
    graph.add_task(tB)
    graph.finalize()

    session = Session(
        session_id="sess_no_reexec",
        workspace_root=str(tmp_path),
        original_objective="Task A then B",
        status=SessionStatus.INTERRUPTED,
        task_graph_state=graph.to_dict(),
    )
    store.save(session)

    executor = MockExecutor()
    verifier = MockVerifier(should_pass=True)
    runtime = AgentRuntime(
        executor=executor,
        verifier=verifier,
        workspace_root=str(tmp_path),
        session_store=store,
    )

    result = runtime.resume_session("sess_no_reexec")
    assert result.success is True

    # CRITICAL: task_A must NEVER have been executed during this resume run!
    assert "task_A" not in executor.executed_task_ids
    assert "task_B" in executor.executed_task_ids
    assert executor.executed_task_ids == ["task_B"]


# =============================================================================
# 13. INTERRUPTED SESSION HANDLING
# =============================================================================

def test_interrupted_session_handling(tmp_path: Path) -> None:
    """When runtime execution is interrupted (KeyboardInterrupt), session is marked INTERRUPTED and checkpointed safely."""
    store = SessionStore(sessions_dir=tmp_path / ".clairecoder" / "sessions")
    events: List[RuntimeEvent] = []
    emitter = EventEmitter()
    emitter.subscribe(events.append)

    t1 = Task(id="task_interrupt", objective_id="obj_1", description="Long running task")
    graph = TaskGraph()
    graph.add_task(t1)
    graph.finalize()

    def interrupt_handler(task: Task) -> ExecutionResult:
        raise KeyboardInterrupt("Simulated Ctrl+C")

    executor = MockExecutor(handler=interrupt_handler)
    runtime = AgentRuntime(
        executor=executor,
        event_emitter=emitter,
        workspace_root=str(tmp_path),
        session_store=store,
    )

    result = runtime.run(
        objective="Run and interrupt",
        session_id="sess_interrupt_test",
        task_graph=graph,
    )

    assert result.success is False
    assert "interrupted" in result.failure_reason.lower()

    # Session on disk must be marked INTERRUPTED
    persisted = store.get("sess_interrupt_test")
    assert persisted.status == SessionStatus.INTERRUPTED

    # SESSION_INTERRUPTED event must be emitted
    interrupted_events = [e for e in events if e.event_type == EventType.SESSION_INTERRUPTED]
    assert len(interrupted_events) == 1
    assert interrupted_events[0].session_id == "sess_interrupt_test"


# =============================================================================
# 14. SESSION LIFECYCLE EVENTS
# =============================================================================

def test_session_lifecycle_events(tmp_path: Path) -> None:
    """Verifies that all required session events (SESSION_CREATED, CHECKPOINTED, COMPLETED) are emitted with session_id."""
    store = SessionStore(sessions_dir=tmp_path / ".clairecoder" / "sessions")
    events: List[RuntimeEvent] = []
    emitter = EventEmitter()
    emitter.subscribe(events.append)

    t1 = Task(id="t_event", objective_id="obj_1", description="Event test task")
    graph = TaskGraph()
    graph.add_task(t1)
    graph.finalize()

    executor = MockExecutor()
    verifier = MockVerifier(should_pass=True)
    runtime = AgentRuntime(
        executor=executor,
        verifier=verifier,
        event_emitter=emitter,
        workspace_root=str(tmp_path),
        session_store=store,
    )

    runtime.run(
        objective="Test event lifecycle",
        session_id="sess_event_lifecycle",
        task_graph=graph,
    )

    event_types = [e.event_type for e in events]
    assert EventType.SESSION_CREATED in event_types
    assert EventType.SESSION_CHECKPOINTED in event_types
    assert EventType.SESSION_COMPLETED in event_types

    # Ensure all session events carry session_id correlation
    for e in events:
        if e.event_type in (
            EventType.SESSION_CREATED,
            EventType.SESSION_CHECKPOINTED,
            EventType.SESSION_COMPLETED,
        ):
            assert e.session_id == "sess_event_lifecycle"


# =============================================================================
# 15. PERSISTENCE FAILURE HANDLING
# =============================================================================

def test_persistence_failure_handling(tmp_path: Path) -> None:
    """Persistence failure does NOT crash the runtime; instead, AGENT_ERROR is emitted and execution continues."""
    class FailingSessionStore(SessionStore):
        def save(self, session: Session) -> None:
            raise SessionStorageError("Simulated filesystem full error")

    store = FailingSessionStore(sessions_dir=tmp_path / "sessions")
    events: List[RuntimeEvent] = []
    emitter = EventEmitter()
    emitter.subscribe(events.append)

    t1 = Task(id="t_fail", objective_id="obj_1", description="Task under failing storage")
    graph = TaskGraph()
    graph.add_task(t1)
    graph.finalize()

    executor = MockExecutor()
    verifier = MockVerifier(should_pass=True)
    runtime = AgentRuntime(
        executor=executor,
        verifier=verifier,
        event_emitter=emitter,
        workspace_root=str(tmp_path),
        session_store=store,
    )

    # Runtime run should complete successfully despite storage failure
    result = runtime.run(
        objective="Resilient objective",
        session_id="sess_failing_storage",
        task_graph=graph,
    )

    assert result.success is True
    # AGENT_ERROR must be emitted reporting the storage failure
    agent_errors = [e for e in events if e.event_type == EventType.AGENT_ERROR]
    assert len(agent_errors) >= 1
    assert "Session checkpoint persistence failed" in agent_errors[0].payload.get("error", "")


# =============================================================================
# 16. CLI SESSION INTEGRATION
# =============================================================================

def test_cli_session_flags(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """CLI --list-sessions and --inspect-session inspect persisted session states accurately."""
    store = SessionStore(workspace_root=tmp_path)
    session = Session(
        session_id="cli_demo_session",
        workspace_root=str(tmp_path),
        original_objective="Demo CLI session inspection",
        status=SessionStatus.COMPLETED,
    )
    store.save(session)

    # Change working directory context to tmp_path for CLI execution
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # 1. Test --list-sessions
        code = run_cli(["--list-sessions"])
        assert code == 0
        captured = capsys.readouterr().out
        assert "cli_demo_session" in captured
        assert "completed" in captured

        # 2. Test --inspect-session
        code = run_cli(["--inspect-session", "cli_demo_session"])
        assert code == 0
        captured = capsys.readouterr().out
        assert "cli_demo_session" in captured
        assert "Demo CLI session inspection" in captured
        assert "Status:             completed" in captured

        # 3. Test --inspect-session non-existent
        code = run_cli(["--inspect-session", "missing_id"])
        assert code == 1
        err_captured = capsys.readouterr().err
        assert "Error: Session 'missing_id' not found." in err_captured
    finally:
        os.chdir(old_cwd)
