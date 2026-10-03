"""Focused tests for TaskGraph and structured Task representation.

Correction #13 — Structured Task Graph:
- Task model with semantic fields (title, type, inputs, expected_outputs, validation)
- Task classification (TaskType) and explicit lifecycle states (TaskState/TaskStatus)
- Dependency validation (unknown, self, circular, diamond)
- Deterministic ready-task calculation
- Dependency completion unlocks dependents
- Dependency failure blocks dependents
- Retrying unblocks dependents
- Task attempts and failure evidence tracking
- RuntimeEvent emission for task lifecycle (TASK_STARTED, TASK_COMPLETED, TASK_FAILED, TASK_RETRYING)
- Planner preserves structured task metadata from model plans
- Serialization round-trip
"""

import pytest
from typing import Any, Dict, List

from clairecoder.workflow.types import (
    Plan,
    PlanningLevel,
    Task,
    TaskState,
    TaskStatus,
    TaskType,
    TaskGraphError,
    DependencyCycleError,
    DependencyNotFoundError,
    InvalidDependencyError,
)
from clairecoder.workflow.task_graph import TaskGraph
from clairecoder.workflow.planner import Planner
from clairecoder.runtime.emitter import EventEmitter
from clairecoder.runtime.events import EventType, RuntimeEvent


# =============================================================================
# HELPERS
# =============================================================================

def _make_task(
    tid: str,
    deps: List[str] = None,
    title: str = "",
    task_type: TaskType = TaskType.IMPLEMENTATION,
    status: TaskState = TaskState.PENDING,
    inputs: List[str] = None,
    outputs: List[str] = None,
    validation: List[str] = None,
    objective_id: str = "obj_test",
) -> Task:
    """Helper to build a structured Task."""
    return Task(
        id=tid,
        objective_id=objective_id,
        title=title or f"Title for {tid}",
        description=f"Description for {tid}",
        type=task_type,
        status=status,
        dependencies=deps or [],
        inputs=inputs or [],
        expected_outputs=outputs or [],
        validation=validation or [],
    )


# =============================================================================
# 1. TASK MODEL & TYPES
# =============================================================================

class TestTaskModel:
    """Tests for the enriched Task dataclass and type classifications."""

    def test_task_has_all_semantic_fields(self):
        task = Task(
            id="t1",
            objective_id="obj_1",
            title="Implement calculator",
            description="Add calculator operations",
            type=TaskType.IMPLEMENTATION,
            dependencies=["t0"],
            inputs=["src/calc.py"],
            expected_outputs=["working calculator"],
            validation=["pytest tests/test_calc.py"],
            status=TaskState.PENDING,
            attempts=0,
            failure_evidence=[],
            metadata={"priority": "high"},
        )
        assert task.id == "t1"
        assert task.objective_id == "obj_1"
        assert task.title == "Implement calculator"
        assert task.description == "Add calculator operations"
        assert task.type == TaskType.IMPLEMENTATION
        assert task.dependencies == ["t0"]
        assert task.inputs == ["src/calc.py"]
        assert task.expected_outputs == ["working calculator"]
        assert task.validation == ["pytest tests/test_calc.py"]
        assert task.status == TaskState.PENDING
        assert task.attempts == 0
        assert task.failure_evidence == []
        assert task.metadata == {"priority": "high"}

    def test_task_type_enum_members(self):
        expected = {
            "analysis", "implementation", "test", "refactor",
            "verification", "documentation", "other",
        }
        actual = {t.value for t in TaskType}
        assert expected.issubset(actual)

    def test_task_type_fallback(self):
        # Unknown string falls back to OTHER
        assert TaskType("non_existent_type") == TaskType.OTHER

    def test_task_state_alias_and_compatibility(self):
        assert TaskStatus is TaskState
        assert TaskState.COMPLETED == TaskState.SUCCEEDED
        assert TaskState("completed") == TaskState.SUCCEEDED
        assert TaskState("done") == TaskState.SUCCEEDED
        assert TaskState("succeeded") == TaskState.SUCCEEDED

    def test_task_post_init_coercion(self):
        # Passing string for type/status coerces properly
        task = Task(
            id="t1",
            objective_id="obj",
            description="desc",
            type="test",
            status="ready",
        )
        assert task.type == TaskType.TEST
        assert task.status == TaskState.READY

    def test_task_convenience_properties(self):
        task = _make_task("t1", status=TaskState.READY)
        assert task.is_ready
        assert not task.is_completed
        assert not task.is_blocked

        task.status = TaskState.SUCCEEDED
        assert task.is_completed
        assert not task.is_ready

        task.status = TaskState.BLOCKED
        assert task.is_blocked


