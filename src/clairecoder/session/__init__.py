"""Session and persistence package for ClaireCoder (Correction #21)."""

from .errors import (
    SessionCorruptedError,
    SessionError,
    SessionNotFoundError,
    SessionStorageError,
    UnsupportedSchemaVersionError,
)
from .store import SessionStore
from .types import (
    CURRENT_SCHEMA_VERSION,
    ChangeSetReference,
    Session,
    SessionMetadata,
    SessionRunState,
    SessionStatus,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "ChangeSetReference",
    "Session",
    "SessionCorruptedError",
    "SessionError",
    "SessionMetadata",
    "SessionNotFoundError",
    "SessionRunState",
    "SessionStatus",
    "SessionStorageError",
    "SessionStore",
    "UnsupportedSchemaVersionError",
]
