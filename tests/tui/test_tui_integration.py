"""Integration test for TUI event streaming, correlation, and public permission flow."""
import pytest
from unittest.mock import Mock

from clairecoder.engine.engine import EngineeringEngine
from clairecoder.engine.types import EngineeringObjective
from clairecoder.interaction.controller import InteractionController
from clairecoder.tui.app import TuiApplication
from clairecoder.tui.activity import ActivityState, ActivityType
from clairecoder.tui.states import InputState
from clairecoder.core.types import ToolResult, ToolState, PermissionState, PermissionRequirement
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.permissions.types import PermissionRequest, PermissionCategory, ResourceScope
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.registry import ToolRegistry
from clairecoder.tools.types import ToolMetadata, ToolCategory
from clairecoder.tools.base import Tool

def test_tui_event_correlation_integration():
    # Setup Engine with a mock tool executor that returns deterministic results
    mock_executor = Mock()
    
    # We will control the mock to return specific tool states to test success and failure
    def mock_invoke(tool_id, **kwargs):
        if tool_id == "pytest":
            return ToolResult(state=ToolState.SUCCESS, output="Passed all tests")
        elif tool_id == "flake8":
            return ToolResult(state=ToolState.FAILURE, output=None, error="Syntax error")
        elif tool_id == "write_file":
            return ToolResult(state=ToolState.DENIED, output=None, metadata={"requires_confirmation": True, "action": "write", "resource": "file.py"})
        return ToolResult(state=ToolState.SUCCESS, output=None)

    mock_executor.invoke.side_effect = mock_invoke
    
    engine = EngineeringEngine(model_gateway=Mock(), tool_executor=mock_executor)
    controller = InteractionController(engine)
    app = TuiApplication()
    
    # Wire them up
    app.connect_controller(controller)
    
    # 1. Start objective using public API
    objective = EngineeringObjective(id="obj1", request="Test objective", session_id="sess1")
    engine.receive_objective(objective)
    
    assert len(app.transcript.activities) == 1
    assert app.transcript.activities[0].correlation_key == "obj_obj1"
    assert app.transcript.activities[0].title == "Starting objective"
    
    # 2 & 3. Tool requested & completed (successful) using public API
    engine.request_tool("pytest", session_id="sess1")
    
    # Because request_tool is synchronous in the mock, it emits both REQUESTED and COMPLETED.
    # The transcript should have updated the same activity to COMPLETED.
    assert len(app.transcript.activities) == 2
    tool_activity = app.transcript.activities[1]
    assert tool_activity.correlation_key.startswith("tool_")
    assert tool_activity.state == ActivityState.COMPLETED
    assert tool_activity.type == ActivityType.TOOL
    assert tool_activity.expandable_content == "Passed all tests"
    
    # 4. Another tool fails using public API
    engine.request_tool("flake8", session_id="sess1")
    
    assert len(app.transcript.activities) == 3
    failed_activity = app.transcript.activities[2]
    assert failed_activity.state == ActivityState.FAILED
    assert failed_activity.type == ActivityType.TOOL
    
    # 5. Permission requested using public API
    engine.request_tool("write_file", session_id="sess1")
    
    assert len(app.transcript.activities) == 4
    perm_activity = app.transcript.activities[3]
    assert perm_activity.state == ActivityState.APPROVAL_REQUIRED
    assert perm_activity.type == ActivityType.PERMISSION
    
    # Complete objective using public API
    engine.complete_objective("sess1")
    
    assert len(app.transcript.activities) == 4
    obj_activity = app.transcript.activities[0]
    assert obj_activity.state == ActivityState.COMPLETED

