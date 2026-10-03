"""Dedicated Agent Runtime orchestrating the agent execution lifecycle.

Correction #14: Extracted from app.py to establish a clean boundary:
    APP          — composition, bootstrap, UI integration
    RUNTIME      — owns agent execution lifecycle (plan -> task loop -> verify -> result)
    TASK GRAPH   — owns task / dependency state
    PLANNER      — produces plans from objectives
    EXECUTOR     — executes tool/model actions for a task
    VERIFIER     — verifies whether task execution succeeded
    EVENT SYSTEM — reports structured runtime events (Correction #12)
    ROLES        — bounded role responsibilities (Correction #18)
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

from clairecoder.workspace.workspace import Workspace
from clairecoder.tools.registry import ToolRegistry
from clairecoder.tools.tool import ToolContext
from clairecoder.core.types import ToolResult, ToolState

from clairecoder.workflow.types import (
    Plan,
    PlanningError,
    PlanningLevel,
    Task,
    TaskState,
    TaskType,
    WorkflowState,
)
from clairecoder.workflow.task_graph import TaskGraph
from clairecoder.workflow.planner import Planner
from clairecoder.execution.types import (
    ExecutionResult,
    ExecutionResultCategory,
    ExecutionTask,
    FailureCategory,
    FailureEvidence,
)
from clairecoder.verification.types import (
    VerificationCriterion,
    VerificationResult,
    VerificationStatus,
    VerificationTestType,
)
from clairecoder.verification.verifier import Verifier, DefaultVerifier
from clairecoder.runtime.events import EventType, RuntimeEvent
from clairecoder.runtime.emitter import EventEmitter
from clairecoder.changeset.types import (
    ChangeSet,
    ChangeSetStatus,
    FileOperation,
)
from clairecoder.changeset.store import ChangeSetStore
from clairecoder.changeset.tracker import ChangeTracker
from clairecoder.runtime.roles import (
    Role,
    RoleContext,
    RoleResult,
    RoleRegistry,
    AgentRole,
    PlannerRole,
    ImplementerRole,
    VerifierRole,
    RecoveryRole,
)
from clairecoder.session.types import (
    ChangeSetReference,
    Session,
    SessionMetadata,
    SessionRunState,
    SessionStatus,
)
from clairecoder.session.store import SessionStore
from clairecoder.session.errors import (
    SessionCorruptedError,
    SessionError,
    SessionNotFoundError,
    SessionStorageError,
    UnsupportedSchemaVersionError,
)


# =============================================================================
# RUN RESULT (Section 10)
# =============================================================================

@dataclass
class RunResult:
    """Structured result returned by AgentRuntime.run().

    Enables programmatic inspection of run success, completion,
    failures, blocked tasks, verification results, and recovery.
    """
    success: bool
    run_id: str
    objective_id: str
    completed_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)
    blocked_tasks: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None
    task_graph: Optional[TaskGraph] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_success: bool = True
    verification_success: bool = True
    recovered_success: bool = False
    final_failure: bool = False
    verification_results: Dict[str, VerificationResult] = field(default_factory=dict)


# =============================================================================
# AGENT RUNTIME (Sections 3, 4, 8, 11, 12, 13, 14, 15)
# =============================================================================

class AgentRuntime:
    """Orchestrates agent execution lifecycle cleanly decoupled from presentation."""

    def __init__(
        self,
        planner: Optional[Planner] = None,
        executor: Optional[Any] = None,
        verifier: Optional[Any] = None,
        event_emitter: Optional[EventEmitter] = None,
        workflow_manager: Optional[Any] = None,
        execution_manager: Optional[Any] = None,
        engineering_engine: Optional[Any] = None,
        verification_engine: Optional[Any] = None,
        model_gateway: Optional[Any] = None,
        config_manager: Optional[Any] = None,
        workspace_root: Optional[str] = None,
        changeset_store: Optional[ChangeSetStore] = None,
        max_task_retries: int = 0,
        role_registry: Optional[RoleRegistry] = None,
        workspace: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        session_store: Optional[SessionStore] = None,
    ) -> None:
        self._planner = planner if planner is not None else Planner()
        self._executor = executor
        self._verifier = verifier
        self._event_emitter = event_emitter if event_emitter is not None else EventEmitter()
        self._workflow_manager = workflow_manager
        self._execution_manager = execution_manager
        self._engineering_engine = engineering_engine
        self._verification_engine = verification_engine or (verifier if hasattr(verifier, "create_verification") else None)
        self._model_gateway = model_gateway
        self._config_manager = config_manager

        # Workspace abstraction boundary (Correction #19)
        if workspace is not None:
            self._workspace = workspace
            self._workspace_root = str(self._workspace.root)
        elif workspace_root is not None:
            self._workspace = Workspace(workspace_root)
            self._workspace_root = str(self._workspace.root)
        else:
            self._workspace = Workspace(Path.cwd())
            self._workspace_root = str(self._workspace.root)

        # ToolRegistry boundary (Correction #19)
        if tool_registry is not None:
            self._tool_registry = tool_registry
        else:
            self._tool_registry = ToolRegistry.create_default(workspace=self._workspace)

        self._changeset_store = changeset_store if changeset_store is not None else ChangeSetStore()
        self._max_task_retries = max_task_retries
        self._role_registry = role_registry if role_registry is not None else self._build_default_registry()

        # SessionStore boundary (Correction #21)
        if session_store is not None:
            self._session_store = session_store
        else:
            self._session_store = SessionStore(workspace_root=self._workspace_root)

    @property
    def session_store(self) -> SessionStore:
        """Access the session store abstraction."""
        return self._session_store

    @property
    def event_emitter(self) -> EventEmitter:
        return self._event_emitter

    @property
    def planner(self) -> Planner:
        return self._planner

    @property
    def changeset_store(self) -> ChangeSetStore:
        return self._changeset_store

    @property
    def max_task_retries(self) -> int:
        return self._max_task_retries

    @property
    def role_registry(self) -> RoleRegistry:
        """Access the role registry for inspection or injection."""
        return self._role_registry

    @property
    def workspace(self) -> Workspace:
        """Access the workspace abstraction for safe project-root operations."""
        return self._workspace

    @property
    def tool_registry(self) -> ToolRegistry:
        """Access the tool registry."""
        return self._tool_registry

    def _build_default_registry(self) -> RoleRegistry:
        """Build a default role registry from current subsystem configuration."""
        registry = RoleRegistry()
        # Register roles from available subsystems
        if self._planner is not None:
            registry.register(Role.PLANNER, PlannerRole(self._planner))
        if self._executor is not None:
            registry.register(Role.IMPLEMENTER, ImplementerRole(self._executor))
        if self._verifier is not None:
            registry.register(Role.VERIFIER, VerifierRole(self._verifier))
        registry.register(Role.RECOVERY, RecoveryRole(
            max_task_retries=self._max_task_retries,
        ))
        return registry

    def execute_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> ToolResult:
        """Execute a tool via ToolRegistry with structured event emission and error containment (Correction #19 §7, §9).

        Emits:
            TOOL_STARTED -> tool.execute() -> TOOL_COMPLETED or TOOL_FAILED
        """
        r_run_id = run_id or getattr(context, "run_id", None)
        r_task_id = task_id or getattr(context, "task_id", None)

        safe_args = {
            k: (v if k != "content" or len(str(v)) <= 50 else f"<content {len(str(v))} chars>")
            for k, v in (arguments or {}).items()
        }

        # Emit TOOL_STARTED
        self._emit(
            EventType.TOOL_STARTED,
            run_id=r_run_id,
            task_id=r_task_id,
            payload={
                "tool": tool_name,
                "arguments": safe_args,
            },
        )

        # Resolve tool
        try:
            tool = self._tool_registry.resolve(tool_name)
        except Exception as e:
            self._emit(
                EventType.TOOL_FAILED,
                run_id=r_run_id,
                task_id=r_task_id,
                payload={
                    "tool": tool_name,
                    "success": False,
                    "error": str(e),
                },
            )
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"tool": tool_name, "error_type": type(e).__name__},
            )

        # Build context if needed
        t_ctx = context
        if t_ctx is None:
            t_ctx = ToolContext(
                run_id=r_run_id,
                task_id=r_task_id,
                workspace=self._workspace,
            )

        # Execute
        start_t = time.time()
        try:
            result = tool.execute(context=t_ctx, arguments=arguments)
        except Exception as e:
            duration = time.time() - start_t
            result = ToolResult(
                success=False,
                error=str(e),
                duration=duration,
                metadata={"tool": tool_name, "exception_type": type(e).__name__},
            )

        # Emit outcome
        if result.success:
            self._emit(
                EventType.TOOL_COMPLETED,
                run_id=r_run_id,
                task_id=r_task_id,
                payload={
                    "tool": tool_name,
                    "success": True,
                    "duration": result.duration,
                    "changed_files": result.changed_files,
                    "changeset_id": result.changeset_id,
                    "metadata": result.metadata,
                },
            )
        else:
            self._emit(
                EventType.TOOL_FAILED,
                run_id=r_run_id,
                task_id=r_task_id,
                payload={
                    "tool": tool_name,
                    "success": False,
                    "error": result.error,
                    "duration": result.duration,
                    "metadata": result.metadata,
                },
            )

        return result

    def invoke_role(
        self,
        role: Role,
        context: RoleContext,
        run_id: Optional[str] = None,
        objective_id: Optional[str] = None,
    ) -> RoleResult:
        """Invoke a role with structured event emission and failure isolation.

        Lifecycle:
            ROLE_STARTED -> role.execute(context) -> ROLE_COMPLETED or ROLE_FAILED

        Role failures are caught and returned as RoleResult(success=False).
        A role failure cannot produce a false-successful task or run.
        """
        r_run_id = run_id or context.run_id
        r_obj_id = objective_id or context.objective_id

        # Resolve role implementation
        try:
            impl = self._role_registry.resolve(role)
        except KeyError as e:
            return RoleResult(
                role=role,
                success=False,
                error=str(e),
            )

        # Emit ROLE_STARTED
        self._emit(
            EventType.ROLE_STARTED,
            run_id=r_run_id,
            objective_id=r_obj_id,
            task_id=context.task_id,
            payload={
                "role": role.value,
                "description": impl.description,
                **context.to_dict(),
            },
        )

        # Execute with failure isolation
        try:
            result = impl.execute(context)
        except Exception as e:
            result = RoleResult(
                role=role,
                success=False,
                error=str(e),
                evidence={"exception_type": type(e).__name__},
            )

        # Emit outcome
        if result.success:
            self._emit(
                EventType.ROLE_COMPLETED,
                run_id=r_run_id,
                objective_id=r_obj_id,
                task_id=context.task_id,
                payload={
                    "role": role.value,
                    "success": True,
                    **result.to_dict(),
                },
            )
        else:
            self._emit(
                EventType.ROLE_FAILED,
                run_id=r_run_id,
                objective_id=r_obj_id,
                task_id=context.task_id,
                payload={
                    "role": role.value,
                    "success": False,
                    "error": result.error,
                    **result.to_dict(),
                },
            )

        return result

    def _get_max_retries(self, task: Task, max_task_retries: int) -> int:
        """Resolve maximum allowed retries for a task."""
        if getattr(task, "max_retries", None) is not None:
            return task.max_retries  # type: ignore[return-value]
        return max_task_retries

    def _can_retry_task(self, task: Task, max_task_retries: int) -> bool:
        """Determine whether a task is eligible for retry."""
        limit = self._get_max_retries(task, max_task_retries)
        if limit <= 0:
            return False
        retries_done = max(0, task.attempts - 1)
        return retries_done < limit

    def _sync_session_changesets(self, session: Session) -> None:
        """Update session changeset references from changeset store (Correction #16, #21)."""
        all_cs = self._changeset_store.list_changesets()
        session.changesets = [
            ChangeSetReference(
                changeset_id=cs.id,
                task_id=cs.task_id,
                status=cs.status.value if hasattr(cs.status, "value") else str(cs.status),
                files_count=len(cs.files),
                additions=cs.total_additions,
                deletions=cs.total_deletions,
                created_at=cs.created_at,
            )
            for cs in all_cs
        ]

    def _checkpoint_session(
        self,
        session: Session,
        run_id: Optional[str] = None,
        graph: Optional[TaskGraph] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist session checkpoint and emit SESSION_CHECKPOINTED event (Correction #21 §5, §8)."""
        session.touch()
        if graph is not None:
            session.task_graph_state = graph.to_dict()
        if run_id:
            session.current_run_id = run_id

        # Update changeset references
        self._sync_session_changesets(session)

        # Attempt atomic filesystem persistence
        if self._session_store is not None:
            try:
                self._session_store.save(session)
            except Exception as e:
                # Structured error containment — persistence failure does not crash the runtime
                self._emit(
                    EventType.AGENT_ERROR,
                    session_id=session.session_id,
                    run_id=run_id or session.current_run_id,
                    payload={"error": f"Session checkpoint persistence failed: {e}", "details": str(e)},
                )

        # Emit SESSION_CHECKPOINTED
        payload = {
            "session_id": session.session_id,
            "status": session.status.value,
            "turn_count": session.turn_count,
            "current_task_id": session.current_task_id,
            "tasks_total": len(graph.tasks) if graph else 0,
            "tasks_completed": sum(1 for t in graph.tasks if t.status == TaskState.SUCCEEDED) if graph else 0,
        }
        if extra_payload:
            payload.update(extra_payload)

        self._emit(
            EventType.SESSION_CHECKPOINTED,
            session_id=session.session_id,
            run_id=run_id or session.current_run_id,
            payload=payload,
        )

    # =========================================================================
    # PRIMARY EXECUTION ENTRY POINT
    # =========================================================================

    def run(
        self,
        objective: Union[str, Any],
        session_id: Optional[str] = None,
        task_graph: Optional[TaskGraph] = None,
        max_cycles: int = 10,
        max_replans: int = 2,
        active_model: Optional[str] = None,
        run_id: Optional[str] = None,
        objective_id: Optional[str] = None,
        max_task_retries: Optional[int] = None,
    ) -> RunResult:
        """Run the engineering loop for an objective until complete, failed, or cancelled.

        Lifecycle:
            1. Emit RUN_STARTED
            2. PLAN (if task_graph not provided)
            3. TaskGraph get_ready_tasks() loop:
               - mark_started (TASK_STARTED)
               - execute (TOOL_STARTED, etc.)
               - if execution failed:
                   mark_failed (TASK_FAILED) -> blocks dependents
                   recovery / retry if permitted
               - if execution succeeded:
                   mark_executed -> mark_verifying
                   verify (VERIFICATION_STARTED / VERIFICATION_PASSED / VERIFICATION_FAILED)
                   if passed: mark_completed (TASK_COMPLETED) -> unlocks dependents
                   if failed: mark_failed (TASK_FAILED) -> blocks dependents -> recovery / retry
            4. Emit RUN_COMPLETED or RUN_FAILED
            5. Return structured RunResult
        """
        run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
        task_retries_limit = max_task_retries if max_task_retries is not None else self._max_task_retries

        # Resolve objective parameters
        if hasattr(objective, "id") and hasattr(objective, "request"):
            objective_id = objective_id or objective.id
            objective_req = objective.request
            session_id = session_id or getattr(objective, "session_id", None) or f"sess_{uuid.uuid4().hex[:8]}"
            if not active_model and getattr(objective, "model_profile_id", None):
                active_model = objective.model_profile_id
        else:
            objective_id = objective_id or f"obj_{uuid.uuid4().hex[:8]}"
            objective_req = str(objective)
            session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"

        workflow_id = f"wf_{session_id}"

        # Resolve model profile
        if not active_model:
            active_model = self._resolve_model(session_id)

        # Resolve or initialize session state (Correction #21)
        session: Optional[Session] = None
        if self._session_store:
            session = Session(
                session_id=session_id,
                workspace_root=self._workspace_root,
                original_objective=objective_req,
                status=SessionStatus.ACTIVE,
                metadata=SessionMetadata(active_model=active_model),
            )
            self._emit(
                EventType.SESSION_CREATED,
                session_id=session_id,
                run_id=run_id,
                objective_id=objective_id,
                payload={
                    "session_id": session_id,
                    "objective": objective_req,
                    "workspace_root": self._workspace_root,
                },
            )
            self._checkpoint_session(session, run_id=run_id, graph=task_graph)

        # 1. Emit RUN_STARTED
        self._emit(
            EventType.RUN_STARTED,
            session_id=session_id,
            run_id=run_id,
            objective_id=objective_id,
            payload={
                "run_id": run_id,
                "objective_id": objective_id,
                "session_id": session_id,
                "request": objective_req,
            },
        )

        if session:
            session.status = SessionStatus.ACTIVE
            session.current_run_id = run_id
            session.turn_count += 1
            self._checkpoint_session(session, run_id=run_id, graph=task_graph)

        # Context assembly & understanding via EngineeringEngine if present
        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.understand(session_id)
            except Exception as e:
                self._emit(
                    EventType.AGENT_ERROR,
                    session_id=session_id,
                    run_id=run_id,
                    payload={"error": f"Context assembly (understand) failed: {e}", "phase": "understand"},
                )

        # 2. Plan and initialize TaskGraph
        graph, plan = self._initialize_task_graph(
            objective_id=objective_id,
            objective_req=objective_req,
            workflow_id=workflow_id,
            session_id=session_id,
            run_id=run_id,
            active_model=active_model,
            provided_graph=task_graph,
        )

        if session:
            self._checkpoint_session(session, run_id=run_id, graph=graph)

        if plan is None and task_graph is None and graph.has_failures():
            # Planning failed fatally before execution started
            reason = graph.tasks[0].description if graph.tasks else "Planning failed"
            if session:
                session.status = SessionStatus.FAILED
                self._checkpoint_session(session, run_id=run_id, graph=graph)
                self._emit(
                    EventType.SESSION_FAILED,
                    session_id=session.session_id,
                    run_id=run_id,
                    objective_id=objective_id,
                    payload={"session_id": session.session_id, "reason": reason, "status": "failed"},
                )
            if self._workflow_manager:
                wf = self._workflow_manager.get_workflow(workflow_id)
                if wf and wf.state == WorkflowState.CREATED:
                    self._workflow_manager.transition_state(workflow_id, WorkflowState.CANCELLED)

            self._emit(
                EventType.RUN_FAILED,
                session_id=session_id,
                run_id=run_id,
                objective_id=objective_id,
                payload={
                    "run_id": run_id,
                    "objective_id": objective_id,
                    "reason": reason,
                    "failed_tasks": [t.id for t in graph.tasks if t.status == TaskState.FAILED],
                    "blocked_tasks": [t.id for t in graph.tasks if t.status == TaskState.BLOCKED],
                },
            )

            return self._build_result(
                success=False,
                run_id=run_id,
                objective_id=objective_id,
                graph=graph,
                failure_reason=reason,
            )

        # 3. Main Agent Execution Loop
        cycles = 0
        replan_count = 0
        has_recovered_attempts = False
        verification_results: Dict[str, VerificationResult] = {}

        try:
            while not graph.all_completed() and cycles < max_cycles:
                cycles += 1

                # Cancellation & interruption check
                if self._is_cancelled(session_id, objective):
                    if session:
                        session.status = SessionStatus.INTERRUPTED
                        self._checkpoint_session(session, run_id=run_id, graph=graph)
                        self._emit(
                            EventType.SESSION_INTERRUPTED,
                            session_id=session.session_id,
                            run_id=run_id,
                            objective_id=objective_id,
                            payload={"session_id": session.session_id, "reason": "Cancelled"},
                        )
                    self._emit(
                        EventType.RUN_CANCELLED,
                        session_id=session.session_id if session else session_id,
                        run_id=run_id,
                        objective_id=objective_id,
                        payload={"run_id": run_id, "objective_id": objective_id},
                    )
                    if self._engineering_engine and session_id:
                        self._engineering_engine.cancel_objective(session_id)
                    return self._build_result(
                        success=False,
                        run_id=run_id,
                        objective_id=objective_id,
                        graph=graph,
                        failure_reason="Execution interrupted or cancelled by user",
                        execution_success=False,
                        verification_success=False,
                        verification_results=verification_results,
                    )

                ready_tasks = graph.get_ready_tasks()

                if not ready_tasks:
                    if graph.has_failures():
                        # Check if replanning is allowed
                        if replan_count < max_replans and self._can_replan(has_provided_graph=(task_graph is not None)):
                            replan_count += 1
                            self._emit(
                                EventType.RECOVERY_STARTED,
                                session_id=session_id,
                                run_id=run_id,
                                objective_id=objective_id,
                                payload={
                                    "recovery_type": "replan",
                                    "replan_count": replan_count,
                                    "max_replans": max_replans,
                                },
                            )
                            self._emit(
                                EventType.REPLAN_STARTED,
                                session_id=session_id,
                                run_id=run_id,
                                objective_id=objective_id,
                                payload={
                                    "replan_count": replan_count,
                                    "max_replans": max_replans,
                                },
                            )
                            new_graph, new_plan = self._replan(
                                objective_req=objective_req,
                                objective_id=objective_id,
                                workflow_id=workflow_id,
                                session_id=session_id,
                                run_id=run_id,
                                active_model=active_model,
                                current_graph=graph,
                                current_plan=plan,
                                replan_count=replan_count,
                            )
                            if new_graph:
                                graph = new_graph
                                plan = new_plan
                                has_recovered_attempts = True
                                if session:
                                    session.recovery_state["replan"] = {
                                        "replan_count": replan_count,
                                        "status": "completed",
                                    }
                                    self._checkpoint_session(session, run_id=run_id, graph=new_graph)
                                continue
                            else:
                                self._emit(
                                    EventType.RECOVERY_FAILED,
                                    session_id=session_id,
                                    run_id=run_id,
                                    objective_id=objective_id,
                                    payload={
                                        "recovery_type": "replan",
                                        "replan_count": replan_count,
                                        "reason": "Replanning failed to generate a new graph",
                                    },
                                )
                                break
                        else:
                            # Replan budget exhausted or not permitted — terminal failure
                            if replan_count > 0 or has_recovered_attempts:
                                self._emit(
                                    EventType.RECOVERY_FAILED,
                                    session_id=session_id,
                                    run_id=run_id,
                                    objective_id=objective_id,
                                    payload={
                                        "recovery_type": "replan" if replan_count > 0 else "retry",
                                        "reason": "Recovery exhausted: all retries and replans completed without success",
                                    },
                                )
                            break
                    else:
                        # No ready tasks and no failures (e.g. empty or unresolvable)
                        break

                # Execute ready tasks in deterministic order
                for task in ready_tasks:
                    if self._is_cancelled(session_id, objective):
                        break

                    task_id = task.id

                    # Start Task in TaskGraph (increments attempts, emits TASK_STARTED)
                    graph.mark_started(task_id)
                    if session:
                        session.current_task_id = task_id
                        session.run_state.cycles = cycles
                        self._checkpoint_session(session, run_id=run_id, graph=graph)

                    # Sync with ExecutionManager and EngineeringEngine
                    attempt_num = task.attempts
                    exec_id = f"exec_{task_id}_{attempt_num}"
                    self._sync_task_start(task, session_id, workflow_id, exec_id, attempt_num)

                    # Capture workspace state BEFORE task execution (Correction #16, #19)
                    tracker = self._workspace.create_tracker()
                    tracker.capture_before()

                    # Execute Task via Executor
                    try:
                        exec_result = self._execute_task(task, session_id=session_id, attempt_number=attempt_num)
                    except Exception as e:
                        self._emit(
                            EventType.AGENT_ERROR,
                            session_id=session_id,
                            run_id=run_id,
                            task_id=task_id,
                            payload={"error": f"Task execution failed with uncaught exception: {e}", "phase": "execution"},
                        )
                        exec_result = ExecutionResult(
                            category=ExecutionResultCategory.FAILURE,
                            failure_category=FailureCategory.UNKNOWN_FAILURE,
                            error_message=str(e),
                            failure_evidence=FailureEvidence(task_id=task_id, reason=str(e)),
                            task_id=task_id,
                        )

                    # Capture workspace state AFTER task execution & calculate changeset (Correction #16)
                    changeset = tracker.capture_after(task_id=task_id, run_id=run_id)
                    if not exec_result.success:
                        changeset.status = ChangeSetStatus.FAILED
                    else:
                        changeset.status = ChangeSetStatus.APPLIED

                    self._changeset_store.record_changeset(changeset)
                    if session:
                        self._sync_session_changesets(session)
                        self._checkpoint_session(session, run_id=run_id, graph=graph)

                    # Expose changeset_id and changed files on ExecutionResult
                    exec_result.changeset_id = changeset.id
                    if changeset.files:
                        new_paths = [cf.path for cf in changeset.files]
                        if exec_result.changed_files:
                            all_paths = list(dict.fromkeys(exec_result.changed_files + new_paths))
                            exec_result.changed_files = all_paths
                        else:
                            exec_result.changed_files = new_paths

                    # Emit runtime events for changeset (only if files actually changed)
                    if changeset.files:
                        self._emit_changeset_events(
                            changeset=changeset,
                            run_id=run_id,
                            objective_id=objective_id,
                            task_id=task_id,
                        )

                    # --- Strict Gating: Check Execution Success ---
                    if not exec_result.success:
                        # Execution failed!
                        # DO NOT RUN VERIFICATION. Monotonic failure gating.
                        failure_detail = (
                            exec_result.failure_evidence.to_summary()
                            if exec_result.failure_evidence
                            else (exec_result.error_message or "Execution failed")
                        )
                        evidence_payload = {
                            "task_id": task_id,
                            "kind": "execution_failure",
                            "error": exec_result.error_message or "Execution failed",
                            "message": exec_result.error_message or "Execution failed",
                            "detail": failure_detail,
                            "evidence": failure_detail,
                            "attempt": attempt_num,
                            "changeset_id": changeset.id,
                            "affected_files": [cf.path for cf in changeset.files] if changeset.files else [],
                        }

                        # Mark failed in graph (emits TASK_FAILED, cascades BLOCKED to dependents)
                        graph.mark_failed(task_id, evidence=evidence_payload)

                        # Sync failure to execution manager and engine
                        self._sync_task_failure(task_id, session_id, exec_id, exec_result)

                        # Recovery: determine if retry is allowed
                        if self._can_retry_task(task, task_retries_limit):
                            has_recovered_attempts = True
                            max_retries_val = self._get_max_retries(task, task_retries_limit)
                            self._emit(
                                EventType.RECOVERY_STARTED,
                                session_id=session_id,
                                run_id=run_id,
                                objective_id=objective_id,
                                task_id=task_id,
                                payload={
                                    "task_id": task_id,
                                    "recovery_type": "retry",
                                    "attempt": attempt_num,
                                    "max_retries": max_retries_val,
                                    "failure": evidence_payload,
                                },
                            )
                            self._emit(
                                EventType.RETRY_STARTED,
                                session_id=session_id,
                                run_id=run_id,
                                objective_id=objective_id,
                                task_id=task_id,
                                payload={
                                    "task_id": task_id,
                                    "attempt": attempt_num + 1,
                                    "max_retries": max_retries_val,
                                },
                            )
                            graph.mark_retrying(task_id)
                            if session:
                                session.recovery_state[task_id] = {
                                    "action": "retry",
                                    "attempt": attempt_num + 1,
                                }
                                self._checkpoint_session(session, run_id=run_id, graph=graph)
                            continue
                        else:
                            if attempt_num > 1:
                                self._emit(
                                    EventType.RECOVERY_FAILED,
                                    session_id=session_id,
                                    run_id=run_id,
                                    objective_id=objective_id,
                                    task_id=task_id,
                                    payload={
                                        "task_id": task_id,
                                        "recovery_type": "retry",
                                        "attempt": attempt_num,
                                        "reason": f"Retry budget exhausted after {attempt_num} attempts",
                                        "failure": evidence_payload,
                                    },
                                )
                            continue

                    # --- Execution Succeeded -> Transition to EXECUTED then VERIFYING ---
                    graph.mark_executed(task_id)
                    graph.mark_verifying(task_id)

                    self._emit(
                        EventType.VERIFICATION_STARTED,
                        session_id=session_id,
                        run_id=run_id,
                        objective_id=objective_id,
                        task_id=task_id,
                        payload={
                            "task_id": task_id,
                            "title": task.title,
                            "changeset_id": changeset.id if changeset else None,
                        },
                    )
                    if self._workflow_manager:
                        wf = self._workflow_manager.get_workflow(workflow_id)
                        if wf and wf.state != WorkflowState.VALIDATING:
                            self._workflow_manager.transition_state(workflow_id, WorkflowState.VALIDATING)

                    try:
                        ver_result = self._verify_task(
                            task,
                            exec_result,
                            changeset=changeset,
                            session_id=session_id,
                            attempt_number=attempt_num,
                        )
                        passed = ver_result.success if hasattr(ver_result, "success") else bool(ver_result)
                    except Exception as e:
                        ver_result = VerificationResult(
                            task_id=task_id,
                            success=False,
                            status=VerificationStatus.FAILED,
                            failures=[str(e)],
                            evidence=[f"Verification error: {e}"],
                            changeset_id=changeset.id if changeset else None,
                        )
                        passed = False

                    if isinstance(ver_result, VerificationResult):
                        verification_results[task_id] = ver_result

                    if passed:
                        self._emit(
                            EventType.VERIFICATION_PASSED,
                            session_id=session_id,
                            run_id=run_id,
                            objective_id=objective_id,
                            task_id=task_id,
                            payload={
                                "task_id": task_id,
                                "passed": True,
                                "checks": getattr(ver_result, "checks", []),
                                "evidence": getattr(ver_result, "evidence", []),
                                "changeset_id": getattr(ver_result, "changeset_id", None),
                            },
                        )
                        self._emit(
                            EventType.VERIFICATION_COMPLETED,
                            session_id=session_id,
                            run_id=run_id,
                            objective_id=objective_id,
                            task_id=task_id,
                            payload={
                                "task_id": task_id,
                                "passed": True,
                                "checks": getattr(ver_result, "checks", []),
                            },
                        )
                        # Complete task in graph (emits TASK_COMPLETED, unlocks dependents to READY)
                        graph.mark_completed(task_id)
                        self._sync_task_success(task_id, session_id, exec_id, exec_result)
                        if session:
                            session.verification_state[task_id] = {
                                "status": "passed",
                                "attempt": task.attempts,
                            }
                            self._checkpoint_session(session, run_id=run_id, graph=graph)

                        if task.attempts > 1:
                            has_recovered_attempts = True
                            self._emit(
                                EventType.RECOVERY_COMPLETED,
                                session_id=session_id,
                                run_id=run_id,
                                objective_id=objective_id,
                                task_id=task_id,
                                payload={
                                    "task_id": task_id,
                                    "recovery_type": "retry",
                                    "attempt": task.attempts,
                                },
                            )
                    else:
                        failures_list = getattr(ver_result, "failures", []) or ["Verification failed"]
                        evidence_list = getattr(ver_result, "evidence", [])
                        self._emit(
                            EventType.VERIFICATION_FAILED,
                            session_id=session_id,
                            run_id=run_id,
                            objective_id=objective_id,
                            task_id=task_id,
                            payload={
                                "task_id": task_id,
                                "passed": False,
                                "failures": failures_list,
                                "evidence": evidence_list,
                                "changeset_id": getattr(ver_result, "changeset_id", None),
                            },
                        )
                        ver_evidence = {
                            "task_id": task_id,
                            "kind": "verification_failure",
                            "error": "; ".join(str(f) for f in failures_list) if failures_list else "Verification failed",
                            "message": "; ".join(str(f) for f in failures_list) if failures_list else "Verification failed",
                            "detail": str(ver_result),
                            "evidence": evidence_list or str(ver_result),
                            "failures": failures_list,
                            "attempt": attempt_num,
                            "changeset_id": changeset.id if changeset else None,
                            "affected_files": [cf.path for cf in changeset.files] if changeset and changeset.files else [],
                        }
                        exec_result.category = ExecutionResultCategory.FAILURE
                        exec_result.failure_category = FailureCategory.VALIDATION_FAILURE
                        # Mark failed in graph (emits TASK_FAILED, cascades BLOCKED to dependents)
                        graph.mark_failed(task_id, evidence=ver_evidence)
                        self._sync_task_verification_failure(task_id, session_id, exec_id, exec_result)
                        if session:
                            session.verification_state[task_id] = {
                                "status": "failed",
                                "failures": failures_list,
                                "attempt": task.attempts,
                            }
                            self._checkpoint_session(session, run_id=run_id, graph=graph)

                        # Recovery: determine if retry is allowed
                        if self._can_retry_task(task, task_retries_limit):
                            has_recovered_attempts = True
                            max_retries_val = self._get_max_retries(task, task_retries_limit)
                            self._emit(
                                EventType.RECOVERY_STARTED,
                                session_id=session_id,
                                run_id=run_id,
                                objective_id=objective_id,
                                task_id=task_id,
                                payload={
                                    "task_id": task_id,
                                    "recovery_type": "retry",
                                    "attempt": attempt_num,
                                    "max_retries": max_retries_val,
                                    "failure": ver_evidence,
                                },
                            )
                            self._emit(
                                EventType.RETRY_STARTED,
                                session_id=session_id,
                                run_id=run_id,
                                objective_id=objective_id,
                                task_id=task_id,
                                payload={
                                    "task_id": task_id,
                                    "attempt": attempt_num + 1,
                                    "max_retries": max_retries_val,
                                },
                            )
                            graph.mark_retrying(task_id)
                            if session:
                                session.recovery_state[task_id] = {
                                    "action": "retry",
                                    "attempt": attempt_num + 1,
                                }
                                self._checkpoint_session(session, run_id=run_id, graph=graph)
                            continue
                        else:
                            if attempt_num > 1:
                                self._emit(
                                    EventType.RECOVERY_FAILED,
                                    session_id=session_id,
                                    run_id=run_id,
                                    objective_id=objective_id,
                                    task_id=task_id,
                                    payload={
                                        "task_id": task_id,
                                        "recovery_type": "retry",
                                        "attempt": attempt_num,
                                        "reason": f"Retry budget exhausted after {attempt_num} attempts",
                                        "failure": ver_evidence,
                                    },
                                )
                            continue
        except KeyboardInterrupt:
            # Clean interruption handling (Correction #21 §7)
            if session:
                session.status = SessionStatus.INTERRUPTED
                self._checkpoint_session(session, run_id=run_id, graph=graph)
                self._emit(
                    EventType.SESSION_INTERRUPTED,
                    session_id=session.session_id,
                    run_id=run_id,
                    objective_id=objective_id,
                    payload={"session_id": session.session_id, "reason": "KeyboardInterrupt"},
                )
            self._emit(
                EventType.RUN_CANCELLED,
                session_id=session.session_id if session else session_id,
                run_id=run_id,
                objective_id=objective_id,
                payload={"run_id": run_id, "objective_id": objective_id, "reason": "Interrupted"},
            )
            return self._build_result(
                success=False,
                run_id=run_id,
                objective_id=objective_id,
                graph=graph,
                failure_reason="Execution interrupted by user (Ctrl+C)",
                execution_success=False,
                verification_success=False,
                verification_results=verification_results,
            )

        # 4. Final Completion Determination (Section 11)
        any_failed = any(t.status == TaskState.FAILED for t in graph.tasks)
        any_blocked = any(t.status == TaskState.BLOCKED for t in graph.tasks)
        is_complete = graph.all_completed() and graph.task_count > 0 and not any_failed and not any_blocked

        # Check explicit workflow completion criteria if WorkflowManager is configured
        if is_complete and self._workflow_manager:
            satisfied_reqs = []
            if self._verification_engine:
                for t in graph.tasks:
                    history = self._verification_engine.get_history(t.id)
                    for v in history:
                        if v.status == VerificationStatus.PASSED:
                            for c in v.criteria:
                                satisfied_reqs.append(c.description)

            is_complete = self._workflow_manager.check_completion(
                workflow_id,
                graph.tasks,
                satisfied_criteria=satisfied_reqs,
                satisfied_validations=satisfied_reqs,
            )

        if is_complete:
            if self._workflow_manager:
                wf = self._workflow_manager.get_workflow(workflow_id)
                if wf:
                    if wf.state != WorkflowState.VALIDATING:
                        self._workflow_manager.transition_state(workflow_id, WorkflowState.VALIDATING)
                    self._workflow_manager.transition_state(workflow_id, WorkflowState.COMPLETE)

            if self._engineering_engine and session_id:
                self._engineering_engine.complete_objective(session_id)

            if has_recovered_attempts or replan_count > 0:
                self._emit(
                    EventType.RECOVERY_COMPLETED,
                    session_id=session_id,
                    run_id=run_id,
                    objective_id=objective_id,
                    payload={
                        "recovery_type": "replan" if replan_count > 0 else "retry",
                        "replan_count": replan_count,
                        "status": "success",
                    },
                )

            if session:
                session.status = SessionStatus.COMPLETED
                session.current_task_id = None
                self._checkpoint_session(session, run_id=run_id, graph=graph)
                self._emit(
                    EventType.SESSION_COMPLETED,
                    session_id=session.session_id,
                    run_id=run_id,
                    objective_id=objective_id,
                    payload={"session_id": session.session_id, "status": "completed"},
                )

            self._emit(
                EventType.RUN_COMPLETED,
                session_id=session_id,
                run_id=run_id,
                objective_id=objective_id,
                payload={
                    "run_id": run_id,
                    "objective_id": objective_id,
                    "completed_tasks": [t.id for t in graph.tasks],
                },
            )

            return self._build_result(
                success=True,
                run_id=run_id,
                objective_id=objective_id,
                graph=graph,
                execution_success=True,
                verification_success=True,
                recovered_success=(has_recovered_attempts or replan_count > 0),
                verification_results=verification_results,
            )
        else:
            # Build failure reason from collected evidence
            failure_reasons = []
            for t in graph.tasks:
                if t.status == TaskState.FAILED:
                    for ev in t.failure_evidence:
                        if isinstance(ev, dict) and "error" in ev:
                            failure_reasons.append(str(ev["error"]))
                        elif isinstance(ev, dict) and "message" in ev:
                            failure_reasons.append(str(ev["message"]))
                        else:
                            failure_reasons.append(str(ev))
            reason = "; ".join(failure_reasons) if failure_reasons else "Run failed or blocked"

            final_exec_failed = any(
                t.status == TaskState.FAILED and any(
                    isinstance(ev, dict) and ev.get("kind") == "execution_failure" for ev in t.failure_evidence
                )
                for t in graph.tasks
            )
            final_ver_failed = any(
                t.status == TaskState.FAILED and any(
                    isinstance(ev, dict) and ev.get("kind") == "verification_failure" for ev in t.failure_evidence
                )
                for t in graph.tasks
            )

            if self._workflow_manager:
                wf = self._workflow_manager.get_workflow(workflow_id)
                if wf and wf.state != WorkflowState.COMPLETE:
                    # If blocked by unsatisfied criteria but tasks succeeded, or failures occurred
                    if cycles >= max_cycles and not graph.has_failures():
                        # Loop ended without completion (e.g. max_cycles reached before criteria met)
                        pass
                    else:
                        if wf.state != WorkflowState.FAILED:
                            self._workflow_manager.transition_state(workflow_id, WorkflowState.FAILED)

            if self._engineering_engine and session_id:
                if graph.has_failures():
                    self._engineering_engine.fail_objective(session_id)

            if session:
                session.status = SessionStatus.FAILED
                self._checkpoint_session(session, run_id=run_id, graph=graph)
                self._emit(
                    EventType.SESSION_FAILED,
                    session_id=session.session_id,
                    run_id=run_id,
                    objective_id=objective_id,
                    payload={
                        "session_id": session.session_id,
                        "reason": reason,
                        "status": "failed",
                    },
                )

            self._emit(
                EventType.RUN_FAILED,
                session_id=session_id,
                run_id=run_id,
                objective_id=objective_id,
                payload={
                    "run_id": run_id,
                    "objective_id": objective_id,
                    "reason": reason,
                    "failed_tasks": [t.id for t in graph.tasks if t.status == TaskState.FAILED],
                    "blocked_tasks": [t.id for t in graph.tasks if t.status == TaskState.BLOCKED],
                },
            )

            return self._build_result(
                success=False,
                run_id=run_id,
                objective_id=objective_id,
                graph=graph,
                failure_reason=reason,
                execution_success=not final_exec_failed,
                verification_success=not final_ver_failed,
                recovered_success=False,
                verification_results=verification_results,
            )

    # =========================================================================
    # RESUME BOUNDARY (Correction #21 §6)
    # =========================================================================

    def resume_session(
        self,
        session_id: str,
        max_cycles: int = 10,
        max_replans: int = 2,
        active_model: Optional[str] = None,
        max_task_retries: Optional[int] = None,
    ) -> RunResult:
        """Resume an existing persisted session.

        - Loads persisted Session from SessionStore (raising structured errors if missing/corrupt)
        - Reconstructs TaskGraph from session.task_graph_state
        - Preserves completed and verified tasks (never blindly re-executed)
        - Resets in-flight/interrupted tasks back to READY for safe resumption
        - Emits SESSION_RESUMED
        - Executes runtime loop from the persisted state
        """
        session = self._session_store.get(session_id)

        # Emit SESSION_RESUMED event
        self._emit(
            EventType.SESSION_RESUMED,
            session_id=session.session_id,
            run_id=session.current_run_id,
            payload={
                "session_id": session.session_id,
                "status": session.status.value,
                "turn_count": session.turn_count,
                "original_objective": session.original_objective,
            },
        )

        # Restore TaskGraph
        graph = None
        if session.task_graph_state:
            graph = TaskGraph.from_dict(
                session.task_graph_state,
                event_emitter=self._event_emitter,
                run_id=session.current_run_id,
            )

            # Sanitize in-flight / interrupted and blocked tasks:
            # Completed & verified tasks (SUCCEEDED) are preserved.
            # In-flight and blocked tasks are re-evaluated against dependencies.
            graph.sanitize_for_resume()

        # Mark session active again
        session.status = SessionStatus.ACTIVE
        self._checkpoint_session(session, graph=graph)

        # Continue execution with existing graph and session objective
        return self.run(
            objective=session.original_objective,
            session_id=session.session_id,
            task_graph=graph,
            max_cycles=max_cycles,
            max_replans=max_replans,
            active_model=active_model or session.metadata.active_model,
            max_task_retries=max_task_retries,
        )

    # =========================================================================
    # PLANNING BOUNDARY (Section 14)
    # =========================================================================

    def _initialize_task_graph(
        self,
        objective_id: str,
        objective_req: str,
        workflow_id: str,
        session_id: str,
        run_id: str,
        active_model: Optional[str],
        provided_graph: Optional[TaskGraph] = None,
    ) -> Tuple[TaskGraph, Optional[Plan]]:
        """Initialize or construct the TaskGraph."""
        if provided_graph is not None:
            if not provided_graph.is_finalized:
                provided_graph.finalize()
            return provided_graph, None

        # Workflow creation
        wf = None
        if self._workflow_manager:
            wf = self._workflow_manager.get_workflow(workflow_id)
            if wf and wf.state in (WorkflowState.COMPLETE, WorkflowState.CANCELLED, WorkflowState.FAILED):
                self._workflow_manager.remove_workflow(workflow_id)
                wf = None
            if not wf:
                wf = self._workflow_manager.create_workflow(workflow_id, objective_id, "Main workflow")

        self._emit(
            EventType.PLAN_STARTED,
            run_id=run_id,
            objective_id=objective_id,
            payload={"objective": objective_req},
        )

        model_resp = None
        if self._engineering_engine and active_model:
            use_structured = True
            if self._model_gateway and hasattr(self._model_gateway, "check_capability"):
                from clairecoder.gateway.types import Capability
                try:
                    use_structured = (
                        self._model_gateway.check_capability(active_model, Capability.STRUCTURED_OUTPUT)
                        or self._model_gateway.check_capability(active_model, Capability.JSON_SCHEMA)
                    )
                except Exception as e:
                    use_structured = True
                    self._emit(
                        EventType.AGENT_ERROR,
                        run_id=run_id,
                        payload={"error": f"Capability check failed, defaulting to structured: {e}", "phase": "planning"},
                    )

            req = self._planner.build_planning_request(
                objective=objective_req,
                planning_level=PlanningLevel.STRUCTURED,
                context_summary="Planning phase",
                model_id=active_model,
                use_structured_output=use_structured,
            )
            try:
                model_resp = self._engineering_engine.execute_model(req)
            except Exception as e:
                model_resp = None
                self._emit(
                    EventType.AGENT_ERROR,
                    run_id=run_id,
                    objective_id=objective_id,
                    payload={"error": f"Planning model execution failed: {e}", "phase": "planning"},
                )

        try:
            plan = self._planner.create_plan(
                workflow_id=workflow_id,
                objective=objective_req,
                planning_level=PlanningLevel.STRUCTURED,
                model_response=model_resp,
            )
        except PlanningError as pe:
            # Emit AGENT_ERROR for planning failure diagnostics.
            # Do NOT emit RUN_FAILED here — the caller (run()) is the single
            # authority for run lifecycle events (Fix #10: duplicate RUN_FAILED prevention).
            self._emit(
                EventType.AGENT_ERROR,
                run_id=run_id,
                objective_id=objective_id,
                payload={
                    "error": f"Planning failed: {pe}",
                    "phase": "planning",
                },
            )
            graph = TaskGraph(event_emitter=self._event_emitter, run_id=run_id)
            failed_task = Task(
                id=f"plan_failure_{run_id[-6:]}",
                objective_id=objective_id,
                title="Planning Failure",
                description=f"Planning failed: {pe}",
                type=TaskType.ANALYSIS,
                status=TaskState.FAILED,
                failure_evidence=[{"error": f"Planning failed: {pe}"}],
            )
            graph.add_task(failed_task)
            graph.finalize()
            return graph, None


        # Propagate plan completion criteria & validation strategy into workflow
        if wf:
            if plan.completion_criteria:
                wf.completion_criteria = list(plan.completion_criteria)
            if plan.validation_strategy:
                wf.validation_requirements = list(plan.validation_strategy)

        tasks = self._planner.create_tasks_from_plan(plan, objective_id)
        if not tasks:
            # Fallback default task if plan produced no tasks
            task_id = f"T1_{objective_id.replace('-', '')[:8]}"
            tasks = [
                Task(
                    id=task_id,
                    objective_id=objective_id,
                    title=objective_req,
                    description=objective_req,
                    type=TaskType.IMPLEMENTATION,
                )
            ]
            plan.task_ids = [task_id]

        graph = TaskGraph(
            event_emitter=self._event_emitter,
            run_id=run_id,
        )
        for t in tasks:
            graph.add_task(t)
        graph.finalize()

        # Sync to workflow manager and engine
        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.plan_tasks(session_id, tasks)
            except Exception as e:
                self._emit(
                    EventType.AGENT_ERROR,
                    run_id=run_id,
                    objective_id=objective_id,
                    payload={"error": f"Engine plan_tasks sync failed: {e}", "phase": "planning"},
                )

        if self._workflow_manager:
            self._workflow_manager.add_plan(plan)
            wf = self._workflow_manager.get_workflow(workflow_id)
            if wf and wf.state == WorkflowState.CREATED:
                self._workflow_manager.transition_state(workflow_id, WorkflowState.PLANNED)
                self._workflow_manager.transition_state(workflow_id, WorkflowState.ACTIVE)
            elif wf and wf.state == WorkflowState.PLANNED:
                self._workflow_manager.transition_state(workflow_id, WorkflowState.ACTIVE)

        self._emit(
            EventType.PLAN_CREATED,
            run_id=run_id,
            objective_id=objective_id,
            payload={"plan_id": plan.id, "task_ids": plan.task_ids},
        )

        return graph, plan

    # =========================================================================
    # TASK EXECUTION BOUNDARY (Section 15)
    # =========================================================================

    def _execute_task(
        self,
        task: Task,
        session_id: Optional[str] = None,
        attempt_number: int = 1,
    ) -> ExecutionResult:
        """Execute a task via executor boundary."""
        # 1. Custom executor passed to runtime
        if self._executor is not None:
            if hasattr(self._executor, "execute"):
                try:
                    res = self._executor.execute(task, session_id=session_id)
                except TypeError:
                    res = self._executor.execute(task)
            elif callable(self._executor):
                res = self._executor(task)
            else:
                raise TypeError(f"Unsupported executor: {type(self._executor)}")

            if isinstance(res, ExecutionResult):
                return res
            elif isinstance(res, bool):
                return ExecutionResult(
                    success=res,
                    task_id=task.id,
                    error_message="" if res else "Task execution failed",
                )
            elif isinstance(res, dict):
                return ExecutionResult(
                    success=res.get("success", True),
                    task_id=task.id,
                    error_message=res.get("error"),
                    outputs=res.get("outputs", []),
                )
            return ExecutionResult(success=True, task_id=task.id)

        # 2. EngineeringEngine interaction loop
        if self._engineering_engine is not None and session_id is not None:
            return self._engineering_engine.interaction_loop(session_id, task.id, max_iterations=5)

        # 3. Default fallback
        return ExecutionResult(success=True, task_id=task.id, outputs=["Default execution succeeded"])

    # =========================================================================
    # VERIFICATION BOUNDARY (Section 13)
    # =========================================================================

    def _verify_task(
        self,
        task: Task,
        exec_result: ExecutionResult,
        changeset: Optional[ChangeSet] = None,
        session_id: Optional[str] = None,
        attempt_number: int = 1,
    ) -> VerificationResult:
        """Verify task execution via verifier boundary."""
        changeset_id = getattr(changeset, "id", getattr(exec_result, "changeset_id", None))

        # 1. Custom verifier (object with .verify or callable)
        if self._verifier is not None and not hasattr(self._verifier, "create_verification"):
            if hasattr(self._verifier, "verify"):
                try:
                    v_res = self._verifier.verify(
                        task,
                        exec_result,
                        changeset=changeset,
                        session_id=session_id,
                        attempt_number=attempt_number,
                    )
                except TypeError:
                    v_res = self._verifier.verify(task, exec_result)
            elif callable(self._verifier):
                v_res = self._verifier(task, exec_result)
            else:
                raise TypeError(f"Unsupported verifier: {type(self._verifier)}")

            if isinstance(v_res, VerificationResult):
                if changeset_id and not v_res.changeset_id:
                    v_res.changeset_id = changeset_id
                return v_res

            if isinstance(v_res, bool):
                return VerificationResult(
                    task_id=task.id,
                    success=v_res,
                    status=VerificationStatus.PASSED if v_res else VerificationStatus.FAILED,
                    checks=["custom_verifier_bool"],
                    failures=[] if v_res else ["Verifier rejected task execution"],
                    evidence=["Custom verifier returned " + str(v_res)],
                    changeset_id=changeset_id,
                )

            if hasattr(v_res, "success"):
                is_success = bool(v_res.success)
                return VerificationResult(
                    task_id=task.id,
                    success=is_success,
                    status=getattr(v_res, "status", VerificationStatus.PASSED if is_success else VerificationStatus.FAILED),
                    checks=getattr(v_res, "checks", ["custom_verifier"]),
                    failures=getattr(v_res, "failures", [] if is_success else ["Verifier indicated failure"]),
                    evidence=getattr(v_res, "evidence", []),
                    changeset_id=changeset_id,
                    metadata=getattr(v_res, "metadata", {}),
                )

            if hasattr(v_res, "status"):
                is_passed = (v_res.status == VerificationStatus.PASSED)
                return VerificationResult(
                    task_id=task.id,
                    success=is_passed,
                    status=v_res.status,
                    checks=getattr(v_res, "checks", ["custom_verifier"]),
                    failures=getattr(v_res, "failures", [] if is_passed else ["Verification status not passed"]),
                    evidence=getattr(v_res, "evidence", []),
                    changeset_id=changeset_id,
                )

            return VerificationResult(
                task_id=task.id,
                success=True,
                status=VerificationStatus.PASSED,
                checks=["custom_verifier_object"],
                evidence=[str(v_res)],
                changeset_id=changeset_id,
            )

        # 2. VerificationEngine or DefaultVerifier
        v_engine = self._verification_engine or (self._verifier if hasattr(self._verifier, "create_verification") else None)
        default_verifier = DefaultVerifier(
            engine=v_engine,
            workspace_root=self._workspace_root,
        )
        return default_verifier.verify(
            task=task,
            execution_result=exec_result,
            changeset=changeset,
            session_id=session_id,
            attempt_number=attempt_number,
        )

    # =========================================================================
    # REPLANNING SUPPORT
    # =========================================================================

    def _can_replan(self, has_provided_graph: bool = False) -> bool:
        if has_provided_graph:
            return False
        return self._planner is not None

    def _replan(
        self,
        objective_req: str,
        objective_id: str,
        workflow_id: str,
        session_id: str,
        run_id: str,
        active_model: Optional[str],
        current_graph: TaskGraph,
        current_plan: Optional[Plan],
        replan_count: int,
    ) -> Tuple[Optional[TaskGraph], Optional[Plan]]:
        """Execute replanning when failures occur within replan budget."""
        if self._workflow_manager:
            wf = self._workflow_manager.get_workflow(workflow_id)
            if wf and wf.state in (WorkflowState.ACTIVE, WorkflowState.VALIDATING):
                self._workflow_manager.transition_state(workflow_id, WorkflowState.FAILED)
                self._workflow_manager.transition_state(workflow_id, WorkflowState.REPLANNING)
            elif wf and wf.state == WorkflowState.FAILED:
                self._workflow_manager.transition_state(workflow_id, WorkflowState.REPLANNING)

        # Emit replanning started
        self._emit(
            EventType.PLAN_UPDATED,
            run_id=run_id,
            objective_id=objective_id,
            payload={"replan_count": replan_count},
        )
        if self._engineering_engine:
            from clairecoder.engine.types import EngineEvent
            self._engineering_engine._emit(EngineEvent.REPLANNING_STARTED, {
                "workflow_id": workflow_id,
                "replan_count": replan_count,
            })

        # Collect failure evidence
        failure_evidence_parts = []
        for t in current_graph.tasks:
            if t.status == TaskState.FAILED:
                for ev in t.failure_evidence:
                    if isinstance(ev, dict) and "error" in ev:
                        failure_evidence_parts.append(ev["error"])
                    else:
                        failure_evidence_parts.append(str(ev))

        failure_reason = "; ".join(failure_evidence_parts) if failure_evidence_parts else "Execution or validation failed"

        if not current_plan:
            current_plan = Plan(
                id=f"plan_prev_{replan_count}",
                workflow_id=workflow_id,
                objective=objective_req,
                planning_level=PlanningLevel.STRUCTURED,
                task_ids=[t.id for t in current_graph.tasks],
            )

        model_resp = None
        if hasattr(self._planner, "build_replan_request"):
            use_structured = True
            if self._model_gateway and hasattr(self._model_gateway, "check_capability") and active_model:
                from clairecoder.gateway.types import Capability
                try:
                    use_structured = (
                        self._model_gateway.check_capability(active_model, Capability.STRUCTURED_OUTPUT)
                        or self._model_gateway.check_capability(active_model, Capability.JSON_SCHEMA)
                    )
                except Exception as e:
                    use_structured = True
                    self._emit(
                        EventType.AGENT_ERROR,
                        run_id=run_id,
                        payload={"error": f"Capability check failed in replan, defaulting to structured: {e}", "phase": "replanning"},
                    )

            try:
                req = self._planner.build_replan_request(
                    objective=objective_req,
                    previous_plan=current_plan,
                    failure_reason=failure_reason,
                    context_summary="Replanning phase",
                    model_id=active_model,
                    use_structured_output=use_structured,
                )
                if self._engineering_engine and active_model and req is not None:
                    model_resp = self._engineering_engine.execute_model(req)
            except Exception as e:
                model_resp = None
                self._emit(
                    EventType.AGENT_ERROR,
                    run_id=run_id,
                    objective_id=objective_id,
                    payload={"error": f"Replanning model execution failed: {e}", "phase": "replanning"},
                )

        try:
            new_plan = self._planner.create_plan(
                workflow_id=workflow_id,
                objective=objective_req,
                planning_level=PlanningLevel.STRUCTURED,
                model_response=model_resp,
                strict=True if model_resp is not None else False,
            )

            new_tasks = self._planner.create_tasks_from_plan(new_plan, objective_id)
            if not new_tasks:
                task_id = f"T{replan_count}_r{replan_count}_{objective_id.replace('-', '')[:8]}"
                new_tasks = [
                    Task(
                        id=task_id,
                        objective_id=objective_id,
                        title=f"Replan attempt {replan_count}: {objective_req}",
                        description=objective_req,
                        type=TaskType.IMPLEMENTATION,
                    )
                ]
                new_plan.task_ids = [task_id]

            new_graph = TaskGraph(event_emitter=self._event_emitter, run_id=run_id)
            for t in new_tasks:
                new_graph.add_task(t)
            new_graph.finalize()

            if self._engineering_engine and session_id:
                try:
                    self._engineering_engine.plan_tasks(session_id, new_tasks)
                except Exception as e:
                    self._emit(
                        EventType.AGENT_ERROR,
                        run_id=run_id,
                        objective_id=objective_id,
                        payload={"error": f"Engine replan sync failed: {e}", "phase": "replanning"},
                    )

            if self._workflow_manager:
                self._workflow_manager.add_plan(new_plan)
                self._workflow_manager.transition_state(workflow_id, WorkflowState.PLANNED)
                self._workflow_manager.transition_state(workflow_id, WorkflowState.ACTIVE)

            return new_graph, new_plan
        except PlanningError as pe:
            self._emit(
                EventType.AGENT_ERROR,
                run_id=run_id,
                objective_id=objective_id,
                payload={"error": f"Replanning plan generation failed: {pe}", "phase": "replanning"},
            )
            if self._workflow_manager:
                wf = self._workflow_manager.get_workflow(workflow_id)
                if wf and wf.state == WorkflowState.REPLANNING:
                    self._workflow_manager.transition_state(workflow_id, WorkflowState.FAILED)
            return None, None
        except Exception as e:
            self._emit(
                EventType.AGENT_ERROR,
                run_id=run_id,
                objective_id=objective_id,
                payload={"error": f"Replanning failed unexpectedly: {e}", "phase": "replanning"},
            )
            if self._workflow_manager:
                wf = self._workflow_manager.get_workflow(workflow_id)
                if wf and wf.state == WorkflowState.REPLANNING:
                    self._workflow_manager.transition_state(workflow_id, WorkflowState.FAILED)
            return None, None

    # =========================================================================
    # SUBSYSTEM SYNCHRONIZATION HELPERS
    # =========================================================================

    def _sync_task_start(self, task: Task, session_id: Optional[str], workflow_id: str, exec_id: str, attempt_num: int) -> None:
        """Synchronize task start state with ExecutionManager and EngineeringEngine."""
        if self._execution_manager:
            from clairecoder.execution.types import TaskState as ETaskState
            exec_t = self._execution_manager.get_task(task.id)
            if not exec_t:
                exec_t = ExecutionTask.from_workflow_task(task, workflow_id=workflow_id)
                self._execution_manager.register_task(exec_t)
            if exec_t.status in (ETaskState.PENDING, ETaskState.FAILED):
                self._execution_manager.transition_task(task.id, ETaskState.READY)
            if exec_t.status in (ETaskState.READY, ETaskState.PAUSED):
                try:
                    self._execution_manager.start_execution(task.id)
                except Exception as e:
                    self._emit(
                        EventType.AGENT_ERROR,
                        session_id=session_id,
                        task_id=task.id,
                        payload={"error": f"ExecutionManager start_execution sync failed: {e}", "phase": "sync"},
                    )

        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.start_task(session_id, task.id)
            except Exception as e:
                self._emit(
                    EventType.AGENT_ERROR,
                    session_id=session_id,
                    task_id=task.id,
                    payload={"error": f"EngineeringEngine start_task sync failed: {e}", "phase": "sync"},
                )

    def _sync_task_success(self, task_id: str, session_id: Optional[str], exec_id: str, exec_result: ExecutionResult) -> None:
        """Synchronize task success with ExecutionManager and EngineeringEngine."""
        if self._execution_manager:
            try:
                exec_t = self._execution_manager.get_task(task_id)
                attempt_id = exec_t.attempts[-1].execution_id if (exec_t and exec_t.attempts) else exec_id
                self._execution_manager.complete_execution(task_id, attempt_id, exec_result, is_verified=True)
            except Exception as e:
                self._emit(
                    EventType.AGENT_ERROR,
                    session_id=session_id,
                    task_id=task_id,
                    payload={"error": f"ExecutionManager complete_execution sync failed: {e}", "phase": "sync"},
                )

        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.validate_task(session_id, task_id, passed=True)
            except Exception as e:
                self._emit(
                    EventType.AGENT_ERROR,
                    session_id=session_id,
                    task_id=task_id,
                    payload={"error": f"EngineeringEngine validate_task sync failed: {e}", "phase": "sync"},
                )

    def _sync_task_failure(self, task_id: str, session_id: Optional[str], exec_id: str, exec_result: ExecutionResult) -> None:
        """Synchronize execution failure with ExecutionManager and EngineeringEngine."""
        if self._execution_manager:
            try:
                exec_t = self._execution_manager.get_task(task_id)
                attempt_id = exec_t.attempts[-1].execution_id if (exec_t and exec_t.attempts) else exec_id
                self._execution_manager.complete_execution(task_id, attempt_id, exec_result, is_verified=False)
            except Exception as e:
                self._emit(
                    EventType.AGENT_ERROR,
                    session_id=session_id,
                    task_id=task_id,
                    payload={"error": f"ExecutionManager complete_execution sync failed: {e}", "phase": "sync"},
                )

        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.fail_task(session_id, task_id, failure_reason=exec_result.error_message)
            except Exception as e:
                self._emit(
                    EventType.AGENT_ERROR,
                    session_id=session_id,
                    task_id=task_id,
                    payload={"error": f"EngineeringEngine fail_task sync failed: {e}", "phase": "sync"},
                )

    def _sync_task_verification_failure(self, task_id: str, session_id: Optional[str], exec_id: str, exec_result: ExecutionResult) -> None:
        """Synchronize verification failure with ExecutionManager and EngineeringEngine."""
        if self._execution_manager:
            try:
                exec_t = self._execution_manager.get_task(task_id)
                attempt_id = exec_t.attempts[-1].execution_id if (exec_t and exec_t.attempts) else exec_id
                self._execution_manager.complete_execution(task_id, attempt_id, exec_result, is_verified=False)
            except Exception as e:
                self._emit(
                    EventType.AGENT_ERROR,
                    session_id=session_id,
                    task_id=task_id,
                    payload={"error": f"ExecutionManager complete_execution sync failed: {e}", "phase": "sync"},
                )

        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.validate_task(session_id, task_id, passed=False, failure_reason="Verification failed")
            except Exception as e:
                self._emit(
                    EventType.AGENT_ERROR,
                    session_id=session_id,
                    task_id=task_id,
                    payload={"error": f"EngineeringEngine validate_task sync failed: {e}", "phase": "sync"},
                )

    def _is_cancelled(self, session_id: Optional[str], objective: Any) -> bool:
        """Check if execution has been cancelled."""
        from clairecoder.engine.types import ObjectiveStatus
        if hasattr(objective, "status") and objective.status in (
            ObjectiveStatus.PAUSED, ObjectiveStatus.CANCELLED, ObjectiveStatus.FAILED
        ):
            return True
        if self._engineering_engine and session_id:
            sess = self._engineering_engine.get_session(session_id)
            if sess and sess.objective and sess.objective.status in (
                ObjectiveStatus.PAUSED, ObjectiveStatus.CANCELLED, ObjectiveStatus.FAILED
            ):
                return True
        return False

    def _resolve_model(self, session_id: Optional[str]) -> Optional[str]:
        """Resolve active model ID."""
        if self._config_manager:
            active = self._config_manager.get_active()
            if active.get("model_id"):
                return active["model_id"]
        if self._engineering_engine and session_id:
            sess = self._engineering_engine.get_session(session_id)
            if sess and sess.model_profile:
                return sess.model_profile
        if self._model_gateway:
            if hasattr(self._model_gateway, "get_registered_model_ids"):
                mids = self._model_gateway.get_registered_model_ids()
                if mids:
                    return mids[0]
            if hasattr(self._model_gateway, "_models") and isinstance(self._model_gateway._models, dict) and self._model_gateway._models:
                return next(iter(self._model_gateway._models.keys()))
            if type(self._model_gateway).__name__ != "ModelGateway" and hasattr(self._model_gateway, "execute"):
                return "test-model"
        return None

    def _emit(
        self,
        event_type: EventType,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        objective_id: Optional[str] = None,
        task_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        changeset_id: Optional[str] = None,
    ) -> None:
        """Emit a structured RuntimeEvent via EventEmitter."""
        if self._event_emitter:
            try:
                sid = session_id or (payload.get("session_id") if payload else None)
                event = RuntimeEvent(
                    event_type=event_type,
                    session_id=sid,
                    run_id=run_id,
                    objective_id=objective_id,
                    task_id=task_id,
                    changeset_id=changeset_id,
                    payload=payload or {},
                )
                self._event_emitter.emit(event)
            except Exception as e:
                # Absolute last resort: event emission failure must not crash the runtime,
                # but must not be invisible either. Log to Python logger.
                logger.debug("Event emission failed for %s: %s", event_type, e)

    def _emit_changeset_events(
        self,
        changeset: ChangeSet,
        run_id: str,
        objective_id: str,
        task_id: str,
    ) -> None:
        """Emit structured runtime events for ChangeSet lifecycle and file mutations."""
        # 1. CHANGESET_CREATED
        self._emit(
            EventType.CHANGESET_CREATED,
            run_id=run_id,
            objective_id=objective_id,
            task_id=task_id,
            changeset_id=changeset.id,
            payload={
                "run_id": run_id,
                "task_id": task_id,
                "changeset_id": changeset.id,
                "file_count": len(changeset.files),
                "total_additions": changeset.total_additions,
                "total_deletions": changeset.total_deletions,
                "status": changeset.status.value,
            },
        )

        # 2. File-level events: FILE_CREATED, FILE_MODIFIED, FILE_DELETED
        for cf in changeset.files:
            if cf.operation == FileOperation.CREATED:
                event_type = EventType.FILE_CREATED
            elif cf.operation == FileOperation.MODIFIED:
                event_type = EventType.FILE_MODIFIED
            elif cf.operation == FileOperation.DELETED:
                event_type = EventType.FILE_DELETED
            else:
                event_type = EventType.FILE_MODIFIED

            self._emit(
                event_type,
                run_id=run_id,
                objective_id=objective_id,
                task_id=task_id,
                changeset_id=changeset.id,
                payload={
                    "run_id": run_id,
                    "task_id": task_id,
                    "changeset_id": changeset.id,
                    "path": cf.path,
                    "operation": cf.operation.value,
                    "additions": cf.additions,
                    "deletions": cf.deletions,
                    "existed_before": cf.existed_before,
                    "is_binary": cf.is_binary,
                },
            )

        # 3. CHANGESET_COMPLETED
        self._emit(
            EventType.CHANGESET_COMPLETED,
            run_id=run_id,
            objective_id=objective_id,
            task_id=task_id,
            changeset_id=changeset.id,
            payload={
                "run_id": run_id,
                "task_id": task_id,
                "changeset_id": changeset.id,
                "file_count": len(changeset.files),
                "total_additions": changeset.total_additions,
                "total_deletions": changeset.total_deletions,
                "status": changeset.status.value,
                "paths": [f.path for f in changeset.files],
            },
        )

    def _build_result(
        self,
        success: bool,
        run_id: str,
        objective_id: str,
        graph: TaskGraph,
        failure_reason: Optional[str] = None,
        execution_success: bool = True,
        verification_success: bool = True,
        recovered_success: bool = False,
        verification_results: Optional[Dict[str, VerificationResult]] = None,
    ) -> RunResult:
        """Construct the authoritative RunResult from TaskGraph state."""
        completed = [t.id for t in graph.tasks if t.status == TaskState.SUCCEEDED]
        failed = [t.id for t in graph.tasks if t.status == TaskState.FAILED]
        blocked = [t.id for t in graph.tasks if t.status == TaskState.BLOCKED]

        # Strict monotonic guarantee: a run can never be marked successful if
        # there are failed or blocked tasks, if graph is empty, or if verification/execution failed!
        if failed or blocked or not graph.all_completed() or graph.task_count == 0 or not verification_success or not execution_success:
            success = False

        return RunResult(
            success=success,
            run_id=run_id,
            objective_id=objective_id,
            completed_tasks=completed,
            failed_tasks=failed,
            blocked_tasks=blocked,
            failure_reason=failure_reason,
            task_graph=graph,
            execution_success=execution_success,
            verification_success=verification_success,
            recovered_success=recovered_success,
            final_failure=not success,
            verification_results=verification_results or {},
        )
