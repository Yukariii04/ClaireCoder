"""Phase 4 — Core Tools test suite.

Tests cover:
- Tool registration and discovery (AC-002, AC-019)
- Tool identity and metadata (AC-016)
- Tool invocation through executor (AC-003)
- Permission boundary integration (AC-004)
- Tool results through normalized interface (AC-005)
- Input validation
- ALLOW execution
- DENY prevention
- ASK behavior (does not silently execute)
- Tool errors and malformed input
- Tool isolation (AC-022)
- Model independence (AC-024)
- Security boundary integrity
- Direct execution bypass prevention (CC-ADR-003 Section 32)
"""
import pytest
from clairecoder.core.types import PermissionState, ToolState, PermissionRequirement, ToolResult
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.permissions.types import (
    AutonomyLevel, PermissionCategory, ResourceScope,
    PermissionRequest, PermissionRule
)
from clairecoder.tools.types import ToolExecutionError
from clairecoder.tools.types import (
    ToolCategory, ToolAvailability, ToolMetadata,
    ToolValidationError, ToolNotFoundError, ToolUnavailableError,
    ExtensionSource, TrustLevel
)
from clairecoder.tools.base import Tool
from clairecoder.tools.registry import ToolRegistry
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.core import (
    ReadFileTool, WriteFileTool, DeleteFileTool,
    SearchTool, TerminalTool,
    GitStatusTool, GitCommitTool,
    RunTestsTool, DiagnosticsTool
)


# ---------------------------------------------------------------------------
# TOOL REGISTRATION & DISCOVERY
# ---------------------------------------------------------------------------

def test_tool_registration():
    registry = ToolRegistry()
    tool = ReadFileTool()
    registry.register(tool)
    assert registry.is_registered("filesystem.read")

def test_tool_unregister():
    registry = ToolRegistry()
    tool = ReadFileTool()
    registry.register(tool)
    registry.unregister("filesystem.read")
    assert not registry.is_registered("filesystem.read")

def test_tool_get():
    registry = ToolRegistry()
    tool = ReadFileTool()
    registry.register(tool)
    retrieved = registry.get("filesystem.read")
    assert retrieved.metadata.id == "filesystem.read"

def test_tool_get_not_found():
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.get("nonexistent")

def test_tool_get_unavailable():
    from typing import Any, List
    class DisabledTool(Tool):
        @property
        def metadata(self):
            return ToolMetadata(
                id="disabled.tool", name="Disabled", description="A disabled tool",
                version="1.0.0", category=ToolCategory.FILESYSTEM,
                availability=ToolAvailability.DISABLED
            )
        @property
        def required_permissions(self):
            return []
        def validate_input(self, **kwargs): pass
        def _execute(self, **kwargs):
            return ToolResult(state=ToolState.SUCCESS, output="nope")

    registry = ToolRegistry()
    registry.register(DisabledTool())
    with pytest.raises(ToolUnavailableError):
        registry.get("disabled.tool")

def test_tool_list_all():
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(SearchTool())
    assert len(registry.list_tools()) == 3

def test_tool_list_by_category():
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(SearchTool())
    fs_tools = registry.list_tools(category=ToolCategory.FILESYSTEM)
    assert len(fs_tools) == 2
    search_tools = registry.list_tools(category=ToolCategory.SEARCH)
    assert len(search_tools) == 1

def test_tool_list_available():
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    available = registry.list_available()
    assert len(available) == 2

def test_extension_registry_enumerates_tools():
    """AC-019: Installed Tools can be enumerated through a registry."""
    registry = ToolRegistry()
    all_core = [
        ReadFileTool(), WriteFileTool(), DeleteFileTool(),
        SearchTool(), TerminalTool(),
        GitStatusTool(), GitCommitTool(),
        RunTestsTool(), DiagnosticsTool()
    ]
    for t in all_core:
        registry.register(t)
    assert len(registry.list_tools()) == 9


# ---------------------------------------------------------------------------
# TOOL IDENTITY & METADATA
# ---------------------------------------------------------------------------

def test_tool_metadata_fields():
    """AC-016: Tools expose sufficient metadata."""
    tool = ReadFileTool()
    m = tool.metadata
    assert m.id == "filesystem.read"
    assert m.name == "Read File"
    assert m.description
    assert m.version == "1.0.0"
    assert m.category == ToolCategory.FILESYSTEM
    assert isinstance(m.input_schema, dict)
    assert m.source == ExtensionSource.BUILT_IN
    assert m.trust == TrustLevel.BUILT_IN