# =============================================================================
# 2. TASK GRAPH MANAGEMENT & RETRIEVAL
# =============================================================================

class TestTaskGraphBasic:
    """Tests for basic task addition, retrieval, and duplication rejection."""

    def test_add_and_retrieve_task(self):
        graph = TaskGraph()
        t1 = _make_task("t1")
        graph.add_task(t1)

        assert graph.task_count == 1
        assert graph.get_task("t1") is t1
        assert graph.get_task("nonexistent") is None
        assert graph.tasks == [t1]

    def test_duplicate_task_id_rejected(self):
        graph = TaskGraph()
        t1a = _make_task("t1")
        t1b = _make_task("t1")
        graph.add_task(t1a)

        with pytest.raises(TaskGraphError, match="Duplicate task ID"):
            graph.add_task(t1b)


# =============================================================================
# 3. DEPENDENCY VALIDATION
# =============================================================================

class TestTaskGraphValidation:
    """Tests for dependency integrity validation."""

    def test_unknown_dependency_rejected(self):
        graph = TaskGraph()
        t1 = _make_task("t1", deps=["missing_task"])
        graph.add_task(t1)

        with pytest.raises(DependencyNotFoundError, match="missing_task"):
            graph.finalize()

    def test_self_dependency_rejected(self):
        graph = TaskGraph()
        t1 = _make_task("t1", deps=["t1"])

        # Caught either on add_task or finalize
        with pytest.raises(InvalidDependencyError, match="cannot depend on itself"):
            graph.add_task(t1)

    def test_direct_circular_dependency_rejected(self):
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=["B"]))
        graph.add_task(_make_task("B", deps=["A"]))

        with pytest.raises(DependencyCycleError, match="Dependency cycle"):
            graph.finalize()

    def test_indirect_circular_dependency_rejected(self):
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=["B"]))
        graph.add_task(_make_task("B", deps=["C"]))
        graph.add_task(_make_task("C", deps=["A"]))

        with pytest.raises(DependencyCycleError, match="Dependency cycle"):
            graph.finalize()

    def test_diamond_graph_is_valid(self):
        """Diamond: A -> B, A -> C, (B, C) -> D should not be flagged as cycle."""
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=[]))
        graph.add_task(_make_task("B", deps=["A"]))
        graph.add_task(_make_task("C", deps=["A"]))
        graph.add_task(_make_task("D", deps=["B", "C"]))

        graph.finalize()
        assert graph.is_finalized
        assert graph.task_count == 4


# =============================================================================
# 4. INITIAL STATES & READY TASK CALCULATION
# =============================================================================

class TestTaskGraphReadiness:
    """Tests for initial states, ready calculation, and deterministic ordering."""

    def test_initial_ready_and_pending_states(self):
        graph = TaskGraph()
        t_root = _make_task("root", deps=[])
        t_child = _make_task("child", deps=["root"])

        graph.add_task(t_root)
        graph.add_task(t_child)
        graph.finalize()

        assert t_root.status == TaskState.READY
        assert t_child.status == TaskState.PENDING
        assert graph.get_ready_tasks() == [t_root]

    def test_dependencies_satisfied_query(self):
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=[]))
        graph.add_task(_make_task("B", deps=["A"]))
        graph.finalize()

        assert graph.dependencies_satisfied("A") is True
        assert graph.dependencies_satisfied("B") is False

        graph.mark_started("A")
        assert graph.dependencies_satisfied("B") is False

        graph.mark_completed("A")
        assert graph.dependencies_satisfied("B") is True

    def test_deterministic_ready_task_ordering(self):
        """Independent tasks must always return in deterministic insertion order."""
        graph = TaskGraph()
        ids = ["task_delta", "task_alpha", "task_charlie", "task_bravo"]
        for tid in ids:
            graph.add_task(_make_task(tid, deps=[]))
        graph.finalize()

        ready_1 = [t.id for t in graph.get_ready_tasks()]
        ready_2 = [t.id for t in graph.get_ready_tasks()]
        ready_3 = [t.id for t in graph.get_ready_tasks()]

        assert ready_1 == ids
        assert ready_1 == ready_2 == ready_3


