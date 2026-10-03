"""ChangeSet & Diff Store subsystem.

CC-PRD-007 / Correction #16: Structured ChangeSet representation and Diff Store.
"""

from .types import FileOperation, ChangeSetStatus, ChangedFile, ChangeSet
from .diff import generate_file_diff, compute_unified_diff, is_binary_buffer
from .store import ChangeSetStore
from .tracker import ChangeTracker, WorkspaceSnapshot

__all__ = [
    "FileOperation",
    "ChangeSetStatus",
    "ChangedFile",
    "ChangeSet",
    "generate_file_diff",
    "compute_unified_diff",
    "is_binary_buffer",
    "ChangeSetStore",
    "ChangeTracker",
    "WorkspaceSnapshot",
]
