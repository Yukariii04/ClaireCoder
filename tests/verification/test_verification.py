"""Tests for the Verification & Validation subsystem (CC-PRD-009).

Covers:
- Runner interface contract
- Runner mock/fake execution
- Evaluator required criterion PASS
- Evaluator required criterion FAIL
- Evaluator optional criterion behavior
- BLOCKED verification
- unsupported/model-only evidence rejection
- History recording
- History retrieval
- VerificationEngine orchestration
- Verification boundary isolation
- no Tool/Permission/Workflow/Execution/Model bypass
"""
import pytest
from datetime import datetime, timezone
from typing import Tuple, Optional

from clairecoder.verification.types import (
    VerificationStatus,
    VerificationTestType,
    VerificationTestStatus,
    FailureCategory,
    VerificationCriterion,
    Evidence,
    VerificationTestResult,
    CriterionResult,
    Verification,
)
from clairecoder.verification.engine import VerificationEngine
from clairecoder.verification.runner import VerificationRunner
from clairecoder.verification.evaluator import VerificationResultEvaluator
from clairecoder.verification.history import VerificationHistory


# =============================================================================
# TYPE ENUM TESTS
# =============================================================================

def test_verification_status_enum():
    expected = {"pending", "running", "passed", "failed", "blocked", "cancelled"}
    assert {s.value for s in VerificationStatus} == expected

def test_test_type_enum():
    expected = {"unit", "integration", "functional", "build", "static", "repository"}
    assert {t.value for t in VerificationTestType} == expected

def test_test_status_enum():
    expected = {"passed", "failed", "skipped", "blocked", "cancelled"}
    assert {s.value for s in VerificationTestStatus} == expected

def test_failure_category_enum():
    expected = {
        "assertion_failure", "test_failure", "build_failure",
        "static_failure", "repository_mismatch", "tool_failure",
        "permission_failure", "timeout", "dependency_failure",
        "unknown_failure",
    }
    assert {f.value for f in FailureCategory} == expected


# =============================================================================
# RUNNER COMPONENT TESTS
# =============================================================================

class MockRunner(VerificationRunner):
    """A fake runner for testing the interface without executing real commands."""
    def __init__(self, result_mapping):
        self.result_mapping = result_mapping
        
    def run(self, criterion: VerificationCriterion, execution_id: str) -> Tuple[Optional[VerificationTestResult], Optional[Evidence]]:
        return self.result_mapping.get(criterion.id, (None, None))

def test_runner_interface_contract():
    """Runner interface contract and mock/fake execution."""
    tr = VerificationTestResult("t1", "e1", VerificationTestStatus.PASSED, exit_code=0)
    ev = Evidence(command="test", exit_code=0)
    runner = MockRunner({"c1": (tr, ev)})
    
    crit = VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT)
    result_tr, result_ev = runner.run(crit, "exec1")
    
    assert result_tr == tr
    assert result_ev == ev


# =============================================================================
# EVALUATOR COMPONENT TESTS
# =============================================================================

def test_evaluator_required_criterion_pass():
    """Evaluator required criterion PASS."""
    evaluator = VerificationResultEvaluator()
    v = Verification(verification_id="v1", task_id="t1", criteria=[
        VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT, required=True)
    ])
    v.status = VerificationStatus.RUNNING
    
    tr = VerificationTestResult("test1", "exec1", VerificationTestStatus.PASSED, 0)
    evaluator.submit_criterion_result(v, "c1", test_result=tr)
    v = evaluator.evaluate_verification(v)
    
    assert v.status == VerificationStatus.PASSED

def test_evaluator_required_criterion_fail():
    """Evaluator required criterion FAIL."""
    evaluator = VerificationResultEvaluator()
    v = Verification(verification_id="v1", task_id="t1", criteria=[
        VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT, required=True)
    ])
    v.status = VerificationStatus.RUNNING
    
    tr = VerificationTestResult("test1", "exec1", VerificationTestStatus.FAILED, 1, error="failed")
    evaluator.submit_criterion_result(v, "c1", test_result=tr)
    v = evaluator.evaluate_verification(v)
    
    assert v.status == VerificationStatus.FAILED
    assert v.failure_category == FailureCategory.TEST_FAILURE

