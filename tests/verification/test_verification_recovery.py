"""Tests for Verification as a first-class boundary and bounded recovery (Correction #17).

Validates:
1. Verification as a first-class runtime boundary.
2. Structured VerificationResult model with checks, evidence, and failures.
3. Verifier interface and DefaultVerifier.
4. Real verification evidence consumption (ChangeSet, exit codes, criteria).
5. Task state transitions: READY -> RUNNING -> EXECUTED -> VERIFYING -> SUCCEEDED/FAILED.
6. Controlled, bounded retries and recovery.
7. Structured and persistent failure evidence.
8. ChangeSet integration with verification.
9. Runtime verification and recovery events.
10. RunResult distinction: execution_success, verification_success, recovered_success, final_failure.
11. Regression test against false success bug.
"""

import os
from typing import Any, Dict, List, Optional
import pytest

from clairecoder.workflow.types import Task, TaskState, TaskType, Plan, PlanningLevel
from clairecoder.workflow.task_graph import TaskGraph
from clairecoder.execution.types import (
    ExecutionResult,
    ExecutionResultCategory,
    FailureCategory,
    FailureEvidence,
)
from clairecoder.verification.types import (
    VerificationResult,
    VerificationStatus,
    VerificationCriterion,
    VerificationTestType,
)
from clairecoder.verification.verifier import Verifier, DefaultVerifier
from clairecoder.runtime.agent_runtime import AgentRuntime, RunResult
from clairecoder.runtime.events import EventType, RuntimeEvent
from clairecoder.runtime.emitter import EventEmitter
from clairecoder.changeset.types import ChangeSet, ChangedFile, FileOperation, ChangeSetStatus


# =============================================================================
# TEST DOUBLES
# =============================================================================

class MockPlanner:
    def __init__(self, tasks: List[Task], replan_tasks: Optional[List[Task]] = None):
        self.tasks = tasks
        self.replan_tasks = replan_tasks or []
        self.plan_called = False
        self.replan_called = False

    def build_planning_request(self, *args, **kwargs) -> Any:
        return None

    def create_plan(self, *args, **kwargs) -> Plan:
        if self.replan_called and self.replan_tasks:
            return Plan(
                id="plan_replan",
                workflow_id="wf_1",
                objective="Replanned objective",
                planning_level=PlanningLevel.STRUCTURED,
                task_ids=[t.id for t in self.replan_tasks],
            )
        self.plan_called = True
        return Plan(
            id="plan_1",
            workflow_id="wf_1",
            objective="Test objective",
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=[t.id for t in self.tasks],
        )

    def create_tasks_from_plan(self, plan: Plan, objective_id: str) -> List[Task]:
        if plan.id == "plan_replan":
            return self.replan_tasks
        return self.tasks

    def build_replan_request(self, *args, **kwargs) -> Any:
        self.replan_called = True
        return None


class ScriptedExecutor:
    """Executes tasks according to a scripted sequence of results."""

    def __init__(self, results_per_task: Optional[Dict[str, List[ExecutionResult]]] = None):
        self.results_per_task = results_per_task or {}
        self.call_counts: Dict[str, int] = {}

    def execute(self, task: Task, **kwargs) -> ExecutionResult:
        count = self.call_counts.get(task.id, 0)
        self.call_counts[task.id] = count + 1

        task_results = self.results_per_task.get(task.id, [])
        if task_results and count < len(task_results):
            return task_results[count]
        return ExecutionResult(category=ExecutionResultCategory.SUCCESS, task_id=task.id)

    def __call__(self, task: Task) -> ExecutionResult:
        return self.execute(task)


