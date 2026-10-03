"""Workflow & Planning type definitions.

CC-PRD-004 Section 6–10: Workflow, Task, dependency, and state representation.
CC-ADR-004 Section 5–8: Workflow architecture, adaptive planning, task model.

Correction #13: Enriched Task model with TaskType, structured metadata,
failure evidence, attempt tracking, and full plan semantics preservation.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# =============================================================================
# WORKFLOW STATE  (CC-PRD-004 Section 7)
# =============================================================================

class WorkflowState(str, Enum):
    """Lifecycle states for a Workflow.

    CC-PRD-004 Section 7:
        CREATED → PLANNED → ACTIVE → VALIDATING → COMPLETE / FAILED → REPLANNING → ACTIVE / FAILED
    """
    CREATED = "created"
    PLANNED = "planned"
    ACTIVE = "active"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"
    REPLANNING = "replanning"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    INTERRUPTED = "interrupted"


# =============================================================================
# TASK TYPE  (Correction #13)
# =============================================================================

class TaskType(str, Enum):
    """Classification of task work type.

    Used by the planner to communicate the nature of each task unit.
    If the model does not provide a type, IMPLEMENTATION is the safe default.
    """
    ANALYSIS = "analysis"
    IMPLEMENTATION = "implementation"
    TEST = "test"
    REFACTOR = "refactor"
    VERIFICATION = "verification"
    DOCUMENTATION = "documentation"
    OTHER = "other"

    @classmethod
    def _missing_(cls, value: Any) -> "TaskType":
        if isinstance(value, str):
            v = value.lower().strip()
            for member in cls:
                if member.value == v:
                    return member
        return cls.OTHER


# =============================================================================
# TASK STATE  (CC-PRD-004 Section 8, Correction #13)
# =============================================================================

class TaskState(str, Enum):
    """Lifecycle states for a Workflow Task.

    Correction #13: Added READY and CANCELLED to distinguish dependency
    readiness from initial pending, and support explicit cancellation.

    PENDING   — task has unresolved dependencies
    READY     — all dependencies are satisfied, eligible for execution
    RUNNING   — currently executing
    SUCCEEDED — execution and validation succeeded (also aliased as COMPLETED)
    FAILED    — task attempted and failed
    BLOCKED   — cannot execute because a dependency failed
    CANCELLED — explicitly cancelled
    """
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    EXECUTED = "executed"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"

    @classmethod
    def _missing_(cls, value: Any) -> "TaskState":
        if isinstance(value, str):
            v = value.lower().strip()
            if v in ("completed", "done", "verified"):
                return cls.SUCCEEDED
            for member in cls:
                if member.value == v:
                    return member
        return super()._missing_(value)


# Alias TaskState.COMPLETED and TaskState.VERIFIED to SUCCEEDED
TaskState.COMPLETED = TaskState.SUCCEEDED
TaskState.VERIFIED = TaskState.SUCCEEDED

# Alias TaskStatus to TaskState for naming compatibility
TaskStatus = TaskState


# =============================================================================
# PLANNING LEVEL  (CC-ADR-004 Section 6.2)
# =============================================================================

class PlanningLevel(int, Enum):
    """Adaptive planning depth.

    CC-ADR-004 Section 6.2:
        LEVEL 0 — Direct (simple, well-defined operations)
        LEVEL 1 — Lightweight (limited repository inspection)
        LEVEL 2 — Structured (multiple files/components)
        LEVEL 3 — Deep (complex architectural / multi-stage)
    """
    DIRECT = 0
    LIGHTWEIGHT = 1
    STRUCTURED = 2
    DEEP = 3


# =============================================================================
# WORKFLOW  (CC-PRD-004 Section 6, CC-ADR-004 Section 5.1)
# =============================================================================

@dataclass
class Workflow:
    """A structured engineering process.

    CC-PRD-004 Section 6: A Workflow represents the structured process through
    which an engineering objective is completed.

    CC-ADR-004 Section 5.1: Examples include implementation, debugging, review,
    research, testing, refactoring.
    """
    id: str
    objective_id: str
    description: str
    state: WorkflowState = WorkflowState.CREATED
    task_ids: List[str] = field(default_factory=list)
    completion_criteria: List[str] = field(default_factory=list)
    validation_requirements: List[str] = field(default_factory=list)
    relevant_skills: List[str] = field(default_factory=list)
    relevant_tools: List[str] = field(default_factory=list)
    context_requirements: List[str] = field(default_factory=list)
    planning_level: PlanningLevel = PlanningLevel.STRUCTURED
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# TASK  (CC-PRD-004 Section 8, Correction #13)
# =============================================================================

@dataclass
class Task:
    """A Workflow Task carrying full semantic plan information.

    CC-PRD-004 Section 8: Task representation distinct from Execution State.

    Correction #13: Enriched with title, type, inputs, expected_outputs,
    validation, failure_evidence, and attempt count to preserve plan
    semantics through the entire pipeline:
        model plan → planner → Task → execution → result
    """
    id: str
    objective_id: str
    description: str

    # --- Correction #13: Structured semantic fields ---
    title: str = ""
    type: TaskType = TaskType.IMPLEMENTATION

    status: TaskState = TaskState.PENDING
    dependencies: List[str] = field(default_factory=list)

    # What the task will consume and produce
    inputs: List[str] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)

    # How the task result will be validated
    validation: List[str] = field(default_factory=list)

    # --- Existing fields preserved for backward compatibility ---
    expected_result: Optional[str] = None
    validation_requirements: List[str] = field(default_factory=list)
    context_references: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)

    # --- Correction #13 & #17: Attempt, retry & failure tracking ---
    attempts: int = 0
    max_retries: Optional[int] = None
    failure_evidence: List[Dict[str, Any]] = field(default_factory=list)

    # --- Arbitrary metadata ---
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.type, str) and not isinstance(self.type, TaskType):
            try:
                self.type = TaskType(self.type)
            except (ValueError, KeyError):
                self.type = TaskType.IMPLEMENTATION
        if isinstance(self.status, str) and not isinstance(self.status, TaskState):
            try:
                self.status = TaskState(self.status)
            except (ValueError, KeyError):
                self.status = TaskState.PENDING

    @property
    def is_completed(self) -> bool:
        return self.status == TaskState.SUCCEEDED

    @property
    def is_ready(self) -> bool:
        return self.status == TaskState.READY

    @property
    def is_blocked(self) -> bool:
        return self.status == TaskState.BLOCKED


# =============================================================================
# PLAN  (CC-ADR-004 Section 6.3)
# =============================================================================

@dataclass
class Plan:
    """A planning artifact produced by the Planner.

    CC-ADR-004 Section 6.3: A plan SHOULD contain objective, assumptions,
    affected areas, tasks, dependencies, validation strategy, risks,
    completion criteria.

    The plan SHALL be persistable inside the Engineering Session.

    Correction #13: Added task_details to preserve structured per-task
    metadata from the model's plan output.
    """
    id: str
    workflow_id: str
    objective: str
    planning_level: PlanningLevel
    assumptions: List[str] = field(default_factory=list)
    affected_areas: List[str] = field(default_factory=list)
    task_ids: List[str] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    validation_strategy: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    completion_criteria: List[str] = field(default_factory=list)
    is_superseded: bool = False
    superseded_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Correction #13: Structured per-task details from model output
    # Maps task_id → dict with keys like title, description, type, inputs, etc.
    task_details: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @property
    def tasks(self) -> List[Dict[str, Any]]:
        """Correction #15: Return structured task records for TaskGraph construction."""
        records: List[Dict[str, Any]] = []
        for tid in self.task_ids:
            details = dict(self.task_details.get(tid, {}))
            details["id"] = tid
            if "dependencies" not in details or not details["dependencies"]:
                details["dependencies"] = list(self.dependencies.get(tid, []))
            records.append(details)
        return records


# =============================================================================
# ERRORS
# =============================================================================

class WorkflowError(Exception):
    """Base error for Workflow system failures."""
    pass


class WorkflowStateError(WorkflowError):
    """Raised when an invalid workflow state transition is attempted."""
    pass


class PlanningError(WorkflowError):
    """Raised when planning fails."""
    pass


class TaskGraphError(WorkflowError):
    """Raised when the TaskGraph detects a structural or state error."""
    pass


class DependencyCycleError(TaskGraphError):
    """Raised when a dependency cycle is detected in a task graph."""
    pass


class DependencyNotFoundError(TaskGraphError):
    """Raised when a dependency references a non-existent task."""
    pass


class InvalidDependencyError(TaskGraphError):
    """Raised when a dependency relationship is malformed or invalid."""
    pass
