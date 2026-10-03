r"""Centralized path normalization and boundary checking (Correction #19 §2).

Provides authoritative path security:
- relative paths
- absolute paths
- '..' directory traversal attempts
- symlinks pointing outside workspace
- Windows path separators (\ and /)
- nonexistent paths

The final resolved path must strictly remain inside the configured workspace root.
Never silently rewrites an unsafe path into another location.
"""

from pathlib import Path
from typing import Optional, Union
from .errors import WorkspacePathEscapeError, WorkspaceSecurityError


def _resolve_root_and_target(
    arg1: Union[str, Path],
    arg2: Union[str, Path],
) -> tuple[Path, str]:
    """Disambiguate root and requested target between two positional arguments.

    Supports both (workspace_root, requested) and (requested, workspace_root)
    calling conventions cleanly and deterministically.
    """
    p1 = Path(arg1) if isinstance(arg1, (str, Path)) else Path(str(arg1))
    p2 = Path(arg2) if isinstance(arg2, (str, Path)) else Path(str(arg2))

    # If one is relative and one is absolute, the absolute one is the workspace root
    if not p1.is_absolute() and p2.is_absolute():
        return p2.resolve(), str(arg1).strip()
    if not p2.is_absolute() and p1.is_absolute():
        return p1.resolve(), str(arg2).strip()

    # If both are absolute: check if one is an existing directory
    if not p1.is_dir() and p2.is_dir():
        return p2.resolve(), str(arg1).strip()
    if not p2.is_dir() and p1.is_dir():
        return p1.resolve(), str(arg2).strip()

    # If both are directories or both non-directories:
    # Check if p2 is inside p1
    try:
        p2.resolve().relative_to(p1.resolve())
        return p1.resolve(), str(arg2).strip()
    except ValueError:
        pass

    try:
        p1.resolve().relative_to(p2.resolve())
        return p2.resolve(), str(arg1).strip()
    except ValueError:
        pass

    # Default fallback: arg1 is root, arg2 is requested
    return p1.resolve(), str(arg2).strip()


def normalize_workspace_path(
    arg1: Union[str, Path],
    arg2: Union[str, Path],
) -> Path:
    """Normalize and validate that a requested path strictly remains inside workspace root.

    Accepts either (workspace_root, requested) or (requested, workspace_root).

    Returns:
        Resolved absolute Path strictly within workspace_root.

    Raises:
        WorkspacePathEscapeError: If the resolved path escapes the workspace root boundary.
    """
    root, req_str = _resolve_root_and_target(arg1, arg2)

    if not req_str or req_str in (".", "./", ".\\"):
        return root

    req_path = Path(req_str)

    if req_path.is_absolute():
        candidate = req_path.resolve()
    else:
        candidate = (root / req_path).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspacePathEscapeError(
            f"Path escapes workspace boundary: {req_str!r} "
            f"(resolved to {candidate}, workspace root is {root})",
            path=req_str,
        ) from exc

    return candidate


def is_within_workspace(
    arg1: Union[str, Path],
    arg2: Union[str, Path],
) -> bool:
    """Check whether a requested path is safely within workspace root without raising."""
    try:
        normalize_workspace_path(arg1, arg2)
        return True
    except (WorkspacePathEscapeError, WorkspaceSecurityError, Exception):
        return False
