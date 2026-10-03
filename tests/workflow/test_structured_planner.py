"""Tests for Correction #15 — Structured Planner.

Verifies:
1. Planning request contains structured_output_schema
2. Schema contains expected task fields and top-level fields
3. Valid structured response creates a Plan
4. Task metadata survives planner -> TaskGraph (and TaskGraph.from_plan(plan.tasks))
5. Duplicate task IDs are rejected
6. Unknown dependencies are rejected
7. Malformed task objects are rejected
8. Invalid task type is rejected
9. Provider without structured-output capability uses fallback
10. Malformed fallback output produces a planning failure
11. Existing planner behavior remains compatible
12. AgentRuntime capability check and graceful PlanningError handling
"""

import pytest
from unittest.mock import MagicMock

from clairecoder.gateway.types import Capability, ModelRequest, ModelResponse
from clairecoder.workflow.planner import (
    Planner,
    PLAN_SCHEMA,
    parse_structured_plan,
    validate_plan,
)
from clairecoder.workflow.task_graph import TaskGraph
from clairecoder.workflow.types import (
    Plan,
    PlanningError,
    PlanningLevel,
    Task,
    TaskState,
    TaskType,
)
from clairecoder.runtime.agent_runtime import AgentRuntime
from clairecoder.runtime.events import EventType


@pytest.fixture
def planner():
    return Planner()


class TestStructuredPlanContract:
    def test_planning_request_contains_structured_output_schema(self, planner):
        """Planning request must populate ModelRequest.structured_output_schema."""
        req = planner.build_planning_request(
            objective="Implement oauth2 authentication",
            planning_level=PlanningLevel.STRUCTURED,
            context_summary="Repo has FastAPI and SQLModel",
            model_id="gpt-4o",
            use_structured_output=True,
        )
        assert isinstance(req, ModelRequest)
        assert req.model_id == "gpt-4o"
        assert req.structured_output_schema is not None
        assert req.structured_output_schema == PLAN_SCHEMA

        # Check compact DAG example in prompt
        sys_msg = req.messages[0]["content"]
        assert "task-1 -> task-2 -> task-3" in sys_msg
        assert "task-1 -> task-4" in sys_msg
        assert "Dependencies must strictly reference valid task IDs" in sys_msg

    def test_schema_contains_expected_task_fields(self):
        """PLAN_SCHEMA must specify all required top-level and task fields."""
        # Top-level required fields
        required_top_level = [
            "assumptions",
            "affected_areas",
            "risks",
            "validation_strategy",
            "completion_criteria",
            "tasks",
        ]
        for field in required_top_level:
            assert field in PLAN_SCHEMA["properties"], f"Missing top-level property: {field}"
            assert field in PLAN_SCHEMA["required"], f"Top-level field not marked required: {field}"

        # Per-task properties
        task_props = PLAN_SCHEMA["properties"]["tasks"]["items"]["properties"]
        expected_task_fields = [
            "id",
            "title",
            "description",
            "type",
            "dependencies",
            "inputs",
            "expected_outputs",
            "validation",
        ]
        for field in expected_task_fields:
            assert field in task_props, f"Missing task property: {field}"

        # Required task fields
        required_task_fields = ["id", "title", "description", "type", "dependencies"]
        for field in required_task_fields:
            assert field in PLAN_SCHEMA["properties"]["tasks"]["items"]["required"]

    def test_valid_structured_response_creates_plan(self, planner):
        """Valid structured output creates a rich Plan."""
        response = ModelResponse(
            text="",
            structured_output={
                "assumptions": ["Database is PostgreSQL 16"],
                "affected_areas": ["src/auth", "src/models"],
                "risks": ["Token expiration race condition"],
                "validation_strategy": ["Integration tests with testcontainers"],
                "completion_criteria": ["All auth tests pass with 100% coverage"],
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Define User and Token schemas",
                        "description": "Create SQLModel definitions for users and refresh tokens",
                        "type": "implementation",
                        "dependencies": [],
                        "inputs": ["schema.sql"],
                        "expected_outputs": ["src/models/user.py"],
                        "validation": ["pytest tests/test_models.py"],
                    },
                    {
                        "id": "task-2",
                        "title": "Implement JWT issue and verify",
                        "description": "Create token generation and validation helpers",
                        "type": "implementation",
                        "dependencies": ["task-1"],
                        "inputs": ["src/models/user.py"],
                        "expected_outputs": ["src/auth/jwt.py"],
                        "validation": ["pytest tests/test_jwt.py"],
                    },
                ],
            },
        )
        plan = planner.create_plan("wf-1", "Auth Feature", PlanningLevel.STRUCTURED, model_response=response)
        assert plan.task_ids == ["task-1", "task-2"]
        assert plan.dependencies == {"task-1": [], "task-2": ["task-1"]}
        assert plan.assumptions == ["Database is PostgreSQL 16"]
        assert plan.affected_areas == ["src/auth", "src/models"]
        assert plan.risks == ["Token expiration race condition"]
        assert plan.validation_strategy == ["Integration tests with testcontainers"]
        assert plan.completion_criteria == ["All auth tests pass with 100% coverage"]

        # Rich task_details preserved
        assert "task-1" in plan.task_details
        assert plan.task_details["task-1"]["title"] == "Define User and Token schemas"
        assert plan.task_details["task-1"]["type"] == "implementation"

        # plan.tasks property works
        assert len(plan.tasks) == 2
        assert plan.tasks[0]["id"] == "task-1"
        assert plan.tasks[1]["dependencies"] == ["task-1"]

    def test_task_metadata_survives_planner_to_task_graph(self, planner):
        """Rich task metadata survives planner -> Plan -> TaskGraph."""
        response = ModelResponse(
            text="",
            structured_output={
                "assumptions": [],
                "affected_areas": [],
                "risks": [],
                "validation_strategy": [],
                "completion_criteria": [],
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Analyze schema",
                        "description": "Analyze existing database migrations",
                        "type": "analysis",
                        "dependencies": [],
                        "inputs": ["migrations/"],
                        "expected_outputs": ["analysis.md"],
                        "validation": ["test -f analysis.md"],
                    },
                    {
                        "id": "task-2",
                        "title": "Apply migration",
                        "description": "Run alembic upgrade head",
                        "type": "implementation",
                        "dependencies": ["task-1"],
                        "inputs": ["analysis.md"],
                        "expected_outputs": ["alembic_version table"],
                        "validation": ["alembic check"],
                    },
                ],
            },
        )
        plan = planner.create_plan("wf-1", "Migration", PlanningLevel.STRUCTURED, model_response=response)

        # 1. From Plan directly
        graph = TaskGraph.from_plan(plan, objective_id="obj-1")
        t1 = graph.get_task("task-1")
        assert t1.id == "task-1"
        assert t1.title == "Analyze schema"
        assert t1.description == "Analyze existing database migrations"
        assert t1.type == TaskType.ANALYSIS
        assert t1.dependencies == []
        assert t1.inputs == ["migrations/"]
        assert t1.expected_outputs == ["analysis.md"]
        assert t1.validation == ["test -f analysis.md"]

        t2 = graph.get_task("task-2")
        assert t2.id == "task-2"
        assert t2.type == TaskType.IMPLEMENTATION
        assert t2.dependencies == ["task-1"]

        # 2. From plan.tasks conceptually
        graph2 = TaskGraph.from_plan(plan.tasks, objective_id="obj-1")
        assert graph2.get_task("task-1").title == "Analyze schema"
        assert graph2.get_task("task-2").dependencies == ["task-1"]


