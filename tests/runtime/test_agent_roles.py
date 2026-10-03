"""Tests for Agent Roles / Subagent architecture (Correction #18).

Covers:
1.  Role enum definitions and values
2.  RoleRegistry registration and resolution
3.  RoleRegistry error handling for missing roles
4.  PlannerRole delegates to existing Planner
5.  ImplementerRole delegates to existing executor
6.  VerifierRole delegates to existing Verifier
7.  RecoveryRole preserves bounded recovery decisions
8.  RoleContext contains only expected information (bounded)
9.  Role events contain correlation data (ROLE_STARTED/COMPLETED/FAILED)
10. Role failure becomes structured evidence (not false success)
11. Injected fake role works through AgentRuntime
12. AgentRuntime remains single orchestration authority
13. Existing execution/verification/recovery behavior remains compatible
14. RoleResult structured outcome
15. RecoveryDecision exhaustion (retry -> replan -> fail)
"""

import pytest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from clairecoder.runtime.roles import (
    Role,
    RoleContext,
    RoleResult,
    AgentRole,
    PlannerRole,
    ImplementerRole,
    VerifierRole,
    RecoveryRole,
    RecoveryDecision,
    RoleRegistry,
)
from clairecoder.runtime.events import EventType, RuntimeEvent
from clairecoder.runtime.emitter import EventEmitter
from clairecoder.runtime.agent_runtime import AgentRuntime, RunResult
from clairecoder.workflow.types import (
    Plan,
    PlanningLevel,
    Task,
    TaskState,
    TaskType,
)
from clairecoder.workflow.task_graph import TaskGraph
from clairecoder.execution.types import ExecutionResult
from clairecoder.verification.types import VerificationResult, VerificationStatus


# =============================================================================
# Helpers
# =============================================================================

class EventCollector:
    """Collects emitted RuntimeEvents for assertion."""

    def __init__(self) -> None:
        self.events: List[RuntimeEvent] = []

    def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    def of_type(self, et: EventType) -> List[RuntimeEvent]:
        return [e for e in self.events if e.event_type == et]


class FakeRole(AgentRole):
    """A test-injectable fake role."""

    def __init__(self, role: Role, succeed: bool = True, output: Any = None, error: str = "") -> None:
        self._role = role
        self._succeed = succeed
        self._output = output
        self._error = error
        self.called = False
        self.last_context: Optional[RoleContext] = None

    @property
    def name(self) -> Role:
        return self._role

    @property
    def description(self) -> str:
        return f"Fake {self._role.value} role for testing"

    def execute(self, context: RoleContext) -> RoleResult:
        self.called = True
        self.last_context = context
        if not self._succeed:
            return RoleResult(
                role=self._role,
                success=False,
                error=self._error or "Fake failure",
            )
        return RoleResult(
            role=self._role,
            success=True,
            output=self._output or "fake_output",
        )


class CrashingRole(AgentRole):
    """A role that raises an exception to test failure isolation."""

    @property
    def name(self) -> Role:
        return Role.VERIFIER

    @property
    def description(self) -> str:
        return "Role that crashes"

    def execute(self, context: RoleContext) -> RoleResult:
        raise RuntimeError("Simulated crash inside role")


class FakePlanner:
    """Minimal planner stub for PlannerRole testing."""

    def __init__(self) -> None:
        self.created = False

    def create_plan(self, workflow_id="", objective="", planning_level=None, model_response=None):
        self.created = True
        return Plan(
            id="plan_test",
            workflow_id=workflow_id,
            objective=objective,
            planning_level=planning_level or PlanningLevel.STRUCTURED,
            task_ids=["t1"],
        )

    def create_tasks_from_plan(self, plan, objective_id):
        return [
            Task(
                id="t1",
                objective_id=objective_id,
                title="Test task",
                description="Test task description",
                type=TaskType.IMPLEMENTATION,
            )
        ]


class FakeExecutor:
    """Minimal executor stub for ImplementerRole testing."""

    def __init__(self, succeed: bool = True) -> None:
        self._succeed = succeed
        self.executed = False

    def execute(self, task, session_id=None):
        self.executed = True
        return ExecutionResult(success=self._succeed, task_id=getattr(task, "id", "t1"))


