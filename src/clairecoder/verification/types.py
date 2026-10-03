"""Verification & Validation type definitions per CC-PRD-009.

This module defines the data models for the Verification subsystem:
- Verification object (§7)
- Verification states (§8)
- Verification criteria (§10)
- Test types (§11)
- Test result (§21)
- Test status (§22)
- Evidence (§23)
- Failure classification (§32)
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone


class VerificationStatus(str, Enum):
    """Verification states per CC-PRD-009 §8.

    PENDING   — Verification exists but has not started (§9).
    RUNNING   — Verification is actively executing (§9).
    PASSED    — All required criteria satisfied (§9).
    FAILED    — One or more required criteria failed (§9).
    BLOCKED   — Required dependency or resource unavailable (§9).
    CANCELLED — Verification was explicitly cancelled (§9).
    """
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class VerificationTestType(str, Enum):
    """Test type categories per CC-PRD-009 §11.

    These describe verification intent, not a specific testing framework.
    """
    UNIT = "unit"
    INTEGRATION = "integration"
    FUNCTIONAL = "functional"
    BUILD = "build"
    STATIC = "static"
    REPOSITORY = "repository"


class VerificationTestStatus(str, Enum):
    """Test result states per CC-PRD-009 §22."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class FailureCategory(str, Enum):
    """Failure classification per CC-PRD-009 §32.

    Tool failures (§33) are distinct from test failures.
    Permission failures are distinct from test failures.
    """
    ASSERTION_FAILURE = "assertion_failure"
    TEST_FAILURE = "test_failure"
    BUILD_FAILURE = "build_failure"
    STATIC_FAILURE = "static_failure"
    REPOSITORY_MISMATCH = "repository_mismatch"
    TOOL_FAILURE = "tool_failure"
    PERMISSION_FAILURE = "permission_failure"
    TIMEOUT = "timeout"
    DEPENDENCY_FAILURE = "dependency_failure"
    UNKNOWN_FAILURE = "unknown_failure"


@dataclass
class VerificationCriterion:
    """A single verification criterion per CC-PRD-009 §10.

    A Task defines what constitutes successful completion via criteria.
    Criteria may be required or optional (§27).
    """
    id: str
    description: str
    test_type: VerificationTestType
    required: bool = True
    command: Optional[str] = None
    expected_result: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)


@dataclass
class Evidence:
    """Verification evidence per CC-PRD-009 §23.

    Evidence preserves what was checked and the resulting output.
    Evidence is associated with a Verification (§23).
    Secrets SHALL NOT be retained (§48).
    """
    command: Optional[str] = None
    exit_code: Optional[int] = None
    output: Optional[str] = None
    error: Optional[str] = None
    working_directory: Optional[str] = None
    environment_info: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    summary: Optional[str] = None


@dataclass
class VerificationTestResult:
    """Test execution result per CC-PRD-009 §21.

    Preserves enough information to determine the verification outcome.
    """
    test_id: str
    execution_id: str
    status: VerificationTestStatus
    exit_code: Optional[int] = None
    output: Optional[str] = None
    error: Optional[str] = None
    duration: Optional[float] = None


@dataclass
class CriterionResult:
    """Result for a single verification criterion."""
    criterion_id: str
    status: VerificationStatus
    failure_category: Optional[FailureCategory] = None
    evidence: Optional[Evidence] = None
    test_result: Optional[VerificationTestResult] = None


@dataclass
class Verification:
    """Verification object per CC-PRD-009 §7.

    Represents the verification lifecycle for a Task.
    Independent of the underlying testing framework (§7).
    """
    verification_id: str
    task_id: str
    execution_id: Optional[str] = None
    criteria: List[VerificationCriterion] = field(default_factory=list)
    status: VerificationStatus = VerificationStatus.PENDING
    evidence: List[Evidence] = field(default_factory=list)
    criterion_results: List[CriterionResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failure_category: Optional[FailureCategory] = None
    attempt_number: int = 1
    max_retries: int = 3


@dataclass
class VerificationResult:
    """Structured result of a task verification boundary (Correction #17).

    Distinguishes execution success from verification correctness and
    preserves verification evidence, performed checks, and failure reasons.
    """
    task_id: str
    success: bool
    status: Union[VerificationStatus, str] = VerificationStatus.PASSED
    checks: List[str] = field(default_factory=list)
    evidence: List[Any] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    duration: Optional[float] = None
    changeset_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __iter__(self):
        """Enable tuple unpacking: ver_result, passed = result."""
        yield self
        yield self.success

    def to_dict(self) -> Dict[str, Any]:
        """Serialize VerificationResult to dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "checks": list(self.checks),
            "evidence": list(self.evidence),
            "failures": list(self.failures),
            "duration": self.duration,
            "changeset_id": self.changeset_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        """Deserialize VerificationResult from dictionary."""
        raw_status = data.get("status", "passed")
        try:
            status = VerificationStatus(raw_status)
        except (ValueError, KeyError):
            status = VerificationStatus.PASSED if data.get("success", False) else VerificationStatus.FAILED

        return cls(
            task_id=data.get("task_id", ""),
            success=bool(data.get("success", False)),
            status=status,
            checks=list(data.get("checks", [])),
            evidence=list(data.get("evidence", [])),
            failures=list(data.get("failures", [])),
            duration=data.get("duration"),
            changeset_id=data.get("changeset_id"),
            metadata=dict(data.get("metadata", {})),
        )

