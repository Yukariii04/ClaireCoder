"""Correction #23: End-to-End Hardening & Integration Invariants Test Suite.

Validates the full execution lifecycle:
- Full lifecycle trace from objective to session completion
- Execution failure -> retry -> recovery -> success
- Verification failure -> replan -> recovery
- Session pause -> resume -> sanitization of in-flight and blocked tasks
- max_retries round-trip preservation across TaskGraph serialization
- Tool execution error graceful handling (AGENT_ERROR emission without runtime crash)
- Multi-task dependency chain with conditional branch and blocked propagation
- Gateway resilience and retry under transient provider errors
- Runtime invariants enforcement (state machine, event ordering, changeset integrity, role bounds)
"""

import os
import time
import pytest
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from clairecoder.runtime import EventEmitter, RuntimeEvent, EventType, AgentRuntime, RunResult
from clairecoder.workspace.workspace import Workspace
from clairecoder.tools.registry import ToolRegistry
from clairecoder.changeset.store import ChangeSetStore
from clairecoder.session.store import SessionStore
from clairecoder.session.types import Session, SessionStatus
from clairecoder.runtime.roles import (
    Role,
    RoleContext,
    RoleResult,
    RoleRegistry,
    AgentRole,
    PlannerRole,
    ImplementerRole,
    VerifierRole,
    RecoveryRole,
    RecoveryDecision,
)
from clairecoder.workflow.types import Task, TaskState, TaskType, Plan, PlanningLevel, WorkflowState, PlanningError
from clairecoder.workflow.manager import WorkflowManager
from clairecoder.workflow.task_graph import TaskGraph, TaskGraphError
from clairecoder.workflow.planner import Planner
from clairecoder.execution.types import (
    ExecutionResult,
    ExecutionResultCategory,
    FailureCategory,
)
from clairecoder.verification.types import (
    VerificationResult,
    VerificationStatus,
)
from clairecoder.verification.verifier import Verifier, DefaultVerifier
from clairecoder.gateway.types import (
    Model, Provider, Endpoint, ModelRequest, ModelResponse, Capability,
)
from clairecoder.gateway.gateway import ModelGateway
from clairecoder.gateway.reliability import ReliabilityConfig
from clairecoder.gateway.errors import ProviderRateLimitError, ProviderUnavailableError


# =============================================================================
# HELPERS & MOCKS FOR DETERMINISTIC LIFECYCLE TESTING
# =============================================================================

class ScriptedPlanner:
    """Planner that returns a pre-configured sequence of tasks."""

    def __init__(self, task_batches: List[List[Task]]):
        self._batches = list(task_batches)
        self.call_count = 0

    def build_planning_request(self, **kwargs):
        return None

    def create_plan(self, workflow_id: str, objective: str, **kwargs) -> Plan:
        self.call_count += 1
        tasks = self._batches[0] if self._batches else []
        return Plan(
            id=f"plan_{self.call_count}",
            workflow_id=workflow_id,
            objective=objective,
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=[t.id for t in tasks],
        )

    def create_tasks_from_plan(self, plan: Plan, objective_id: str) -> List[Task]:
        if self._batches:
            return self._batches.pop(0)
        return []

    def build_replan_request(self, **kwargs):
        return None


