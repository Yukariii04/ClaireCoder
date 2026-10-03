"""Agent Role / Subagent architecture (Correction #18).

Introduces bounded role abstraction for separated reasoning responsibilities
without creating a second runtime, planner, task system, or event system.

Architecture:
    AgentRuntime (single orchestration authority)
        |
        +-- PlannerRole      -> existing Planner
        +-- ImplementerRole  -> existing executor
        +-- VerifierRole     -> existing Verifier
        +-- RecoveryRole     -> existing recovery logic
        |
        +-- TaskGraph
        +-- ChangeSetStore
        +-- RuntimeEvent stream

Design decisions:
- Role is a string enum (consistent with EventType, TaskState, etc.)
- RoleContext is a bounded, read-only-by-convention context object
  containing only the information a role needs — never the full runtime state.
- AgentRole is a small ABC defining the execute() boundary.
- Concrete roles delegate to existing subsystem components (Planner, Verifier, etc.)
  without duplicating them.
- RoleRegistry provides registration, resolution, and injection.
- RoleResult is a structured outcome wrapper for role execution.
- All role failures are caught and converted to structured RoleResult failures.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# ROLE ENUM (Section 1)
# =============================================================================

class Role(str, Enum):
    """Architectural responsibilities within the agent runtime."""

    PLANNER = "planner"
    IMPLEMENTER = "implementer"
    VERIFIER = "verifier"
    RECOVERY = "recovery"


# =============================================================================
# ROLE CONTEXT (Section 3)
# =============================================================================

@dataclass
class RoleContext:
    """Bounded context object for role execution.

    Contains only the information a role needs to execute.
    Does NOT expose the full AgentRuntime state or mutable internals.
    """

    run_id: str
    objective: str
    objective_id: str = ""
    session_id: str = ""
    task_id: Optional[str] = None
    task: Optional[Any] = None
    execution_result: Optional[Any] = None
    verification_result: Optional[Any] = None
    changeset: Optional[Any] = None
    failure_evidence: Optional[List[Any]] = None
    attempt: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for event payloads."""
        d: Dict[str, Any] = {
            "run_id": self.run_id,
            "objective": self.objective,
            "objective_id": self.objective_id,
            "session_id": self.session_id,
        }
        if self.task_id is not None:
            d["task_id"] = self.task_id
        if self.attempt != 1:
            d["attempt"] = self.attempt
        if self.metadata:
            d["metadata"] = self.metadata
        return d


# =============================================================================
# ROLE RESULT (structured outcome)
# =============================================================================

@dataclass
class RoleResult:
    """Structured outcome of a role execution.

    Every role returns a RoleResult so the runtime can make decisions
    based on structured data rather than exception handling.
    """

    role: Role
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "role": self.role.value,
            "success": self.success,
        }
        if self.error:
            d["error"] = self.error
        if self.evidence:
            d["evidence"] = self.evidence
        if self.metadata:
            d["metadata"] = self.metadata
        return d


# =============================================================================
# AGENT ROLE INTERFACE (Section 2)
# =============================================================================

class AgentRole(ABC):
    """Abstract role boundary for separated reasoning responsibilities.

    Each role defines a responsibility but does NOT replace the underlying
    component. The role coordinates; the component executes.
    """

    @property
    @abstractmethod
    def name(self) -> Role:
        """The role's identity."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of this role's responsibility."""
        ...

    @abstractmethod
    def execute(self, context: RoleContext) -> RoleResult:
        """Execute this role's responsibility with the given context.

        Returns a structured RoleResult. Must NOT raise exceptions —
        failures become RoleResult(success=False, error=...).
        """
        ...


# =============================================================================
# PLANNER ROLE (Section 6)
# =============================================================================

