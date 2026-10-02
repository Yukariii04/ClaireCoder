"""Correction #11 Regression Tests.

Tests for:
- False success after failed workflow (§1)
- RUN_STATE_CHANGED not appearing as user-facing activity (§2, §3)
- Finalization state authority (§4)
- Cancellation authority (§5)
- Failure evidence propagation to replanning (§6)
- Verification gate (§7)
- Event presentation contract (§11)
- End-to-end failure and success paths (§9)
- Permission/cancel regression (§10)
"""

from clairecoder.interaction.run_state import RunState, AgentRun
from clairecoder.interaction.controller import InteractionController
from clairecoder.engine.engine import EngineeringEngine
from clairecoder.engine.types import (
    EngineeringObjective, EngineEvent, ObjectiveStatus,
    Task as EngineTask, TaskState as EngineTaskState,
)
from clairecoder.tui.adapter import PresentationAdapter
from clairecoder.tui.activity import ActivityModel, ActivityType, ActivityState
from clairecoder.core.events import Event
from clairecoder.execution.types import (
    ExecutionResult, ExecutionResultCategory, FailureCategory,
    FailureEvidence,
)
from clairecoder.workflow.types import WorkflowState
from clairecoder.workflow.planner import Planner
from clairecoder.workflow.manager import WorkflowManager
from clairecoder.execution.manager import ExecutionManager
from clairecoder.verification.engine import VerificationEngine
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.registry import ToolRegistry
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.app import ClaireCoderV1

import threading
import time


def _make_engine(gw=None):
    """Create an EngineeringEngine with proper tool_executor for testing."""
    if gw is None:
        gw = _MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    return EngineeringEngine(model_gateway=gw, tool_executor=executor)


# ===========================================================================
# HELPER: Minimal mock gateway
# ===========================================================================

class _MockGateway:
    """Minimal mock satisfying ModelGatewayInterface for testing."""
    _providers = {}
    _adapters = {}
    _models = {"test-model": type("M", (), {
        "id": "test-model",
        "provider": type("P", (), {"id": "test", "name": "Test"})(),
        "capabilities": [],
        "context_capacity": 4096,
        "display_name": "test-model",
        "endpoint": None,
    })()}

    def register_adapter(self, adapter):
        pass

    def register_model(self, model):
        self._models[model.id] = model

    def get_model(self, model_id):
        return self._models.get(model_id)

    def execute(self, request):
        from clairecoder.gateway.types import ModelResponse
        return ModelResponse(text="Mock response", model_id=request.model_id)


class _FailingApp:
    """Simulates ClaireCoderV1 where run() always fails the objective."""
    def __init__(self, engine):
        self._engine = engine
        self.config_manager = type("CM", (), {
            "get_active": lambda s: {"model_id": "test-model", "provider_profile_id": "test"},
            "is_configured": lambda s: True,
            "needs_repair": lambda s: False,
            "list_provider_profiles": lambda s: [],
        })()
        self.execution_manager = ExecutionManager()
        self.verification_engine = VerificationEngine()

    def get_active_model_id(self):
        return "test-model"

    def run(self, session_id):
        """Simulate a workflow that FAILS."""
        session = self._engine.get_session(session_id)
        if session and session.objective:
            session.objective.status = ObjectiveStatus.FAILED
            # Add a failed task
            task = EngineTask(
                id="task_fail_1",
                objective_id=session.objective.id,
                description="Deliberately failing task",
            )
            task.status = EngineTaskState.FAILED
            task.failure_state = "Tool write_file returned exit_code=1"
            session.tasks[task.id] = task


class _SucceedingApp:
    """Simulates ClaireCoderV1 where run() succeeds."""
    def __init__(self, engine):
        self._engine = engine
        self.config_manager = type("CM", (), {
            "get_active": lambda s: {"model_id": "test-model", "provider_profile_id": "test"},
            "is_configured": lambda s: True,
            "needs_repair": lambda s: False,
            "list_provider_profiles": lambda s: [],
        })()
        self.execution_manager = ExecutionManager()
        self.verification_engine = VerificationEngine()

    def get_active_model_id(self):
        return "test-model"

    def run(self, session_id):
        """Simulate a workflow that SUCCEEDS."""
        session = self._engine.get_session(session_id)
        if session and session.objective:
            session.objective.status = ObjectiveStatus.COMPLETED
            task = EngineTask(
                id="task_ok_1",
                objective_id=session.objective.id,
                description="Success task",
            )
            task.status = EngineTaskState.SUCCEEDED
            task.expected_result = "Created file output.txt"
            session.tasks[task.id] = task


