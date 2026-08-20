"""Stage 6 Correction #10 Comprehensive Test Suite.

Authorities: CC-PRD-011, CC-ADR-007, TUI-DESIGN.md, CLI-TUI-DESKTOP-ROADMAP.md.

Covers:
1. Real workspace filesystem discovery & normalized data model
2. Interactive Tree Navigation (expansion/collapse, selection marker, glyphs, scrolling, viewport bounds)
3. Direct Secondary-View Navigation (Ctrl+T, Ctrl+R, Ctrl+P, Esc, direct replacement, focus ownership)
4. Slash Command Suggestions (trigger rules, slash+space, command+space, prose, selection, acceptance, dismissal)
"""
import os
import stat
from pathlib import Path
from typing import List

import pytest

from clairecoder.tui.tree import (
    FileTreeItem,
    FileTreeOverlay,
    scan_workspace,
    _MAX_DEPTH,
    _MAX_ENTRIES_PER_DIR,
    _IGNORED_DIRS,
)
from clairecoder.tui.app import TuiApplication
from clairecoder.tui.states import InputState, TerminalMode
from clairecoder.tui.terminal import TerminalCapability


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_tree(root: Path, spec: dict) -> None:
    """Recursively create files/dirs from a nested dict spec."""
    for name, val in spec.items():
        p = root / name.rstrip("/")
        if isinstance(val, dict):
            p.mkdir(parents=True, exist_ok=True)
            _make_tree(p, val)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(val or "", encoding="utf-8")


# ── 1. scan_workspace & Data Model ──────────────────────────────────────────

class TestScanWorkspace:

    def test_basic_discovery(self, tmp_path):
        """Scanner discovers files and directories at the root level."""
        _make_tree(tmp_path, {
            "src/": {"main.py": "# main", "utils.py": "# utils"},
            "README.md": "# Readme",
            "pyproject.toml": "",
        })
        items = scan_workspace(tmp_path)
        names = [i.name for i in items]
        assert names == ["src", "pyproject.toml", "README.md"]

    def test_ordering_dirs_first_alpha(self, tmp_path):
        """Directories come before files; within each group, alphabetical."""
        _make_tree(tmp_path, {
            "zebra/": {},
            "alpha/": {},
            "z_file.txt": "",
            "a_file.txt": "",
        })
        items = scan_workspace(tmp_path)
        names = [i.name for i in items]
        assert names == ["alpha", "zebra", "a_file.txt", "z_file.txt"]

    def test_recursive_children_collapsed_by_default(self, tmp_path):
        """Children are discovered recursively and child directories default to expanded=False."""
        _make_tree(tmp_path, {
            "pkg/": {
                "sub/": {"deep.py": ""},
                "top.py": "",
            },
        })
        items = scan_workspace(tmp_path)
        assert len(items) == 1
        pkg = items[0]
        assert pkg.is_directory
        assert pkg.expanded is False
        child_names = [c.name for c in pkg.children]
        assert child_names == ["sub", "top.py"]
        assert pkg.children[0].children[0].name == "deep.py"

    def test_ignored_dirs_excluded(self, tmp_path):
        """Directories in _IGNORED_DIRS are skipped."""
        _make_tree(tmp_path, {
            "__pycache__/": {"bytecode.pyc": ""},
            ".git/": {"HEAD": ""},
            "node_modules/": {"index.js": ""},
            "real_code/": {"app.py": ""},
        })
        items = scan_workspace(tmp_path)
        names = [i.name for i in items]
        assert "real_code" in names
        assert "__pycache__" not in names
        assert ".git" not in names
        assert "node_modules" not in names

    def test_egg_info_excluded(self, tmp_path):
        """*.egg-info directories are excluded."""
        (tmp_path / "mypackage.egg-info").mkdir()
        (tmp_path / "keep.txt").write_text("ok", encoding="utf-8")
        items = scan_workspace(tmp_path)
        names = [i.name for i in items]
        assert "keep.txt" in names
        assert "mypackage.egg-info" not in names

    def test_missing_root(self, tmp_path):
        """Non-existent root returns empty list without raising."""
        items = scan_workspace(tmp_path / "nonexistent")
        assert items == []

    def test_empty_dir(self, tmp_path):
        """Empty directory returns empty list."""
        items = scan_workspace(tmp_path)
        assert items == []

    def test_max_depth_honoured(self, tmp_path):
        """Scanning stops at _MAX_DEPTH levels."""
        current = tmp_path
        for i in range(_MAX_DEPTH + 2):
            current = current / f"level_{i}"
            current.mkdir()
        (current / "unreachable.txt").write_text("too deep", encoding="utf-8")

        items = scan_workspace(tmp_path)
        node = items
        for i in range(_MAX_DEPTH):
            if not node:
                break
            found = [n for n in node if n.is_directory]
            node = found[0].children if found else []
        assert node == []

    def test_max_entries_per_dir(self, tmp_path):
        """Only _MAX_ENTRIES_PER_DIR entries are returned per directory."""
        for i in range(_MAX_ENTRIES_PER_DIR + 50):
            (tmp_path / f"file_{i:04d}.txt").write_text("", encoding="utf-8")
        items = scan_workspace(tmp_path)
        assert len(items) == _MAX_ENTRIES_PER_DIR

    @pytest.mark.skipif(os.name == "nt", reason="Unix-only permission test")
    def test_permission_error_graceful(self, tmp_path):
        """Permission errors during listing are silently skipped."""
        no_read = tmp_path / "locked"
        no_read.mkdir()
        (no_read / "secret.txt").write_text("secret", encoding="utf-8")
        no_read.chmod(0o000)
        try:
            items = scan_workspace(tmp_path)
            locked = [i for i in items if i.name == "locked"]
            assert len(locked) == 1
            assert locked[0].children == []
        finally:
            no_read.chmod(stat.S_IRWXU)