class FakeVerifier:
    """Minimal verifier stub for VerifierRole testing."""

    def __init__(self, passed: bool = True) -> None:
        self._passed = passed
        self.verified = False

    def verify(self, task, execution_result, changeset=None):
        self.verified = True
        return VerificationResult(
            task_id=getattr(task, "id", "t1"),
            success=self._passed,
            status=VerificationStatus.PASSED if self._passed else VerificationStatus.FAILED,
            checks=["test_check"],
            failures=[] if self._passed else ["test_failure"],
        )


# =============================================================================
# 1. Role Enum Definitions
# =============================================================================

def test_role_enum_values():
    """All four required roles exist with correct string values."""
    assert Role.PLANNER.value == "planner"
    assert Role.IMPLEMENTER.value == "implementer"
    assert Role.VERIFIER.value == "verifier"
    assert Role.RECOVERY.value == "recovery"
    assert len(Role) == 4


# =============================================================================
# 2. RoleRegistry Registration and Resolution
# =============================================================================

def test_registry_register_and_resolve():
    """Roles can be registered and resolved."""
    registry = RoleRegistry()
    fake = FakeRole(Role.PLANNER)
    registry.register(Role.PLANNER, fake)
    assert registry.has(Role.PLANNER)
    resolved = registry.resolve(Role.PLANNER)
    assert resolved is fake


def test_registry_replace_registration():
    """Registering a second implementation replaces the first."""
    registry = RoleRegistry()
    first = FakeRole(Role.VERIFIER)
    second = FakeRole(Role.VERIFIER, output="replaced")
    registry.register(Role.VERIFIER, first)
    registry.register(Role.VERIFIER, second)
    assert registry.resolve(Role.VERIFIER) is second


def test_registry_registered_roles():
    """registered_roles lists all registered roles."""
    registry = RoleRegistry()
    registry.register(Role.PLANNER, FakeRole(Role.PLANNER))
    registry.register(Role.RECOVERY, FakeRole(Role.RECOVERY))
    assert set(registry.registered_roles) == {Role.PLANNER, Role.RECOVERY}


def test_registry_unregister():
    """Roles can be unregistered."""
    registry = RoleRegistry()
    registry.register(Role.PLANNER, FakeRole(Role.PLANNER))
    registry.unregister(Role.PLANNER)
    assert not registry.has(Role.PLANNER)


def test_registry_to_dict():
    """Registry serializes to diagnostic dict."""
    registry = RoleRegistry()
    registry.register(Role.PLANNER, FakeRole(Role.PLANNER))
    d = registry.to_dict()
    assert d["planner"] == "FakeRole"


# =============================================================================
# 3. Missing Role Handling
# =============================================================================

def test_registry_resolve_missing_raises():
    """Resolving unregistered role raises KeyError."""
    registry = RoleRegistry()
    with pytest.raises(KeyError, match="verifier"):
        registry.resolve(Role.VERIFIER)


def test_registry_register_type_errors():
    """Registry rejects invalid types."""
    registry = RoleRegistry()
    with pytest.raises(TypeError, match="Role enum"):
        registry.register("not_a_role", FakeRole(Role.PLANNER))
    with pytest.raises(TypeError, match="AgentRole"):
        registry.register(Role.PLANNER, "not_a_role")


# =============================================================================
# 4. PlannerRole Delegates to Existing Planner
# =============================================================================

def test_planner_role_delegates():
    """PlannerRole.execute() calls the existing Planner."""
    planner = FakePlanner()
    role = PlannerRole(planner)
    assert role.name == Role.PLANNER
    assert "Planner" in role.description

    ctx = RoleContext(
        run_id="r1",
        objective="build feature X",
        objective_id="obj1",
        session_id="s1",
        metadata={"workflow_id": "wf_s1"},
    )
    result = role.execute(ctx)
    assert result.success
    assert result.role == Role.PLANNER
    assert planner.created
    assert result.output["plan"].id == "plan_test"
    assert len(result.output["tasks"]) == 1


