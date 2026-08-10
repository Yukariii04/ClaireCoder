"""Phase 8 tests — Workflow & Planning.

Tests cover CC-PRD-004 and CC-ADR-004 acceptance criteria:
  AC-001: Workflow representation
  AC-002: Tasks with state and dependencies
  AC-003: Workflow lifecycle state persistence/restoration
  AC-017: Current and superseded plans distinguished
  AC-023: Context assembly (workflow context)
"""

import pytest
from typing import Any, Dict, List, Optional

from clairecoder.workflow.types import (
    Workflow,
    WorkflowState,
    Plan,
    PlanningLevel,
    WorkflowError,
    WorkflowStateError,
    DependencyCycleError,
    DependencyNotFoundError,
    InvalidDependencyError,
    PlanningError,
)
from clairecoder.workflow.manager import WorkflowManager
from clairecoder.workflow.planner import Planner
from clairecoder.workflow.dependencies import (
    validate_dependencies,
    topological_order,
    get_ready_tasks,
)
from clairecoder.engine.types import (
    Task,
    TaskState,
    EngineeringObjective,
    EngineEvent,
)
from clairecoder.gateway.types import ModelRequest, ModelResponse


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def manager():
    return WorkflowManager()


@pytest.fixture
def planner():
    return Planner()


def _make_tasks(*specs):
    """Helper: create tasks from (id, deps) tuples."""
    tasks = []
    for spec in specs:
        if isinstance(spec, str):
            tasks.append(Task(id=spec, objective_id="obj1", description=f"Task {spec}"))
        else:
            tid, deps = spec
            tasks.append(
                Task(id=tid, objective_id="obj1", description=f"Task {tid}", dependencies=deps)
            )
    return tasks


# =============================================================================
# WORKFLOW CREATION  (AC-001)
# =============================================================================