class ScriptedVerifier(Verifier):
    """Verifies tasks according to a scripted sequence of VerificationResults."""

    def __init__(self, results_per_task: Optional[Dict[str, List[VerificationResult]]] = None):
        self.results_per_task = results_per_task or {}
        self.call_counts: Dict[str, int] = {}
        self.received_changesets: Dict[str, List[Optional[ChangeSet]]] = {}

    def verify(
        self,
        task: Any,
        execution_result: Any,
        changeset: Optional[Any] = None,
        session_id: Optional[str] = None,
        attempt_number: int = 1,
    ) -> VerificationResult:
        task_id = getattr(task, "id", str(task))
        count = self.call_counts.get(task_id, 0)
        self.call_counts[task_id] = count + 1

        if task_id not in self.received_changesets:
            self.received_changesets[task_id] = []
        self.received_changesets[task_id].append(changeset)

        task_results = self.results_per_task.get(task_id, [])
        if task_results and count < len(task_results):
            return task_results[count]

        return VerificationResult(
            task_id=task_id,
            success=True,
            status=VerificationStatus.PASSED,
            checks=["default_scripted_check"],
            evidence=["All tests passed"],
        )


class EventRecorder:
    def __init__(self, emitter: EventEmitter):
        self.events: List[RuntimeEvent] = []
        emitter.subscribe(self._record)

    def _record(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    def by_type(self, event_type: EventType) -> List[RuntimeEvent]:
        return [e for e in self.events if e.event_type == event_type]

    @property
    def types(self) -> List[EventType]:
        return [e.event_type for e in self.events]


# =============================================================================
# 1. VERIFICATION BOUNDARY TESTS
# =============================================================================

def test_successful_execution_and_successful_verification():
    """Execution succeeds and verification succeeds -> task SUCCEEDED, run succeeds."""
    t1 = Task(id="t1", objective_id="obj_1", description="Implement task 1", title="Task 1", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1])
    emitter = EventEmitter()
    recorder = EventRecorder(emitter)

    ver_res = VerificationResult(
        task_id="t1",
        success=True,
        status=VerificationStatus.PASSED,
        checks=["pytest"],
        evidence=["5 passed in 0.2s"],
        failures=[],
    )
    verifier = ScriptedVerifier(results_per_task={"t1": [ver_res]})
    runtime = AgentRuntime(planner=planner, verifier=verifier, event_emitter=emitter)

    res = runtime.run("Implement feature")

    assert res.success is True
    assert res.execution_success is True
    assert res.verification_success is True
    assert res.recovered_success is False
    assert res.final_failure is False
    assert res.completed_tasks == ["t1"]
    assert res.failed_tasks == []
    assert res.blocked_tasks == []
    assert "t1" in res.verification_results
    assert res.verification_results["t1"].success is True

    # Check event order
    types = recorder.types
    assert EventType.VERIFICATION_STARTED in types
    assert EventType.VERIFICATION_PASSED in types
    assert EventType.VERIFICATION_COMPLETED in types
    assert EventType.RUN_COMPLETED in types


def test_successful_execution_and_failed_verification_fails_task_and_run():
    """Execution succeeds but verification fails -> task marked FAILED, run fails."""
    t1 = Task(id="t1", objective_id="obj_1", description="Implement task 1", title="Task 1", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1])
    emitter = EventEmitter()
    recorder = EventRecorder(emitter)

    ver_res = VerificationResult(
        task_id="t1",
        success=False,
        status=VerificationStatus.FAILED,
        checks=["pytest"],
        evidence=["2 tests failed"],
        failures=["test_feature_regression", "test_edge_case"],
    )
    verifier = ScriptedVerifier(results_per_task={"t1": [ver_res]})
    runtime = AgentRuntime(planner=planner, verifier=verifier, event_emitter=emitter)

    res = runtime.run("Implement feature")

    assert res.success is False
    assert res.execution_success is True  # Executor ran fine
    assert res.verification_success is False  # Verification caught defects
    assert res.final_failure is True
    assert res.failed_tasks == ["t1"]
    assert res.completed_tasks == []

    # Check failure events
    assert EventType.VERIFICATION_STARTED in recorder.types
    assert EventType.VERIFICATION_FAILED in recorder.types
    assert EventType.TASK_FAILED in recorder.types
    assert EventType.RUN_FAILED in recorder.types


