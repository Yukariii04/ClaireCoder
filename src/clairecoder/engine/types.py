from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from clairecoder.core.types import ExecutionState

class ObjectiveStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
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
    """Normalized event protocol.

    §29 — All significant runtime events are represented here.
    The TUI is an observer.
    """
    # Run lifecycle
    RUN_STARTED = "run_started"
    RUN_STATE_CHANGED = "run_state_changed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"

    # Objective lifecycle
    OBJECTIVE_STARTED = "objective_started"
    OBJECTIVE_COMPLETED = "objective_completed"

    # Planning
    PLANNING_STARTED = "planning_started"
    PLANNING_COMPLETED = "planning_completed"

    # Task lifecycle
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"

    # Model interactions
    MODEL_STARTED = "model_started"
    STREAMING_CHUNK = "streaming_chunk"
    MODEL_COMPLETED = "model_completed"
    MODEL_FAILED = "model_failed"
    RESPONSE_COMPLETE = "response_complete"

    # Tool interactions
    TOOL_REQUESTED = "tool_requested"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    TOOL_DIFF = "tool_diff"

    # Permission interactions
    PERMISSION_REQUESTED = "permission_requested"
    PERMISSION_RESOLVED = "permission_resolved"

    # Verification
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"

    # Replanning
    REPLANNING_STARTED = "replanning_started"

    # Execution control
    EXECUTION_PAUSED = "execution_paused"
    EXECUTION_RESUMED = "execution_resumed"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_FAILED = "execution_failed"

    # Model/Mode switching
    MODEL_SWITCHED = "model_switched"
    MODE_CHANGED = "mode_changed"