class TestFileTreeItem:

    def test_defaults(self):
        item = FileTreeItem(name="foo.py", path="/a/foo.py")
        assert item.is_directory is False
        assert item.children == []
        assert item.status == ""
        assert item.expanded is False

    def test_directory_with_children(self):
        child = FileTreeItem(name="bar.py", path="/a/src/bar.py")
        parent = FileTreeItem(name="src", path="/a/src", is_directory=True, children=[child], expanded=True)
        assert parent.is_directory
        assert parent.expanded is True
        assert len(parent.children) == 1
        assert parent.children[0].name == "bar.py"


# ── 2. Interactive File Tree Navigation & Viewport ──────────────────────────

class TestFileTreeOverlayInteractive:

    def test_root_expanded_child_dirs_collapsed_initially(self, tmp_path):
        """Workspace root starts expanded; child directories start collapsed."""
        _make_tree(tmp_path, {
            "docs/": {"guide.md": ""},
            "src/": {"app.py": ""},
            "README.md": "",
        })
        overlay = FileTreeOverlay(workspace_root=str(tmp_path))
        lines = overlay.render(mode=TerminalMode.FULL, width=58)
        full = "\n".join(lines)

        # Root and top-level dirs/files visible
        assert f"{tmp_path.name}/" in full
        assert "docs/" in full
        assert "src/" in full
        assert "README.md" in full
        # Deep children not yet visible because child dirs are collapsed
        assert "guide.md" not in full
        assert "app.py" not in full

    def test_selection_marker_and_expansion_glyphs(self, tmp_path):
        """Selected row gets visible '▶ ' selector; expanded dirs get '▾ ' glyph."""
        _make_tree(tmp_path, {
            "docs/": {"guide.md": ""},
            "README.md": "",
        })
        overlay = FileTreeOverlay(workspace_root=str(tmp_path))
        lines = overlay.render(mode=TerminalMode.FULL, width=58)

        # Row 0 (root) is selected by default
        assert any("▶ " in l and f"{tmp_path.name}/" in l for l in lines)

        # Move selection to docs/ (index 1) and expand it
        overlay.handle_key("down")
        assert overlay.selected_index == 1
        overlay.handle_key("enter")  # Toggle expand

        lines_expanded = overlay.render(mode=TerminalMode.FULL, width=58)
        full_expanded = "\n".join(lines_expanded)
        # Selection marker is on docs/
        assert any("▶ " in l and "docs/" in l for l in lines_expanded)
        # Expansion glyph ▾ appears for docs/
        assert "▾ docs/" in full_expanded
        # guide.md is now visible
        assert "guide.md" in full_expanded

    def test_enter_expand_and_collapse(self, tmp_path):
        """Enter toggles directory expansion; does not crash on files."""
        _make_tree(tmp_path, {
            "src/": {"main.py": ""},
            "README.md": "",
        })
        overlay = FileTreeOverlay(workspace_root=str(tmp_path))
        # Move to src/
        overlay.handle_key("down")
        assert overlay.selected_item.name == "src"
        assert overlay.selected_item.expanded is False

        # Enter -> expands
        overlay.handle_key("enter")
        assert overlay.selected_item.expanded is True
        assert any(r.item.name == "main.py" for r in overlay.items)

        # Enter again -> collapses
        overlay.handle_key("enter")
        assert overlay.selected_item.expanded is False
        assert not any(r.item.name == "main.py" for r in overlay.items)

        # Move to README.md (file) and press Enter -> no crash
        overlay.handle_key("down")
        assert overlay.selected_item.name == "README.md"
        overlay.handle_key("enter")
        assert overlay.selected_item.name == "README.md"

    def test_left_right_tree_navigation(self, tmp_path):
        """Right expands directory / steps into child; Left collapses / steps to parent."""
        _make_tree(tmp_path, {
            "src/": {"main.py": ""},
        })
        overlay = FileTreeOverlay(workspace_root=str(tmp_path))
        overlay.handle_key("down")  # on src/ (collapsed)

        # Right expands
        overlay.handle_key("right")
        assert overlay.selected_item.name == "src"
        assert overlay.selected_item.expanded is True

        # Right again steps into first child
        overlay.handle_key("right")
        assert overlay.selected_item.name == "main.py"

        # Left on child steps back to parent (src/)
        overlay.handle_key("left")
        assert overlay.selected_item.name == "src"

        # Left on expanded directory collapses it
        overlay.handle_key("left")
        assert overlay.selected_item.expanded is False

    def test_pageup_pagedown_home_end(self, tmp_path):
        """PageUp, PageDown, Home, End navigate the visible items."""
        # Create 20 files
        spec = {f"file_{i:02d}.txt": "" for i in range(20)}
        _make_tree(tmp_path, spec)
        overlay = FileTreeOverlay(workspace_root=str(tmp_path), viewport_height=10)

        assert overlay.selected_index == 0
        overlay.handle_key("pagedown")
        assert overlay.selected_index == 10

        overlay.handle_key("end")
        assert overlay.selected_index == len(overlay.items) - 1

        overlay.handle_key("home")
        assert overlay.selected_index == 0

        overlay.handle_key("pageup")
        assert overlay.selected_index == 0

    def test_viewport_scroll_and_fixed_card_height(self, tmp_path):
        """Card height remains exactly 16 lines while scrolling internally."""
        spec = {f"file_{i:02d}.txt": "" for i in range(30)}
        _make_tree(tmp_path, spec)
        overlay = FileTreeOverlay(workspace_root=str(tmp_path), viewport_height=10)

        # Render initially
        lines_top = overlay.render(mode=TerminalMode.FULL, width=58)
        assert len(lines_top) == 16
        assert "file_00.txt" in "\n".join(lines_top)

        # Scroll down to the bottom
        overlay.handle_key("end")
        assert overlay.scroll_position > 0
        lines_bot = overlay.render(mode=TerminalMode.FULL, width=58)
        assert len(lines_bot) == 16
        assert "file_29.txt" in "\n".join(lines_bot)

    def test_keyboard_hints_footer(self, tmp_path):
        """Card visibly displays the required navigation hints."""
        _make_tree(tmp_path, {"a.txt": ""})
        overlay = FileTreeOverlay(workspace_root=str(tmp_path))
        lines = overlay.render(mode=TerminalMode.FULL, width=58)
        full = "\n".join(lines)
        assert "select" in full
        assert "expand/collapse" in full
        assert "tree" in full
        assert "scroll" in full
        assert "Esc back" in full


