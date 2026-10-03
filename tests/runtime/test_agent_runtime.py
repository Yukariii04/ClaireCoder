"""Tests for AgentRuntime (Correction #14).

Verifies the dedicated agent execution lifecycle, architectural boundaries,
event emission, structured RunResult, and prevention of contradictory states.
"""

import pytest
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from clairecoder.runtime import EventEmitter, RuntimeEvent, EventType, AgentRuntime, RunResult
from clairecoder.workflow.types import Task, TaskState, TaskType, Plan, PlanningLevel
from clairecoder.workflow.task_graph import TaskGraph
from clairecoder.execution.types import (
    ExecutionResult,
    ExecutionResultCategory,
    FailureCategory,
    FailureEvidence,
)


class MockPlanner:
    """Mock planner producing deterministic tasks."""

    def __init__(self, tasks: Optional[List[Task]] = None):
        self._tasks = tasks or []
        self.create_plan_called = False
        self.create_tasks_called = False

    def build_planning_request(self, **kwargs):
        return None

    def create_plan(self, workflow_id: str, objective: str, **kwargs) -> Plan:
        self.create_plan_called = True
        return Plan(
            id=f"plan_{workflow_id}",
            workflow_id=workflow_id,
            objective=objective,
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=[t.id for t in self._tasks],
        )

    def create_tasks_from_plan(self, plan: Plan, objective_id: str) -> List[Task]:
        self.create_tasks_called = True
        return list(self._tasks)


class MockExecutor:
    """Mock executor tracking calls and returning custom results."""

    def __init__(self, handler=None):
        self.executed_task_ids: List[str] = []
        self._handler = handler

    def execute(self, task: Task, **kwargs) -> ExecutionResult:
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

    def __init__(self, should_pass: bool = True):
        self.should_pass = should_pass
        self.verified_task_ids: List[str] = []

    def verify(self, task: Task, exec_result: ExecutionResult, **kwargs) -> bool:
        self.verified_task_ids.append(task.id)
        return self.should_pass


class EventCollector:
    """Captures all emitted RuntimeEvents."""

    def __init__(self, emitter: EventEmitter):
        self.events: List[RuntimeEvent] = []
        emitter.subscribe(self._on_event)

    def _on_event(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> List[EventType]:
        return [e.event_type for e in self.events]


# =============================================================================
# 1. RUNTIME START AND STRUCTURED RESULT
# =============================================================================

def test_runtime_start_run_and_structured_result():
    """AgentRuntime starts a run and returns a structured RunResult."""
    t1 = Task(id="t1", objective_id="obj_1", description="Task 1 desc", title="Task 1", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1])
    executor = MockExecutor()
    runtime = AgentRuntime(planner=planner, executor=executor)

    result = runtime.run(objective="Implement feature", objective_id="obj_1", run_id="run_101")

    assert isinstance(result, RunResult)
    assert result.success is True
    assert result.run_id == "run_101"
    assert result.objective_id == "obj_1"
    assert result.completed_tasks == ["t1"]
    assert result.failed_tasks == []
    assert result.blocked_tasks == []
    assert result.failure_reason is None


# =============================================================================
# 2. PLANNER BOUNDARY & TASKGRAPH HYDRATION
# =============================================================================

def test_runtime_invokes_planner_and_builds_taskgraph():
    """AgentRuntime invokes planner and converts plan into a TaskGraph."""
    t1 = Task(id="t1", objective_id="obj_1", description="Research desc", title="Task 1", type=TaskType.ANALYSIS)
    t2 = Task(id="t2", objective_id="obj_1", description="Impl desc", title="Task 2", type=TaskType.IMPLEMENTATION, dependencies=["t1"])
    planner = MockPlanner(tasks=[t1, t2])
    runtime = AgentRuntime(planner=planner)

    result = runtime.run(objective="Multi-step task", objective_id="obj_1")

    assert planner.create_plan_called is True
    assert planner.create_tasks_called is True
    assert result.success is True
    assert "t1" in result.completed_tasks
    assert "t2" in result.completed_tasks


# =============================================================================
# 3. TASK EXECUTION & UNLOCKING DEPENDENTS
# =============================================================================

