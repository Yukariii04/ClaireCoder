"""Serializable Session data models for ClaireCoder (Correction #21).

Enforces typed, versioned, structured session state decoupled from presentation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .errors import SessionCorruptedError, UnsupportedSchemaVersionError

CURRENT_SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStatus(str, Enum):
    """Lifecycle statuses for a Session."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"

    @classmethod
    def _missing_(cls, value: Any) -> "SessionStatus":
        if isinstance(value, str):
            val = value.lower().strip()
            for member in cls:
                if member.value == val:
                    return member
        return cls.ACTIVE


@dataclass
class SessionMetadata:
    """Persisted configuration and environment metadata for a session."""
    schema_version: int = CURRENT_SCHEMA_VERSION
    active_model: Optional[str] = None
    provider_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "active_model": self.active_model,
            "provider_id": self.provider_id,
            "tags": list(self.tags),
            "custom": dict(self.custom),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SessionMetadata":
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            schema_version=data.get("schema_version", CURRENT_SCHEMA_VERSION),
            active_model=data.get("active_model"),
            provider_id=data.get("provider_id"),
            tags=list(data.get("tags", [])),
            custom=dict(data.get("custom", {})),
        )


@dataclass
class SessionRunState:
    """Persisted execution progress for run, cycle, and active task tracking."""
    schema_version: int = CURRENT_SCHEMA_VERSION
    current_run_id: Optional[str] = None
    current_task_id: Optional[str] = None
    turn_count: int = 0
    cycles: int = 0
    replan_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "current_run_id": self.current_run_id,
            "current_task_id": self.current_task_id,
            "turn_count": self.turn_count,
            "cycles": self.cycles,
            "replan_count": self.replan_count,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SessionRunState":
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            schema_version=data.get("schema_version", CURRENT_SCHEMA_VERSION),
            current_run_id=data.get("current_run_id"),
            current_task_id=data.get("current_task_id"),
            turn_count=data.get("turn_count", 0),
            cycles=data.get("cycles", 0),
            replan_count=data.get("replan_count", 0),
        )


