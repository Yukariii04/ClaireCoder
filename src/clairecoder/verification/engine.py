"""Verification Engine per CC-PRD-009.

The VerificationEngine acts as the orchestration boundary.
It coordinates Runner, Evaluator, and History but SHALL NOT
absorb their responsibilities.

Architectural boundaries (§3, §54):
- Does NOT execute tools directly (routes through Engineering Engine).
- Does NOT make permission decisions.
- Does NOT own Workflow, Execution, or Interaction state.
- Does NOT couple to a specific model provider.
- Does NOT replace the Execution State system (CC-PRD-007).
- Does NOT create unlimited retry loops (§38).
- Model claims are NOT verification evidence (§24).
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone

from .types import (
    Verification,
    VerificationStatus,
    VerificationCriterion,
    CriterionResult,
    Evidence,
    VerificationTestResult,
    FailureCategory,
    VerificationTestStatus,
)
from .history import VerificationHistory
from .evaluator import VerificationResultEvaluator
from .runner import VerificationRunner


class VerificationEngine:
    """Orchestrates verification lifecycle, evaluation, and history."""

    def __init__(
        self,
        max_retries: int = 3,
        history: Optional[VerificationHistory] = None,
        evaluator: Optional[VerificationResultEvaluator] = None,
        runner: Optional[VerificationRunner] = None,
    ):
        self._max_retries = max_retries
        self._history = history or VerificationHistory()
        self._evaluator = evaluator or VerificationResultEvaluator()
        self._runner = runner

    # =========================================================================
    # VERIFICATION LIFECYCLE
    # =========================================================================

    def create_verification(
        self,
        verification_id: str,
        task_id: str,
        criteria: List[VerificationCriterion],
        execution_id: Optional[str] = None,
    ) -> Verification:
        """Create a Verification object for a Task (§7)."""
        verification = Verification(
            verification_id=verification_id,
            task_id=task_id,
            execution_id=execution_id,
            criteria=criteria,
            status=VerificationStatus.PENDING,
            max_retries=self._max_retries,
        )
        self._history.record(verification)
        return verification

    def start_verification(self, verification_id: str) -> Verification:
        """Transition verification to RUNNING (§8)."""
        v = self._get_verification(verification_id)
        if v.status != VerificationStatus.PENDING:
            raise ValueError(
                f"Cannot start verification in state {v.status.value}"
            )
        v.status = VerificationStatus.RUNNING
        v.started_at = datetime.now(timezone.utc)
        self._history.record(v)
        return v

    def cancel_verification(self, verification_id: str) -> Verification:
        """Cancel a verification (§35). Distinct from failure."""
        v = self._get_verification(verification_id)
        if v.status in (VerificationStatus.PASSED, VerificationStatus.FAILED):
            raise ValueError(
                f"Cannot cancel verification in terminal state {v.status.value}"
            )
        v.status = VerificationStatus.CANCELLED
        v.completed_at = datetime.now(timezone.utc)
        self._history.record(v)
        return v

    def get_verification(self, verification_id: str) -> Optional[Verification]:
        """Retrieve a verification by ID."""
        return self._history.get_verification(verification_id)

    def get_history(self, task_id: str) -> List[Verification]:
        """Retrieve verification history for a task (§49)."""
        return self._history.get_history(task_id)

    # =========================================================================
    # CRITERION RESULT SUBMISSION & EVALUATION
    # =========================================================================

    def submit_criterion_result(
        self,
        verification_id: str,
        criterion_id: str,
        test_result: Optional[VerificationTestResult] = None,
        evidence: Optional[Evidence] = None,
        failure_category: Optional[FailureCategory] = None,
    ) -> CriterionResult:
        """Delegate result evaluation to VerificationResultEvaluator."""
        v = self._get_verification(verification_id)
        result = self._evaluator.submit_criterion_result(
            verification=v,
            criterion_id=criterion_id,
            test_result=test_result,
            evidence=evidence,
            failure_category=failure_category,
        )
        self._history.record(v)
        return result

    def evaluate_verification(self, verification_id: str) -> Verification:
        """Delegate overall outcome evaluation to VerificationResultEvaluator."""
        v = self._get_verification(verification_id)
        v = self._evaluator.evaluate_verification(v)
        self._history.record(v)
        return v

    def execute_verification(self, verification_id: str) -> Verification:
        """Executes a full verification lifecycle using the Runner and Evaluator.
        
        Satisfies the requirement to explicitly coordinate the components:
        1. Receives the verification request/criteria.
        2. Invokes the VerificationRunner.
        3. Obtains structured TestResult and/or Evidence.
        4. Passes the resulting evidence to VerificationResultEvaluator.
        5. Obtains the evaluated Verification result.
        6. Records the result through VerificationHistory.
        7. Returns the final verification result.
        """
        v = self._get_verification(verification_id)
        if v.status != VerificationStatus.RUNNING:
            raise ValueError(f"Cannot execute verification in state {v.status.value}")
            
        if not self._runner:
            raise RuntimeError("VerificationRunner is required to execute verification")

        for criterion in v.criteria:
            # CORRECTION #1: Dependency Check before Runner invocation
            dep_status = self._evaluator.check_dependencies(v, criterion)
            if dep_status == VerificationStatus.BLOCKED:
                self.submit_criterion_result(
                    verification_id=verification_id,
                    criterion_id=criterion.id,
                    test_result=None,
                    evidence=None
                )
                continue

            try:
                test_result, evidence = self._runner.run(
                    criterion=criterion,
                    execution_id=v.execution_id or ""
                )
            except Exception as e:
                # CORRECTION #2: Distinct Exception Boundary.
                # Only runner failures are caught here.
                tr = VerificationTestResult(
                    test_id=criterion.id,
                    execution_id=v.execution_id or "",
                    status=VerificationTestStatus.FAILED,
                    error=str(e)
                )
                self.submit_criterion_result(
                    verification_id=verification_id,
                    criterion_id=criterion.id,
                    test_result=tr,
                    failure_category=FailureCategory.TOOL_FAILURE
                )
                continue
                
            # Evaluator failures propagate normally (not swallowed as tool failures)
            self.submit_criterion_result(
                verification_id=verification_id,
                criterion_id=criterion.id,
                test_result=test_result,
                evidence=evidence,
            )
                
        # Evaluate overall outcome and history is recorded by evaluate_verification
        v = self.evaluate_verification(verification_id)
        return v

    # =========================================================================
    # RETRY SUPPORT (§37, §38)
    # =========================================================================

    def can_retry(self, verification_id: str) -> bool:
        """Check if verification can be retried within bounds (§38)."""
        v = self._get_verification(verification_id)
        return v.attempt_number < v.max_retries

    def create_retry(self, verification_id: str) -> Verification:
        """Create a retry verification with incremented attempt (§37)."""
        v = self._get_verification(verification_id)
        if v.status not in (VerificationStatus.FAILED, VerificationStatus.BLOCKED):
            raise ValueError(
                f"Cannot retry verification in state {v.status.value}"
            )
        if not self.can_retry(verification_id):
            raise ValueError(
                f"Maximum retries ({v.max_retries}) exceeded for verification {verification_id}"
            )

        new_id = f"{v.verification_id}_retry{v.attempt_number}"
        retry = self.create_verification(
            verification_id=new_id,
            task_id=v.task_id,
            criteria=v.criteria,
            execution_id=v.execution_id,
        )
        retry.attempt_number = v.attempt_number + 1
        retry.max_retries = v.max_retries
        self._history.record(retry)
        return retry

    # =========================================================================
    # TIMEOUT HANDLING (§34)
    # =========================================================================

    def timeout_verification(self, verification_id: str) -> Verification:
        """Mark verification as timed out (§34)."""
        v = self._get_verification(verification_id)
        if v.status != VerificationStatus.RUNNING:
            raise ValueError(
                f"Cannot timeout verification in state {v.status.value}"
            )
        v.status = VerificationStatus.FAILED
        v.failure_category = FailureCategory.TIMEOUT
        v.completed_at = datetime.now(timezone.utc)
        self._history.record(v)
        return v

    # =========================================================================
    # CONTEXT / MEMORY INTEGRATION (§39, §40)
    # =========================================================================

    def to_context(self, verification_id: str) -> Dict:
        """Produce a context-compatible summary of verification results (§39)."""
        v = self._get_verification(verification_id)
        return {
            "verification_id": v.verification_id,
            "task_id": v.task_id,
            "status": v.status.value,
            "failure_category": v.failure_category.value if v.failure_category else None,
            "attempt_number": v.attempt_number,
            "criteria_count": len(v.criteria),
            "passed_count": sum(
                1 for cr in v.criterion_results
                if cr.status == VerificationStatus.PASSED
            ),
            "failed_count": sum(
                1 for cr in v.criterion_results
                if cr.status == VerificationStatus.FAILED
            ),
            "evidence_count": len(v.evidence),
        }

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _get_verification(self, verification_id: str) -> Verification:
        v = self._history.get_verification(verification_id)
        if not v:
            raise ValueError(f"Verification {verification_id} not found")
        return v
