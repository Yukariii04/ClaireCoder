"""Structured core tools implementing the Tool model (Correction #19 §4, §5).

Wraps filesystem access via Workspace and command execution into:
- ReadFileTool ("read_file")
- WriteFileTool ("write_file")
- DeleteFileTool ("delete_file")
- ListFilesTool ("list_files")
- RunCommandTool ("run_command")
"""

import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from clairecoder.core.types import ToolResult, ToolState
from clairecoder.workspace.errors import (
    WorkspaceBinaryFileError,
    WorkspaceFileNotFoundError,
    WorkspaceFileTooLargeError,
    WorkspaceIsADirectoryError,
    WorkspaceNotADirectoryError,
    WorkspacePathEscapeError,
    WorkspacePermissionError,
)
from clairecoder.workspace.workspace import Workspace
from .tool import Tool, ToolContext, normalize_tool_call


def _resolve_workspace(instance_ws: Optional[Workspace], context: Optional[ToolContext]) -> Workspace:
    """Resolve active workspace from instance, context, or fallback to current directory."""
    if instance_ws is not None:
        return instance_ws
    if context is not None and getattr(context, "workspace", None) is not None:
        return context.workspace
    from clairecoder.tools.core import get_workspace_root
    return Workspace(get_workspace_root())


# =============================================================================
# READ FILE TOOL
# =============================================================================

class ReadFileTool(Tool):
    """Reads file content safely within the workspace boundary."""

    def __init__(self, workspace: Optional[Workspace] = None) -> None:
        self._workspace = workspace

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the text contents of a file within the workspace."

    def execute(
        self,
        context: Optional[Any] = None,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        ctx, args = normalize_tool_call(context, arguments, kwargs)
        path = args.get("path")
        if not path or not isinstance(path, (str, Path)) or not str(path).strip():
            return ToolResult(
                success=False,
                error="Argument 'path' is required and must be a non-empty string",
                metadata={"error_type": "invalid_arguments"},
            )

        path_str = str(path).strip()
        ws = _resolve_workspace(self._workspace, ctx)
        start_t = time.time()

        try:
            content = ws.read_file(path_str)
            duration = time.time() - start_t
            return ToolResult(
                success=True,
                output=content,
                duration=duration,
                metadata={"path": path_str, "size": len(content)},
            )
        except WorkspacePathEscapeError as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": path_str, "error_type": "WorkspacePathEscapeError"},
            )
        except WorkspaceFileNotFoundError as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": path_str, "error_type": "WorkspaceFileNotFoundError"},
            )
        except WorkspaceIsADirectoryError as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": path_str, "error_type": "WorkspaceIsADirectoryError"},
            )
        except WorkspaceBinaryFileError as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": path_str, "is_binary": True, "error_type": "WorkspaceBinaryFileError"},
            )
        except WorkspaceFileTooLargeError as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": path_str, "error_type": "WorkspaceFileTooLargeError"},
            )
        except Exception as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": path_str},
            )


# =============================================================================
# WRITE FILE TOOL
# =============================================================================

class WriteFileTool(Tool):
    """Writes content to a file within the workspace boundary."""

    def __init__(self, workspace: Optional[Workspace] = None) -> None:
        self._workspace = workspace

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file within the workspace."

    def execute(
        self,
        context: Optional[Any] = None,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        ctx, args = normalize_tool_call(context, arguments, kwargs)
        path = args.get("path")
        if not path or not isinstance(path, (str, Path)) or not str(path).strip():
            return ToolResult(
                success=False,
                error="Argument 'path' is required and must be a non-empty string",
                metadata={"error_type": "invalid_arguments"},
            )
        if "content" not in args:
            return ToolResult(
                success=False,
                error="Argument 'content' is required",
                metadata={"error_type": "invalid_arguments"},
            )

        path_str = str(path).strip()
        content = args["content"]
        ws = _resolve_workspace(self._workspace, ctx)
        start_t = time.time()

        try:
            bytes_written = ws.write_file(path_str, content)
            rel_path = ws.relative_path(path_str)
            duration = time.time() - start_t
            return ToolResult(
                success=True,
                output=f"Successfully wrote {bytes_written} bytes to {path_str}",
                changed_files=[rel_path],
                duration=duration,
                metadata={"path": path_str, "bytes_written": bytes_written},
            )
        except WorkspacePathEscapeError as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": path_str, "error_type": "WorkspacePathEscapeError"},
            )
        except Exception as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": path_str},
            )


# =============================================================================
# DELETE FILE TOOL
# =============================================================================