def test_execution_failure_strictly_prevents_verification():
    """If execution fails, verification must NOT run (monotonic gating)."""
    t1 = Task(id="t1", objective_id="obj_1", description="Implement task 1", title="Task 1", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1])
    emitter = EventEmitter()
    recorder = EventRecorder(emitter)

    executor = ScriptedExecutor(
        results_per_task={
            "t1": [ExecutionResult(category=ExecutionResultCategory.FAILURE, error_message="SyntaxError")]
        }
    )
    verifier = ScriptedVerifier()
    runtime = AgentRuntime(planner=planner, executor=executor, verifier=verifier, event_emitter=emitter)

    res = runtime.run("Implement feature")

    assert res.success is False
    assert res.execution_success is False
    assert res.final_failure is True
    assert verifier.call_counts.get("t1", 0) == 0, "Verifier was invoked despite execution failure!"
    assert EventType.VERIFICATION_STARTED not in recorder.types


# =============================================================================
# 2. VERIFICATION FAILURE EVIDENCE & STRUCTURE
# =============================================================================

def test_verification_failure_evidence_structure_and_persistence():
    """Verification failure evidence must be structured and preserved in TaskGraph."""
    t1 = Task(id="t1", objective_id="obj_1", description="Compute answer", title="Task 1", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1])

    ver_res = VerificationResult(
        task_id="t1",
        success=False,
        status=VerificationStatus.FAILED,
        checks=["pytest", "linter"],
        evidence=["AssertionError: expected 42 got 0"],
        failures=["test_compute"],
        metadata={"run_env": "ci"},
    )
    verifier = ScriptedVerifier(results_per_task={"t1": [ver_res]})
    runtime = AgentRuntime(planner=planner, verifier=verifier)

    res = runtime.run("Compute answer")

    task = res.task_graph.get_task("t1")
    assert task is not None
    assert task.status == TaskState.FAILED
    assert len(task.failure_evidence) > 0

    ev = task.failure_evidence[-1]
    assert isinstance(ev, dict)
    assert ev["kind"] == "verification_failure"
    assert "test_compute" in ev["error"]
    assert "failures" in ev
    assert ev["failures"] == ["test_compute"]
    assert ev["attempt"] == 1


# =============================================================================
# 3. BOUNDED RETRIES & RECOVERY
# =============================================================================

def test_bounded_retry_exhaustion():
    """Task fails repeatedly and exhausts max_retries without endless looping."""
    t1 = Task(id="t1", objective_id="obj_1", description="Retry task", title="Task 1", type=TaskType.IMPLEMENTATION, max_retries=2)
    planner = MockPlanner(tasks=[t1])
    emitter = EventEmitter()
    recorder = EventRecorder(emitter)

    fail_ver = VerificationResult(
        task_id="t1",
        success=False,
        status=VerificationStatus.FAILED,
        failures=["Persistent failure"],
    )
    # Fail 3 times (initial + 2 retries)
    verifier = ScriptedVerifier(results_per_task={"t1": [fail_ver, fail_ver, fail_ver]})
    runtime = AgentRuntime(planner=planner, verifier=verifier, event_emitter=emitter)

    res = runtime.run("Run bounded retry", max_cycles=10, max_replans=0)

    assert res.success is False
    assert res.final_failure is True
    assert verifier.call_counts["t1"] == 3  # Initial (1) + 2 retries = 3 attempts total

    task = res.task_graph.get_task("t1")
    assert task.attempts == 3
    assert task.status == TaskState.FAILED

    # Events emitted
    recovery_starts = recorder.by_type(EventType.RECOVERY_STARTED)
    retry_starts = recorder.by_type(EventType.RETRY_STARTED)
    recovery_fails = recorder.by_type(EventType.RECOVERY_FAILED)

    assert len(recovery_starts) == 2
    assert len(retry_starts) == 2
    assert len(recovery_fails) >= 1


