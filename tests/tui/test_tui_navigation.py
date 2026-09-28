"""Tests for TUI Overlay Navigation, Secondary Views, Hotkeys, and Focus Ownership.

Authorities: CC-PRD-011, CC-ADR-007, TUI-DESIGN.md.
"""
import pytest
from clairecoder.tui.app import TuiApplication, InputState


def test_main_pane_vs_overlay_focus_ownership():
    """Verify arrow keys route to prompt/transcript in Main Pane and to overlay in Overlay mode."""
    app = TuiApplication()
    assert app.state == InputState.NORMAL
    assert app.active_overlay is None

    # In Normal mode, typing goes to prompt
    app.handle_key("h")
    app.handle_key("i")
    assert app.prompt.get_text() == "hi"

    # Open palette -> InputState.OVERLAY
    app.open_palette()
    assert app.state == InputState.OVERLAY
    assert app.active_overlay == "palette"

    # In Overlay mode, arrows navigate palette
    sel_before = app.command_palette.selected_index
    app.handle_key("down")
    assert app.command_palette.selected_index == sel_before + 1

    # Escape returns to Main Pane
    app.handle_key("escape")
    assert app.state == InputState.NORMAL
    assert app.active_overlay is None


def test_overlay_transitions_and_restoration():
    """Verify transitions across all secondary overlays (Palette, Task, Tree, Review)."""
    app = TuiApplication()

    # Open Tree
    app.open_tree()
    assert app.active_overlay == "tree"

    # Switch directly to Task View (Ctrl+P)
    app.open_task()
    assert app.active_overlay == "task"

    # Switch directly to Review (Ctrl+R)
    app.open_review()
    assert app.active_overlay == "review"

    # Switch directly to Palette
    app.open_palette()
    assert app.active_overlay == "palette"

    # Close palette -> returns to Normal
    app.close_overlay()
    assert app.state == InputState.NORMAL
    assert app.active_overlay is None


def test_direct_secondary_view_navigation_hotkeys():
    """Verify Ctrl+P (Task), Ctrl+T (Tree), Ctrl+R (Review) hotkeys toggle overlays."""
    app = TuiApplication()

    # Ctrl+P opens task view
    app.handle_key("ctrl+p")
    assert app.active_overlay == "task"

    # Ctrl+T switches to tree
    app.handle_key("ctrl+t")
    assert app.active_overlay == "tree"

    # Ctrl+R switches to review
    app.handle_key("ctrl+r")
    assert app.active_overlay == "review"

    # Esc closes overlay
    app.handle_key("escape")
    assert app.active_overlay is None


def test_escape_key_overlay_dismissal():
    """Verify Escape dismisses active overlays without losing session state."""
    app = TuiApplication()
    app.header.session_id = "sess_keep"

    app.open_task()
    assert app.active_overlay == "task"

    app.handle_escape()
    assert app.active_overlay is None
    assert app.header.session_id == "sess_keep"
