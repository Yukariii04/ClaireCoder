"""Execution State Manager.

CC-PRD-007: Manages execution state transitions, retry policy, cancellation,
and checkpoints.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid

from clairecoder.execution.types import (
    Task, TaskState, ExecutionAttempt, ExecutionResult,
    ExecutionResultCategory, FailureCategory,
    ExecutionError, InvalidStateTransitionError,
    TaskNotFoundError, ExecutionNotFoundError,
    DependencyBlockedError, VerificationError, RecoveryError
)

# Defined by CC-PRD-007 Section 11
_VALID_TRANSITIONS: Dict[TaskState, set] = {
    TaskState.PENDING: {TaskState.READY},
    TaskState.READY:   {TaskState.RUNNING, TaskState.BLOCKED},
    TaskState.RUNNING: {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.PAUSED, TaskState.CANCELLED},
    TaskState.PAUSED:  {TaskState.RUNNING},
    TaskState.FAILED:  {TaskState.READY}, # for retry
    TaskState.BLOCKED: {TaskState.READY}, # developer intervention
    TaskState.SUCCEEDED: set(), # terminal
    TaskState.CANCELLED: set(), # terminal
}

class ExecutionManager:
    """Manages Task and Execution lifecycle."""

    def __init__(self) -> None:
        self._tasks: Dict[str, Task] = {}

    def register_task(self, task: Task) -> None:
        """Register a newly created Task."""
        self._tasks[task.id] = task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def transition_task(self, task_id: str, new_state: TaskState) -> Task:
        """Safely transition a Task to a new state."""
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task '{task_id}' not found.")
            
        allowed = _VALID_TRANSITIONS.get(task.status, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(f"Cannot transition Task '{task_id}' from {task.status.value} to {new_state.value}")
            
        task.status = new_state
        task.updated_at = datetime.now(timezone.utc)
        return task

    def start_execution(self, task_id: str) -> ExecutionAttempt:
        """Start or resume execution for a task."""
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task '{task_id}' not found.")
            
        # Must be READY or PAUSED to run
        if task.status not in (TaskState.READY, TaskState.PAUSED):
            raise InvalidStateTransitionError(f"Task '{task_id}' must be READY or PAUSED to start execution.")
            
        self.transition_task(task_id, TaskState.RUNNING)
        
        attempt_number = len(task.attempts) + 1
        execution_id = f"exec_{uuid.uuid4().hex[:8]}"
        
        attempt = ExecutionAttempt(
            execution_id=execution_id,
            task_id=task_id,
            attempt_number=attempt_number,
            started_at=datetime.now(timezone.utc),
            status=TaskState.RUNNING
        )
        task.attempts.append(attempt)
        return attempt

    def complete_execution(
        self, 
        task_id: str, 
        execution_id: str, 
        result: ExecutionResult, 
        is_verified: bool = False
    ) -> Task:
        """Record an execution result and transition the Task accordingly."""
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task '{task_id}' not found.")
            
        if not task.attempts or task.attempts[-1].execution_id != execution_id:
            raise ExecutionNotFoundError(f"Execution '{execution_id}' not found or not active for Task '{task_id}'.")
            
        attempt = task.attempts[-1]
        attempt.completed_at = datetime.now(timezone.utc)
        attempt.result = result
        
        if result.category == ExecutionResultCategory.SUCCESS:
            if is_verified:
                attempt.status = TaskState.SUCCEEDED
                self.transition_task(task_id, TaskState.SUCCEEDED)
                task.result = result.tool_result
            else:
                # CC-PRD-007 Section 15: Cannot mark successful without verification
                attempt.status = TaskState.FAILED
                attempt.error = "Validation failed: Tool completed but verification step was missing or failed."
                result.category = ExecutionResultCategory.FAILURE
                result.failure_category = FailureCategory.VALIDATION_FAILURE
                self.transition_task(task_id, TaskState.FAILED)
        elif result.category == ExecutionResultCategory.CANCELLED:
            attempt.status = TaskState.CANCELLED
            self.transition_task(task_id, TaskState.CANCELLED)
        elif result.category == ExecutionResultCategory.TIMEOUT:
            attempt.status = TaskState.FAILED
            attempt.error = "Execution timed out."
            self.transition_task(task_id, TaskState.FAILED)
        else:
            attempt.status = TaskState.FAILED
            attempt.error = result.error_message
            self.transition_task(task_id, TaskState.FAILED)
            
        return task

    def retry_execution(self, task_id: str, max_retries: int = 3) -> None:
        """Attempt to retry a failed execution."""
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task '{task_id}' not found.")
            
        if task.status != TaskState.FAILED:
            raise InvalidStateTransitionError("Can only retry FAILED tasks.")
            
        if len(task.attempts) >= max_retries:
            raise RecoveryError(f"Retry limit exceeded for Task '{task_id}'. Max retries: {max_retries}.")
            
        # Transition back to READY
        self.transition_task(task_id, TaskState.READY)

    def cancel_task(self, task_id: str) -> None:
        """Cancel a task."""
        self.transition_task(task_id, TaskState.CANCELLED)
        task = self._tasks[task_id]
        if task.attempts and task.attempts[-1].status == TaskState.RUNNING:
            task.attempts[-1].status = TaskState.CANCELLED
            task.attempts[-1].completed_at = datetime.now(timezone.utc)
            task.attempts[-1].result = ExecutionResult(category=ExecutionResultCategory.CANCELLED)

    def pause_task(self, task_id: str) -> None:
        """Pause a task."""
        self.transition_task(task_id, TaskState.PAUSED)
        task = self._tasks[task_id]
        if task.attempts and task.attempts[-1].status == TaskState.RUNNING:
            task.attempts[-1].status = TaskState.PAUSED

    def block_task(self, task_id: str) -> None:
        """Mark task as blocked (e.g. by permission)."""
        self.transition_task(task_id, TaskState.BLOCKED)

    # =========================================================================
    # CHECKPOINT / SERIALIZATION
    # =========================================================================

    def task_to_dict(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self._tasks.get(task_id)
        if not task:
            return None
            
        attempts_data = []
        for att in task.attempts:
            res_data = None
            if att.result:
                res_data = {
                    "category": att.result.category.value,
                    "failure_category": att.result.failure_category.value if att.result.failure_category else None,
                    "error_message": att.result.error_message,
                    "tool_result": att.result.tool_result,
                }
            attempts_data.append({
                "execution_id": att.execution_id,
                "task_id": att.task_id,
                "attempt_number": att.attempt_number,
                "started_at": att.started_at.isoformat(),
                "status": att.status.value,
                "completed_at": att.completed_at.isoformat() if att.completed_at else None,
                "result": res_data,
                "error": att.error
            })
            
        return {
            "id": task.id,
            "objective_id": task.objective_id,
            "description": task.description,
            "workflow_id": task.workflow_id,
            "status": task.status.value,
            "dependencies": task.dependencies,
            "affected_areas": task.affected_areas,
            "required_capabilities": task.required_capabilities,
            "required_skills": task.required_skills,
            "validation_requirements": task.validation_requirements,
            "attempts": attempts_data,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "failure_state": task.failure_state
        }

    def task_from_dict(self, data: Dict[str, Any]) -> Task:
        attempts = []
        for att_data in data.get("attempts", []):
            res = None
            if att_data.get("result"):
                rd = att_data["result"]
                fc = FailureCategory(rd["failure_category"]) if rd.get("failure_category") else None
                res = ExecutionResult(
                    category=ExecutionResultCategory(rd["category"]),
                    failure_category=fc,
                    error_message=rd.get("error_message"),
                    tool_result=rd.get("tool_result")
                )
            
            att = ExecutionAttempt(
                execution_id=att_data["execution_id"],
                task_id=att_data["task_id"],
                attempt_number=att_data["attempt_number"],
                started_at=datetime.fromisoformat(att_data["started_at"]),
                status=TaskState(att_data["status"]),
                completed_at=datetime.fromisoformat(att_data["completed_at"]) if att_data.get("completed_at") else None,
                result=res,
                error=att_data.get("error")
            )
            attempts.append(att)
            
        task = Task(
            id=data["id"],
            objective_id=data["objective_id"],
            description=data["description"],
            workflow_id=data.get("workflow_id", ""),
            status=TaskState(data["status"]),
            dependencies=data.get("dependencies", []),
            affected_areas=data.get("affected_areas", []),
            required_capabilities=data.get("required_capabilities", []),
            required_skills=data.get("required_skills", []),
            validation_requirements=data.get("validation_requirements", []),
            attempts=attempts,
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(timezone.utc),
            result=None, # not serialized for now
            failure_state=data.get("failure_state")
        )
        self.register_task(task)
        return task