class TestWorkflowCreation:
    def test_create_workflow(self, manager):
        wf = manager.create_workflow("wf1", "obj1", "Implement auth")
        assert wf.id == "wf1"
        assert wf.objective_id == "obj1"
        assert wf.state == WorkflowState.CREATED

    def test_create_workflow_with_criteria(self, manager):
        wf = manager.create_workflow(
            "wf1", "obj1", "Add API",
            completion_criteria=["tests pass"],
            validation_requirements=["lint clean"],
            relevant_skills=["api-skill"],
            relevant_tools=["terminal"],
        )
        assert wf.completion_criteria == ["tests pass"]
        assert wf.relevant_skills == ["api-skill"]

    def test_duplicate_workflow_rejected(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        with pytest.raises(WorkflowError):
            manager.create_workflow("wf1", "obj1", "another desc")

    def test_workflow_identity(self, manager):
        wf = manager.create_workflow("wf1", "obj1", "desc")
        assert manager.get_workflow("wf1") is wf
        assert manager.get_workflow("nonexistent") is None

    def test_workflow_planning_level_default(self, manager):
        wf = manager.create_workflow("wf1", "obj1", "desc")
        assert wf.planning_level == PlanningLevel.STRUCTURED

    def test_workflow_planning_level_custom(self, manager):
        wf = manager.create_workflow("wf1", "obj1", "desc", planning_level=PlanningLevel.DEEP)
        assert wf.planning_level == PlanningLevel.DEEP


# =============================================================================
# WORKFLOW STATE  (AC-003)
# =============================================================================


class TestWorkflowState:
    def test_valid_transitions(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")

        manager.transition_state("wf1", WorkflowState.PLANNED)
        assert manager.get_workflow("wf1").state == WorkflowState.PLANNED

        manager.transition_state("wf1", WorkflowState.ACTIVE)
        assert manager.get_workflow("wf1").state == WorkflowState.ACTIVE

        manager.transition_state("wf1", WorkflowState.VALIDATING)
        assert manager.get_workflow("wf1").state == WorkflowState.VALIDATING

        manager.transition_state("wf1", WorkflowState.COMPLETE)
        assert manager.get_workflow("wf1").state == WorkflowState.COMPLETE

    def test_invalid_transition_rejected(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        with pytest.raises(WorkflowStateError):
            manager.transition_state("wf1", WorkflowState.ACTIVE)  # CREATED → ACTIVE invalid

    def test_complete_is_terminal(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        manager.transition_state("wf1", WorkflowState.PLANNED)
        manager.transition_state("wf1", WorkflowState.ACTIVE)
        manager.transition_state("wf1", WorkflowState.VALIDATING)
        manager.transition_state("wf1", WorkflowState.COMPLETE)
        with pytest.raises(WorkflowStateError):
            manager.transition_state("wf1", WorkflowState.ACTIVE)

    def test_cancelled_is_terminal(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        manager.transition_state("wf1", WorkflowState.CANCELLED)
        with pytest.raises(WorkflowStateError):
            manager.transition_state("wf1", WorkflowState.ACTIVE)

    def test_failed_to_replanning(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        manager.transition_state("wf1", WorkflowState.PLANNED)
        manager.transition_state("wf1", WorkflowState.ACTIVE)
        manager.transition_state("wf1", WorkflowState.FAILED)
        manager.transition_state("wf1", WorkflowState.REPLANNING)
        assert manager.get_workflow("wf1").state == WorkflowState.REPLANNING

    def test_replanning_back_to_planned(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        manager.transition_state("wf1", WorkflowState.PLANNED)
        manager.transition_state("wf1", WorkflowState.ACTIVE)
        manager.transition_state("wf1", WorkflowState.FAILED)
        manager.transition_state("wf1", WorkflowState.REPLANNING)
        manager.transition_state("wf1", WorkflowState.PLANNED)
        assert manager.get_workflow("wf1").state == WorkflowState.PLANNED

    def test_paused_resume(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        manager.transition_state("wf1", WorkflowState.PLANNED)
        manager.transition_state("wf1", WorkflowState.ACTIVE)
        manager.transition_state("wf1", WorkflowState.PAUSED)
        manager.transition_state("wf1", WorkflowState.ACTIVE)
        assert manager.get_workflow("wf1").state == WorkflowState.ACTIVE

    def test_nonexistent_workflow_transition(self, manager):
        with pytest.raises(WorkflowError):
            manager.transition_state("nonexistent", WorkflowState.ACTIVE)


# =============================================================================
# TASK DEPENDENCIES  (AC-002)
# =============================================================================


class TestTaskDependencies:
    def test_valid_linear_dependencies(self):
        tasks = _make_tasks(
            ("t1", []),
            ("t2", ["t1"]),
            ("t3", ["t2"]),
        )
        validate_dependencies(tasks)  # Should not raise

    def test_valid_diamond_dependencies(self):
        tasks = _make_tasks(
            ("t1", []),
            ("t2", ["t1"]),
            ("t3", ["t1"]),
            ("t4", ["t2", "t3"]),
        )
        validate_dependencies(tasks)

    def test_no_dependencies(self):
        tasks = _make_tasks("t1", "t2", "t3")
        validate_dependencies(tasks)

    def test_missing_dependency_rejected(self):
        tasks = _make_tasks(("t1", ["nonexistent"]))
        with pytest.raises(DependencyNotFoundError):
            validate_dependencies(tasks)

    def test_self_dependency_rejected(self):
        tasks = _make_tasks(("t1", ["t1"]))
        with pytest.raises(InvalidDependencyError):
            validate_dependencies(tasks)

    def test_cycle_detected(self):
        tasks = _make_tasks(
            ("t1", ["t3"]),
            ("t2", ["t1"]),
            ("t3", ["t2"]),
        )
        with pytest.raises(DependencyCycleError):
            validate_dependencies(tasks)

    def test_two_node_cycle(self):
        tasks = _make_tasks(
            ("t1", ["t2"]),
            ("t2", ["t1"]),
        )
        with pytest.raises(DependencyCycleError):
            validate_dependencies(tasks)

    def test_topological_order_linear(self):
        tasks = _make_tasks(
            ("t1", []),
            ("t2", ["t1"]),
            ("t3", ["t2"]),
        )
        order = topological_order(tasks)
        assert order == ["t1", "t2", "t3"]

    def test_topological_order_diamond(self):
        tasks = _make_tasks(
            ("t1", []),
            ("t2", ["t1"]),
            ("t3", ["t1"]),
            ("t4", ["t2", "t3"]),
        )
        order = topological_order(tasks)
        assert order.index("t1") < order.index("t2")
        assert order.index("t1") < order.index("t3")
        assert order.index("t2") < order.index("t4")
        assert order.index("t3") < order.index("t4")

    def test_topological_order_independent(self):
        tasks = _make_tasks("t1", "t2", "t3")
        order = topological_order(tasks)
        assert set(order) == {"t1", "t2", "t3"}

    def test_ready_tasks_none_completed(self):
        tasks = _make_tasks(
            ("t1", []),
            ("t2", ["t1"]),
        )
        ready = get_ready_tasks(tasks)
        assert len(ready) == 1
        assert ready[0].id == "t1"

    def test_ready_tasks_after_completion(self):
        t1 = Task(id="t1", objective_id="obj1", description="T1", status=TaskState.COMPLETE)
        t2 = Task(id="t2", objective_id="obj1", description="T2", dependencies=["t1"])
        tasks = [t1, t2]
        ready = get_ready_tasks(tasks)
        assert len(ready) == 1
        assert ready[0].id == "t2"

    def test_ready_tasks_all_completed(self):
        t1 = Task(id="t1", objective_id="obj1", description="T1", status=TaskState.COMPLETE)
        t2 = Task(id="t2", objective_id="obj1", description="T2", status=TaskState.COMPLETE, dependencies=["t1"])
        tasks = [t1, t2]
        ready = get_ready_tasks(tasks)
        assert len(ready) == 0  # Nothing is PENDING

    def test_ready_tasks_blocked(self):
        t1 = Task(id="t1", objective_id="obj1", description="T1", status=TaskState.RUNNING)
        t2 = Task(id="t2", objective_id="obj1", description="T2", dependencies=["t1"])
        tasks = [t1, t2]
        ready = get_ready_tasks(tasks)
        assert len(ready) == 0  # t1 is RUNNING, not COMPLETE

    def test_manager_validates_dependencies(self, manager):
        tasks = _make_tasks(("t1", ["nonexistent"]))
        with pytest.raises(DependencyNotFoundError):
            manager.validate_task_dependencies(tasks)

    def test_manager_get_task_order(self, manager):
        tasks = _make_tasks(
            ("t1", []),
            ("t2", ["t1"]),
            ("t3", ["t2"]),
        )
        order = manager.get_task_order(tasks)
        assert order == ["t1", "t2", "t3"]

    def test_manager_get_ready_tasks(self, manager):
        tasks = _make_tasks(("t1", []), ("t2", ["t1"]))
        ready = manager.get_ready_tasks(tasks)
        assert len(ready) == 1
        assert ready[0].id == "t1"


# =============================================================================
# PLAN MANAGEMENT  (AC-017)
# =============================================================================


class TestPlanManagement:
    def test_add_plan(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        plan = Plan(id="p1", workflow_id="wf1", objective="Do it", planning_level=PlanningLevel.STRUCTURED)
        manager.add_plan(plan)
        assert manager.get_active_plan("wf1") is plan

    def test_plan_supersedes_previous(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        p1 = Plan(id="p1", workflow_id="wf1", objective="First", planning_level=PlanningLevel.STRUCTURED)
        manager.add_plan(p1)
        p2 = Plan(id="p2", workflow_id="wf1", objective="Second", planning_level=PlanningLevel.STRUCTURED)
        manager.add_plan(p2)

        assert p1.is_superseded is True
        assert p1.superseded_by == "p2"
        assert manager.get_active_plan("wf1") is p2

    def test_plan_history(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        p1 = Plan(id="p1", workflow_id="wf1", objective="First", planning_level=PlanningLevel.STRUCTURED)
        p2 = Plan(id="p2", workflow_id="wf1", objective="Second", planning_level=PlanningLevel.STRUCTURED)
        manager.add_plan(p1)
        manager.add_plan(p2)

        history = manager.get_plan_history("wf1")
        assert len(history) == 2
        assert history[0].id == "p1"
        assert history[1].id == "p2"

    def test_plan_syncs_task_ids_to_workflow(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        plan = Plan(
            id="p1", workflow_id="wf1", objective="X",
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1", "t2", "t3"],
        )
        manager.add_plan(plan)
        wf = manager.get_workflow("wf1")
        assert wf.task_ids == ["t1", "t2", "t3"]

    def test_add_plan_to_nonexistent_workflow_fails(self, manager):
        plan = Plan(id="p1", workflow_id="nonexistent", objective="X", planning_level=PlanningLevel.STRUCTURED)
        with pytest.raises(WorkflowError):
            manager.add_plan(plan)

    def test_no_active_plan_initially(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        assert manager.get_active_plan("wf1") is None

    def test_empty_plan_history(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        assert manager.get_plan_history("wf1") == []


# =============================================================================
# WORKFLOW COMPLETION  (CC-PRD-004 Section 10)
# =============================================================================


class TestWorkflowCompletion:
    def test_complete_when_all_tasks_done(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        tasks = [
            Task(id="t1", objective_id="obj1", description="T1", status=TaskState.COMPLETE),
            Task(id="t2", objective_id="obj1", description="T2", status=TaskState.COMPLETE),
        ]
        assert manager.check_completion("wf1", tasks) is True

    def test_incomplete_when_task_pending(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        tasks = [
            Task(id="t1", objective_id="obj1", description="T1", status=TaskState.COMPLETE),
            Task(id="t2", objective_id="obj1", description="T2", status=TaskState.PENDING),
        ]
        assert manager.check_completion("wf1", tasks) is False

    def test_incomplete_when_task_failed(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        tasks = [
            Task(id="t1", objective_id="obj1", description="T1", status=TaskState.FAILED),
        ]
        assert manager.check_completion("wf1", tasks) is False

    def test_nonexistent_workflow(self, manager):
        assert manager.check_completion("nonexistent", []) is False


# =============================================================================
# PLANNER  (CC-ADR-004 Section 6)
# =============================================================================


class TestPlanner:
    def test_create_minimal_plan(self, planner):
        plan = planner.create_plan("wf1", "Do it", PlanningLevel.DIRECT)
        assert plan.workflow_id == "wf1"
        assert plan.objective == "Do it"
        assert plan.planning_level == PlanningLevel.DIRECT

    def test_create_plan_from_structured_response(self, planner):
        response = ModelResponse(
            text="",
            tool_calls=[],
            structured_output={
                "assumptions": ["repo is clean"],
                "affected_areas": ["src/auth"],
                "task_ids": ["t1", "t2"],
                "dependencies": {"t2": ["t1"]},
                "validation_strategy": ["run tests"],
                "risks": ["breaking change"],
                "completion_criteria": ["tests pass"],
            },
        )
        plan = planner.create_plan("wf1", "Add auth", PlanningLevel.STRUCTURED, model_response=response)
        assert plan.assumptions == ["repo is clean"]
        assert plan.task_ids == ["t1", "t2"]
        assert plan.dependencies == {"t2": ["t1"]}
        assert plan.risks == ["breaking change"]

    def test_create_plan_from_text_json(self, planner):
        json_text = '{"assumptions": ["A"], "task_ids": ["t1"], "dependencies": {}, "validation_strategy": [], "risks": [], "affected_areas": [], "completion_criteria": []}'
        response = ModelResponse(text=json_text, tool_calls=[])
        plan = planner.create_plan("wf1", "Plan", PlanningLevel.LIGHTWEIGHT, model_response=response)
        assert plan.assumptions == ["A"]
        assert plan.task_ids == ["t1"]

    def test_create_plan_from_invalid_text(self, planner):
        response = ModelResponse(text="This is not JSON at all", tool_calls=[])
        plan = planner.create_plan("wf1", "Plan", PlanningLevel.DIRECT, model_response=response)
        # Falls back to minimal scaffold
        assert plan.task_ids == []

    def test_create_tasks_from_plan(self, planner):
        plan = Plan(
            id="p1", workflow_id="wf1", objective="X",
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1", "t2"],
            dependencies={"t2": ["t1"]},
        )
        tasks = planner.create_tasks_from_plan(plan, "obj1")
        assert len(tasks) == 2
        assert tasks[0].id == "t1"
        assert tasks[1].id == "t2"
        assert tasks[1].dependencies == ["t1"]
        assert all(t.objective_id == "obj1" for t in tasks)

    def test_build_planning_request(self, planner):
        req = planner.build_planning_request(
            "Add auth", PlanningLevel.STRUCTURED, "context summary"
        )
        assert isinstance(req, ModelRequest)
        assert "Structured planning" in req.messages[0]["content"]
        assert "Add auth" in req.messages[1]["content"]

    def test_build_replan_request(self, planner):
        prev_plan = Plan(
            id="p1", workflow_id="wf1", objective="X",
            planning_level=PlanningLevel.STRUCTURED,
            assumptions=["clean repo"],
            task_ids=["t1"],
            risks=["breakage"],
        )
        req = planner.build_replan_request(
            "Add auth", prev_plan, "tests failed", "context"
        )
        assert isinstance(req, ModelRequest)
        assert "REPLANNING" in req.messages[0]["content"]
        assert "tests failed" in req.messages[0]["content"]
        assert "clean repo" in req.messages[0]["content"]

    def test_planning_request_is_provider_agnostic(self, planner):
        req = planner.build_planning_request("obj", PlanningLevel.DEEP, "ctx")
        # Must not contain any provider-specific references
        full_text = str(req.messages)
        assert "openai" not in full_text.lower()
        assert "anthropic" not in full_text.lower()
        assert "gemini" not in full_text.lower()


# =============================================================================
# SERIALIZATION  (AC-003 — Workflow persistence/restoration)
# =============================================================================


class TestSerialization:
    def test_workflow_roundtrip(self, manager):
        manager.create_workflow("wf1", "obj1", "desc", planning_level=PlanningLevel.DEEP)
        plan = Plan(
            id="p1", workflow_id="wf1", objective="X",
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1", "t2"],
            dependencies={"t2": ["t1"]},
            assumptions=["clean"],
        )
        manager.add_plan(plan)
        manager.transition_state("wf1", WorkflowState.PLANNED)

        data = manager.workflow_to_dict("wf1")
        assert data is not None

        restored = WorkflowManager.workflow_from_dict(data)
        wf = restored.get_workflow("wf1")
        assert wf is not None
        assert wf.state == WorkflowState.PLANNED
        assert wf.planning_level == PlanningLevel.DEEP

        active_plan = restored.get_active_plan("wf1")
        assert active_plan is not None
        assert active_plan.id == "p1"
        assert active_plan.task_ids == ["t1", "t2"]

    def test_serialize_nonexistent(self, manager):
        assert manager.workflow_to_dict("nonexistent") is None

    def test_plan_history_preserved_through_serialization(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        p1 = Plan(id="p1", workflow_id="wf1", objective="First", planning_level=PlanningLevel.LIGHTWEIGHT)
        p2 = Plan(id="p2", workflow_id="wf1", objective="Second", planning_level=PlanningLevel.STRUCTURED)
        manager.add_plan(p1)
        manager.add_plan(p2)

        data = manager.workflow_to_dict("wf1")
        restored = WorkflowManager.workflow_from_dict(data)
        history = restored.get_plan_history("wf1")
        assert len(history) == 2
        assert history[0].is_superseded is True
        assert history[1].is_superseded is False


# =============================================================================
# SESSION / WORKFLOW ISOLATION
# =============================================================================


class TestIsolation:
    def test_separate_workflows_independent(self, manager):
        manager.create_workflow("wf1", "obj1", "first")
        manager.create_workflow("wf2", "obj2", "second")

        manager.transition_state("wf1", WorkflowState.PLANNED)
        assert manager.get_workflow("wf2").state == WorkflowState.CREATED

    def test_plan_belongs_to_workflow(self, manager):
        manager.create_workflow("wf1", "obj1", "first")
        manager.create_workflow("wf2", "obj2", "second")

        plan = Plan(id="p1", workflow_id="wf1", objective="X", planning_level=PlanningLevel.STRUCTURED)
        manager.add_plan(plan)

        assert manager.get_active_plan("wf1") is plan
        assert manager.get_active_plan("wf2") is None


# =============================================================================
# CONTEXT INTEGRATION
# =============================================================================


class TestContextIntegration:
    def test_workflow_provides_context_info(self, manager):
        """Workflow data can be serialized for context assembly."""
        manager.create_workflow("wf1", "obj1", "Add auth", relevant_skills=["auth-skill"])
        plan = Plan(
            id="p1", workflow_id="wf1", objective="Add auth",
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1"],
        )
        manager.add_plan(plan)

        data = manager.workflow_to_dict("wf1")
        # Context builder can use this data
        assert data["relevant_skills"] == ["auth-skill"]
        assert data["plans"][0]["task_ids"] == ["t1"]


# =============================================================================
# BOUNDARY VALIDATION (Architectural audit)
# =============================================================================


class TestBoundaryValidation:
    """Verify that the workflow module does not violate architectural boundaries."""

    def test_workflow_does_not_import_tool_executor(self):
        import clairecoder.workflow.manager as mod
        source = open(mod.__file__).read()
        assert "ToolExecutor" not in source
        assert "Tool._execute" not in source

    def test_workflow_does_not_import_permission_engine(self):
        import clairecoder.workflow.manager as mod
        source = open(mod.__file__).read()
        # Check actual import lines, not docstring mentions
        import_lines = [line.strip() for line in source.splitlines()
                        if line.strip().startswith(("import ", "from "))]
        for line in import_lines:
            assert "PermissionEngine" not in line

    def test_workflow_does_not_import_provider_sdks(self):
        import clairecoder.workflow.planner as mod
        source = open(mod.__file__).read()
        assert "openai" not in source.lower()
        assert "anthropic" not in source.lower()
        assert "google" not in source.lower()

    def test_planner_does_not_import_model_gateway(self):
        """Planner builds requests but does not execute them."""
        import clairecoder.workflow.planner as mod
        source = open(mod.__file__).read()
        assert "ModelGatewayInterface" not in source
        assert "ModelGateway(" not in source

    def test_workflow_does_not_create_skill_registry(self):
        import clairecoder.workflow.manager as mod
        source = open(mod.__file__).read()
        assert "SkillRegistry()" not in source

    def test_workflow_does_not_mutate_engineering_context(self):
        import clairecoder.workflow.manager as mod
        source = open(mod.__file__).read()
        assert "EngineeringContext" not in source

    def test_no_phase_9_execution_state(self):
        """Workflow must not implement execution state machinery."""
        import clairecoder.workflow.types as mod
        source = open(mod.__file__).read()
        assert "checkpoint" not in source.lower()
        assert "recovery" not in source.lower()
        assert "retry_policy" not in source.lower()


# =============================================================================
# ADDITIONAL CORRECTIONS TESTING
# =============================================================================


class TestPlanDependencyValidation:
    def test_add_plan_rejects_missing_dependency(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        plan = Plan(
            id="p1", workflow_id="wf1", objective="X", planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1"],
            dependencies={"t1": ["nonexistent"]}
        )
        with pytest.raises(DependencyNotFoundError):
            manager.add_plan(plan)

    def test_add_plan_rejects_self_dependency(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        plan = Plan(
            id="p1", workflow_id="wf1", objective="X", planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1"],
            dependencies={"t1": ["t1"]}
        )
        with pytest.raises(InvalidDependencyError):
            manager.add_plan(plan)

    def test_add_plan_rejects_cycle(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        plan = Plan(
            id="p1", workflow_id="wf1", objective="X", planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1", "t2"],
            dependencies={"t1": ["t2"], "t2": ["t1"]}
        )
        with pytest.raises(DependencyCycleError):
            manager.add_plan(plan)

    def test_add_plan_rejects_unknown_dependency_key(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        plan = Plan(
            id="p1", workflow_id="wf1", objective="X", planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1"],
            dependencies={"unknown_key": ["t1"]}
        )
        with pytest.raises(InvalidDependencyError):
            manager.add_plan(plan)

    def test_invalid_plan_does_not_supersede_active_plan(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        valid_plan = Plan(
            id="p_valid", workflow_id="wf1", objective="Valid", planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1"], dependencies={"t1": []}
        )
        manager.add_plan(valid_plan)
        assert manager.get_active_plan("wf1").id == "p_valid"
        assert not manager.get_active_plan("wf1").is_superseded

        invalid_plan = Plan(
            id="p_invalid", workflow_id="wf1", objective="Invalid", planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t2"], dependencies={"t2": ["nonexistent"]}
        )
        with pytest.raises(DependencyNotFoundError):
            manager.add_plan(invalid_plan)
        
        # Valid plan remains active and is NOT superseded
        active = manager.get_active_plan("wf1")
        assert active.id == "p_valid"
        assert not active.is_superseded


class TestCompletionSemantics:
    def test_incomplete_task_leaves_workflow_incomplete(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        tasks = [
            Task(id="t1", objective_id="obj1", description="T1", status=TaskState.PENDING)
        ]
        assert not manager.check_completion("wf1", tasks)

    def test_failed_task_leaves_workflow_incomplete(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        tasks = [
            Task(id="t1", objective_id="obj1", description="T1", status=TaskState.FAILED)
        ]
        assert not manager.check_completion("wf1", tasks)

    def test_completed_tasks_with_unresolved_criteria_not_complete(self, manager):
        manager.create_workflow("wf1", "obj1", "desc", completion_criteria=["req1", "req2"])
        tasks = [
            Task(id="t1", objective_id="obj1", description="T1", status=TaskState.COMPLETE)
        ]
        # Providing only one criteria
        assert not manager.check_completion("wf1", tasks, satisfied_criteria=["req1"])

    def test_completed_tasks_with_satisfied_criteria_is_complete(self, manager):
        manager.create_workflow(
            "wf1", "obj1", "desc", 
            completion_criteria=["req1"], validation_requirements=["val1"]
        )
        tasks = [
            Task(id="t1", objective_id="obj1", description="T1", status=TaskState.COMPLETE)
        ]
        assert manager.check_completion("wf1", tasks, satisfied_criteria=["req1"], satisfied_validations=["val1"])


class TestPlannerValidation:
    def test_planner_rejects_missing_dependency(self, planner):
        response = ModelResponse(
            text="", tool_calls=[],
            structured_output={"task_ids": ["t1"], "dependencies": {"t1": ["missing"]}}
        )
        with pytest.raises(PlanningError, match="Invalid plan structure"):
            planner.create_plan("wf1", "obj1", PlanningLevel.STRUCTURED, model_response=response)

    def test_planner_rejects_unknown_key(self, planner):
        response = ModelResponse(
            text="", tool_calls=[],
            structured_output={"task_ids": ["t1"], "dependencies": {"unknown": ["t1"]}}
        )
        with pytest.raises(PlanningError, match="Invalid plan structure"):
            planner.create_plan("wf1", "obj1", PlanningLevel.STRUCTURED, model_response=response)

    def test_planner_rejects_self_dependency(self, planner):
        response = ModelResponse(
            text="", tool_calls=[],
            structured_output={"task_ids": ["t1"], "dependencies": {"t1": ["t1"]}}
        )
        with pytest.raises(PlanningError, match="Invalid plan structure"):
            planner.create_plan("wf1", "obj1", PlanningLevel.STRUCTURED, model_response=response)

    def test_planner_rejects_cycle(self, planner):
        response = ModelResponse(
            text="", tool_calls=[],
            structured_output={"task_ids": ["t1", "t2"], "dependencies": {"t1": ["t2"], "t2": ["t1"]}}
        )
        with pytest.raises(PlanningError, match="Invalid plan structure"):
            planner.create_plan("wf1", "obj1", PlanningLevel.STRUCTURED, model_response=response)

    def test_planner_rejects_malformed_type(self, planner):
        response = ModelResponse(
            text="", tool_calls=[],
            structured_output={"task_ids": "not_a_list"}
        )
        with pytest.raises(PlanningError, match="Invalid plan structure"):
            planner.create_plan("wf1", "obj1", PlanningLevel.STRUCTURED, model_response=response)

    def test_planner_rejects_non_mapping_structured_output(self, planner):
        invalid_outputs = [
            [],
            "invalid",
            123,
            None,
        ]
        for invalid_out in invalid_outputs:
            response = ModelResponse(text="", tool_calls=[], structured_output=invalid_out)
            with pytest.raises(PlanningError, match="Invalid plan structure from model: structured_output must be a mapping"):
                planner.create_plan("wf1", "obj1", PlanningLevel.STRUCTURED, model_response=response)

    def test_planner_accepts_valid_structured_plan(self, planner):
        response = ModelResponse(
            text="", tool_calls=[],
            structured_output={"task_ids": ["t1", "t2"], "dependencies": {"t2": ["t1"]}}
        )
        plan = planner.create_plan("wf1", "obj1", PlanningLevel.STRUCTURED, model_response=response)
        assert plan.task_ids == ["t1", "t2"]

    def test_invalid_json_text_fallback(self, planner):
        response = ModelResponse(text="not json text", tool_calls=[])
        plan = planner.create_plan("wf1", "obj1", PlanningLevel.STRUCTURED, model_response=response)
        # Invalid JSON falls back to minimal scaffold
        assert plan.task_ids == []

    def test_plan_rejects_duplicate_task_ids(self, planner, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        
        # Test planner boundary
        response = ModelResponse(
            text="", tool_calls=[],
            structured_output={"task_ids": ["task-a", "task-a"], "dependencies": {}}
        )
        with pytest.raises(PlanningError, match="Invalid plan structure"):
            planner.create_plan("wf1", "obj1", PlanningLevel.STRUCTURED, model_response=response)

        # Test manager boundary
        plan = Plan(
            id="p_dup", workflow_id="wf1", objective="Invalid", planning_level=PlanningLevel.STRUCTURED,
            task_ids=["task-b", "task-b"], dependencies={}
        )
        with pytest.raises(InvalidDependencyError, match="Duplicate task IDs"):
            manager.add_plan(plan)

    def test_duplicate_task_plan_does_not_supersede_active_plan(self, manager):
        manager.create_workflow("wf1", "obj1", "desc")
        valid_plan = Plan(
            id="p_valid", workflow_id="wf1", objective="Valid", planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1"], dependencies={}
        )
        manager.add_plan(valid_plan)
        
        active = manager.get_active_plan("wf1")
        assert active.id == "p_valid"
        assert not active.is_superseded

        invalid_plan = Plan(
            id="p_invalid", workflow_id="wf1", objective="Invalid", planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t2", "t2"], dependencies={}
        )
        with pytest.raises(InvalidDependencyError, match="Duplicate task IDs"):
            manager.add_plan(invalid_plan)
        
        active_after = manager.get_active_plan("wf1")
        assert active_after.id == "p_valid"
        assert not active_after.is_superseded
