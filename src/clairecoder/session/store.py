"""Local filesystem SessionStore implementation for ClaireCoder (Correction #21).

Provides atomic filesystem persistence into .clairecoder/sessions/<session-id>.json
with corruption protection, schema version checking, and full CRUD operations.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import uuid

from .errors import (
    SessionCorruptedError,
    SessionError,
    SessionNotFoundError,
    SessionStorageError,
    UnsupportedSchemaVersionError,
)
from .types import Session, SessionMetadata, SessionRunState, SessionStatus


class SessionStore:
    """Thread-safe and process-safe filesystem Session Store."""

    def __init__(self, sessions_dir: Optional[Union[str, Path]] = None, workspace_root: Optional[Union[str, Path]] = None) -> None:
        if sessions_dir is not None:
            self._dir = Path(sessions_dir)
        elif workspace_root is not None:
            self._dir = Path(workspace_root) / ".clairecoder" / "sessions"
        else:
            self._dir = Path.cwd() / ".clairecoder" / "sessions"

    @property
    def sessions_dir(self) -> Path:
        return self._dir

    def _ensure_dir(self) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise SessionStorageError(f"Failed to create sessions directory '{self._dir}': {e}", original_error=e)

    def _session_path(self, session_id: str) -> Path:
        # Sanitize session_id to avoid path traversal
        safe_id = Path(session_id).name
        return self._dir / f"{safe_id}.json"

    def create(
        self,
        session_id: Optional[str] = None,
        workspace_root: Optional[str] = None,
        original_objective: str = "",
        active_model: Optional[str] = None,
        provider_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """Create a new session, persist it atomically, and return the instance."""
        sid = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        ws = workspace_root or str(self._dir.parent.parent)

        meta = SessionMetadata(
            active_model=active_model,
            provider_id=provider_id,
            custom=metadata or {},
        )

        session = Session(
            session_id=sid,
            workspace_root=ws,
            original_objective=original_objective,
            status=SessionStatus.ACTIVE,
            metadata=meta,
        )

        self.save(session)
        return session

    def save(self, session: Session) -> None:
        """Atomically persist a session to disk using temp file + flush + fsync + replace."""
        self._ensure_dir()
        target_path = self._session_path(session.session_id)
        temp_path = self._dir / f".tmp_{session.session_id}_{uuid.uuid4().hex}.json"

        try:
            data = session.to_dict()
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except (AttributeError, OSError):
                    pass

            # Atomic replace target file with temp file
            os.replace(temp_path, target_path)
        except Exception as e:
            # Clean up temp file if present
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            raise SessionStorageError(
                f"Failed to persist session '{session.session_id}' to '{target_path}': {e}",
                original_error=e,
            )

    def get(self, session_id: str) -> Session:
        """Load and deserialize a session from disk."""
        target_path = self._session_path(session_id)
        if not target_path.is_file():
            raise SessionNotFoundError(session_id)

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as jde:
            raise SessionCorruptedError(session_id, f"Malformed JSON: {jde}")
        except Exception as e:
            raise SessionStorageError(f"Failed to read session file '{target_path}': {e}", original_error=e)

        return Session.from_dict(data)

    def exists(self, session_id: str) -> bool:
        """Check if a session file exists on disk."""
        return self._session_path(session_id).is_file()

    def delete(self, session_id: str) -> bool:
        """Delete a session file from disk if it exists. Returns True if deleted."""
        target_path = self._session_path(session_id)
        if target_path.is_file():
            try:
                target_path.unlink()
                return True
            except Exception as e:
                raise SessionStorageError(f"Failed to delete session '{session_id}': {e}", original_error=e)
        return False

    def list(self) -> List[Session]:
        """List all valid sessions ordered by updated_at descending."""
        if not self._dir.is_dir():
            return []

        sessions: List[Session] = []
        for file in self._dir.glob("*.json"):
            if file.name.startswith("."):
                continue
            session_id = file.stem
            try:
                sess = self.get(session_id)
                sessions.append(sess)
            except (SessionCorruptedError, UnsupportedSchemaVersionError, SessionStorageError):
                # Ignore corrupt sessions in list enumeration so valid sessions can still be displayed
                continue

        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def list_ids(self) -> List[str]:
        """List session IDs found in the storage directory."""
        if not self._dir.is_dir():
            return []
        return [f.stem for f in self._dir.glob("*.json") if not f.name.startswith(".")]