class ScriptedExecutor:
    """Task execution delegate that can simulate file operations and failures."""

    def __init__(
        self,
        workspace_root: Path,
        behaviors: Optional[Dict[str, List[Any]]] = None,
        error_messages: Optional[Dict[str, str]] = None,
    ):
        self.workspace_root = workspace_root
        self.behaviors = behaviors or {}
        self.error_messages = error_messages or {}
        self.execution_counts: Dict[str, int] = {}

    def __call__(self, task: Task, **kwargs) -> ExecutionResult:
        task_id = task.id
        self.execution_counts[task_id] = self.execution_counts.get(task_id, 0) + 1
        attempt = self.execution_counts[task_id]

        behavior_list = self.behaviors.get(task_id, [])
        behavior = behavior_list[attempt - 1] if attempt <= len(behavior_list) else None

        if behavior == "fail":
            msg = self.error_messages.get(task_id, f"Simulated execution failure on attempt {attempt}")
            return ExecutionResult(
                category=ExecutionResultCategory.FAILURE,
                success=False,
                error_message=msg,
                task_id=task_id,
            )
        elif behavior == "crash":
            raise RuntimeError("Tool crash in execution engine")

        # Default happy-path behavior: create a file for the task
        file_path = self.workspace_root / f"{task_id}.txt"
        file_path.write_text(f"Output of {task_id} attempt {attempt}\n", encoding="utf-8")

        return ExecutionResult(
            category=ExecutionResultCategory.SUCCESS,
            success=True,
            outputs=[f"Executed {task_id}"],
            changed_files=[str(file_path)],
            task_id=task_id,
        )


class ConfigurableVerifier(Verifier):
    """Verifier that can pass, fail, or unverify based on task ID and attempt."""

    def __init__(self, fail_tasks: Optional[Dict[str, int]] = None):
        self.fail_tasks = fail_tasks or {}
        self.verify_counts: Dict[str, int] = {}

    def verify(
        self,
        task: Any,
        execution_result: Any,
        changeset: Optional[Any] = None,
        session_id: Optional[str] = None,
        attempt_number: int = 1,
    ) -> VerificationResult:
        task_id = task.id
        self.verify_counts[task_id] = self.verify_counts.get(task_id, 0) + 1
        failures_allowed = self.fail_tasks.get(task_id, 0)

        if self.verify_counts[task_id] <= failures_allowed:
            return VerificationResult(
                task_id=task_id,
                success=False,
                status=VerificationStatus.FAILED,
                checks=["content_validation"],
                failures=[f"Simulated verification failure for {task_id}"],
                changeset_id=changeset.id if changeset else None,
            )

        return VerificationResult(
            task_id=task_id,
            success=True,
            status=VerificationStatus.PASSED,
            checks=["content_validation"],
            evidence=[f"Task {task_id} verified passed"],
            changeset_id=changeset.id if changeset else None,
        )


# =============================================================================
# END-TO-END LIFECYCLE TESTS
# =============================================================================

def test_e2e_happy_path_all_stages(tmp_path):
    """Trace a full execution: Objective -> Session -> Planning -> Execution -> ChangeSet -> Verification -> Completion."""
    emitter = EventEmitter()
    events: List[RuntimeEvent] = []
    emitter.subscribe(lambda ev: events.append(ev))

    session_store = SessionStore(str(tmp_path / ".sessions"))
    changeset_store = ChangeSetStore()

    executor = ScriptedExecutor(tmp_path)
    planner = ScriptedPlanner([[
        Task(id="task_1", objective_id="obj_happy", title="Create primary artifact", description="Write greeting", type=TaskType.IMPLEMENTATION)
    ]])

    runtime = AgentRuntime(
        workspace_root=str(tmp_path),
        planner=planner,
        executor=executor,
        event_emitter=emitter,
        session_store=session_store,
        changeset_store=changeset_store,
    )

    result = runtime.run(
        objective="Create primary artifact",
        session_id="sess_happy",
    )

    # 1. Run result correctness
    assert result.success is True
    assert len(result.completed_tasks) == 1
    assert len(result.failed_tasks) == 0
    assert result.execution_success is True
    assert result.verification_success is True

    # 2. File created & ChangeSet integrity
    created_file = tmp_path / "task_1.txt"
    assert created_file.exists()
    assert "Output of task_1 attempt 1" in created_file.read_text(encoding="utf-8")

    changesets = changeset_store.list_changesets()
    assert len(changesets) >= 1
    cs = changesets[-1]
    assert any("task_1.txt" in f.path for f in cs.files)

    # 3. Session state saved
    saved_session = session_store.load_session("sess_happy")
    assert saved_session is not None
    assert saved_session.status == SessionStatus.COMPLETED
    assert saved_session.turn_count == 1

    # 4. Lifecycle event causal ordering
    event_types = [ev.event_type for ev in events]
    assert EventType.SESSION_CREATED in event_types
    assert EventType.RUN_STARTED in event_types
    assert EventType.PLAN_STARTED in event_types
    assert EventType.TASK_STARTED in event_types
    assert EventType.CHANGESET_CREATED in event_types
    assert EventType.CHANGESET_COMPLETED in event_types
    assert EventType.TASK_COMPLETED in event_types
    assert EventType.SESSION_COMPLETED in event_types
    assert EventType.RUN_COMPLETED in event_types

    # Strict ordering: RUN_STARTED < TASK_STARTED < TASK_COMPLETED < RUN_COMPLETED
    idx_run_started = event_types.index(EventType.RUN_STARTED)
    idx_task_started = event_types.index(EventType.TASK_STARTED)
    idx_task_completed = event_types.index(EventType.TASK_COMPLETED)
    idx_run_completed = event_types.index(EventType.RUN_COMPLETED)
    assert idx_run_started < idx_task_started < idx_task_completed < idx_run_completed


