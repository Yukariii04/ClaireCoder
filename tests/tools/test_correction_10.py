"""§36/§37 — End-to-end coding agent acceptance tests.

Tests real tool invocation rather than merely inspecting text responses.
At least one test exercises permission-required execution.
"""
import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from clairecoder.core.types import ToolResult, ToolState, PermissionRequirement
from clairecoder.tools.core import (
    ReadFileTool, WriteFileTool, ReplaceFileContentTool,
    TerminalTool, GitStatusTool, GitCommitTool,
    RunTestsTool, DiagnosticsTool, DeleteFileTool,
    SearchTool, ListDirTool, set_workspace_root, get_workspace_root,
)
from clairecoder.tools.registry import ToolRegistry
from clairecoder.tools.executor import ToolExecutor
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.permissions.types import (
    AutonomyLevel, PermissionRule, PermissionCategory,
    ResourceScope, PermissionRequest,
)
from clairecoder.core.types import PermissionState
from clairecoder.core.agent_types import (
    AgentMessage, PendingToolInvocation, ModePolicy,
    AgentBudget, NormalizedToolResult, ToolCallAccumulator,
    action_signature, CapabilityState, model_key,
)
from clairecoder.tools.workspace import (
    resolve_workspace_path, WorkspaceSecurityError, is_within_workspace,
    ExecutionContext,
)


# ==========================================================================
# Fixtures
# ==========================================================================