def test_evaluator_optional_criterion_behavior():
    """Evaluator optional criterion behavior."""
    evaluator = VerificationResultEvaluator()
    v = Verification(verification_id="v1", task_id="t1", criteria=[
        VerificationCriterion(id="c1", description="Req", test_type=VerificationTestType.UNIT, required=True),
        VerificationCriterion(id="c2", description="Opt", test_type=VerificationTestType.STATIC, required=False),
    ])
    v.status = VerificationStatus.RUNNING
    
    tr_req = VerificationTestResult("t1", "e1", VerificationTestStatus.PASSED, 0)
    tr_opt = VerificationTestResult("t2", "e1", VerificationTestStatus.FAILED, 1)
    
    evaluator.submit_criterion_result(v, "c1", test_result=tr_req)
    evaluator.submit_criterion_result(v, "c2", test_result=tr_opt)
    
    v = evaluator.evaluate_verification(v)
    # Optional failure does not block overall pass
    assert v.status == VerificationStatus.PASSED

def test_evaluator_blocked_verification():
    """BLOCKED verification (e.g. missing evidence or failed dependency)."""
    evaluator = VerificationResultEvaluator()
    v = Verification(verification_id="v1", task_id="t1", criteria=[
        VerificationCriterion(id="c1", description="Dep", test_type=VerificationTestType.BUILD),
        VerificationCriterion(id="c2", description="Test", test_type=VerificationTestType.UNIT, dependencies=["c1"])
    ])
    v.status = VerificationStatus.RUNNING
    
    tr_dep = VerificationTestResult("t1", "e1", VerificationTestStatus.FAILED, 1)
    evaluator.submit_criterion_result(v, "c1", test_result=tr_dep)
    
    # c2 should be blocked because c1 failed
    tr_test = VerificationTestResult("t2", "e1", VerificationTestStatus.PASSED, 0)
    cr2 = evaluator.submit_criterion_result(v, "c2", test_result=tr_test)
    
    assert cr2.status == VerificationStatus.BLOCKED
    assert cr2.failure_category == FailureCategory.DEPENDENCY_FAILURE

def test_evaluator_reject_model_only_evidence():
    """unsupported/model-only evidence rejection."""
    evaluator = VerificationResultEvaluator()
    v = Verification(verification_id="v1", task_id="t1", criteria=[
        VerificationCriterion(id="c1", description="Claim", test_type=VerificationTestType.UNIT)
    ])
    v.status = VerificationStatus.RUNNING
    
    # No test result, no evidence
    cr = evaluator.submit_criterion_result(v, "c1")
    
    # Model claims are not evidence -> BLOCKED
    assert cr.status == VerificationStatus.BLOCKED


# =============================================================================
# HISTORY COMPONENT TESTS
# =============================================================================

def test_history_recording_and_retrieval():
    """History recording and retrieval."""
    history = VerificationHistory()
    v1 = Verification(verification_id="v1", task_id="task_1", status=VerificationStatus.PASSED)
    v2 = Verification(verification_id="v2", task_id="task_1", status=VerificationStatus.FAILED)
    v3 = Verification(verification_id="v3", task_id="task_2", status=VerificationStatus.RUNNING)
    
    history.record(v1)
    history.record(v2)
    history.record(v3)
    
    # Retrieval by ID
    assert history.get_verification("v1") == v1
    assert history.get_verification("v2") == v2
    
    # Retrieval by Task
    task1_history = history.get_history("task_1")
    assert len(task1_history) == 2
    assert v1 in task1_history
    assert v2 in task1_history
    
    task2_history = history.get_history("task_2")
    assert len(task2_history) == 1
    assert v3 in task2_history

def test_history_idempotent_recording():
    """Recording the same verification again shouldn't duplicate in history list."""
    history = VerificationHistory()
    v = Verification(verification_id="v1", task_id="task_1", status=VerificationStatus.PENDING)
    history.record(v)
    v.status = VerificationStatus.RUNNING
    history.record(v)
    
    task_hist = history.get_history("task_1")
    assert len(task_hist) == 1


