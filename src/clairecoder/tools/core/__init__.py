"""Core tool implementations for ClaireCoder.

These are stub implementations that define the correct Tool contracts,
metadata, permission declarations, and input validation for the core
tool categories required by CC-PRD-003 / CC-ADR-003.

Actual I/O operations are NOT performed — these tools serve as the
architectural contract and will be connected to real backends in
later phases. The stubs return structured ToolResult objects to
verify the full permission-integrated execution path.
"""
from typing import Any, Dict, List, Optional
from clairecoder.core.types import PermissionRequirement, ToolResult, ToolState
from ..base import Tool
from ..types import ToolMetadata, ToolCategory, ToolValidationError


class ReadFileTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="filesystem.read",
            name="Read File",
            description="Read the contents of a file.",
            version="1.0.0",
            category=ToolCategory.FILESYSTEM,
            input_schema={"path": {"type": "string", "required": True}},
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="read", resource="file", scope="file")]

    def validate_input(self, **kwargs: Any) -> None:
        if "path" not in kwargs or not isinstance(kwargs["path"], str):
            raise ToolValidationError("'path' is required and must be a string")
        if not kwargs["path"].strip():
            raise ToolValidationError("'path' must not be empty")

    def _execute(self, **kwargs: Any) -> ToolResult:
        # Stub: would read actual file in production
        return ToolResult(
            state=ToolState.SUCCESS,
            output=f"[stub] contents of {kwargs['path']}",
            metadata={"path": kwargs["path"]}
        )


class WriteFileTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="filesystem.write",
            name="Write File",
            description="Write content to a file.",
            version="1.0.0",
            category=ToolCategory.FILESYSTEM,
            input_schema={
                "path": {"type": "string", "required": True},
                "content": {"type": "string", "required": True},
            },
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="write", resource="file", scope="file")]

    def validate_input(self, **kwargs: Any) -> None:
        if "path" not in kwargs or not isinstance(kwargs["path"], str):
            raise ToolValidationError("'path' is required and must be a string")
        if "content" not in kwargs:
            raise ToolValidationError("'content' is required")

    def _execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            state=ToolState.SUCCESS,
            output=f"[stub] wrote to {kwargs['path']}",
            metadata={"path": kwargs["path"], "bytes_written": len(str(kwargs["content"]))}
        )


class DeleteFileTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="filesystem.delete",
            name="Delete File",
            description="Delete a file or directory.",
            version="1.0.0",
            category=ToolCategory.FILESYSTEM,
            input_schema={"path": {"type": "string", "required": True}},
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="delete", resource="file", scope="file")]

    def validate_input(self, **kwargs: Any) -> None:
        if "path" not in kwargs or not isinstance(kwargs["path"], str):
            raise ToolValidationError("'path' is required and must be a string")

    def _execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            state=ToolState.SUCCESS,
            output=f"[stub] deleted {kwargs['path']}",
            metadata={"path": kwargs["path"]}
        )


class SearchTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="search.text",
            name="Text Search",
            description="Search for text patterns across the repository.",
            version="1.0.0",
            category=ToolCategory.SEARCH,
            input_schema={"query": {"type": "string", "required": True}},
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="read", resource="repository", scope="project")]

    def validate_input(self, **kwargs: Any) -> None:
        if "query" not in kwargs or not isinstance(kwargs["query"], str):
            raise ToolValidationError("'query' is required and must be a string")

    def _execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            state=ToolState.SUCCESS,
            output=f"[stub] search results for '{kwargs['query']}'",
            metadata={"query": kwargs["query"], "matches": 0}
        )


class TerminalTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="shell.execute",
            name="Terminal",
            description="Execute a shell command.",
            version="1.0.0",
            category=ToolCategory.SHELL,
            input_schema={"command": {"type": "string", "required": True}},
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="execute", resource="command", scope="command")]

    def validate_input(self, **kwargs: Any) -> None:
        if "command" not in kwargs or not isinstance(kwargs["command"], str):
            raise ToolValidationError("'command' is required and must be a string")
        if not kwargs["command"].strip():
            raise ToolValidationError("'command' must not be empty")

    def _execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            state=ToolState.SUCCESS,
            output=f"[stub] executed: {kwargs['command']}",
            metadata={"command": kwargs["command"], "exit_code": 0}
        )


class GitStatusTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="git.status",
            name="Git Status",
            description="Inspect the current Git repository status.",
            version="1.0.0",
            category=ToolCategory.VERSION_CONTROL,
            input_schema={},
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="read", resource="repository", scope="repository")]

    def validate_input(self, **kwargs: Any) -> None:
        pass  # No required input

    def _execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            state=ToolState.SUCCESS,
            output="[stub] git status output",
            metadata={"branch": "main", "clean": True}
        )


class GitCommitTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="git.commit",
            name="Git Commit",
            description="Create a Git commit.",
            version="1.0.0",
            category=ToolCategory.VERSION_CONTROL,
            input_schema={"message": {"type": "string", "required": True}},
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="modify_repository", resource="repository", scope="repository")]

    def validate_input(self, **kwargs: Any) -> None:
        if "message" not in kwargs or not isinstance(kwargs["message"], str):
            raise ToolValidationError("'message' is required and must be a string")

    def _execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            state=ToolState.SUCCESS,
            output=f"[stub] committed: {kwargs['message']}",
            metadata={"message": kwargs["message"]}
        )


class RunTestsTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="testing.run",
            name="Run Tests",
            description="Run the project test suite.",
            version="1.0.0",
            category=ToolCategory.TESTING,
            input_schema={"target": {"type": "string", "required": False}},
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="execute", resource="command", scope="project")]

    def validate_input(self, **kwargs: Any) -> None:
        if "target" in kwargs and not isinstance(kwargs["target"], str):
            raise ToolValidationError("'target' must be a string if provided")

    def _execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            state=ToolState.SUCCESS,
            output="[stub] test results",
            metadata={"passed": 0, "failed": 0, "target": kwargs.get("target")}
        )


class DiagnosticsTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="diagnostics.lint",
            name="Diagnostics",
            description="Run linting and static analysis.",
            version="1.0.0",
            category=ToolCategory.DIAGNOSTICS,
            input_schema={"path": {"type": "string", "required": False}},
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="read", resource="file", scope="project")]

    def validate_input(self, **kwargs: Any) -> None:
        if "path" in kwargs and not isinstance(kwargs["path"], str):
            raise ToolValidationError("'path' must be a string if provided")

    def _execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            state=ToolState.SUCCESS,
            output="[stub] diagnostics output",
            metadata={"issues": 0, "path": kwargs.get("path")}
        )
