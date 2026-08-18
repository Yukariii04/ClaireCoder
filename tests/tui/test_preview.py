"""Unit tests for the Developer Manual TUI Preview Harness."""
import pytest
from clairecoder.tui.states import TerminalMode
from clairecoder.tui.preview import create_preview_app, render_preview

def test_preview_app_creation():
    """Verify preview app creates populated state."""
    app = create_preview_app(mode=TerminalMode.FULL)
    assert app.header.directory == "~/projects/claire-speech-engine"
    assert app.header.model == "claire-large"
    assert app.header.mode == "IMPLEMENT"
    assert len(app.transcript.activities) >= 4
    assert len(app.review_overlay.files) == 3

def test_preview_render_screens():
    """Verify all preview screens render without crashing."""
    main_lines = render_preview(screen="main")
    assert any("Streaming decode support" in l for l in main_lines)

    loading_lines = render_preview(screen="loading")
    assert any("CLAIRECODER" in l for l in loading_lines)
    assert any("Engineering. Automated." in l for l in loading_lines)

    perm_lines = render_preview(screen="permission")
    assert any("Permission Required" in l for l in perm_lines)

    rev_lines = render_preview(screen="review")
    assert any("Changes this session" in l for l in rev_lines)

    pal_lines = render_preview(screen="palette")
    assert any("Commands" in l for l in pal_lines)

    tree_lines = render_preview(screen="tree")
    assert any("Files" in l for l in tree_lines)

    task_lines = render_preview(screen="task")
    assert any("Current Workflow" in l for l in task_lines)
