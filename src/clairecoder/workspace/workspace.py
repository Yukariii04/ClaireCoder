"""Workspace abstraction responsible for project-root filesystem access (Correction #19 §1).

Enforces safe project-root operations:
- read_file(path)
- write_file(path, content)
- delete_file(path)
- exists(path)
- list_files(path, recursive=False)
- snapshot() and create_tracker() integration with ChangeTracker/ChangeSet
"""

import os
from pathlib import Path
from typing import List, Optional, Set, Union

from clairecoder.changeset.diff import is_binary_buffer
from clairecoder.changeset.tracker import (
    DEFAULT_IGNORED_DIRS,
    MAX_TEXT_FILE_SIZE,
    ChangeTracker,
    WorkspaceSnapshot,
)
from .errors import (
    WorkspaceBinaryFileError,
    WorkspaceFileNotFoundError,
    WorkspaceFileTooLargeError,
    WorkspaceIsADirectoryError,
    WorkspaceNotADirectoryError,
    WorkspacePathEscapeError,
    WorkspacePermissionError,
)
from .path_safety import is_within_workspace, normalize_workspace_path


class Workspace:
    """Encapsulates safe, project-root bounded filesystem operations."""

    def __init__(
        self,
        root: Union[str, Path],
        ignored_dirs: Optional[Set[str]] = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._ignored_dirs = set(ignored_dirs) if ignored_dirs is not None else set(DEFAULT_IGNORED_DIRS)

    @property
    def root(self) -> Path:
        """Authoritative project root directory."""
        return self._root

    def resolve_path(self, path: Union[str, Path]) -> Path:
        """Resolve a path strictly within the workspace boundary.

        Raises WorkspacePathEscapeError if the path escapes the workspace root.
        """
        return normalize_workspace_path(self._root, path)

    def is_within(self, path: Union[str, Path]) -> bool:
        """Check if a path is strictly inside the workspace boundary without raising."""
        return is_within_workspace(self._root, path)

    def relative_path(self, path: Union[str, Path]) -> str:
        """Return the normalized relative path string (forward slashes) from workspace root."""
        resolved = self.resolve_path(path)
        try:
            rel = resolved.relative_to(self._root)
            return str(rel).replace("\\", "/")
        except ValueError:
            return str(resolved).replace("\\", "/")

    def exists(self, path: Union[str, Path]) -> bool:
        """Check whether a path exists within the workspace boundary."""
        resolved = self.resolve_path(path)
        return resolved.exists()

    def is_file(self, path: Union[str, Path]) -> bool:
        """Check whether a path points to an existing regular file."""
        resolved = self.resolve_path(path)
        return resolved.is_file()

    def is_dir(self, path: Union[str, Path]) -> bool:
        """Check whether a path points to an existing directory."""
        resolved = self.resolve_path(path)
        return resolved.is_dir()

    def read_file(
        self,
        path: Union[str, Path],
        encoding: str = "utf-8",
        max_bytes: int = MAX_TEXT_FILE_SIZE,
    ) -> str:
        """Read a text file within the workspace boundary safely.

        Raises:
            WorkspacePathEscapeError: If path escapes the workspace.
            WorkspaceFileNotFoundError: If the file does not exist.
            WorkspaceIsADirectoryError: If the path is a directory.
            WorkspaceFileTooLargeError: If file exceeds max_bytes.
            WorkspaceBinaryFileError: If file contains binary content.
        """
        resolved = self.resolve_path(path)
        if not resolved.exists():
            raise WorkspaceFileNotFoundError(f"File not found: {path}")
        if resolved.is_dir():
            raise WorkspaceIsADirectoryError(f"Path is a directory, not a file: {path}")

        try:
            stat = resolved.stat()
        except OSError as e:
            raise WorkspacePermissionError(f"Cannot access file {path}: {e}") from e

        if stat.st_size > max_bytes:
            raise WorkspaceFileTooLargeError(
                f"File '{path}' ({stat.st_size} bytes) exceeds maximum size limit of {max_bytes} bytes"
            )

        try:
            with open(resolved, "rb") as f:
                chunk = f.read(min(8192, stat.st_size))
                if is_binary_buffer(chunk):
                    raise WorkspaceBinaryFileError(f"Cannot read binary file as text: {path}")
                f.seek(0)
                raw_bytes = f.read()
        except (WorkspaceBinaryFileError, WorkspaceFileTooLargeError):
            raise
        except OSError as e:
            raise WorkspacePermissionError(f"Failed to read file {path}: {e}") from e

        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError as exc:
            raise WorkspaceBinaryFileError(f"Cannot decode file '{path}' using {encoding}: {exc}") from exc

    def read_bytes(
        self,
        path: Union[str, Path],
        max_bytes: Optional[int] = None,
    ) -> bytes:
        """Read raw bytes from a file within the workspace boundary."""
        resolved = self.resolve_path(path)
        if not resolved.exists():
            raise WorkspaceFileNotFoundError(f"File not found: {path}")
        if resolved.is_dir():
            raise WorkspaceIsADirectoryError(f"Path is a directory, not a file: {path}")

        try:
            with open(resolved, "rb") as f:
                if max_bytes is not None:
                    return f.read(max_bytes)
                return f.read()
        except OSError as e:
            raise WorkspacePermissionError(f"Failed to read bytes from {path}: {e}") from e

    def write_file(
        self,
        path: Union[str, Path],
        content: Union[str, bytes],
        encoding: str = "utf-8",
    ) -> int:
        """Write content to a file within the workspace boundary.

        Automatically creates parent directories.
        Returns number of bytes written.
        """
        resolved = self.resolve_path(path)
        if resolved.exists() and resolved.is_dir():
            raise WorkspaceIsADirectoryError(f"Cannot write file; path is an existing directory: {path}")

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                data = content.encode(encoding)
            elif isinstance(content, (bytes, bytearray)):
                data = bytes(content)
            else:
                raise TypeError(f"Content must be str or bytes, got {type(content).__name__}")

            with open(resolved, "wb") as f:
                return f.write(data)
        except (WorkspaceIsADirectoryError, TypeError):
            raise
        except OSError as e:
            raise WorkspacePermissionError(f"Failed to write file {path}: {e}") from e

    def write_bytes(self, path: Union[str, Path], content: bytes) -> int:
        """Write raw bytes to a file within the workspace boundary."""
        return self.write_file(path, content)

    def delete_file(self, path: Union[str, Path]) -> bool:
        """Delete a file within the workspace boundary.

        Returns True on successful deletion.
        """
        resolved = self.resolve_path(path)
        if not resolved.exists():
            raise WorkspaceFileNotFoundError(f"File not found: {path}")
        if resolved.is_dir():
            raise WorkspaceIsADirectoryError(f"Cannot delete directory using delete_file: {path}")

        try:
            resolved.unlink()
            return True
        except OSError as e:
            raise WorkspacePermissionError(f"Failed to delete file {path}: {e}") from e

    def list_files(
        self,
        path: Union[str, Path] = "",
        recursive: bool = False,
    ) -> List[str]:
        """List files and directories within a workspace subpath with deterministic ordering.

        Args:
            path: Relative or absolute subpath to list (defaults to workspace root).
            recursive: If False (default), lists only direct children.
                       If True, walks subtrees while skipping ignored directories.

        Returns:
            Alphabetically sorted list of relative path strings (using forward slashes).
        """
        resolved = self.resolve_path(path)
        if not resolved.exists():
            raise WorkspaceFileNotFoundError(f"Path does not exist: {path}")
        if not resolved.is_dir():
            raise WorkspaceNotADirectoryError(f"Path is not a directory: {path}")

        result: List[str] = []

        if not recursive:
            try:
                for entry in sorted(resolved.iterdir(), key=lambda p: p.name):
                    if entry.name in self._ignored_dirs:
                        continue
                    # Return relative to the directory being queried
                    result.append(entry.name)
            except OSError as e:
                raise WorkspacePermissionError(f"Failed to list directory {path}: {e}") from e
            return sorted(result)

        # Recursive listing
        try:
            for dirpath, dirnames, filenames in os.walk(resolved):
                # Filter ignored directories in-place
                dirnames[:] = [
                    d for d in sorted(dirnames)
                    if d not in self._ignored_dirs and not d.startswith(".")
                ]
                for fname in sorted(filenames):
                    if fname.endswith((".pyc", ".pyo", ".zip")):
                        continue
                    full_p = os.path.join(dirpath, fname)
                    rel_p = os.path.relpath(full_p, resolved).replace("\\", "/")
                    result.append(rel_p)
        except OSError as e:
            raise WorkspacePermissionError(f"Failed during recursive walk of {path}: {e}") from e

        return sorted(result)

    def snapshot(self) -> WorkspaceSnapshot:
        """Capture and return a WorkspaceSnapshot reusing ChangeTracker infrastructure."""
        snap = WorkspaceSnapshot(str(self._root), ignored_dirs=self._ignored_dirs)
        snap.scan()
        return snap

    def create_tracker(self) -> ChangeTracker:
        """Create a ChangeTracker bound to this workspace root."""
        return ChangeTracker(workspace_root=str(self._root))