class TestPlannerValidationRules:
    def test_duplicate_task_ids_are_rejected(self, planner):
        """Duplicate task IDs must raise PlanningError."""
        response = ModelResponse(
            text="",
            structured_output={
                "assumptions": [],
                "affected_areas": [],
                "risks": [],
                "validation_strategy": [],
                "completion_criteria": [],
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "First task",
                        "description": "Do part 1",
                        "type": "implementation",
                        "dependencies": [],
                    },
                    {
                        "id": "task-1",
                        "title": "Duplicate task ID",
                        "description": "Do part 2",
                        "type": "implementation",
                        "dependencies": [],
                    },
                ],
            },
        )
        with pytest.raises(PlanningError, match="(?i)duplicate task id"):
            planner.create_plan("wf-1", "Duplicate test", PlanningLevel.STRUCTURED, model_response=response)

    def test_empty_task_id_is_rejected(self, planner):
        """Empty or whitespace-only task IDs must raise PlanningError."""
        for bad_id in ["", "   "]:
            response = ModelResponse(
                text="",
                structured_output={
                    "assumptions": [],
                    "affected_areas": [],
                    "risks": [],
                    "validation_strategy": [],
                    "completion_criteria": [],
                    "tasks": [
                        {
                            "id": bad_id,
                            "title": "Bad ID",
                            "description": "Desc",
                            "type": "implementation",
                            "dependencies": [],
                        }
                    ],
                },
            )
            with pytest.raises(PlanningError, match="(?i)non-empty string"):
                planner.create_plan("wf-1", "Bad ID", PlanningLevel.STRUCTURED, model_response=response)

    def test_unknown_dependencies_are_rejected(self, planner):
        """Dependencies referencing non-existent tasks must raise PlanningError."""
        response = ModelResponse(
            text="",
            structured_output={
                "assumptions": [],
                "affected_areas": [],
                "risks": [],
                "validation_strategy": [],
                "completion_criteria": [],
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "First task",
                        "description": "Desc",
                        "type": "implementation",
                        "dependencies": ["nonexistent-task-99"],
                    }
                ],
            },
        )
        with pytest.raises(PlanningError, match="(?i)(does not exist|unknown)"):
            planner.create_plan("wf-1", "Unknown dep", PlanningLevel.STRUCTURED, model_response=response)

    def test_self_dependency_is_rejected(self, planner):
        """Self-referencing dependencies must raise PlanningError."""
        response = ModelResponse(
            text="",
            structured_output={
                "assumptions": [],
                "affected_areas": [],
                "risks": [],
                "validation_strategy": [],
                "completion_criteria": [],
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Self dep task",
                        "description": "Desc",
                        "type": "implementation",
                        "dependencies": ["task-1"],
                    }
                ],
            },
        )
        with pytest.raises(PlanningError, match="(?i)cannot depend on itself"):
            planner.create_plan("wf-1", "Self dep", PlanningLevel.STRUCTURED, model_response=response)

    def test_malformed_task_objects_are_rejected(self, planner):
        """Malformed task objects (non-dict, missing required fields) must raise PlanningError."""
        # Non-dict task
        bad_response_1 = ModelResponse(
            text="",
            structured_output={"tasks": ["not_a_dictionary_task"]},
        )
        with pytest.raises(PlanningError, match="(?i)malformed task object"):
            planner.create_plan("wf-1", "Malformed", PlanningLevel.STRUCTURED, model_response=bad_response_1)

        # Missing required field 'description'
        bad_response_2 = ModelResponse(
            text="",
            structured_output={
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Title only",
                        "type": "implementation",
                        "dependencies": [],
                    }
                ]
            },
        )
        with pytest.raises(PlanningError, match="(?i)missing required field 'description'"):
            planner.create_plan("wf-1", "Missing field", PlanningLevel.STRUCTURED, model_response=bad_response_2)

        # Dependencies is not a list
        bad_response_3 = ModelResponse(
            text="",
            structured_output={
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "T1",
                        "description": "D1",
                        "type": "implementation",
                        "dependencies": "not-a-list",
                    }
                ]
            },
        )
        with pytest.raises(PlanningError, match="(?i)dependencies' must be a list"):
            planner.create_plan("wf-1", "Bad deps", PlanningLevel.STRUCTURED, model_response=bad_response_3)

    def test_invalid_task_type_is_rejected(self, planner):
        """Invalid task type string must raise PlanningError."""
        response = ModelResponse(
            text="",
            structured_output={
                "assumptions": [],
                "affected_areas": [],
                "risks": [],
                "validation_strategy": [],
                "completion_criteria": [],
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Bad type task",
                        "description": "Desc",
                        "type": "completely_unsupported_type_xyz",
                        "dependencies": [],
                    }
                ],
            },
        )
        with pytest.raises(PlanningError, match="(?i)invalid task type"):
            planner.create_plan("wf-1", "Invalid type", PlanningLevel.STRUCTURED, model_response=response)