def test_e2e_execution_failure_retry_and_recovery(tmp_path):
    """Test: Task execution failure on attempt 1 -> retrying -> succeeds on attempt 2."""
    emitter = EventEmitter()
    events: List[RuntimeEvent] = []
    emitter.subscribe(lambda ev: events.append(ev))

    executor = ScriptedExecutor(tmp_path, behaviors={"task_retry": ["fail", "success"]})
    planner = ScriptedPlanner([[
        Task(
            id="task_retry",
            objective_id="obj_retry",
            title="Flaky task",
            description="Fails once then succeeds",
            type=TaskType.IMPLEMENTATION,
            max_retries=2,
        )
    ]])

    runtime = AgentRuntime(
        workspace_root=str(tmp_path),
        planner=planner,
        executor=executor,
        event_emitter=emitter,
        session_store=SessionStore(str(tmp_path / ".sessions")),
    )

    result = runtime.run(
        objective="Execute flaky task",
        session_id="sess_retry",
        max_task_retries=2,
    )

    assert result.success is True
    assert result.recovered_success is True
    assert executor.execution_counts["task_retry"] == 2

    event_types = [ev.event_type for ev in events]
    assert EventType.TASK_FAILED in event_types
    assert EventType.TASK_RETRYING in event_types
    assert EventType.TASK_COMPLETED in event_types
    assert EventType.RUN_COMPLETED in event_types


def test_e2e_verification_failure_and_replan_recovery(tmp_path):
    """Test: Task succeeds execution but fails verification -> triggers replan -> recovers."""
    emitter = EventEmitter()
    events: List[RuntimeEvent] = []
    emitter.subscribe(lambda ev: events.append(ev))

    # Batch 1: task_ver fails verification once
    # Batch 2 (replan): task_replan succeeds verification
    planner = ScriptedPlanner([
        [Task(id="task_ver", objective_id="obj_ver", title="Needs replan", description="Fail ver", type=TaskType.IMPLEMENTATION)],
        [Task(id="task_replan", objective_id="obj_ver", title="Replanned task", description="Succeed ver", type=TaskType.IMPLEMENTATION)],
    ])

    verifier = ConfigurableVerifier(fail_tasks={"task_ver": 1})
    executor = ScriptedExecutor(tmp_path)

    runtime = AgentRuntime(
        workspace_root=str(tmp_path),
        planner=planner,
        executor=executor,
        verifier=verifier,
        event_emitter=emitter,
        session_store=SessionStore(str(tmp_path / ".sessions")),
    )

    result = runtime.run(
        objective="Objective requiring verification recovery",
        session_id="sess_ver_replan",
        max_task_retries=0,  # Force replan on failure rather than in-place task retry
        max_replans=2,
    )

    assert result.success is True
    event_types = [ev.event_type for ev in events]
    assert EventType.RECOVERY_STARTED in event_types
    assert EventType.REPLAN_STARTED in event_types
    assert EventType.RUN_COMPLETED in event_types


