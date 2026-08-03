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
    state: ToolState
    output: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