def test_runtime_executes_ready_tasks_and_unlocks_dependents():
    """Completing an upstream task transitions dependent task to READY and executes it."""
    t1 = Task(id="t1", objective_id="obj_1", description="First desc", title="First", type=TaskType.IMPLEMENTATION)
    t2 = Task(id="t2", objective_id="obj_1", description="Second desc", title="Second", type=TaskType.IMPLEMENTATION, dependencies=["t1"])
    planner = MockPlanner(tasks=[t1, t2])
    executor = MockExecutor()
    runtime = AgentRuntime(planner=planner, executor=executor)

    result = runtime.run(objective="Sequential pipeline", objective_id="obj_1")

    assert result.success is True
    assert executor.executed_task_ids == ["t1", "t2"]
    assert result.completed_tasks == ["t1", "t2"]


def test_runtime_handles_multiple_independent_tasks():
    """Multiple independent tasks execute without blocking each other."""
    t1 = Task(id="t1", objective_id="obj_1", description="Indep 1 desc", title="Independent 1", type=TaskType.IMPLEMENTATION)
    t2 = Task(id="t2", objective_id="obj_1", description="Indep 2 desc", title="Independent 2", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1, t2])
    executor = MockExecutor()
    runtime = AgentRuntime(planner=planner, executor=executor)

    result = runtime.run(objective="Independent tasks", objective_id="obj_1")

    assert result.success is True
    assert set(executor.executed_task_ids) == {"t1", "t2"}
    assert set(result.completed_tasks) == {"t1", "t2"}


# =============================================================================
# 4. FAILURE HANDLING & DEPENDENCY BLOCKING
# =============================================================================

def test_runtime_execution_failure_marks_task_failed_and_blocks_dependents():
    """An execution failure marks the task FAILED and cascades BLOCKED to dependents."""
    t1 = Task(id="t1", objective_id="obj_1", description="Fail desc", title="Failing Task", type=TaskType.IMPLEMENTATION)
    t2 = Task(id="t2", objective_id="obj_1", description="Dep desc", title="Dependent Task", type=TaskType.IMPLEMENTATION, dependencies=["t1"])
    planner = MockPlanner(tasks=[t1, t2])

    def fail_t1(task: Task) -> ExecutionResult:
        if task.id == "t1":
            return ExecutionResult(
                category=ExecutionResultCategory.FAILURE,
                failure_category=FailureCategory.TOOL_FAILURE,
                error_message="Tool syntax error",
                failure_evidence=FailureEvidence(task_id="t1", reason="Syntax error in tool execution"),
                task_id="t1",
            )
        return ExecutionResult(category=ExecutionResultCategory.SUCCESS, task_id=task.id)

    executor = MockExecutor(handler=fail_t1)
    runtime = AgentRuntime(planner=planner, executor=executor)

    result = runtime.run(objective="Pipeline with failure", objective_id="obj_1")

    assert result.success is False
    assert result.failed_tasks == ["t1"]
    assert result.blocked_tasks == ["t2"]
    assert "t2" not in executor.executed_task_ids  # Downstream task was never executed!
    assert "Tool syntax error" in (result.failure_reason or "")


# =============================================================================
# 5. VERIFICATION BOUNDARY
# =============================================================================

def test_runtime_verification_success_completes_task():
    """Verifier returning success allows task to be marked completed."""
    t1 = Task(id="t1", objective_id="obj_1", description="Verified desc", title="Verified Task", type=TaskType.IMPLEMENTATION, validation_requirements=["Check X"])
    planner = MockPlanner(tasks=[t1])
    verifier = MockVerifier(should_pass=True)
    runtime = AgentRuntime(planner=planner, verifier=verifier)

    result = runtime.run(objective="Verified flow", objective_id="obj_1")

    assert result.success is True
    assert verifier.verified_task_ids == ["t1"]
    assert result.completed_tasks == ["t1"]


