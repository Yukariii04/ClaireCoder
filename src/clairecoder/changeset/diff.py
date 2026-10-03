"""Deterministic diff generation and line statistics.

Correction #16: Unified diff calculation between before and after file states.
Handles created, modified, deleted, unchanged, and binary files.
"""

import difflib
from typing import Optional, Tuple
from .types import ChangedFile, FileOperation


def is_binary_buffer(buffer: bytes) -> bool:
    """Check if byte buffer contains binary content (null bytes or non-UTF8)."""
    if b"\x00" in buffer:
        return True
    try:
        buffer.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def compute_unified_diff(
    path: str,
    old_content: Optional[str],
    new_content: Optional[str],
    existed_before: bool = True,
) -> Tuple[str, int, int]:
    """Compute unified diff string and return (diff, additions, deletions).

    Deterministic:
    - fromfile is 'a/{path}' if existed_before else '/dev/null'
    - tofile is 'b/{path}' if new_content is not None else '/dev/null'
    - No timestamps are included in headers
    """
    norm_path = path.replace("\\", "/")
    fromfile = f"a/{norm_path}" if existed_before else "/dev/null"
    tofile = f"b/{norm_path}" if new_content is not None else "/dev/null"

    old_text = (old_content.replace("\r\n", "\n").replace("\r", "\n")) if old_content is not None else None
    new_text = (new_content.replace("\r\n", "\n").replace("\r", "\n")) if new_content is not None else None

    old_lines = old_text.splitlines(keepends=True) if existed_before and old_text is not None else []
    new_lines = new_text.splitlines(keepends=True) if new_text is not None else []

    # Ensure last line ends with newline for clean diff generation
    old_lines_nl = [l if l.endswith("\n") else l + "\n" for l in old_lines]
    new_lines_nl = [l if l.endswith("\n") else l + "\n" for l in new_lines]

    diff_lines = list(
        difflib.unified_diff(
            old_lines_nl,
            new_lines_nl,
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )

    if not diff_lines:
        return "", 0, 0

    diff_text = "\n".join(diff_lines)
    additions = 0
    deletions = 0

    # Count additions and deletions from diff hunk lines (skip header lines --- and +++)
    for line in diff_lines[2:]:
        if line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1

    return diff_text, additions, deletions


def generate_file_diff(
    path: str,
    old_content: Optional[str],
    new_content: Optional[str],
    existed_before: bool,
    exists_after: Optional[bool] = None,
    is_binary: bool = False,
) -> Optional[ChangedFile]:
    """Generate a ChangedFile from before and after content.

    Returns None if the file is unchanged.
    """
    norm_path = path.replace("\\", "/")
    if exists_after is None:
        exists_after = (new_content is not None)

    # Check for unchanged file
    if existed_before and exists_after:
        if is_binary:
            if old_content is not None and old_content == new_content:
                return None
        else:
            if old_content is not None and new_content is not None:
                old_norm = old_content.replace("\r\n", "\n").replace("\r", "\n")
                new_norm = new_content.replace("\r\n", "\n").replace("\r", "\n")
                if old_norm == new_norm:
                    return None

    # Determine operation
    if not existed_before and exists_after:
        operation = FileOperation.CREATED
    elif existed_before and not exists_after:
        operation = FileOperation.DELETED
    elif existed_before and exists_after:
        operation = FileOperation.MODIFIED
    else:
        # File did not exist before and does not exist after
        return None

    # Binary handling
    if is_binary:
        fromfile = f"a/{norm_path}" if existed_before else "/dev/null"
        tofile = f"b/{norm_path}" if exists_after else "/dev/null"
        diff_text = f"Binary files {fromfile} and {tofile} differ"
        return ChangedFile(
            path=norm_path,
            operation=operation,
            old_content=None,
            new_content=None,
            additions=0,
            deletions=0,
            diff=diff_text,
            existed_before=existed_before,
            is_binary=True,
        )

    # Normalize text content for clean storage
    norm_old = (old_content.replace("\r\n", "\n").replace("\r", "\n")) if old_content is not None else None
    norm_new = (new_content.replace("\r\n", "\n").replace("\r", "\n")) if new_content is not None else None

    # Text diff
    diff_text, additions, deletions = compute_unified_diff(
        path=norm_path,
        old_content=norm_old,
        new_content=norm_new,
        existed_before=existed_before,
    )

    return ChangedFile(
        path=norm_path,
        operation=operation,
        old_content=norm_old,
        new_content=norm_new,
        additions=additions,
        deletions=deletions,
        diff=diff_text,
        existed_before=existed_before,
        is_binary=False,
    )