# =============================================================================
# ENGINE ORCHESTRATION TESTS
# =============================================================================

def test_engine_orchestration_lifecycle():
    """VerificationEngine orchestration: creation, start, submit, evaluate, history."""
    engine = VerificationEngine()
    criteria = [VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT)]
    
    # Creation
    v = engine.create_verification("v1", "task_1", criteria)
    assert v.status == VerificationStatus.PENDING
    assert engine.get_verification("v1") == v
    assert engine.get_history("task_1")[0] == v
    
    # Start
    engine.start_verification("v1")
    assert v.status == VerificationStatus.RUNNING
    
    # Submit
    tr = VerificationTestResult("t1", "e1", VerificationTestStatus.PASSED, 0)
    engine.submit_criterion_result("v1", "c1", test_result=tr)
    
    # Evaluate
    v_eval = engine.evaluate_verification("v1")
    assert v_eval.status == VerificationStatus.PASSED
    
    # History still intact
    assert engine.get_verification("v1").status == VerificationStatus.PASSED

def test_engine_retry_orchestration():
    """VerificationEngine handles retry creation via history propagation."""
    engine = VerificationEngine(max_retries=2)
    criteria = [VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT)]
    
    engine.create_verification("v1", "task_1", criteria)
    engine.start_verification("v1")
    engine.submit_criterion_result("v1", "c1", test_result=VerificationTestResult("t1", "e1", VerificationTestStatus.FAILED, 1))
    engine.evaluate_verification("v1")
    
    retry = engine.create_retry("v1")
    assert retry.attempt_number == 2
    assert retry.verification_id == "v1_retry1"
    assert len(engine.get_history("task_1")) == 2

def test_engine_timeout_orchestration():
    engine = VerificationEngine()
    criteria = [VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT)]
    engine.create_verification("v1", "task_1", criteria)
    engine.start_verification("v1")
    
    v = engine.timeout_verification("v1")
    assert v.status == VerificationStatus.FAILED
    assert v.failure_category == FailureCategory.TIMEOUT
    
def test_engine_cancel_orchestration():
    engine = VerificationEngine()
    criteria = [VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT)]
    engine.create_verification("v1", "task_1", criteria)
    
    v = engine.cancel_verification("v1")
    assert v.status == VerificationStatus.CANCELLED


# =============================================================================
# ARCHITECTURAL BOUNDARY & SECURITY TESTS
# =============================================================================

def test_verification_boundary_isolation():
    """Verification boundary isolation and bypass impossibility.
    
    Verification -> Permission bypass       = impossible
    Verification -> Tool bypass             = impossible
    Verification -> Model provider coupling = impossible
    Verification -> Workflow ownership      = impossible
    Verification -> Execution ownership     = impossible
    Verification -> Interaction ownership   = impossible
    """
    engine = VerificationEngine()
    
    # Check that engine instances have NO references to privileged components
    assert not hasattr(engine, "_tool_executor")
    assert not hasattr(engine, "_permission_engine")
    assert not hasattr(engine, "_model_gateway")
    assert not hasattr(engine, "_workflow_manager")
    assert not hasattr(engine, "_execution_manager")
    assert not hasattr(engine, "_interaction_controller")
    
    # Evaluator should be pure logic
    assert not hasattr(engine._evaluator, "_tool_executor")
    
    # History should be pure data
    assert not hasattr(engine._history, "_tool_executor")


# =============================================================================
# ADDITIONAL AC & EDGE CASE TESTS
# =============================================================================