def test_runtime_verification_failure_produces_task_failure():
    """Verifier returning failure causes task failure and run failure."""
    t1 = Task(id="t1", objective_id="obj_1", description="Strict desc", title="Task with bad test", type=TaskType.IMPLEMENTATION, validation_requirements=["Strict test"])
    planner = MockPlanner(tasks=[t1])
    verifier = MockVerifier(should_pass=False)
    runtime = AgentRuntime(planner=planner, verifier=verifier)

    result = runtime.run(objective="Verification failure flow", objective_id="obj_1")

    assert result.success is False
    assert verifier.verified_task_ids == ["t1"]
    assert result.failed_tasks == ["t1"]
    assert result.completed_tasks == []


# =============================================================================
# 6. EVENT EMISSION (Correction #12 Integration)
# =============================================================================

def test_runtime_event_lifecycle_on_success():
    """AgentRuntime emits a clean, non-contradictory event stream on success."""
    emitter = EventEmitter()
    collector = EventCollector(emitter)

    t1 = Task(id="t1", objective_id="obj_1", description="T1 desc", title="Task 1", type=TaskType.IMPLEMENTATION, validation_requirements=["Val 1"])
    planner = MockPlanner(tasks=[t1])
    verifier = MockVerifier(should_pass=True)
    runtime = AgentRuntime(planner=planner, verifier=verifier, event_emitter=emitter)

    result = runtime.run(objective="Success run", objective_id="obj_1", run_id="run_success")

    assert result.success is True
    expected_order = [
        EventType.RUN_STARTED,
        EventType.PLAN_STARTED,
        EventType.PLAN_CREATED,
        EventType.TASK_STARTED,
        EventType.VERIFICATION_STARTED,
        EventType.VERIFICATION_COMPLETED,
        EventType.TASK_COMPLETED,
        EventType.RUN_COMPLETED,
    ]
    # Check that events occurred in this relative order
    actual_types = collector.types
    for exp in expected_order:
        assert exp in actual_types, f"Expected event {exp} was not emitted. Emitted: {actual_types}"

    # Verify order
    indices = [actual_types.index(e) for e in expected_order]
    assert indices == sorted(indices), f"Events out of order: {actual_types}"


def test_runtime_event_lifecycle_on_failure():
    """AgentRuntime emits RUN_FAILED when tasks fail terminally."""
    emitter = EventEmitter()
    collector = EventCollector(emitter)

    t1 = Task(id="t1", objective_id="obj_1", description="Fail desc", title="Fail Task", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1])
    executor = MockExecutor(handler=lambda t: ExecutionResult(success=False, error_message="Crash", task_id=t.id))
    runtime = AgentRuntime(planner=planner, executor=executor, event_emitter=emitter)

    result = runtime.run(objective="Failing run", objective_id="obj_1", run_id="run_fail")

    assert result.success is False
    actual_types = collector.types
    assert EventType.RUN_STARTED in actual_types
    assert EventType.TASK_STARTED in actual_types
    assert EventType.TASK_FAILED in actual_types
    assert EventType.RUN_FAILED in actual_types
    assert EventType.RUN_COMPLETED not in actual_types


# =============================================================================
# 7. SECTION 19 REGRESSION: ELIMINATION OF CONTRADICTIONS
# =============================================================================

def test_regression_execution_failure_never_triggers_verification_or_task_completion():
    """REGRESSION TEST (Section 19): Execution failure must NEVER trigger verification,

    must NEVER emit VERIFICATION_STARTED, and must NEVER emit TASK_COMPLETED.
    """
    emitter = EventEmitter()
    collector = EventCollector(emitter)

    t1 = Task(id="t1", objective_id="obj_1", description="Broken desc", title="Broken Task", type=TaskType.IMPLEMENTATION, validation_requirements=["Must Validate"])
    planner = MockPlanner(tasks=[t1])
    executor = MockExecutor(handler=lambda t: ExecutionResult(success=False, error_message="Compilation Error", task_id=t.id))
    verifier = MockVerifier(should_pass=True)  # Should never be called!
    runtime = AgentRuntime(planner=planner, executor=executor, verifier=verifier, event_emitter=emitter)

    result = runtime.run(objective="Regression test execution failure", objective_id="obj_1")

    # 1. Verifier was NEVER invoked
    assert len(verifier.verified_task_ids) == 0, "Verifier was invoked despite execution failure!"

    # 2. Events emitted must NOT include VERIFICATION or TASK_COMPLETED
    actual_types = collector.types
    assert EventType.VERIFICATION_STARTED not in actual_types
    assert EventType.VERIFICATION_COMPLETED not in actual_types
    assert EventType.TASK_COMPLETED not in actual_types

    # 3. TASK_FAILED and RUN_FAILED must be emitted
    assert EventType.TASK_FAILED in actual_types
    assert EventType.RUN_FAILED in actual_types

    # 4. Result must unambiguously report failure
    assert result.success is False
    assert result.failed_tasks == ["t1"]
    assert result.completed_tasks == []


