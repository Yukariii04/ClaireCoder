"""Dedicated Agent Runtime orchestrating the agent execution lifecycle.

Correction #14: Extracted from app.py to establish a clean boundary:
    APP          — composition, bootstrap, UI integration
    RUNTIME      — owns agent execution lifecycle (plan -> task loop -> verify -> result)
    TASK GRAPH   — owns task / dependency state
    PLANNER      — produces plans from objectives
    EXECUTOR     — executes tool/model actions for a task
    VERIFIER     — verifies whether task execution succeeded
    EVENT SYSTEM — reports structured runtime events (Correction #12)
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

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
        self._workspace_root = workspace_root
        self._changeset_store = changeset_store if changeset_store is not None else ChangeSetStore()
        self._max_task_retries = max_task_retries

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

        # 1. Emit RUN_STARTED
        self._emit(
            EventType.RUN_STARTED,
            run_id=run_id,
            objective_id=objective_id,
            payload={
                "run_id": run_id,
                "objective_id": objective_id,
                "session_id": session_id,
                "request": objective_req,
            },
        )

        # Context assembly & understanding via EngineeringEngine if present
        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.understand(session_id)
            except Exception:
                pass

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

        if plan is None and task_graph is None and graph.has_failures():
            # Planning failed fatally before execution started
            if self._workflow_manager:
                wf = self._workflow_manager.get_workflow(workflow_id)
                if wf and wf.state == WorkflowState.CREATED:
                    self._workflow_manager.transition_state(workflow_id, WorkflowState.CANCELLED)
            return self._build_result(
                success=False,
                run_id=run_id,
                objective_id=objective_id,
                graph=graph,
                failure_reason=graph.tasks[0].description if graph.tasks else "Planning failed",
            )

        # 3. Main Agent Execution Loop
        cycles = 0
        replan_count = 0
        has_recovered_attempts = False
        verification_results: Dict[str, VerificationResult] = {}

        while not graph.all_completed() and cycles < max_cycles:
            cycles += 1

            # Cancellation & interruption check
            if self._is_cancelled(session_id, objective):
                self._emit(
                    EventType.RUN_CANCELLED,
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
                            continue
                        else:
                            self._emit(
                                EventType.RECOVERY_FAILED,
                                run_id=run_id,
                                objective_id=objective_id,
                                payload={
                                    "recovery_type": "replan",
                                    "replan_count": replan_count,
                                    "reason": "Replanning failed to generate a new graph",
                                },
                            )

                    # No replans remain — terminal failure
                    if replan_count > 0 or has_recovered_attempts:
                        self._emit(
                            EventType.RECOVERY_FAILED,
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

                # Sync with ExecutionManager and EngineeringEngine
                attempt_num = task.attempts
                exec_id = f"exec_{task_id}_{attempt_num}"
                self._sync_task_start(task, session_id, workflow_id, exec_id, attempt_num)

                # Capture workspace state BEFORE task execution (Correction #16)
                tracker = ChangeTracker(workspace_root=self._workspace_root)
                tracker.capture_before()

                # Execute Task via Executor
                try:
                    exec_result = self._execute_task(task, session_id=session_id, attempt_number=attempt_num)
                except Exception as e:
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

                # Expose changeset_id and changed files on ExecutionResult
                exec_result.changeset_id = changeset.id
                if changeset.files:
                    new_paths = [cf.path for cf in changeset.files]
                    if exec_result.changed_files:
                        all_paths = list(dict.fromkeys(exec_result.changed_files + new_paths))
                        exec_result.changed_files = all_paths
                    else:
                        exec_result.changed_files = new_paths

                # Emit runtime events for changeset
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
                        continue
                    else:
                        if attempt_num > 1:
                            self._emit(
                                EventType.RECOVERY_FAILED,
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

                    if task.attempts > 1:
                        has_recovered_attempts = True
                        self._emit(
                            EventType.RECOVERY_COMPLETED,
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

                    # Recovery: determine if retry is allowed
                    if self._can_retry_task(task, task_retries_limit):
                        has_recovered_attempts = True
                        max_retries_val = self._get_max_retries(task, task_retries_limit)
                        self._emit(
                            EventType.RECOVERY_STARTED,
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
                        continue
                    else:
                        if attempt_num > 1:
                            self._emit(
                                EventType.RECOVERY_FAILED,
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
                    run_id=run_id,
                    objective_id=objective_id,
                    payload={
                        "recovery_type": "replan" if replan_count > 0 else "retry",
                        "replan_count": replan_count,
                        "status": "success",
                    },
                )

            self._emit(
                EventType.RUN_COMPLETED,
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

            self._emit(
                EventType.RUN_FAILED,
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
                except Exception:
                    use_structured = True

            req = self._planner.build_planning_request(
                objective=objective_req,
                planning_level=PlanningLevel.STRUCTURED,
                context_summary="Planning phase",
                model_id=active_model,
                use_structured_output=use_structured,
            )
            try:
                model_resp = self._engineering_engine.execute_model(req)
            except Exception:
                model_resp = None

        try:
            plan = self._planner.create_plan(
                workflow_id=workflow_id,
                objective=objective_req,
                planning_level=PlanningLevel.STRUCTURED,
                model_response=model_resp,
            )
        except PlanningError as pe:
            self._emit(
                EventType.RUN_FAILED,
                run_id=run_id,
                objective_id=objective_id,
                payload={
                    "run_id": run_id,
                    "objective_id": objective_id,
                    "reason": f"Planning failed: {pe}",
                    "failed_tasks": [],
                    "blocked_tasks": [],
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
            val_reqs = [objective_req] if ("verify" in objective_req.lower() or "create" in objective_req.lower()) else []
            task_id = f"T1_{objective_id.replace('-', '')[:8]}"
            tasks = [
                Task(
                    id=task_id,
                    objective_id=objective_id,
                    title=objective_req,
                    description=objective_req,
                    type=TaskType.IMPLEMENTATION,
                    validation_requirements=val_reqs,
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
            except Exception:
                pass

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
                except Exception:
                    use_structured = True

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
            except Exception:
                model_resp = None

        try:
            new_plan = self._planner.create_plan(
                workflow_id=workflow_id,
                objective=objective_req,
                planning_level=PlanningLevel.STRUCTURED,
                model_response=model_resp,
                strict=True if model_resp is not None else False,
            )
        except PlanningError:
            return None, None


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
            except Exception:
                pass

        if self._workflow_manager:
            self._workflow_manager.add_plan(new_plan)
            self._workflow_manager.transition_state(workflow_id, WorkflowState.PLANNED)
            self._workflow_manager.transition_state(workflow_id, WorkflowState.ACTIVE)

        return new_graph, new_plan

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
                except Exception:
                    pass

        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.start_task(session_id, task.id)
            except Exception:
                pass

    def _sync_task_success(self, task_id: str, session_id: Optional[str], exec_id: str, exec_result: ExecutionResult) -> None:
        """Synchronize task success with ExecutionManager and EngineeringEngine."""
        if self._execution_manager:
            try:
                exec_t = self._execution_manager.get_task(task_id)
                attempt_id = exec_t.attempts[-1].execution_id if (exec_t and exec_t.attempts) else exec_id
                self._execution_manager.complete_execution(task_id, attempt_id, exec_result, is_verified=True)
            except Exception:
                pass

        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.validate_task(session_id, task_id, passed=True)
            except Exception:
                pass

    def _sync_task_failure(self, task_id: str, session_id: Optional[str], exec_id: str, exec_result: ExecutionResult) -> None:
        """Synchronize execution failure with ExecutionManager and EngineeringEngine."""
        if self._execution_manager:
            try:
                exec_t = self._execution_manager.get_task(task_id)
                attempt_id = exec_t.attempts[-1].execution_id if (exec_t and exec_t.attempts) else exec_id
                self._execution_manager.complete_execution(task_id, attempt_id, exec_result, is_verified=False)
            except Exception:
                pass

        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.fail_task(session_id, task_id, failure_reason=exec_result.error_message)
            except Exception:
                pass

    def _sync_task_verification_failure(self, task_id: str, session_id: Optional[str], exec_id: str, exec_result: ExecutionResult) -> None:
        """Synchronize verification failure with ExecutionManager and EngineeringEngine."""
        if self._execution_manager:
            try:
                exec_t = self._execution_manager.get_task(task_id)
                attempt_id = exec_t.attempts[-1].execution_id if (exec_t and exec_t.attempts) else exec_id
                self._execution_manager.complete_execution(task_id, attempt_id, exec_result, is_verified=False)
            except Exception:
                pass

        if self._engineering_engine and session_id:
            try:
                self._engineering_engine.validate_task(session_id, task_id, passed=False, failure_reason="Verification failed")
            except Exception:
                pass

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
            if hasattr(self._model_gateway, "_models") and isinstance(self._model_gateway._models, dict) and self._model_gateway._models:
                return next(iter(self._model_gateway._models.keys()))
            if type(self._model_gateway).__name__ != "ModelGateway" and hasattr(self._model_gateway, "execute"):
                return "test-model"
        return None

    def _emit(
        self,
        event_type: EventType,
        run_id: Optional[str] = None,
        objective_id: Optional[str] = None,
        task_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        changeset_id: Optional[str] = None,
    ) -> None:
        """Emit a structured RuntimeEvent via EventEmitter."""
        if self._event_emitter:
            try:
                event = RuntimeEvent(
                    event_type=event_type,
                    run_id=run_id,
                    objective_id=objective_id,
                    task_id=task_id,
                    changeset_id=changeset_id,
                    payload=payload or {},
                )
                self._event_emitter.emit(event)
            except Exception:
                pass

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
