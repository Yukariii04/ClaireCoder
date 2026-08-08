from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Mapping
from types import MappingProxyType
from datetime import datetime, timezone

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def make_immutable(obj: Any) -> Any:
    """Recursively freeze basic standard-library collections."""
    if isinstance(obj, dict):
        return MappingProxyType({k: make_immutable(v) for k, v in obj.items()})
    elif isinstance(obj, (list, tuple)):
        return tuple(make_immutable(v) for v in obj)
    elif isinstance(obj, set):
        return frozenset(make_immutable(v) for v in obj)
    return obj

class ContextSource(int, Enum):
    """Context source ordering as defined in CC-PRD-008 Section 18 & 19."""
    SYSTEM = 10
    USER = 20
    SESSION = 30
    WORKFLOW = 40
    TASK = 50
    REPOSITORY = 60
    TOOL = 70
    MEMORY = 80
    MODEL = 90

class MemoryCategory(str, Enum):
    SESSION = "session"
    PROJECT = "project"
    DECISION = "decision"
    TASK = "task"

class MemoryScope(str, Enum):
    SESSION = "session"
    TASK = "task"
    PROJECT = "project"

class MemoryStatus(str, Enum):
    ACTIVE = "active"
    INVALID = "invalid"
    ARCHIVED = "archived"

class MemoryTrust(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"

@dataclass(frozen=True)
class Provenance:
    source: ContextSource
    identity: str
    description: Optional[str] = None

@dataclass(frozen=True)
class MemoryRecord:
    id: str
    category: MemoryCategory
    scope: MemoryScope
    content: Any
    provenance: Provenance
    status: MemoryStatus = MemoryStatus.ACTIVE
    trust: MemoryTrust = MemoryTrust.UNVERIFIED
    created_at: datetime = field(default_factory=now_utc)
    updated_at: datetime = field(default_factory=now_utc)
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self):
        # Deep freeze metadata. Content remains opaque/unfrozen by design as per PRD.
        object.__setattr__(self, 'metadata', make_immutable(self.metadata))

@dataclass(frozen=True)
class EngineeringContext:
    """Immutable snapshot of Context.
    
    CC-PRD-008 Section 22: The Context object SHALL be immutable after construction.
    If context changes, a new Context SHALL be constructed.
    """
    id: str
    session_info: Mapping[str, Any]
    workflow_info: Mapping[str, Any]
    task_info: Mapping[str, Any]
    repository_state: Mapping[str, Any]
    memories: tuple[MemoryRecord, ...]
    tool_results: tuple[Mapping[str, Any], ...]
    instructions: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self):
        # Deep freeze all nested dictionary and list structures
        object.__setattr__(self, 'session_info', make_immutable(self.session_info))
        object.__setattr__(self, 'workflow_info', make_immutable(self.workflow_info))
        object.__setattr__(self, 'task_info', make_immutable(self.task_info))
        object.__setattr__(self, 'repository_state', make_immutable(self.repository_state))
        object.__setattr__(self, 'tool_results', make_immutable(self.tool_results))
        object.__setattr__(self, 'instructions', make_immutable(self.instructions))
        object.__setattr__(self, 'metadata', make_immutable(self.metadata))

class ContextError(Exception):
    pass

class ContextConstructionError(ContextError):
    pass

class MemoryNotFoundError(ContextError):
    pass