def test_e2e_session_pause_and_resume_sanitization(tmp_path):
    """Test: Interrupted session preserves SUCCEEDED, sanitizes RUNNING and BLOCKED tasks on resume."""
    session_store = SessionStore(str(tmp_path / ".sessions"))
    emitter = EventEmitter()

    # Pre-populate a session where:
    # Task 1: SUCCEEDED
    # Task 2: RUNNING (was interrupted mid-execution)
    # Task 3: BLOCKED (depended on Task 2)
    t1 = Task(id="t1", objective_id="obj_resume", title="T1", description="Done", status=TaskState.SUCCEEDED, max_retries=3)
    t2 = Task(id="t2", objective_id="obj_resume", title="T2", description="In flight", status=TaskState.RUNNING, dependencies=["t1"], max_retries=5)
    t3 = Task(id="t3", objective_id="obj_resume", title="T3", description="Waiting", status=TaskState.BLOCKED, dependencies=["t2"], max_retries=2)

    graph = TaskGraph(event_emitter=emitter)
    graph._tasks = {"t1": t1, "t2": t2, "t3": t3}
    graph._insertion_order = ["t1", "t2", "t3"]
    graph._finalized = True

    # Verify max_retries serialization round-trip (Fix #11)
    graph_dict = graph.to_dict()
    assert graph_dict["tasks"][0]["max_retries"] == 3
    assert graph_dict["tasks"][1]["max_retries"] == 5
    assert graph_dict["tasks"][2]["max_retries"] == 2

    restored_graph = TaskGraph.from_dict(graph_dict)
    assert restored_graph.get_task("t1").max_retries == 3
    assert restored_graph.get_task("t2").max_retries == 5
    assert restored_graph.get_task("t3").max_retries == 2

    # Save session
    session = Session(
        session_id="sess_interrupted",
        workspace_root=str(tmp_path),
        original_objective="Finish multi-task work",
        status=SessionStatus.INTERRUPTED,
        task_graph_state=graph_dict,
    )
    session_store.save_session(session)

    # Resume session with runtime
    executor = ScriptedExecutor(tmp_path)
    runtime = AgentRuntime(
        workspace_root=str(tmp_path),
        executor=executor,
        event_emitter=emitter,
        session_store=session_store,
    )

    result = runtime.resume_session("sess_interrupted")

    # t1 must NOT be re-executed
    assert executor.execution_counts.get("t1", 0) == 0
    # t2 and t3 must be executed
    assert executor.execution_counts.get("t2", 0) == 1
    assert executor.execution_counts.get("t3", 0) == 1
    assert result.success is True
    assert len(result.completed_tasks) == 3


def test_e2e_tool_execution_error_graceful_handling(tmp_path):
    """Test: When tool execution raises an unexpected exception, AGENT_ERROR is emitted and runtime does not crash."""
    emitter = EventEmitter()
    errors_emitted: List[RuntimeEvent] = []
    emitter.subscribe(lambda ev: errors_emitted.append(ev) if ev.event_type == EventType.AGENT_ERROR else None)

    executor = ScriptedExecutor(tmp_path, behaviors={"task_crash": ["crash"]})
    planner = ScriptedPlanner([[
        Task(id="task_crash", objective_id="obj_crash", title="Crashing task", description="Throws uncaught", type=TaskType.IMPLEMENTATION)
    ]])

    runtime = AgentRuntime(
        workspace_root=str(tmp_path),
        planner=planner,
        executor=executor,
        event_emitter=emitter,
        session_store=SessionStore(str(tmp_path / ".sessions")),
    )

    result = runtime.run(
        objective="Run crashing tool",
        session_id="sess_crash",
        max_task_retries=0,
        max_replans=0,
    )

    # Runtime caught exception gracefully
    assert result.success is False
    assert len(result.failed_tasks) == 1
    assert len(errors_emitted) >= 1
    assert "Tool crash" in errors_emitted[0].payload.get("error", "")


