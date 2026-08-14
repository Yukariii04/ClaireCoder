"""Verification History per CC-PRD-009.

Responsible for recording and retrieving verification outcomes.
Maintains history independently of workflow/execution authority.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from .types import (
    Verification, VerificationStatus, VerificationTestStatus, VerificationTestType,
    FailureCategory, VerificationCriterion, VerificationTestResult, CriterionResult, Evidence,
)

class VerificationHistory:
    """Stores verification outcomes and preserves verification identity."""

    def __init__(self):
        # Maps task_id -> list of verifications for that task
        self._history: Dict[str, List[Verification]] = {}
        # Fast lookup by verification_id
        self._verifications: Dict[str, Verification] = {}

    def record(self, verification: Verification) -> None:
        """Record a verification outcome."""
        self._verifications[verification.verification_id] = verification
        
        if verification.task_id not in self._history:
            self._history[verification.task_id] = []
            
        # Avoid duplicate entries if the same verification is recorded multiple times
        # (e.g. state updates)
        existing = [v for v in self._history[verification.task_id] 
                   if v.verification_id == verification.verification_id]
        if not existing:
            self._history[verification.task_id].append(verification)

    def get_verification(self, verification_id: str) -> Optional[Verification]:
        """Retrieve a specific verification record by ID."""
        return self._verifications.get(verification_id)

    def get_history(self, task_id: str) -> List[Verification]:
        """Retrieve all verification records for a given task (§49)."""
        return self._history.get(task_id, [])

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize history for persistence.
        
        Preserves all fields required by CC-PRD-009 §7:
        verificationId, taskId, executionId, criteria, status,
        evidence, startedAt, completedAt, plus criterion_results.
        """
        data: Dict[str, Any] = {"verifications": {}}
        for v_id, v in self._verifications.items():
            data["verifications"][v_id] = _serialize_verification(v)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VerificationHistory':
        """Restore history from serialized state.
        
        Rejects malformed verification records rather than silently
        substituting empty state for missing required fields.
        """
        history = cls()
        
        for v_id, v_data in data.get("verifications", {}).items():
            v = _deserialize_verification(v_data)
            history.record(v)
            
        return history


# =============================================================================
# SERIALIZATION HELPERS (module-private)
# =============================================================================

def _serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _deserialize_datetime(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


def _serialize_criterion(c: VerificationCriterion) -> Dict[str, Any]:
    return {
        "id": c.id,
        "description": c.description,
        "test_type": c.test_type.value,
        "required": c.required,
        "command": c.command,
        "expected_result": c.expected_result,
        "dependencies": list(c.dependencies),
    }


def _deserialize_criterion(d: Dict[str, Any]) -> VerificationCriterion:
    return VerificationCriterion(
        id=d["id"],
        description=d["description"],
        test_type=VerificationTestType(d["test_type"]),
        required=d.get("required", True),
        command=d.get("command"),
        expected_result=d.get("expected_result"),
        dependencies=d.get("dependencies", []),
    )


def _serialize_evidence(e: Evidence) -> Dict[str, Any]:
    return {
        "command": e.command,
        "exit_code": e.exit_code,
        "output": e.output,
        "error": e.error,
        "working_directory": e.working_directory,
        "environment_info": dict(e.environment_info) if e.environment_info else {},
        "timestamp": _serialize_datetime(e.timestamp),
        "summary": e.summary,
    }


def _deserialize_evidence(d: Dict[str, Any]) -> Evidence:
    return Evidence(
        command=d.get("command"),
        exit_code=d.get("exit_code"),
        output=d.get("output"),
        error=d.get("error"),
        working_directory=d.get("working_directory"),
        environment_info=d.get("environment_info", {}),
        timestamp=_deserialize_datetime(d.get("timestamp")),
        summary=d.get("summary"),
    )


def _serialize_test_result(tr: VerificationTestResult) -> Dict[str, Any]:
    return {
        "test_id": tr.test_id,
        "execution_id": tr.execution_id,
        "status": tr.status.value,
        "exit_code": tr.exit_code,
        "output": tr.output,
        "error": tr.error,
        "duration": tr.duration,
    }


def _deserialize_test_result(d: Dict[str, Any]) -> VerificationTestResult:
    return VerificationTestResult(
        test_id=d["test_id"],
        execution_id=d["execution_id"],
        status=VerificationTestStatus(d["status"]),
        exit_code=d.get("exit_code"),
        output=d.get("output"),
        error=d.get("error"),
        duration=d.get("duration"),
    )


def _serialize_criterion_result(cr: CriterionResult) -> Dict[str, Any]:
    return {
        "criterion_id": cr.criterion_id,
        "status": cr.status.value,
        "failure_category": cr.failure_category.value if cr.failure_category else None,
        "evidence": _serialize_evidence(cr.evidence) if cr.evidence else None,
        "test_result": _serialize_test_result(cr.test_result) if cr.test_result else None,
    }


def _deserialize_criterion_result(d: Dict[str, Any]) -> CriterionResult:
    fc = FailureCategory(d["failure_category"]) if d.get("failure_category") else None
    ev = _deserialize_evidence(d["evidence"]) if d.get("evidence") else None
    tr = _deserialize_test_result(d["test_result"]) if d.get("test_result") else None
    return CriterionResult(
        criterion_id=d["criterion_id"],
        status=VerificationStatus(d["status"]),
        failure_category=fc,
        evidence=ev,
        test_result=tr,
    )


def _serialize_verification(v: Verification) -> Dict[str, Any]:
    """Serialize a complete Verification per CC-PRD-009 §7."""
    return {
        "verification_id": v.verification_id,
        "task_id": v.task_id,
        "execution_id": v.execution_id,
        "criteria": [_serialize_criterion(c) for c in v.criteria],
        "status": v.status.value,
        "evidence": [_serialize_evidence(e) for e in v.evidence],
        "criterion_results": [_serialize_criterion_result(cr) for cr in v.criterion_results],
        "started_at": _serialize_datetime(v.started_at),
        "completed_at": _serialize_datetime(v.completed_at),
        "failure_category": v.failure_category.value if v.failure_category else None,
        "attempt_number": v.attempt_number,
        "max_retries": v.max_retries,
    }


def _deserialize_verification(d: Dict[str, Any]) -> Verification:
    """Deserialize a Verification, rejecting malformed records.
    
    Required fields per CC-PRD-009 §7: verification_id, task_id, status.
    If any required field is missing, raises ValueError.
    """
    # Validate required fields
    for required_key in ("verification_id", "task_id", "status"):
        if required_key not in d:
            raise ValueError(
                f"Malformed persisted Verification: missing required field '{required_key}'"
            )

    fc = FailureCategory(d["failure_category"]) if d.get("failure_category") else None

    v = Verification(
        verification_id=d["verification_id"],
        task_id=d["task_id"],
        execution_id=d.get("execution_id"),
        criteria=[_deserialize_criterion(c) for c in d.get("criteria", [])],
        status=VerificationStatus(d["status"]),
        evidence=[_deserialize_evidence(e) for e in d.get("evidence", [])],
        criterion_results=[_deserialize_criterion_result(cr) for cr in d.get("criterion_results", [])],
        started_at=_deserialize_datetime(d.get("started_at")),
        completed_at=_deserialize_datetime(d.get("completed_at")),
        failure_category=fc,
        attempt_number=d.get("attempt_number", 1),
        max_retries=d.get("max_retries", 3),
    )
    return v

