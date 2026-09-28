"""Central workspace security boundary.

Provides ONE authoritative workspace root and path resolver.
All file-based tools use this to prevent path escapes.

Per §6 — Do not duplicate path-security rules in individual tools.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ExecutionContext:
    """Authoritative execution context for all tool invocations."""
    workspace_root: Path
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None


class WorkspaceSecurityError(PermissionError):
    """Raised when a path escapes the workspace boundary."""
    pass


def resolve_workspace_path(workspace_root: Path, requested: str) -> Path:
    """Resolve a requested path within the workspace boundary.

    Handles:
      - Relative paths (resolved against workspace_root)
      - Absolute paths (must be within workspace_root)
      - Symlinks (resolved before containment check)
      - Drive-root escapes
      - UNC path escapes
      - ../../outside traversals

    Returns the resolved absolute path if it is within workspace_root.
    Raises WorkspaceSecurityError if the path escapes.
    """
    root = workspace_root.resolve()

    if not requested or not requested.strip():
        return root

    requested = requested.strip()

    # Handle absolute paths
    req_path = Path(requested)
    if req_path.is_absolute():
        candidate = req_path.resolve()
    else:
        candidate = (root / requested).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspaceSecurityError(
            f"Path escapes workspace: {requested!r} "
            f"(resolved to {candidate}, workspace is {root})"
        ) from exc

    return candidate


def is_within_workspace(workspace_root: Path, requested: str) -> bool:
    """Check if a path is within workspace without raising."""
    try:
        resolve_workspace_path(workspace_root, requested)
        return True
    except (WorkspaceSecurityError, Exception):
        return False
