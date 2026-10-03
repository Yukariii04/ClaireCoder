"""Activity mapper translating RuntimeEvents, ToolResults, and ChangeSets to ActivityEvents (Correction #20).

Architecture:
    RuntimeEvent / ToolResult / ChangeSet
            |
            v
      ActivityMapper
            |
            v
      ActivityEvent -> ActivityModel
            |
            v
       TUI Renderer
"""

import re
from typing import Any, Dict, List, Optional, Union

from clairecoder.runtime.events import EventType, RuntimeEvent
from clairecoder.core.types import ToolResult
from .activity import (
    ActivityEvent,
    ActivityModel,
    ActivityOperation,
    ActivityStatus,
    ChangeSummaryItem,
    ExecutionChangeSummary,
    truncate_path,
)


def format_concise_error(raw_error: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Convert raw error strings, exceptions, and exit codes into concise user-facing summaries.

    Strips Python stack trace frames, internal object representations, and isolates
    the primary failure reason (e.g. exit codes, assertion lines, not-found messages).
    """
    raw_str = str(raw_error or "").strip()
    if not raw_str and not metadata:
        return "Unknown error"

    parts: List[str] = []
    meta = metadata or {}
    exit_code = meta.get("exit_code")
    if exit_code is not None and exit_code != 0:
        parts.append(f"exit code {exit_code}")

    if raw_str:
        clean_lines: List[str] = []
        in_tb = False

        for line in raw_str.splitlines():
            s = line.strip()
            if not s:
                continue
            lower_s = s.lower()
            if "traceback (most recent call last)" in lower_s:
                in_tb = True
                continue
            if in_tb:
                if s.startswith('File "') or s.startswith("During handling") or s.startswith("Traceback"):
                    continue
                # Line containing the exception class name or colon
                if ":" in s or "Error" in s or "Exception" in s:
                    in_tb = False
                    clean_lines.append(s)
                    continue
            else:
                clean_lines.append(s)

        # Look for salient test failure lines (e.g. '2 tests failed', 'failed: ...')
        salient_lines: List[str] = []
        for l in clean_lines:
            lower = l.lower()
            if any(k in lower for k in ("failed", "failure", "not found", "denied", "timed out", "cannot", "error")):
                # Avoid exact duplicate of exit code line
                if not (parts and parts[0] in l and len(l) <= len(parts[0]) + 4):
                    if l not in salient_lines and l not in parts:
                        salient_lines.append(l)

        if salient_lines:
            parts.extend(salient_lines[:2])
        elif clean_lines:
            # Fall back to the most meaningful line
            parts.append(clean_lines[-1][:100])

    return "\n".join(parts) if parts else (str(raw_error)[:80] if raw_error else "Failed")


def extract_command_summary(output: Any) -> Optional[str]:
    """Extract a concise outcome from command output (e.g. pytest '14 passed')."""
    if not output:
        return None
    text = str(output)

    # Pytest failed summary: e.g. "2 failed, 14 passed"
    match_fail = re.search(r"(\d+\s+failed(?:,\s*\d+\s+passed)?)", text, re.IGNORECASE)
    if match_fail:
        return match_fail.group(1).strip()

    # Pytest passed summary: e.g. "14 passed in 0.12s", "14 passed"
    match = re.search(r"(\d+\s+passed(?:,\s*\d+\s+skipped)?)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Generic test count: e.g. "Ran 14 tests"
    match_ran = re.search(r"(ran\s+\d+\s+tests?)", text, re.IGNORECASE)
    if match_ran:
        return match_ran.group(1).strip()

    return None


class ActivityMapper:
    """Translates RuntimeEvents, ToolResults, and ChangeSets into ActivityEvents."""

    @staticmethod
    def from_runtime_event(event: Any) -> Optional[ActivityEvent]:
        """Convert a RuntimeEvent into an ActivityEvent."""
        if event is None:
            return None

        # Extract event_type and payload safely
        if isinstance(event, RuntimeEvent):
            etype = event.event_type
            payload = event.payload or {}
            tool_call_id = event.tool_call_id
            task_id = event.task_id
            run_id = event.run_id
        elif isinstance(event, dict):
            raw_type = event.get("event_type") or event.get("type", "")
            try:
                etype = EventType(raw_type)
            except ValueError:
                return None
            payload = event.get("payload") or event
            tool_call_id = event.get("tool_call_id")
            task_id = event.get("task_id")
            run_id = event.get("run_id")
        elif hasattr(event, "event_type"):
            etype = event.event_type
            payload = getattr(event, "payload", {}) or {}
            tool_call_id = getattr(event, "tool_call_id", None)
            task_id = getattr(event, "task_id", None)
            run_id = getattr(event, "run_id", None)
        else:
            return None

        # Ignore internal lifecycle events that have no user-facing representation
        if etype in (EventType.RUN_STARTED, EventType.RUN_COMPLETED, EventType.CHANGESET_CREATED):
            return None

        corr_tool = f"rtool_{tool_call_id}" if tool_call_id else f"rtool_{payload.get('tool', 'tool')}_{task_id or run_id or '0'}"

        # ── Tool Started ──
        if etype == EventType.TOOL_STARTED:
            tool = payload.get("tool", "tool")
            args = payload.get("arguments", {}) or {}
            path = args.get("path", "")
            cmd = args.get("command", "")

            if tool in ("read_file", "filesystem.read"):
                return ActivityEvent(
                    status=ActivityStatus.RUNNING,
                    operation=ActivityOperation.READING,
                    target=str(path or tool),
                    file_path=str(path) if path else None,
                    correlation_key=corr_tool,
                    metadata=payload,
                )
            elif tool in ("write_file", "filesystem.write", "filesystem.replace"):
                is_new = args.get("is_new", False) or payload.get("created", False)
                return ActivityEvent(
                    status=ActivityStatus.RUNNING,
                    operation=ActivityOperation.CREATING if is_new else ActivityOperation.EDITING,
                    target=str(path or tool),
                    file_path=str(path) if path else None,
                    correlation_key=corr_tool,
                    metadata=payload,
                )
            elif tool in ("delete_file", "filesystem.delete"):
                return ActivityEvent(
                    status=ActivityStatus.RUNNING,
                    operation=ActivityOperation.DELETING,
                    target=str(path or tool),
                    file_path=str(path) if path else None,
                    correlation_key=corr_tool,
                    metadata=payload,
                )
            elif tool in ("run_command", "shell.execute", "terminal", "terminal.execute"):
                return ActivityEvent(
                    status=ActivityStatus.RUNNING,
                    operation=ActivityOperation.RUNNING,
                    target=str(cmd or tool),
                    correlation_key=corr_tool,
                    metadata=payload,
                )
            elif tool in ("list_files", "list_dir", "filesystem.list"):
                return ActivityEvent(
                    status=ActivityStatus.RUNNING,
                    operation=ActivityOperation.READING,
                    target=str(path or "."),
                    file_path=str(path) if path else None,
                    correlation_key=corr_tool,
                    metadata=payload,
                )
            else:
                return ActivityEvent(
                    status=ActivityStatus.RUNNING,
                    operation=ActivityOperation.RUNNING,
                    target=str(tool),
                    correlation_key=corr_tool,
                    metadata=payload,
                )

        # ── Tool Completed ──
        if etype == EventType.TOOL_COMPLETED:
            tool = payload.get("tool", "tool")
            meta = payload.get("metadata", {}) or {}
            duration = payload.get("duration") or meta.get("duration")

            if tool in ("read_file", "filesystem.read"):
                path = meta.get("path") or payload.get("arguments", {}).get("path", "")
                output = payload.get("output", "")
                line_count = meta.get("lines")
                if line_count is None and isinstance(output, str):
                    line_count = len(output.splitlines()) if output else 0

                details = f"Read {line_count} lines" if line_count is not None and line_count > 0 else None
                return ActivityEvent(
                    status=ActivityStatus.COMPLETED,
                    operation=ActivityOperation.READING,
                    target=str(path or tool),
                    details=details,
                    file_path=str(path) if path else None,
                    duration=duration,
                    correlation_key=corr_tool,
                    metadata=payload,
                )
            elif tool in ("write_file", "filesystem.write", "filesystem.replace"):
                path = meta.get("path") or (payload.get("changed_files", [None])[0] if payload.get("changed_files") else None)
                adds = meta.get("additions") or payload.get("additions")
                dels = meta.get("deletions") or payload.get("deletions")
                is_new = meta.get("created", False) or payload.get("created", False)
                return ActivityEvent(
                    status=ActivityStatus.COMPLETED,
                    operation=ActivityOperation.CREATING if is_new else ActivityOperation.EDITING,
                    target=str(path or tool),
                    file_path=str(path) if path else None,
                    additions=adds,
                    deletions=dels,
                    duration=duration,
                    correlation_key=corr_tool,
                    metadata=payload,
                )
            elif tool in ("delete_file", "filesystem.delete"):
                path = meta.get("path") or (payload.get("changed_files", [None])[0] if payload.get("changed_files") else None)
                return ActivityEvent(
                    status=ActivityStatus.COMPLETED,
                    operation=ActivityOperation.DELETING,
                    target=str(path or tool),
                    file_path=str(path) if path else None,
                    duration=duration,
                    correlation_key=corr_tool,
                    metadata=payload,
                )
            elif tool in ("run_command", "shell.execute", "terminal", "terminal.execute"):
                cmd = meta.get("command") or payload.get("command", "")
                out_summary = extract_command_summary(payload.get("output") or meta.get("stdout"))
                return ActivityEvent(
                    status=ActivityStatus.COMPLETED,
                    operation=ActivityOperation.RUNNING,
                    target=str(cmd or tool),
                    details=out_summary,
                    duration=duration,
                    correlation_key=corr_tool,
                    metadata=payload,
                )
            else:
                return ActivityEvent(
                    status=ActivityStatus.COMPLETED,
                    operation=ActivityOperation.RUNNING,
                    target=str(tool),
                    duration=duration,
                    correlation_key=corr_tool,
                    metadata=payload,
                )

        # ── Tool Failed ──
        if etype == EventType.TOOL_FAILED:
            tool = payload.get("tool", "tool")
            meta = payload.get("metadata", {}) or {}
            cmd = meta.get("command") or payload.get("arguments", {}).get("command")
            target = cmd if cmd else (meta.get("path") or tool)
            err_details = format_concise_error(payload.get("error"), meta)

            op = ActivityOperation.RUNNING
            if tool in ("read_file", "filesystem.read"):
                op = ActivityOperation.READING
            elif tool in ("write_file", "filesystem.write"):
                op = ActivityOperation.EDITING
            elif tool in ("delete_file", "filesystem.delete"):
                op = ActivityOperation.DELETING

            return ActivityEvent(
                status=ActivityStatus.FAILED,
                operation=op,
                target=str(target),
                details=err_details,
                correlation_key=corr_tool,
                metadata=payload,
            )

        # ── Verification ──
        if etype == EventType.VERIFICATION_STARTED:
            check = payload.get("check") or "verification"
            return ActivityEvent(
                status=ActivityStatus.RUNNING,
                operation=ActivityOperation.VERIFYING,
                target=str(check),
                correlation_key=f"rver_{task_id}" if task_id else None,
                metadata=payload,
            )

        if etype in (EventType.VERIFICATION_PASSED, EventType.VERIFICATION_COMPLETED):
            check = payload.get("check") or "verification"
            return ActivityEvent(
                status=ActivityStatus.COMPLETED,
                operation=ActivityOperation.VERIFYING,
                target=str(check),
                details=None,
                correlation_key=f"rver_{task_id}" if task_id else None,
                metadata=payload,
            )

        if etype == EventType.VERIFICATION_FAILED:
            check = payload.get("check") or "verification"
            err = format_concise_error(payload.get("error"))
            return ActivityEvent(
                status=ActivityStatus.FAILED,
                operation=ActivityOperation.VERIFYING,
                target=str(check),
                details=err,
                correlation_key=f"rver_{task_id}" if task_id else None,
                metadata=payload,
            )

        # ── Planning ──
        if etype == EventType.PLAN_STARTED:
            return ActivityEvent(
                status=ActivityStatus.RUNNING,
                operation=ActivityOperation.PLANNING,
                target="Planning changes",
                correlation_key=f"rplan_{run_id}" if run_id else None,
                metadata=payload,
            )

        if etype == EventType.PLAN_CREATED:
            return ActivityEvent(
                status=ActivityStatus.COMPLETED,
                operation=ActivityOperation.PLANNING,
                target="Plan ready",
                correlation_key=f"rplan_{run_id}" if run_id else None,
                metadata=payload,
            )

        # ── Task Lifecycle ──
        if etype == EventType.TASK_STARTED:
            title = payload.get("title") or payload.get("description") or task_id or "task"
            return ActivityEvent(
                status=ActivityStatus.RUNNING,
                operation=ActivityOperation.RUNNING,
                target=str(title),
                correlation_key=f"rtask_{task_id}" if task_id else None,
                metadata=payload,
            )

        if etype == EventType.TASK_COMPLETED:
            title = payload.get("title") or payload.get("description") or task_id or "task"
            return ActivityEvent(
                status=ActivityStatus.COMPLETED,
                operation=ActivityOperation.RUNNING,
                target=str(title),
                correlation_key=f"rtask_{task_id}" if task_id else None,
                metadata=payload,
            )

        if etype == EventType.TASK_FAILED:
            title = payload.get("title") or payload.get("description") or task_id or "task"
            err = format_concise_error(payload.get("error"))
            return ActivityEvent(
                status=ActivityStatus.FAILED,
                operation=ActivityOperation.RUNNING,
                target=str(title),
                details=err,
                correlation_key=f"rtask_{task_id}" if task_id else None,
                metadata=payload,
            )

        # ── ChangeSet Completed (Section 4) ──
        if etype == EventType.CHANGESET_COMPLETED:
            summary = ActivityMapper.from_changeset(payload)
            count = summary.file_count
            f_word = "file" if count == 1 else "files"
            return ActivityEvent(
                status=ActivityStatus.COMPLETED,
                operation=ActivityOperation.EDITING,
                target=f"{count} {f_word} changed",
                change_summary=summary,
                correlation_key=f"rcs_{payload.get('changeset_id')}" if payload.get("changeset_id") else None,
                metadata=payload,
            )

        # ── Direct File Operations (Legacy / compatibility) ──
        if etype == EventType.FILE_READ:
            path = payload.get("path", "file")
            return ActivityEvent(
                status=ActivityStatus.COMPLETED,
                operation=ActivityOperation.READING,
                target=str(path),
                file_path=str(path),
                correlation_key=f"rtool_{tool_call_id}" if tool_call_id else None,
                metadata=payload,
            )

        if etype in (EventType.FILE_CREATED, EventType.FILE_EDITED, EventType.FILE_MODIFIED):
            path = payload.get("path", "file")
            is_new = (etype == EventType.FILE_CREATED)
            return ActivityEvent(
                status=ActivityStatus.COMPLETED,
                operation=ActivityOperation.CREATING if is_new else ActivityOperation.EDITING,
                target=str(path),
                file_path=str(path),
                additions=payload.get("additions"),
                deletions=payload.get("deletions"),
                correlation_key=f"rtool_{tool_call_id}" if tool_call_id else None,
                metadata=payload,
            )

        if etype == EventType.FILE_DELETED:
            path = payload.get("path", "file")
            return ActivityEvent(
                status=ActivityStatus.COMPLETED,
                operation=ActivityOperation.DELETING,
                target=str(path),
                file_path=str(path),
                correlation_key=f"rtool_{tool_call_id}" if tool_call_id else None,
                metadata=payload,
            )

        # ── Direct Command Operations (Legacy / compatibility) ──
        if etype == EventType.COMMAND_STARTED:
            cmd = payload.get("command", "command")
            return ActivityEvent(
                status=ActivityStatus.RUNNING,
                operation=ActivityOperation.RUNNING,
                target=str(cmd),
                correlation_key=f"rcmd_{tool_call_id}" if tool_call_id else None,
                metadata=payload,
            )

        if etype == EventType.COMMAND_COMPLETED:
            cmd = payload.get("command", "command")
            out_summary = extract_command_summary(payload.get("output") or payload.get("stdout"))
            return ActivityEvent(
                status=ActivityStatus.COMPLETED,
                operation=ActivityOperation.RUNNING,
                target=str(cmd),
                details=out_summary,
                correlation_key=f"rcmd_{tool_call_id}" if tool_call_id else None,
                metadata=payload,
            )

        if etype == EventType.COMMAND_FAILED:
            cmd = payload.get("command", "command")
            err_details = format_concise_error(payload.get("error"), payload)
            return ActivityEvent(
                status=ActivityStatus.FAILED,
                operation=ActivityOperation.RUNNING,
                target=str(cmd),
                details=err_details,
                correlation_key=f"rcmd_{tool_call_id}" if tool_call_id else None,
                metadata=payload,
            )

        return None

    @staticmethod
    def from_tool_result(
        result: ToolResult,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        correlation_key: Optional[str] = None,
    ) -> ActivityEvent:
        """Convert a ToolResult directly into an ActivityEvent."""
        args = arguments or {}
        meta = result.metadata or {}
        duration = result.duration or meta.get("duration")
        path = args.get("path") or meta.get("path")
        cmd = args.get("command") or meta.get("command")

        if result.success:
            if tool_name in ("read_file", "filesystem.read"):
                output = result.output or ""
                lines = meta.get("lines")
                if lines is None and isinstance(output, str):
                    lines = len(output.splitlines()) if output else 0
                return ActivityEvent(
                    status=ActivityStatus.COMPLETED,
                    operation=ActivityOperation.READING,
                    target=str(path or "file"),
                    details=f"Read {lines} lines" if lines else None,
                    file_path=str(path) if path else None,
                    duration=duration,
                    correlation_key=correlation_key,
                    metadata=meta,
                )
            elif tool_name in ("write_file", "filesystem.write"):
                return ActivityEvent(
                    status=ActivityStatus.COMPLETED,
                    operation=ActivityOperation.EDITING,
                    target=str(path or "file"),
                    file_path=str(path) if path else None,
                    additions=meta.get("additions"),
                    deletions=meta.get("deletions"),
                    duration=duration,
                    correlation_key=correlation_key,
                    metadata=meta,
                )
            elif tool_name in ("delete_file", "filesystem.delete"):
                return ActivityEvent(
                    status=ActivityStatus.COMPLETED,
                    operation=ActivityOperation.DELETING,
                    target=str(path or "file"),
                    file_path=str(path) if path else None,
                    duration=duration,
                    correlation_key=correlation_key,
                    metadata=meta,
                )
            elif tool_name in ("run_command", "shell.execute", "terminal"):
                out_summary = extract_command_summary(result.output or meta.get("stdout"))
                return ActivityEvent(
                    status=ActivityStatus.COMPLETED,
                    operation=ActivityOperation.RUNNING,
                    target=str(cmd or "command"),
                    details=out_summary,
                    duration=duration,
                    correlation_key=correlation_key,
                    metadata=meta,
                )
            else:
                return ActivityEvent(
                    status=ActivityStatus.COMPLETED,
                    operation=ActivityOperation.RUNNING,
                    target=str(tool_name),
                    duration=duration,
                    correlation_key=correlation_key,
                    metadata=meta,
                )
        else:
            err = format_concise_error(result.error, meta)
            tgt = cmd if cmd else (path or tool_name)
            op = ActivityOperation.RUNNING
            if tool_name in ("read_file", "filesystem.read"):
                op = ActivityOperation.READING
            elif tool_name in ("write_file", "filesystem.write"):
                op = ActivityOperation.EDITING
            elif tool_name in ("delete_file", "filesystem.delete"):
                op = ActivityOperation.DELETING

            return ActivityEvent(
                status=ActivityStatus.FAILED,
                operation=op,
                target=str(tgt),
                details=err,
                duration=duration,
                correlation_key=correlation_key,
                metadata=meta,
            )

    @staticmethod
    def from_changeset(changeset: Any) -> ExecutionChangeSummary:
        """Convert a ChangeSet object or dict into an ExecutionChangeSummary."""
        if changeset is None:
            return ExecutionChangeSummary()

        # If it's a ChangeSet dataclass
        if hasattr(changeset, "files"):
            items: List[ChangeSummaryItem] = []
            for f in changeset.files:
                p = getattr(f, "path", "")
                adds = getattr(f, "additions", 0)
                dels = getattr(f, "deletions", 0)
                op = getattr(f, "operation", "modified")
                status = op.value if hasattr(op, "value") else str(op)
                items.append(ChangeSummaryItem(path=p, additions=adds, deletions=dels, status=status))

            return ExecutionChangeSummary(
                file_count=getattr(changeset, "file_count", len(items)),
                total_additions=getattr(changeset, "total_additions", sum(i.additions for i in items)),
                total_deletions=getattr(changeset, "total_deletions", sum(i.deletions for i in items)),
                files=items,
            )

        # If it's a dict payload
        if isinstance(changeset, dict):
            raw_files = changeset.get("files") or []
            items = []
            for rf in raw_files:
                if isinstance(rf, dict):
                    items.append(ChangeSummaryItem(
                        path=rf.get("path", ""),
                        additions=rf.get("additions", 0),
                        deletions=rf.get("deletions", 0),
                        status=rf.get("operation", "modified"),
                    ))
                elif isinstance(rf, str):
                    items.append(ChangeSummaryItem(path=rf, additions=0, deletions=0))

            # If no files list, check paths list
            if not items and changeset.get("paths"):
                for p in changeset["paths"]:
                    items.append(ChangeSummaryItem(path=str(p), additions=0, deletions=0))

            f_count = changeset.get("file_count", len(items))
            tot_adds = changeset.get("total_additions", sum(i.additions for i in items))
            tot_dels = changeset.get("total_deletions", sum(i.deletions for i in items))
            return ExecutionChangeSummary(
                file_count=f_count,
                total_additions=tot_adds,
                total_deletions=tot_dels,
                files=items,
            )

        return ExecutionChangeSummary()