class TestFallbackBehavior:
    def test_provider_without_structured_output_capability_uses_fallback(self, planner):
        """When use_structured_output is False, request does not set schema and prompt requests JSON."""
        req = planner.build_planning_request(
            objective="Fallback Objective",
            planning_level=PlanningLevel.STRUCTURED,
            context_summary="Fallback context",
            use_structured_output=False,
        )
        assert req.structured_output_schema is None
        assert "```json" in req.messages[0]["content"]

        # Valid fallback response parses correctly
        fallback_json = """```json
{
  "assumptions": ["Fallback works"],
  "affected_areas": ["src/fallback"],
  "risks": [],
  "validation_strategy": [],
  "completion_criteria": [],
  "tasks": [
    {
      "id": "task-fb-1",
      "title": "Fallback Task",
      "description": "Execute in fallback mode",
      "type": "implementation",
      "dependencies": []
    }
  ]
}
```"""
        resp = ModelResponse(text=fallback_json)
        plan = planner.create_plan("wf-1", "Fallback test", PlanningLevel.STRUCTURED, model_response=resp)
        assert plan.task_ids == ["task-fb-1"]
        assert plan.assumptions == ["Fallback works"]

    def test_malformed_fallback_output_produces_planning_failure(self, planner):
        """Malformed fallback output raises PlanningError instead of creating fake plan."""
        # 1. Broken JSON syntax
        broken_json = "```json\n{ 'tasks': [ broken json\n```"
        resp_broken = ModelResponse(text=broken_json)
        with pytest.raises(PlanningError, match="(?i)malformed json"):
            planner.create_plan("wf-1", "Obj", PlanningLevel.STRUCTURED, model_response=resp_broken)

        # 2. Valid JSON but invalid plan structure (missing tasks)
        missing_tasks_json = "```json\n{ \"assumptions\": [\"A\"] }\n```"
        resp_missing = ModelResponse(text=missing_tasks_json)
        with pytest.raises(PlanningError, match="(?i)missing required top-level field 'tasks'"):
            planner.create_plan("wf-1", "Obj", PlanningLevel.STRUCTURED, model_response=resp_missing)

        # 3. Direct parse_structured_plan on non-JSON text raises PlanningError
        with pytest.raises(PlanningError, match="(?i)failed to parse structured plan"):
            parse_structured_plan(ModelResponse(text="I cannot fulfill this request as an AI."))

        # 4. Strict mode on non-JSON text raises PlanningError
        with pytest.raises(PlanningError):
            planner.create_plan(
                "wf-1", "Obj", PlanningLevel.STRUCTURED,
                model_response=ModelResponse(text="Non JSON text"),
                strict=True,
            )


