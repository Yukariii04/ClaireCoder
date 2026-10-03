"""Structured error types for Tool subsystem (Correction #19 §10)."""

from typing import Optional


class ToolError(Exception):
    """Base exception for all tool operations."""
    pass


class UnknownToolError(ToolError, KeyError):
    """Raised when an requested tool is not registered in the ToolRegistry."""
    def __init__(self, message: str, tool_name: Optional[str] = None) -> None:
        super().__init__(message)
        self.tool_name = tool_name or message


class DuplicateToolError(ToolError):
    """Raised when attempting to register a tool with an already-registered name."""
    def __init__(self, message: str, tool_name: Optional[str] = None) -> None:
        super().__init__(message)
        self.tool_name = tool_name or message


class InvalidToolArgumentsError(ToolError, ValueError):
    """Raised when tool arguments are missing, malformed, or invalid."""
    pass


class CommandExecutionError(ToolError):
    """Raised when command execution fails or exits non-zero unexpectedly."""
    pass


class ToolExecutionError(ToolError):
    """Raised when an internal error occurs during tool execution."""
    pass
