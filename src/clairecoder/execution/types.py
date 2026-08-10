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
class ExecutionResult:
    category: ExecutionResultCategory
    failure_category: Optional[FailureCategory] = None
    error_message: Optional[str] = None
    tool_result: Optional[Any] = None

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
    """A single bounded engineering operation (CC-PRD-007 Section 7)."""
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