class TestReplanAndCompatibility:
    def test_replan_request_structure(self, planner):
        """build_replan_request populates schema and failure context."""
        prev_plan = Plan(
            id="plan-old",
            workflow_id="wf-1",
            objective="Old obj",
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1"],
            assumptions=["prev assumption"],
            risks=["prev risk"],
        )
        req = planner.build_replan_request(
            objective="Old obj",
            previous_plan=prev_plan,
            failure_reason="Unit test failed on t1",
            context_summary="Replanning info",
            use_structured_output=True,
        )
        assert req.structured_output_schema == PLAN_SCHEMA
        prompt_text = req.messages[0]["content"]
        assert "Unit test failed on t1" in prompt_text
        assert "plan-old" in prompt_text
        assert "task-1 -> task-2 -> task-3" in prompt_text

    def test_existing_planner_behavior_remains_compatible(self, planner):
        """Direct execution without model response creates minimal scaffold."""
        plan = planner.create_plan("wf-1", "Direct operation", PlanningLevel.DIRECT)
        assert plan.workflow_id == "wf-1"
        assert plan.objective == "Direct operation"
        assert plan.planning_level == PlanningLevel.DIRECT
        assert plan.task_ids == []

    def test_runtime_structured_capability_and_planning_error_handling(self):
        """AgentRuntime checks capability and handles PlanningError gracefully."""
        mock_gateway = MagicMock()
        mock_gateway.check_capability.return_value = False  # Model doesn't support structured output

        mock_engine = MagicMock()
        # Return fallback text
        fallback_json = """```json
{
  "assumptions": [],
  "affected_areas": [],
  "risks": [],
  "validation_strategy": [],
  "completion_criteria": [],
  "tasks": [
    {
      "id": "task-runtime-1",
      "title": "Runtime Task",
      "description": "Run via runtime",
      "type": "implementation",
      "dependencies": []
    }
  ]
}
```"""
        mock_engine.execute_model.return_value = ModelResponse(text=fallback_json)

        runtime = AgentRuntime(
            model_gateway=mock_gateway,
            engineering_engine=mock_engine,
            executor=lambda task: True,
        )

        result = runtime.run(
            objective="Test runtime fallback",
            active_model="simple-model",
        )
        assert result.success is True
        # Verify check_capability was called for STRUCTURED_OUTPUT
        mock_gateway.check_capability.assert_any_call("simple-model", Capability.STRUCTURED_OUTPUT)

    def test_runtime_reports_failure_on_planning_error(self):
        """When planning raises PlanningError, AgentRuntime emits RUN_FAILED and fails run."""
        mock_gateway = MagicMock()
        mock_gateway.check_capability.return_value = True

        mock_engine = MagicMock()
        # Return broken output that fails planning validation
        mock_engine.execute_model.return_value = ModelResponse(
            structured_output={"tasks": [{"id": "t1", "dependencies": ["unknown_dep"]}]}
        )

        runtime = AgentRuntime(
            model_gateway=mock_gateway,
            engineering_engine=mock_engine,
        )

        events_emitted = []
        runtime.event_emitter.subscribe(lambda event: events_emitted.append(event.event_type))

        result = runtime.run(
            objective="Failing plan test",
            active_model="gpt-4o",
        )
        assert result.success is False
        assert "Planning failed" in result.failure_reason
        assert EventType.RUN_FAILED in events_emitted
