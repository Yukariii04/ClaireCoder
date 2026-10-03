"""ClaireCoder Workspace Layer (Correction #19).

Provides safe project-root file access, centralized path normalization,
and ChangeTracker / ChangeSet integration.
"""

from .errors import (
    WorkspaceError,
    WorkspacePathEscapeError,
    WorkspaceSecurityError,
    WorkspaceFileNotFoundError,
    WorkspaceIsADirectoryError,
    WorkspaceNotADirectoryError,
    WorkspacePermissionError,
    WorkspaceFileTooLargeError,
    WorkspaceBinaryFileError,
)
from .path_safety import normalize_workspace_path, is_within_workspace
from .workspace import Workspace

__all__ = [
    "Workspace",
    "normalize_workspace_path",
    "is_within_workspace",
    "WorkspaceError",
    "WorkspacePathEscapeError",
    "WorkspaceSecurityError",
    "WorkspaceFileNotFoundError",
    "WorkspaceIsADirectoryError",
    "WorkspaceNotADirectoryError",
    "WorkspacePermissionError",
    "WorkspaceFileTooLargeError",
    "WorkspaceBinaryFileError",
]
