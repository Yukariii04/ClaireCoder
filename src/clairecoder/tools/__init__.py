"""ClaireCoder Tools Subsystem.

Correction #19: Tool + Workspace boundary with structured results,
deterministic registry, and safe workspace access.
"""

from .errors import (
    ToolError,
    UnknownToolError,
    DuplicateToolError,
    InvalidToolArgumentsError,
    CommandExecutionError,
    ToolExecutionError,
)
from .types import (
    ToolCategory,
    ToolAvailability,
    ToolMetadata,
    ExtensionSource,
    TrustLevel,
    ToolValidationError,
    ToolNotFoundError,
    ToolUnavailableError,
)
from .base import Tool as BaseTool
from .tool import Tool, ToolContext, normalize_tool_call
from .registry import ToolRegistry
from .executor import ToolExecutor
from .structured import (
    ReadFileTool,
    WriteFileTool,
    DeleteFileTool,
    ListFilesTool,
    RunCommandTool,
)

__all__ = [
    # Structured Tool model (Correction #19)
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ReadFileTool",
    "WriteFileTool",
    "DeleteFileTool",
    "ListFilesTool",
    "RunCommandTool",
    "ToolError",
    "UnknownToolError",
    "DuplicateToolError",
    "InvalidToolArgumentsError",
    "CommandExecutionError",
    "ToolExecutionError",
    # Legacy / Phase 4 integration
    "BaseTool",
    "ToolExecutor",
    "ToolCategory",
    "ToolAvailability",
    "ToolMetadata",
    "ExtensionSource",
    "TrustLevel",
    "ToolValidationError",
    "ToolNotFoundError",
    "ToolUnavailableError",
]
