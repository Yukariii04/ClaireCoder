import pytest
import os
import json
import tempfile
from clairecoder.app import ClaireCoderV1
from clairecoder.gateway.interfaces import ModelGatewayInterface
from clairecoder.gateway.types import ModelRequest, ModelResponse, ModelError, ErrorCategory
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.registry import ToolRegistry
from clairecoder.tools.base import Tool
from clairecoder.tools.types import ToolMetadata, ToolCategory
from clairecoder.core.types import ToolResult, ToolState, PermissionState, PermissionRequirement
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.permissions.types import PermissionRule, PermissionRequest, PermissionCategory, ResourceScope
from clairecoder.skills.registry import SkillRegistry
from clairecoder.skills.base import Skill
from clairecoder.skills.types import SkillMetadata, SkillCategory
from clairecoder.workflow.manager import WorkflowManager
from clairecoder.execution.manager import ExecutionManager
from clairecoder.execution.types import ExecutionResult, ExecutionResultCategory, FailureCategory
from clairecoder.verification.engine import VerificationEngine
from clairecoder.verification.runner import VerificationRunner
from clairecoder.verification.evaluator import VerificationResultEvaluator
from clairecoder.verification.types import VerificationCriterion, VerificationTestType, VerificationTestResult, VerificationTestStatus
from clairecoder.engine.types import ObjectiveStatus, TaskState