def test_planner_role_failure():
    """PlannerRole returns structured failure on planner exception."""
    class BadPlanner:
        def create_plan(self, **kw):
            raise ValueError("bad objective")

    role = PlannerRole(BadPlanner())
    ctx = RoleContext(run_id="r1", objective="x", objective_id="o1")
    result = role.execute(ctx)
    assert not result.success
    assert "bad objective" in result.error
    assert result.evidence["exception_type"] == "ValueError"


# =============================================================================
# 5. ImplementerRole Delegates to Existing Executor
# =============================================================================

def test_implementer_role_delegates():
    """ImplementerRole.execute() calls the existing executor."""
    executor = FakeExecutor(succeed=True)
    role = ImplementerRole(executor)
    assert role.name == Role.IMPLEMENTER

    task = Task(id="t1", objective_id="o1", title="test", description="test", type=TaskType.IMPLEMENTATION)
    ctx = RoleContext(run_id="r1", objective="x", task=task, task_id="t1")
    result = role.execute(ctx)
    assert result.success
    assert executor.executed


def test_implementer_role_no_task():
    """ImplementerRole returns failure if no task in context."""
    role = ImplementerRole(FakeExecutor())
    ctx = RoleContext(run_id="r1", objective="x")
    result = role.execute(ctx)
    assert not result.success
    assert "No task" in result.error


# =============================================================================
# 6. VerifierRole Delegates to Existing Verifier
# =============================================================================

def test_verifier_role_delegates():
    """VerifierRole.execute() calls the existing Verifier."""
    verifier = FakeVerifier(passed=True)
    role = VerifierRole(verifier)
    assert role.name == Role.VERIFIER

    task = Task(id="t1", objective_id="o1", title="test", description="test", type=TaskType.IMPLEMENTATION)
    exec_result = ExecutionResult(success=True, task_id="t1")
    ctx = RoleContext(run_id="r1", objective="x", task=task, execution_result=exec_result, task_id="t1")
    result = role.execute(ctx)
    assert result.success
    assert verifier.verified
    assert isinstance(result.output, VerificationResult)


def test_verifier_role_failure():
    """VerifierRole returns failure when verification fails."""
    verifier = FakeVerifier(passed=False)
    role = VerifierRole(verifier)
    task = Task(id="t1", objective_id="o1", title="test", description="test", type=TaskType.IMPLEMENTATION)
    exec_result = ExecutionResult(success=True, task_id="t1")
    ctx = RoleContext(run_id="r1", objective="x", task=task, execution_result=exec_result, task_id="t1")
    result = role.execute(ctx)
    assert not result.success
    assert result.metadata["verification_passed"] is False


def test_verifier_role_missing_context():
    """VerifierRole returns failure if task or exec_result is missing."""
    role = VerifierRole(FakeVerifier())
    ctx = RoleContext(run_id="r1", objective="x")
    result = role.execute(ctx)
    assert not result.success
    assert "required" in result.error


# =============================================================================
# 7. RecoveryRole Preserves Bounded Recovery
# =============================================================================

def test_recovery_role_retry():
    """RecoveryRole recommends retry when retries remain."""
    role = RecoveryRole(max_task_retries=3)
    task = Task(id="t1", objective_id="o1", title="test", description="test", type=TaskType.IMPLEMENTATION)
    ctx = RoleContext(run_id="r1", objective="x", task=task, attempt=1)
    result = role.execute(ctx)
    assert result.success
    assert result.output == RecoveryDecision.RETRY


def test_recovery_role_replan():
    """RecoveryRole recommends replan when retries are exhausted."""
    role = RecoveryRole(max_task_retries=1, max_replans=2, can_replan=True)
    task = Task(id="t1", objective_id="o1", title="test", description="test", type=TaskType.IMPLEMENTATION)
    ctx = RoleContext(run_id="r1", objective="x", task=task, attempt=2, metadata={"replan_count": 0})
    result = role.execute(ctx)
    assert result.success
    assert result.output == RecoveryDecision.REPLAN


def test_recovery_role_fail():
    """RecoveryRole recommends fail when all strategies exhausted."""
    role = RecoveryRole(max_task_retries=0, max_replans=1, can_replan=True)
    ctx = RoleContext(run_id="r1", objective="x", attempt=1, metadata={"replan_count": 1})
    result = role.execute(ctx)
    assert result.success
    assert result.output == RecoveryDecision.FAIL


