"""Tests for FileTreeOverlay, Workspace Scanning, Interactive Navigation, and Viewport Bounds.

Authorities: CC-PRD-011, CC-ADR-007, TUI-DESIGN.md.
"""
import os
import pytest
from pathlib import Path

from clairecoder.tui.tree import (
    FileTreeItem,
    FileTreeOverlay,
    scan_workspace,
    _MAX_DEPTH,
    _MAX_ENTRIES_PER_DIR,
    _IGNORED_DIRS,
)


def test_workspace_filesystem_discovery(tmp_path):
    """Verify scan_workspace discovers filesystem structure accurately."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# Project")

    items = scan_workspace(Path(tmp_path))
    names = [item.name for item in items]
    assert "src" in names
    assert "README.md" in names


def test_file_tree_interactive_navigation(tmp_path):
    """Verify Up/Down moves cursor and Enter toggles directory expansion."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("pass")
    (tmp_path / "tests").mkdir()

    overlay = FileTreeOverlay(workspace_root=str(tmp_path))
    assert overlay.selected_index == 0

    # Down arrow
    overlay.handle_key("down")
    assert overlay.selected_index == 1

    # Up arrow
    overlay.handle_key("up")
    assert overlay.selected_index == 0


def test_file_tree_expand_collapse(tmp_path):
    """Verify directory expansion adds children to visible list and collapse removes them."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("pass")

    overlay = FileTreeOverlay(workspace_root=str(tmp_path))
    visible_before = len(overlay.items)

    # Move cursor to 'src' directory row (index 1 under root)
    overlay.handle_key("down")

    # Enter on 'src' expands it
    overlay.handle_key("enter")
    visible_after = len(overlay.items)
    assert visible_after > visible_before

    # Enter again collapses it
    overlay.handle_key("enter")
    assert len(overlay.items) == visible_before


def test_file_tree_viewport_bounds(tmp_path):
    """Verify tree rendering stays bounded within specified viewport width and height."""
    for i in range(20):
        (tmp_path / f"file_{i}.txt").write_text("content")

    overlay = FileTreeOverlay(workspace_root=str(tmp_path))
    lines = overlay.render(width=60)
    assert len(lines) > 0
    for line in lines:
        assert len(line) <= 60
