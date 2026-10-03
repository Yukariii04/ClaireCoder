from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

class PermissionState(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"

class ExecutionState(str, Enum):
    IDLE = "idle"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    REPLANNING = "replanning"
    FAILED = "failed"

from dataclasses import field

@dataclass
class PermissionRequirement:
    action: str
    resource: str
    scope: str = "project"


class ToolState(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"

@dataclass
class ToolResult:
    state: ToolState = ToolState.SUCCESS
    output: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration: Optional[float] = None
    success: Optional[bool] = None
    changed_files: Optional[List[str]] = None
    changeset_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.success is None:
            self.success = (self.state == ToolState.SUCCESS)
        elif self.success and self.state != ToolState.SUCCESS:
            self.state = ToolState.SUCCESS
        elif not self.success and self.state == ToolState.SUCCESS:
            self.state = ToolState.FAILURE

    def __bool__(self) -> bool:
        return bool(self.success)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "success": bool(self.success),
            "state": self.state.value if hasattr(self.state, "value") else str(self.state),
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }
        if self.duration is not None:
            d["duration"] = self.duration
        if self.changed_files is not None:
            d["changed_files"] = self.changed_files
        if self.changeset_id is not None:
            d["changeset_id"] = self.changeset_id
        return d