class DeleteFileTool(Tool):
    """Deletes a file within the workspace boundary."""

    def __init__(self, workspace: Optional[Workspace] = None) -> None:
        self._workspace = workspace

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return "Delete a file within the workspace."

    def execute(
        self,
        context: Optional[Any] = None,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        ctx, args = normalize_tool_call(context, arguments, kwargs)
        path = args.get("path")
        if not path or not isinstance(path, (str, Path)) or not str(path).strip():
            return ToolResult(
                success=False,
                error="Argument 'path' is required and must be a non-empty string",
                metadata={"error_type": "invalid_arguments"},
            )

        path_str = str(path).strip()
        ws = _resolve_workspace(self._workspace, ctx)
        start_t = time.time()

        try:
            rel_path = ws.relative_path(path_str)
            ws.delete_file(path_str)
            duration = time.time() - start_t
            return ToolResult(
                success=True,
                output=f"Successfully deleted {path_str}",
                changed_files=[rel_path],
                duration=duration,
                metadata={"path": path_str},
            )
        except (WorkspacePathEscapeError, WorkspaceFileNotFoundError, WorkspaceIsADirectoryError) as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": path_str, "error_type": type(e).__name__},
            )
        except Exception as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": path_str},
            )


# =============================================================================
# LIST FILES TOOL
# =============================================================================

class ListFilesTool(Tool):
    """Lists files and directories within the workspace with deterministic ordering."""

    def __init__(self, workspace: Optional[Workspace] = None) -> None:
        self._workspace = workspace

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "List files and directories in the workspace."

    def execute(
        self,
        context: Optional[Any] = None,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        ctx, args = normalize_tool_call(context, arguments, kwargs)
        path = args.get("path", "")
        recursive = bool(args.get("recursive", False))
        ws = _resolve_workspace(self._workspace, ctx)
        start_t = time.time()

        try:
            files = ws.list_files(path=path or "", recursive=recursive)
            duration = time.time() - start_t
            return ToolResult(
                success=True,
                output=files,
                duration=duration,
                metadata={"path": str(path), "count": len(files), "recursive": recursive},
            )
        except (WorkspacePathEscapeError, WorkspaceFileNotFoundError, WorkspaceNotADirectoryError) as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": str(path), "error_type": type(e).__name__},
            )
        except Exception as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"path": str(path)},
            )


# =============================================================================
# RUN COMMAND TOOL
# =============================================================================

class RunCommandTool(Tool):
    """Runs a command strictly within the workspace directory boundary (Correction #19 §5)."""

    def __init__(
        self,
        workspace: Optional[Workspace] = None,
        default_timeout: int = 60,
    ) -> None:
        self._workspace = workspace
        self._default_timeout = default_timeout

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return "Run a command within the workspace directory."

    def execute(
        self,
        context: Optional[Any] = None,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        ctx, args = normalize_tool_call(context, arguments, kwargs)
        cmd = args.get("command")
        if not cmd or not isinstance(cmd, str) or not cmd.strip():
            return ToolResult(
                success=False,
                error="Argument 'command' is required and must be a non-empty string",
                metadata={"error_type": "invalid_arguments"},
            )

        cmd_str = cmd.strip()
        timeout = int(args.get("timeout", self._default_timeout))
        ws = _resolve_workspace(self._workspace, ctx)
        cwd = str(ws.root)
        start_t = time.time()

        try:
            res = subprocess.run(
                cmd_str,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = time.time() - start_t
            exit_code = res.returncode
            stdout = res.stdout or ""
            stderr = res.stderr or ""
            success = (exit_code == 0)
            if success:
                out = stdout
                err = None
            else:
                out = stdout or stderr or f"Process exited with code {exit_code}"
                err = f"Process exited with code {exit_code}"
                if stderr.strip():
                    err = f"{err}: {stderr.strip()}"

            return ToolResult(
                success=success,
                output=out,
                error=err,
                duration=duration,
                metadata={
                    "command": cmd_str,
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                    "duration": duration,
                    "cwd": cwd,
                    "timed_out": False,
                },
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.time() - start_t
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return ToolResult(
                success=False,
                output=stdout,
                error=f"Command timed out after {timeout} seconds: {cmd_str}",
                duration=duration,
                metadata={
                    "command": cmd_str,
                    "exit_code": None,
                    "stdout": stdout,
                    "stderr": stderr,
                    "duration": duration,
                    "cwd": cwd,
                    "timed_out": True,
                },
            )
        except Exception as e:
            duration = time.time() - start_t
            return ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={
                    "command": cmd_str,
                    "cwd": cwd,
                    "duration": duration,
                },
            )