class PlannerRole(AgentRole):
    """Represents planning as the PLANNER responsibility.

    Delegates to the existing structured Planner (Correction #15).
    Does not create a second planning implementation.
    """

    def __init__(self, planner: Any) -> None:
        self._planner = planner

    @property
    def name(self) -> Role:
        return Role.PLANNER

    @property
    def description(self) -> str:
        return "Decomposes objectives into structured task graphs via the Planner"

    @property
    def planner(self) -> Any:
        """Access the underlying planner for direct delegation."""
        return self._planner

    def execute(self, context: RoleContext) -> RoleResult:
        """Execute planning for the given objective.

        The runtime is responsible for calling this at the right lifecycle
        point and applying the resulting plan to the TaskGraph.
        """
        try:
            plan = self._planner.create_plan(
                workflow_id=context.metadata.get("workflow_id", f"wf_{context.session_id}"),
                objective=context.objective,
                planning_level=context.metadata.get("planning_level"),
                model_response=context.metadata.get("model_response"),
            )
            tasks = self._planner.create_tasks_from_plan(
                plan, context.objective_id
            )
            return RoleResult(
                role=self.name,
                success=True,
                output={"plan": plan, "tasks": tasks},
                metadata={"plan_id": plan.id, "task_count": len(tasks)},
            )
        except Exception as e:
            return RoleResult(
                role=self.name,
                success=False,
                error=str(e),
                evidence={"objective": context.objective, "exception_type": type(e).__name__},
            )


# =============================================================================
# IMPLEMENTER ROLE (Section 5)
# =============================================================================

class ImplementerRole(AgentRole):
    """Represents task execution as the IMPLEMENTER responsibility.

    The existing execution engine remains responsible for actual execution.
    This role boundary simply makes the responsibility explicit.
    """

    def __init__(self, executor: Any) -> None:
        self._executor = executor

    @property
    def name(self) -> Role:
        return Role.IMPLEMENTER

    @property
    def description(self) -> str:
        return "Executes engineering tasks via the tool executor"

    @property
    def executor(self) -> Any:
        """Access the underlying executor for direct delegation."""
        return self._executor

    def execute(self, context: RoleContext) -> RoleResult:
        """Execute a task via the underlying executor.

        The runtime wraps this call with workspace capture, changeset
        recording, and event emission.
        """
        try:
            task = context.task
            if task is None:
                return RoleResult(
                    role=self.name,
                    success=False,
                    error="No task provided in context",
                )

            if hasattr(self._executor, "execute"):
                try:
                    result = self._executor.execute(task, session_id=context.session_id)
                except TypeError:
                    result = self._executor.execute(task)
            elif callable(self._executor):
                result = self._executor(task)
            else:
                return RoleResult(
                    role=self.name,
                    success=False,
                    error=f"Unsupported executor type: {type(self._executor).__name__}",
                )

            return RoleResult(
                role=self.name,
                success=True,
                output=result,
                metadata={"task_id": getattr(task, "id", str(task))},
            )
        except Exception as e:
            return RoleResult(
                role=self.name,
                success=False,
                error=str(e),
                evidence={
                    "task_id": getattr(context.task, "id", None) if context.task else None,
                    "exception_type": type(e).__name__,
                },
            )


# =============================================================================
# VERIFIER ROLE (Section 7)
# =============================================================================

class VerifierRole(AgentRole):
    """Represents verification as the VERIFIER responsibility.

    Reuses the existing Verifier (Correction #17).
    Verification must continue to be the authority for task correctness.
    """

    def __init__(self, verifier: Any) -> None:
        self._verifier = verifier

    @property
    def name(self) -> Role:
        return Role.VERIFIER

    @property
    def description(self) -> str:
        return "Verifies task execution correctness via structured verification"

    @property
    def verifier(self) -> Any:
        """Access the underlying verifier for direct delegation."""
        return self._verifier

    def execute(self, context: RoleContext) -> RoleResult:
        """Verify a task's execution result.

        Delegates to the existing Verifier.verify() boundary.
        Does not bypass VerificationResult.
        """
        try:
            task = context.task
            exec_result = context.execution_result
            if task is None or exec_result is None:
                return RoleResult(
                    role=self.name,
                    success=False,
                    error="Task and execution_result are required for verification",
                )

            ver_result = self._verifier.verify(
                task=task,
                execution_result=exec_result,
                changeset=context.changeset,
            )
            passed = getattr(ver_result, "success", bool(ver_result))
            return RoleResult(
                role=self.name,
                success=passed,
                output=ver_result,
                metadata={
                    "task_id": getattr(task, "id", str(task)),
                    "verification_passed": passed,
                },
            )
        except Exception as e:
            return RoleResult(
                role=self.name,
                success=False,
                error=str(e),
                evidence={
                    "task_id": getattr(context.task, "id", None) if context.task else None,
                    "exception_type": type(e).__name__,
                },
            )


# =============================================================================
# RECOVERY ROLE (Section 8)
# =============================================================================

