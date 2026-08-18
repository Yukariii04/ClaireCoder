"""Presentation activity model for the TUI transcript."""
from enum import Enum, auto
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import uuid
import time

class ActivityType(Enum):
    MESSAGE = auto()
    READING = auto()
    EDITING = auto()
    TOOL = auto()
    TEST = auto()
    VERIFICATION = auto()
    PERMISSION = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()
    THINKING = auto()

class ActivityState(Enum):
    RUNNING = auto()
    COMPLETED = auto()
    APPROVAL_REQUIRED = auto()
    FAILED = auto()
    BLOCKED = auto()

@dataclass
class DiffLine:
    type: str # 'add', 'remove', 'context'
    content: str

@dataclass
class DiffInfo:
    summary: str
    lines: List[DiffLine] = field(default_factory=list)

@dataclass
class ActivityModel:
    type: ActivityType = ActivityType.MESSAGE
    state: ActivityState = ActivityState.RUNNING
    title: str = ""
    detail: Optional[str] = None
    expandable_content: Optional[str] = None
    diff_info: Optional[DiffInfo] = None
    correlation_key: Optional[str] = None
    updates_activity: bool = False
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    expanded: bool = False
    order_index: int = 0
    
    @property
    def starts_new_activity(self) -> bool:
        return not self.updates_activity