class MockModelGateway(ModelGatewayInterface):
    def __init__(self):
        self.requests = []
        self.next_responses = []

    def register_adapter(self, adapter) -> None: pass
    def register_model(self, model) -> None: pass
    def register_profile(self, profile) -> None: pass
    def resolve_profile(self, profile_id): pass
    def get_model(self, model_id): pass
    def check_capability(self, model_id, capability): pass
    
    def execute(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.next_responses:
            return self.next_responses.pop(0)
        return ModelResponse(text="Mocked response", tool_calls=[])

class MockTool(Tool):
    def __init__(self, name: str):
        self._name = name
        
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(id=self._name, name=self._name, description="Mock", version="1.0", category=ToolCategory.TESTING)
        
    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return "Mock tool"
    @property
    def required_permissions(self) -> list:
        return [PermissionRequirement(action="execute", resource=self._name)]
        
    def validate_input(self, **kwargs) -> None:
        pass
        
    def _execute(self, **kwargs) -> ToolResult:
        return ToolResult(state=ToolState.SUCCESS, output="Tool succeeded")

class MockSkill(Skill):
    def __init__(self, id: str):
        self._id = id
        
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(id=self._id, name=self._id, description="Mock Skill", category=SkillCategory.ENGINEERING, version="1.0")
        
    @property
    def instructions(self) -> str:
        return "Mock Skill Instructions"
        
    def validate(self) -> None: pass
    def execute(self, **kwargs) -> any: pass

class MockVerificationRunner(VerificationRunner):
    def run(self, criterion, execution_id):
        tr = VerificationTestResult(test_id=criterion.id, execution_id=execution_id, status=VerificationTestStatus.PASSED, exit_code=0)
        return tr, None

@pytest.fixture
def v1_app():
    gateway = MockModelGateway()
    
    perm_engine = PermissionEngine()
    perm_engine.add_rule(PermissionRule(decision=PermissionState.ALLOW, priority=0))
    
    tool_reg = ToolRegistry()
    tool_reg.register(MockTool("test_tool"))
    tool_exec = ToolExecutor(tool_reg, perm_engine)
    
    skill_reg = SkillRegistry()
    skill_reg.register(MockSkill("test_skill"))
    skill_reg.enable("test_skill")
    
    wf_mgr = WorkflowManager()
    exec_mgr = ExecutionManager()
    
    v_runner = MockVerificationRunner()
    v_engine = VerificationEngine(runner=v_runner)
    
    app = ClaireCoderV1(
        model_gateway=gateway,
        permission_engine=perm_engine,
        tool_executor=tool_exec,
        skill_registry=skill_reg,
        workflow_manager=wf_mgr,
        execution_manager=exec_mgr,
        verification_engine=v_engine
    )
    return app

def test_v1_startup_and_version(v1_app):
    assert v1_app.get_version() == "1.0.0"

def test_v1_session_creation(v1_app):
    session_id = v1_app.create_session("s1")
    assert session_id == "s1"
    status = v1_app.status("s1")
    assert status["id"] == "s1"

def test_v1_objective_submission(v1_app):
    v1_app.create_session("s1")
    res = v1_app.submit_objective("s1", "Fix the bug")
    assert "Objective accepted" in res
    
    status = v1_app.status("s1")
    assert status["objective"]["request"] == "Fix the bug"

def test_v1_interaction_commands(v1_app):
    res = v1_app.execute_command("help")
    assert res.success
    assert "Available commands" in res.message
    
    v1_app.create_session("s1")
    v1_app.pause("s1")
    # Verify command went through
    # (Checking engine events is harder from the outside, but we can verify success)

def test_v1_end_to_end_flow(v1_app):
    """Verifies Objective -> Plan -> Execute -> Verify -> Complete flow."""
    v1_app.create_session("s1")
    v1_app.submit_objective("s1", "Fix the authentication test")
    
    # Mock understand response
    v1_app.model_gateway.next_responses.append(
        ModelResponse(text="Understanding objective")
    )
    # Mock planning response
    v1_app.model_gateway.next_responses.append(
        ModelResponse(text="Understood", structured_output={"task_ids": ["t1"]})
    )
    # Mock execution response
    v1_app.model_gateway.next_responses.append(
        ModelResponse(text="Tool execution needed", tool_calls=[{"name": "test_tool", "arguments": {}}])
    )
    # Mock completion response
    v1_app.model_gateway.next_responses.append(
        ModelResponse(text="Task done", tool_calls=[])
    )
    
    v1_app.run("s1")
    
    status = v1_app.status("s1")
    # Task should have succeeded because Verification is mocked to PASSED
    assert len(status["tasks"]) > 0
    first_task = list(status["tasks"].values())[0]
    assert first_task["status"] == TaskState.SUCCEEDED.value
    
    assert status["objective"]["status"] == ObjectiveStatus.COMPLETED.value

def test_application_level_session_persistence_and_resumption(v1_app):
    """Tests save_session/resume_session through ClaireCoderV1 public API.
    
    Validates that verification criteria, evidence, criterion_results,
    and status all survive the round-trip per CC-PRD-009 §7.
    """
    session_id = "s_persist_1"
    v1_app.create_session(session_id)
    v1_app.submit_objective(session_id, "Persist me")
    
    v1_app.model_gateway.next_responses.append(ModelResponse(text="Understand"))
    v1_app.model_gateway.next_responses.append(ModelResponse(text="Plan", structured_output={"task_ids": ["t1"]}))
    
    # We want to run one cycle to get the plan and tasks created
    original_run = v1_app.engineering_engine.interaction_loop
    v1_app.engineering_engine.interaction_loop = lambda *args, **kwargs: ExecutionResult(category=ExecutionResultCategory.SUCCESS)
    
    # Mock task with validation to ensure verification engine creates history
    original_create = v1_app.planner.create_tasks_from_plan
    def mock_create(*args, **kwargs):
        tasks = original_create(*args, **kwargs)
        for t in tasks:
            t.validation_requirements = ["Require test"]
        return tasks
    v1_app.planner.create_tasks_from_plan = mock_create
    
    v1_app.run(session_id, max_cycles=1)
    
    # Capture original verification state BEFORE save
    original_v_history = v1_app.verification_engine.get_history("t1")
    assert len(original_v_history) > 0
    original_v = original_v_history[0]
    
    # Now save it!
    v1_app.save_session(session_id)
    
    app2 = ClaireCoderV1(
        model_gateway=MockModelGateway(),
        permission_engine=PermissionEngine(),
        tool_executor=ToolExecutor(ToolRegistry(), PermissionEngine()),
        skill_registry=SkillRegistry(),
        workflow_manager=WorkflowManager(),
        execution_manager=ExecutionManager(),
        verification_engine=VerificationEngine()
    )
    
    app2.resume_session(session_id)
    
    restored = app2.status(session_id)
    assert restored["id"] == session_id
    assert restored["objective"]["request"] == "Persist me"
    assert "t1" in restored["tasks"]
    
    # Execution state restored
    exec_task = app2.execution_manager.get_task("t1")
    assert exec_task is not None
    
    # Workflow state restored
    wf = app2.workflow_manager.get_workflow(f"wf_{session_id}")
    assert wf is not None
    assert wf.task_ids == ["t1"]
    
    # Verification history restored — deep state comparison
    restored_v_history = app2.verification_engine.get_history("t1")
    assert len(restored_v_history) > 0
    restored_v = restored_v_history[0]
    
    # Identity and status
    assert restored_v.verification_id == original_v.verification_id
    assert restored_v.task_id == original_v.task_id
    assert restored_v.status == original_v.status
    
    # Criteria survived
    assert len(restored_v.criteria) == len(original_v.criteria)
    for orig_c, rest_c in zip(original_v.criteria, restored_v.criteria):
        assert rest_c.id == orig_c.id
        assert rest_c.description == orig_c.description
        assert rest_c.test_type == orig_c.test_type
    
    # Evidence survived
    assert len(restored_v.evidence) == len(original_v.evidence)
    
    # Criterion results survived
    assert len(restored_v.criterion_results) == len(original_v.criterion_results)
    for orig_cr, rest_cr in zip(original_v.criterion_results, restored_v.criterion_results):
        assert rest_cr.criterion_id == orig_cr.criterion_id
        assert rest_cr.status == orig_cr.status
def test_v1_execution_failure_replanning_flow(v1_app):
    """Verifies execution failure -> execution failure state -> workflow replanning."""
    v1_app.create_session("s1")
    v1_app.submit_objective("s1", "Fail task")
    
    # Mock understand response
    v1_app.model_gateway.next_responses.append(
        ModelResponse(text="Understanding objective")
    )
    # Mock planning response
    v1_app.model_gateway.next_responses.append(
        ModelResponse(text="Understood", structured_output={"task_ids": ["t1"]})
    )
    # Mock replanning response
    v1_app.model_gateway.next_responses.append(
        ModelResponse(text="Replanned", structured_output={"task_ids": ["t1_retry"]})
    )
    
    # Mock interaction loop to fail on first call, succeed on second call
    call_count = {"count": 0}
    def mock_interaction_loop(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            return ExecutionResult(category=ExecutionResultCategory.FAILURE, failure_category=FailureCategory.TOOL_FAILURE, error_message="Execution failed")
        else:
            return ExecutionResult(category=ExecutionResultCategory.SUCCESS)
        
    v1_app.engineering_engine.interaction_loop = mock_interaction_loop
    
    v1_app.run("s1", max_cycles=10)
    
    status = v1_app.status("s1")
    assert len(status["tasks"]) == 2  # The original failed task, plus the replanned task
    tasks = list(status["tasks"].values())
    
    assert tasks[0]["status"] == "failed"
    assert tasks[1]["status"] == "succeeded"
    
    workflow_id = "wf_s1"
    wf = v1_app.workflow_manager.get_workflow(workflow_id)
    # The workflow should end up COMPLETE after the second task succeeds
    assert wf.state.value == "complete"
    
def test_v1_verification_failure_replanning_flow(v1_app):
    """Verifies execution success -> verification failure -> execution/workflow failure -> replanning."""
    v1_app.create_session("s2")
    v1_app.submit_objective("s2", "Verify failure")
    
    # Mock understand response
    v1_app.model_gateway.next_responses.append(
        ModelResponse(text="Understanding objective")
    )
    v1_app.model_gateway.next_responses.append(
        ModelResponse(text="Understood", structured_output={"task_ids": ["t2"]})
    )
    # Mock replanning response
    v1_app.model_gateway.next_responses.append(
        ModelResponse(text="Replanned", structured_output={"task_ids": ["t2_retry"]})
    )
    
    # Mock interaction loop to succeed execution
    def mock_interaction_loop(*args, **kwargs):
        return ExecutionResult(category=ExecutionResultCategory.SUCCESS)
        
    v1_app.engineering_engine.interaction_loop = mock_interaction_loop
    
    # Mock tasks to have validation requirements so Verification is run
    original_create = v1_app.planner.create_tasks_from_plan
    def mock_create(*args, **kwargs):
        tasks = original_create(*args, **kwargs)
        for t in tasks:
            t.validation_requirements = ["Require test"]
        return tasks
    v1_app.planner.create_tasks_from_plan = mock_create
    
    # Make VerificationRunner fail on first task, pass on second task
    class FailingVerificationRunner(VerificationRunner):
        def __init__(self):
            self.call_count = 0
            
        def run(self, criterion, execution_id):
            self.call_count += 1
            if self.call_count == 1:
                tr = VerificationTestResult(test_id=criterion.id, execution_id=execution_id, status=VerificationTestStatus.FAILED, error="Tests failed")
            else:
                tr = VerificationTestResult(test_id=criterion.id, execution_id=execution_id, status=VerificationTestStatus.PASSED)
            return tr, None
            
    v1_app.verification_engine._runner = FailingVerificationRunner()
    
    v1_app.run("s2", max_cycles=10)
    
    status = v1_app.status("s2")
    assert len(status["tasks"]) == 2
    tasks = list(status["tasks"].values())
    
    assert tasks[0]["status"] == "failed"
    assert tasks[1]["status"] == "succeeded"
    
    workflow_id = "wf_s2"
    wf = v1_app.workflow_manager.get_workflow(workflow_id)
    assert wf.state.value == "complete"
    
    # Check execution state failure category for the first task
    exec_task = v1_app.execution_manager.get_task(tasks[0]["id"])
    assert exec_task.status.value == "failed"
    assert exec_task.attempts[-1].result.failure_category.value == "validation_failure"


def test_task_validation_requirements_to_verification(v1_app):
    session_id = "s_val_1"
    v1_app.create_session(session_id)
    v1_app.submit_objective(session_id, "Test validations")
    v1_app.model_gateway.next_responses.append(ModelResponse(text="Understand"))
    v1_app.model_gateway.next_responses.append(ModelResponse(text="Plan", structured_output={"task_ids": ["t1"]}))
    
    v1_app.engineering_engine.interaction_loop = lambda *args, **kwargs: ExecutionResult(category=ExecutionResultCategory.SUCCESS)
    
    original_create = v1_app.planner.create_tasks_from_plan
    def mock_create(*args, **kwargs):
        tasks = original_create(*args, **kwargs)
        for t in tasks:
            t.validation_requirements = ["Rule A"]
        return tasks
    v1_app.planner.create_tasks_from_plan = mock_create
    
    v1_app.run(session_id)
    history = v1_app.verification_engine.get_history("t1")
    assert len(history) > 0
    verification = history[0]
    assert len(verification.criteria) == 1
    assert verification.criteria[0].description == "Rule A"
    
def test_multiple_task_validation_requirements(v1_app):
    session_id = "s_val_2"
    v1_app.create_session(session_id)
    v1_app.submit_objective(session_id, "Test multiple validations")
    v1_app.model_gateway.next_responses.append(ModelResponse(text="Understand"))
    v1_app.model_gateway.next_responses.append(ModelResponse(text="Plan", structured_output={"task_ids": ["t1"]}))
    
    v1_app.engineering_engine.interaction_loop = lambda *args, **kwargs: ExecutionResult(category=ExecutionResultCategory.SUCCESS)
    
    original_create = v1_app.planner.create_tasks_from_plan
    def mock_create(*args, **kwargs):
        tasks = original_create(*args, **kwargs)
        for t in tasks:
            t.validation_requirements = ["Rule X", "Rule Y"]
        return tasks
    v1_app.planner.create_tasks_from_plan = mock_create
    
    v1_app.run(session_id)
    history = v1_app.verification_engine.get_history("t1")
    assert len(history) > 0
    verification = history[0]
    assert len(verification.criteria) == 2
    descriptions = [c.description for c in verification.criteria]
    assert "Rule X" in descriptions
    assert "Rule Y" in descriptions

def test_plan_completion_criteria_propagation(v1_app):
    session_id = "s_plan_1"
    v1_app.create_session(session_id)
    v1_app.submit_objective(session_id, "Test propagation")
    v1_app.model_gateway.next_responses.append(ModelResponse(text="Understand"))
    
    # Inject plan completion criteria directly via mock ModelResponse
    structured = {
        "task_ids": ["t1"],
        "completion_criteria": ["Everything done"],
        "validation_strategy": ["Test everything"]
    }
    v1_app.model_gateway.next_responses.append(ModelResponse(text="Plan", structured_output=structured))
    
    v1_app.engineering_engine.interaction_loop = lambda *args, **kwargs: ExecutionResult(category=ExecutionResultCategory.SUCCESS)
    
    v1_app.run(session_id, max_cycles=1)
    
    wf = v1_app.workflow_manager.get_workflow(f"wf_{session_id}")
    assert "Everything done" in wf.completion_criteria
    assert "Test everything" in wf.validation_requirements

def test_completion_blocked_by_unsatisfied_criteria(v1_app):
    session_id = "s_plan_2"
    v1_app.create_session(session_id)
    v1_app.submit_objective(session_id, "Test blocked completion")
    v1_app.model_gateway.next_responses.append(ModelResponse(text="Understand"))
    
    structured = {
        "task_ids": ["t1"],
        "completion_criteria": ["Something that is never satisfied"],
    }
    v1_app.model_gateway.next_responses.append(ModelResponse(text="Plan", structured_output=structured))
    
    v1_app.engineering_engine.interaction_loop = lambda *args, **kwargs: ExecutionResult(category=ExecutionResultCategory.SUCCESS)
    
    v1_app.run(session_id, max_cycles=10)
    
    wf = v1_app.workflow_manager.get_workflow(f"wf_{session_id}")
    # Workflow should not be COMPLETE because the completion criteria was never met
    assert wf.state.value != "complete"