def test_all_core_tools_have_metadata():
    tools = [
        ReadFileTool(), WriteFileTool(), DeleteFileTool(),
        SearchTool(), TerminalTool(),
        GitStatusTool(), GitCommitTool(),
        RunTestsTool(), DiagnosticsTool()
    ]
    for tool in tools:
        m = tool.metadata
        assert m.id
        assert m.name
        assert m.description
        assert m.version
        assert isinstance(m.category, ToolCategory)


# ---------------------------------------------------------------------------
# TOOL INPUT VALIDATION
# ---------------------------------------------------------------------------

def test_read_file_validation_missing_path():
    tool = ReadFileTool()
    with pytest.raises(ToolValidationError):
        tool.validate_input()

def test_read_file_validation_empty_path():
    tool = ReadFileTool()
    with pytest.raises(ToolValidationError):
        tool.validate_input(path="  ")

def test_write_file_validation_missing_content():
    tool = WriteFileTool()
    with pytest.raises(ToolValidationError):
        tool.validate_input(path="file.txt")

def test_terminal_validation_empty_command():
    tool = TerminalTool()
    with pytest.raises(ToolValidationError):
        tool.validate_input(command="")

def test_git_commit_validation_missing_message():
    tool = GitCommitTool()
    with pytest.raises(ToolValidationError):
        tool.validate_input()

def test_search_validation_missing_query():
    tool = SearchTool()
    with pytest.raises(ToolValidationError):
        tool.validate_input()

def test_malformed_input_does_not_reach_execution():
    """Invalid input produces structured failure before execution."""
    tool = ReadFileTool()
    with pytest.raises(ToolValidationError):
        tool.validate_input()  # No path provided — validation catches it


# ---------------------------------------------------------------------------
# TOOL RESULTS (AC-005)
# ---------------------------------------------------------------------------

def test_tool_result_success_through_executor():
    """AC-005: Tool results returned through normalized interface."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    engine = PermissionEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)
    executor = ToolExecutor(registry, engine)

    result = executor.invoke("filesystem.read", path="test.txt")
    assert result.state == ToolState.SUCCESS
    assert result.output is not None
    assert result.error is None

def test_tool_result_states_distinguishable():
    """AC-005: Can distinguish SUCCESS, FAILURE, DENIED, CANCELLED, TIMEOUT, UNAVAILABLE."""
    for state in ToolState:
        r = ToolResult(state=state, output=None)
        assert r.state == state


# ---------------------------------------------------------------------------
# PERMISSION BOUNDARY INTEGRATION (AC-004)
# ---------------------------------------------------------------------------

def test_allow_execution():
    """ALLOW → Tool executes and returns result."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    engine = PermissionEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)
    executor = ToolExecutor(registry, engine)

    result = executor.invoke("filesystem.read", path="test.txt")
    assert result.state == ToolState.SUCCESS

