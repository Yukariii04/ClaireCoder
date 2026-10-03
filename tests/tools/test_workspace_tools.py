r"""Tests for Tool abstraction, core tools, and ToolRegistry (Correction #19).

Validates:
- registry registration
- duplicate registration rejection (DuplicateToolError)
- unknown tool resolution rejection (UnknownToolError)
- read_file tool execution & result structure
- write_file tool execution & changeset metadata
- delete_file tool execution & changeset metadata
- list_files tool execution & options
- run_command tool execution (exit_code, stdout, stderr, duration, success)
- command result structure
- tool failure propagation (graceful ToolResult error, no unexpected crash)
- injected fake tool execution
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional
import pytest

from clairecoder.workspace import Workspace
from clairecoder.core.types import ToolResult
from clairecoder.tools import (
    Tool,
    ToolContext,
    ToolRegistry,
    ReadFileTool,
    WriteFileTool,
    DeleteFileTool,
    ListFilesTool,
    RunCommandTool,
    ToolError,
    UnknownToolError,
    DuplicateToolError,
    InvalidToolArgumentsError,
)


class FakeEchoTool(Tool):
    """Injected fake tool for registry and execution testing."""

    @property
    def name(self) -> str:
        return "fake_echo"

    @property
    def description(self) -> str:
        return "Echoes message back"

    def execute(
        self,
        context: Optional[ToolContext] = None,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        args = arguments or {}
        msg = args.get("message", "default")
        return ToolResult(
            success=True,
            output=f"Echo: {msg}",
            metadata={"injected": True},
        )


class TestToolRegistry:
    """Tests for ToolRegistry behavior."""

    @pytest.fixture
    def registry(self, tmp_path: Path) -> ToolRegistry:
        ws = Workspace(tmp_path)
        return ToolRegistry(workspace=ws)

    def test_register_and_resolve(self, registry: ToolRegistry):
        fake = FakeEchoTool()
        registry.register(fake)
        assert registry.has("fake_echo")
        assert "fake_echo" in registry.registered_names
        resolved = registry.resolve("fake_echo")
        assert resolved is fake

    def test_duplicate_registration_raises_error(self, registry: ToolRegistry):
        fake1 = FakeEchoTool()
        fake2 = FakeEchoTool()
        registry.register(fake1)
        with pytest.raises(DuplicateToolError) as exc_info:
            registry.register(fake2)
        assert "already registered" in str(exc_info.value).lower()
        assert exc_info.value.tool_name == "fake_echo"

    def test_duplicate_registration_with_overwrite(self, registry: ToolRegistry):
        fake1 = FakeEchoTool()
        fake2 = FakeEchoTool()
        registry.register(fake1)
        registry.register(fake2, overwrite=True)
        assert registry.resolve("fake_echo") is fake2

    def test_unknown_tool_raises_error(self, registry: ToolRegistry):
        with pytest.raises(UnknownToolError) as exc_info:
            registry.resolve("nonexistent_tool")
        assert "unknown tool" in str(exc_info.value).lower()
        assert exc_info.value.tool_name == "nonexistent_tool"

    def test_execute_injected_fake_tool(self, registry: ToolRegistry):
        registry.register(FakeEchoTool())
        result = registry.execute("fake_echo", arguments={"message": "hello"})
        assert result.success is True
        assert result.output == "Echo: hello"
        assert result.metadata.get("injected") is True

    def test_create_default_registry(self, tmp_path: Path):
        ws = Workspace(tmp_path)
        reg = ToolRegistry.create_default(workspace=ws)
        names = reg.registered_names
        assert "read_file" in names
        assert "write_file" in names
        assert "delete_file" in names
        assert "list_files" in names
        assert "run_command" in names
        assert len(names) == 5


class TestCoreTools:
    """Tests for core built-in tools."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Workspace:
        return Workspace(tmp_path)

    @pytest.fixture
    def context(self, workspace: Workspace) -> ToolContext:
        return ToolContext(
            run_id="run_test",
            task_id="task_1",
            workspace=workspace,
        )

    def test_write_file_tool(self, workspace: Workspace, context: ToolContext):
        tool = WriteFileTool(workspace=workspace)
        result = tool.execute(context, {"path": "src/code.py", "content": "print(42)"})

        assert result.success is True
        assert "wrote" in result.output.lower()
        assert result.changed_files == ["src/code.py"]
        assert workspace.read_file("src/code.py") == "print(42)"

    def test_read_file_tool(self, workspace: Workspace, context: ToolContext):
        workspace.write_file("data.txt", "some important data")
        tool = ReadFileTool(workspace=workspace)
        result = tool.execute(context, {"path": "data.txt"})

        assert result.success is True
        assert result.output == "some important data"
        assert result.metadata.get("path") == "data.txt"

    def test_delete_file_tool(self, workspace: Workspace, context: ToolContext):
        workspace.write_file("temp.txt", "temp data")
        assert workspace.exists("temp.txt")

        tool = DeleteFileTool(workspace=workspace)
        result = tool.execute(context, {"path": "temp.txt"})

        assert result.success is True
        assert not workspace.exists("temp.txt")
        assert result.changed_files == ["temp.txt"]

    def test_list_files_tool(self, workspace: Workspace, context: ToolContext):
        workspace.write_file("b.txt", "b")
        workspace.write_file("a.txt", "a")
        workspace.write_file("sub/c.txt", "c")

        tool = ListFilesTool(workspace=workspace)
        result = tool.execute(context, {"path": ".", "recursive": True})

        assert result.success is True
        assert isinstance(result.output, list)
        normalized = [p.replace("\\", "/") for p in result.output]
        assert normalized == ["a.txt", "b.txt", "sub/c.txt"]

    def test_run_command_tool(self, workspace: Workspace, context: ToolContext):
        tool = RunCommandTool(workspace=workspace)
        # Run a simple python one-liner using the current python executable
        cmd = f'"{sys.executable}" -c "import sys; sys.stdout.write(\'stdout_msg\'); sys.stderr.write(\'stderr_msg\')"'
        result = tool.execute(context, {"command": cmd})

        assert result.success is True
        assert result.metadata["command"] == cmd
        assert result.metadata["exit_code"] == 0
        assert "stdout_msg" in result.metadata["stdout"]
        assert "stderr_msg" in result.metadata["stderr"]
        assert result.duration >= 0.0

    def test_run_command_failure_reports_structured_error(self, workspace: Workspace, context: ToolContext):
        tool = RunCommandTool(workspace=workspace)
        cmd = f'"{sys.executable}" -c "import sys; sys.exit(7)"'
        result = tool.execute(context, {"command": cmd})

        assert result.success is False
        assert result.metadata["exit_code"] == 7
        assert "code 7" in result.error.lower()

    def test_tool_failure_propagation_missing_path(self, workspace: Workspace, context: ToolContext):
        tool = ReadFileTool(workspace=workspace)
        result = tool.execute(context, {"path": "nonexistent.txt"})

        assert result.success is False
        assert "not found" in result.error.lower()
        assert result.metadata.get("error_type") == "WorkspaceFileNotFoundError"

    def test_tool_failure_propagation_path_traversal(self, workspace: Workspace, context: ToolContext):
        tool = ReadFileTool(workspace=workspace)
        result = tool.execute(context, {"path": "../../secret.txt"})

        assert result.success is False
        assert "escapes workspace" in result.error.lower()
        assert result.metadata.get("error_type") == "WorkspacePathEscapeError"

    def test_invalid_arguments_reports_structured_error(self, workspace: Workspace, context: ToolContext):
        tool = WriteFileTool(workspace=workspace)
        # Missing content argument
        result = tool.execute(context, {"path": "test.txt"})

        assert result.success is False
        assert "required" in result.error.lower()
        assert result.metadata.get("error_type") == "invalid_arguments"