def test_e2e_multi_task_dependency_graph_branching(tmp_path):
    """Test: Diamond graph where failure in one branch blocks dependents, but independent branch succeeds."""
    # Graph:
    #      t_root
    #      /    \
    #    t_fail  t_ok
    #     |
    #    t_blocked
    t_root = Task(id="t_root", objective_id="obj_diamond", title="Root", description="Root task")
    t_fail = Task(id="t_fail", objective_id="obj_diamond", title="Failing branch", description="Fails", dependencies=["t_root"])
    t_ok = Task(id="t_ok", objective_id="obj_diamond", title="Healthy branch", description="Succeeds", dependencies=["t_root"])
    t_blocked = Task(id="t_blocked", objective_id="obj_diamond", title="Blocked dependent", description="Waits on fail", dependencies=["t_fail"])

    planner = ScriptedPlanner([[t_root, t_fail, t_ok, t_blocked]])
    executor = ScriptedExecutor(tmp_path, behaviors={"t_fail": ["fail"]})

    runtime = AgentRuntime(
        workspace_root=str(tmp_path),
        planner=planner,
        executor=executor,
        session_store=SessionStore(str(tmp_path / ".sessions")),
    )

    result = runtime.run(
        objective="Execute branching workflow",
        session_id="sess_diamond",
        max_task_retries=0,
        max_replans=0,
    )

    assert result.success is False
    assert "t_root" in [t.id for t in result.task_graph.tasks if t.status == TaskState.SUCCEEDED]
    assert "t_ok" in [t.id for t in result.task_graph.tasks if t.status == TaskState.SUCCEEDED]
    assert "t_fail" in [t.id for t in result.task_graph.tasks if t.status == TaskState.FAILED]
    assert "t_blocked" in [t.id for t in result.task_graph.tasks if t.status == TaskState.BLOCKED]


def test_e2e_gateway_resilience_and_retry(tmp_path):
    """Test: ModelGateway handles transient errors via RetryExecutor and succeeds without crashing runtime."""
    emitter = EventEmitter()
    events: List[RuntimeEvent] = []
    emitter.subscribe(lambda ev: events.append(ev))

    reliability_config = ReliabilityConfig(max_retry_attempts=3, initial_retry_delay=0.01)
    gateway = ModelGateway(reliability_config=reliability_config, event_emitter=emitter)

    model = Model(
        id="mock-resilient",
        display_name="Mock Resilient",
        provider=Provider(id="resilient-prov", name="Resilient Provider"),
        endpoint=Endpoint(url="http://mock"),
    )
    gateway.register_model(model)

    # Adapter with 2 transient failures then success
    attempt_count = 0
    def mock_execute(model, req):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ProviderRateLimitError(provider="resilient-prov", message="Rate limited; please back off")
        return ModelResponse(text="Resilience recovered successfully", tool_calls=[])

    mock_adapter = MagicMock()
    mock_adapter.provider_id = "resilient-prov"
    mock_adapter.execute.side_effect = mock_execute
    gateway.register_adapter(mock_adapter)

    # Execute request
    req = ModelRequest(model_id="mock-resilient", messages=[{"role": "user", "content": "Hi"}])
    resp = gateway.execute(req)

    assert resp.text == "Resilience recovered successfully"
    assert attempt_count == 3

    # Check retry events emitted
    event_types = [ev.event_type for ev in events]
    assert EventType.PROVIDER_REQUEST_RETRYING in event_types


# =============================================================================
# RUNTIME INVARIANTS ENFORCEMENT
# =============================================================================