def test_full_public_permission_flow_approve():
    """Test full public permission confirmation flow with 'y' approval."""
    perm_engine = PermissionEngine()
    registry = ToolRegistry()
    
    class MockDeleteTool(Tool):
        @property
        def metadata(self) -> ToolMetadata:
            return ToolMetadata(
                id="rm",
                name="rm",
                description="Deletes a file",
                version="1.0.0",
                category=ToolCategory.FILESYSTEM
            )
        @property
        def required_permissions(self):
            return [
                PermissionRequirement(action="delete", scope="file", resource="src/old.py")
            ]
        def validate_input(self, **kwargs):
            pass
        def _execute(self, **kwargs):
            return ToolResult(state=ToolState.SUCCESS, output="File deleted")
            
    registry.register(MockDeleteTool())
    executor = ToolExecutor(registry=registry, permission_engine=perm_engine)
    
    engine = EngineeringEngine(model_gateway=Mock(), tool_executor=executor)
    controller = InteractionController(engine)
    app = TuiApplication()
    app.connect_controller(controller)
    
    # Start session
    engine.receive_objective(EngineeringObjective(id="obj_perm", request="Cleanup", session_id="sess_p1"))
    
    # 1. Tool requested - requires confirmation in SUPERVISED mode
    res = engine.request_tool("rm", session_id="sess_p1", path="src/old.py")
    assert res.state == ToolState.DENIED
    assert res.metadata.get("requires_confirmation") is True
    
    # 2. TUI receives event and enters CONFIRMATION state
    assert app.state == InputState.CONFIRMATION
    assert app.permission_surface.has_pending()
    assert app.permission_surface.active_request.tool_id == "rm"
    
    # 3. User approves with 'y' keypress
    app.handle_key("y")
    
    # 4. Public boundary routes response, emits PERMISSION_RESOLVED, updates transcript in-place
    assert app.state == InputState.NORMAL
    perm_activity = [a for a in app.transcript.activities if a.type == ActivityType.PERMISSION][0]
    assert perm_activity.title == "Permission approved"
    assert perm_activity.state == ActivityState.COMPLETED
    assert "Running rm" in perm_activity.detail

def test_full_public_permission_flow_session_always():
    """Test full public permission flow with 'a' (session-scoped authorization)."""
    perm_engine = PermissionEngine()
    registry = ToolRegistry()
    
    class MockPytestTool(Tool):
        @property
        def metadata(self) -> ToolMetadata:
            return ToolMetadata(
                id="pytest",
                name="pytest",
                description="Runs tests",
                version="1.0.0",
                category=ToolCategory.TESTING
            )
        @property
        def required_permissions(self):
            return [
                PermissionRequirement(action="execute", scope="command", resource="tests/")
            ]
        def validate_input(self, **kwargs):
            pass
        def _execute(self, **kwargs):
            return ToolResult(state=ToolState.SUCCESS, output="All passed")
            
    registry.register(MockPytestTool())
    executor = ToolExecutor(registry=registry, permission_engine=perm_engine)
    
    engine = EngineeringEngine(model_gateway=Mock(), tool_executor=executor)
    controller = InteractionController(engine)
    app = TuiApplication()
    app.connect_controller(controller)
    
    # Start session
    engine.receive_objective(EngineeringObjective(id="obj_test", request="Run tests", session_id="sess_p2"))
    
    # 1. Tool requested - triggers permission confirmation
    engine.request_tool("pytest", session_id="sess_p2")
    assert app.state == InputState.CONFIRMATION
    
    # 2. User presses 'a' for session-scoped approval
    app.handle_key("a")
    assert app.state == InputState.NORMAL
    
    # 3. Verify PermissionEngine now allows pytest for this session automatically
    check_req = PermissionRequest(
        tool_id="pytest",
        operation="execute",
        resource="tests/",
        category=PermissionCategory.EXECUTE,
        resource_scope=ResourceScope.COMMAND,
        session_id="sess_p2"
    )
    assert perm_engine.evaluate_request(check_req) == PermissionState.ALLOW
    
    # Subsequent execution in this session succeeds without ASK
    res2 = executor.invoke("pytest", session_id="sess_p2")
    assert res2.state == ToolState.SUCCESS
    assert res2.output == "All passed"