def test_successful_retry_recovery():
    """Task fails verification on attempt 1, passes on attempt 2 -> recovered success."""
    t1 = Task(id="t1", objective_id="obj_1", description="Flaky task", title="Task 1", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1])
    emitter = EventEmitter()
    recorder = EventRecorder(emitter)

    fail_ver = VerificationResult(
        task_id="t1",
        success=False,
        status=VerificationStatus.FAILED,
        failures=["First attempt flaky failure"],
    )
    pass_ver = VerificationResult(
        task_id="t1",
        success=True,
        status=VerificationStatus.PASSED,
        checks=["pytest"],
        evidence=["All passed on retry"],
    )
    verifier = ScriptedVerifier(results_per_task={"t1": [fail_ver, pass_ver]})
    runtime = AgentRuntime(planner=planner, verifier=verifier, event_emitter=emitter, max_task_retries=1)

    res = runtime.run("Run with retry")

    assert res.success is True
    assert res.recovered_success is True
    assert res.execution_success is True
    assert res.verification_success is True
    assert res.final_failure is False
    assert res.completed_tasks == ["t1"]
    assert verifier.call_counts["t1"] == 2

    # Events
    assert len(recorder.by_type(EventType.RECOVERY_STARTED)) == 1
    assert len(recorder.by_type(EventType.RETRY_STARTED)) == 1
    assert len(recorder.by_type(EventType.RECOVERY_COMPLETED)) >= 1
    assert EventType.RUN_COMPLETED in recorder.types


def test_failed_retry_terminal_blocks_downstream():
    """Task A fails retries -> Task B depending on A remains BLOCKED."""
    t1 = Task(id="t1", objective_id="obj_1", description="Dep task 1", title="Task 1", type=TaskType.IMPLEMENTATION, max_retries=1)
    t2 = Task(id="t2", objective_id="obj_1", description="Dep task 2", title="Task 2", type=TaskType.IMPLEMENTATION, dependencies=["t1"])

    graph = TaskGraph()
    graph.add_task(t1)
    graph.add_task(t2)
    graph.finalize()

    fail_ver = VerificationResult(task_id="t1", success=False, status=VerificationStatus.FAILED, failures=["Fail"])
    verifier = ScriptedVerifier(results_per_task={"t1": [fail_ver, fail_ver]})
    runtime = AgentRuntime(verifier=verifier)

    res = runtime.run("Run pipeline", task_graph=graph)

    assert res.success is False
    assert res.final_failure is True
    assert res.failed_tasks == ["t1"]
    assert res.blocked_tasks == ["t2"]
    assert res.completed_tasks == []
    assert verifier.call_counts.get("t2", 0) == 0, "Downstream task t2 was executed despite t1 failure!"


# =============================================================================
# 4. REPLANNING AFTER RECOVERY EXHAUSTION
# =============================================================================

def test_replan_after_recovery_exhaustion():
    """When task retries are exhausted, replan triggers and recovers the run."""
    t1 = Task(id="t1", objective_id="obj_1", description="Initial plan task", title="Initial Task", type=TaskType.IMPLEMENTATION, max_retries=0)
    t_replan = Task(id="t_replan", objective_id="obj_1", description="Replanned task", title="Replanned Task", type=TaskType.IMPLEMENTATION)

    planner = MockPlanner(tasks=[t1], replan_tasks=[t_replan])
    emitter = EventEmitter()
    recorder = EventRecorder(emitter)

    fail_ver = VerificationResult(task_id="t1", success=False, status=VerificationStatus.FAILED, failures=["Flaw in initial approach"])
    pass_ver = VerificationResult(task_id="t_replan", success=True, status=VerificationStatus.PASSED)

    verifier = ScriptedVerifier(results_per_task={"t1": [fail_ver], "t_replan": [pass_ver]})
    runtime = AgentRuntime(planner=planner, verifier=verifier, event_emitter=emitter)

    res = runtime.run("Objective needing replan", max_replans=1)

    assert res.success is True
    assert res.recovered_success is True
    assert res.final_failure is False
    assert res.completed_tasks == ["t_replan"]

    assert EventType.REPLAN_STARTED in recorder.types
    replan_events = recorder.by_type(EventType.REPLAN_STARTED)
    assert len(replan_events) == 1
    assert EventType.RECOVERY_COMPLETED in recorder.types