def test_invariant_task_graph_state_machine():
    """Invariant: Illegal state transitions raise TaskGraphError."""
    graph = TaskGraph()
    t = Task(id="inv_t1", objective_id="obj_inv", description="Test invariant")
    graph.add_task(t)
    graph.finalize()

    # Initial state is READY
    assert t.status == TaskState.READY

    # Mark started -> RUNNING
    graph.mark_started("inv_t1")
    assert t.status == TaskState.RUNNING

    # Attempting to start an already running task raises TaskGraphError
    with pytest.raises(TaskGraphError):
        graph.mark_started("inv_t1")

    # Mark completed -> SUCCEEDED
    graph.mark_completed("inv_t1")
    assert t.status == TaskState.SUCCEEDED

    # Cannot transition SUCCEEDED to RUNNING
    with pytest.raises(TaskGraphError):
        graph.mark_started("inv_t1")


def test_invariant_changeset_tracking_integrity(tmp_path):
    """Invariant: Every file creation and modification during task execution is captured."""
    workspace = Workspace(str(tmp_path))
    tracker = workspace.create_tracker()
    tracker.capture_before()

    # Modify workspace: create file A, modify file B
    (tmp_path / "file_a.txt").write_text("Alpha content", encoding="utf-8")
    (tmp_path / "file_b.txt").write_text("Beta original", encoding="utf-8")
    tracker.capture_before()  # snapshot before B modification
    (tmp_path / "file_b.txt").write_text("Beta modified", encoding="utf-8")

    cs = tracker.capture_after(task_id="inv_task")
    assert cs is not None
    modified_paths = {f.path for f in cs.files}
    assert any("file_b.txt" in p for p in modified_paths)


def test_invariant_role_boundedness():
    """Invariant: RoleContext carries only specified bounded fields, preventing internal state leakage."""
    ctx = RoleContext(
        run_id="inv_run",
        objective="test invariant",
        task_id="t1",
        attempt=1,
    )
    # Role context must not leak runtime mutable internals
    assert not hasattr(ctx, "runtime")
    assert not hasattr(ctx, "event_emitter")
    assert not hasattr(ctx, "task_graph")
    assert not hasattr(ctx, "session_store")
    assert not hasattr(ctx, "changeset_store")


# =============================================================================
# CORRECTION #23 REGRESSION SUITE: REPLANNING -> FAILED LIFECYCLE BUG
# =============================================================================

class MockReplanPlanner:
    """Planner for simulating initial planning and replanning outcomes."""

    def __init__(self, initial_tasks: List[Task], replan_tasks: Optional[List[Task]] = None, fail_replan: bool = False):
        self.initial_tasks = initial_tasks
        self.replan_tasks = replan_tasks or []
        self.fail_replan = fail_replan
        self.plan_count = 0

    def create_plan(self, workflow_id: str, objective: str, planning_level: PlanningLevel, model_response: Any = None, strict: bool = False) -> Plan:
        self.plan_count += 1
        if self.plan_count == 1:
            return Plan(
                id="plan_init",
                workflow_id=workflow_id,
                objective=objective,
                planning_level=planning_level,
                task_ids=[t.id for t in self.initial_tasks],
            )
        if self.fail_replan:
            raise PlanningError("Simulated replanning model response failure: invalid schema")
        return Plan(
            id=f"plan_replan_{self.plan_count}",
            workflow_id=workflow_id,
            objective=objective,
            planning_level=planning_level,
            task_ids=[t.id for t in self.replan_tasks],
        )

    def create_tasks_from_plan(self, plan: Plan, objective_id: str) -> List[Task]:
        if plan.id == "plan_init":
            return self.initial_tasks
        return self.replan_tasks