def test_context_integration():
    """AC-019: Verification results can become engineering Context (§39)."""
    engine = VerificationEngine()
    v = engine.create_verification("v1", "task_1", [
        VerificationCriterion(id="c1", description="Unit", test_type=VerificationTestType.UNIT),
        VerificationCriterion(id="c2", description="Build", test_type=VerificationTestType.BUILD),
    ])
    engine.start_verification("v1")
    engine.submit_criterion_result("v1", "c1", test_result=VerificationTestResult("t1", "e1", VerificationTestStatus.PASSED, 0))
    engine.submit_criterion_result("v1", "c2", test_result=VerificationTestResult("t2", "e1", VerificationTestStatus.FAILED, 1))
    engine.evaluate_verification("v1")

    ctx = engine.to_context("v1")
    assert ctx["verification_id"] == "v1"
    assert ctx["status"] == "failed"
    assert ctx["passed_count"] == 1
    assert ctx["failed_count"] == 1
    assert ctx["criteria_count"] == 2

def test_evidence_reproducibility():
    """AC-024: Evidence preserves enough info to reproduce the check (§48)."""
    evidence = Evidence(
        command="pytest tests/ -v",
        exit_code=0,
        output="10 passed",
        working_directory="/home/dev/project",
        environment_info={"python": "3.14", "os": "linux"},
        timestamp=datetime.now(timezone.utc),
    )
    assert evidence.command is not None
    assert evidence.working_directory is not None
    assert evidence.environment_info is not None

def test_tool_failure_distinct_from_test_failure():
    """AC-014 / §33: Tool failure (command not found) ≠ test failure."""
    evaluator = VerificationResultEvaluator()
    v = Verification(verification_id="v1", task_id="t1", criteria=[
        VerificationCriterion(id="c1", description="Tests", test_type=VerificationTestType.UNIT)
    ])
    v.status = VerificationStatus.RUNNING
    
    tr = VerificationTestResult("t1", "e1", VerificationTestStatus.FAILED, exit_code=127, error="command not found")
    cr = evaluator.submit_criterion_result(v, "c1", test_result=tr)
    assert cr.failure_category == FailureCategory.TOOL_FAILURE

def test_lifecycle_errors():
    """Test exceptions for invalid state transitions."""
    engine = VerificationEngine()
    criteria = [VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT)]
    engine.create_verification("v1", "task_1", criteria)
    
    # Cannot evaluate pending
    with pytest.raises(ValueError):
        engine.evaluate_verification("v1")
        
    # Cannot timeout pending
    with pytest.raises(ValueError):
        engine.timeout_verification("v1")
        
    engine.start_verification("v1")
    
    # Cannot start running
    with pytest.raises(ValueError):
        engine.start_verification("v1")


# =============================================================================
# ENGINE EXECUTE_VERIFICATION INTEGRATION TESTS
# =============================================================================

class TrackingRunner(VerificationRunner):
    """A runner that tracks what was invoked."""
    def __init__(self, result_mapping):
        self.result_mapping = result_mapping
        self.invoked_criteria = []
        
    def run(self, criterion: VerificationCriterion, execution_id: str) -> Tuple[Optional[VerificationTestResult], Optional[Evidence]]:
        self.invoked_criteria.append(criterion.id)
        if criterion.id in self.result_mapping:
            if isinstance(self.result_mapping[criterion.id], Exception):
                raise self.result_mapping[criterion.id]
            return self.result_mapping[criterion.id]
        return None, None

def test_execute_verification_full_lifecycle():
    """Verify Engine coordinates Runner -> Evaluator -> History."""
    tr = VerificationTestResult("t1", "e1", VerificationTestStatus.PASSED, 0)
    runner = TrackingRunner({"c1": (tr, None)})
    
    engine = VerificationEngine(runner=runner)
    criteria = [VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT)]
    
    # 1. Create and start
    v = engine.create_verification("v1", "task_1", criteria)
    engine.start_verification("v1")
    
    # 2. Execute full lifecycle
    v_result = engine.execute_verification("v1")
    
    # 3. Assertions
    assert v_result.status == VerificationStatus.PASSED
    assert "c1" in runner.invoked_criteria  # Runner was invoked
    assert len(v_result.criterion_results) == 1  # Evaluator was invoked
    assert v_result.criterion_results[0].status == VerificationStatus.PASSED
    
    # History contains the final evaluated state
    history_v = engine.get_verification("v1")
    assert history_v.status == VerificationStatus.PASSED

