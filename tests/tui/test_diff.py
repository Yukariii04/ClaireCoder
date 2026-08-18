"""Unit tests for the TUI Diff presentation foundation (CLI/TUI Stage 4)."""
import pytest
from clairecoder.tui.states import TerminalMode
from clairecoder.tui.activity import DiffInfo, DiffLine
from clairecoder.tui.diff import FileDiff, DiffRenderer

def test_file_diff_formatted_summary():
    """Verify FileDiff summary formatting with new/deleted tags."""
    diff1 = FileDiff(file_path="src/decoder.py", additions=18, deletions=4)
    assert "+18 -4" in diff1.formatted_summary
    assert "src/decoder.py" in diff1.formatted_summary

    diff2 = FileDiff(file_path="src/router.py", additions=6, deletions=0, is_new=True)
    assert "(new)" in diff2.formatted_summary
    assert "+6 -0" in diff2.formatted_summary

    diff3 = FileDiff(file_path="old.py", additions=0, deletions=50, is_deleted=True)
    assert "(deleted)" in diff3.formatted_summary

def test_diff_renderer_collapsed():
    """Verify collapsed diff renders concise summary only."""
    diff = DiffInfo(
        summary="+18 -4",
        lines=[
            DiffLine(type="add", content="new code line"),
            DiffLine(type="remove", content="old code line")
        ]
    )
    lines = DiffRenderer.render_inline_diff(diff, file_path="src/decoder.py", expanded=False)
    assert len(lines) == 1
    assert "+18 -4" in lines[0]
    assert "new code line" not in lines[0]

def test_diff_renderer_expanded_full():
    """Verify expanded full mode diff includes borders, line numbers, and +/- prefixes."""
    diff = DiffInfo(
        summary="+2 -1",
        lines=[
            DiffLine(type="context", content="def decode(self):"),
            DiffLine(type="remove", content="    return False"),
            DiffLine(type="add", content="    if self.streaming:"),
            DiffLine(type="add", content="        return True")
        ]
    )
    lines = DiffRenderer.render_inline_diff(diff, file_path="src/decoder.py", mode=TerminalMode.FULL, width=80, expanded=True)
    text = "\n".join(lines)
    assert ("┌" in text or "╭" in text) and ("┐" in text or "╮" in text) and ("└" in text or "╰" in text) and ("┘" in text or "╯" in text)
    assert "+     if self.streaming:" in text
    assert "-     return False" in text
    assert "42" in text

def test_diff_renderer_compact_and_minimal():
    """Verify compact and minimal terminal mode diff rendering."""
    diff = DiffInfo(
        summary="+1 -0",
        lines=[DiffLine(type="add", content="import math")]
    )
    # Compact
    compact_lines = DiffRenderer.render_inline_diff(diff, file_path="src/math_util.py", mode=TerminalMode.COMPACT)
    compact_text = "\n".join(compact_lines)
    assert "+ import math" in compact_text
    assert "┌" not in compact_text and "╭" not in compact_text

    # Minimal
    minimal_lines = DiffRenderer.render_inline_diff(diff, file_path="src/math_util.py", mode=TerminalMode.MINIMAL)
    minimal_text = "\n".join(minimal_lines)
    assert "+ import math" in minimal_text

def test_diff_renderer_empty():
    """Verify handling of empty or None diff info gracefully."""
    lines = DiffRenderer.render_inline_diff(None, file_path="empty.py")
    assert len(lines) == 1
    assert "empty.py" in lines[0]
