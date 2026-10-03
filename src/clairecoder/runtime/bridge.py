"""Bridge adapter: EngineEvent -> RuntimeEvent.

Correction #12 — Backward compatibility layer.

Translates legacy EngineEvent emissions from the existing EngineeringEngine
into structured RuntimeEvent emissions on the new EventEmitter.

This allows the new TUI and future consumers to subscribe to a single
RuntimeEvent stream while the existing engine emission code remains untouched.

Architecture:
    EngineeringEngine._emit(EngineEvent, data)
            |
            v
      EngineBridge (subscribed as engine callback)
            |
            v
      EventEmitter.emit(RuntimeEvent)
            |
      +-----+--------+
      v     v        v
     TUI  Logger  Recorder
"""

from typing import Any, Dict, Optional

from clairecoder.engine.types import EngineEvent
from clairecoder.core.types import ToolState
from .events import RuntimeEvent, EventType
from .emitter import EventEmitter


# Mapping from EngineEvent to EventType for direct 1:1 translations.
_ENGINE_TO_RUNTIME: Dict[str, EventType] = {
    EngineEvent.RUN_STARTED.value: EventType.RUN_STARTED,
    EngineEvent.RUN_COMPLETED.value: EventType.RUN_COMPLETED,
    EngineEvent.RUN_FAILED.value: EventType.RUN_FAILED,
    EngineEvent.RUN_CANCELLED.value: EventType.RUN_CANCELLED,

    EngineEvent.PLANNING_STARTED.value: EventType.PLAN_STARTED,
    EngineEvent.PLANNING_COMPLETED.value: EventType.PLAN_CREATED,

    EngineEvent.TASK_STARTED.value: EventType.TASK_STARTED,
    EngineEvent.TASK_COMPLETED.value: EventType.TASK_COMPLETED,

    EngineEvent.VERIFICATION_STARTED.value: EventType.VERIFICATION_STARTED,
    EngineEvent.VERIFICATION_COMPLETED.value: EventType.VERIFICATION_COMPLETED,

    EngineEvent.PERMISSION_REQUESTED.value: EventType.PERMISSION_REQUESTED,
}


