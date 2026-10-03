"""Verifier interface and DefaultVerifier implementation (Correction #17).

Establishes a first-class runtime verification boundary:
- Separates execution success from verification correctness.
- Produces structured VerificationResult with checks, evidence, and failures.
- Consumes real filesystem state, exit codes, and ChangeSet evidence.
- Integrates with VerificationEngine and VerificationRunner.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import os

from .types import (
    VerificationCriterion,
    VerificationResult,
    VerificationStatus,
    VerificationTestType,
)
from .runner import VerificationRunner, DefaultVerificationRunner
from .engine import VerificationEngine


class Verifier(ABC):
    """Abstract verifier boundary determining whether execution satisfies task requirements."""

    @abstractmethod
    def verify(
        self,
        task: Any,
        execution_result: Any,
        changeset: Optional[Any] = None,
        session_id: Optional[str] = None,
        attempt_number: int = 1,
    ) -> VerificationResult:
        """Evaluate task execution against verification criteria."""
        pass


class DefaultVerifier(Verifier):
    """Default verifier combining VerificationEngine, criteria runner, and ChangeSet evidence."""

    def __init__(
        self,
        engine: Optional[VerificationEngine] = None,
        runner: Optional[VerificationRunner] = None,
        workspace_root: Optional[str] = None,
    ) -> None:
        self._workspace_root = workspace_root or os.getcwd()
        self._runner = runner or DefaultVerificationRunner(workspace_root=self._workspace_root)
        self._engine = engine or VerificationEngine(runner=self._runner)

    @property
    def engine(self) -> VerificationEngine:
        return self._engine

    @property
    def runner(self) -> VerificationRunner:
        return self._runner

    def verify(
        self,
        task: Any,
        execution_result: Any,
        changeset: Optional[Any] = None,
        session_id: Optional[str] = None,
        attempt_number: int = 1,
    ) -> VerificationResult:
        """Evaluate task execution against verification criteria."""
        task_id = getattr(task, "id", str(task))
        changeset_id = getattr(changeset, "id", getattr(execution_result, "changeset_id", None))

        # 1. Monotonic Execution Gating: If execution failed, verification fails immediately
        exec_success = getattr(execution_result, "success", True)
        if not exec_success:
            err_msg = getattr(execution_result, "error_message", None) or "Task execution failed"
            return VerificationResult(
                task_id=task_id,
                success=False,
                status=VerificationStatus.FAILED,
                checks=["execution_result"],
                failures=[err_msg],
                evidence=[err_msg],
                changeset_id=changeset_id,
                metadata={"reason": "execution_failure"},
            )

        # 2. Check command exit codes if present on execution result
        exit_code = getattr(execution_result, "exit_code", None)
        if exit_code is not None and exit_code != 0:
            err_msg = f"Command failed with exit code {exit_code}"
            return VerificationResult(
                task_id=task_id,
                success=False,
                status=VerificationStatus.FAILED,
                checks=["command_exit_code"],
                failures=[err_msg],
                evidence=[getattr(execution_result, "error_message", None) or err_msg],
                changeset_id=changeset_id,
                metadata={"exit_code": exit_code},
            )

        # 3. Check test failures on execution result
        test_failures = getattr(execution_result, "test_failures", None)
        if test_failures:
            return VerificationResult(
                task_id=task_id,
                success=False,
                status=VerificationStatus.FAILED,
                checks=["test_results"],
                failures=list(test_failures),
                evidence=[f"{len(test_failures)} test(s) failed: {test_failures}"],
                changeset_id=changeset_id,
                metadata={"test_failures": test_failures},
            )

        # 4. Extract validation criteria from task
        val_reqs = list(
            getattr(task, "validation_requirements", [])
            or getattr(task, "validation", [])
            or []
        )
        if not val_reqs and getattr(task, "expected_result", None):
            val_reqs.append(task.expected_result)

        # 3. If explicit criteria exist, execute real verification through VerificationEngine
        if val_reqs:
            criteria = [
                VerificationCriterion(
                    id=f"{task_id}:{idx}",
                    description=req,
                    test_type=VerificationTestType.UNIT,
                )
                for idx, req in enumerate(val_reqs)
            ]

            v_id = f"v_{task_id}_{attempt_number}"
            self._engine.create_verification(
                verification_id=v_id,
                task_id=task_id,
                criteria=criteria,
                execution_id=getattr(execution_result, "execution_id", None),
            )
            self._engine.start_verification(v_id)
            v = self._engine.execute_verification(v_id)

            checks: List[str] = [c.description for c in v.criteria]
            failures: List[str] = []
            evidence: List[Any] = []

            for cr in v.criterion_results:
                if cr.status != VerificationStatus.PASSED:
                    if cr.test_result and cr.test_result.error:
                        failures.append(cr.test_result.error)
                    elif cr.evidence and cr.evidence.error:
                        failures.append(cr.evidence.error)
                    else:
                        failures.append(f"Criterion failed: {cr.criterion_id}")

                if cr.evidence:
                    if cr.evidence.summary:
                        evidence.append(cr.evidence.summary)
                    if cr.evidence.output:
                        evidence.append(cr.evidence.output)
                    if cr.evidence.error:
                        evidence.append(cr.evidence.error)

            if changeset:
                file_count = len(getattr(changeset, "files", []))
                evidence.append(f"ChangeSet {changeset.id} captured: {file_count} file(s) changed")

            is_passed = (v.status == VerificationStatus.PASSED)
            return VerificationResult(
                task_id=task_id,
                success=is_passed,
                status=v.status,
                checks=checks,
                evidence=evidence,
                failures=failures,
                changeset_id=changeset_id,
                metadata={"verification_id": v_id},
            )

        # 4. If no explicit criteria, evaluate against task type and ChangeSet evidence
        task_type_val = getattr(getattr(task, "type", None), "value", str(getattr(task, "type", "")))
        if changeset and getattr(changeset, "files", None):
            changed_paths = [cf.path for cf in changeset.files]
            return VerificationResult(
                task_id=task_id,
                success=True,
                status=VerificationStatus.PASSED,
                checks=["changeset_inspection"],
                evidence=[f"{len(changed_paths)} file(s) modified: {changed_paths}"],
                failures=[],
                changeset_id=changeset_id,
                metadata={"has_criteria": False, "verified_by_changeset": True},
            )

        if task_type_val in ("analysis", "documentation", "other"):
            return VerificationResult(
                task_id=task_id,
                success=True,
                status=VerificationStatus.PASSED,
                checks=[f"task_type_{task_type_val}_exempt"],
                evidence=[f"No filesystem verification required for {task_type_val} task"],
                failures=[],
                changeset_id=changeset_id,
                metadata={"has_criteria": False, "exempt_type": task_type_val},
            )

        # Non-modifying task with no explicit criteria
        return VerificationResult(
            task_id=task_id,
            success=True,
            status="unverified",
            checks=["no_criteria_provided"],
            evidence=["Execution succeeded; no explicit verification criteria specified"],
            failures=[],
            changeset_id=changeset_id,
            metadata={"has_criteria": False, "unverified": True},
        )
