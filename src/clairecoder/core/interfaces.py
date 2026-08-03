from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from .types import ExecutionState, PermissionState, PermissionRequirement, ToolResult

class ToolInterface(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A description of what the tool does."""
        pass

    @property
    @abstractmethod
    def required_permissions(self) -> List[PermissionRequirement]:
        """Declare the permission requirements for this tool."""
        pass


class PermissionEngineInterface(ABC):
    @abstractmethod
    def check_permission(self, action: str, target: str, **kwargs: Any) -> PermissionState:
        """Check if an action is allowed, denied, or needs asking."""
        pass
