"""Verification Result Evaluator per CC-PRD-009.

Responsible for interpreting verification evidence/results against
verification criteria. Distinguishes PASS/FAIL/BLOCKED semantics,
accounts for required vs. optional criteria, and never treats
an unsupported model claim as verification evidence.
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone

from .types import (
    Verification,
    VerificationStatus,
    VerificationCriterion,
    CriterionResult,
    Evidence,
    VerificationTestResult,
    VerificationTestStatus,
    FailureCategory,
)

class VerificationResultEvaluator:
    """Evaluates evidence and test results against criteria."""

    def submit_criterion_result(
        self,
        verification: Verification,
        criterion_id: str,
        test_result: Optional[VerificationTestResult] = None,
        evidence: Optional[Evidence] = None,
        failure_category: Optional[FailureCategory] = None,
    ) -> CriterionResult:
        """Submit and evaluate a result for a single verification criterion."""
        if verification.status != VerificationStatus.RUNNING:
            raise ValueError(
                f"Cannot submit results to verification in state {verification.status.value}"
            )

        criterion = self._find_criterion(verification, criterion_id)

        # Check dependencies (§28)
        dep_status = self.check_dependencies(verification, criterion)
        if dep_status == VerificationStatus.BLOCKED:
            result = CriterionResult(
                criterion_id=criterion_id,
                status=VerificationStatus.BLOCKED,
                failure_category=FailureCategory.DEPENDENCY_FAILURE,
                evidence=evidence,
            )
            verification.criterion_results.append(result)
            if evidence:
                verification.evidence.append(evidence)
            return result

        # Determine status from evidence or test result
        if test_result:
            status = self._status_from_test_result(test_result)
            if status == VerificationStatus.FAILED and failure_category is None:
                failure_category = self._classify_failure(test_result)
        elif evidence:
            # Evidence without test result
            if evidence.exit_code is not None and evidence.exit_code == 0:
                status = VerificationStatus.PASSED
            elif evidence.exit_code is not None:
                status = VerificationStatus.FAILED
                if failure_category is None:
                    failure_category = FailureCategory.UNKNOWN_FAILURE
            else:
                status = VerificationStatus.BLOCKED
        else:
            # Model claims are NOT evidence (§24) - blocked
            status = VerificationStatus.BLOCKED
            failure_category = FailureCategory.UNKNOWN_FAILURE

        result = CriterionResult(
            criterion_id=criterion_id,
            status=status,
            failure_category=failure_category,
            evidence=evidence,
            test_result=test_result,
        )
        verification.criterion_results.append(result)
        if evidence:
            verification.evidence.append(evidence)
        return result

    def evaluate_verification(self, verification: Verification) -> Verification:
        """Evaluate overall verification outcome from criterion results."""
        if verification.status != VerificationStatus.RUNNING:
            raise ValueError(
                f"Cannot evaluate verification in state {verification.status.value}"
            )

        result_map: Dict[str, CriterionResult] = {
            cr.criterion_id: cr for cr in verification.criterion_results
        }

        has_required_failure = False
        has_blocked = False
        all_required_passed = True

        for criterion in verification.criteria:
            cr = result_map.get(criterion.id)

            if cr is None:
                if criterion.required:
                    # §45: Required but unavailable -> BLOCKED
                    all_required_passed = False
                    has_blocked = True
                continue

            if criterion.required:
                if cr.status == VerificationStatus.FAILED:
                    has_required_failure = True
                    all_required_passed = False
                elif cr.status == VerificationStatus.BLOCKED:
                    has_blocked = True
                    all_required_passed = False
                elif cr.status != VerificationStatus.PASSED:
                    all_required_passed = False

        if has_required_failure:
            verification.status = VerificationStatus.FAILED
            # Use the first required failure category
            for cr in verification.criterion_results:
                crit = self._find_criterion(verification, cr.criterion_id)
                if crit.required and cr.status == VerificationStatus.FAILED:
                    verification.failure_category = cr.failure_category
                    break
        elif has_blocked:
            verification.status = VerificationStatus.BLOCKED
        elif all_required_passed:
            verification.status = VerificationStatus.PASSED
        else:
            verification.status = VerificationStatus.BLOCKED

        verification.completed_at = datetime.now(timezone.utc)
        return verification

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _find_criterion(
        self, v: Verification, criterion_id: str
    ) -> VerificationCriterion:
        for c in v.criteria:
            if c.id == criterion_id:
                return c
        raise ValueError(
            f"Criterion {criterion_id} not found in verification {v.verification_id}"
        )

    def check_dependencies(
        self, v: Verification, criterion: VerificationCriterion
    ) -> Optional[VerificationStatus]:
        if not criterion.dependencies:
            return None

        result_map = {cr.criterion_id: cr for cr in v.criterion_results}
        for dep_id in criterion.dependencies:
            dep_result = result_map.get(dep_id)
            if dep_result is None:
                return VerificationStatus.BLOCKED
            if dep_result.status in (
                VerificationStatus.FAILED,
                VerificationStatus.BLOCKED,
            ):
                return VerificationStatus.BLOCKED
        return None

    def _status_from_test_result(self, tr: VerificationTestResult) -> VerificationStatus:
        mapping = {
            VerificationTestStatus.PASSED: VerificationStatus.PASSED,
            VerificationTestStatus.FAILED: VerificationStatus.FAILED,
            VerificationTestStatus.SKIPPED: VerificationStatus.BLOCKED,
            VerificationTestStatus.BLOCKED: VerificationStatus.BLOCKED,
            VerificationTestStatus.CANCELLED: VerificationStatus.CANCELLED,
        }
        return mapping.get(tr.status, VerificationStatus.BLOCKED)

    def _classify_failure(self, tr: VerificationTestResult) -> FailureCategory:
        if tr.exit_code is not None and tr.exit_code == 127:
            return FailureCategory.TOOL_FAILURE
        if tr.error and "permission" in tr.error.lower():
            return FailureCategory.PERMISSION_FAILURE
        if tr.error and "assertion" in tr.error.lower():
            return FailureCategory.ASSERTION_FAILURE
        return FailureCategory.TEST_FAILURE
