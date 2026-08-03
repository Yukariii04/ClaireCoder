from clairecoder.core.types import PermissionState, ExecutionState, ToolState, ToolResult

def test_permission_states():
    assert PermissionState.ALLOW == "allow"
    assert PermissionState.ASK == "ask"
    assert PermissionState.DENY == "deny"

def test_execution_states():
    assert ExecutionState.IDLE == "idle"
    assert ExecutionState.EXECUTING == "executing"

from clairecoder.core.types import PermissionRequirement


def test_permission_requirement():
    req = PermissionRequirement(action="write", resource="file")
    assert req.action == "write"
    assert req.resource == "file"
    assert req.scope == "project"

def test_tool_result():
    res = ToolResult(state=ToolState.SUCCESS, output="done")
    assert res.state == ToolState.SUCCESS
    assert res.output == "done"
    assert res.error is None