def test_regression_verification_failure_never_completes_task_or_run():
    """REGRESSION TEST (Section 19): Verification failure must NEVER emit TASK_COMPLETED

    or RUN_COMPLETED.
    """
    emitter = EventEmitter()
    collector = EventCollector(emitter)

    t1 = Task(id="t1", objective_id="obj_1", description="Strict val desc", title="Failing Verification", type=TaskType.IMPLEMENTATION, validation_requirements=["Rule"])
    planner = MockPlanner(tasks=[t1])
    executor = MockExecutor(handler=lambda t: ExecutionResult(success=True, task_id=t.id))
    verifier = MockVerifier(should_pass=False)
    runtime = AgentRuntime(planner=planner, executor=executor, verifier=verifier, event_emitter=emitter)

    result = runtime.run(objective="Regression test verification failure", objective_id="obj_1")

    actual_types = collector.types
    assert EventType.VERIFICATION_STARTED in actual_types
    assert EventType.VERIFICATION_FAILED in actual_types
    assert EventType.TASK_FAILED in actual_types
    assert EventType.RUN_FAILED in actual_types
    assert EventType.TASK_COMPLETED not in actual_types
    assert EventType.RUN_COMPLETED not in actual_types

    assert result.success is False
    assert result.failed_tasks == ["t1"]


# =============================================================================
# 8. DIRECT TASKGRAPH EXECUTION
# =============================================================================

def test_runtime_executes_custom_task_graph():
    """AgentRuntime can execute an existing pre-built TaskGraph directly."""
    graph = TaskGraph()
    t1 = Task(id="custom_1", objective_id="obj_custom", description="C1 desc", title="Custom 1", type=TaskType.IMPLEMENTATION)
    t2 = Task(id="custom_2", objective_id="obj_custom", description="C2 desc", title="Custom 2", type=TaskType.IMPLEMENTATION, dependencies=["custom_1"])
    graph.add_task(t1)
    graph.add_task(t2)
    graph.finalize()

    executor = MockExecutor()
    runtime = AgentRuntime(executor=executor)

    result = runtime.run(
        objective="Execute custom graph",
        objective_id="obj_custom",
        task_graph=graph,
    )

    assert result.success is True
    assert executor.executed_task_ids == ["custom_1", "custom_2"]
    assert result.completed_tasks == ["custom_1", "custom_2"]


# =============================================================================
# 9. APP.PY THIN INVOCATION INTEGRATION
# =============================================================================

def test_app_delegates_to_agent_runtime():
    """ClaireCoderV1.run() delegates execution directly to AgentRuntime."""
    from clairecoder.app import ClaireCoderV1

    app = ClaireCoderV1()
    assert hasattr(app, "agent_runtime")
    assert isinstance(app.agent_runtime, AgentRuntime)

    session_id = "test_delegation_sess"
    app.create_session(session_id)
    app.submit_objective(session_id, "Test delegation")

    sess = app.engineering_engine.get_session(session_id)
    sess.model_profile = "test-model"

    # Replace agent_runtime with a spy/mock to verify clean delegation
    delegated = []

    def mock_run(**kwargs):
        delegated.append(kwargs)
        return RunResult(
            success=True,
            run_id="spy_run",
            objective_id="spy_obj",
            completed_tasks=["spy_task"],
            failed_tasks=[],
            blocked_tasks=[],
        )

    app.agent_runtime.run = mock_run

    res = app.run(session_id)
    assert len(delegated) == 1
    assert delegated[0]["session_id"] == session_id
    assert res.success is True
    assert res.completed_tasks == ["spy_task"]
