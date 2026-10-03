"""Adaptive Planner — plan generation through the Model Gateway.

CC-ADR-004 Section 6: Adaptive Planning.
CC-PRD-004 Section 33: Plan persistence, plan history.
CC-ADR-004 Section 10: Replanning.

The Planner generates Plans by interacting with the Model Gateway through
the EngineeringEngine boundary. It does NOT access models, tools, or
permissions directly.

Correction #13: Task creation preserves structured information from the
model's plan output (title, description, type, inputs, expected_outputs,
validation) instead of reducing to "Task: {task_id}".
"""

import json
import uuid
from typing import Any, Dict, List, Optional

from clairecoder.gateway.types import ModelRequest, ModelResponse
from .types import Plan, PlanningLevel, PlanningError, Task, TaskState, TaskType
from .dependencies import validate_plan_dependencies


# Safe mapping from model-provided type strings to TaskType
_TYPE_MAP: Dict[str, TaskType] = {
    "analysis": TaskType.ANALYSIS,
    "implementation": TaskType.IMPLEMENTATION,
    "implement": TaskType.IMPLEMENTATION,
    "test": TaskType.TEST,
    "testing": TaskType.TEST,
    "refactor": TaskType.REFACTOR,
    "refactoring": TaskType.REFACTOR,
    "verification": TaskType.VERIFICATION,
    "verify": TaskType.VERIFICATION,
    "documentation": TaskType.DOCUMENTATION,
    "docs": TaskType.DOCUMENTATION,
    "doc": TaskType.DOCUMENTATION,
    "other": TaskType.OTHER,
}


def _parse_task_type(raw: Any) -> TaskType:
    """Parse a task type string into a TaskType enum, defaulting safely."""
    if isinstance(raw, str):
        return _TYPE_MAP.get(raw.lower().strip(), TaskType.IMPLEMENTATION)
    return TaskType.IMPLEMENTATION


def _ensure_str_list(val: Any) -> List[str]:
    """Coerce a value to a list of strings, tolerating model output quirks."""
    if val is None:
        return []
    if isinstance(val, str):
        return [val] if val.strip() else []
    if isinstance(val, list):
        return [str(v) for v in val if v is not None]
    return []


