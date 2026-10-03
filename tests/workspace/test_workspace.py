r"""Tests for Workspace abstraction and path safety (Correction #19).

Validates:
- read_file, write_file, delete_file, exists, list_files
- path traversal rejection
- absolute-path handling (within vs outside workspace)
- Windows path normalization
- workspace-root boundary enforcement
- missing file handling
- binary file handling
- snapshot / change tracker integration
"""

import os
from pathlib import Path
import pytest

from clairecoder.workspace import (
    Workspace,
    WorkspaceError,
    WorkspacePathEscapeError,
    WorkspaceFileNotFoundError,
    WorkspaceIsADirectoryError,
    WorkspaceBinaryFileError,
    normalize_workspace_path,
    is_within_workspace,
)


class TestPathSafety:
    """Tests for path safety and boundary checks."""

    def test_normalize_relative_path(self, tmp_path: Path):
        normalized = normalize_workspace_path("src/main.py", tmp_path)
        expected = (tmp_path / "src" / "main.py").resolve()
        assert normalized == expected

    def test_normalize_windows_separators(self, tmp_path: Path):
        normalized = normalize_workspace_path(r"src\nested\file.py", tmp_path)
        expected = (tmp_path / "src" / "nested" / "file.py").resolve()
        assert normalized == expected

    def test_normalize_mixed_separators(self, tmp_path: Path):
        normalized = normalize_workspace_path("src/nested\\file.py", tmp_path)
        expected = (tmp_path / "src" / "nested" / "file.py").resolve()
        assert normalized == expected

    def test_normalize_absolute_path_inside_workspace(self, tmp_path: Path):
        inside_file = tmp_path / "src" / "inside.py"
        normalized = normalize_workspace_path(str(inside_file), tmp_path)
        assert normalized == inside_file.resolve()

    def test_reject_relative_traversal_escaping_workspace(self, tmp_path: Path):
        with pytest.raises(WorkspacePathEscapeError) as exc_info:
            normalize_workspace_path("../../secret.txt", tmp_path)
        assert "escapes workspace" in str(exc_info.value).lower()
        assert exc_info.value.path == "../../secret.txt"

    def test_reject_nested_relative_traversal(self, tmp_path: Path):
        with pytest.raises(WorkspacePathEscapeError):
            normalize_workspace_path("subdir/../../secret.txt", tmp_path)

    def test_reject_absolute_path_outside_workspace(self, tmp_path: Path):
        outside_path = (tmp_path.parent / "outside_file.txt").resolve()
        with pytest.raises(WorkspacePathEscapeError) as exc_info:
            normalize_workspace_path(str(outside_path), tmp_path)
        assert "escapes workspace" in str(exc_info.value).lower()

    def test_is_within_workspace_helper(self, tmp_path: Path):
        inside = tmp_path / "a" / "b.txt"
        outside = tmp_path.parent / "other.txt"
        assert is_within_workspace(inside, tmp_path) is True
        assert is_within_workspace(outside, tmp_path) is False

    def test_empty_path_resolves_to_root(self, tmp_path: Path):
        resolved = normalize_workspace_path("", tmp_path)
        assert resolved == tmp_path.resolve()

    def test_dot_path_resolves_to_root(self, tmp_path: Path):
        resolved = normalize_workspace_path(".", tmp_path)
        assert resolved == tmp_path.resolve()