def test_deny_prevents_execution():
    """DENY → Tool does not execute."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    # Add an explicit DENY rule
    engine.add_rule(PermissionRule(
        decision=PermissionState.DENY,
        tool_id="filesystem.read",
        priority=100
    ))
    executor = ToolExecutor(registry, engine)

    result = executor.invoke("filesystem.read", path="test.txt")
    assert result.state == ToolState.DENIED
    assert "denied" in result.error.lower()

def test_ask_does_not_silently_execute():
    """ASK → Tool does not silently execute."""
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    # SUPERVISED defaults to ASK
    executor = ToolExecutor(registry, engine)

    result = executor.invoke("filesystem.write", path="test.txt", content="hello")
    assert result.state == ToolState.DENIED
    assert result.metadata.get("requires_confirmation") is True

def test_unavailable_tool_returns_unavailable():
    """Tool not in registry → UNAVAILABLE result."""
    registry = ToolRegistry()
    engine = PermissionEngine()
    executor = ToolExecutor(registry, engine)

    result = executor.invoke("nonexistent.tool")
    assert result.state == ToolState.UNAVAILABLE


# ---------------------------------------------------------------------------
# SECURITY BOUNDARY TESTS
# ---------------------------------------------------------------------------

def test_no_public_execute_method():
    """CC-ADR-003 Section 32: There SHALL be no alternate execution path.
    
    The Tool base class exposes NO public `execute()` method. 
    By strict architectural contract, the `ToolExecutor` is the only 
    supported execution API."""
    tool = ReadFileTool()
    assert not hasattr(tool, "execute")

def test_no_importable_execution_token_exists():
    """Verify that there is no importable token that bypasses the execution boundary.
    
    This regression test ensures no implementation detail (like a module-private
    _EXECUTION_TOKEN) is exposed that would allow a caller to authorize
    themselves outside the Permission Engine."""
    import clairecoder.tools.base
    assert not hasattr(clairecoder.tools.base, "_EXECUTION_TOKEN")

def test_denied_tool_cannot_execute_through_api():
    """DENY + attempted API execution = cannot succeed.
    
    Since Tool has no public execute method, the only way to run it is
    through ToolExecutor, which enforces DENY."""
    registry = ToolRegistry()
    tool = DeleteFileTool()
    registry.register(tool)

    # Set up DENY
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    engine.add_rule(PermissionRule(
        decision=PermissionState.DENY,
        tool_id="filesystem.delete",
        priority=100
    ))
    executor = ToolExecutor(registry, engine)

    # Through executor: denied
    result = executor.invoke("filesystem.delete", path="/important")
    assert result.state == ToolState.DENIED

    # Direct attempt: structurally impossible (method doesn't exist)
    with pytest.raises(AttributeError):
        tool.execute(path="/important")

def test_executor_is_only_valid_execution_path():
    """Verify ToolExecutor → PermissionEngine → Tool is the valid path."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    engine = PermissionEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)
    executor = ToolExecutor(registry, engine)

    # Valid path: executor → permission → tool
    result = executor.invoke("filesystem.read", path="test.txt")
    assert result.state == ToolState.SUCCESS

    # Invalid path: direct tool call → AttributeError
    tool = registry.get("filesystem.read")
    with pytest.raises(AttributeError):
        tool.execute(path="test.txt")

def test_tool_cannot_bypass_permission_engine():
    """Tool execution through executor MUST go through permission check."""
    registry = ToolRegistry()
    registry.register(DeleteFileTool())
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    engine.add_rule(PermissionRule(
        decision=PermissionState.DENY,
        category=PermissionCategory.DELETE,
        priority=100
    ))
    executor = ToolExecutor(registry, engine)

    result = executor.invoke("filesystem.delete", path="/important")
    assert result.state == ToolState.DENIED

def test_tool_cannot_grant_itself_permission():
    """A Tool object has no method to modify Permission Engine policy."""
    tool = ReadFileTool()
    # Tool has no reference to permission engine, no grant method
    assert not hasattr(tool, 'grant_permission')
    assert not hasattr(tool, 'permission_engine')

def test_tool_cannot_mutate_permission_engine():
    """Tool has no access to the permission engine to add/remove rules."""
    tool = WriteFileTool()
    assert not hasattr(tool, '_permission_engine')
    assert not hasattr(tool, 'add_rule')
    assert not hasattr(tool, 'revoke_rule')

def test_tool_cannot_execute_another_tool():
    """A Tool cannot invoke another tool — only ToolExecutor can do that."""
    tool = ReadFileTool()
    assert not hasattr(tool, 'invoke')
    assert not hasattr(tool, 'registry')

def test_tool_cannot_invoke_model():
    """Tool must not perform model inference."""
    tool = TerminalTool()
    assert not hasattr(tool, 'model')
    assert not hasattr(tool, 'gateway')
    assert not hasattr(tool, 'inference')

def test_credential_tool_denied_by_default():
    """Credential access is denied even in high-autonomy modes."""
    from typing import Any, List
    class FakeCredentialTool(Tool):
        @property
        def metadata(self):
            return ToolMetadata(
                id="cred.read", name="Cred", description="Read creds",
                version="1.0.0", category=ToolCategory.FILESYSTEM
            )
        @property
        def required_permissions(self):
            return [PermissionRequirement(action="access_credential", resource="secret", scope="credential")]
        def validate_input(self, **kwargs): pass
        def _execute(self, **kwargs):
            return ToolResult(state=ToolState.SUCCESS, output="secret_value")

    registry = ToolRegistry()
    registry.register(FakeCredentialTool())
    engine = PermissionEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)
    executor = ToolExecutor(registry, engine)

    result = executor.invoke("cred.read")
    assert result.state == ToolState.DENIED

