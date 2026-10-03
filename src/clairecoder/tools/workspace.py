"""Central workspace security boundary.

Provides ONE authoritative workspace root and path resolver.
All file-based tools use this to prevent path escapes.

Correction #19: Re-exports from clairecoder.workspace for backwards compatibility.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from clairecoder.workspace.errors import (
    WorkspaceError,
    WorkspacePathEscapeError,
    WorkspaceSecurityError,
)
from clairecoder.workspace.path_safety import (
    is_within_workspace,
    normalize_workspace_path,
)
from clairecoder.workspace.workspace import Workspace


@dataclass(frozen=True)
class ExecutionContext:
    """Authoritative execution context for all tool invocations."""
    workspace_root: Path
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None


def resolve_workspace_path(workspace_root: Path, requested: str) -> Path:
    """Resolve a requested path within the workspace boundary.

    Backwards compatibility wrapper over normalize_workspace_path.
    """
    return normalize_workspace_path(workspace_root, requested)


__all__ = [
    "ExecutionContext",
    "WorkspaceSecurityError",
    "WorkspacePathEscapeError",
    "WorkspaceError",
    "resolve_workspace_path",
    "is_within_workspace",
    "normalize_workspace_path",
    "Workspace",
]