def test_execute_verification_runner_failure():
    """Runner failure is represented correctly as TOOL_FAILURE."""
    runner = TrackingRunner({"c1": Exception("Crash")})
    engine = VerificationEngine(runner=runner)
    
    criteria = [VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT, required=True)]
    engine.create_verification("v1", "task_1", criteria)
    engine.start_verification("v1")
    
    v = engine.execute_verification("v1")
    
    assert v.status == VerificationStatus.FAILED
    assert v.failure_category == FailureCategory.TOOL_FAILURE

def test_execute_verification_blocked_dependencies():
    """Evaluator BLOCKED result is preserved through execution and blocks runner invocation."""
    tr_fail = VerificationTestResult("t1", "e1", VerificationTestStatus.FAILED, 1)
    runner = TrackingRunner({
        "c1": (tr_fail, None),
        "c2": (None, None) # Will be blocked anyway
    })
    engine = VerificationEngine(runner=runner)
    
    criteria = [
        VerificationCriterion(id="c1", description="Dep", test_type=VerificationTestType.UNIT),
        VerificationCriterion(id="c2", description="Test", test_type=VerificationTestType.UNIT, dependencies=["c1"])
    ]
    engine.create_verification("v1", "task_1", criteria)
    engine.start_verification("v1")
    
    v = engine.execute_verification("v1")
    
    # Since c1 fails, c2 becomes blocked before runner invocation.
    assert "c1" in runner.invoked_criteria
    assert "c2" not in runner.invoked_criteria # Runner MUST NOT be invoked for blocked criteria
    
    c2_result = [cr for cr in v.criterion_results if cr.criterion_id == "c2"][0]
    assert c2_result.status == VerificationStatus.BLOCKED
    assert c2_result.failure_category == FailureCategory.DEPENDENCY_FAILURE

def test_execute_verification_evaluator_failure():
    """Evaluator exception is NOT converted into TOOL_FAILURE and is not silently swallowed."""
    
    # A runner that returns valid results
    tr = VerificationTestResult("t1", "e1", VerificationTestStatus.PASSED, 0)
    runner = TrackingRunner({"c1": (tr, None)})
    
    # An evaluator that raises an exception
    class CrashingEvaluator(VerificationResultEvaluator):
        def submit_criterion_result(self, *args, **kwargs):
            raise ValueError("Evaluator crash")
            
    evaluator = CrashingEvaluator()
    engine = VerificationEngine(runner=runner, evaluator=evaluator)
    
    criteria = [VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT, required=True)]
    engine.create_verification("v1", "task_1", criteria)
    engine.start_verification("v1")
    
    with pytest.raises(ValueError, match="Evaluator crash"):
        engine.execute_verification("v1")

def test_execute_verification_requires_runner():
    """Engine must have a runner to execute verification."""
    engine = VerificationEngine() # No runner
    criteria = [VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT)]
    engine.create_verification("v1", "task_1", criteria)
    engine.start_verification("v1")
    
    with pytest.raises(RuntimeError, match="VerificationRunner is required"):
        engine.execute_verification("v1")


# =============================================================================
# ROUND-TRIP SERIALIZATION TESTS (Correction #7)
# =============================================================================

def test_criterion_roundtrip():
    """VerificationCriterion survives serialization round-trip."""
    from clairecoder.verification.history import _serialize_criterion, _deserialize_criterion
    
    original = VerificationCriterion(
        id="c1",
        description="Unit tests pass",
        test_type=VerificationTestType.UNIT,
        required=True,
        command="pytest tests/",
        expected_result="0 failures",
        dependencies=["c0"],
    )
    serialized = _serialize_criterion(original)
    restored = _deserialize_criterion(serialized)
    
    assert restored.id == original.id
    assert restored.description == original.description
    assert restored.test_type == original.test_type
    assert restored.required == original.required
    assert restored.command == original.command
    assert restored.expected_result == original.expected_result
    assert restored.dependencies == original.dependencies