# ── 3. Direct Secondary-View Navigation & Focus Ownership ───────────────────

class TestSecondaryViewNavigationAndFocus:

    def test_direct_secondary_view_switching(self, tmp_path):
        """Ctrl+T, Ctrl+R, Ctrl+P switch directly between secondary views without Esc."""
        term = TerminalCapability(width=104, height=30)
        app = TuiApplication(terminal=term, workspace_root=str(tmp_path))
        assert app.state == InputState.NORMAL
        assert app.active_overlay is None

        # 1. Main -> Tree
        app.handle_key("ctrl+t")
        assert app.is_tree_open
        assert app.state == InputState.OVERLAY

        # 2. Tree -> Review (direct)
        app.handle_key("ctrl+r")
        assert app.is_review_open
        assert not app.is_tree_open
        assert app.state == InputState.OVERLAY

        # 3. Review -> Task (direct)
        app.handle_key("ctrl+p")
        assert app.is_task_open
        assert not app.is_review_open
        assert app.state == InputState.OVERLAY

        # 4. Task -> Tree (direct)
        app.handle_key("ctrl+t")
        assert app.is_tree_open
        assert not app.is_task_open
        assert app.state == InputState.OVERLAY

        # 5. Tree -> Main (Esc)
        app.handle_key("\x1b")
        assert app.active_overlay is None
        assert app.state == InputState.NORMAL

    def test_palette_direct_switch_to_other_views(self, tmp_path):
        """Palette can directly switch to Tree, Review, Task via Ctrl+T/R/P."""
        app = TuiApplication(workspace_root=str(tmp_path))
        app.open_palette()
        assert app.is_palette_open

        app.handle_key("ctrl+r")
        assert app.is_review_open
        assert not app.is_palette_open

    def test_secondary_views_absorb_keys_no_prompt_leak(self, tmp_path):
        """Typing alphanumeric characters in secondary views does not feed Main prompt."""
        app = TuiApplication(workspace_root=str(tmp_path))
        app.open_tree()
        assert app.is_tree_open

        # Type letters that shouldn't leak to prompt
        app.handle_key("x")
        app.handle_key("y")
        app.handle_key("z")
        assert app.prompt.get_text() == ""

        # Close overlay -> prompt still empty
        app.handle_key("\x1b")
        assert app.state == InputState.NORMAL
        assert app.prompt.get_text() == ""

        # Now typing in normal state goes into prompt
        app.handle_key("a")
        app.handle_key("b")
        assert app.prompt.get_text() == "ab"