class RecoveryDecision(str, Enum):
    """Decisions the recovery role can make."""
    RETRY = "retry"
    REPLAN = "replan"
    FAIL = "fail"


class RecoveryRole(AgentRole):
    """Represents retry/replan decisions as the RECOVERY responsibility.

    Reuses the existing bounded recovery logic.
    Must NOT execute unlimited retries, directly mutate the TaskGraph
    without runtime authority, create another planner, or bypass
    failure evidence.

    AgentRuntime remains responsible for applying the resulting decision.
    """

    def __init__(
        self,
        max_task_retries: int = 0,
        max_replans: int = 2,
        can_replan: bool = True,
    ) -> None:
        self._max_task_retries = max_task_retries
        self._max_replans = max_replans
        self._can_replan = can_replan

    @property
    def name(self) -> Role:
        return Role.RECOVERY

    @property
    def description(self) -> str:
        return "Decides recovery strategy (retry, replan, or fail) upon task failure"

    def execute(self, context: RoleContext) -> RoleResult:
        """Decide recovery strategy for a failed task.

        Returns a RoleResult with output=RecoveryDecision indicating
        the recommended recovery action. The AgentRuntime is responsible
        for actually applying the decision.
        """
        try:
            task = context.task
            attempt = context.attempt
            replan_count = context.metadata.get("replan_count", 0)

            # Determine retry eligibility
            task_max = getattr(task, "max_retries", None) if task else None
            effective_limit = task_max if task_max is not None else self._max_task_retries

            retries_done = max(0, attempt - 1)

            if effective_limit > 0 and retries_done < effective_limit:
                return RoleResult(
                    role=self.name,
                    success=True,
                    output=RecoveryDecision.RETRY,
                    metadata={
                        "decision": RecoveryDecision.RETRY.value,
                        "attempt": attempt,
                        "max_retries": effective_limit,
                        "retries_remaining": effective_limit - retries_done,
                    },
                )

            # Retry exhausted — try replan
            if self._can_replan and replan_count < self._max_replans:
                return RoleResult(
                    role=self.name,
                    success=True,
                    output=RecoveryDecision.REPLAN,
                    metadata={
                        "decision": RecoveryDecision.REPLAN.value,
                        "replan_count": replan_count,
                        "max_replans": self._max_replans,
                    },
                )

            # All recovery exhausted
            return RoleResult(
                role=self.name,
                success=True,
                output=RecoveryDecision.FAIL,
                metadata={
                    "decision": RecoveryDecision.FAIL.value,
                    "reason": "All recovery strategies exhausted",
                    "attempt": attempt,
                    "replan_count": replan_count,
                },
            )
        except Exception as e:
            return RoleResult(
                role=self.name,
                success=False,
                error=str(e),
                evidence={"exception_type": type(e).__name__},
            )


# =============================================================================
# ROLE REGISTRY (Section 4)
# =============================================================================

class RoleRegistry:
    """Registry for role resolution and injection.

    Allows registering, resolving, and replacing role implementations.
    Supports test injection of fake roles.
    """

    def __init__(self) -> None:
        self._roles: Dict[Role, AgentRole] = {}

    def register(self, role: Role, implementation: AgentRole) -> None:
        """Register a role implementation.

        Replaces any previous registration for the same role.
        """
        if not isinstance(role, Role):
            raise TypeError(f"Expected Role enum, got {type(role).__name__}")
        if not isinstance(implementation, AgentRole):
            raise TypeError(f"Expected AgentRole instance, got {type(implementation).__name__}")
        self._roles[role] = implementation

    def resolve(self, role: Role) -> AgentRole:
        """Resolve a registered role implementation.

        Raises KeyError if the role is not registered.
        """
        if role not in self._roles:
            raise KeyError(f"No implementation registered for role: {role.value}")
        return self._roles[role]

    def has(self, role: Role) -> bool:
        """Check whether a role is registered."""
        return role in self._roles

    def unregister(self, role: Role) -> None:
        """Remove a role registration."""
        self._roles.pop(role, None)

    @property
    def registered_roles(self) -> List[Role]:
        """List all registered roles."""
        return list(self._roles.keys())

    def to_dict(self) -> Dict[str, str]:
        """Serialize registry state for diagnostics."""
        return {
            role.value: type(impl).__name__
            for role, impl in self._roles.items()
        }