class EngineBridge:
    """Translates legacy EngineEvent callbacks to RuntimeEvent emissions.

    Usage:
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        engine = EngineeringEngine(..., event_callback=bridge.on_engine_event)
        # or
        engine.subscribe(bridge.on_engine_event)
    """

    def __init__(self, emitter: EventEmitter) -> None:
        self._emitter = emitter

    def on_engine_event(self, event: EngineEvent, data: Dict[str, Any]) -> None:
        """Callback compatible with EngineeringEngine._emit signature."""
        event_value = event.value if isinstance(event, EngineEvent) else str(event)

        # Extract common correlation IDs from data
        run_id = data.get("run_id")
        objective_id = data.get("objective_id")
        task_id = data.get("task_id")
        tool_call_id = data.get("tool_call_id") or data.get("request_id")

        # --- Handle tool events with richer logic ---
        if event_value == EngineEvent.TOOL_REQUESTED.value:
            self._emitter.emit(RuntimeEvent(
                event_type=EventType.TOOL_STARTED,
                run_id=run_id,
                task_id=task_id,
                tool_call_id=tool_call_id,
                payload={"tool": data.get("tool_name") or data.get("tool_id", "unknown")},
            ))
            return

        if event_value == EngineEvent.TOOL_COMPLETED.value:
            tool_state = data.get("state")
            tool_name = data.get("tool_name") or data.get("tool_id", "unknown")
            metadata = data.get("metadata", {})

            # Emit file events if this is a file tool
            file_event = _extract_file_event(tool_name, tool_state, metadata, run_id, task_id, tool_call_id)
            if file_event:
                self._emitter.emit(file_event)

            # Emit command events if this is a command tool
            cmd_event = _extract_command_event(tool_name, tool_state, metadata, run_id, task_id, tool_call_id)
            if cmd_event:
                self._emitter.emit(cmd_event)

            # Emit TOOL_COMPLETED or TOOL_FAILED
            if _is_failure_state(tool_state):
                self._emitter.emit(RuntimeEvent(
                    event_type=EventType.TOOL_FAILED,
                    run_id=run_id,
                    task_id=task_id,
                    tool_call_id=tool_call_id,
                    payload={
                        "tool": tool_name,
                        "error": data.get("result") or str(tool_state),
                    },
                ))
            else:
                self._emitter.emit(RuntimeEvent(
                    event_type=EventType.TOOL_COMPLETED,
                    run_id=run_id,
                    task_id=task_id,
                    tool_call_id=tool_call_id,
                    payload={"tool": tool_name},
                ))
            return

        if event_value == EngineEvent.TOOL_FAILED.value:
            self._emitter.emit(RuntimeEvent(
                event_type=EventType.TOOL_FAILED,
                run_id=run_id,
                task_id=task_id,
                tool_call_id=tool_call_id,
                payload={
                    "tool": data.get("tool_name") or data.get("tool_id", "unknown"),
                    "error": data.get("error") or data.get("result", ""),
                },
            ))
            return

        # --- Handle permission resolution ---
        if event_value == EngineEvent.PERMISSION_RESOLVED.value:
            decision = data.get("decision", "")
            if decision in ("granted", "approved", "always", "session"):
                etype = EventType.PERMISSION_GRANTED
            elif decision in ("denied", "no"):
                etype = EventType.PERMISSION_DENIED
            else:
                etype = EventType.PERMISSION_DENIED
            self._emitter.emit(RuntimeEvent(
                event_type=etype,
                run_id=run_id,
                task_id=task_id,
                tool_call_id=tool_call_id,
                payload={
                    "decision": decision,
                    "tool": data.get("tool_name") or data.get("tool_id"),
                    "scope": data.get("scope"),
                },
            ))
            return

        # --- Handle verification completed with pass/fail ---
        if event_value == EngineEvent.VERIFICATION_COMPLETED.value:
            passed = data.get("passed", True)
            if passed:
                etype = EventType.VERIFICATION_COMPLETED
            else:
                etype = EventType.VERIFICATION_FAILED
            self._emitter.emit(RuntimeEvent(
                event_type=etype,
                run_id=run_id,
                task_id=task_id,
                payload=_strip_internal(data),
            ))
            return

        if event_value == EngineEvent.VALIDATION_STARTED.value:
            self._emitter.emit(RuntimeEvent(
                event_type=EventType.VERIFICATION_STARTED,
                run_id=run_id,
                task_id=task_id,
                payload=_strip_internal(data),
            ))
            return

        if event_value == EngineEvent.VALIDATION_COMPLETED.value:
            passed = data.get("passed", True)
            etype = EventType.VERIFICATION_COMPLETED if passed else EventType.VERIFICATION_FAILED
            self._emitter.emit(RuntimeEvent(
                event_type=etype,
                run_id=run_id,
                task_id=task_id,
                payload=_strip_internal(data),
            ))
            return

        # --- Handle execution failure as run/task failure ---
        if event_value == EngineEvent.EXECUTION_FAILED.value:
            self._emitter.emit(RuntimeEvent(
                event_type=EventType.RUN_FAILED,
                run_id=run_id,
                objective_id=objective_id,
                task_id=task_id,
                payload=_strip_internal(data),
            ))
            return

        if event_value == EngineEvent.EXECUTION_CANCELLED.value:
            self._emitter.emit(RuntimeEvent(
                event_type=EventType.RUN_CANCELLED,
                run_id=run_id,
                objective_id=objective_id,
                payload=_strip_internal(data),
            ))
            return

        if event_value == EngineEvent.REPLANNING_STARTED.value:
            self._emitter.emit(RuntimeEvent(
                event_type=EventType.PLAN_UPDATED,
                run_id=run_id,
                task_id=task_id,
                payload=_strip_internal(data),
            ))
            return

        # --- Direct 1:1 mapping ---
        mapped = _ENGINE_TO_RUNTIME.get(event_value)
        if mapped:
            self._emitter.emit(RuntimeEvent(
                event_type=mapped,
                run_id=run_id,
                objective_id=objective_id,
                task_id=task_id,
                tool_call_id=tool_call_id,
                payload=_strip_internal(data),
            ))
            return

        # --- Unmapped events: emit as AGENT_MESSAGE for debugging ---
        # Skip purely internal TUI state events
        skip = {"streaming_chunk", "response_complete", "model_switched", "mode_changed", "run_state_changed"}
        if event_value in skip:
            return

        self._emitter.emit(RuntimeEvent(
            event_type=EventType.AGENT_MESSAGE,
            run_id=run_id,
            payload={"legacy_event": event_value, **_strip_internal(data)},
        ))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_failure_state(state: Any) -> bool:
    """Check whether a tool state represents failure."""
    if isinstance(state, ToolState):
        return state in (ToolState.FAILURE, ToolState.DENIED, ToolState.TIMEOUT, ToolState.UNAVAILABLE, ToolState.CANCELLED)
    s = str(state).lower() if state else ""
    return s in ("failure", "denied", "timeout", "unavailable", "cancelled")


