"""Structured Task Graph for dependency-aware task execution.

CC-PRD-004 Section 8: Task model and dependency representation.
CC-ADR-004 Section 5–8: Workflow architecture, task state machine.
Correction #13: Real task graph managing task lifecycle, dependency
resolution, ready-task calculation, and failure propagation.

The TaskGraph:
- Owns task state within a single plan/workflow context
- Validates dependency integrity (unknown, self, circular)
- Calculates ready tasks deterministically
- Tracks attempts and failure evidence
- Emits RuntimeEvent for task lifecycle via EventEmitter and/or callbacks
- Does NOT own workflow state or overall run orchestration
"""

from typing import Any, Callable, Dict, List, Optional, Set, Union

from .types import (
    Task,
    TaskState,
    TaskType,
    TaskGraphError,
    DependencyCycleError,
    DependencyNotFoundError,
    InvalidDependencyError,
)


class TaskGraph:
    """Manages tasks, dependencies, and execution readiness.

    Usage:
        graph = TaskGraph()
        graph.add_task(task_a)
        graph.add_task(task_b)  # depends on task_a
        graph.finalize()        # validates dependencies, sets initial states

        ready = graph.get_ready_tasks()  # [task_a]
        graph.mark_started(task_a.id)
        graph.mark_completed(task_a.id)

        ready = graph.get_ready_tasks()  # [task_b]

    Events:
        Emits task.started, task.completed, task.failed, task.retrying
        via EventEmitter (RuntimeEvent) and/or optional event_callback.
    """

    def __init__(
        self,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        event_emitter: Optional[Any] = None,
        run_id: Optional[str] = None,
    ) -> None:
        self._tasks: Dict[str, Task] = {}
        self._insertion_order: List[str] = []
        self._finalized: bool = False
        self._run_id = run_id

        # Support EventEmitter passed as either parameter
        try:
            from clairecoder.runtime.emitter import EventEmitter
            if isinstance(event_callback, EventEmitter):
                self._event_emitter = event_callback
                self._event_callback = None
            else:
                self._event_emitter = event_emitter
                self._event_callback = event_callback
        except ImportError:
            self._event_emitter = event_emitter
            self._event_callback = event_callback

    # =========================================================================
    # TASK MANAGEMENT
    # =========================================================================

    def add_task(self, task: Task) -> None:
        """Add a task to the graph.

        Raises:
            TaskGraphError: If the task ID already exists.
            InvalidDependencyError: If the task depends on itself.
        """
        if task.id in self._tasks:
            raise TaskGraphError(
                f"Duplicate task ID '{task.id}' — task IDs must be unique"
            )
        if task.id in task.dependencies:
            raise InvalidDependencyError(
                f"Task '{task.id}' cannot depend on itself"
            )

        # Set initial status based on dependencies
        if not task.dependencies and task.status == TaskState.PENDING:
            task.status = TaskState.READY

        self._tasks[task.id] = task
        self._insertion_order.append(task.id)
        self._finalized = False

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by ID."""
        return self._tasks.get(task_id)

    @property
    def tasks(self) -> List[Task]:
        """All tasks in insertion order."""
        return [self._tasks[tid] for tid in self._insertion_order]

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def is_finalized(self) -> bool:
        return self._finalized

    # =========================================================================
    # FINALIZATION & VALIDATION
    # =========================================================================

    def validate(self) -> None:
        """Check all dependency relationships for validity.

        Raises:
            DependencyNotFoundError: A dependency references an unknown task.
            InvalidDependencyError: A task depends on itself.
            DependencyCycleError: Circular dependency detected.
        """
        task_ids: Set[str] = set(self._tasks.keys())

        for task in self._tasks.values():
            for dep_id in task.dependencies:
                if dep_id == task.id:
                    raise InvalidDependencyError(
                        f"Task '{task.id}' cannot depend on itself"
                    )
                if dep_id not in task_ids:
                    raise DependencyNotFoundError(
                        f"Task '{task.id}' depends on '{dep_id}' which does not exist"
                    )

        # Cycle detection via DFS
        self._detect_cycles()

    def finalize(self) -> None:
        """Validate dependencies and set initial task states.

        After finalization:
        - Tasks with no unresolved dependencies become READY
        - Tasks with dependencies remain PENDING
        """
        self.validate()
        self._set_initial_states()
        self._finalized = True

    def _detect_cycles(self) -> None:
        """Detect circular dependencies using DFS with recursion tracking."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def _dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            task = self._tasks[node]
            for dep_id in sorted(task.dependencies):
                if dep_id not in visited:
                    _dfs(dep_id, path)
                elif dep_id in rec_stack:
                    cycle_start = path.index(dep_id)
                    cycle_path = " -> ".join(path[cycle_start:] + [dep_id])
                    raise DependencyCycleError(
                        f"Dependency cycle detected in task graph: {cycle_path}"
                    )

            rec_stack.remove(node)
            path.pop()

        for tid in sorted(self._tasks.keys()):
            if tid not in visited:
                _dfs(tid, [])

    def _set_initial_states(self) -> None:
        """Set tasks with no dependencies to READY, others to PENDING."""
        for task in self._tasks.values():
            if task.status in (TaskState.SUCCEEDED, TaskState.FAILED,
                               TaskState.CANCELLED, TaskState.RUNNING):
                # Preserve terminal/active states (e.g. restored from session)
                continue
            if not task.dependencies:
                task.status = TaskState.READY
            else:
                task.status = TaskState.PENDING

    # =========================================================================
    # DEPENDENCY & READY TASK CALCULATION
    # =========================================================================

    def dependencies_satisfied(self, task_id: str) -> bool:
        """Check if all dependencies for a task are completed.

        Returns True if all dependencies are in SUCCEEDED state,
        or if the task has no dependencies.

        Raises:
            TaskGraphError: If task_id does not exist.
        """
        task = self._require_task(task_id)
        if not task.dependencies:
            return True
        return all(
            self._tasks[dep_id].status == TaskState.SUCCEEDED
            for dep_id in task.dependencies
            if dep_id in self._tasks
        )

    def get_ready_tasks(self) -> List[Task]:
        """Return tasks eligible for execution in deterministic order.

        A task is READY when:
        - It is in READY state, OR
        - It is PENDING and all dependencies are SUCCEEDED

        A task is BLOCKED (not ready) when any dependency is FAILED or CANCELLED.

        Returns tasks sorted by insertion order for determinism.
        """
        # If not explicitly finalized, finalize/validate first
        if not self._finalized:
            self.finalize()

        # Update pending/blocked states based on latest dependency states
        self._update_pending_states()

        ready: List[Task] = []
        for tid in self._insertion_order:
            task = self._tasks[tid]
            if task.status == TaskState.READY:
                ready.append(task)

        return ready

    def _update_pending_states(self) -> None:
        """Re-evaluate PENDING and BLOCKED tasks against dependency states."""
        for tid in self._insertion_order:
            task = self._tasks[tid]
            if task.status not in (TaskState.PENDING, TaskState.BLOCKED):
                continue

            dep_states = [
                self._tasks[d].status
                for d in task.dependencies
                if d in self._tasks
            ]

            # Any dependency failed/cancelled/blocked → block this task
            if any(s in (TaskState.FAILED, TaskState.CANCELLED, TaskState.BLOCKED)
                   for s in dep_states):
                task.status = TaskState.BLOCKED
                continue

            # All dependencies succeeded → ready
            if all(s == TaskState.SUCCEEDED for s in dep_states):
                task.status = TaskState.READY
            else:
                # Still waiting on pending/ready/running dependencies
                task.status = TaskState.PENDING

    # =========================================================================
    # LIFECYCLE TRANSITIONS
    # =========================================================================

    def mark_started(self, task_id: str) -> None:
        """Mark a task as started (READY → RUNNING).

        Increments attempt count and emits TASK_STARTED event.
        """
        task = self._require_task(task_id)

        # Auto-promote to READY if pending with dependencies satisfied
        if task.status == TaskState.PENDING and self.dependencies_satisfied(task_id):
            task.status = TaskState.READY

        if task.status != TaskState.READY:
            raise TaskGraphError(
                f"Cannot start task '{task_id}': status is {task.status.value}, expected READY"
            )

        task.status = TaskState.RUNNING
        task.attempts += 1

        self._emit("task.started", {
            "task_id": task_id,
            "title": task.title or task.description,
            "description": task.description,
            "attempt": task.attempts,
            "type": task.type.value,
        })

    def mark_executed(self, task_id: str) -> None:
        """Mark a task as executed (RUNNING → EXECUTED).

        Correction #17: Explicit state indicating execution completed
        prior to verification evaluation.
        """
        task = self._require_task(task_id)
        if task.status != TaskState.RUNNING:
            raise TaskGraphError(
                f"Cannot mark task '{task_id}' executed: status is {task.status.value}, expected RUNNING"
            )
        task.status = TaskState.EXECUTED

    def mark_verifying(self, task_id: str) -> None:
        """Mark a task as actively undergoing verification (RUNNING or EXECUTED → VERIFYING).

        Correction #17: Explicit state during verifier evaluation.
        """
        task = self._require_task(task_id)
        if task.status not in (TaskState.RUNNING, TaskState.EXECUTED):
            raise TaskGraphError(
                f"Cannot mark task '{task_id}' verifying: status is {task.status.value}, expected RUNNING or EXECUTED"
            )
        task.status = TaskState.VERIFYING

    def mark_completed(self, task_id: str) -> None:
        """Mark a task as completed (RUNNING / EXECUTED / VERIFYING → SUCCEEDED).

        Triggers re-evaluation of dependent tasks.
        """
        task = self._require_task(task_id)

        if task.status not in (TaskState.RUNNING, TaskState.EXECUTED, TaskState.VERIFYING):
            raise TaskGraphError(
                f"Cannot complete task '{task_id}': status is {task.status.value}, expected RUNNING, EXECUTED, or VERIFYING"
            )

        task.status = TaskState.SUCCEEDED

        self._emit("task.completed", {
            "task_id": task_id,
            "title": task.title or task.description,
            "description": task.description,
        })

        # Re-evaluate pending dependents
        self._update_pending_states()

    def mark_failed(
        self,
        task_id: str,
        evidence: Optional[Union[Dict[str, Any], List[Dict[str, Any]], str]] = None,
    ) -> None:
        """Mark a task as failed (RUNNING / EXECUTED / VERIFYING → FAILED).

        Preserves failure evidence and propagates BLOCKED to dependents.
        """
        task = self._require_task(task_id)

        if task.status not in (TaskState.RUNNING, TaskState.EXECUTED, TaskState.VERIFYING):
            raise TaskGraphError(
                f"Cannot fail task '{task_id}': status is {task.status.value}, expected RUNNING, EXECUTED, or VERIFYING"
            )

        task.status = TaskState.FAILED
        if evidence is not None:
            if isinstance(evidence, list):
                task.failure_evidence.extend(evidence)
            elif isinstance(evidence, dict):
                task.failure_evidence.append(evidence)
            else:
                task.failure_evidence.append({"error": str(evidence)})

        self._emit("task.failed", {
            "task_id": task_id,
            "title": task.title or task.description,
            "description": task.description,
            "failure_evidence": task.failure_evidence,
        })

        # Propagate blocked state to dependents
        self._update_pending_states()

    def mark_retrying(self, task_id: str) -> None:
        """Mark a failed task for retry (FAILED → READY).

        Emits TASK_RETRYING event and re-evaluates blocked dependents.
        """
        task = self._require_task(task_id)

        if task.status != TaskState.FAILED:
            raise TaskGraphError(
                f"Cannot retry task '{task_id}': status is {task.status.value}, expected FAILED"
            )

        task.status = TaskState.READY

        self._emit("task.retrying", {
            "task_id": task_id,
            "title": task.title or task.description,
            "attempt": task.attempts,
        })

        # Re-evaluate dependents (unblocks dependents if no other failed deps)
        self._update_pending_states()

    def mark_cancelled(self, task_id: str) -> None:
        """Mark a task as cancelled."""
        task = self._require_task(task_id)
        task.status = TaskState.CANCELLED

        # Block dependents
        self._update_pending_states()

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def all_completed(self) -> bool:
        """Check if all tasks are in terminal success state."""
        return all(
            t.status == TaskState.SUCCEEDED for t in self._tasks.values()
        )

    def has_failures(self) -> bool:
        """Check if any task is in FAILED or BLOCKED state."""
        return any(
            t.status in (TaskState.FAILED, TaskState.BLOCKED)
            for t in self._tasks.values()
        )

    def get_blocked_tasks(self) -> List[Task]:
        """Return tasks blocked by failed dependencies."""
        return [
            t for tid in self._insertion_order
            if (t := self._tasks[tid]).status == TaskState.BLOCKED
        ]

    def get_blocking_reasons(self, task_id: str) -> List[str]:
        """Return IDs of failed/cancelled dependencies blocking a task."""
        task = self._require_task(task_id)
        reasons: List[str] = []
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if dep and dep.status in (TaskState.FAILED, TaskState.CANCELLED, TaskState.BLOCKED):
                reasons.append(dep_id)
        return reasons

    def topological_order(self) -> List[str]:
        """Return task IDs in topological (dependency-respecting) order.

        Deterministic: uses sorted insertion order for tie-breaking.
        """
        in_degree: Dict[str, int] = {tid: 0 for tid in self._tasks}
        adjacency: Dict[str, List[str]] = {tid: [] for tid in self._tasks}

        for task in self._tasks.values():
            for dep_id in task.dependencies:
                adjacency[dep_id].append(task.id)
                in_degree[task.id] += 1

        queue: List[str] = sorted(
            [tid for tid, deg in in_degree.items() if deg == 0]
        )
        result: List[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbour in sorted(adjacency[node]):
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)
            queue.sort()

        return result

    # =========================================================================
    # FACTORY & SERIALIZATION
    # =========================================================================

    @classmethod
    def from_plan(
        cls,
        plan: Any,
        objective_id: str = "",
        event_callback: Optional[Callable] = None,
        event_emitter: Optional[Any] = None,
        run_id: Optional[str] = None,
    ) -> "TaskGraph":
        """Create and finalize a TaskGraph directly from a Plan artifact or task list.

        Correction #15: Supports both Plan objects and plan.tasks lists.
        """
        from .planner import Planner
        from .types import Plan, PlanningLevel

        tasks: List[Task] = []
        if isinstance(plan, list):
            planner = Planner()
            for item in plan:
                if isinstance(item, Task):
                    tasks.append(item)
                elif isinstance(item, dict):
                    tid = str(item.get("id") or item.get("task_id") or "")
                    single_plan = Plan(
                        id=f"plan_item_{tid}",
                        workflow_id=objective_id,
                        objective="",
                        planning_level=PlanningLevel.STRUCTURED,
                        task_ids=[tid],
                        dependencies={tid: item.get("dependencies", [])},
                        task_details={tid: item},
                    )
                    tasks.extend(planner.create_tasks_from_plan(single_plan, objective_id=objective_id))
        else:
            planner = Planner()
            tasks = planner.create_tasks_from_plan(
                plan, objective_id=objective_id or getattr(plan, "workflow_id", "")
            )

        graph = cls(
            event_callback=event_callback,
            event_emitter=event_emitter,
            run_id=run_id,
        )
        for task in tasks:
            graph.add_task(task)
        graph.finalize()
        return graph

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the graph state."""
        tasks_data = []
        for tid in self._insertion_order:
            task = self._tasks[tid]
            tasks_data.append({
                "id": task.id,
                "objective_id": task.objective_id,
                "title": task.title,
                "description": task.description,
                "type": task.type.value,
                "status": task.status.value,
                "dependencies": task.dependencies,
                "inputs": task.inputs,
                "expected_outputs": task.expected_outputs,
                "validation": task.validation,
                "attempts": task.attempts,
                "failure_evidence": task.failure_evidence,
                "metadata": task.metadata,
                "validation_requirements": task.validation_requirements,
            })
        return {
            "tasks": tasks_data,
            "finalized": self._finalized,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        event_emitter: Optional[Any] = None,
        run_id: Optional[str] = None,
    ) -> "TaskGraph":
        """Restore a TaskGraph from serialized data."""
        graph = cls(
            event_callback=event_callback,
            event_emitter=event_emitter,
            run_id=run_id,
        )
        for td in data.get("tasks", []):
            task_type = TaskType.IMPLEMENTATION
            try:
                task_type = TaskType(td.get("type", "implementation"))
            except (ValueError, KeyError):
                pass

            task_status = TaskState.PENDING
            try:
                task_status = TaskState(td.get("status", "pending"))
            except (ValueError, KeyError):
                pass

            task = Task(
                id=td["id"],
                objective_id=td.get("objective_id", ""),
                title=td.get("title", ""),
                description=td.get("description", td["id"]),
                type=task_type,
                status=task_status,
                dependencies=td.get("dependencies", []),
                inputs=td.get("inputs", []),
                expected_outputs=td.get("expected_outputs", []),
                validation=td.get("validation", []),
                validation_requirements=td.get("validation_requirements", []),
                attempts=td.get("attempts", 0),
                failure_evidence=td.get("failure_evidence", []),
                metadata=td.get("metadata", {}),
            )
            graph._tasks[task.id] = task
            graph._insertion_order.append(task.id)

        graph._finalized = data.get("finalized", False)
        return graph

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _require_task(self, task_id: str) -> Task:
        """Get a task or raise TaskGraphError."""
        task = self._tasks.get(task_id)
        if task is None:
            raise TaskGraphError(f"Task '{task_id}' not found in graph")
        return task

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit event to callback and/or EventEmitter."""
        # 1. Raw callback
        if self._event_callback:
            try:
                self._event_callback(event_type, data)
            except Exception:
                pass

        # 2. RuntimeEvent via EventEmitter
        if self._event_emitter:
            try:
                from clairecoder.runtime.events import EventType, RuntimeEvent

                etype = EventType(event_type)
                task_id = data.get("task_id")
                task = self._tasks.get(task_id) if task_id else None
                obj_id = task.objective_id if task else ""

                event = RuntimeEvent(
                    event_type=etype,
                    run_id=self._run_id,
                    objective_id=obj_id,
                    task_id=task_id,
                    payload=data,
                )
                self._event_emitter.emit(event)
            except Exception:
                pass