# =============================================================================
# 5. DEPENDENCY RESOLUTION & PROPAGATION
# =============================================================================

class TestTaskGraphLifecycle:
    """Tests for dependency unlocking, failure propagation, and retrying."""

    def test_dependency_completion_unlocks_dependent(self):
        """Task A completes -> dependent Task B becomes READY."""
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=[]))
        graph.add_task(_make_task("B", deps=["A"]))
        graph.finalize()

        assert [t.id for t in graph.get_ready_tasks()] == ["A"]

        graph.mark_started("A")
        assert graph.get_ready_tasks() == []

        graph.mark_completed("A")
        assert graph.get_task("A").status == TaskState.SUCCEEDED
        assert graph.get_task("B").status == TaskState.READY
        assert [t.id for t in graph.get_ready_tasks()] == ["B"]

    def test_multiple_dependencies_all_must_complete(self):
        """
        A ─┐
           ├──> C
        B ─┘
        C becomes READY only when BOTH A and B complete.
        """
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=[]))
        graph.add_task(_make_task("B", deps=[]))
        graph.add_task(_make_task("C", deps=["A", "B"]))
        graph.finalize()

        # Both A and B are initially READY
        assert set(t.id for t in graph.get_ready_tasks()) == {"A", "B"}

        # Complete A only
        graph.mark_started("A")
        graph.mark_completed("A")

        assert graph.get_task("C").status == TaskState.PENDING
        assert [t.id for t in graph.get_ready_tasks()] == ["B"]

        # Complete B
        graph.mark_started("B")
        graph.mark_completed("B")

        # Now C is READY
        assert graph.get_task("C").status == TaskState.READY
        assert [t.id for t in graph.get_ready_tasks()] == ["C"]

    def test_failed_dependency_blocks_dependent(self):
        """When A fails, B becomes BLOCKED and cannot run."""
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=[]))
        graph.add_task(_make_task("B", deps=["A"]))
        graph.finalize()

        graph.mark_started("A")
        evidence = {
            "type": "command_failure",
            "command": "pytest",
            "exit_code": 1,
            "stderr": "AssertionError",
        }
        graph.mark_failed("A", evidence=evidence)

        assert graph.get_task("A").status == TaskState.FAILED
        assert graph.get_task("A").failure_evidence == [evidence]

        # B is now BLOCKED
        assert graph.get_task("B").status == TaskState.BLOCKED
        assert graph.get_ready_tasks() == []
        assert graph.get_blocked_tasks() == [graph.get_task("B")]
        assert graph.get_blocking_reasons("B") == ["A"]
        assert graph.has_failures() is True

    def test_retrying_unblocks_dependents(self):
        """Retrying a failed dependency unblocks its dependents back to PENDING."""
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=[]))
        graph.add_task(_make_task("B", deps=["A"]))
        graph.finalize()

        graph.mark_started("A")
        graph.mark_failed("A", evidence={"error": "fail"})
        assert graph.get_task("B").status == TaskState.BLOCKED

        # Retry A
        graph.mark_retrying("A")
        assert graph.get_task("A").status == TaskState.READY

        # B transitions back to PENDING because A is no longer failed
        assert graph.get_task("B").status == TaskState.PENDING

        # Now run A again and succeed
        graph.mark_started("A")
        graph.mark_completed("A")

        # B becomes READY
        assert graph.get_task("B").status == TaskState.READY
        assert [t.id for t in graph.get_ready_tasks()] == ["B"]

    def test_attempt_counting(self):
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=[]))
        graph.finalize()

        task = graph.get_task("A")
        assert task.attempts == 0

        # First attempt
        graph.mark_started("A")
        assert task.attempts == 1

        graph.mark_failed("A")
        assert task.attempts == 1

        # Retry
        graph.mark_retrying("A")
        assert task.attempts == 1

        # Second attempt
        graph.mark_started("A")
        assert task.attempts == 2

        graph.mark_completed("A")
        assert task.attempts == 2

    def test_invalid_lifecycle_transitions_rejected(self):
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=[]))
        graph.add_task(_make_task("B", deps=["A"]))
        graph.finalize()

        # Cannot complete task that isn't running
        with pytest.raises(TaskGraphError, match="expected RUNNING"):
            graph.mark_completed("A")

        # Cannot fail task that isn't running
        with pytest.raises(TaskGraphError, match="expected RUNNING"):
            graph.mark_failed("A")

        # Cannot start task that is PENDING
        with pytest.raises(TaskGraphError, match="expected READY"):
            graph.mark_started("B")

        # Cannot retry task that isn't FAILED
        with pytest.raises(TaskGraphError, match="expected FAILED"):
            graph.mark_retrying("A")

    def test_topological_order(self):
        graph = TaskGraph()
        graph.add_task(_make_task("C", deps=["B"]))
        graph.add_task(_make_task("B", deps=["A"]))
        graph.add_task(_make_task("A", deps=[]))
        graph.finalize()

        topo = graph.topological_order()
        assert topo.index("A") < topo.index("B") < topo.index("C")

    def test_all_completed(self):
        graph = TaskGraph()
        graph.add_task(_make_task("A", deps=[]))
        graph.add_task(_make_task("B", deps=["A"]))
        graph.finalize()

        assert not graph.all_completed()

        graph.mark_started("A")
        graph.mark_completed("A")
        assert not graph.all_completed()

        graph.mark_started("B")
        graph.mark_completed("B")
        assert graph.all_completed()