def test_recovery_role_no_unlimited_retries():
    """RecoveryRole cannot execute unlimited retries."""
    role = RecoveryRole(max_task_retries=2)
    task = Task(id="t1", objective_id="o1", title="test", description="test", type=TaskType.IMPLEMENTATION)
    # attempt=3 means 2 retries already done (attempt 1 original + retry 2 + retry 3)
    ctx = RoleContext(run_id="r1", objective="x", task=task, attempt=3)
    result = role.execute(ctx)
    # Should NOT recommend retry — budget exhausted
    assert result.output != RecoveryDecision.RETRY


def test_recovery_decision_exhaustion_sequence():
    """Full exhaustion: retry -> replan -> fail."""
    role = RecoveryRole(max_task_retries=1, max_replans=1, can_replan=True)
    task = Task(id="t1", objective_id="o1", title="test", description="test", type=TaskType.IMPLEMENTATION)

    # Attempt 1: should retry
    ctx1 = RoleContext(run_id="r1", objective="x", task=task, attempt=1, metadata={"replan_count": 0})
    r1 = role.execute(ctx1)
    assert r1.output == RecoveryDecision.RETRY

    # Attempt 2: retries exhausted, should replan
    ctx2 = RoleContext(run_id="r1", objective="x", task=task, attempt=2, metadata={"replan_count": 0})
    r2 = role.execute(ctx2)
    assert r2.output == RecoveryDecision.REPLAN

    # After 1 replan, should fail
    ctx3 = RoleContext(run_id="r1", objective="x", task=task, attempt=2, metadata={"replan_count": 1})
    r3 = role.execute(ctx3)
    assert r3.output == RecoveryDecision.FAIL


# =============================================================================
# 8. RoleContext Bounded Information
# =============================================================================

def test_role_context_bounded():
    """RoleContext carries only specified fields, not runtime internals."""
    ctx = RoleContext(
        run_id="r1",
        objective="build X",
        objective_id="o1",
        session_id="s1",
        task_id="t1",
        attempt=2,
    )
    assert ctx.run_id == "r1"
    assert ctx.objective == "build X"
    assert ctx.task_id == "t1"
    assert ctx.attempt == 2
    # Should NOT have runtime, event_emitter, task_graph, etc.
    assert not hasattr(ctx, "runtime")
    assert not hasattr(ctx, "event_emitter")
    assert not hasattr(ctx, "task_graph")


def test_role_context_to_dict():
    """RoleContext serializes to dict with expected keys."""
    ctx = RoleContext(run_id="r1", objective="x", objective_id="o1", session_id="s1", task_id="t1", attempt=3)
    d = ctx.to_dict()
    assert d["run_id"] == "r1"
    assert d["task_id"] == "t1"
    assert d["attempt"] == 3
    assert "objective" in d


# =============================================================================
# 9. Role Events Contain Correlation Data
# =============================================================================

def test_role_events_correlation():
    """invoke_role emits ROLE_STARTED and ROLE_COMPLETED/FAILED with correlation."""
    emitter = EventEmitter()
    collector = EventCollector()
    emitter.subscribe(collector)

    registry = RoleRegistry()
    registry.register(Role.PLANNER, FakeRole(Role.PLANNER))

    runtime = AgentRuntime(event_emitter=emitter, role_registry=registry)
    ctx = RoleContext(run_id="r1", objective="x", objective_id="o1", task_id="t1")
    result = runtime.invoke_role(Role.PLANNER, ctx)
    assert result.success

    started = collector.of_type(EventType.ROLE_STARTED)
    assert len(started) == 1
    assert started[0].run_id == "r1"
    assert started[0].task_id == "t1"
    assert started[0].payload["role"] == "planner"

    completed = collector.of_type(EventType.ROLE_COMPLETED)
    assert len(completed) == 1
    assert completed[0].payload["role"] == "planner"
    assert completed[0].payload["success"] is True