def test_regression_replan_failure_transitions_to_failed_without_error(tmp_path):
    """Reproduce exact live CLI scenario:
    - Task execution failure
    - Workflow enters REPLANNING
    - Replan fails to generate a new plan
    - Workflow reaches terminal WorkflowState.FAILED without 'Cannot transition Workflow ... from replanning to failed'
    - Exactly one terminal failure event emitted
    - No false RUN_COMPLETED
    - Original failure evidence is preserved
    """
    emitter = EventEmitter()
    events: List[RuntimeEvent] = []
    emitter.subscribe(lambda ev: events.append(ev))

    wm = WorkflowManager()
    session_id = "cli_dc717eac"
    task_fail = Task(
        id="task-1",
        objective_id="obj_cli",
        title="Failing live task",
        description="Fails with exit code 1",
        type=TaskType.IMPLEMENTATION,
        max_retries=0,
    )

    executor = ScriptedExecutor(
        tmp_path,
        behaviors={"task-1": ["fail"]},
        error_messages={"task-1": "Process returned non-zero exit status 1"},
    )
    planner = MockReplanPlanner(initial_tasks=[task_fail], fail_replan=True)

    runtime = AgentRuntime(
        workspace_root=str(tmp_path),
        planner=planner,
        executor=executor,
        verifier=DefaultVerifier(),
        workflow_manager=wm,
        event_emitter=emitter,
        session_store=SessionStore(str(tmp_path / ".sessions")),
    )

    # Must execute cleanly without raising WorkflowStateError
    result = runtime.run(
        objective="Run live CLI task with replanning",
        session_id=session_id,
        max_replans=1,
    )

    assert result.success is False
    assert result.execution_success is False
    assert "Process returned non-zero exit status 1" in result.failure_reason

    # Verify workflow state machine reached FAILED cleanly
    workflow = wm.get_workflow(f"wf_{session_id}")
    assert workflow is not None
    assert workflow.state == WorkflowState.FAILED

    # Verify terminal event invariants
    replan_started = [e for e in events if e.event_type == EventType.REPLAN_STARTED]
    assert len(replan_started) == 1

    recovery_failed = [e for e in events if e.event_type == EventType.RECOVERY_FAILED]
    assert len(recovery_failed) == 1, f"Expected exactly 1 RECOVERY_FAILED, got {len(recovery_failed)}"
    assert recovery_failed[0].payload.get("recovery_type") == "replan"

    run_failed = [e for e in events if e.event_type == EventType.RUN_FAILED]
    assert len(run_failed) == 1
    assert "Process returned non-zero exit status 1" in run_failed[0].payload["reason"]

    run_completed = [e for e in events if e.event_type == EventType.RUN_COMPLETED]
    assert len(run_completed) == 0, "Must not emit false RUN_COMPLETED on failure!"

    session_failed = [e for e in events if e.event_type == EventType.SESSION_FAILED]
    assert len(session_failed) == 1


def test_regression_successful_replan_returns_to_executable_and_completes(tmp_path):
    """Verify that successful replan transitions REPLANNING -> PLANNED -> ACTIVE and completes."""
    emitter = EventEmitter()
    events: List[RuntimeEvent] = []
    emitter.subscribe(lambda ev: events.append(ev))

    wm = WorkflowManager()
    session_id = "sess_replan_ok"
    t_fail = Task(id="t_fail", objective_id="obj_ok", title="First task", description="Initial", type=TaskType.IMPLEMENTATION, max_retries=0)
    t_replan = Task(id="t_replan", objective_id="obj_ok", title="Fixed task", description="Replanned", type=TaskType.IMPLEMENTATION)

    executor = ScriptedExecutor(tmp_path, behaviors={"t_fail": ["fail"], "t_replan": ["success"]})
    planner = MockReplanPlanner(initial_tasks=[t_fail], replan_tasks=[t_replan], fail_replan=False)

    runtime = AgentRuntime(
        workspace_root=str(tmp_path),
        planner=planner,
        executor=executor,
        verifier=DefaultVerifier(),
        workflow_manager=wm,
        event_emitter=emitter,
        session_store=SessionStore(str(tmp_path / ".sessions")),
    )

    result = runtime.run(
        objective="Objective recovering via replan",
        session_id=session_id,
        max_replans=1,
    )

    assert result.success is True
    assert result.recovered_success is True
    assert "t_replan" in result.completed_tasks

    workflow = wm.get_workflow(f"wf_{session_id}")
    assert workflow is not None
    assert workflow.state == WorkflowState.COMPLETE

    event_types = [e.event_type for e in events]
    assert EventType.REPLAN_STARTED in event_types
    assert EventType.RECOVERY_COMPLETED in event_types
    assert EventType.RUN_COMPLETED in event_types
    assert EventType.RUN_FAILED not in event_types


