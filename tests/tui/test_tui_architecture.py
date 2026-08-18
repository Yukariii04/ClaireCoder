"""Architectural tests for the TUI foundation, Permission Confirmation UI, and Overlays."""
import ast
import os
from unittest.mock import Mock

from clairecoder.tui.app import TuiApplication
from clairecoder.tui.states import InputState
from clairecoder.tui.review import ReviewOverlay
from clairecoder.tui.palette import CommandPalette
from clairecoder.tui.diff import DiffRenderer

def test_tui_does_not_import_subsystems():
    """Verify that the TUI does not import private/forbidden subsystems or provider SDKs."""
    forbidden_imports = [
        "clairecoder.engine.engine",  # Should not import EngineeringEngine directly to recreate it
        "clairecoder.execution",      # Should not import execution directly
        "clairecoder.permissions",    # Should not import permission internals directly
        "clairecoder.verification",   # Should not import verification directly
        "clairecoder.workflow",       # Should not import workflow directly
        "clairecoder.tools.executor", # Should not import ToolExecutor directly
        "openai",                     # Provider SDK
        "anthropic",                  # Provider SDK
        "google.generativeai",        # Provider SDK
    ]
    
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src/clairecoder/tui"))
    
    for root, _, files in os.walk(src_dir):
        for file in files:
            if not file.endswith(".py"):
                continue
                
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in forbidden_imports:
                            assert not alias.name.startswith(forbidden), f"{filepath} illegally imported {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for forbidden in forbidden_imports:
                            assert not node.module.startswith(forbidden), f"{filepath} illegally imported {node.module}"

def test_no_private_engine_access():
    """Ensure InteractionController and TUI do not access private Engine members."""
    forbidden_attributes = ["_event_callback", "_emit", "_sessions", "_rules"]
    
    dirs_to_check = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src/clairecoder/tui")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src/clairecoder/interaction"))
    ]
    
    for src_dir in dirs_to_check:
        for root, _, files in os.walk(src_dir):
            for file in files:
                if not file.endswith(".py"):
                    continue
                    
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Attribute):
                        for forbidden in forbidden_attributes:
                            assert node.attr != forbidden, f"{filepath} illegally accessed private member: {forbidden}"

def test_escape_does_not_cancel_execution():
    """Verify that Esc in TUI is UI-level cancellation only and never calls execution cancellation."""
    app = TuiApplication()
    mock_interrupt = Mock()
    mock_response = Mock()
    app.on_interrupt = mock_interrupt
    app.on_permission_response = mock_response
    
    # 1. Normal state escape
    app.handle_escape()
    mock_interrupt.assert_not_called()
    
    # 2. Confirmation state escape
    app.set_state(InputState.CONFIRMATION)
    app.permission_surface.request_confirmation(
        request_id="req_test",
        tool_id="rm",
        resource="file.py"
    )
    app.handle_escape()
    mock_interrupt.assert_not_called()
    assert app.state == InputState.NORMAL

    # 3. Overlay state escape
    app.open_palette()
    assert app.state == InputState.OVERLAY
    app.handle_escape()
    mock_interrupt.assert_not_called()
    assert app.state == InputState.NORMAL

def test_help_command_architectural_ownership():
    """Verify that /help is registered as an Application/Interaction command in InteractionController."""
    from clairecoder.interaction.controller import InteractionController
    from clairecoder.interaction.types import CommandCategory
    mock_engine = Mock()
    controller = InteractionController(engine=mock_engine)

    assert "help" in controller._commands
    help_def = controller._commands["help"]
    assert help_def.name == "help"
    assert help_def.category == CommandCategory.SYSTEM