@dataclass
class ChangeSetReference:
    """Summary reference to a ChangeSet produced during session execution (Correction #16)."""
    changeset_id: str
    task_id: str
    status: str
    files_count: int = 0
    additions: int = 0
    deletions: int = 0
    created_at: float = 0.0
    schema_version: int = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "changeset_id": self.changeset_id,
            "task_id": self.task_id,
            "status": self.status,
            "files_count": self.files_count,
            "additions": self.additions,
            "deletions": self.deletions,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChangeSetReference":
        return cls(
            changeset_id=data["changeset_id"],
            task_id=data.get("task_id", ""),
            status=data.get("status", "completed"),
            files_count=data.get("files_count", 0),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            created_at=data.get("created_at", 0.0),
            schema_version=data.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class Session:
    """Durable state representation for an engineering session.

    Contains:
    - session_id
    - created_at / updated_at
    - workspace/project root
    - original objective
    - current run/turn/task state
    - task graph state
    - relevant execution metadata
    - ChangeSet references/summaries
    - verification/recovery state
    - session status: active / completed / failed / interrupted
    """
    session_id: str
    workspace_root: str
    original_objective: str
    schema_version: int = CURRENT_SCHEMA_VERSION
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    # Run and task progress
    run_state: SessionRunState = field(default_factory=SessionRunState)

    # Task graph representation (serialized via TaskGraph.to_dict())
    task_graph_state: Optional[Dict[str, Any]] = None

    # Relevant execution metadata
    execution_metadata: Dict[str, Any] = field(default_factory=dict)

    # ChangeSet references (Correction #16)
    changesets: List[ChangeSetReference] = field(default_factory=list)

    # Verification and recovery states (Correction #17)
    verification_state: Dict[str, Any] = field(default_factory=dict)
    recovery_state: Dict[str, Any] = field(default_factory=dict)

    # Metadata & tags
    metadata: SessionMetadata = field(default_factory=SessionMetadata)

    def __post_init__(self) -> None:
        if isinstance(self.status, str) and not isinstance(self.status, SessionStatus):
            self.status = SessionStatus(self.status)

    @property
    def current_run_id(self) -> Optional[str]:
        return self.run_state.current_run_id

    @current_run_id.setter
    def current_run_id(self, val: Optional[str]) -> None:
        self.run_state.current_run_id = val

    @property
    def current_task_id(self) -> Optional[str]:
        return self.run_state.current_task_id

    @current_task_id.setter
    def current_task_id(self, val: Optional[str]) -> None:
        self.run_state.current_task_id = val

    @property
    def turn_count(self) -> int:
        return self.run_state.turn_count

    @turn_count.setter
    def turn_count(self, val: int) -> None:
        self.run_state.turn_count = val

    @property
    def changeset_ids(self) -> List[str]:
        return [cs.changeset_id for cs in self.changesets]

    def touch(self) -> None:
        """Update the updated_at timestamp to now."""
        self.updated_at = _utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize Session to a JSON-compatible dictionary with explicit schemas."""
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "workspace_root": self.workspace_root,
            "original_objective": self.original_objective,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "run_state": self.run_state.to_dict(),
            "task_graph_state": self.task_graph_state,
            "execution_metadata": self.execution_metadata,
            "changesets": [cs.to_dict() for cs in self.changesets],
            "verification_state": self.verification_state,
            "recovery_state": self.recovery_state,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Deserialize a Session from dictionary with strict schema version and corruption checking."""
        if not isinstance(data, dict):
            raise SessionCorruptedError(session_id="", reason="Payload is not a valid JSON dictionary")

        session_id = data.get("session_id") or data.get("id")
        if not session_id or not isinstance(session_id, str):
            raise SessionCorruptedError(session_id=str(session_id or ""), reason="Missing or invalid session_id")

        schema_version = data.get("schema_version", 1)
        if not isinstance(schema_version, int):
            raise SessionCorruptedError(session_id=session_id, reason="schema_version must be an integer")

        if schema_version > CURRENT_SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(
                session_id=session_id,
                found_version=schema_version,
                supported_version=CURRENT_SCHEMA_VERSION,
            )

        workspace_root = data.get("workspace_root")
        if workspace_root is None or not isinstance(workspace_root, str):
            # Fallback for sessions where workspace_root wasn't explicitly persisted
            workspace_root = ""

        original_objective = data.get("original_objective")
        if original_objective is None:
            if isinstance(data.get("objective"), dict):
                original_objective = data["objective"].get("request", "")
            elif isinstance(data.get("objective"), str):
                original_objective = data["objective"]
            else:
                raise SessionCorruptedError(session_id=session_id, reason="Missing original_objective")

        status_str = data.get("status", SessionStatus.ACTIVE.value)
        try:
            status = SessionStatus(status_str)
        except Exception as e:
            raise SessionCorruptedError(session_id=session_id, reason=f"Invalid session status: {e}")

        created_at = data.get("created_at") or _utc_now_iso()
        updated_at = data.get("updated_at") or created_at

        run_state = SessionRunState.from_dict(data.get("run_state"))
        metadata = SessionMetadata.from_dict(data.get("metadata"))

        changesets = []
        for cs_data in data.get("changesets", []):
            if isinstance(cs_data, dict) and "changeset_id" in cs_data:
                changesets.append(ChangeSetReference.from_dict(cs_data))

        return cls(
            session_id=session_id,
            workspace_root=workspace_root,
            original_objective=str(original_objective),
            schema_version=schema_version,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            run_state=run_state,
            task_graph_state=data.get("task_graph_state"),
            execution_metadata=data.get("execution_metadata", {}),
            changesets=changesets,
            verification_state=data.get("verification_state", {}),
            recovery_state=data.get("recovery_state", {}),
            metadata=metadata,
        )