# =============================================================================
# 5. CHANGESET INTEGRATION
# =============================================================================

def test_changeset_information_reaches_verification_and_evidence():
    """Changeset captured during task execution must be passed to verifier and recorded in failure evidence."""
    t1 = Task(id="t1", objective_id="obj_1", description="Create file task", title="Task 1", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1])

    # Custom executor that writes a file to workspace to produce an actual changeset
    test_file_path = "changeset_test_file.txt"
    try:
        def executor_fn(task: Task) -> ExecutionResult:
            with open(test_file_path, "w", encoding="utf-8") as f:
                f.write("Line 1\nLine 2\n")
            return ExecutionResult(success=True, task_id=task.id)

        fail_ver = VerificationResult(
            task_id="t1",
            success=False,
            status=VerificationStatus.FAILED,
            failures=["File content does not match spec"],
        )
        verifier = ScriptedVerifier(results_per_task={"t1": [fail_ver]})
        runtime = AgentRuntime(planner=planner, executor=executor_fn, verifier=verifier, workspace_root=".")

        res = runtime.run("Create file")

        # 1. Verifier received the changeset
        assert verifier.received_changesets["t1"][0] is not None
        cs = verifier.received_changesets["t1"][0]
        assert any(test_file_path in cf.path for cf in cs.files)

        # 2. Failure evidence includes changeset_id and affected_files
        task = res.task_graph.get_task("t1")
        assert len(task.failure_evidence) > 0
        ev = task.failure_evidence[-1]
        assert ev["changeset_id"] == cs.id
        assert any(test_file_path in p for p in ev["affected_files"])

    finally:
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


# =============================================================================
# 6. RUNTIME VERIFICATION & RECOVERY EVENTS
# =============================================================================

def test_runtime_events_verification_and_recovery_lifecycle():
    """Verify exact sequence of structured runtime events across verification & recovery."""
    t1 = Task(id="t1", objective_id="obj_1", description="Lifecycle task", title="Task 1", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1])
    emitter = EventEmitter()
    recorder = EventRecorder(emitter)

    fail_ver = VerificationResult(task_id="t1", success=False, status=VerificationStatus.FAILED, failures=["Broken"])
    pass_ver = VerificationResult(task_id="t1", success=True, status=VerificationStatus.PASSED, checks=["fixed"])
    verifier = ScriptedVerifier(results_per_task={"t1": [fail_ver, pass_ver]})
    runtime = AgentRuntime(planner=planner, verifier=verifier, event_emitter=emitter, max_task_retries=1)

    res = runtime.run("Lifecycle event test")

    assert res.success is True

    # Check payload structure on events
    ver_started = recorder.by_type(EventType.VERIFICATION_STARTED)
    assert len(ver_started) == 2
    assert ver_started[0].task_id == "t1"

    ver_failed = recorder.by_type(EventType.VERIFICATION_FAILED)
    assert len(ver_failed) == 1
    assert ver_failed[0].payload["passed"] is False
    assert "Broken" in ver_failed[0].payload["failures"]

    recovery_started = recorder.by_type(EventType.RECOVERY_STARTED)
    assert len(recovery_started) == 1
    assert recovery_started[0].payload["recovery_type"] == "retry"

    ver_passed = recorder.by_type(EventType.VERIFICATION_PASSED)
    assert len(ver_passed) == 1
    assert ver_passed[0].payload["passed"] is True

    recovery_completed = recorder.by_type(EventType.RECOVERY_COMPLETED)
    assert len(recovery_completed) >= 1


# =============================================================================
# 7. REGRESSION TEST: FALSE SUCCESS BUG
# =============================================================================