def test_role_failure_emits_role_failed():
    """A failing role emits ROLE_FAILED with structured error payload."""
    emitter = EventEmitter()
    collector = EventCollector()
    emitter.subscribe(collector)

    registry = RoleRegistry()
    registry.register(Role.VERIFIER, FakeRole(Role.VERIFIER, succeed=False, error="bad check"))

    runtime = AgentRuntime(event_emitter=emitter, role_registry=registry)
    ctx = RoleContext(run_id="r2", objective="y", objective_id="o2")
    result = runtime.invoke_role(Role.VERIFIER, ctx)
    assert not result.success

    failed = collector.of_type(EventType.ROLE_FAILED)
    assert len(failed) == 1
    assert failed[0].payload["role"] == "verifier"
    assert failed[0].payload["error"] == "bad check"


# =============================================================================
# 10. Role Failure Becomes Structured Evidence (No False Success)
# =============================================================================

def test_role_failure_is_structured_evidence():
    """Role failure produces RoleResult with error, not exception propagation."""
    registry = RoleRegistry()
    registry.register(Role.VERIFIER, CrashingRole())

    emitter = EventEmitter()
    collector = EventCollector()
    emitter.subscribe(collector)

    runtime = AgentRuntime(event_emitter=emitter, role_registry=registry)
    ctx = RoleContext(run_id="r1", objective="x", objective_id="o1")
    result = runtime.invoke_role(Role.VERIFIER, ctx)

    # Must NOT have raised — failure is structured
    assert not result.success
    assert "Simulated crash" in result.error
    assert result.evidence["exception_type"] == "RuntimeError"

    # Must have emitted ROLE_FAILED, not ROLE_COMPLETED
    assert len(collector.of_type(EventType.ROLE_COMPLETED)) == 0
    assert len(collector.of_type(EventType.ROLE_FAILED)) == 1


def test_missing_role_returns_failure():
    """Invoking an unregistered role returns structured failure."""
    registry = RoleRegistry()
    runtime = AgentRuntime(event_emitter=EventEmitter(), role_registry=registry)
    ctx = RoleContext(run_id="r1", objective="x", objective_id="o1")
    result = runtime.invoke_role(Role.IMPLEMENTER, ctx)
    assert not result.success
    assert "implementer" in result.error.lower()


# =============================================================================
# 11. Injected Fake Role Works Through AgentRuntime
# =============================================================================

def test_injected_fake_role():
    """A test-injected fake role works through AgentRuntime.invoke_role()."""
    emitter = EventEmitter()
    collector = EventCollector()
    emitter.subscribe(collector)

    fake = FakeRole(Role.IMPLEMENTER, output={"result": "custom"})
    registry = RoleRegistry()
    registry.register(Role.IMPLEMENTER, fake)

    runtime = AgentRuntime(event_emitter=emitter, role_registry=registry)
    ctx = RoleContext(run_id="r1", objective="x", objective_id="o1", task_id="t1")
    result = runtime.invoke_role(Role.IMPLEMENTER, ctx)

    assert result.success
    assert fake.called
    assert fake.last_context is ctx
    assert result.output == {"result": "custom"}

    # Events were emitted
    assert len(collector.of_type(EventType.ROLE_STARTED)) == 1
    assert len(collector.of_type(EventType.ROLE_COMPLETED)) == 1


# =============================================================================
# 12. AgentRuntime Remains Single Orchestration Authority
# =============================================================================

def test_runtime_remains_orchestration_authority():
    """AgentRuntime.run() still works with role_registry present.

    The runtime is the single owner of run lifecycle and state transitions.
    Roles are coordinated by the runtime, not the other way around.
    """
    emitter = EventEmitter()
    collector = EventCollector()
    emitter.subscribe(collector)

    executor = FakeExecutor(succeed=True)
    runtime = AgentRuntime(
        executor=executor,
        event_emitter=emitter,
    )

    # Runtime has a default registry
    assert runtime.role_registry is not None
    assert runtime.role_registry.has(Role.PLANNER)
    assert runtime.role_registry.has(Role.RECOVERY)
    # IMPLEMENTER registered because executor was provided
    assert runtime.role_registry.has(Role.IMPLEMENTER)

    # Run still works
    result = runtime.run("Test objective", run_id="r1", objective_id="o1")
    assert isinstance(result, RunResult)

    # RUN_STARTED and RUN_COMPLETED/RUN_FAILED must have been emitted
    run_events = collector.of_type(EventType.RUN_STARTED) + collector.of_type(EventType.RUN_COMPLETED) + collector.of_type(EventType.RUN_FAILED)
    assert len(run_events) >= 2  # at least started + completed/failed