class TestWorkspaceOperations:
    """Tests for core Workspace filesystem operations."""

    @pytest.fixture
    def ws(self, tmp_path: Path) -> Workspace:
        return Workspace(root=tmp_path)

    def test_write_and_read_file(self, ws: Workspace):
        bytes_written = ws.write_file("hello.txt", "Hello World!")
        assert bytes_written > 0
        assert ws.exists("hello.txt")
        assert ws.is_file("hello.txt")
        content = ws.read_file("hello.txt")
        assert content == "Hello World!"

    def test_write_creates_parent_directories(self, ws: Workspace):
        ws.write_file("deep/nested/dir/file.py", "print('nested')")
        assert ws.exists("deep/nested/dir/file.py")
        assert ws.read_file("deep/nested/dir/file.py") == "print('nested')"

    def test_read_missing_file_raises_error(self, ws: Workspace):
        with pytest.raises(WorkspaceFileNotFoundError):
            ws.read_file("nonexistent.txt")

    def test_delete_file(self, ws: Workspace):
        ws.write_file("to_delete.txt", "bye")
        assert ws.exists("to_delete.txt")
        deleted = ws.delete_file("to_delete.txt")
        assert deleted is True
        assert not ws.exists("to_delete.txt")

    def test_delete_missing_file_raises_error(self, ws: Workspace):
        with pytest.raises(WorkspaceFileNotFoundError):
            ws.delete_file("ghost.txt")

    def test_exists_for_files_and_directories(self, ws: Workspace):
        assert not ws.exists("dir1")
        ws.write_file("dir1/test.txt", "data")
        assert ws.exists("dir1")
        assert ws.is_dir("dir1")
        assert ws.exists("dir1/test.txt")
        assert ws.is_file("dir1/test.txt")

    def test_path_traversal_rejection_on_read(self, ws: Workspace):
        with pytest.raises(WorkspacePathEscapeError):
            ws.read_file("../../secret.txt")

    def test_path_traversal_rejection_on_write(self, ws: Workspace):
        with pytest.raises(WorkspacePathEscapeError):
            ws.write_file("../forbidden.txt", "payload")

    def test_path_traversal_rejection_on_delete(self, ws: Workspace):
        with pytest.raises(WorkspacePathEscapeError):
            ws.delete_file("../../something.txt")

    def test_list_files_deterministic_ordering(self, ws: Workspace):
        ws.write_file("c.py", "c")
        ws.write_file("a.py", "a")
        ws.write_file("b.py", "b")
        files = ws.list_files()
        assert files == ["a.py", "b.py", "c.py"]

    def test_list_files_nested_non_recursive(self, ws: Workspace):
        ws.write_file("root.py", "r")
        ws.write_file("subdir/child1.py", "c1")
        ws.write_file("subdir/child2.py", "c2")

        # Non-recursive should list top level items
        top_items = ws.list_files(recursive=False)
        assert "root.py" in top_items
        assert "subdir" in top_items

    def test_list_files_nested_recursive(self, ws: Workspace):
        ws.write_file("z.py", "z")
        ws.write_file("dir_b/file.py", "b")
        ws.write_file("dir_a/file.py", "a")

        all_files = ws.list_files(recursive=True)
        # Should be sorted deterministically
        expected = sorted([
            "dir_a/file.py",
            "dir_b/file.py",
            "z.py"
        ])
        # Compare with forward-slash normalized paths
        normalized_all = [p.replace("\\", "/") for p in all_files]
        assert normalized_all == expected

    def test_binary_file_handling(self, ws: Workspace):
        binary_data = b"\x00\x01\x02\xff\xfe\xfd\x00\x00\x1b[31m"
        ws.write_bytes("binary.bin", binary_data)

        # Reading as text should raise WorkspaceBinaryFileError
        with pytest.raises(WorkspaceBinaryFileError):
            ws.read_file("binary.bin")

        # Reading as bytes should succeed
        read_back = ws.read_bytes("binary.bin")
        assert read_back == binary_data

    def test_read_directory_as_file_raises_error(self, ws: Workspace):
        ws.write_file("some_dir/f.txt", "content")
        with pytest.raises(WorkspaceIsADirectoryError):
            ws.read_file("some_dir")

    def test_relative_path_helper(self, ws: Workspace):
        abs_p = ws.root / "sub" / "file.txt"
        assert ws.relative_path(abs_p) == "sub/file.txt"

    def test_snapshot_and_change_tracker_integration(self, ws: Workspace):
        ws.write_file("initial.txt", "v1")
        tracker = ws.create_tracker()
        assert tracker is not None
        tracker.capture_before()

        ws.write_file("initial.txt", "v2")
        ws.write_file("created.txt", "new")

        changeset = tracker.capture_after(task_id="t1", run_id="r1")
        assert changeset is not None
        assert "initial.txt" in changeset.modified_paths
        assert "created.txt" in changeset.modified_paths
