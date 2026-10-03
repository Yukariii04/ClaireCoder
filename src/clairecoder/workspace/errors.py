"""Workspace error hierarchy (Correction #19 §1, §10).

Provides structured error types for workspace access and path security violations.
"""

from typing import Optional


class WorkspaceError(Exception):
    """Base exception for all workspace operations."""
    pass


class WorkspacePathEscapeError(WorkspaceError, PermissionError):
    """Raised when a path escapes the configured workspace root."""
    def __init__(self, message: str, path: Optional[str] = None) -> None:
        super().__init__(message)
        self.path = path


# Backward compatibility alias
WorkspaceSecurityError = WorkspacePathEscapeError


class WorkspaceFileNotFoundError(WorkspaceError, FileNotFoundError):
    """Raised when a requested file or directory does not exist in workspace."""
    def __init__(self, message: str, path: Optional[str] = None) -> None:
        super().__init__(message)
        self.path = path


class WorkspaceIsADirectoryError(WorkspaceError, IsADirectoryError):
    """Raised when a file operation is attempted on a directory."""
    def __init__(self, message: str, path: Optional[str] = None) -> None:
        super().__init__(message)
        self.path = path


class WorkspaceNotADirectoryError(WorkspaceError, NotADirectoryError):
    """Raised when a directory operation is attempted on a file."""
    def __init__(self, message: str, path: Optional[str] = None) -> None:
        super().__init__(message)
        self.path = path


class WorkspacePermissionError(WorkspaceError, PermissionError):
    """Raised when an operation fails due to OS filesystem permissions."""
    def __init__(self, message: str, path: Optional[str] = None) -> None:
        super().__init__(message)
        self.path = path


class WorkspaceFileTooLargeError(WorkspaceError):
    """Raised when a file exceeds the allowed size budget for in-memory reading."""
    def __init__(self, message: str, path: Optional[str] = None, size: Optional[int] = None) -> None:
        super().__init__(message)
        self.path = path
        self.size = size


class WorkspaceBinaryFileError(WorkspaceError):
    """Raised when binary file content cannot be safely handled as text."""
    def __init__(self, message: str, path: Optional[str] = None) -> None:
        super().__init__(message)
        self.path = path
