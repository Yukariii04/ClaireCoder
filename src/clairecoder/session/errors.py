"""Session error hierarchy for ClaireCoder (Correction #21).

Structured errors for session lifecycle and persistence failures.
"""

from typing import Optional


class SessionError(Exception):
    """Base exception for all session-related operations."""
    pass


class SessionNotFoundError(SessionError):
    """Raised when a requested session is not found in the session store."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session '{session_id}' not found")
        self.session_id = session_id


class SessionCorruptedError(SessionError):
    """Raised when a session file on disk is malformed, partially written, or corrupted."""

    def __init__(self, session_id: str, reason: str) -> None:
        super().__init__(f"Session '{session_id}' is corrupted: {reason}")
        self.session_id = session_id
        self.reason = reason


class UnsupportedSchemaVersionError(SessionError):
    """Raised when a persisted session schema version is incompatible with current code."""

    def __init__(self, session_id: str, found_version: int, supported_version: int) -> None:
        super().__init__(
            f"Session '{session_id}' has schema version {found_version}, but supported version is {supported_version}"
        )
        self.session_id = session_id
        self.found_version = found_version
        self.supported_version = supported_version


class SessionStorageError(SessionError):
    """Raised when underlying filesystem/storage operations fail."""

    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.original_error = original_error
