"""Workflow manager — lifecycle, state transitions, and plan coordination.

CC-PRD-004 Section 6–10: Workflow lifecycle and task coordination.
CC-ADR-004 Section 5–10: Workflow architecture, planning, replanning.

The WorkflowManager owns Workflow lifecycle and state transitions.
It does NOT own Tool execution, Permission, or Model Gateway access.
Those responsibilities remain with the EngineeringEngine.
"""

from typing import Any, Dict, List, Optional

from clairecoder.engine.types import Task, TaskState
from .types import (
    Workflow,
    WorkflowState,
    Plan,
    PlanningLevel,
    WorkflowError,
    WorkflowStateError,
)
from .dependencies import validate_dependencies, topological_order, get_ready_tasks, validate_plan_dependencies


# Valid state transitions per CC-PRD-004 Section 7
_VALID_TRANSITIONS: Dict[WorkflowState, set] = {
    WorkflowState.CREATED:      {WorkflowState.PLANNED, WorkflowState.CANCELLED},
    WorkflowState.PLANNED:      {WorkflowState.ACTIVE, WorkflowState.CANCELLED},
    WorkflowState.ACTIVE:       {WorkflowState.VALIDATING, WorkflowState.PAUSED,
                                 WorkflowState.INTERRUPTED, WorkflowState.CANCELLED,
                                 WorkflowState.BLOCKED, WorkflowState.FAILED},
    WorkflowState.VALIDATING:   {WorkflowState.COMPLETE, WorkflowState.FAILED},
    WorkflowState.FAILED:       {WorkflowState.REPLANNING, WorkflowState.CANCELLED},
    WorkflowState.REPLANNING:   {WorkflowState.PLANNED, WorkflowState.CANCELLED},
    WorkflowState.PAUSED:       {WorkflowState.ACTIVE, WorkflowState.CANCELLED},
    WorkflowState.INTERRUPTED:  {WorkflowState.ACTIVE, WorkflowState.CANCELLED},
    WorkflowState.BLOCKED:      {WorkflowState.ACTIVE, WorkflowState.CANCELLED},
    WorkflowState.COMPLETE:     set(),  # terminal
    WorkflowState.CANCELLED:    set(),  # terminal
}