def test_evidence_roundtrip():
    """Evidence survives serialization round-trip."""
    from clairecoder.verification.history import _serialize_evidence, _deserialize_evidence
    
    ts = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)
    original = Evidence(
        command="pytest -v",
        exit_code=0,
        output="10 passed",
        error=None,
        working_directory="/project",
        environment_info={"python": "3.14", "os": "linux"},
        timestamp=ts,
        summary="All tests passed",
    )
    serialized = _serialize_evidence(original)
    restored = _deserialize_evidence(serialized)
    
    assert restored.command == original.command
    assert restored.exit_code == original.exit_code
    assert restored.output == original.output
    assert restored.error == original.error
    assert restored.working_directory == original.working_directory
    assert restored.environment_info == original.environment_info
    assert restored.timestamp == original.timestamp
    assert restored.summary == original.summary


def test_test_result_roundtrip():
    """VerificationTestResult survives serialization round-trip."""
    from clairecoder.verification.history import _serialize_test_result, _deserialize_test_result
    
    original = VerificationTestResult(
        test_id="t1",
        execution_id="exec_1",
        status=VerificationTestStatus.FAILED,
        exit_code=1,
        output="FAILED: test_foo",
        error="AssertionError",
        duration=3.5,
    )
    serialized = _serialize_test_result(original)
    restored = _deserialize_test_result(serialized)
    
    assert restored.test_id == original.test_id
    assert restored.execution_id == original.execution_id
    assert restored.status == original.status
    assert restored.exit_code == original.exit_code
    assert restored.output == original.output
    assert restored.error == original.error
    assert restored.duration == original.duration


def test_criterion_result_roundtrip():
    """CriterionResult (with evidence and test_result) survives round-trip."""
    from clairecoder.verification.history import _serialize_criterion_result, _deserialize_criterion_result
    
    ev = Evidence(command="pytest", exit_code=1, output="1 failed")
    tr = VerificationTestResult("t1", "e1", VerificationTestStatus.FAILED, exit_code=1, error="fail")
    
    original = CriterionResult(
        criterion_id="c1",
        status=VerificationStatus.FAILED,
        failure_category=FailureCategory.TEST_FAILURE,
        evidence=ev,
        test_result=tr,
    )
    serialized = _serialize_criterion_result(original)
    restored = _deserialize_criterion_result(serialized)
    
    assert restored.criterion_id == original.criterion_id
    assert restored.status == original.status
    assert restored.failure_category == original.failure_category
    assert restored.evidence.command == ev.command
    assert restored.evidence.exit_code == ev.exit_code
    assert restored.test_result.test_id == tr.test_id
    assert restored.test_result.status == tr.status


def test_criterion_result_roundtrip_no_evidence():
    """CriterionResult without evidence or test_result survives round-trip."""
    from clairecoder.verification.history import _serialize_criterion_result, _deserialize_criterion_result
    
    original = CriterionResult(
        criterion_id="c1",
        status=VerificationStatus.BLOCKED,
        failure_category=FailureCategory.DEPENDENCY_FAILURE,
    )
    serialized = _serialize_criterion_result(original)
    restored = _deserialize_criterion_result(serialized)
    
    assert restored.criterion_id == original.criterion_id
    assert restored.status == original.status
    assert restored.failure_category == original.failure_category
    assert restored.evidence is None
    assert restored.test_result is None


def test_verification_status_roundtrip():
    """Verification status survives round-trip for all terminal states."""
    from clairecoder.verification.history import _serialize_verification, _deserialize_verification
    
    for status in [VerificationStatus.PASSED, VerificationStatus.FAILED, VerificationStatus.BLOCKED, VerificationStatus.CANCELLED]:
        v = Verification(
            verification_id=f"v_{status.value}",
            task_id="t1",
            status=status,
        )
        serialized = _serialize_verification(v)
        restored = _deserialize_verification(serialized)
        assert restored.status == status