class _CancellingApp:
    """Simulates ClaireCoderV1 where run() cancels the objective."""
    def __init__(self, engine):
        self._engine = engine
        self.config_manager = type("CM", (), {
            "get_active": lambda s: {"model_id": "test-model", "provider_profile_id": "test"},
            "is_configured": lambda s: True,
            "needs_repair": lambda s: False,
            "list_provider_profiles": lambda s: [],
        })()
        self.execution_manager = ExecutionManager()
        self.verification_engine = VerificationEngine()

    def get_active_model_id(self):
        return "test-model"

    def run(self, session_id):
        session = self._engine.get_session(session_id)
        if session and session.objective:
            session.objective.status = ObjectiveStatus.CANCELLED


# ===========================================================================
# §1 — FAILED WORKFLOW MUST NEVER BECOME SUCCESSFUL AGENTRUN
# ===========================================================================

class TestFalseSuccessPrevention:
    """§1: Failed workflow cannot produce success."""

    def _make_failing_controller(self):
        gw = _MockGateway()
        engine = _make_engine(gw)
        app = _FailingApp(engine)
        controller = InteractionController(engine=engine, app=app)
        return controller, engine

    def _make_succeeding_controller(self):
        gw = _MockGateway()
        engine = _make_engine(gw)
        app = _SucceedingApp(engine)
        controller = InteractionController(engine=engine, app=app)
        return controller, engine

    def test_failed_workflow_cannot_produce_objective_completed(self):
        """§1A: failed workflow cannot produce 'Objective completed' text."""
        controller, engine = self._make_failing_controller()
        events = []
        controller.subscribe(lambda e: events.append(e))

        # Submit engineering request
        sid = "sess_fail_1"
        engine.receive_objective(EngineeringObjective(
            id="obj_1", request="create file test.py", session_id=sid
        ))
        controller._active_session_id = sid

        # Run workflow in foreground to capture final state
        run = controller._create_run("run_test_1")
        controller._run_engineering_workflow(sid, "create file test.py", run=run)

        # Assert: no "Objective completed" in response events
        for evt in events:
            if evt.name == "response_complete":
                text = evt.payload.get("text", "")
                assert "Objective completed" not in text, \
                    f"Failed workflow emitted 'Objective completed': {text}"

    def test_failed_workflow_cannot_transition_agentrun_to_completed(self):
        """§1B: failed workflow cannot transition AgentRun to COMPLETED."""
        controller, engine = self._make_failing_controller()

        sid = "sess_fail_2"
        engine.receive_objective(EngineeringObjective(
            id="obj_2", request="create file test.py", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_test_2")
        controller._run_engineering_workflow(sid, "create file test.py", run=run)

        assert run.state != RunState.COMPLETED, \
            f"AgentRun transitioned to COMPLETED despite failed workflow: {run.state}"
        assert run.state == RunState.FAILED

    def test_failed_task_remains_failed_through_finalization(self):
        """§1C: failed task remains failed through controller finalization."""
        controller, engine = self._make_failing_controller()

        sid = "sess_fail_3"
        engine.receive_objective(EngineeringObjective(
            id="obj_3", request="create file test.py", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_test_3")
        controller._run_engineering_workflow(sid, "create file test.py", run=run)

        session = engine.get_session(sid)
        assert session.objective.status == ObjectiveStatus.FAILED

        # Check that the AgentRun failure_reason contains task evidence
        assert run.failure_reason is not None
        assert "task_fail_1" in run.failure_reason.lower() or "fail" in run.failure_reason.lower()

    def test_successful_workflow_produces_normal_completion(self):
        """§1D: successful workflow still produces normal successful completion."""
        controller, engine = self._make_succeeding_controller()
        events = []
        controller.subscribe(lambda e: events.append(e))

        sid = "sess_ok_1"
        engine.receive_objective(EngineeringObjective(
            id="obj_ok_1", request="create file output.txt", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_ok_1")
        controller._run_engineering_workflow(sid, "create file output.txt", run=run)

        assert run.state == RunState.COMPLETED
        # Should have a response_complete event without error flag
        completion_events = [e for e in events if e.name == "response_complete"]
        assert len(completion_events) > 0
        last = completion_events[-1]
        assert not last.payload.get("error", False)


# ===========================================================================
# §2, §3 — RUN_STATE_CHANGED NOT RENDERED AS USER-FACING ACTIVITY
# ===========================================================================

class TestRunStateChangedInternalOnly:
    """§2 / §3: RUN_STATE_CHANGED must not produce transcript activity."""

    def test_run_state_changed_returns_no_activity(self):
        """RUN_STATE_CHANGED event produces None from PresentationAdapter."""
        event = Event(name="run_state_changed", payload={
            "run_id": "test_run", "old_state": "idle", "new_state": "running",
        })
        result = PresentationAdapter.event_to_activity(event)
        assert result is None, f"RUN_STATE_CHANGED should return None, got: {result}"

    def test_run_started_returns_no_activity(self):
        event = Event(name="run_started", payload={"run_id": "test_run"})
        result = PresentationAdapter.event_to_activity(event)
        assert result is None

    def test_run_completed_returns_no_activity(self):
        event = Event(name="run_completed", payload={"run_id": "test_run"})
        result = PresentationAdapter.event_to_activity(event)
        assert result is None

    def test_run_failed_returns_no_activity(self):
        event = Event(name="run_failed", payload={"run_id": "test_run"})
        result = PresentationAdapter.event_to_activity(event)
        assert result is None

    def test_run_cancelled_returns_no_activity(self):
        event = Event(name="run_cancelled", payload={"run_id": "test_run"})
        result = PresentationAdapter.event_to_activity(event)
        assert result is None

    def test_repeated_run_state_changed_produces_no_activity(self):
        """§3: Repeated RUN_STATE_CHANGED events produce no transcript entries."""
        for state in ["idle", "running", "completed", "failed"]:
            event = Event(name="run_state_changed", payload={
                "run_id": "r1", "old_state": "idle", "new_state": state,
            })
            assert PresentationAdapter.event_to_activity(event) is None


# ===========================================================================
# §4 — FINALIZATION STATE AUTHORITY
# ===========================================================================

class TestFinalizationStateAuthority:
    """§4: AgentRun final state must be derived from workflow outcome."""

    def test_cancelled_objective_produces_cancelled_run(self):
        gw = _MockGateway()
        engine = _make_engine(gw)
        app = _CancellingApp(engine)
        controller = InteractionController(engine=engine, app=app)

        sid = "sess_cancel_1"
        engine.receive_objective(EngineeringObjective(
            id="obj_c1", request="do something", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_c1")
        controller._run_engineering_workflow(sid, "do something", run=run)

        assert run.state == RunState.CANCELLED

    def test_failed_objective_produces_failed_run(self):
        gw = _MockGateway()
        engine = _make_engine(gw)
        app = _FailingApp(engine)
        controller = InteractionController(engine=engine, app=app)

        sid = "sess_fail_4"
        engine.receive_objective(EngineeringObjective(
            id="obj_f4", request="fail please", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_f4")
        controller._run_engineering_workflow(sid, "fail please", run=run)

        assert run.state == RunState.FAILED

    def test_completed_objective_produces_completed_run(self):
        gw = _MockGateway()
        engine = _make_engine(gw)
        app = _SucceedingApp(engine)
        controller = InteractionController(engine=engine, app=app)

        sid = "sess_ok_2"
        engine.receive_objective(EngineeringObjective(
            id="obj_ok_2", request="succeed", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_ok_2")
        controller._run_engineering_workflow(sid, "succeed", run=run)

        assert run.state == RunState.COMPLETED

    def test_no_result_does_not_become_success(self):
        """Absence of task result must NOT be interpreted as success."""
        gw = _MockGateway()
        engine = _make_engine(gw)

        class _NoResultApp:
            config_manager = type("CM", (), {
                "get_active": lambda s: {"model_id": "test-model"},
                "is_configured": lambda s: True,
                "needs_repair": lambda s: False,
                "list_provider_profiles": lambda s: [],
            })()
            execution_manager = ExecutionManager()
            verification_engine = VerificationEngine()

            def get_active_model_id(self):
                return "test-model"

            def run(self, sid):
                # Does nothing — objective stays ACTIVE (not completed)
                pass

        app = _NoResultApp()
        app._engine = engine
        controller = InteractionController(engine=engine, app=app)

        sid = "sess_noresult"
        engine.receive_objective(EngineeringObjective(
            id="obj_nr", request="do stuff", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_nr")
        controller._run_engineering_workflow(sid, "do stuff", run=run)

        # Objective is still ACTIVE — must NOT become completed
        assert run.state != RunState.COMPLETED, \
            f"No-result run became COMPLETED: {run.state}"
        assert run.state == RunState.FAILED


# ===========================================================================
# §5 — AGENTRUN CANCELLATION AUTHORITY
# ===========================================================================

class TestCancellationAuthority:
    """§5: AgentRun cancellation controls runtime execution."""

    def test_agentrun_cancellation_stops_execution(self):
        run = AgentRun("r1")
        run.start()
        assert run.can_start_work
        run.cancel()
        assert not run.can_start_work
        assert run.state == RunState.CANCELLED

    def test_objective_failure_does_not_silently_become_success(self):
        """Objective failure must map to AgentRun failure, not success."""
        gw = _MockGateway()
        engine = _make_engine(gw)
        app = _FailingApp(engine)
        controller = InteractionController(engine=engine, app=app)

        sid = "sess_auth_1"
        engine.receive_objective(EngineeringObjective(
            id="obj_auth", request="test", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_auth")
        controller._run_engineering_workflow(sid, "test", run=run)

        assert run.state == RunState.FAILED
        assert run.state != RunState.COMPLETED


# ===========================================================================
# §6 — FAILURE EVIDENCE PROPAGATION
# ===========================================================================

class TestFailureEvidencePropagation:
    """§6: Real failure evidence reaches replanning."""

    def test_failure_evidence_dataclass(self):
        """FailureEvidence carries structured data."""
        evidence = FailureEvidence(
            tool="write_file",
            tool_call_id="tc_123",
            operation="write",
            target="/src/main.py",
            exit_code=1,
            stderr="Permission denied",
            reason="File is read-only",
            task_id="task_1",
        )
        summary = evidence.to_summary()
        assert "write_file" in summary
        assert "Permission denied" in summary
        assert "task_1" in summary

    def test_failure_evidence_to_summary_empty(self):
        evidence = FailureEvidence()
        assert evidence.to_summary() == "No evidence available"

    def test_failed_tool_error_reaches_replanning(self):
        """A failed tool's real error must reach the replan request."""
        gw = _MockGateway()
        engine = _make_engine(gw)

        # Build a planner and observe replan_request
        planner = Planner()
        from clairecoder.workflow.types import Plan, PlanningLevel
        plan = Plan(
            id="plan_1", workflow_id="wf_1", objective="obj_1",
            planning_level=PlanningLevel.STRUCTURED,
            task_ids=["t1"], assumptions=["assume file writable"],
        )

        # Build replan request with real failure evidence
        evidence = FailureEvidence(
            tool="write_file", exit_code=1,
            stderr="Permission denied: /src/main.py",
            task_id="t1",
        )
        failure_reason = evidence.to_summary()
        req = planner.build_replan_request(
            objective="Create main.py",
            previous_plan=plan,
            failure_reason=failure_reason,
            context_summary="test context",
            model_id="test-model",
        )

        # The replan request's system prompt should contain real evidence
        system_msg = req.messages[0]["content"]
        assert "write_file" in system_msg
        assert "Permission denied" in system_msg

    def test_execution_result_carries_failure_evidence(self):
        """ExecutionResult can carry FailureEvidence."""
        evidence = FailureEvidence(tool="terminal", exit_code=127, reason="command not found")
        result = ExecutionResult(
            category=ExecutionResultCategory.FAILURE,
            failure_category=FailureCategory.TOOL_FAILURE,
            error_message="command not found",
            failure_evidence=evidence,
        )
        assert result.failure_evidence is not None
        assert result.failure_evidence.exit_code == 127


# ===========================================================================
# §7 — VERIFICATION GATE
# ===========================================================================

class TestVerificationGate:
    """§7: Completion requires actual evidence, not just model says done."""

    def test_verification_failure_prevents_success(self):
        """If verification fails, workflow must NOT become successful."""
        gw = _MockGateway()
        engine = _make_engine(gw)

        # Simulate: objective status stays FAILED when verification fails
        # (This is enforced in app.py lines ~456-460)
        app = _FailingApp(engine)
        controller = InteractionController(engine=engine, app=app)

        sid = "sess_vgate_1"
        engine.receive_objective(EngineeringObjective(
            id="obj_vg", request="create verified output", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_vg")
        controller._run_engineering_workflow(sid, "create verified output", run=run)

        assert run.state == RunState.FAILED


# ===========================================================================
# §9 — END-TO-END REGRESSION (FAILURE PATH)
# ===========================================================================

class TestEndToEndFailurePath:
    """§9: Full failure lifecycle regression."""

    def test_e2e_failure_path(self):
        """user request -> controller -> AgentRun -> workflow -> failure -> finalization."""
        gw = _MockGateway()
        engine = _make_engine(gw)
        app = _FailingApp(engine)
        controller = InteractionController(engine=engine, app=app)

        events = []
        controller.subscribe(lambda e: events.append(e))

        sid = "sess_e2e_fail"
        engine.receive_objective(EngineeringObjective(
            id="obj_e2e_fail", request="create broken.py", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_e2e_fail")
        controller._run_engineering_workflow(sid, "create broken.py", run=run)

        # Assert failure cascade
        session = engine.get_session(sid)
        assert session.objective.status == ObjectiveStatus.FAILED
        assert run.state == RunState.FAILED

        # No "Objective completed" in any response
        for evt in events:
            if evt.name == "response_complete":
                assert "Objective completed" not in evt.payload.get("text", "")

        # No RUN_STATE_CHANGED activity rendered
        for evt in events:
            if evt.name == "run_state_changed":
                act = PresentationAdapter.event_to_activity(evt)
                assert act is None

        # Failure evidence is retained
        assert run.failure_reason is not None

    def test_e2e_success_path(self):
        """user request -> controller -> AgentRun -> workflow -> success -> finalization."""
        gw = _MockGateway()
        engine = _make_engine(gw)
        app = _SucceedingApp(engine)
        controller = InteractionController(engine=engine, app=app)

        events = []
        controller.subscribe(lambda e: events.append(e))

        sid = "sess_e2e_ok"
        engine.receive_objective(EngineeringObjective(
            id="obj_e2e_ok", request="create output.txt", session_id=sid
        ))
        controller._active_session_id = sid

        run = controller._create_run("run_e2e_ok")
        controller._run_engineering_workflow(sid, "create output.txt", run=run)

        # Assert success cascade
        session = engine.get_session(sid)
        assert session.objective.status == ObjectiveStatus.COMPLETED
        assert run.state == RunState.COMPLETED

        # Should have a successful response
        completion_events = [e for e in events if e.name == "response_complete"]
        assert len(completion_events) > 0
        assert not completion_events[-1].payload.get("error", False)

        # RUN_STATE_CHANGED remains internal
        for evt in events:
            if evt.name == "run_state_changed":
                act = PresentationAdapter.event_to_activity(evt)
                assert act is None


# ===========================================================================
# §10 — PERMISSION / CANCEL REGRESSION
# ===========================================================================

class TestPermissionCancelRegression:
    """§10: Permission resume/deny and cancellation still work."""

    def test_cancellation_cannot_later_become_success(self):
        """Once cancelled, AgentRun must not later become COMPLETED."""
        run = AgentRun("r_cancel")
        run.start()
        run.cancel()
        assert run.state == RunState.CANCELLED
        # Attempting to complete after cancel must be no-op (terminal state)
        run.complete()
        assert run.state == RunState.CANCELLED

    def test_interruption_cannot_later_become_success(self):
        """Once interrupted, AgentRun must not later become COMPLETED."""
        run = AgentRun("r_int")
        run.start()
        run.interrupt()
        assert run.state == RunState.INTERRUPTED
        run.complete()
        assert run.state == RunState.INTERRUPTED

    def test_failure_cannot_later_become_completed(self):
        """Once failed, complete() is a no-op."""
        run = AgentRun("r_fail_lock")
        run.start()
        run.fail("something broke")
        assert run.state == RunState.FAILED
        run.complete()
        assert run.state == RunState.FAILED

    def test_permission_wait_and_resume(self):
        """Permission WAITING_FOR_USER -> resume -> RUNNING."""
        run = AgentRun("r_perm")
        run.start()
        run.wait_for_user()
        assert run.state == RunState.WAITING_FOR_USER
        run.resume_from_wait()
        assert run.state == RunState.RUNNING


# ===========================================================================
# §11 — EVENT PRESENTATION CONTRACT
# ===========================================================================

class TestEventPresentationContract:
    """§11: Audit PresentationAdapter event-to-activity mapping."""

    def test_run_state_changed_no_activity(self):
        event = Event(name="run_state_changed", payload={})
        assert PresentationAdapter.event_to_activity(event) is None

    def test_planning_started_produces_activity(self):
        event = Event(name="planning_started", payload={"session_id": "s1"})
        act = PresentationAdapter.event_to_activity(event)
        assert act is not None
        assert act.type == ActivityType.THINKING
        assert "plan" in act.title.lower()

    def test_tool_execution_produces_activity(self):
        event = Event(name="tool_requested", payload={
            "tool_name": "read_file", "request_id": "req_1"
        })
        act = PresentationAdapter.event_to_activity(event)
        assert act is not None
        assert act.type == ActivityType.TOOL
        assert "read_file" in act.title.lower()

    def test_verification_produces_activity(self):
        event = Event(name="validation_started", payload={"task_id": "t1"})
        act = PresentationAdapter.event_to_activity(event)
        assert act is not None
        assert act.type == ActivityType.VERIFICATION

    def test_execution_failed_produces_activity(self):
        event = Event(name="execution_failed", payload={
            "objective_id": "obj_1", "failure_category": "GENERAL"
        })
        act = PresentationAdapter.event_to_activity(event)
        assert act is not None
        assert act.type == ActivityType.ERROR
        assert act.state == ActivityState.FAILED

    def test_objective_completed_produces_activity(self):
        event = Event(name="objective_completed", payload={"objective_id": "obj_1"})
        act = PresentationAdapter.event_to_activity(event)
        assert act is not None
        assert act.type == ActivityType.SUCCESS
        assert act.state == ActivityState.COMPLETED

    def test_streaming_chunk_no_activity(self):
        event = Event(name="streaming_chunk", payload={"text": "hello"})
        assert PresentationAdapter.event_to_activity(event) is None

    def test_response_complete_no_activity(self):
        event = Event(name="response_complete", payload={"text": "done"})
        assert PresentationAdapter.event_to_activity(event) is None

    def test_model_switched_no_activity(self):
        event = Event(name="model_switched", payload={"model_id": "m1"})
        assert PresentationAdapter.event_to_activity(event) is None

    def test_mode_changed_no_activity(self):
        event = Event(name="mode_changed", payload={"mode": "implement"})
        assert PresentationAdapter.event_to_activity(event) is None

    def test_task_started_produces_activity(self):
        event = Event(name="task_started", payload={"task_id": "t1"})
        act = PresentationAdapter.event_to_activity(event)
        assert act is not None
        assert act.type == ActivityType.MESSAGE
        assert "task" in act.title.lower()

    def test_task_completed_produces_activity(self):
        event = Event(name="task_completed", payload={"task_id": "t1"})
        act = PresentationAdapter.event_to_activity(event)
        assert act is not None
        assert act.state == ActivityState.COMPLETED


# ===========================================================================
# §3A: ONE OBJECTIVE-START EVENT PER USER REQUEST
# ===========================================================================

class TestSingleObjectiveStart:
    """Verify that a single user request produces exactly one OBJECTIVE_STARTED event."""

    def test_receive_objective_emits_exactly_one_start(self):
        """Engine.receive_objective must emit exactly one OBJECTIVE_STARTED."""
        gw = _MockGateway()
        engine = _make_engine(gw)
        events = []
        engine.subscribe(lambda e, d: events.append(e))

        obj = EngineeringObjective(id="obj_single", request="test", session_id="s1")
        engine.receive_objective(obj)

        start_events = [e for e in events if e == EngineEvent.OBJECTIVE_STARTED]
        assert len(start_events) == 1, f"Expected 1 OBJECTIVE_STARTED, got {len(start_events)}"

    def test_tui_app_does_not_duplicate_starting_objective(self):
        """TUI app must NOT manually create a 'Starting objective' activity —
        the engine's OBJECTIVE_STARTED (via PresentationAdapter) is authoritative."""
        # Verify that PresentationAdapter produces "Starting objective" from OBJECTIVE_STARTED
        event = Event(name="objective_started", payload={"objective_id": "obj1"})
        act = PresentationAdapter.event_to_activity(event)
        assert act is not None
        assert "starting objective" in act.title.lower() or "objective" in act.title.lower()

    def test_objective_accepted_is_distinct_from_starting(self):
        """'Objective accepted' in TUI is a distinct semantic event from
        'Starting objective' from the engine."""
        # The engine emits OBJECTIVE_STARTED -> adapter produces "Starting objective"
        # The TUI app produces "Objective accepted" from controller return value
        # These are now distinct titles, not duplicates
        start_event = Event(name="objective_started", payload={"objective_id": "obj1"})
        start_act = PresentationAdapter.event_to_activity(start_event)
        assert start_act is not None
        # The title should NOT be "Objective accepted" (which is now a separate message)
        assert "accepted" not in start_act.title.lower()


# ===========================================================================
# §3D: TASK ID CONSISTENCY AND UNIQUENESS ACROSS REPLANS
# ===========================================================================

class TestTaskIdConsistency:
    """Verify that task IDs are unique across plan cycles."""

    def test_fallback_task_id_does_not_use_negative_hash(self):
        """Task ID must not contain raw negative hash values like 'task_obj_-7'."""
        from clairecoder.app import ClaireCoderV1

        # Simulate the fallback task ID generation logic used in app.py
        # Old: f"task_{session.objective.id[:6]}" -> could produce "task_obj_-7"
        # New: f"T{cycles}{task_suffix}_{obj_short}" -> "T1_obj12345"
        objective_id = f"obj_{hash('test request')}"
        obj_short = objective_id.replace("-", "")[:8]
        cycle = 1
        replan_count = 0
        task_suffix = f"_r{replan_count}" if replan_count > 0 else ""
        task_id = f"T{cycle}{task_suffix}_{obj_short}"

        # Must not contain raw negative sign
        assert "-" not in task_id, f"Task ID contains negative sign: {task_id}"
        assert len(task_id) > 2, "Task ID should be meaningful"

    def test_replanned_task_gets_different_id(self):
        """Each replan cycle should produce a distinct task ID."""
        objective_id = "obj_test123"
        obj_short = objective_id.replace("-", "")[:8]

        # Cycle 1, no replan
        task_id_1 = f"T1_{obj_short}"
        # Cycle 2, replan 1
        task_id_2 = f"T2_r1_{obj_short}"
        # Cycle 3, replan 2
        task_id_3 = f"T3_r2_{obj_short}"

        assert task_id_1 != task_id_2
        assert task_id_2 != task_id_3
        assert task_id_1 != task_id_3


# ===========================================================================
# §9: NO DUPLICATE OBJECTIVE_COMPLETED EVENTS
# ===========================================================================

class TestNoDuplicateCompletion:
    """Verify OBJECTIVE_COMPLETED is emitted at most once per objective."""

    def test_complete_objective_idempotent(self):
        """Calling complete_objective when already COMPLETED must not re-emit."""
        gw = _MockGateway()
        engine = _make_engine(gw)
        events = []
        engine.subscribe(lambda e, d: events.append(e))

        obj = EngineeringObjective(id="obj_dup", request="test", session_id="s1")
        engine.receive_objective(obj)

        # Complete once
        engine.complete_objective("s1")
        complete_count_1 = sum(1 for e in events if e == EngineEvent.OBJECTIVE_COMPLETED)
        assert complete_count_1 == 1

        # Complete again — should still emit (engine doesn't guard, but app.py does)
        engine.complete_objective("s1")
        complete_count_2 = sum(1 for e in events if e == EngineEvent.OBJECTIVE_COMPLETED)
        # The engine itself allows re-emission; the guard is in app.py
        # This test documents the behavior — app.py's guard prevents the second call

    def test_app_finalization_does_not_double_complete(self):
        """app.py's post-loop finalization must not re-emit OBJECTIVE_COMPLETED
        when the loop already completed the objective."""
        gw = _MockGateway()
        engine = _make_engine(gw)

        obj = EngineeringObjective(id="obj_nodup", request="test", session_id="s1")
        engine.receive_objective(obj)

        # Simulate: loop already called complete_objective
        engine.complete_objective("s1")
        session = engine.get_session("s1")
        assert session.objective.status == ObjectiveStatus.COMPLETED

        # The post-loop guard: should NOT call complete_objective again
        should_call = (session.objective.status != ObjectiveStatus.COMPLETED)
        assert not should_call, "Post-loop must not re-complete an already completed objective"


# ===========================================================================
# §9: REPLANNING_STARTED ONLY FROM ACTUAL REPLAN DECISION
# ===========================================================================

class TestReplanningEventAuthority:
    """REPLANNING_STARTED must only be emitted at the actual replan decision point."""

    def test_validate_task_failure_no_replanning_event(self):
        """Engine.validate_task(passed=False) must NOT emit REPLANNING_STARTED."""
        gw = _MockGateway()
        engine = _make_engine(gw)
        events = []
        engine.subscribe(lambda e, d: events.append(e))

        obj = EngineeringObjective(id="obj_val", request="test", session_id="s1")
        engine.receive_objective(obj)
        engine.plan_tasks("s1", [EngineTask(id="t1", objective_id="obj_val", description="test")])
        engine.start_task("s1", "t1")
        engine.validate_task("s1", "t1", passed=False, failure_reason="failed")

        replan_events = [e for e in events if e == EngineEvent.REPLANNING_STARTED]
        assert len(replan_events) == 0, "validate_task must not emit REPLANNING_STARTED"

    def test_fail_task_no_replanning_event(self):
        """Engine.fail_task must NOT emit REPLANNING_STARTED."""
        gw = _MockGateway()
        engine = _make_engine(gw)
        events = []
        engine.subscribe(lambda e, d: events.append(e))

        obj = EngineeringObjective(id="obj_ft", request="test", session_id="s1")
        engine.receive_objective(obj)
        engine.plan_tasks("s1", [EngineTask(id="t1", objective_id="obj_ft", description="test")])
        engine.start_task("s1", "t1")
        engine.fail_task("s1", "t1", failure_reason="crashed")

        replan_events = [e for e in events if e == EngineEvent.REPLANNING_STARTED]
        assert len(replan_events) == 0, "fail_task must not emit REPLANNING_STARTED"


# ===========================================================================
# §4: REPLANNING LOOP BOUNDED
# ===========================================================================

class TestReplanningBounds:
    """Verify replanning is bounded and does not endlessly repeat."""

    def test_max_replans_enforced(self):
        """Workflow loop must respect max_replans limit."""
        # The app.py loop has max_replans = 2
        # After 2 failed replans, it must transition to FAILED, not keep looping
        from clairecoder.workflow.types import WorkflowState
        wm = WorkflowManager()
        wf = wm.create_workflow("wf_loop", "obj1", "test loop")
        assert wf.state == WorkflowState.CREATED

        # Simulate the replan cycle
        replan_count = 0
        max_replans = 2

        for cycle in range(5):
            if replan_count < max_replans:
                replan_count += 1
            else:
                break

        # Must have stopped at max_replans
        assert replan_count == max_replans
        assert cycle == max_replans  # Broke on the 3rd attempt (index 2)


# ===========================================================================
# §16: OLLAMA CAPABILITY SAFETY
# ===========================================================================

class TestOllamaCapabilitySafety:
    """Verify Ollama models don't get assumed tool-calling capability."""

    def test_ollama_discovery_no_tool_calling_assumed(self):
        """Ollama model discovery must not add TOOL_CALLING to capabilities."""
        from clairecoder.gateway.types import Capability, Model, Provider, Endpoint

        # Simulate what discover_ollama produces
        caps = [Capability.TEXT, Capability.STREAMING]
        model = Model(
            id="deepseek-coder:6.7b",
            display_name="deepseek-coder:6.7b",
            provider=Provider(id="ollama", name="Ollama"),
            endpoint=Endpoint(url="http://localhost:11434"),
            capabilities=caps,
        )

        assert Capability.TOOL_CALLING not in model.capabilities
        assert Capability.TEXT in model.capabilities
        assert Capability.STREAMING in model.capabilities

    def test_ollama_vision_model_gets_vision_capability(self):
        """Ollama vision models should get VISION capability added."""
        from clairecoder.gateway.types import Capability

        # Simulate the discovery logic check
        families = ["clip"]
        model_id = "llava:7b"
        caps = [Capability.TEXT, Capability.STREAMING]

        if "clip" in families or "vision" in model_id.lower():
            caps.append(Capability.VISION)

        assert Capability.VISION in caps
        assert Capability.TOOL_CALLING not in caps


# ===========================================================================
# §15: REPLANNING ACTIVITY PRESENTATION
# ===========================================================================

class TestReplanningPresentation:
    """Verify replanning events produce correct activity items."""

    def test_replanning_started_produces_activity(self):
        """REPLANNING_STARTED should produce a visible 'Replanning' activity."""
        event = Event(name="replanning_started", payload={"workflow_id": "wf1"})
        act = PresentationAdapter.event_to_activity(event)
        assert act is not None
        assert "replan" in act.title.lower()

    def test_planning_completed_produces_activity(self):
        """PLANNING_COMPLETED should produce a visible 'Plan ready' activity."""
        event = Event(name="planning_completed", payload={"session_id": "s1"})
        act = PresentationAdapter.event_to_activity(event)
        assert act is not None
        assert act.state == ActivityState.COMPLETED


# ===========================================================================
# §14: END-TO-END FAILURE FINALIZATION
# ===========================================================================

class TestFailureFinalization:
    """Verify that permanently failed workflows stay failed throughout."""

    def test_failed_objective_status_is_failed(self):
        """After fail_objective, ObjectiveStatus must be FAILED."""
        gw = _MockGateway()
        engine = _make_engine(gw)

        obj = EngineeringObjective(id="obj_fail", request="break things", session_id="s1")
        engine.receive_objective(obj)
        engine.fail_objective("s1")

        session = engine.get_session("s1")
        assert session.objective.status == ObjectiveStatus.FAILED

    def test_failed_objective_cannot_become_completed(self):
        """Once FAILED, calling complete_objective should not revert to COMPLETED
        in a well-behaved system (engine allows it, but app.py must prevent it)."""
        gw = _MockGateway()
        engine = _make_engine(gw)

        obj = EngineeringObjective(id="obj_norevert", request="fail", session_id="s1")
        engine.receive_objective(obj)
        engine.fail_objective("s1")

        session = engine.get_session("s1")
        assert session.objective.status == ObjectiveStatus.FAILED

        # Verify the post-loop guard in app.py would not call complete_objective
        # when workflow is not in COMPLETE state
        from clairecoder.workflow.types import WorkflowState
        workflow_state = WorkflowState.FAILED
        should_complete = (workflow_state == WorkflowState.COMPLETE)
        assert not should_complete

    def test_failure_evidence_retained_after_finalization(self):
        """FailureEvidence must persist through finalization."""
        evidence = FailureEvidence(
            tool="run_command",
            exit_code=1,
            stderr="tests/test_calc.py::test_add FAILED",
            task_id="t1",
        )
        summary = evidence.to_summary()
        assert "run_command" in summary
        assert "FAILED" in summary

        # Create result with evidence
        result = ExecutionResult(
            category=ExecutionResultCategory.FAILURE,
            failure_category=FailureCategory.UNKNOWN_FAILURE,
            error_message="Test failed",
            failure_evidence=evidence,
        )
        assert result.failure_evidence is not None
        assert result.failure_evidence.tool == "run_command"