def test_multiple_permissions_all_must_pass():
    """If a tool declares multiple permissions, ALL must be ALLOW."""
    from typing import Any, List
    class MultiPermTool(Tool):
        @property
        def metadata(self):
            return ToolMetadata(
                id="multi.perm", name="Multi", description="Multi perm tool",
                version="1.0.0", category=ToolCategory.FILESYSTEM
            )
        @property
        def required_permissions(self):
            return [
                PermissionRequirement(action="read", resource="file", scope="file"),
                PermissionRequirement(action="write", resource="file", scope="file"),
            ]
        def validate_input(self, **kwargs): pass
        def _execute(self, **kwargs):
            return ToolResult(state=ToolState.SUCCESS, output="done")

    registry = ToolRegistry()
    registry.register(MultiPermTool())
    # Allow read but deny write
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    engine.add_rule(PermissionRule(
        decision=PermissionState.ALLOW,
        category=PermissionCategory.READ,
        priority=20
    ))
    engine.add_rule(PermissionRule(
        decision=PermissionState.DENY,
        category=PermissionCategory.WRITE,
        priority=20
    ))
    executor = ToolExecutor(registry, engine)

    result = executor.invoke("multi.perm")
    assert result.state == ToolState.DENIED

def test_execution_error_returns_failure():
    """Runtime exception during execution produces FAILURE result."""
    from typing import Any, List
    class BrokenTool(Tool):
        @property
        def metadata(self):
            return ToolMetadata(
                id="broken.tool", name="Broken", description="Always fails",
                version="1.0.0", category=ToolCategory.FILESYSTEM
            )
        @property
        def required_permissions(self):
            return [PermissionRequirement(action="read", resource="file", scope="file")]
        def validate_input(self, **kwargs): pass
        def _execute(self, **kwargs):
            raise RuntimeError("internal failure")

    registry = ToolRegistry()
    registry.register(BrokenTool())
    engine = PermissionEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)
    executor = ToolExecutor(registry, engine)

    result = executor.invoke("broken.tool")
    assert result.state == ToolState.FAILURE
    assert "internal failure" in result.error


# ---------------------------------------------------------------------------
# TOOL ISOLATION (AC-022)
# ---------------------------------------------------------------------------

def test_tool_isolation_from_engine():
    """AC-022: Tool implementations remain outside the Engineering Engine."""
    tool = ReadFileTool()
    assert not hasattr(tool, 'engineering_engine')
    assert not hasattr(tool, 'workflow')
    assert not hasattr(tool, 'skill')


# ---------------------------------------------------------------------------
# MODEL INDEPENDENCE (AC-024)
# ---------------------------------------------------------------------------

def test_model_independence():
    """AC-024: Tools do not require a specific model provider."""
    for tool_cls in [ReadFileTool, WriteFileTool, DeleteFileTool,
                     SearchTool, TerminalTool, GitStatusTool,
                     GitCommitTool, RunTestsTool, DiagnosticsTool]:
        tool = tool_cls()
        assert not hasattr(tool, 'model')
        assert not hasattr(tool, 'provider')


# ---------------------------------------------------------------------------
# DETERMINISTIC BEHAVIOR
# ---------------------------------------------------------------------------

def test_deterministic_permission_evaluation():
    """Same request, same state → same result."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    engine = PermissionEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)
    executor = ToolExecutor(registry, engine)

    r1 = executor.invoke("filesystem.read", path="test.txt")
    r2 = executor.invoke("filesystem.read", path="test.txt")
    assert r1.state == r2.state == ToolState.SUCCESS

def test_session_scoped_permission():
    """Permission rule scoped to a session works through executor."""
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    engine.add_rule(PermissionRule(
        decision=PermissionState.ALLOW,
        session_id="session_1",
        priority=20
    ))
    executor = ToolExecutor(registry, engine)

    r1 = executor.invoke("filesystem.write", session_id="session_1", path="f.txt", content="x")
    assert r1.state == ToolState.SUCCESS

    r2 = executor.invoke("filesystem.write", session_id="session_2", path="f.txt", content="x")
    assert r2.state == ToolState.DENIED  # ASK → DENIED (no silent execution)
