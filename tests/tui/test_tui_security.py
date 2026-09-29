"""Tests for TUI Security, Permission Surface, Confirmation Cards, and Decision Handling.

Authorities: CC-PRD-004, CC-ADR-004, CC-PRD-011, CC-ADR-007.
"""
import pytest
from unittest.mock import Mock

from clairecoder.tui.states import InputState, TerminalMode
from clairecoder.tui.app import TuiApplication
from clairecoder.tui.permission import (
    PermissionSurface,
    PermissionDecision,
    PermissionRequestViewModel,
    sanitize_display_text,
    format_permission_command
)
from clairecoder.tui.activity import ActivityType, ActivityState, DiffInfo, DiffLine


def test_sanitize_display_text():
    """Verify that passwords, tokens, and API keys are redacted for safe display."""
    assert sanitize_display_text("pytest tests/") == "pytest tests/"
    assert "token=***" in sanitize_display_text("connect --token=secret12345")
    assert "password=***" in sanitize_display_text("login password=my_secret_pass")
    assert "OPENAI_API_KEY=***" in sanitize_display_text("OPENAI_API_KEY=sk-123456789012345678901234567890")


def test_format_permission_command():
    """Verify safe and concise formatting of tool commands."""
    assert format_permission_command("rm", "delete", "src/file.py") == "rm src/file.py"
    assert format_permission_command("write_file", "write", "src/main.py") == "write src/main.py"
    assert format_permission_command("pytest", "execute", "tests/") == "pytest tests/"


def test_permission_surface_render_full():
    """Verify full TUI rendering matches TUI-DESIGN.md reference."""
    surface = PermissionSurface()
    surface.request_confirmation(
        request_id="req_1",
        tool_id="rm",
        action="delete",
        resource="src/old.py",
        reason="This will permanently delete the file."
    )

    lines = surface.render(TerminalMode.FULL, width=80)
    full_text = "\n".join(lines)

    assert "Permission Required" in full_text
    assert "ClaireCoder wants to run:" in full_text
    assert "[y] yes" in full_text
    assert "[n] no" in full_text


def test_permission_surface_decision_handling():
    """Verify keypresses return correct PermissionDecision values."""
    surface = PermissionSurface()

    surface.request_confirmation(
        request_id="req_dec_1",
        tool_id="terminal",
        action="execute",
        resource="npm test"
    )

    # Press 'y' -> APPROVE
    decision = surface.handle_key("y")
    assert decision == PermissionDecision.APPROVE
