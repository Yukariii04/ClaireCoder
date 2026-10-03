"""Execution State subsystem types.

CC-PRD-007 Section 6-15: Execution State Model, Task lifecycle, failure categories.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class TaskState(str, Enum):
    """Lifecycle states for a Task.
    
    CC-PRD-007 Section 9: V1 SHALL implement ONLY these explicit states.
    """
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"

class ExecutionResultCategory(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"

class FailureCategory(str, Enum):
    TOOL_FAILURE = "tool_failure"
    PERMISSION_FAILURE = "permission_failure"
    VALIDATION_FAILURE = "validation_failure"
    TIMEOUT = "timeout"
    RESOURCE_FAILURE = "resource_failure"
    DEPENDENCY_FAILURE = "dependency_failure"
    USER_CANCELLATION = "user_cancellation"
    UNKNOWN_FAILURE = "unknown_failure"

@dataclass
class FailureEvidence:
    """Structured failure context for replanning.

    Carries actual available evidence rather than a generic sentence.
    Not all fields will be populated — only pass what exists.
    """
    tool: Optional[str] = None
    tool_call_id: Optional[str] = None
    operation: Optional[str] = None
    target: Optional[str] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    diff: Optional[str] = None
    verification: Optional[str] = None
    reason: Optional[str] = None
    task_id: Optional[str] = None
    timeout: Optional[bool] = None
    cancellation: Optional[bool] = None

    def to_summary(self) -> str:
        """Produce a human-readable summary from available fields."""
        parts = []
        if self.tool:
            parts.append(f"tool={self.tool}")
        if self.operation:
            parts.append(f"op={self.operation}")
        if self.target:
            parts.append(f"target={self.target}")
        if self.exit_code is not None:
            parts.append(f"exit_code={self.exit_code}")
        if self.reason:
            parts.append(f"reason={self.reason}")
        if self.stderr:
            parts.append(f"stderr={self.stderr[:200]}")
        if self.stdout:
            parts.append(f"stdout={self.stdout[:200]}")
        if self.verification:
            parts.append(f"verification={self.verification}")
        if self.diff:
            parts.append(f"diff={self.diff[:200]}")
        if self.timeout:
            parts.append("timeout=True")
        if self.cancellation:
            parts.append("cancelled=True")
        if self.task_id:
            parts.append(f"task_id={self.task_id}")
        return "; ".join(parts) if parts else "No evidence available"


@dataclass
class ExecutionResult:
    """The result of executing a Task (CC-PRD-007 Section 10).

    Correction #14: Separates WHAT happened (ExecutionResult) from WHAT
    needed to happen (Task). Supports duration, changed files, commands,
    outputs, and a direct .success boolean property.
    """
    category: ExecutionResultCategory = ExecutionResultCategory.SUCCESS
    failure_category: Optional[FailureCategory] = None
    error_message: Optional[str] = None
    tool_result: Optional[Any] = None
    failure_evidence: Optional[FailureEvidence] = None
    task_id: Optional[str] = None
    outputs: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    duration: float = 0.0

    def __init__(
        self,
        category: Optional[ExecutionResultCategory] = None,
        failure_category: Optional[FailureCategory] = None,
        error_message: Optional[str] = None,
        tool_result: Optional[Any] = None,
        failure_evidence: Optional[FailureEvidence] = None,
        task_id: Optional[str] = None,
        outputs: Optional[List[str]] = None,
        changed_files: Optional[List[str]] = None,
        commands: Optional[List[str]] = None,
        duration: float = 0.0,
        success: Optional[bool] = None,
    ) -> None:
        if category is not None:
            self.category = category
        elif success is not None:
            self.category = ExecutionResultCategory.SUCCESS if success else ExecutionResultCategory.FAILURE
        else:
            self.category = ExecutionResultCategory.SUCCESS

        self.failure_category = failure_category
        self.error_message = error_message
        self.tool_result = tool_result
        self.failure_evidence = failure_evidence
        self.task_id = task_id
        self.outputs = outputs or []
        self.changed_files = changed_files or []
        self.commands = commands or []
        self.duration = duration

    @property
    def success(self) -> bool:
        return self.category == ExecutionResultCategory.SUCCESS

    @success.setter
    def success(self, val: bool) -> None:
        self.category = ExecutionResultCategory.SUCCESS if val else ExecutionResultCategory.FAILURE


@dataclass
class ExecutionAttempt:
    """An attempt to perform a Task (CC-PRD-007 Section 13)."""
    execution_id: str
    task_id: str
    attempt_number: int
    started_at: datetime
    status: TaskState
    completed_at: Optional[datetime] = None
    result: Optional[ExecutionResult] = None
    error: Optional[str] = None

@dataclass
class Task:
    """An execution-state tracking record for a Task (CC-PRD-007 Section 7).

    Correction #14: Clarified as an execution tracking entity owned by
    ExecutionManager. The authoritative semantic task definition is workflow.Task.
    """
    id: str
    objective_id: str
    description: str
    workflow_id: str = ""
    status: TaskState = TaskState.PENDING
    dependencies: List[str] = field(default_factory=list)
    affected_areas: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    validation_requirements: List[str] = field(default_factory=list)
    attempts: List[ExecutionAttempt] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    result: Optional[Any] = None
    failure_state: Optional[str] = None

    @classmethod
    def from_workflow_task(cls, w_task: Any, workflow_id: str = "") -> "Task":
        """Hydrate an ExecutionTask record from a workflow.Task object."""
        status_val = w_task.status.value if hasattr(w_task.status, "value") else str(w_task.status)
        try:
            state = TaskState(status_val)
        except ValueError:
            state = TaskState.PENDING

        if state == TaskState.RUNNING:
            state = TaskState.PENDING

        return cls(
            id=w_task.id,
            objective_id=w_task.objective_id,
            description=w_task.description,
            workflow_id=workflow_id,
            status=state,
            dependencies=list(w_task.dependencies),
            validation_requirements=list(getattr(w_task, "validation_requirements", []) or getattr(w_task, "validation", [])),
        )


# Alias ExecutionTask to Task for explicit semantic naming
ExecutionTask = Task

# Exceptions CC-PRD-007 Section 44
class ExecutionError(Exception):
    pass

class InvalidStateTransitionError(ExecutionError):
    pass

class TaskNotFoundError(ExecutionError):
    pass

class ExecutionNotFoundError(ExecutionError):
    pass

class ExecutionTimeoutError(ExecutionError):
    pass

class ExecutionCancelledError(ExecutionError):
    pass

class DependencyBlockedError(ExecutionError):
    pass

class RecoveryError(ExecutionError):
    pass

class VerificationError(ExecutionError):
    pass
