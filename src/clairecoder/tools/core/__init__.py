"""Core tool implementations for ClaireCoder.

Defines the Tool contracts, metadata, permission declarations, and input validation
for the core tool categories required by CC-PRD-003 / CC-ADR-003.
Provides real filesystem, search, and terminal execution with safety boundaries.

§6 — Central workspace path resolver used for all file-based tools.
§7 — Terminal uses authoritative workspace cwd.
§8 — No false success semantics.
§9 — Real edit with diff output and recovery hints.
§10 — Real diff after mutation.
"""
import os
import base64
import subprocess
import time
import difflib
from pathlib import Path
from typing import Any, Dict, List, Optional

from clairecoder.core.types import PermissionRequirement, ToolResult, ToolState
from ..base import Tool
from ..types import ToolMetadata, ToolCategory, ToolValidationError
from ..workspace import resolve_workspace_path, WorkspaceSecurityError


# ---------------------------------------------------------------------------
# Module-level workspace root — set by the runtime at initialization.
# Tools use this as the authoritative workspace boundary.
# If not set, tools fall back to the current working directory.
# ---------------------------------------------------------------------------
_workspace_root: Optional[Path] = None


def set_workspace_root(root) -> None:
    """Set the authoritative workspace root for all core tools. Pass None to reset."""
    global _workspace_root
    if root is None:
        _workspace_root = None
    else:
        _workspace_root = Path(root).resolve()


def get_workspace_root() -> Path:
    """Get the authoritative workspace root, defaulting to cwd."""
    global _workspace_root
    if _workspace_root is not None:
        return _workspace_root
    return Path.cwd().resolve()


def _resolve_path(path_str: str) -> Path:
    """Resolve a path within the workspace boundary.

    Raises WorkspaceSecurityError if the path escapes.
    """
    return resolve_workspace_path(get_workspace_root(), path_str)


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
        path_str = kwargs.get("path", "").strip()
        try:
            p = _resolve_path(path_str)
        except WorkspaceSecurityError as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e), metadata={"path": path_str})

        # §8: Missing file is FAILURE, not SUCCESS with "[file not found]"
        if not p.exists():
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=f"File not found: {path_str}",
                metadata={"path": path_str, "reason": "not_found"},
            )
        if p.is_dir():
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=f"Path is a directory, not a file: {path_str}",
                metadata={"path": path_str, "reason": "is_directory"},
            )
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            return ToolResult(
                state=ToolState.SUCCESS,
                output=content,
                metadata={"path": str(p), "size": len(content)},
            )
        except Exception as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e), metadata={"path": path_str})


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
        path_str = kwargs.get("path", "").strip()
        content = str(kwargs.get("content", ""))
        try:
            p = _resolve_path(path_str)
        except WorkspaceSecurityError as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e), metadata={"path": path_str})

        try:
            # §10: Capture before-state for diff
            before = ""
            existed_before = p.exists() and p.is_file()
            if existed_before:
                try:
                    before = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

            # Generate diff
            diff_info = _generate_diff(before, content, str(p))

            return ToolResult(
                state=ToolState.SUCCESS,
                output=f"Successfully wrote {len(content)} bytes to {path_str}",
                metadata={
                    "path": str(p),
                    "existed_before": existed_before,
                    "bytes_written": len(content),
                    "additions": diff_info["additions"],
                    "deletions": diff_info["deletions"],
                    "diff": diff_info["diff"],
                },
            )
        except Exception as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e), metadata={"path": path_str})


class ReplaceFileContentTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="filesystem.replace",
            name="Replace File Content",
            description="Replace target text in a file with new content.",
            version="1.0.0",
            category=ToolCategory.FILESYSTEM,
            input_schema={
                "path": {"type": "string", "required": True},
                "target_content": {"type": "string", "required": False},
                "replacement_content": {"type": "string", "required": False},
            },
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="write", resource="file", scope="file")]

    def validate_input(self, **kwargs: Any) -> None:
        if "path" not in kwargs or not isinstance(kwargs["path"], str):
            raise ToolValidationError("'path' is required and must be a string")

    def _execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", "").strip()
        target = kwargs.get("target_content") or kwargs.get("old_str") or kwargs.get("find", "")
        replacement = kwargs.get("replacement_content") or kwargs.get("new_str") or kwargs.get("replace", "")

        try:
            p = _resolve_path(path_str)
        except WorkspaceSecurityError as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e), metadata={"path": path_str})

        # §8: File not found is FAILURE
        if not p.exists() or not p.is_file():
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=f"File not found: {path_str}. Cannot edit a file that does not exist.",
                metadata={"path": path_str, "reason": "not_found"},
            )

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            before = content

            if target:
                count = content.count(target)
                if count == 0:
                    # §9: Recovery hint for failed edit
                    return ToolResult(
                        state=ToolState.FAILURE,
                        output=None,
                        error=(
                            f"Target text was not found in {path_str}. "
                            "The file may have changed since the previous read. "
                            "Re-read the file before attempting another edit."
                        ),
                        metadata={"path": path_str, "reason": "target_not_found"},
                    )
                if count > 1:
                    return ToolResult(
                        state=ToolState.FAILURE,
                        output=None,
                        error=(
                            f"Target text found {count} times in {path_str}. "
                            "Provide a more specific target to avoid ambiguous edits."
                        ),
                        metadata={"path": path_str, "reason": "ambiguous_match", "match_count": count},
                    )
                new_content = content.replace(target, replacement, 1)
            else:
                new_content = replacement

            # §9: Detect no-op edit
            if new_content == before:
                return ToolResult(
                    state=ToolState.SUCCESS,
                    output=f"No changes needed in {path_str} (content already matches).",
                    metadata={"path": path_str, "changed": False, "additions": 0, "deletions": 0},
                )

            p.write_text(new_content, encoding="utf-8")

            # §10: Generate real diff
            diff_info = _generate_diff(before, new_content, str(p))

            return ToolResult(
                state=ToolState.SUCCESS,
                output=f"Successfully updated {path_str}",
                metadata={
                    "path": str(p),
                    "changed": True,
                    "additions": diff_info["additions"],
                    "deletions": diff_info["deletions"],
                    "diff": diff_info["diff"],
                },
            )
        except Exception as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e), metadata={"path": path_str})


class ListDirTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="filesystem.list",
            name="List Directory",
            description="List files and directories at path.",
            version="1.0.0",
            category=ToolCategory.FILESYSTEM,
            input_schema={"path": {"type": "string", "required": False}},
        )

    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="read", resource="file", scope="directory")]

    def validate_input(self, **kwargs: Any) -> None:
        if "path" in kwargs and not isinstance(kwargs["path"], str):
            raise ToolValidationError("'path' must be a string if provided")

    def _execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", ".").strip() or "."
        try:
            p = _resolve_path(path_str)
        except WorkspaceSecurityError as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e))

        if not p.exists():
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=f"Directory not found: {path_str}",
                metadata={"path": path_str, "reason": "not_found"},
            )
        if not p.is_dir():
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=f"Path is a file, not a directory: {path_str}",
                metadata={"path": path_str, "reason": "not_directory"},
            )
        try:
            entries = []
            for item in sorted(p.iterdir()):
                item_type = "dir" if item.is_dir() else "file"
                entries.append(f"{item.name} ({item_type})")
            return ToolResult(
                state=ToolState.SUCCESS,
                output="\n".join(entries) if entries else "(empty directory)",
                metadata={"path": str(p), "count": len(entries)},
            )
        except Exception as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e))


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
        path_str = kwargs.get("path", "").strip()
        try:
            p = _resolve_path(path_str)
        except WorkspaceSecurityError as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e), metadata={"path": path_str})

        if not p.exists():
            # §8: Deleting a non-existent file is not success
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=f"File not found: {path_str}",
                metadata={"path": path_str, "reason": "not_found"},
            )
        try:
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                import shutil
                shutil.rmtree(p)
            return ToolResult(
                state=ToolState.SUCCESS,
                output=f"Successfully deleted {path_str}",
                metadata={"path": str(p)},
            )
        except Exception as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e), metadata={"path": path_str})


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
        query = kwargs.get("query", "")
        search_root = str(get_workspace_root())
        matches = []
        try:
            for root, dirs, files in os.walk(search_root):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "venv", ".git")]
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                            for idx, line in enumerate(file, 1):
                                if query.lower() in line.lower():
                                    # Use relative path
                                    rel = os.path.relpath(fp, search_root)
                                    matches.append(f"{rel}:{idx}: {line.strip()}")
                                    if len(matches) >= 40:
                                        break
                    except Exception:
                        pass
                    if len(matches) >= 40:
                        break
                if len(matches) >= 40:
                    break
            return ToolResult(
                state=ToolState.SUCCESS,
                output="\n".join(matches) if matches else f"No matches found for '{query}'",
                metadata={"query": query, "matches": len(matches)},
            )
        except Exception as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e))


class TerminalTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="shell.execute",
            name="Terminal",
            description=(
                "Run a command in the project workspace. On Windows use PowerShell syntax; "
                "on other platforms use the default POSIX shell. Use filesystem tools for file access."
            ),
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
        cmd = kwargs.get("command", "")
        timeout = kwargs.get("timeout", 60)
        # §7: Use workspace cwd
        cwd = str(get_workspace_root())
        start_time = time.time()

        try:
            if os.name == "nt":
                # Use the shell ClaireCoder tells the model to target. Encoded
                # command input avoids quoting/escaping corruption in paths and
                # nested PowerShell expressions.
                encoded_command = base64.b64encode(cmd.encode("utf-16-le")).decode("ascii")
                run_args = [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-EncodedCommand",
                    encoded_command,
                ]
                res = subprocess.run(
                    run_args,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            else:
                res = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            duration_ms = int((time.time() - start_time) * 1000)
            out = res.stdout
            if res.stderr:
                out = f"{out}\n{res.stderr}" if out else res.stderr

            # §8: Non-zero exit code is FAILURE, not SUCCESS
            return ToolResult(
                state=ToolState.SUCCESS if res.returncode == 0 else ToolState.FAILURE,
                output=out or f"Command finished with code {res.returncode}",
                error=res.stderr if res.returncode != 0 else None,
                metadata={
                    "command": cmd,
                    "cwd": cwd,
                    "exit_code": res.returncode,
                    "duration_ms": duration_ms,
                    "timed_out": False,
                },
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            # §8: Timeout is FAILURE (specifically TIMEOUT state)
            return ToolResult(
                state=ToolState.TIMEOUT,
                output=None,
                error=f"Command timed out after {timeout}s: {cmd}",
                metadata={
                    "command": cmd,
                    "cwd": cwd,
                    "exit_code": None,
                    "duration_ms": duration_ms,
                    "timed_out": True,
                },
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=str(e),
                metadata={"command": cmd, "cwd": cwd, "duration_ms": duration_ms},
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
        pass

    def _execute(self, **kwargs: Any) -> ToolResult:
        cwd = str(get_workspace_root())
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=10,
                cwd=cwd,
            )
            if res.returncode != 0:
                # §8: Git failure is FAILURE, not clean
                return ToolResult(
                    state=ToolState.FAILURE,
                    output=None,
                    error=f"git status failed (exit code {res.returncode}): {res.stderr}",
                    metadata={"exit_code": res.returncode, "cwd": cwd},
                )
            return ToolResult(
                state=ToolState.SUCCESS,
                output=res.stdout or "Clean working directory",
                metadata={"clean": not bool(res.stdout.strip()), "cwd": cwd},
            )
        except FileNotFoundError:
            # §8: Git not installed is UNAVAILABLE, not clean
            return ToolResult(
                state=ToolState.UNAVAILABLE,
                output=None,
                error="git is not installed or not found in PATH",
                metadata={"reason": "git_not_found"},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                state=ToolState.TIMEOUT,
                output=None,
                error="git status timed out",
            )
        except Exception as e:
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=f"git status unavailable: {str(e)}",
                metadata={"reason": "error"},
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
        # §8: Real git commit, not a stub
        msg = kwargs["message"]
        cwd = str(get_workspace_root())
        try:
            # Stage all changes first
            add_res = subprocess.run(
                ["git", "add", "-A"],
                capture_output=True, text=True, timeout=10, cwd=cwd,
            )
            if add_res.returncode != 0:
                return ToolResult(
                    state=ToolState.FAILURE,
                    output=None,
                    error=f"git add failed: {add_res.stderr}",
                    metadata={"exit_code": add_res.returncode, "cwd": cwd},
                )

            res = subprocess.run(
                ["git", "commit", "-m", msg],
                capture_output=True, text=True, timeout=30, cwd=cwd,
            )
            if res.returncode != 0:
                return ToolResult(
                    state=ToolState.FAILURE,
                    output=None,
                    error=f"git commit failed: {res.stderr or res.stdout}",
                    metadata={"exit_code": res.returncode, "cwd": cwd},
                )
            return ToolResult(
                state=ToolState.SUCCESS,
                output=res.stdout.strip(),
                metadata={"message": msg, "exit_code": 0, "cwd": cwd},
            )
        except FileNotFoundError:
            return ToolResult(
                state=ToolState.UNAVAILABLE,
                output=None,
                error="git is not installed or not found in PATH",
                metadata={"reason": "git_not_found"},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                state=ToolState.TIMEOUT,
                output=None,
                error="git commit timed out",
            )
        except Exception as e:
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=str(e),
                metadata={"cwd": cwd},
            )


class RunTestsTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="testing.run",
            name="Run Tests",
            description=(
                "Run the project test suite. On Windows use PowerShell syntax; "
                "on other platforms use the default POSIX shell."
            ),
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
        target = kwargs.get("target") or "pytest -q"
        cwd = str(get_workspace_root())
        start_time = time.time()
        try:
            if os.name == "nt":
                encoded_target = base64.b64encode(target.encode("utf-16-le")).decode("ascii")
                res = subprocess.run(
                    [
                        "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                        "-EncodedCommand", encoded_target,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=cwd,
                )
            else:
                res = subprocess.run(
                    target, shell=True, capture_output=True, text=True,
                    timeout=120, cwd=cwd,
                )
            duration_ms = int((time.time() - start_time) * 1000)
            output = res.stdout or res.stderr
            return ToolResult(
                state=ToolState.SUCCESS if res.returncode == 0 else ToolState.FAILURE,
                output=output,
                error=res.stderr if res.returncode != 0 else None,
                metadata={
                    "exit_code": res.returncode,
                    "target": target,
                    "cwd": cwd,
                    "duration_ms": duration_ms,
                    "timed_out": False,
                },
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                state=ToolState.TIMEOUT,
                output=None,
                error=f"Test execution timed out after 120s: {target}",
                metadata={"target": target, "cwd": cwd, "duration_ms": duration_ms, "timed_out": True},
            )
        except Exception as e:
            return ToolResult(state=ToolState.FAILURE, output=None, error=str(e), metadata={"target": target, "cwd": cwd})


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
        return [PermissionRequirement(action="execute", resource="command", scope="project")]

    def validate_input(self, **kwargs: Any) -> None:
        if "path" in kwargs and not isinstance(kwargs["path"], str):
            raise ToolValidationError("'path' must be a string if provided")

    def _execute(self, **kwargs: Any) -> ToolResult:
        # §8: Do not claim success without execution.
        # Try to run real diagnostics; report UNAVAILABLE if no linter found.
        path_arg = kwargs.get("path", ".")
        cwd = str(get_workspace_root())
        try:
            path_arg = str(_resolve_path(str(path_arg)))
        except WorkspaceSecurityError as exc:
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=str(exc),
                metadata={"path": str(path_arg), "reason": "workspace_path_rejected"},
            )

        # Try ruff, flake8, pylint in order without invoking a shell.
        for linter_args in [("ruff", "check"), ("flake8",), ("pylint", "--score=n")]:
            full_cmd = [*linter_args, path_arg]
            try:
                res = subprocess.run(
                    full_cmd, capture_output=True, text=True,
                    timeout=30, cwd=cwd,
                )
                output = res.stdout or res.stderr or ""
                issues = len([l for l in output.strip().split("\n") if l.strip()]) if res.returncode != 0 else 0
                return ToolResult(
                    state=ToolState.SUCCESS if res.returncode == 0 else ToolState.FAILURE,
                    output=output or "No issues found.",
                    error=None if res.returncode == 0 else f"Linter found issues (exit code {res.returncode})",
                    metadata={
                        "linter": linter_args[0],
                        "issues": issues,
                        "path": path_arg,
                        "cwd": cwd,
                        "command": " ".join(full_cmd),
                    },
                )
            except FileNotFoundError:
                continue  # Try next linter
            except subprocess.TimeoutExpired:
                return ToolResult(
                    state=ToolState.TIMEOUT,
                    output=None,
                    error=f"Diagnostics timed out: {' '.join(full_cmd)}",
                )
            except Exception:
                continue

        # No linter available
        return ToolResult(
            state=ToolState.UNAVAILABLE,
            output=None,
            error="No linter available (tried ruff, flake8, pylint). Install one to enable diagnostics.",
            metadata={"reason": "no_linter", "path": path_arg},
        )


# ---------------------------------------------------------------------------
# Diff generation helper
# ---------------------------------------------------------------------------

def _generate_diff(before: str, after: str, path: str) -> Dict[str, Any]:
    """Generate a unified diff between before and after content."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)

    diff = list(difflib.unified_diff(
        before_lines, after_lines,
        fromfile=f"a/{path}", tofile=f"b/{path}",
        lineterm="",
    ))

    additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    return {
        "diff": "\n".join(diff) if diff else "",
        "additions": additions,
        "deletions": deletions,
        "path": path,
    }