def test_verification_timestamp_roundtrip():
    """Verification timestamps survive round-trip."""
    from clairecoder.verification.history import _serialize_verification, _deserialize_verification
    
    started = datetime(2026, 8, 14, 10, 0, 0, tzinfo=timezone.utc)
    completed = datetime(2026, 8, 14, 10, 5, 0, tzinfo=timezone.utc)
    
    v = Verification(
        verification_id="v1",
        task_id="t1",
        status=VerificationStatus.PASSED,
        started_at=started,
        completed_at=completed,
    )
    serialized = _serialize_verification(v)
    restored = _deserialize_verification(serialized)
    
    assert restored.started_at == started
    assert restored.completed_at == completed


def test_complete_verification_roundtrip():
    """A fully-populated Verification survives complete round-trip."""
    from clairecoder.verification.history import _serialize_verification, _deserialize_verification
    
    criteria = [
        VerificationCriterion(id="c1", description="Build", test_type=VerificationTestType.BUILD, required=True),
        VerificationCriterion(id="c2", description="Unit", test_type=VerificationTestType.UNIT, required=True, dependencies=["c1"]),
    ]
    ev1 = Evidence(command="make build", exit_code=0, output="OK")
    ev2 = Evidence(command="pytest", exit_code=0, output="5 passed")
    tr1 = VerificationTestResult("t1", "e1", VerificationTestStatus.PASSED, exit_code=0)
    tr2 = VerificationTestResult("t2", "e1", VerificationTestStatus.PASSED, exit_code=0)
    cr1 = CriterionResult(criterion_id="c1", status=VerificationStatus.PASSED, evidence=ev1, test_result=tr1)
    cr2 = CriterionResult(criterion_id="c2", status=VerificationStatus.PASSED, evidence=ev2, test_result=tr2)
    
    started = datetime(2026, 8, 14, 10, 0, 0, tzinfo=timezone.utc)
    completed = datetime(2026, 8, 14, 10, 1, 0, tzinfo=timezone.utc)
    
    original = Verification(
        verification_id="v_full",
        task_id="t1",
        execution_id="exec_1",
        criteria=criteria,
        status=VerificationStatus.PASSED,
        evidence=[ev1, ev2],
        criterion_results=[cr1, cr2],
        started_at=started,
        completed_at=completed,
        failure_category=None,
        attempt_number=2,
        max_retries=5,
    )
    
    serialized = _serialize_verification(original)
    restored = _deserialize_verification(serialized)
    
    assert restored.verification_id == original.verification_id
    assert restored.task_id == original.task_id
    assert restored.execution_id == original.execution_id
    assert restored.status == original.status
    assert restored.started_at == original.started_at
    assert restored.completed_at == original.completed_at
    assert restored.attempt_number == original.attempt_number
    assert restored.max_retries == original.max_retries
    assert restored.failure_category == original.failure_category
    
    # Criteria round-trip
    assert len(restored.criteria) == 2
    assert restored.criteria[0].id == "c1"
    assert restored.criteria[0].test_type == VerificationTestType.BUILD
    assert restored.criteria[1].id == "c2"
    assert restored.criteria[1].dependencies == ["c1"]
    
    # Evidence round-trip
    assert len(restored.evidence) == 2
    assert restored.evidence[0].command == "make build"
    assert restored.evidence[1].output == "5 passed"
    
    # Criterion results round-trip
    assert len(restored.criterion_results) == 2
    assert restored.criterion_results[0].criterion_id == "c1"
    assert restored.criterion_results[0].status == VerificationStatus.PASSED
    assert restored.criterion_results[0].test_result.test_id == "t1"
    assert restored.criterion_results[1].criterion_id == "c2"
    assert restored.criterion_results[1].evidence.command == "pytest"


