"""ChangeSet & ChangedFile data models.

CC-PRD-007 / Correction #16: Structured ChangeSet representation of workspace file mutations.
Provides observable, reviewable, and deterministic diffs between task execution
and workspace files instead of opaque direct disk mutations.
"""

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class FileOperation(str, Enum):
    """File mutation operations."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"

    @classmethod
    def _missing_(cls, value: Any) -> "FileOperation":
        if isinstance(value, str):
            val = value.lower().strip()
            for member in cls:
                if member.value == val:
                    return member
        return cls.MODIFIED


class ChangeSetStatus(str, Enum):
    """Status of a ChangeSet lifecycle."""
    PENDING = "pending"
    RECORDED = "recorded"
    APPLIED = "applied"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTED = "reverted"


@dataclass
class ChangedFile:
    """Represents a single file mutation within a ChangeSet.

    Carries:
    - path: normalized relative workspace path
    - operation: created, modified, or deleted
    - old_content / new_content: file text content (None if binary/absent)
    - additions / deletions: line change counts
    - diff: unified diff text
    - existed_before: whether the file existed prior to execution
    - is_binary: whether the file is binary
    """
    path: str
    operation: FileOperation
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    additions: int = 0
    deletions: int = 0
    diff: str = ""
    existed_before: bool = False
    is_binary: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.operation, str) and not isinstance(self.operation, FileOperation):
            self.operation = FileOperation(self.operation)
        # Normalize path separators to forward slashes for cross-platform determinism
        self.path = self.path.replace("\\", "/")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ChangedFile to a dictionary."""
        return {
            "path": self.path,
            "operation": self.operation.value,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "additions": self.additions,
            "deletions": self.deletions,
            "diff": self.diff,
            "existed_before": self.existed_before,
            "is_binary": self.is_binary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChangedFile":
        """Deserialize ChangedFile from a dictionary."""
        return cls(
            path=data["path"],
            operation=FileOperation(data["operation"]),
            old_content=data.get("old_content"),
            new_content=data.get("new_content"),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            diff=data.get("diff", ""),
            existed_before=data.get("existed_before", False),
            is_binary=data.get("is_binary", False),
        )


@dataclass
class ChangeSet:
    """A logical set of file changes produced by one task execution.

    Contains:
    - id: unique changeset identifier
    - task_id: task that performed the file mutations
    - files: list of ChangedFile items
    - created_at: epoch timestamp
    - status: current changeset state
    - run_id: optional execution run correlation ID
    - metadata: arbitrary structured metadata
    """
    id: str
    task_id: str
    files: List[ChangedFile] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: ChangeSetStatus = ChangeSetStatus.COMPLETED
    run_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.status, str) and not isinstance(self.status, ChangeSetStatus):
            self.status = ChangeSetStatus(self.status)

    @property
    def total_additions(self) -> int:
        """Sum of lines added across all changed files."""
        return sum(f.additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        """Sum of lines deleted across all changed files."""
        return sum(f.deletions for f in self.files)

    @property
    def changed_paths(self) -> List[str]:
        """List of all file paths mutated in this ChangeSet."""
        return [f.path for f in self.files]

    @property
    def modified_paths(self) -> List[str]:
        """Alias for changed_paths."""
        return self.changed_paths

    @property
    def file_count(self) -> int:
        """Number of changed files in this ChangeSet."""
        return len(self.files)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ChangeSet to a dictionary."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "status": self.status.value,
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "files": [f.to_dict() for f in self.files],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChangeSet":
        """Deserialize ChangeSet from a dictionary."""
        files = [ChangedFile.from_dict(f) for f in data.get("files", [])]
        return cls(
            id=data["id"],
            task_id=data["task_id"],
            run_id=data.get("run_id"),
            files=files,
            created_at=data.get("created_at", time.time()),
            status=ChangeSetStatus(data.get("status", ChangeSetStatus.COMPLETED.value)),
            metadata=data.get("metadata", {}),
        )
