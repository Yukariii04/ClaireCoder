"""Unit tests for the TUI Command Palette overlay (CLI/TUI Stage 4)."""
import pytest
from unittest.mock import Mock

from clairecoder.tui.states import TerminalMode
from clairecoder.tui.palette import CommandPalette, PaletteCommandItem

def test_command_palette_categories_render_full():
    """Verify full card rendering with categorized commands per TUI-DESIGN.md §15."""
    palette = CommandPalette()
    lines = palette.render(mode=TerminalMode.FULL, width=80)
    text = "\n".join(lines)

    assert "Commands" in text
    assert "APPLICATION / INTERACTION" in text
    assert "/help" in text
    assert "/status" in text
    assert "/mode" in text
    assert "/session" in text
    assert "/plan" in text
    assert "/pause" in text
    assert "/resume" in text
    assert "/cancel" in text
    assert "/clear" in text
    assert "/exit" in text

    assert "UI / PRESENTATION" in text
    assert "/tree" in text
    assert "/review" in text
    assert "↑/↓ select" in text
    assert "Enter open" in text
    assert "Esc back" in text

def test_command_palette_command_classification():
    """Verify that /help is classified as Application/Interaction (not UI-owned) per CC-PRD-011."""
    palette = CommandPalette()
    cmd_map = {cmd.name: cmd for cmd in palette.commands}

    # /help MUST be classified as APPLICATION / INTERACTION with is_ui_command=False
    assert "/help" in cmd_map
    assert cmd_map["/help"].category == "APPLICATION / INTERACTION"
    assert cmd_map["/help"].is_ui_command is False

    # UI presentation commands
    assert cmd_map["/review"].category == "UI / PRESENTATION"
    assert cmd_map["/review"].is_ui_command is True
    assert cmd_map["/tree"].category == "UI / PRESENTATION"
    assert cmd_map["/tree"].is_ui_command is True


def test_command_palette_navigation_keys():
    """Verify navigation with Up/Down, PageUp/PageDown, Home/End."""
    palette = CommandPalette()
    assert palette.selected_index == 0

    # Down
    palette.handle_key("down")
    assert palette.selected_index == 1

    # Up
    palette.handle_key("up")
    assert palette.selected_index == 0

    # End
    palette.handle_key("end")
    assert palette.selected_index == len(palette.commands) - 1

    # Home
    palette.handle_key("home")
    assert palette.selected_index == 0

    # PageDown
    palette.handle_key("pagedown")
    assert palette.selected_index == 5

    # PageUp
    palette.handle_key("pageup")
    assert palette.selected_index == 0

def test_command_palette_navigation_and_selection():
    """Verify navigation and Enter selection invokes on_select callback."""
    palette = CommandPalette()
    mock_select = Mock()
    palette.on_select = mock_select

    # Move cursor down
    palette.handle_key("down")
    assert palette.selected_index == 1
    selected = palette.selected_command
    assert selected is not None

    # Press Enter
    palette.handle_key("Enter")
    mock_select.assert_called_once_with(selected)

def test_command_palette_close_callback():
    """Verify Esc closes the palette."""
    palette = CommandPalette()
    mock_close = Mock()
    palette.on_close = mock_close

    palette.handle_key("Esc")
    mock_close.assert_called_once()

def test_command_palette_compact_and_minimal_modes():
    """Verify compact and minimal rendering."""
    palette = CommandPalette()

    compact_text = "\n".join(palette.render(mode=TerminalMode.COMPACT))
    assert "Commands" in compact_text
    assert "/help" in compact_text

    minimal_text = "\n".join(palette.render(mode=TerminalMode.MINIMAL))
    assert "Available Commands" in minimal_text
    assert "/help" in minimal_text