# ── 4. Slash Command Suggestions ────────────────────────────────────────────

class TestSlashCommandSuggestions:

    def test_slash_trigger_and_filtering(self):
        """Slash suggestions open on '/', filter on prefix, and close on space/prose."""
        app = TuiApplication()

        # Empty prompt -> not active
        assert not app.is_slash_suggestions_active()
        assert app.get_slash_suggestions() == []

        # '/' -> active, all commands
        app.prompt.set_text("/")
        assert app.is_slash_suggestions_active()
        assert "/model" in app.get_slash_suggestions()
        assert "/mode" in app.get_slash_suggestions()
        assert "/tree" in app.get_slash_suggestions()

        # '/m' -> active, filtered
        app.prompt.set_text("/m")
        assert app.is_slash_suggestions_active()
        assert app.get_slash_suggestions() == ["/mode", "/model"]

        # '/mo' -> active, filtered
        app.prompt.set_text("/mo")
        assert app.is_slash_suggestions_active()
        assert app.get_slash_suggestions() == ["/mode", "/model"]

        # '/model' -> active
        app.prompt.set_text("/model")
        assert app.is_slash_suggestions_active()
        assert app.get_slash_suggestions() == ["/model"]

    def test_slash_space_rule_closes_suggestions(self):
        """Slash followed by space immediately closes suggestions."""
        app = TuiApplication()

        for text in ["/ ", "/ '", "/ model", "/ mode", "/ hello", "/ anything"]:
            app.prompt.set_text(text)
            assert not app.is_slash_suggestions_active(), f"Expected closed for {text!r}"
            assert app.get_slash_suggestions() == []

    def test_command_space_rule_closes_suggestions(self):
        """Command followed by space (arguments mode) closes suggestions."""
        app = TuiApplication()

        for text in ["/model ", "/mode ", "/model foo", "/tree src"]:
            app.prompt.set_text(text)
            assert not app.is_slash_suggestions_active(), f"Expected closed for {text!r}"
            assert app.get_slash_suggestions() == []

    def test_normal_prose_does_not_trigger_suggestions(self):
        """Slashes inside normal sentences or URLs never open suggestions."""
        app = TuiApplication()

        for text in [
            "hello /world",
            "path /src",
            "https://example.com",
            "explain /src/parser.py",
            "visit https://example.com/?x=1",
            "the ratio is / 2",
        ]:
            app.prompt.set_text(text)
            assert not app.is_slash_suggestions_active(), f"Expected closed for {text!r}"
            assert app.get_slash_suggestions() == []

    def test_suggestion_navigation_and_acceptance(self):
        """Up/Down selects in suggestion list; Enter accepts suggestion into prompt."""
        app = TuiApplication()
        app.prompt.set_text("/mo")
        # Matches: ["/mode", "/model"]
        assert app._slash_selected_index == 0

        # Down -> selects /model
        app.handle_key("down")
        assert app._slash_selected_index == 1

        # Enter -> accepts /model into prompt
        app.handle_key("enter")
        assert app.prompt.get_text() == "/model"
        assert not app.is_slash_suggestions_active()

    def test_suggestion_escape_dismisses_preserves_text(self):
        """Esc dismisses suggestions popup while preserving prompt text."""
        app = TuiApplication()
        app.prompt.set_text("/mo")
        assert app.is_slash_suggestions_active()

        # Esc dismisses suggestions
        app.handle_key("\x1b")
        assert not app.is_slash_suggestions_active()
        assert app.prompt.get_text() == "/mo"

        # Further typing restores suggestion capability
        app.handle_key("d")
        assert app.prompt.get_text() == "/mod"
        assert app.is_slash_suggestions_active()

    def test_suggestion_render_preserves_frame_height(self):
        """Rendering with active suggestions does not expand outer frame."""
        term = TerminalCapability(width=104, height=30)
        app = TuiApplication(terminal=term)

        # Baseline frame height
        lines_baseline = app.render()
        baseline_h = len(lines_baseline)

        # Open suggestions
        app.prompt.set_text("/m")
        assert app.is_slash_suggestions_active()

        lines_with_sugg = app.render()
        assert len(lines_with_sugg) == baseline_h
        full_sugg = "\n".join(lines_with_sugg)
        assert "Suggestions" in full_sugg
        assert "/mode" in full_sugg
        assert "/model" in full_sugg