def test_regression_false_success_bug_eliminated():
    """A run must NEVER report success solely because executor completed without exception."""
    t1 = Task(id="t1", objective_id="obj_1", description="Check false success", title="Task 1", type=TaskType.IMPLEMENTATION)
    planner = MockPlanner(tasks=[t1])

    # Executor returns success
    executor = ScriptedExecutor(
        results_per_task={"t1": [ExecutionResult(category=ExecutionResultCategory.SUCCESS, task_id="t1")]}
    )
    # Verifier explicitly rejects task
    verifier = ScriptedVerifier(
        results_per_task={
            "t1": [
                VerificationResult(
                    task_id="t1",
                    success=False,
                    status=VerificationStatus.FAILED,
                    failures=["Unit tests failed 3/10 assertions"],
                )
            ]
        }
    )

    runtime = AgentRuntime(planner=planner, executor=executor, verifier=verifier)
    res = runtime.run("Ensure false success is blocked", max_replans=0)

    # Strict assertion: Executor succeeded, but RunResult MUST report failure
    assert res.execution_success is True
    assert res.verification_success is False
    assert res.success is False
    assert res.final_failure is True
    assert "t1" in res.failed_tasks
    assert "t1" not in res.completed_tasks


# =============================================================================
# 8. TASK STATE TRANSITIONS (READY -> RUNNING -> EXECUTED -> VERIFYING -> SUCCEEDED)
# =============================================================================

def test_task_state_transitions_executed_and_verifying():
    """TaskGraph transitions through EXECUTED and VERIFYING before terminal states."""
    graph = TaskGraph()
    t1 = Task(id="t1", objective_id="obj_1", description="Transition task", title="Task 1", type=TaskType.IMPLEMENTATION)
    graph.add_task(t1)
    graph.finalize()

    assert t1.status == TaskState.READY

    graph.mark_started("t1")
    assert t1.status == TaskState.RUNNING

    graph.mark_executed("t1")
    assert t1.status == TaskState.EXECUTED

    graph.mark_verifying("t1")
    assert t1.status == TaskState.VERIFYING

    graph.mark_completed("t1")
    assert t1.status == TaskState.SUCCEEDED


def test_task_state_transitions_to_failed_from_verifying():
    """TaskGraph allows failing directly from VERIFYING."""
    graph = TaskGraph()
    t1 = Task(id="t1", objective_id="obj_1", description="Failing transition task", title="Task 1", type=TaskType.IMPLEMENTATION)
    graph.add_task(t1)
    graph.finalize()

    graph.mark_started("t1")
    graph.mark_executed("t1")
    graph.mark_verifying("t1")
    graph.mark_failed("t1", evidence={"error": "Verification failed"})

    assert t1.status == TaskState.FAILED
    assert len(t1.failure_evidence) == 1


# =============================================================================
# 9. DEFAULT VERIFIER & REAL EVIDENCE TESTS
# =============================================================================

def test_default_verifier_consumes_exit_codes_and_criteria():
    """DefaultVerifier rejects non-zero exit codes and executes criteria."""
    verifier = DefaultVerifier()

    # 1. Non-zero exit code
    t1 = Task(id="t1", objective_id="obj_1", description="Command task", title="T1")
    exec_fail_exit = ExecutionResult(success=True, task_id="t1")
    exec_fail_exit.exit_code = 127

    res = verifier.verify(t1, exec_fail_exit)
    assert res.success is False
    assert res.status == VerificationStatus.FAILED
    assert any("127" in f for f in res.failures)

    # 2. Test failures field
    exec_test_fail = ExecutionResult(success=True, task_id="t1")
    exec_test_fail.test_failures = ["test_auth_timeout"]
    res2 = verifier.verify(t1, exec_test_fail)
    assert res2.success is False
    assert "test_auth_timeout" in res2.failures


def test_default_verifier_unverified_representation_when_no_criteria():
    """When no criteria are specified, DefaultVerifier marks UNVERIFIED explicitly."""
    verifier = DefaultVerifier()
    t1 = Task(id="t1", objective_id="obj_1", description="Task without criteria", title="T1", type=TaskType.IMPLEMENTATION)
    exec_ok = ExecutionResult(success=True, task_id="t1")

    res = verifier.verify(t1, exec_ok)
    assert res.success is True
    assert res.status == "unverified"
    assert "no_criteria_provided" in res.checks
    assert res.metadata.get("unverified") is True
