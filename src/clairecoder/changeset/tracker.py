"""Workspace state snapshotting and ChangeTracker.

Correction #16: Non-invasive workspace snapshotting before and after task execution.
Calculates unified diffs and ChangeSets deterministically with binary and unreadable file safety.
"""

import hashlib
import os
import uuid
from typing import Dict, List, Optional, Set

from .types import ChangeSet, ChangedFile, ChangeSetStatus
from .diff import generate_file_diff, is_binary_buffer

# Standard directories ignored from workspace file tracking
DEFAULT_IGNORED_DIRS: Set[str] = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "env",
    ".clairecoder",
    ".gemini",
    "node_modules",
    "dist",
    "build",
    ".eggs",
}

# Maximum file size for text content capture (5 MB)
MAX_TEXT_FILE_SIZE = 5 * 1024 * 1024


class FileSnapshot:
    """Snapshot state of a single file."""
    def __init__(
        self,
        rel_path: str,
        mtime: float,
        size: int,
        is_binary: bool,
        content: Optional[str] = None,
        content_hash: Optional[str] = None,
    ) -> None:
        self.rel_path = rel_path.replace("\\", "/")
        self.mtime = mtime
        self.size = size
        self.is_binary = is_binary
        self.content = content
        self.content_hash = content_hash


class WorkspaceSnapshot:
    """Snapshot of files across a workspace root directory."""

    def __init__(self, root: str, ignored_dirs: Optional[Set[str]] = None) -> None:
        self.root = os.path.abspath(root) if root else os.getcwd()
        self.ignored_dirs = ignored_dirs if ignored_dirs is not None else DEFAULT_IGNORED_DIRS
        self.files: Dict[str, FileSnapshot] = {}

    def scan(self) -> None:
        """Scan workspace root and record file metadata and content."""
        if not os.path.exists(self.root) or not os.path.isdir(self.root):
            return

        for dirpath, dirnames, filenames in os.walk(self.root):
            # Prune ignored directories in-place
            dirnames[:] = [d for d in dirnames if d not in self.ignored_dirs and not d.startswith(".")]

            for fname in filenames:
                # Ignore zip, pyc, coverage artifacts
                if fname.endswith((".pyc", ".pyo", ".zip")):
                    continue

                full_path = os.path.join(dirpath, fname)
                try:
                    rel_path = os.path.relpath(full_path, self.root).replace("\\", "/")
                    stat = os.stat(full_path)
                except (OSError, ValueError):
                    continue

                size = stat.st_size
                mtime = stat.st_mtime

                # Check if file is large (> MAX_TEXT_FILE_SIZE) -> treat as binary
                if size > MAX_TEXT_FILE_SIZE:
                    self.files[rel_path] = FileSnapshot(
                        rel_path=rel_path,
                        mtime=mtime,
                        size=size,
                        is_binary=True,
                        content=None,
                        content_hash=f"size_{size}_mtime_{mtime}",
                    )
                    continue

                # Read sample to check binary
                try:
                    with open(full_path, "rb") as f:
                        data = f.read()
                        is_bin = is_binary_buffer(data[:8192])
                        content_hash = hashlib.sha256(data).hexdigest()

                        if is_bin:
                            self.files[rel_path] = FileSnapshot(
                                rel_path=rel_path,
                                mtime=mtime,
                                size=size,
                                is_binary=True,
                                content=None,
                                content_hash=content_hash,
                            )
                        else:
                            raw = data.decode("utf-8", errors="replace")
                            content = raw.replace("\r\n", "\n").replace("\r", "\n")
                            self.files[rel_path] = FileSnapshot(
                                rel_path=rel_path,
                                mtime=mtime,
                                size=size,
                                is_binary=False,
                                content=content,
                                content_hash=content_hash,
                            )
                except (OSError, PermissionError):
                    # Unreadable file handled safely
                    self.files[rel_path] = FileSnapshot(
                        rel_path=rel_path,
                        mtime=mtime,
                        size=size,
                        is_binary=True,
                        content=None,
                        content_hash=None,
                    )


class ChangeTracker:
    """Tracks file changes between before and after snapshots."""

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = workspace_root or os.getcwd()
        self._before_snapshot: Optional[WorkspaceSnapshot] = None
        self._after_snapshot: Optional[WorkspaceSnapshot] = None

    def scan_workspace(self) -> WorkspaceSnapshot:
        """Scan and return a current snapshot of the workspace."""
        snapshot = WorkspaceSnapshot(self.workspace_root)
        snapshot.scan()
        return snapshot

    def capture_before(self) -> None:
        """Capture the workspace state before task execution."""
        self._before_snapshot = self.scan_workspace()

    def capture_after(
        self,
        task_id: str,
        run_id: Optional[str] = None,
        changeset_id: Optional[str] = None,
    ) -> ChangeSet:
        """Capture the workspace state after task execution and return a ChangeSet."""
        after_snapshot = self.scan_workspace()
        self._after_snapshot = after_snapshot

        before_files = self._before_snapshot.files if self._before_snapshot else {}
        after_files = after_snapshot.files

        all_paths = sorted(set(before_files.keys()) | set(after_files.keys()))
        changed_files: List[ChangedFile] = []

        for path in all_paths:
            in_before = path in before_files
            in_after = path in after_files

            old_snap = before_files.get(path)
            new_snap = after_files.get(path)

            old_content = old_snap.content if old_snap else None
            new_content = new_snap.content if new_snap else None

            is_binary = False
            if old_snap and old_snap.is_binary:
                is_binary = True
            elif new_snap and new_snap.is_binary:
                is_binary = True

            # If both exist and hashes match, skip diff
            if in_before and in_after:
                if old_snap.content_hash and new_snap.content_hash:
                    if old_snap.content_hash == new_snap.content_hash:
                        continue
                elif old_content == new_content and not is_binary:
                    continue

            change = generate_file_diff(
                path=path,
                old_content=old_content,
                new_content=new_content,
                existed_before=in_before,
                exists_after=in_after,
                is_binary=is_binary,
            )
            if change is not None:
                changed_files.append(change)

        cid = changeset_id or f"cs_{uuid.uuid4().hex[:8]}"
        return ChangeSet(
            id=cid,
            task_id=task_id,
            run_id=run_id,
            files=changed_files,
            status=ChangeSetStatus.APPLIED,
        )
