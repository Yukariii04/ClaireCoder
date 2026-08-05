from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from clairecoder.core.types import PermissionState

class AutonomyLevel(str, Enum):
    SUPERVISED = "supervised"
    ASSISTED = "assisted"
    AUTONOMOUS = "autonomous"
    YOLO = "yolo"

class PermissionCategory(str, Enum):
    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    EXECUTE = "execute"
    NETWORK = "network"
    INSTALL = "install"
    MODIFY_REPOSITORY = "modify_repository"
    ACCESS_CREDENTIAL = "access_credential"

class ResourceScope(str, Enum):
    PROJECT = "project"
    REPOSITORY = "repository"
    DIRECTORY = "directory"
    FILE = "file"
    COMMAND = "command"
    NETWORK_RESOURCE = "network_resource"
    CREDENTIAL = "credential"
    EXTERNAL_SERVICE = "external_service"

@dataclass
class PermissionRequest:
    tool_id: str
    operation: str
    resource: str
    category: PermissionCategory
    resource_scope: ResourceScope
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None  # Contextual information only, not used for rule matching in V1
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class PermissionError(Exception):
    pass

class PermissionDeniedError(PermissionError):
    pass

class PermissionRequiredError(PermissionError):
    pass

class PermissionScopeError(PermissionError):
    """Deferred for future scope restriction checking."""
    pass

class PermissionEscalationError(PermissionError):
    """Deferred for future privilege escalation checking."""
    pass

@dataclass
class PermissionRule:
    decision: PermissionState
    tool_id: Optional[str] = None
    operation: Optional[str] = None
    resource: Optional[str] = None
    category: Optional[PermissionCategory] = None
    resource_scope: Optional[ResourceScope] = None
    autonomy_level: Optional[AutonomyLevel] = None
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    priority: int = 0
