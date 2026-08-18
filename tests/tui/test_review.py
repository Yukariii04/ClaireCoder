"""Unit tests for the TUI Review / Changes overlay (CLI/TUI Stage 4)."""
import pytest
from unittest.mock import Mock

from clairecoder.tui.states import TerminalMode
from clairecoder.tui.diff import FileDiff
from clairecoder.tui.activity import DiffLine
from clairecoder.tui.review import ReviewOverlay

def test_review_overlay_totals():
    """Verify calculation of total files, insertions, and deletions."""
    files = [
        FileDiff("src/decoder.py", additions=18, deletions=4),
        FileDiff("src/router.py", additions=6, deletions=0, is_new=True),
        FileDiff("tests/test_decoder.py", additions=22, deletions=0),
    ]
    overlay = ReviewOverlay(files=files)
    assert overlay.total_files_changed == 3
    assert overlay.total_insertions == 46
    assert overlay.total_deletions == 4

def test_review_overlay_render_full():
    """Verify full card rendering matches TUI-DESIGN.md §13."""
    files = [
        FileDiff("src/decoder.py", additions=18, deletions=4),
        FileDiff("src/router.py", additions=6, deletions=0, is_new=True),
        FileDiff("tests/test_decoder.py", additions=22, deletions=0),
    ]
    overlay = ReviewOverlay(files=files)
    lines = overlay.render(mode=TerminalMode.FULL, width=80)
    text = "\n".join(lines)

    assert "Changes this session" in text
    assert "src/decoder.py" in text
    assert "+18 -4" in text
    assert "src/router.py" in text
    assert "(new)" in text
    assert "3 files changed" in text
    assert "46 insertions(+)" in text
    assert "4 deletions(-)" in text
    assert "[enter] view diff" in text
    assert "[c] commit" in text
    assert "[q] back" in text

def test_review_overlay_navigation_and_diff_toggle():
    """Verify arrow navigation and diff viewing on Enter."""
    files = [
        FileDiff("src/a.py", additions=1, deletions=0, lines=[DiffLine("add", "def a(): pass")]),
        FileDiff("src/b.py", additions=2, deletions=1, lines=[DiffLine("add", "def b(): pass")]),
    ]
    overlay = ReviewOverlay(files=files)
    assert overlay.selected_index == 0
    assert overlay.selected_file.file_path == "src/a.py"

    # Select next (Down / j)
    overlay.handle_key("j")
    assert overlay.selected_index == 1
    assert overlay.selected_file.file_path == "src/b.py"

    # Select prev (Up / k)
    overlay.handle_key("k")
    assert overlay.selected_index == 0

    # Toggle view diff on Enter
    assert not overlay.showing_diff
    overlay.handle_key("Enter")
    assert overlay.showing_diff

    # Verify rendered diff contains file lines
    diff_text = "\n".join(overlay.render(mode=TerminalMode.FULL))
    assert "Diff for: src/a.py" in diff_text
    assert "def a(): pass" in diff_text
    assert "[enter/q] back to file list" in diff_text

    # Back to file list on Enter or q
    overlay.handle_key("Enter")
    assert not overlay.showing_diff

def test_review_overlay_close_callback():
    """Verify q / Esc triggers on_close callback."""
    overlay = ReviewOverlay()
    mock_close = Mock()
    overlay.on_close = mock_close

    overlay.handle_key("q")
    mock_close.assert_called_once()

    mock_close.reset_mock()
    overlay.handle_key("Esc")
    mock_close.assert_called_once()

def test_review_overlay_compact_and_minimal_modes():
    """Verify fallback rendering in compact and minimal modes."""
    files = [FileDiff("src/decoder.py", additions=5, deletions=2)]
    overlay = ReviewOverlay(files=files)

    compact_text = "\n".join(overlay.render(mode=TerminalMode.COMPACT))
    assert "src/decoder.py" in compact_text
    assert "+5 -2" in compact_text

    minimal_text = "\n".join(overlay.render(mode=TerminalMode.MINIMAL))
    assert "=== Changes this session" in minimal_text
    assert "src/decoder.py" in minimal_text