def test_verification_history_complete_roundtrip():
    """Complete VerificationHistory round-trip with multiple verifications."""
    history = VerificationHistory()
    
    c1 = VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT)
    ev = Evidence(command="pytest", exit_code=0)
    tr = VerificationTestResult("t1", "e1", VerificationTestStatus.PASSED, 0)
    cr = CriterionResult(criterion_id="c1", status=VerificationStatus.PASSED, evidence=ev, test_result=tr)
    
    v1 = Verification(
        verification_id="v1",
        task_id="task_1",
        criteria=[c1],
        status=VerificationStatus.PASSED,
        evidence=[ev],
        criterion_results=[cr],
    )
    v2 = Verification(
        verification_id="v2",
        task_id="task_1",
        status=VerificationStatus.FAILED,
        failure_category=FailureCategory.TEST_FAILURE,
    )
    v3 = Verification(
        verification_id="v3",
        task_id="task_2",
        status=VerificationStatus.BLOCKED,
    )
    
    history.record(v1)
    history.record(v2)
    history.record(v3)
    
    serialized = history.to_dict()
    restored_history = VerificationHistory.from_dict(serialized)
    
    # All verifications survive
    assert restored_history.get_verification("v1") is not None
    assert restored_history.get_verification("v2") is not None
    assert restored_history.get_verification("v3") is not None
    
    # Task history index survives
    assert len(restored_history.get_history("task_1")) == 2
    assert len(restored_history.get_history("task_2")) == 1
    
    # Deep state survives
    rv1 = restored_history.get_verification("v1")
    assert rv1.status == VerificationStatus.PASSED
    assert len(rv1.criteria) == 1
    assert rv1.criteria[0].description == "Test"
    assert len(rv1.evidence) == 1
    assert rv1.evidence[0].command == "pytest"
    assert len(rv1.criterion_results) == 1
    assert rv1.criterion_results[0].test_result.status == VerificationTestStatus.PASSED
    
    rv2 = restored_history.get_verification("v2")
    assert rv2.failure_category == FailureCategory.TEST_FAILURE


def test_engine_serialization_roundtrip():
    """VerificationEngine to_dict / load_from_dict round-trip."""
    engine = VerificationEngine()
    criteria = [
        VerificationCriterion(id="c1", description="Test", test_type=VerificationTestType.UNIT),
    ]
    engine.create_verification("v1", "t1", criteria)
    engine.start_verification("v1")
    engine.submit_criterion_result(
        "v1", "c1",
        test_result=VerificationTestResult("t1", "e1", VerificationTestStatus.PASSED, 0),
        evidence=Evidence(command="pytest", exit_code=0, output="passed"),
    )
    engine.evaluate_verification("v1")
    
    serialized = engine.to_dict()
    
    engine2 = VerificationEngine()
    engine2.load_from_dict(serialized)
    
    rv1 = engine2.get_verification("v1")
    assert rv1 is not None
    assert rv1.status == VerificationStatus.PASSED
    assert len(rv1.criteria) == 1
    assert rv1.criteria[0].id == "c1"
    assert len(rv1.evidence) == 1
    assert rv1.evidence[0].command == "pytest"
    assert len(rv1.criterion_results) == 1
    assert rv1.criterion_results[0].status == VerificationStatus.PASSED


def test_malformed_verification_missing_required_field():
    """Malformed persisted Verification with missing required field is rejected."""
    from clairecoder.verification.history import _deserialize_verification
    
    # Missing verification_id
    with pytest.raises(ValueError, match="missing required field 'verification_id'"):
        _deserialize_verification({"task_id": "t1", "status": "passed"})
    
    # Missing task_id
    with pytest.raises(ValueError, match="missing required field 'task_id'"):
        _deserialize_verification({"verification_id": "v1", "status": "passed"})
    
    # Missing status
    with pytest.raises(ValueError, match="missing required field 'status'"):
        _deserialize_verification({"verification_id": "v1", "task_id": "t1"})


def test_malformed_verification_invalid_status():
    """Malformed persisted Verification with invalid status value is rejected."""
    from clairecoder.verification.history import _deserialize_verification
    
    with pytest.raises(ValueError):
        _deserialize_verification({
            "verification_id": "v1",
            "task_id": "t1",
            "status": "not_a_real_status",
        })


def test_malformed_history_from_dict():
    """VerificationHistory.from_dict rejects malformed records."""
    with pytest.raises(ValueError):
        VerificationHistory.from_dict({
            "verifications": {
                "v1": {"task_id": "t1", "status": "passed"}  # missing verification_id
            }
        })