class WorkflowManager:
    """Manages Workflow lifecycle, state transitions, and plan coordination.

    The WorkflowManager:
    - Owns Workflow identity and state
    - Validates state transitions
    - Coordinates plan/replan lifecycle
    - Manages task dependencies
    - Does NOT execute Tools
    - Does NOT bypass PermissionEngine
    - Does NOT access ModelGateway directly
    """

    def __init__(self) -> None:
        self._workflows: Dict[str, Workflow] = {}
        self._plans: Dict[str, List[Plan]] = {}  # workflow_id → plan history

    # =========================================================================
    # WORKFLOW LIFECYCLE
    # =========================================================================

    def create_workflow(
        self,
        workflow_id: str,
        objective_id: str,
        description: str,
        planning_level: PlanningLevel = PlanningLevel.STRUCTURED,
        completion_criteria: Optional[List[str]] = None,
        validation_requirements: Optional[List[str]] = None,
        relevant_skills: Optional[List[str]] = None,
        relevant_tools: Optional[List[str]] = None,
        context_requirements: Optional[List[str]] = None,
    ) -> Workflow:
        """Create a new Workflow.

        CC-PRD-004 Section 6: A Workflow SHALL represent the structured process
        through which an engineering objective is completed.
        """
        if workflow_id in self._workflows:
            raise WorkflowError(f"Workflow '{workflow_id}' already exists")

        workflow = Workflow(
            id=workflow_id,
            objective_id=objective_id,
            description=description,
            planning_level=planning_level,
            completion_criteria=completion_criteria or [],
            validation_requirements=validation_requirements or [],
            relevant_skills=relevant_skills or [],
            relevant_tools=relevant_tools or [],
            context_requirements=context_requirements or [],
        )
        self._workflows[workflow_id] = workflow
        self._plans[workflow_id] = []
        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Retrieve a Workflow by ID."""
        return self._workflows.get(workflow_id)

    def transition_state(
        self, workflow_id: str, new_state: WorkflowState
    ) -> Workflow:
        """Transition a Workflow to a new state.

        Validates the transition against the allowed state machine.

        CC-PRD-004 Section 7: Workflow lifecycle state transitions.
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise WorkflowError(f"Workflow '{workflow_id}' not found")

        allowed = _VALID_TRANSITIONS.get(workflow.state, set())
        if new_state not in allowed:
            raise WorkflowStateError(
                f"Cannot transition Workflow '{workflow_id}' "
                f"from {workflow.state.value} to {new_state.value}"
            )

        workflow.state = new_state
        return workflow

    # =========================================================================
    # PLAN MANAGEMENT
    # =========================================================================

    def add_plan(self, plan: Plan) -> None:
        """Add a plan to a Workflow.

        CC-ADR-004 Section 6.3: Plans are persistable inside the Session.
        CC-PRD-004 Section 33: Plan history is preserved; superseded plans are
        distinguishable from the active plan.

        The plan's dependency structure is validated BEFORE acceptance.
        If validation fails, the currently active plan is NOT superseded.

        Order:
            1. Validate new plan
            2. Accept new plan
            3. Supersede previous active plan
            4. Store new plan
        """
        wf_id = plan.workflow_id
        if wf_id not in self._workflows:
            raise WorkflowError(f"Workflow '{wf_id}' not found")

        # Validate dependency structure BEFORE any mutation.
        # This ensures a rejected plan does not destroy the active plan.
        if plan.task_ids or plan.dependencies:
            validate_plan_dependencies(plan.task_ids, plan.dependencies)

        history = self._plans[wf_id]

        # Only after validation succeeds: mark previous active plan as superseded
        for existing in history:
            if not existing.is_superseded:
                existing.is_superseded = True
                existing.superseded_by = plan.id

        history.append(plan)

        # Sync task_ids into the Workflow
        workflow = self._workflows[wf_id]
        workflow.task_ids = list(plan.task_ids)

    def get_active_plan(self, workflow_id: str) -> Optional[Plan]:
        """Return the current (non-superseded) plan for a workflow."""
        for plan in reversed(self._plans.get(workflow_id, [])):
            if not plan.is_superseded:
                return plan
        return None

    def get_plan_history(self, workflow_id: str) -> List[Plan]:
        """Return the full plan history (all plans, including superseded).

        CC-PRD-004 Section 33: Current and superseded plans can be distinguished.
        """
        return list(self._plans.get(workflow_id, []))

    # =========================================================================
    # TASK DEPENDENCY COORDINATION
    # =========================================================================

    def validate_task_dependencies(self, tasks: List[Task]) -> None:
        """Validate task dependencies for a workflow.

        CC-PRD-004 Section 9: Dependencies are validated.
        Delegates to the dependency module.
        """
        validate_dependencies(tasks)

    def get_task_order(self, tasks: List[Task]) -> List[str]:
        """Return task IDs in valid dependency order.

        CC-ADR-004 Section 8: The Planner SHALL be able to determine
        when a task becomes executable.
        """
        return topological_order(tasks)

    def get_ready_tasks(self, tasks: List[Task]) -> List[Task]:
        """Return tasks whose dependencies are satisfied.

        CC-PRD-004 Section 9: A dependent Task SHALL not become executable
        until its required dependencies are satisfied.
        """
        return get_ready_tasks(tasks)

    # =========================================================================
    # WORKFLOW COMPLETION  (CC-PRD-004 Section 10)
    # =========================================================================

    def check_completion(
        self, workflow_id: str, tasks: List[Task],
        satisfied_criteria: Optional[List[str]] = None,
        satisfied_validations: Optional[List[str]] = None,
    ) -> bool:
        """Check whether a Workflow's completion criteria are met.

        CC-PRD-004 Section 10: Completion SHALL not be based solely on whether
        all model requests have finished. The Workflow SHOULD consider:

        - Task completion
        - validation results
        - unresolved failures
        - user requirements
        - explicit completion criteria

        Args:
            workflow_id: Workflow to check.
            tasks: Current task list for the workflow.
            satisfied_criteria: Completion criteria that have been satisfied.
                Each entry must match an entry in workflow.completion_criteria.
            satisfied_validations: Validation requirements that have been satisfied.
                Each entry must match an entry in workflow.validation_requirements.

        The Workflow does NOT run validations itself (that is the responsibility
        of the Verification Engine / EngineeringEngine). It only checks whether
        the declared criteria have been reported as satisfied.
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False

        # All tasks must be COMPLETE
        if tasks and not all(t.status == TaskState.SUCCEEDED for t in tasks):
            return False

        # No task may be in a FAILED state
        if any(t.status == TaskState.FAILED for t in tasks):
            return False

        # Explicit completion criteria must all be satisfied
        if workflow.completion_criteria:
            provided = set(satisfied_criteria or [])
            if not all(c in provided for c in workflow.completion_criteria):
                return False

        # Validation requirements must all be satisfied
        if workflow.validation_requirements:
            provided = set(satisfied_validations or [])
            if not all(v in provided for v in workflow.validation_requirements):
                return False

        return True

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def workflow_to_dict(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Serialize a Workflow + its plan history for session persistence."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None

        plans_data = []
        for plan in self._plans.get(workflow_id, []):
            plans_data.append({
                "id": plan.id,
                "workflow_id": plan.workflow_id,
                "objective": plan.objective,
                "planning_level": plan.planning_level.value,
                "assumptions": plan.assumptions,
                "affected_areas": plan.affected_areas,
                "task_ids": plan.task_ids,
                "dependencies": plan.dependencies,
                "validation_strategy": plan.validation_strategy,
                "risks": plan.risks,
                "completion_criteria": plan.completion_criteria,
                "is_superseded": plan.is_superseded,
                "superseded_by": plan.superseded_by,
                "metadata": plan.metadata,
            })

        return {
            "id": workflow.id,
            "objective_id": workflow.objective_id,
            "description": workflow.description,
            "state": workflow.state.value,
            "task_ids": workflow.task_ids,
            "completion_criteria": workflow.completion_criteria,
            "validation_requirements": workflow.validation_requirements,
            "relevant_skills": workflow.relevant_skills,
            "relevant_tools": workflow.relevant_tools,
            "context_requirements": workflow.context_requirements,
            "planning_level": workflow.planning_level.value,
            "metadata": workflow.metadata,
            "plans": plans_data,
        }

    @classmethod
    def workflow_from_dict(cls, data: Dict[str, Any]) -> 'WorkflowManager':
        """Restore a WorkflowManager from serialized data.

        Returns a new WorkflowManager containing the restored workflow.
        """
        mgr = cls()

        workflow = Workflow(
            id=data["id"],
            objective_id=data["objective_id"],
            description=data["description"],
            state=WorkflowState(data["state"]),
            task_ids=data.get("task_ids", []),
            completion_criteria=data.get("completion_criteria", []),
            validation_requirements=data.get("validation_requirements", []),
            relevant_skills=data.get("relevant_skills", []),
            relevant_tools=data.get("relevant_tools", []),
            context_requirements=data.get("context_requirements", []),
            planning_level=PlanningLevel(data.get("planning_level", 2)),
            metadata=data.get("metadata", {}),
        )
        mgr._workflows[workflow.id] = workflow
        mgr._plans[workflow.id] = []

        for plan_data in data.get("plans", []):
            plan = Plan(
                id=plan_data["id"],
                workflow_id=plan_data["workflow_id"],
                objective=plan_data["objective"],
                planning_level=PlanningLevel(plan_data["planning_level"]),
                assumptions=plan_data.get("assumptions", []),
                affected_areas=plan_data.get("affected_areas", []),
                task_ids=plan_data.get("task_ids", []),
                dependencies=plan_data.get("dependencies", {}),
                validation_strategy=plan_data.get("validation_strategy", []),
                risks=plan_data.get("risks", []),
                completion_criteria=plan_data.get("completion_criteria", []),
                is_superseded=plan_data.get("is_superseded", False),
                superseded_by=plan_data.get("superseded_by"),
                metadata=plan_data.get("metadata", {}),
            )
            mgr._plans[workflow.id].append(plan)

        return mgr