# =============================================================================
# 6. RUNTIMEEVENT EMISSION
# =============================================================================

class TestTaskGraphEvents:
    """Tests for EventEmitter and RuntimeEvent integration."""

    def test_events_emitted_via_event_emitter(self):
        emitter = EventEmitter()
        emitted_events: List[RuntimeEvent] = []
        emitter.subscribe(lambda e: emitted_events.append(e))

        graph = TaskGraph(event_emitter=emitter, run_id="run_123")
        graph.add_task(_make_task("t1", deps=[], title="Build widget"))
        graph.finalize()

        # 1. TASK_STARTED
        graph.mark_started("t1")
        assert len(emitted_events) == 1
        e0 = emitted_events[0]
        assert e0.event_type == EventType.TASK_STARTED
        assert e0.task_id == "t1"
        assert e0.run_id == "run_123"
        assert e0.payload["title"] == "Build widget"
        assert e0.payload["attempt"] == 1

        # 2. TASK_FAILED
        graph.mark_failed("t1", evidence={"error": "timeout"})
        assert len(emitted_events) == 2
        e1 = emitted_events[1]
        assert e1.event_type == EventType.TASK_FAILED
        assert e1.task_id == "t1"
        assert e1.payload["failure_evidence"] == [{"error": "timeout"}]

        # 3. TASK_RETRYING
        graph.mark_retrying("t1")
        assert len(emitted_events) == 3
        e2 = emitted_events[2]
        assert e2.event_type == EventType.TASK_RETRYING
        assert e2.task_id == "t1"

        # 4. TASK_STARTED (attempt 2)
        graph.mark_started("t1")
        assert len(emitted_events) == 4
        assert emitted_events[3].payload["attempt"] == 2

        # 5. TASK_COMPLETED
        graph.mark_completed("t1")
        assert len(emitted_events) == 5
        e4 = emitted_events[4]
        assert e4.event_type == EventType.TASK_COMPLETED
        assert e4.task_id == "t1"

    def test_events_emitted_via_callback(self):
        calls: List[tuple] = []
        graph = TaskGraph(event_callback=lambda et, d: calls.append((et, d)))
        graph.add_task(_make_task("t1", deps=[]))
        graph.finalize()

        graph.mark_started("t1")
        graph.mark_completed("t1")

        assert len(calls) == 2
        assert calls[0][0] == "task.started"
        assert calls[0][1]["task_id"] == "t1"
        assert calls[1][0] == "task.completed"


# =============================================================================
# 7. PLANNER INTEGRATION & METADATA PRESERVATION
# =============================================================================

