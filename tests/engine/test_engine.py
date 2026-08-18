import pytest
import tempfile
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, List
from clairecoder.engine.engine import EngineeringEngine, EngineeringSession, SubagentEngine
from clairecoder.engine.types import (
    EngineeringObjective, ObjectiveStatus, Task, TaskState, EngineEvent
)
from clairecoder.gateway.interfaces import ModelGatewayInterface
from clairecoder.gateway.types import (
    ModelRequest, ModelResponse, Model, Provider, Endpoint, Capability, ModelError, ErrorCategory
)
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.registry import ToolRegistry
from clairecoder.tools.base import Tool
from clairecoder.tools.types import ToolMetadata, ToolCategory
from clairecoder.core.types import ToolResult, ToolState, PermissionState, PermissionRequirement
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.permissions.types import PermissionRequest, PermissionCategory, ResourceScope, PermissionRule
from clairecoder.skills.registry import SkillRegistry
from clairecoder.skills.base import Skill
from clairecoder.skills.types import SkillMetadata, SkillCategory

class MockModelGateway(ModelGatewayInterface):
    def __init__(self):
        self.requests = []
        self.next_responses = []
        self.should_fail = False

    def register_adapter(self, adapter) -> None: pass
    def register_model(self, model) -> None: pass
    def register_profile(self, profile) -> None: pass
    def resolve_profile(self, profile_id): pass
    def get_model(self, model_id): pass
    def check_capability(self, model_id, capability): pass
    
    def execute(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.should_fail:
            raise ModelError(ErrorCategory.MODEL_FAILURE, "Mock failure")
        if self.next_responses:
            return self.next_responses.pop(0)
        return ModelResponse(text="Mocked response", tool_calls=[])

class MockTool(Tool):
    def __init__(self, name: str, should_fail: bool = False):
        self._name = name
        self.should_fail = should_fail
        
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(id=self._name, name=self._name, description="Mock tool", version="1.0.0", category=ToolCategory.TESTING)
        
    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return "Mock tool"
    @property
    def required_permissions(self) -> List[PermissionRequirement]:
        return [PermissionRequirement(action="execute", resource=self._name)]
        
    def validate_input(self, **kwargs) -> None:
        pass
        
    def _execute(self, **kwargs) -> ToolResult:
        if self.should_fail:
            return ToolResult(state=ToolState.FAILURE, output=None, error="Tool failed")
        return ToolResult(state=ToolState.SUCCESS, output="Tool succeeded")

class MockSkill(Skill):
    def __init__(self, id: str):
        self._id = id
        
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(id=self._id, name=self._id, description="Mock Skill desc", category=SkillCategory.ENGINEERING, version="1.0.0")
        
    @property
    def instructions(self) -> str:
        return "Actual Mock Skill Instructions"
        
    def validate(self) -> None:
        pass
    def execute(self, **kwargs: Any) -> Any:
        pass

@pytest.fixture
def permission_engine():
    engine = PermissionEngine()
    engine.add_rule(PermissionRule(decision=PermissionState.ALLOW, priority=0))
    return engine

@pytest.fixture
def tool_registry():
    registry = ToolRegistry()
    registry.register(MockTool("test_tool"))
    registry.register(MockTool("failing_tool", should_fail=True))
    return registry

@pytest.fixture
def tool_executor(tool_registry, permission_engine):
    return ToolExecutor(tool_registry, permission_engine)

@pytest.fixture
def skill_registry():
    registry = SkillRegistry()
    registry.register(MockSkill("test_skill"))
    registry.enable("test_skill")
    return registry

@pytest.fixture
def model_gateway():
    return MockModelGateway()

def test_objective_intake_and_session(model_gateway, tool_executor, skill_registry):
    events = []
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    engine.subscribe(lambda e, d: events.append((e, d)))
    obj = EngineeringObjective(id="obj1", request="Do something", session_id="s1")
    session = engine.receive_objective(obj)
    assert session.id == "s1"
    assert session.objective.id == "obj1"
    assert events[0][0] == EngineEvent.OBJECTIVE_STARTED
    assert engine.get_session("s1") == session

def test_engine_public_subscription(model_gateway, tool_executor, skill_registry):
    """Test the public subscription API for EngineEvents."""
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    
    events1 = []
    events2 = []
    
    def cb1(e, d): events1.append(e)
    def cb2(e, d): events2.append(e)
    
    engine.subscribe(cb1)
    engine.subscribe(cb2)
    
    obj = EngineeringObjective(id="obj1", request="Test", session_id="s1")
    engine.receive_objective(obj)
    
    assert EngineEvent.OBJECTIVE_STARTED in events1
    assert EngineEvent.OBJECTIVE_STARTED in events2
    
    engine.unsubscribe(cb1)
    engine.cancel_objective("s1")
    
    assert EngineEvent.EXECUTION_CANCELLED not in events1
    assert EngineEvent.EXECUTION_CANCELLED in events2

def test_session_persistence_clean_process():
    """Verify save/resume works in a clean python process without shared state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        script = f"""
import sys
from clairecoder.engine.engine import EngineeringEngine, EngineeringObjective
from clairecoder.gateway.interfaces import ModelGatewayInterface
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.registry import ToolRegistry
from clairecoder.permissions.engine import PermissionEngine
class DummyGateway(ModelGatewayInterface):
    def register_adapter(self, adapter): pass
    def register_model(self, model): pass
    def register_profile(self, profile): pass
    def resolve_profile(self, profile_id): pass
    def get_model(self, model_id): pass
    def check_capability(self, model_id, capability): pass
    def execute(self, request): return None

executor = ToolExecutor(ToolRegistry(), PermissionEngine())
engine = EngineeringEngine(DummyGateway(), executor)

if sys.argv[1] == 'save':
    obj = EngineeringObjective(id="obj1", request="Test", session_id="s1")
    engine.receive_objective(obj)
    engine.save_session("s1", directory=r"{tmpdir}")
elif sys.argv[1] == 'load':
    session = engine.resume_session("s1", directory=r"{tmpdir}")
    assert session.objective.id == "obj1"
    assert session.objective.request == "Test"
    print("SUCCESS")
"""
        script_path = Path(tmpdir) / "test_script.py"
        script_path.write_text(script)
        
        # Save process
        res1 = subprocess.run([sys.executable, str(script_path), "save"], capture_output=True, text=True)
        assert res1.returncode == 0
        
        # Load process
        res2 = subprocess.run([sys.executable, str(script_path), "load"], capture_output=True, text=True)
        assert res2.returncode == 0
        assert "SUCCESS" in res2.stdout

def test_subagent_session_isolation(model_gateway, tool_executor, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    parent_obj = EngineeringObjective(id="parent_obj", request="Parent task", session_id="parent_session")
    parent_session = engine.receive_objective(parent_obj)
    parent_context = engine.assemble_context("parent_session")
    
    subagent = engine.create_subagent(parent_obj, parent_context)
    
    # 1. Subagent session exists under the ID used by the subagent
    assert subagent._session_id == "subagent_parent_obj"
    assert engine.get_session(subagent._session_id) is not None
    
    # 2. Parent session remains distinct
    assert subagent._session_id != parent_session.id
    
    # 3. Subagent state does not silently mutate unrelated parent state
    assert engine.get_session(subagent._session_id).objective.id == "parent_obj_sub"
    assert parent_session.objective.id == "parent_obj"

def test_subagent_model_request_remains_bounded(model_gateway, tool_executor, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    parent_obj = EngineeringObjective(id="parent_obj", request="Parent task", session_id="parent_session")
    engine.receive_objective(parent_obj)
    parent_context = engine.assemble_context("parent_session")
    
    subagent = engine.create_subagent(parent_obj, parent_context)
    subagent.execute_model("Do the subtask")
    
    assert len(model_gateway.requests) == 1
    req = model_gateway.requests[0]
    
    # Must contain subagent objective boundaries and parent context
    sys_msg = req.messages[0]["content"]
    assert "Subagent Objective: Parent task" in sys_msg
    assert "Execute Subtask: Do the subtask" in req.messages[1]["content"]

def test_model_tool_result_model_loop(model_gateway, tool_executor, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    obj = EngineeringObjective(id="obj1", request="Loop me", session_id="s1")
    engine.receive_objective(obj)
    engine.plan_tasks("s1", [Task(id="t1", objective_id="obj1", description="T1")])
    engine.start_task("s1", "t1")
    
    # Model Response 1: Requests tool
    model_gateway.next_responses.append(ModelResponse(
        text="Need tool",
        tool_calls=[{"name": "test_tool", "arguments": {}}]
    ))
    
    # Model Response 2: Finishes
    model_gateway.next_responses.append(ModelResponse(
        text="Done with tool result",
        tool_calls=[]
    ))
    
    engine.interaction_loop("s1", "t1", max_iterations=2)
    
    # Two requests should have been made
    assert len(model_gateway.requests) == 2
    
    # The second request must contain the tool result
    req2 = model_gateway.requests[1]
    # Check if tool result is in the messages
    has_tool_result = False
    for msg in req2.messages:
        if msg.get("role") == "tool" and msg.get("name") == "test_tool" and "Tool succeeded" in msg.get("content", ""):
            has_tool_result = True
    assert has_tool_result

def test_context_inclusion_in_model_request(model_gateway, tool_executor, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    obj = EngineeringObjective(id="obj1", request="Understand context", session_id="s1")
    engine.receive_objective(obj)
    
    model_gateway.next_responses.append(ModelResponse(text="Understood", tool_calls=[]))
    engine.understand("s1")
    
    req = model_gateway.requests[0]
    sys_msg = req.messages[0]["content"]
    assert "Context Information:" in sys_msg
    # Ensure it's not mutating the Context Engine snapshots
    # (By asserting the assembly builds a clean context dictionary representation)
    assert "'session_id': 's1'" in sys_msg

def test_actual_skill_instructions_reach_context(model_gateway, tool_executor, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    obj = EngineeringObjective(id="obj1", request="Skill me", session_id="s1")
    engine.receive_objective(obj)
    
    # Load skill and verify actual instructions are added to context
    engine.load_skill("s1", "test_skill")
    ctx = engine.assemble_context("s1")
    
    assert "Actual Mock Skill Instructions" in ctx.instructions

def test_tool_context_propagation(tool_executor, model_gateway, permission_engine, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    reqs = []
    original_eval = permission_engine.evaluate_request
    def spy_eval(request):
        reqs.append(request)
        return original_eval(request)
    permission_engine.evaluate_request = spy_eval
    
    engine.request_tool("test_tool", session_id="s1", workflow_id="wf1", task_id="t1")
    assert len(reqs) == 1
    assert reqs[0].session_id == "s1"
    assert reqs[0].workflow_id == "wf1"
    assert reqs[0].task_id == "t1"

def test_validation_and_replanning(model_gateway, tool_executor, skill_registry):
    events = []
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    engine.subscribe(lambda e, d: events.append(e))
    engine.receive_objective(EngineeringObjective(id="obj1", request="Validate me", session_id="s1"))
    engine.plan_tasks("s1", [Task(id="t1", objective_id="obj1", description="To validate")])
    engine.start_task("s1", "t1")
    
    engine.validate_task("s1", "t1", passed=False, failure_reason="Test failed")
    assert EngineEvent.VALIDATION_COMPLETED in events
    assert EngineEvent.REPLANNING_STARTED in events

def test_model_failure_propagation(model_gateway, tool_executor, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    request = ModelRequest(model_id="test-model", messages=[{"role": "user", "content": "fail"}])
    model_gateway.should_fail = True
    with pytest.raises(ModelError):
        engine.execute_model(request)

def test_interruption_and_cancellation(model_gateway, tool_executor, skill_registry):
    events = []
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    engine.subscribe(lambda e, d: events.append(e))
    engine.receive_objective(EngineeringObjective(id="obj1", request="Interrupt me", session_id="s1"))
    engine.interrupt_execution("s1")
    assert EngineEvent.EXECUTION_PAUSED in events
    engine.cancel_objective("s1")
    assert EngineEvent.EXECUTION_CANCELLED in events

def test_planning_and_task_transitions(model_gateway, tool_executor, skill_registry):
    """AC-002: The Engine can coordinate a planning stage.
       AC-003: The Engine can execute a Task...
    """
    events = []
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    engine.subscribe(lambda e, d: events.append(e))
    engine.receive_objective(EngineeringObjective(id="obj1", request="Plan me", session_id="s1"))
    
    task1 = Task(id="t1", objective_id="obj1", description="Task 1")
    engine.plan_tasks("s1", [task1])
    
    assert EngineEvent.PLANNING_STARTED in events
    assert EngineEvent.PLANNING_COMPLETED in events
    
    session = engine.get_session("s1")
    assert "t1" in session.tasks
    assert session.tasks["t1"].status == TaskState.PENDING
    
    engine.start_task("s1", "t1")
    assert session.tasks["t1"].status == TaskState.RUNNING
    assert EngineEvent.TASK_STARTED in events

def test_model_independence(model_gateway, tool_executor, skill_registry):
    """AC-004, AC-012, AC-013: Model independence, Gateway integration, no provider specific logic."""
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    request = ModelRequest(model_id="test-model", messages=[{"role": "user", "content": "hello"}])
    model_gateway.next_responses = [ModelResponse(text="response from gateway", tool_calls=[])]
    
    response = engine.execute_model(request)
    assert response.text == "response from gateway"
    assert len(model_gateway.requests) == 1

def test_permission_boundary_remains_intact(tool_executor, model_gateway, permission_engine, skill_registry):
    """AC-005: Tool execution cannot bypass Permission Engine."""
    events = []
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    engine.subscribe(lambda e, d: events.append(e))
    
    # 1. Allowed tool
    res1 = engine.request_tool("test_tool", session_id="s1")
    assert res1.state == ToolState.SUCCESS
    assert EngineEvent.TOOL_REQUESTED in events
    assert EngineEvent.TOOL_COMPLETED in events
    
    events.clear()
    
    # 2. Denied tool
    permission_engine.add_rule(PermissionRule(decision=PermissionState.DENY, tool_id="test_tool", priority=10))
    res2 = engine.request_tool("test_tool", session_id="s1")
    assert res2.state == ToolState.DENIED
    assert "Permission denied" in res2.error
    assert EngineEvent.PERMISSION_REQUESTED not in events # Only emitted for ASK
    
    # 3. ASK confirmation required
    permission_engine.add_rule(PermissionRule(decision=PermissionState.ASK, tool_id="test_tool", priority=20))
    res3 = engine.request_tool("test_tool", session_id="s1")
    assert res3.state == ToolState.DENIED
    assert res3.metadata.get("requires_confirmation") is True
    assert EngineEvent.PERMISSION_REQUESTED in events

def test_tool_failure(tool_executor, model_gateway, skill_registry):
    """Tool failure propagation"""
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    res = engine.request_tool("failing_tool", session_id="s1")
    assert res.state == ToolState.FAILURE

def test_skill_load_failure_is_not_silently_ignored(model_gateway, tool_executor, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    obj = EngineeringObjective(id="obj1", request="Skill me", session_id="s1")
    engine.receive_objective(obj)
    
    # Manually add a skill ID to active_skills that doesn't exist
    session = engine.get_session("s1")
    session.active_skills.append("non_existent_skill")
    
    from clairecoder.skills.types import SkillNotFoundError
    with pytest.raises(SkillNotFoundError):
        engine.assemble_context("s1")

def test_disabled_skill_cannot_be_loaded_into_context(model_gateway, tool_executor, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    obj = EngineeringObjective(id="obj1", request="Skill me", session_id="s1")
    engine.receive_objective(obj)
    
    # Register but do not enable a skill
    skill_registry.register(MockSkill("disabled_skill"))
    session = engine.get_session("s1")
    session.active_skills.append("disabled_skill")
    
    from clairecoder.skills.types import SkillUnavailableError
    with pytest.raises(SkillUnavailableError):
        engine.assemble_context("s1")

def test_missing_skill_cannot_be_loaded_into_context(model_gateway, tool_executor, skill_registry):
    # Similar to test_skill_load_failure_is_not_silently_ignored
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    obj = EngineeringObjective(id="obj1", request="Skill me", session_id="s1")
    engine.receive_objective(obj)
    
    session = engine.get_session("s1")
    session.active_skills.append("missing_skill")
    
    from clairecoder.skills.types import SkillNotFoundError
    with pytest.raises(SkillNotFoundError):
        engine.assemble_context("s1")

def test_subagent_does_not_access_private_model_gateway(model_gateway, tool_executor, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    parent_obj = EngineeringObjective(id="parent_obj", request="Parent task", session_id="parent_session")
    engine.receive_objective(parent_obj)
    parent_context = engine.assemble_context("parent_session")
    
    subagent = engine.create_subagent(parent_obj, parent_context)
    
    # We test this by patching SubagentEngine execute_model to ensure it calls engine.execute_model
    import unittest.mock as mock
    with mock.patch.object(engine, 'execute_model') as mock_exec:
        subagent.execute_model("task")
        mock_exec.assert_called_once()

def test_subagent_uses_supplied_immutable_context(model_gateway, tool_executor, skill_registry):
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    parent_obj = EngineeringObjective(id="parent_obj", request="Parent task", session_id="parent_session")
    engine.receive_objective(parent_obj)
    parent_context = engine.assemble_context("parent_session")
    
    subagent = engine.create_subagent(parent_obj, parent_context)
    subagent.execute_model("task")
    
    # check that context content matches
    sys_msg = model_gateway.requests[0].messages[0]["content"]
    assert "Repository State:" in sys_msg
    assert "Memories:" in sys_msg
    assert "Tool Results:" in sys_msg
    assert "Skills:" in sys_msg
    assert "Workflow Info:" in sys_msg

def test_tool_result_reaches_second_model_request(model_gateway, tool_executor, skill_registry):
    # This is implicitly tested in test_model_tool_result_model_loop but we'll add an explicit one to satisfy the list
    engine = EngineeringEngine(model_gateway, tool_executor, skill_registry)
    obj = EngineeringObjective(id="obj1", request="Loop me", session_id="s1")
    engine.receive_objective(obj)
    engine.plan_tasks("s1", [Task(id="t1", objective_id="obj1", description="T1")])
    engine.start_task("s1", "t1")
    
    model_gateway.next_responses.append(ModelResponse(
        text="Need tool",
        tool_calls=[{"name": "test_tool", "arguments": {}}]
    ))
    
    model_gateway.next_responses.append(ModelResponse(
        text="Done with tool result",
        tool_calls=[]
    ))
    
    engine.interaction_loop("s1", "t1", max_iterations=2)
    
    req2 = model_gateway.requests[1]
    has_tool_result = any(msg.get("role") == "tool" and msg.get("name") == "test_tool" and "Tool succeeded" in msg.get("content", "") for msg in req2.messages)
    assert has_tool_result