def test_regression_exhausted_replan_budget_produces_clean_failure(tmp_path):
    """When replan budget is 0, execution failure transitions directly to FAILED with exact 1 failure event."""
    emitter = EventEmitter()
    events: List[RuntimeEvent] = []
    emitter.subscribe(lambda ev: events.append(ev))

    wm = WorkflowManager()
    session_id = "sess_budget_0"
    t_fail = Task(id="t_budget", objective_id="obj_b0", title="Fail task", description="Cannot replan", type=TaskType.IMPLEMENTATION, max_retries=0)

    executor = ScriptedExecutor(tmp_path, behaviors={"t_budget": ["fail"]}, error_messages={"t_budget": "Fatal command error"})
    planner = MockReplanPlanner(initial_tasks=[t_fail], fail_replan=True)

    runtime = AgentRuntime(
        workspace_root=str(tmp_path),
        planner=planner,
        executor=executor,
        verifier=DefaultVerifier(),
        workflow_manager=wm,
        event_emitter=emitter,
        session_store=SessionStore(str(tmp_path / ".sessions")),
    )

    result = runtime.run(
        objective="Run without replans",
        session_id=session_id,
        max_replans=0,
    )

    assert result.success is False
    assert "Fatal command error" in result.failure_reason

    workflow = wm.get_workflow(f"wf_{session_id}")
    assert workflow is not None
    assert workflow.state == WorkflowState.FAILED

    replan_started = [e for e in events if e.event_type == EventType.REPLAN_STARTED]
    assert len(replan_started) == 0

    run_failed = [e for e in events if e.event_type == EventType.RUN_FAILED]
    assert len(run_failed) == 1


def test_regression_verification_failure_replan_semantics(tmp_path):
    """Verification failure triggers replan; when replan fails, workflow cleanly transitions VALIDATING -> FAILED -> REPLANNING -> FAILED."""
    emitter = EventEmitter()
    events: List[RuntimeEvent] = []
    emitter.subscribe(lambda ev: events.append(ev))

    wm = WorkflowManager()
    session_id = "sess_ver_fail"
    t_ver = Task(id="t_ver", objective_id="obj_ver", title="Ver fail task", description="Execution ok, ver fails", type=TaskType.IMPLEMENTATION, max_retries=0)

    executor = ScriptedExecutor(tmp_path, behaviors={"t_ver": ["success"]})
    verifier = ConfigurableVerifier(fail_tasks={"t_ver": 5})
    planner = MockReplanPlanner(initial_tasks=[t_ver], fail_replan=True)

    runtime = AgentRuntime(
        workspace_root=str(tmp_path),
        planner=planner,
        executor=executor,
        verifier=verifier,
        workflow_manager=wm,
        event_emitter=emitter,
        session_store=SessionStore(str(tmp_path / ".sessions")),
    )

    result = runtime.run(
        objective="Verification failure objective",
        session_id=session_id,
        max_replans=1,
    )

    assert result.success is False
    assert result.verification_success is False
    assert "Simulated verification failure for t_ver" in result.failure_reason

    workflow = wm.get_workflow(f"wf_{session_id}")
    assert workflow is not None
    assert workflow.state == WorkflowState.FAILED

    recovery_failed = [e for e in events if e.event_type == EventType.RECOVERY_FAILED]
    assert len(recovery_failed) == 1

    run_failed = [e for e in events if e.event_type == EventType.RUN_FAILED]
    assert len(run_failed) == 1
    assert "Simulated verification failure for t_ver" in run_failed[0].payload["reason"]