def _strip_internal(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys used for routing that shouldn't leak into payload."""
    skip = {"run_id", "objective_id", "task_id", "tool_call_id", "request_id"}
    return {k: v for k, v in data.items() if k not in skip}


_FILE_TOOLS = {"filesystem.read", "filesystem.write", "filesystem.replace", "filesystem.delete", "filesystem.list"}
_FILE_TOOL_ALIASES = {"read_file", "write_to_file", "replace_file_content", "delete_file", "list_dir"}


def _extract_file_event(
    tool_name: str,
    tool_state: Any,
    metadata: Dict[str, Any],
    run_id: Optional[str],
    task_id: Optional[str],
    tool_call_id: Optional[str],
) -> Optional[RuntimeEvent]:
    """Produce a FILE_* RuntimeEvent if this tool is a file tool."""
    is_file_tool = tool_name in _FILE_TOOLS or tool_name in _FILE_TOOL_ALIASES

    if not is_file_tool:
        return None

    path = metadata.get("path", "")
    payload: Dict[str, Any] = {"path": path}

    if _is_failure_state(tool_state):
        return None  # TOOL_FAILED covers it

    # Determine specific file event
    if tool_name in ("filesystem.read", "read_file"):
        etype = EventType.FILE_READ
        if "size" in metadata:
            payload["size"] = metadata["size"]
    elif tool_name in ("filesystem.write", "write_to_file"):
        if metadata.get("bytes_written") is not None:
            # New file creation (or overwrite)
            etype = EventType.FILE_CREATED
        else:
            etype = EventType.FILE_EDITED
        if "additions" in metadata:
            payload["additions"] = metadata["additions"]
        if "deletions" in metadata:
            payload["deletions"] = metadata["deletions"]
        if "diff" in metadata:
            payload["diff"] = metadata["diff"]
    elif tool_name in ("filesystem.replace", "replace_file_content"):
        etype = EventType.FILE_EDITED
        if "additions" in metadata:
            payload["additions"] = metadata["additions"]
        if "deletions" in metadata:
            payload["deletions"] = metadata["deletions"]
        if "diff" in metadata:
            payload["diff"] = metadata["diff"]
    elif tool_name in ("filesystem.delete", "delete_file"):
        etype = EventType.FILE_DELETED
    else:
        return None  # list_dir doesn't need a file event

    return RuntimeEvent(
        event_type=etype,
        run_id=run_id,
        task_id=task_id,
        tool_call_id=tool_call_id,
        payload=payload,
    )


_COMMAND_TOOLS = {"shell.execute", "run_command", "testing.run"}


def _extract_command_event(
    tool_name: str,
    tool_state: Any,
    metadata: Dict[str, Any],
    run_id: Optional[str],
    task_id: Optional[str],
    tool_call_id: Optional[str],
) -> Optional[RuntimeEvent]:
    """Produce COMMAND_* RuntimeEvent if this tool is a command/terminal tool."""
    if tool_name not in _COMMAND_TOOLS:
        return None

    payload: Dict[str, Any] = {}
    if "command" in metadata:
        payload["command"] = metadata["command"]
    if "cwd" in metadata:
        payload["cwd"] = metadata["cwd"]
    if "exit_code" in metadata:
        payload["exit_code"] = metadata["exit_code"]
    if "duration_ms" in metadata:
        payload["duration_ms"] = metadata["duration_ms"]

    if _is_failure_state(tool_state):
        return RuntimeEvent(
            event_type=EventType.COMMAND_FAILED,
            run_id=run_id,
            task_id=task_id,
            tool_call_id=tool_call_id,
            payload=payload,
        )
    else:
        return RuntimeEvent(
            event_type=EventType.COMMAND_COMPLETED,
            run_id=run_id,
            task_id=task_id,
            tool_call_id=tool_call_id,
            payload=payload,
        )
