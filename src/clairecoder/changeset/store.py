"""In-memory and thread-safe ChangeSet store.

Correction #16: Manages ChangeSets independently from the presentation layer.
Provides creation, recording, and retrieval by changeset_id and task_id.
"""

import threading
import uuid
from typing import Any, Dict, List, Optional
from .types import ChangeSet, ChangedFile, ChangeSetStatus


class ChangeSetStore:
    """Thread-safe store for workspace ChangeSets."""

    def __init__(self) -> None:
        self._changesets: Dict[str, ChangeSet] = {}
        self._task_index: Dict[str, List[str]] = {}  # task_id -> list of changeset_ids
        self._lock = threading.RLock()

    def create_changeset(
        self,
        task_id: str,
        run_id: Optional[str] = None,
        changeset_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChangeSet:
        """Create a new ChangeSet associated with a task."""
        with self._lock:
            cid = changeset_id or f"cs_{uuid.uuid4().hex[:8]}"
            cs = ChangeSet(
                id=cid,
                task_id=task_id,
                run_id=run_id,
                status=ChangeSetStatus.PENDING,
                metadata=metadata or {},
            )
            self._changesets[cid] = cs
            self._task_index.setdefault(task_id, []).append(cid)
            return cs

    def record_file_change(self, changeset_id: str, change: ChangedFile) -> ChangeSet:
        """Record or update a ChangedFile in a specific ChangeSet."""
        with self._lock:
            cs = self._changesets.get(changeset_id)
            if not cs:
                raise KeyError(f"ChangeSet not found: {changeset_id}")
            # Replace existing change for this path if present, or append
            for i, f in enumerate(cs.files):
                if f.path == change.path:
                    cs.files[i] = change
                    return cs
            cs.files.append(change)
            return cs

    def record_changeset(self, changeset: ChangeSet) -> None:
        """Record or overwrite a complete ChangeSet."""
        with self._lock:
            self._changesets[changeset.id] = changeset
            task_cids = self._task_index.setdefault(changeset.task_id, [])
            if changeset.id not in task_cids:
                task_cids.append(changeset.id)

    def complete_changeset(self, changeset_id: str) -> Optional[ChangeSet]:
        """Mark a ChangeSet as COMPLETED."""
        with self._lock:
            cs = self._changesets.get(changeset_id)
            if cs:
                cs.status = ChangeSetStatus.COMPLETED
            return cs

    def get_changeset(self, changeset_id: str) -> Optional[ChangeSet]:
        """Retrieve a ChangeSet by its ID."""
        with self._lock:
            return self._changesets.get(changeset_id)

    def list_changesets(self) -> List[ChangeSet]:
        """List all recorded ChangeSets in insertion order."""
        with self._lock:
            return list(self._changesets.values())

    def get_task_changes(self, task_id: str) -> List[ChangeSet]:
        """Retrieve all ChangeSets produced by a specific task."""
        with self._lock:
            cids = self._task_index.get(task_id, [])
            return [self._changesets[cid] for cid in cids if cid in self._changesets]

    def get_latest_task_changeset(self, task_id: str) -> Optional[ChangeSet]:
        """Retrieve the most recent ChangeSet for a task."""
        changes = self.get_task_changes(task_id)
        return changes[-1] if changes else None

    def clear(self) -> None:
        """Clear all stored changesets."""
        with self._lock:
            self._changesets.clear()
            self._task_index.clear()