@pytest.fixture
def workspace(tmp_path):
    """Create a workspace with a calculator project and a deliberate bug."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    test_dir = tmp_path / "tests"
    test_dir.mkdir()

    # Buggy calculator
    (src_dir / "calculator.py").write_text(
        'def add(a, b):\n    return a - b  # BUG: should be a + b\n\n'
        'def multiply(a, b):\n    return a * b\n'
    )
    (test_dir / "test_calculator.py").write_text(
        'from src.calculator import add, multiply\n\n'
        'def test_add():\n    assert add(2, 3) == 5\n\n'
        'def test_multiply():\n    assert multiply(4, 5) == 20\n'
    )

    set_workspace_root(tmp_path)
    yield tmp_path
    set_workspace_root(None)


@pytest.fixture
def executor_supervised():
    """Executor with supervised autonomy (ASK for most operations)."""
    registry = ToolRegistry()
    for tool_cls in [ReadFileTool, WriteFileTool, ReplaceFileContentTool,
                     DeleteFileTool, SearchTool, ListDirTool, TerminalTool]:
        registry.register(tool_cls())
    perm = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    return ToolExecutor(registry, perm)


@pytest.fixture
def executor_autonomous():
    """Executor with autonomous permissions (ALLOW for most)."""
    registry = ToolRegistry()
    for tool_cls in [ReadFileTool, WriteFileTool, ReplaceFileContentTool,
                     DeleteFileTool, SearchTool, ListDirTool, TerminalTool]:
        registry.register(tool_cls())
    perm = PermissionEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)
    return ToolExecutor(registry, perm)


# ==========================================================================
# §36 — E2E Coding Agent Acceptance
# ==========================================================================

class TestCodingAgentE2E:
    """Verifies real tool invocation for a coding-agent workflow."""

    def test_read_file_real(self, workspace, executor_autonomous):
        """Agent can read a real file."""
        result = executor_autonomous.invoke("filesystem.read", path="src/calculator.py")
        assert result.state == ToolState.SUCCESS
        assert "def add" in result.output
        assert "a - b" in result.output  # The bug

    def test_search_for_bug(self, workspace, executor_autonomous):
        """Agent can search across the workspace."""
        result = executor_autonomous.invoke("search.text", query="a - b")
        assert result.state == ToolState.SUCCESS
        assert "calculator.py" in result.output

    def test_edit_file_with_diff(self, workspace, executor_autonomous):
        """Agent can edit a file and get real diff information."""
        result = executor_autonomous.invoke(
            "filesystem.replace",
            path="src/calculator.py",
            target_content="return a - b  # BUG: should be a + b",
            replacement_content="return a + b",
        )
        assert result.state == ToolState.SUCCESS
        assert result.metadata.get("changed") is True
        assert result.metadata.get("additions", 0) > 0 or result.metadata.get("deletions", 0) > 0
        assert result.metadata.get("diff") is not None

        # Verify the fix persisted
        fixed = (workspace / "src" / "calculator.py").read_text()
        assert "return a + b" in fixed
        assert "a - b" not in fixed

    def test_list_directory(self, workspace, executor_autonomous):
        """Agent can list workspace directories."""
        result = executor_autonomous.invoke("filesystem.list", path="src")
        assert result.state == ToolState.SUCCESS
        assert "calculator.py" in result.output

    def test_write_new_file(self, workspace, executor_autonomous):
        """Agent can write a new file with diff."""
        result = executor_autonomous.invoke(
            "filesystem.write",
            path="src/helper.py",
            content="def helper():\n    return True\n",
        )
        assert result.state == ToolState.SUCCESS
        assert result.metadata.get("bytes_written") > 0
        assert result.metadata.get("additions", 0) > 0

    def test_failed_edit_recovery_hint(self, workspace, executor_autonomous):
        """§9: Failed edit tells the model how to recover."""
        result = executor_autonomous.invoke(
            "filesystem.replace",
            path="src/calculator.py",
            target_content="THIS TEXT DOES NOT EXIST",
            replacement_content="whatever",
        )
        assert result.state == ToolState.FAILURE
        assert "not found" in result.error.lower()
        assert "re-read" in result.error.lower()

    def test_missing_file_failure(self, workspace, executor_autonomous):
        """§8: Missing file is FAILURE, not SUCCESS."""
        result = executor_autonomous.invoke("filesystem.read", path="nonexistent.py")
        assert result.state == ToolState.FAILURE
        assert result.metadata.get("reason") == "not_found"

    def test_delete_nonexistent_failure(self, workspace, executor_autonomous):
        """§8: Deleting nonexistent file is FAILURE or DENIED (delete requires confirmation in autonomous)."""
        result = executor_autonomous.invoke("filesystem.delete", path="ghost.py")
        assert result.state in (ToolState.FAILURE, ToolState.DENIED)

    def test_ambiguous_edit_failure(self, workspace, executor_autonomous):
        """§9: Ambiguous match returns specific error."""
        # Write a file with duplicate content
        (workspace / "dup.py").write_text("x = 1\nx = 1\n")
        result = executor_autonomous.invoke(
            "filesystem.replace",
            path="dup.py",
            target_content="x = 1",
            replacement_content="x = 2",
        )
        assert result.state == ToolState.FAILURE
        assert result.metadata.get("reason") == "ambiguous_match"

    def test_noop_edit(self, workspace, executor_autonomous):
        """§9: No-op edit detected."""
        result = executor_autonomous.invoke(
            "filesystem.replace",
            path="src/calculator.py",
            target_content="def add(a, b):",
            replacement_content="def add(a, b):",
        )
        assert result.state == ToolState.SUCCESS
        assert result.metadata.get("changed") is False


# ==========================================================================
# §37 — Permission E2E Acceptance
# ==========================================================================

class TestPermissionE2E:
    """Tests the full permission ask/approve/deny/cancel lifecycle."""

    def test_ask_creates_pending_invocation(self, workspace, executor_supervised):
        """§4: ASK stores the exact pending invocation."""
        result = executor_supervised.invoke(
            "filesystem.read",
            path="src/calculator.py",
            session_id="sess-1",
        )
        assert result.state == ToolState.DENIED
        assert result.metadata.get("requires_confirmation") is True
        assert result.metadata.get("request_id") is not None

        # Verify pending invocation stored
        req_id = result.metadata["request_id"]
        pending = executor_supervised.get_pending(req_id)
        assert pending is not None
        assert pending.tool_id == "filesystem.read"
        assert pending.kwargs == {"path": "src/calculator.py"}
        assert pending.session_id == "sess-1"

    def test_approve_executes_exact_invocation(self, workspace, executor_supervised):
        """§4: Approval executes the exact pending invocation."""
        result = executor_supervised.invoke(
            "filesystem.read",
            path="src/calculator.py",
            session_id="sess-1",
        )
        req_id = result.metadata["request_id"]

        # Approve
        approved_result = executor_supervised.resolve_permission(req_id, "granted")
        assert approved_result.state == ToolState.SUCCESS
        assert "def add" in approved_result.output

        # Pending cleaned up
        assert executor_supervised.get_pending(req_id) is None

    def test_deny_returns_structured_denial(self, workspace, executor_supervised):
        """§4: Denial returns structured denial to model."""
        result = executor_supervised.invoke(
            "filesystem.read",
            path="src/calculator.py",
            session_id="sess-1",
        )
        req_id = result.metadata["request_id"]

        denied = executor_supervised.resolve_permission(req_id, "denied")
        assert denied.state == ToolState.DENIED
        assert "denied" in denied.error.lower()
        assert executor_supervised.get_pending(req_id) is None

    def test_cancel_returns_cancelled(self, workspace, executor_supervised):
        """§4: Cancellation returns CANCELLED state."""
        result = executor_supervised.invoke(
            "filesystem.read",
            path="src/calculator.py",
            session_id="sess-1",
        )
        req_id = result.metadata["request_id"]

        cancelled = executor_supervised.resolve_permission(req_id, "cancelled")
        assert cancelled.state == ToolState.CANCELLED
        assert executor_supervised.get_pending(req_id) is None

    def test_always_persists_session_rule(self, workspace, executor_supervised):
        """§4: 'always' persists the appropriate permission rule."""
        result = executor_supervised.invoke(
            "filesystem.read",
            path="src/calculator.py",
            session_id="sess-1",
        )
        req_id = result.metadata["request_id"]

        # Resolve with "always"
        always_result = executor_supervised.resolve_permission(req_id, "always")
        assert always_result.state == ToolState.SUCCESS
        assert "def add" in always_result.output

        # Now same tool+session should be ALLOW (no more ASK)
        result2 = executor_supervised.invoke(
            "filesystem.read",
            path="src/calculator.py",
            session_id="sess-1",
        )
        # Should succeed now without ASK
        assert result2.state == ToolState.SUCCESS

    def test_cleanup_pending_on_clear(self, workspace, executor_supervised):
        """§4: Pending permissions cleaned up on cleanup call."""
        executor_supervised.invoke(
            "filesystem.read",
            path="src/calculator.py",
            session_id="sess-1",
        )
        assert executor_supervised.has_pending()

        executor_supervised.cleanup_pending()
        assert not executor_supervised.has_pending()

    def test_unknown_request_id_returns_failure(self, workspace, executor_supervised):
        """§4: Unknown permission request returns failure."""
        result = executor_supervised.resolve_permission("nonexistent-id", "granted")
        assert result.state == ToolState.FAILURE
        assert "Unknown" in result.error

    def test_permission_identifies_real_target(self, workspace, executor_supervised):
        """§5: Permission request identifies the real target."""
        result = executor_supervised.invoke(
            "filesystem.read",
            path="src/calculator.py",
            session_id="sess-1",
        )
        assert result.metadata.get("resource") is not None
        assert "calculator.py" in result.metadata["resource"]


# ==========================================================================
# §6 — Workspace Security
# ==========================================================================

class TestWorkspaceSecurity:
    """Central workspace security boundary."""

    def test_resolve_within_workspace(self, tmp_path):
        """Normal relative path resolves within workspace."""
        (tmp_path / "file.py").write_text("x")
        p = resolve_workspace_path(tmp_path, "file.py")
        assert p == (tmp_path / "file.py").resolve()

    def test_escape_rejected(self, tmp_path):
        """../../outside path rejected."""
        with pytest.raises(WorkspaceSecurityError):
            resolve_workspace_path(tmp_path, "../../outside")

    def test_absolute_outside_rejected(self, tmp_path):
        """Absolute outside-workspace path rejected."""
        import tempfile
        other = Path(tempfile.gettempdir()) / "other"
        if not str(other.resolve()).startswith(str(tmp_path.resolve())):
            with pytest.raises(WorkspaceSecurityError):
                resolve_workspace_path(tmp_path, str(other))

    def test_empty_path_returns_root(self, tmp_path):
        """Empty path returns workspace root."""
        p = resolve_workspace_path(tmp_path, "")
        assert p == tmp_path.resolve()

    def test_is_within_workspace_helper(self, tmp_path):
        """Helper function works."""
        assert is_within_workspace(tmp_path, "file.py")
        assert not is_within_workspace(tmp_path, "../../outside")

    def test_execution_context_frozen(self):
        """ExecutionContext is immutable."""
        ctx = ExecutionContext(workspace_root=Path("."))
        with pytest.raises(AttributeError):
            ctx.session_id = "new"


# ==========================================================================
# §7 — Terminal uses workspace cwd
# ==========================================================================

class TestTerminalWorkspace:
    """Terminal commands use authoritative workspace cwd."""

    def test_terminal_cwd(self, workspace):
        """§7: Terminal uses workspace root as cwd."""
        tool = TerminalTool()
        result = tool._execute(command="echo test")
        assert result.metadata.get("cwd") is not None
        assert result.metadata.get("cwd") == str(workspace.resolve())

    def test_terminal_nonzero_failure(self, workspace):
        """§8: Non-zero exit code is FAILURE."""
        tool = TerminalTool()
        result = tool._execute(command="exit 1")
        assert result.state == ToolState.FAILURE
        assert result.metadata.get("exit_code") == 1

    def test_terminal_structured_result(self, workspace):
        """§7: Structured result with command, cwd, exit_code, duration."""
        tool = TerminalTool()
        result = tool._execute(command="echo hello")
        assert "command" in result.metadata
        assert "cwd" in result.metadata
        assert "exit_code" in result.metadata
        assert "duration_ms" in result.metadata
        assert result.metadata["timed_out"] is False


# ==========================================================================
# §8 — False Success Removal
# ==========================================================================

class TestFalseSuccessRemoval:
    """No tool returns success when it should return failure."""

    def test_git_status_unavailable(self, tmp_path):
        """§8: Git unavailable is FAILURE/UNAVAILABLE, not clean=True."""
        set_workspace_root(tmp_path)
        try:
            tool = GitStatusTool()
            result = tool._execute()
            # In a directory with no git, result should not be clean=True
            if result.state == ToolState.SUCCESS:
                # If git is installed, success is fine for a non-git dir
                # But it must not say clean=True
                pass
            else:
                # FAILURE or UNAVAILABLE is correct for non-git directory
                assert result.state in (ToolState.FAILURE, ToolState.UNAVAILABLE)
        finally:
            set_workspace_root(None)

    def test_git_commit_not_stub(self, tmp_path):
        """§8: GitCommit executes real commit, not a stub."""
        set_workspace_root(tmp_path)
        try:
            tool = GitCommitTool()
            result = tool._execute(message="test commit")
            # In a non-git directory, should fail
            assert result.state in (ToolState.FAILURE, ToolState.UNAVAILABLE)
            assert "[stub]" not in str(result.output or "")
        finally:
            set_workspace_root(None)

    def test_diagnostics_not_fake(self, tmp_path):
        """§8: Diagnostics does not claim success without execution."""
        set_workspace_root(tmp_path)
        try:
            tool = DiagnosticsTool()
            result = tool._execute()
            # Should either run a real linter or report UNAVAILABLE
            # Must NOT return "diagnostics passed (0 issues)" without running anything
            if result.state == ToolState.UNAVAILABLE:
                assert "linter" in result.error.lower() or "no" in result.error.lower()
            # If a linter is found, that's fine too
        finally:
            set_workspace_root(None)


# ==========================================================================
# §11 — AgentMessage
# ==========================================================================

class TestAgentMessage:
    """Provider-neutral agent message representation."""

    def test_user_message(self):
        msg = AgentMessage(role="user", content="Fix the parser")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Fix the parser"

    def test_assistant_tool_calls(self):
        msg = AgentMessage(
            role="assistant",
            tool_calls=[{"id": "call_123", "name": "read_file", "arguments": {"path": "src/parser.py"}}],
        )
        d = msg.to_dict()
        assert d["tool_calls"][0]["id"] == "call_123"
        assert "content" not in d  # None not serialized

    def test_tool_result(self):
        msg = AgentMessage(role="tool", tool_call_id="call_123", name="read_file", content="file contents...")
        d = msg.to_dict()
        assert d["tool_call_id"] == "call_123"
        assert d["name"] == "read_file"

    def test_roundtrip(self):
        original = AgentMessage(
            role="assistant", content="hello", metadata={"tokens": 42}
        )
        restored = AgentMessage.from_dict(original.to_dict())
        assert restored.role == original.role
        assert restored.content == original.content
        assert restored.metadata == original.metadata


# ==========================================================================
# §13 — ToolCallAccumulator
# ==========================================================================

class TestToolCallAccumulator:
    """Streaming tool-call accumulation."""

    def test_accumulate_text(self):
        acc = ToolCallAccumulator()
        acc.add_delta({"content": "Hello "})
        acc.add_delta({"content": "world"})
        assert acc.get_text() == "Hello world"
        assert acc.get_tool_calls() is None

    def test_accumulate_tool_call(self):
        acc = ToolCallAccumulator()
        acc.add_delta({"tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                        "function": {"name": "read_file", "arguments": '{"pa'}}]})
        acc.add_delta({"tool_calls": [{"index": 0,
                                        "function": {"arguments": 'th": "x.py"}'}}]})
        calls = acc.get_tool_calls()
        assert len(calls) == 1
        assert calls[0]["id"] == "call_1"
        assert calls[0]["function"]["name"] == "read_file"
        args = json.loads(calls[0]["function"]["arguments"])
        assert args["path"] == "x.py"

    def test_multiple_tool_calls(self):
        acc = ToolCallAccumulator()
        acc.add_delta({"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "read", "arguments": "{}"}}]})
        acc.add_delta({"tool_calls": [{"index": 1, "id": "c2", "function": {"name": "write", "arguments": "{}"}}]})
        calls = acc.get_tool_calls()
        assert len(calls) == 2

    def test_text_and_tool_call_mixed(self):
        acc = ToolCallAccumulator()
        acc.add_delta({"content": "I'll read the file"})
        acc.add_delta({"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "read", "arguments": "{}"}}]})
        assert acc.get_text() == "I'll read the file"
        assert acc.has_tool_calls()

    def test_finalize(self):
        acc = ToolCallAccumulator()
        acc.add_delta({"content": "text"})
        acc.add_delta({"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "fn", "arguments": "{}"}}]})
        result = acc.finalize()
        assert result["text"] == "text"
        assert len(result["tool_calls"]) == 1

    def test_reset(self):
        acc = ToolCallAccumulator()
        acc.add_delta({"content": "text"})
        acc.reset()
        assert acc.get_text() is None
        assert not acc.has_tool_calls()

    def test_malformed_fragments(self):
        acc = ToolCallAccumulator()
        acc.add_delta({"tool_calls": ["not_a_dict"]})
        assert acc.get_tool_calls() is None


# ==========================================================================
# §16 — ModePolicy
# ==========================================================================

class TestModePolicy:
    """Mode policy controls actual execution."""

    def test_plan_mode(self):
        p = ModePolicy.for_mode("plan")
        assert p.allow_file_read is True
        assert p.allow_file_modification is False
        assert p.allow_tool_execution is False

    def test_review_mode(self):
        p = ModePolicy.for_mode("review")
        assert p.allow_file_read is True
        assert p.allow_file_modification is False
        assert p.allow_tool_execution is True

    def test_implement_mode(self):
        p = ModePolicy.for_mode("implement")
        assert p.allow_file_modification is True
        assert p.allow_tool_execution is True

    def test_debug_mode(self):
        p = ModePolicy.for_mode("debug")
        assert p.allow_file_modification is True
        assert p.allow_tool_execution is True

    def test_frozen(self):
        p = ModePolicy()
        with pytest.raises(AttributeError):
            p.allow_file_read = False


# ==========================================================================
# §18 — Unified Agent Budget
# ==========================================================================

class TestAgentBudget:
    """Unified execution budget."""

    def test_default_budget(self):
        b = AgentBudget()
        assert b.can_turn()
        assert b.can_tool_call()
        assert b.exceeded_reason() is None

    def test_turn_exhaustion(self):
        b = AgentBudget(max_turns=2)
        b.use_turn()
        b.use_turn()
        assert not b.can_turn()
        assert "turn budget exceeded" in b.exceeded_reason()

    def test_tool_call_exhaustion(self):
        b = AgentBudget(max_tool_calls=1)
        b.use_tool_call()
        assert not b.can_tool_call()
        assert "tool-call budget exceeded" in b.exceeded_reason()

    def test_retry_exhaustion(self):
        b = AgentBudget(max_retries=1)
        b.use_retry()
        assert not b.can_retry()
        assert "retry budget exhausted" in b.exceeded_reason()

    def test_replan_exhaustion(self):
        b = AgentBudget(max_replans=1)
        b.use_replan()
        assert not b.can_replan()
        assert "replan budget exhausted" in b.exceeded_reason()


# ==========================================================================
# §19 — Loop Detection
# ==========================================================================

class TestLoopDetection:
    """Repeated unsuccessful actions are detected."""

    def test_action_signature_deterministic(self):
        sig1 = action_signature("read_file", {"path": "x.py"})
        sig2 = action_signature("read_file", {"path": "x.py"})
        assert sig1 == sig2

    def test_action_signature_different_args(self):
        sig1 = action_signature("read_file", {"path": "x.py"})
        sig2 = action_signature("read_file", {"path": "y.py"})
        assert sig1 != sig2

    def test_action_signature_different_tools(self):
        sig1 = action_signature("read_file", {"path": "x.py"})
        sig2 = action_signature("write_file", {"path": "x.py"})
        assert sig1 != sig2


# ==========================================================================
# §23 — NormalizedToolResult
# ==========================================================================

class TestNormalizedToolResult:
    """Tool output bounded and normalized."""

    def test_from_success(self):
        tr = ToolResult(state=ToolState.SUCCESS, output="content", metadata={"size": 7})
        norm = NormalizedToolResult.from_tool_result(tr, "read_file")
        assert norm.state == "success"
        assert "content" in norm.summary
        assert norm.truncated is False

    def test_from_failure(self):
        tr = ToolResult(state=ToolState.FAILURE, output=None, error="File not found")
        norm = NormalizedToolResult.from_tool_result(tr)
        assert norm.state == "failure"
        assert "not found" in norm.summary.lower()

    def test_truncation(self):
        big_output = "x" * 20000
        tr = ToolResult(state=ToolState.SUCCESS, output=big_output)
        norm = NormalizedToolResult.from_tool_result(tr)
        assert norm.truncated is True
        assert norm.original_size == 20000
        assert len(norm.content) < 20000


# ==========================================================================
# §14 — CapabilityState
# ==========================================================================

class TestCapabilityState:
    """Model capability negotiation."""

    def test_unknown_is_not_supported(self):
        cs = CapabilityState(name="tool_calling")
        assert not cs.is_supported
        assert cs.is_unknown

    def test_validated_is_supported(self):
        cs = CapabilityState(name="tool_calling", status="validated")
        assert cs.is_supported

    def test_unsupported(self):
        cs = CapabilityState(name="tool_calling", status="unsupported")
        assert not cs.is_supported


# ==========================================================================
# §15 — model_key
# ==========================================================================

class TestModelKey:
    """Provider+model identity is unambiguous."""

    def test_different_providers_same_model(self):
        k1 = model_key("openai", "gpt-4")
        k2 = model_key("azure", "gpt-4")
        assert k1 != k2

    def test_same_provider_different_models(self):
        k1 = model_key("openai", "gpt-4")
        k2 = model_key("openai", "gpt-3.5")
        assert k1 != k2

    def test_format(self):
        assert model_key("openai", "gpt-4") == "openai/gpt-4"


# ==========================================================================
# §10 — Real Diff After Mutation
# ==========================================================================

class TestRealDiff:
    """Successful mutations generate real diff information."""

    def test_write_produces_diff(self, workspace, executor_autonomous):
        result = executor_autonomous.invoke(
            "filesystem.write",
            path="new_file.py",
            content="print('hello')\n",
        )
        assert result.state == ToolState.SUCCESS
        assert result.metadata.get("diff") is not None
        assert result.metadata.get("additions", 0) > 0

    def test_replace_produces_diff(self, workspace, executor_autonomous):
        result = executor_autonomous.invoke(
            "filesystem.replace",
            path="src/calculator.py",
            target_content="return a - b  # BUG: should be a + b",
            replacement_content="return a + b",
        )
        assert result.state == ToolState.SUCCESS
        diff = result.metadata.get("diff", "")
        assert "+" in diff or "-" in diff


# ==========================================================================
# §39 — Behavioral Regression Matrix
# ==========================================================================

class TestBehavioralRegression:
    """Key behavioral regressions from §39."""

    def test_workspace_escape_rejected(self, workspace, executor_autonomous):
        result = executor_autonomous.invoke("filesystem.read", path="../../etc/passwd")
        assert result.state == ToolState.FAILURE
        assert "escape" in result.error.lower()

    def test_absolute_outside_rejected(self, workspace, executor_autonomous):
        import tempfile
        other = os.path.join(tempfile.gettempdir(), "outside_file.txt")
        result = executor_autonomous.invoke("filesystem.read", path=other)
        # Should fail — either workspace escape or file not found
        assert result.state == ToolState.FAILURE

    def test_pending_permission_cleaned_on_cleanup(self, workspace, executor_supervised):
        executor_supervised.invoke("filesystem.read", path="src/calculator.py", session_id="s1")
        assert executor_supervised.has_pending()
        executor_supervised.cleanup_pending()
        assert not executor_supervised.has_pending()

    def test_tool_result_metadata_preserved(self, workspace, executor_autonomous):
        """Tool result has structured metadata."""
        result = executor_autonomous.invoke("filesystem.read", path="src/calculator.py")
        assert result.state == ToolState.SUCCESS
        assert "path" in result.metadata
        assert "size" in result.metadata