# =============================================================================
# 13. Existing Behavior Remains Compatible
# =============================================================================

def test_existing_execution_behavior_compatible():
    """Existing AgentRuntime.run() behavior is unchanged by role introduction."""
    executor = FakeExecutor(succeed=True)
    emitter = EventEmitter()
    collector = EventCollector()
    emitter.subscribe(collector)

    # Build runtime WITHOUT explicit role_registry — defaults should work
    runtime = AgentRuntime(
        executor=executor,
        event_emitter=emitter,
    )

    graph = TaskGraph(event_emitter=emitter, run_id="r1")
    task = Task(
        id="t1",
        objective_id="o1",
        title="Existing task",
        description="Should work as before",
        type=TaskType.IMPLEMENTATION,
    )
    graph.add_task(task)
    graph.finalize()

    result = runtime.run(
        "Test objective",
        task_graph=graph,
        run_id="r1",
        objective_id="o1",
    )
    assert result.success
    assert "t1" in result.completed_tasks
    assert executor.executed


def test_existing_verification_behavior_compatible():
    """Verification lifecycle works correctly with roles present."""
    emitter = EventEmitter()
    collector = EventCollector()
    emitter.subscribe(collector)

    executor = FakeExecutor(succeed=True)
    verifier = FakeVerifier(passed=True)

    runtime = AgentRuntime(
        executor=executor,
        verifier=verifier,
        event_emitter=emitter,
    )

    graph = TaskGraph(event_emitter=emitter, run_id="r1")
    task = Task(
        id="t1",
        objective_id="o1",
        title="test",
        description="test",
        type=TaskType.IMPLEMENTATION,
    )
    graph.add_task(task)
    graph.finalize()

    result = runtime.run(
        "Test verification",
        task_graph=graph,
        run_id="r1",
        objective_id="o1",
    )
    assert result.success
    assert verifier.verified


# =============================================================================
# 14. RoleResult Structured Outcome
# =============================================================================

def test_role_result_to_dict():
    """RoleResult serializes cleanly."""
    r = RoleResult(
        role=Role.PLANNER,
        success=True,
        metadata={"plan_id": "p1"},
    )
    d = r.to_dict()
    assert d["role"] == "planner"
    assert d["success"] is True
    assert d["metadata"]["plan_id"] == "p1"


def test_role_result_failure_to_dict():
    """Failed RoleResult includes error in dict."""
    r = RoleResult(
        role=Role.VERIFIER,
        success=False,
        error="check failed",
        evidence={"test": 1},
    )
    d = r.to_dict()
    assert d["success"] is False
    assert d["error"] == "check failed"
    assert d["evidence"]["test"] == 1


# =============================================================================
# 15. Default Registry Auto-Build
# =============================================================================

def test_default_registry_auto_builds():
    """AgentRuntime builds a default registry from supplied subsystems."""
    executor = FakeExecutor()
    verifier = FakeVerifier()
    runtime = AgentRuntime(
        executor=executor,
        verifier=verifier,
        max_task_retries=3,
    )

    reg = runtime.role_registry
    assert reg.has(Role.PLANNER)      # Planner is always created by default
    assert reg.has(Role.IMPLEMENTER)  # executor was provided
    assert reg.has(Role.VERIFIER)     # verifier was provided
    assert reg.has(Role.RECOVERY)     # always registered


def test_default_registry_without_optional_subsystems():
    """Default registry omits roles when optional subsystems aren't provided."""
    runtime = AgentRuntime()  # no executor, no verifier
    reg = runtime.role_registry
    assert reg.has(Role.PLANNER)
    assert not reg.has(Role.IMPLEMENTER)
    assert not reg.has(Role.VERIFIER)
    assert reg.has(Role.RECOVERY)
