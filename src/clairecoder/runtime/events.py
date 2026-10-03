"""Runtime Event definitions for ClaireCoder.

Correction #12 — Central structured event representation.

Design decisions:
- EventType is a string enum using dotted naming (e.g. "run.started") for
  clean serialization and human readability in JSONL/API output.
- RuntimeEvent is a frozen-friendly dataclass carrying correlation IDs
  (run_id, objective_id, task_id, tool_call_id) and a typed payload dict.
- event_id is auto-generated UUID if not supplied.
- timestamp is UTC-aware datetime.
- Serialization uses to_dict() / from_dict() — no heavy dependencies.
"""

import uuid
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """Structured event types for the runtime event protocol."""

    # --- Run lifecycle ---
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"

    # --- Planning ---
    PLAN_STARTED = "plan.started"
    PLAN_CREATED = "plan.created"
    PLAN_UPDATED = "plan.updated"

    # --- Task lifecycle ---
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_RETRYING = "task.retrying"

    # --- Tool lifecycle ---
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"

    # --- Changeset lifecycle (Correction #16) ---
    CHANGESET_CREATED = "changeset.created"
    CHANGESET_COMPLETED = "changeset.completed"

    # --- File operations ---
    FILE_READ = "file.read"
    FILE_CREATED = "file.created"
    FILE_EDITED = "file.edited"
    FILE_MODIFIED = "file.modified"
    FILE_DELETED = "file.deleted"

    # --- Command execution ---
    COMMAND_STARTED = "command.started"
    COMMAND_OUTPUT = "command.output"
    COMMAND_COMPLETED = "command.completed"
    COMMAND_FAILED = "command.failed"

    # --- Verification (Correction #17) ---
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_COMPLETED = "verification.completed"
    VERIFICATION_FAILED = "verification.failed"

    # --- Recovery & Retry Lifecycle (Correction #17) ---
    RECOVERY_STARTED = "recovery.started"
    RETRY_STARTED = "retry.started"
    REPLAN_STARTED = "replan.started"
    RECOVERY_COMPLETED = "recovery.completed"
    RECOVERY_FAILED = "recovery.failed"

    # --- Role Lifecycle (Correction #18) ---
    ROLE_STARTED = "role.started"
    ROLE_COMPLETED = "role.completed"
    ROLE_FAILED = "role.failed"

    # --- Session lifecycle (Correction #21) ---
    SESSION_CREATED = "session.created"
    SESSION_RESUMED = "session.resumed"
    SESSION_CHECKPOINTED = "session.checkpointed"
    SESSION_COMPLETED = "session.completed"
    SESSION_FAILED = "session.failed"
    SESSION_INTERRUPTED = "session.interrupted"

    # --- Provider lifecycle (Correction #22) ---
    PROVIDER_REQUEST_STARTED = "provider.request.started"
    PROVIDER_REQUEST_RETRYING = "provider.request.retrying"
    PROVIDER_REQUEST_COMPLETED = "provider.request.completed"
    PROVIDER_REQUEST_FAILED = "provider.request.failed"

    # --- Agent messages ---
    AGENT_MESSAGE = "agent.message"
    AGENT_ERROR = "agent.error"

    # --- Permission ---
    PERMISSION_REQUESTED = "permission.requested"
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_DENIED = "permission.denied"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_event_id() -> str:
    return str(uuid.uuid4())


@dataclass
class RuntimeEvent:
    """Central structured runtime event.

    Carries correlation IDs for event tracing across:
      session → run → objective → task → tool_call → changeset

    The payload dict holds event-specific structured data.
    """

    event_type: EventType
    event_id: str = field(default_factory=_new_event_id)
    timestamp: datetime = field(default_factory=_utc_now)

    # --- Correlation IDs ---
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    objective_id: Optional[str] = None
    task_id: Optional[str] = None
    tool_call_id: Optional[str] = None
    changeset_id: Optional[str] = None

    # --- Structured payload ---
    payload: Dict[str, Any] = field(default_factory=dict)

    # --- Attempt tracking ---
    attempt: Optional[int] = None

    # ---- Serialization ----

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict suitable for JSON output."""
        d: Dict[str, Any] = {
            "event_type": self.event_type.value,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.session_id is not None:
            d["session_id"] = self.session_id
        if self.run_id is not None:
            d["run_id"] = self.run_id
        if self.objective_id is not None:
            d["objective_id"] = self.objective_id
        if self.task_id is not None:
            d["task_id"] = self.task_id
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.changeset_id is not None:
            d["changeset_id"] = self.changeset_id
        if self.attempt is not None:
            d["attempt"] = self.attempt
        if self.payload:
            d["payload"] = self.payload
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeEvent":
        """Deserialize from a dict produced by to_dict()."""
        return cls(
            event_type=EventType(data["event_type"]),
            event_id=data.get("event_id", _new_event_id()),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else _utc_now(),
            session_id=data.get("session_id"),
            run_id=data.get("run_id"),
            objective_id=data.get("objective_id"),
            task_id=data.get("task_id"),
            tool_call_id=data.get("tool_call_id"),
            changeset_id=data.get("changeset_id"),
            attempt=data.get("attempt"),
            payload=data.get("payload", {}),
        )