class Planner:
    """Generates and updates Plans via the Model Gateway through the Engine.

    CC-ADR-004 Section 6.1: Adaptive planning — planning depth depends
    on task complexity, repository size, ambiguity, risk, etc.

    The Planner does NOT:
    - execute Tools
    - bypass PermissionEngine
    - contain provider-specific logic
    - access the ModelGateway directly

    It produces Plan artifacts that the WorkflowManager and EngineeringEngine
    can coordinate.
    """

    def create_plan(
        self,
        workflow_id: str,
        objective: str,
        planning_level: PlanningLevel,
        context_summary: str = "",
        model_response: Optional[ModelResponse] = None,
    ) -> Plan:
        """Create a Plan from an objective and optional model reasoning.

        CC-ADR-004 Section 6.3: A plan SHOULD contain objective, assumptions,
        affected areas, tasks, dependencies, validation strategy, risks,
        completion criteria.

        If model_response is provided with structured_output, the planner
        validates and converts it. Malformed structured output raises
        PlanningError — it is NOT silently turned into a minimal scaffold.

        If model_response provides only text, JSON extraction is attempted.
        Invalid JSON text (no parseable JSON) falls back to a minimal scaffold
        since text output is inherently best-effort.

        If no model_response is provided, a minimal scaffold is returned
        (appropriate for DIRECT/LIGHTWEIGHT planning).
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"

        # If model provided structured planning output, validate and use it.
        # Malformed structured output MUST raise PlanningError.
        if model_response:
            has_structured = model_response.structured_output is not None
            # If it explicitly has structured output, or it's completely empty (no text fallback)
            if has_structured or not model_response.text:
                if not isinstance(model_response.structured_output, dict):
                    raise PlanningError(
                        f"Invalid plan structure from model: structured_output must be a mapping, got {type(model_response.structured_output).__name__}"
                    )
                return self._plan_from_structured(
                    plan_id, workflow_id, objective, planning_level,
                    model_response.structured_output
                )

        # If model provided text, try to extract structured JSON.
        # Text is best-effort; invalid JSON falls back to minimal scaffold.
        if model_response and model_response.text:
            parsed = self._try_parse_plan(model_response.text)
            if parsed:
                return self._plan_from_structured(
                    plan_id, workflow_id, objective, planning_level, parsed
                )

        # Minimal scaffold for direct/lightweight planning
        return Plan(
            id=plan_id,
            workflow_id=workflow_id,
            objective=objective,
            planning_level=planning_level,
        )

    def create_tasks_from_plan(self, plan: Plan, objective_id: str) -> List[Task]:
        """Convert a Plan's task descriptions into Task objects.

        Correction #13: Preserves structured task information from
        plan.task_details instead of reducing to "Task: {task_id}".

        If task_details are not available for a task_id, falls back to
        a reasonable default using the task_id as description.
        """
        tasks: List[Task] = []
        for task_id in plan.task_ids:
            deps = plan.dependencies.get(task_id, [])
            details = plan.task_details.get(task_id, {})

            # Extract structured fields with safe defaults
            title = details.get("title", "") or ""
            description = details.get("description", "") or ""
            task_type = _parse_task_type(details.get("type"))
            inputs = _ensure_str_list(details.get("inputs"))
            expected_outputs = _ensure_str_list(details.get("expected_outputs"))
            validation = _ensure_str_list(details.get("validation"))
            metadata = details.get("metadata", {}) if isinstance(details.get("metadata"), dict) else {}

            # Ensure we always have a meaningful description
            if not description:
                if title:
                    description = title
                else:
                    description = f"Task: {task_id}"

            # If no explicit title, derive from task_id
            if not title:
                title = task_id.replace("_", " ").replace("-", " ").title()

            task = Task(
                id=task_id,
                objective_id=objective_id,
                title=title,
                description=description,
                type=task_type,
                dependencies=deps,
                inputs=inputs,
                expected_outputs=expected_outputs,
                validation=validation,
                metadata=metadata,
            )
            tasks.append(task)
        return tasks

    def build_planning_request(
        self,
        objective: str,
        planning_level: PlanningLevel,
        context_summary: str,
        model_id: Optional[str] = None,
    ) -> ModelRequest:
        """Build a ModelRequest for planning.

        CC-ADR-004 Section 6: Planning requires model reasoning.
        This method prepares the request; the EngineeringEngine is responsible
        for executing it through the Model Gateway.

        Correction #13: Request schema now includes per-task structured fields
        (title, description, type, inputs, expected_outputs, validation).
        """
        level_descriptions = {
            PlanningLevel.DIRECT: "Direct execution — minimal planning required.",
            PlanningLevel.LIGHTWEIGHT: "Lightweight planning — limited inspection.",
            PlanningLevel.STRUCTURED: "Structured planning — multiple components.",
            PlanningLevel.DEEP: "Deep planning — complex architectural changes.",
        }

        system_prompt = (
            f"You are an engineering planner. "
            f"Planning level: {level_descriptions[planning_level]}\n\n"
            f"Context:\n{context_summary}\n\n"
            f"Produce a structured JSON plan with these fields:\n"
            f"  assumptions: list of strings\n"
            f"  affected_areas: list of strings\n"
            f"  task_ids: list of task identifier strings\n"
            f"  dependencies: dict mapping task_id to list of dependency task_ids\n"
            f"  task_details: dict mapping each task_id to an object with:\n"
            f"    title: human-readable task title\n"
            f"    description: what needs to be done and why\n"
            f"    type: one of analysis/implementation/test/refactor/verification/documentation/other\n"
            f"    inputs: list of input files or resources\n"
            f"    expected_outputs: list of expected deliverables\n"
            f"    validation: list of validation commands or checks\n"
            f"  validation_strategy: list of strings\n"
            f"  risks: list of strings\n"
            f"  completion_criteria: list of strings\n"
        )

        return ModelRequest(
            model_id=model_id or "",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Plan this objective: {objective}"},
            ],
        )

    def build_replan_request(
        self,
        objective: str,
        previous_plan: Plan,
        failure_reason: str,
        context_summary: str,
        model_id: Optional[str] = None,
    ) -> ModelRequest:
        """Build a ModelRequest for replanning after failure.

        CC-ADR-004 Section 10: Replanning when assumptions are invalid,
        tests fail, dependencies differ, etc.
        """
        previous_summary = (
            f"Previous plan ID: {previous_plan.id}\n"
            f"Previous assumptions: {previous_plan.assumptions}\n"
            f"Previous tasks: {previous_plan.task_ids}\n"
            f"Previous risks: {previous_plan.risks}\n"
        )

        system_prompt = (
            f"You are an engineering planner performing REPLANNING.\n\n"
            f"The previous plan failed.\n"
            f"Failure reason: {failure_reason}\n\n"
            f"Previous plan:\n{previous_summary}\n"
            f"Context:\n{context_summary}\n\n"
            f"Produce a revised structured JSON plan with the same fields as before.\n"
        )

        return ModelRequest(
            model_id=model_id or "",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Replan this objective: {objective}"},
            ],
        )

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _try_parse_plan(self, text: str) -> Optional[Dict[str, Any]]:
        """Attempt to extract a JSON plan from model text output."""
        # Try to find JSON in the text
        try:
            # Look for JSON block
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _plan_from_structured(
        self,
        plan_id: str,
        workflow_id: str,
        objective: str,
        planning_level: PlanningLevel,
        data: Dict[str, Any],
    ) -> Plan:
        """Create a Plan from structured model output.

        Validates structural integrity before constructing the Plan.
        Malformed data raises PlanningError.

        Correction #13: Extracts task_details from the model output
        to preserve per-task structured information.
        """
        task_ids = list(data.get("task_ids", []))
        dependencies = dict(data.get("dependencies", {}))

        # Extract per-task details (Correction #13)
        task_details: Dict[str, Dict[str, Any]] = {}

        # 1. From "tasks" list of dicts (common model format)
        raw_tasks = data.get("tasks", [])
        if isinstance(raw_tasks, list):
            for item in raw_tasks:
                if isinstance(item, dict):
                    tid = item.get("id") or item.get("task_id")
                    if tid:
                        if tid not in task_ids:
                            task_ids.append(tid)
                        if tid not in dependencies and "dependencies" in item:
                            deps = item["dependencies"]
                            if isinstance(deps, list):
                                dependencies[tid] = deps
                        task_details[tid] = item

        # 2. From "task_details" mapping (task_id -> dict)
        raw_task_details = data.get("task_details", {})
        if isinstance(raw_task_details, dict):
            for tid, details in raw_task_details.items():
                if isinstance(details, dict):
                    if tid not in task_ids:
                        task_ids.append(tid)
                    task_details[tid] = details

        # Validate dependency structure using centralized validation.
        # Wraps dependency errors in PlanningError for the planning boundary.
        if task_ids or dependencies:
            try:
                validate_plan_dependencies(task_ids, dependencies)
            except Exception as e:
                raise PlanningError(f"Invalid plan structure from model: {e}") from e

        return Plan(
            id=plan_id,
            workflow_id=workflow_id,
            objective=objective,
            planning_level=planning_level,
            assumptions=data.get("assumptions", []),
            affected_areas=data.get("affected_areas", []),
            task_ids=task_ids,
            dependencies=dependencies,
            validation_strategy=data.get("validation_strategy", []),
            risks=data.get("risks", []),
            completion_criteria=data.get("completion_criteria", []),
            task_details=task_details,
        )
