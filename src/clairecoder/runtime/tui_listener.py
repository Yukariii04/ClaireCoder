"""Minimal TUI listener for RuntimeEvent.

Correction #12 — Connects the new event protocol to the existing
TUI presentation layer without replacing the existing adapter.

The TUI adapter creates ActivityModel objects from RuntimeEvent,
which are then rendered by the existing transcript/activity pipeline.

This module bridges RuntimeEvent -> core.events.Event -> PresentationAdapter.
The existing PresentationAdapter already handles rendering.
"""

from typing import Optional

from clairecoder.core.events import Event
from clairecoder.tui.adapter import PresentationAdapter
from clairecoder.tui.activity import ActivityModel, ActivityType, ActivityState
from .events import RuntimeEvent, EventType


class RuntimeEventTuiListener:
    """Translates RuntimeEvent into TUI-renderable ActivityModel objects.

    This listener is subscribed to the EventEmitter and produces
    ActivityModel instances that the TUI can consume directly.

    Usage:
        listener = RuntimeEventTuiListener(on_activity_callback)
        emitter.subscribe(listener.on_event)
    """

    def __init__(self, activity_callback=None):
        """Initialize the listener.

        Args:
            activity_callback: Optional callable(ActivityModel) invoked
                when a RuntimeEvent produces a renderable activity.
                If None, activities are silently discarded (useful for testing).
        """
        self._activity_callback = activity_callback

    def on_event(self, event: RuntimeEvent) -> None:
        """Handle a RuntimeEvent, converting it to an ActivityModel if appropriate."""
        activity = self.event_to_activity(event)
        if activity and self._activity_callback:
            self._activity_callback(activity)

    @staticmethod
    def event_to_activity(event: RuntimeEvent) -> Optional[ActivityModel]:
        """Convert a RuntimeEvent to an ActivityModel for TUI rendering.

        Returns None for events that don't need user-visible activity.
        """
        activity = RuntimeEventTuiListener._build_activity(event)
        if activity is not None:
            try:
                from clairecoder.tui.activity_mapper import ActivityMapper
                act_event = ActivityMapper.from_runtime_event(event)
                if act_event is not None:
                    activity.activity_event = act_event
                    if act_event.additions is not None:
                        activity.additions = act_event.additions
                    if act_event.deletions is not None:
                        activity.deletions = act_event.deletions
                    if act_event.change_summary is not None:
                        activity.change_summary = act_event.change_summary
            except Exception:
                pass
        return activity

    @staticmethod
    def _build_activity(event: RuntimeEvent) -> Optional[ActivityModel]:
        etype = event.event_type
        payload = event.payload

        # --- Task lifecycle (Correction #13: richer task display) ---
        if etype == EventType.TASK_STARTED:
            title = payload.get("title", "") or payload.get("description", "") or event.task_id or "task"
            attempt = payload.get("attempt")
            attempt_str = f" (attempt {attempt})" if attempt and attempt > 1 else ""
            return ActivityModel(
                type=ActivityType.MESSAGE,
                state=ActivityState.RUNNING,
                title=f"Task started: {title}{attempt_str}",
                correlation_key=f"rtask_{event.task_id}" if event.task_id else None,
            )

        if etype == EventType.TASK_COMPLETED:
            title = payload.get("title", "") or payload.get("description", "") or event.task_id or "task"
            return ActivityModel(
                type=ActivityType.SUCCESS,
                state=ActivityState.COMPLETED,
                title=f"\u2713 {title}",
                correlation_key=f"rtask_{event.task_id}" if event.task_id else None,
                updates_activity=True,
            )

        if etype == EventType.TASK_FAILED:
            title = payload.get("title", "") or payload.get("description", "") or event.task_id or "task"
            return ActivityModel(
                type=ActivityType.ERROR,
                state=ActivityState.FAILED,
                title=f"Task failed: {title}",
                detail=payload.get("error"),
                correlation_key=f"rtask_{event.task_id}" if event.task_id else None,
                updates_activity=True,
            )

        if etype == EventType.TASK_RETRYING:
            title = payload.get("title", "") or event.task_id or "task"
            attempt = payload.get("attempt", "?")
            return ActivityModel(
                type=ActivityType.WARNING,
                state=ActivityState.RUNNING,
                title=f"Retrying: {title} (attempt {attempt})",
                correlation_key=f"rtask_{event.task_id}" if event.task_id else None,
                updates_activity=True,
            )

        # --- Tool lifecycle ---
        if etype == EventType.TOOL_STARTED:
            tool = payload.get("tool", "tool")
            return ActivityModel(
                type=ActivityType.TOOL,
                state=ActivityState.RUNNING,
                title=f"Running {tool}",
                correlation_key=f"rtool_{event.tool_call_id}" if event.tool_call_id else None,
            )

        if etype == EventType.TOOL_COMPLETED:
            tool = payload.get("tool", "tool")
            return ActivityModel(
                type=ActivityType.TOOL,
                state=ActivityState.COMPLETED,
                title=f"Completed {tool}",
                correlation_key=f"rtool_{event.tool_call_id}" if event.tool_call_id else None,
                updates_activity=True,
            )

        if etype == EventType.TOOL_FAILED:
            tool = payload.get("tool", "tool")
            return ActivityModel(
                type=ActivityType.TOOL,
                state=ActivityState.FAILED,
                title=f"Failed {tool}",
                detail=payload.get("error"),
                correlation_key=f"rtool_{event.tool_call_id}" if event.tool_call_id else None,
                updates_activity=True,
            )

        # --- File operations ---
        if etype == EventType.FILE_READ:
            path = payload.get("path", "")
            name = _basename(path)
            return ActivityModel(
                type=ActivityType.TOOL,
                state=ActivityState.COMPLETED,
                title=f"Read {name}",
                detail=path,
                correlation_key=f"rtool_{event.tool_call_id}" if event.tool_call_id else None,
                updates_activity=True,
            )

        if etype == EventType.FILE_CREATED:
            path = payload.get("path", "")
            name = _basename(path)
            adds = payload.get("additions")
            dels = payload.get("deletions")
            stats = _diff_stats(adds, dels)
            return ActivityModel(
                type=ActivityType.TOOL,
                state=ActivityState.COMPLETED,
                title=f"Created {name}{stats}",
                detail=path,
                correlation_key=f"rtool_{event.tool_call_id}" if event.tool_call_id else None,
                updates_activity=True,
            )

        if etype == EventType.FILE_EDITED:
            path = payload.get("path", "")
            name = _basename(path)
            adds = payload.get("additions")
            dels = payload.get("deletions")
            stats = _diff_stats(adds, dels)
            return ActivityModel(
                type=ActivityType.TOOL,
                state=ActivityState.COMPLETED,
                title=f"Edited {name}{stats}",
                detail=path,
                correlation_key=f"rtool_{event.tool_call_id}" if event.tool_call_id else None,
                updates_activity=True,
            )

        if etype == EventType.FILE_DELETED:
            path = payload.get("path", "")
            name = _basename(path)
            return ActivityModel(
                type=ActivityType.TOOL,
                state=ActivityState.COMPLETED,
                title=f"Deleted {name}",
                detail=path,
                correlation_key=f"rtool_{event.tool_call_id}" if event.tool_call_id else None,
                updates_activity=True,
            )

        # --- Command events ---
        if etype == EventType.COMMAND_STARTED:
            cmd = payload.get("command", "command")
            return ActivityModel(
                type=ActivityType.TOOL,
                state=ActivityState.RUNNING,
                title=f"Running {_truncate(cmd, 60)}",
                correlation_key=f"rcmd_{event.tool_call_id}" if event.tool_call_id else None,
            )

        if etype == EventType.COMMAND_COMPLETED:
            cmd = payload.get("command", "command")
            return ActivityModel(
                type=ActivityType.TOOL,
                state=ActivityState.COMPLETED,
                title=f"Completed {_truncate(cmd, 60)}",
                correlation_key=f"rcmd_{event.tool_call_id}" if event.tool_call_id else None,
                updates_activity=True,
            )

        if etype == EventType.COMMAND_FAILED:
            cmd = payload.get("command", "command")
            exit_code = payload.get("exit_code")
            detail = f"exit code {exit_code}" if exit_code is not None else None
            return ActivityModel(
                type=ActivityType.TOOL,
                state=ActivityState.FAILED,
                title=f"Failed {_truncate(cmd, 60)}",
                detail=detail,
                correlation_key=f"rcmd_{event.tool_call_id}" if event.tool_call_id else None,
                updates_activity=True,
            )

        # --- Verification ---
        if etype == EventType.VERIFICATION_STARTED:
            check = payload.get("check", "verification")
            return ActivityModel(
                type=ActivityType.VERIFICATION,
                state=ActivityState.RUNNING,
                title=f"Verification running: {check}",
                correlation_key=f"rver_{event.task_id}" if event.task_id else None,
            )

        if etype == EventType.VERIFICATION_COMPLETED:
            check = payload.get("check", "verification")
            return ActivityModel(
                type=ActivityType.VERIFICATION,
                state=ActivityState.COMPLETED,
                title=f"Verification passed: {check}",
                correlation_key=f"rver_{event.task_id}" if event.task_id else None,
                updates_activity=True,
            )

        if etype == EventType.VERIFICATION_FAILED:
            check = payload.get("check", "verification")
            return ActivityModel(
                type=ActivityType.VERIFICATION,
                state=ActivityState.FAILED,
                title=f"Verification failed: {check}",
                detail=payload.get("error"),
                correlation_key=f"rver_{event.task_id}" if event.task_id else None,
                updates_activity=True,
            )

        # --- Permission ---
        if etype == EventType.PERMISSION_REQUESTED:
            tool = payload.get("tool", "tool")
            return ActivityModel(
                type=ActivityType.PERMISSION,
                state=ActivityState.APPROVAL_REQUIRED,
                title="Approval required",
                detail=f"ClaireCoder wants to run: {tool}",
                correlation_key=f"rperm_{event.tool_call_id}" if event.tool_call_id else None,
                metadata=payload,
            )

        if etype == EventType.PERMISSION_GRANTED:
            return ActivityModel(
                type=ActivityType.PERMISSION,
                state=ActivityState.COMPLETED,
                title="Permission approved",
                correlation_key=f"rperm_{event.tool_call_id}" if event.tool_call_id else None,
                updates_activity=True,
            )

        if etype == EventType.PERMISSION_DENIED:
            return ActivityModel(
                type=ActivityType.PERMISSION,
                state=ActivityState.FAILED,
                title="Permission denied",
                correlation_key=f"rperm_{event.tool_call_id}" if event.tool_call_id else None,
                updates_activity=True,
            )

        # --- Run lifecycle (mostly internal, minimal rendering) ---
        if etype == EventType.RUN_FAILED:
            return ActivityModel(
                type=ActivityType.ERROR,
                state=ActivityState.FAILED,
                title="Run failed",
                detail=payload.get("error_message") or payload.get("error"),
            )

        if etype == EventType.RUN_CANCELLED:
            return ActivityModel(
                type=ActivityType.WARNING,
                state=ActivityState.COMPLETED,
                title="Run cancelled",
            )

        # --- Plan events ---
        if etype == EventType.PLAN_STARTED:
            return ActivityModel(
                type=ActivityType.THINKING,
                state=ActivityState.RUNNING,
                title="Planning changes",
                correlation_key=f"rplan_{event.run_id}" if event.run_id else None,
            )

        if etype == EventType.PLAN_CREATED:
            return ActivityModel(
                type=ActivityType.MESSAGE,
                state=ActivityState.COMPLETED,
                title="Plan ready",
                correlation_key=f"rplan_{event.run_id}" if event.run_id else None,
                updates_activity=True,
            )

        # --- Agent messages ---
        if etype == EventType.AGENT_MESSAGE:
            msg = payload.get("message", payload.get("legacy_event", ""))
            if msg:
                return ActivityModel(
                    type=ActivityType.MESSAGE,
                    state=ActivityState.COMPLETED,
                    title=str(msg),
                )

        if etype == EventType.AGENT_ERROR:
            return ActivityModel(
                type=ActivityType.ERROR,
                state=ActivityState.FAILED,
                title="Agent error",
                detail=payload.get("error"),
            )

        # --- ChangeSet events ---
        if etype == EventType.CHANGESET_COMPLETED:
            from clairecoder.tui.activity_mapper import ActivityMapper
            act_event = ActivityMapper.from_runtime_event(event)
            if act_event is not None:
                return act_event.to_activity_model()

        # Unhandled events — no activity
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _basename(path: str) -> str:
    """Extract filename from path."""
    if not path:
        return "file"
    # Handle both forward and back slashes
    parts = path.replace("\\", "/").rstrip("/").rsplit("/", 1)
    return parts[-1] if parts else "file"


def _diff_stats(additions: Optional[int], deletions: Optional[int]) -> str:
    """Format +N -M stats string."""
    if additions is None and deletions is None:
        return ""
    parts = []
    if additions is not None and additions > 0:
        parts.append(f"+{additions}")
    if deletions is not None and deletions > 0:
        parts.append(f"-{deletions}")
    if parts:
        return " " + " ".join(parts)
    return ""


def _truncate(s: str, max_len: int) -> str:
    """Truncate a string for display."""
    if len(s) <= max_len:
        return s
    return s[:max_len - 3] + "..."
