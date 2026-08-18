from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from clairecoder.core.types import ExecutionState

class ObjectiveStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class EngineeringObjective:
    id: str
    request: str
    session_id: str
    mode: Optional[str] = None
    model_profile_id: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    status: ObjectiveStatus = ObjectiveStatus.ACTIVE
    workflow_id: Optional[str] = None
    completion_criteria: List[str] = field(default_factory=list)

from clairecoder.workflow.types import Task, TaskState

class EngineEvent(str, Enum):
    OBJECTIVE_STARTED = "objective_started"
    PLANNING_STARTED = "planning_started"
    PLANNING_COMPLETED = "planning_completed"
    TASK_STARTED = "task_started"
    TOOL_REQUESTED = "tool_requested"
    PERMISSION_REQUESTED = "permission_requested"
    PERMISSION_RESOLVED = "permission_resolved"
    TOOL_COMPLETED = "tool_completed"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    TASK_COMPLETED = "task_completed"
    REPLANNING_STARTED = "replanning_started"
    OBJECTIVE_COMPLETED = "objective_completed"
    EXECUTION_PAUSED = "execution_paused"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_FAILED = "execution_failed"

