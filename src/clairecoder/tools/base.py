from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from clairecoder.core.types import PermissionRequirement, ToolResult, ToolState
from .types import ToolMetadata, ToolCategory, ToolValidationError, ToolExecutionError

class Tool(ABC):
    """Base class for all ClaireCoder tools.
    
    A Tool is an executable capability. It declares its metadata,
    permission requirements, validates its inputs, and produces
    structured ToolResult outputs.
    
    Tools do NOT decide whether they are authorized to execute.
    Authorization belongs to the Permission Engine.
    
    Architectural Guarantee (CC-ADR-003 Section 32):
    This class intentionally provides NO public `execute()` method. 
    By strict architectural contract, the `ToolExecutor` is the only 
    supported execution path. While Python permits calling internal 
    methods (like `_execute`) directly, doing so violates the API 
    boundary and is not an authorized alternate execution path.
    """

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Return the tool's metadata including id, name, description, category, etc."""
        pass

    @property
    @abstractmethod
    def required_permissions(self) -> List[PermissionRequirement]:
        """Declare the permission requirements for this tool's operations."""
        pass

    @abstractmethod
    def validate_input(self, **kwargs: Any) -> None:
        """Validate inputs before execution.
        
        Raises ToolValidationError if inputs are invalid.
        """
        pass

    @abstractmethod
    def _execute(self, **kwargs: Any) -> ToolResult:
        """Internal execution logic. Called only after permission is granted.
        
        Subclasses implement their actual operation here.
        This method MUST NOT perform its own permission checks.
        """
        pass