class TestPlannerMetadataPreservation:
    """Tests verifying model plan semantics survive into Task objects."""

    def test_planner_preserves_structured_task_details(self):
        planner = Planner()
        plan = Plan(
            id="plan_01",
            workflow_id="wf_01",
            objective="Build calculator",
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t_impl", "t_test"],
            dependencies={"t_test": ["t_impl"]},
            task_details={
                "t_impl": {
                    "title": "Implement basic math",
                    "description": "Add add, sub, mul, div functions",
                    "type": "implementation",
                    "inputs": ["src/calc.py"],
                    "expected_outputs": ["math operations"],
                    "validation": ["pytest tests/test_calc.py"],
                    "metadata": {"risk": "low"},
                },
                "t_test": {
                    "title": "Write unit tests",
                    "description": "Cover all edge cases",
                    "type": "test",
                    "inputs": ["tests/test_calc.py"],
                    "expected_outputs": ["passing tests"],
                    "validation": ["pytest --cov"],
                },
            },
        )

        tasks = planner.create_tasks_from_plan(plan, objective_id="obj_calc")
        assert len(tasks) == 2

        t_impl = tasks[0]
        assert t_impl.id == "t_impl"
        assert t_impl.objective_id == "obj_calc"
        assert t_impl.title == "Implement basic math"
        assert t_impl.description == "Add add, sub, mul, div functions"
        assert t_impl.type == TaskType.IMPLEMENTATION
        assert t_impl.inputs == ["src/calc.py"]
        assert t_impl.expected_outputs == ["math operations"]
        assert t_impl.validation == ["pytest tests/test_calc.py"]
        assert t_impl.metadata == {"risk": "low"}

        t_test = tasks[1]
        assert t_test.id == "t_test"
        assert t_test.title == "Write unit tests"
        assert t_test.type == TaskType.TEST
        assert t_test.dependencies == ["t_impl"]

    def test_planner_extracts_from_tasks_list_format(self):
        """Model output with 'tasks' list instead of task_details dict."""
        planner = Planner()
        data = {
            "objective": "Build parser",
            "tasks": [
                {
                    "id": "step_1",
                    "title": "Tokenize input",
                    "description": "Lexer implementation",
                    "type": "implementation",
                    "dependencies": [],
                    "inputs": ["lexer.py"],
                    "expected_outputs": ["token stream"],
                    "validation": ["pytest tests/test_lexer.py"],
                },
                {
                    "id": "step_2",
                    "title": "Parse tokens",
                    "description": "Parser implementation",
                    "type": "implementation",
                    "dependencies": ["step_1"],
                    "inputs": ["parser.py"],
                    "expected_outputs": ["AST"],
                    "validation": ["pytest tests/test_parser.py"],
                },
            ],
        }

        plan = planner._plan_from_structured(
            plan_id="plan_02",
            workflow_id="wf_02",
            objective="Build parser",
            planning_level=PlanningLevel.STRUCTURED,
            data=data,
        )

        tasks = planner.create_tasks_from_plan(plan, objective_id="obj_parser")
        assert len(tasks) == 2
        assert tasks[0].title == "Tokenize input"
        assert tasks[1].title == "Parse tokens"
        assert tasks[1].dependencies == ["step_1"]

    def test_task_graph_from_plan_factory(self):
        plan = Plan(
            id="plan_03",
            workflow_id="wf_03",
            objective="Refactor engine",
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=["step_a", "step_b"],
            dependencies={"step_b": ["step_a"]},
            task_details={
                "step_a": {"title": "Extract interface", "type": "refactor"},
                "step_b": {"title": "Update callers", "type": "refactor"},
            },
        )

        graph = TaskGraph.from_plan(plan)
        assert graph.is_finalized
        assert graph.task_count == 2
        assert [t.id for t in graph.get_ready_tasks()] == ["step_a"]


# =============================================================================
# 8. SERIALIZATION ROUNDTRIP
# =============================================================================

class TestTaskGraphSerialization:
    """Tests for TaskGraph to_dict / from_dict roundtrip."""

    def test_roundtrip_preserves_all_state(self):
        graph = TaskGraph()
        t1 = _make_task(
            "t1",
            deps=[],
            title="Task 1",
            inputs=["in.txt"],
            outputs=["out.txt"],
            validation=["test.sh"],
        )
        t2 = _make_task("t2", deps=["t1"], title="Task 2")
        graph.add_task(t1)
        graph.add_task(t2)
        graph.finalize()

        graph.mark_started("t1")
        graph.mark_completed("t1")

        data = graph.to_dict()
        restored = TaskGraph.from_dict(data)

        assert restored.is_finalized is True
        assert restored.task_count == 2
        assert restored.get_task("t1").status == TaskState.SUCCEEDED
        assert restored.get_task("t2").status == TaskState.READY
        assert restored.get_task("t1").title == "Task 1"
        assert restored.get_task("t1").inputs == ["in.txt"]
        assert restored.get_task("t1").expected_outputs == ["out.txt"]
        assert restored.get_task("t1").validation == ["test.sh"]
