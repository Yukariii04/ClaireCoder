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

Correction #15: Schema-driven structured planner with explicit plan validation,
ModelRequest.structured_output_schema integration, compact DAG prompting,
safe provider fallback, and rejection of malformed plan outputs.
"""

import json
import re
import uuid
from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Set

from clairecoder.gateway.types import ModelRequest, ModelResponse
from .types import Plan, PlanningLevel, PlanningError, Task, TaskState, TaskType
from .dependencies import validate_plan_dependencies


# Standard JSON Schema for structured execution plans
PLAN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Explicit assumptions made during planning",
        },
        "affected_areas": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Files, modules, or architectural boundaries impacted",
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Potential pitfalls, regressions, or failure modes",
        },
        "validation_strategy": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Testing and verification strategy to ensure correctness",
        },
        "completion_criteria": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific criteria that confirm objective satisfaction",
        },
        "tasks": {
            "type": "array",
            "description": "Ordered DAG of atomic engineering tasks",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique task identifier (e.g., task-1)",
                    },
                    "title": {
                        "type": "string",
                        "description": "Short human-readable task title",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed explanation of what must be done",
                    },
                    "type": {
                        "type": "string",
                        "enum": [
                            "implementation",
                            "verification",
                            "research",
                            "documentation",
                            "refactoring",
                            "analysis",
                            "test",
                            "custom",
                            "other",
                        ],
                        "description": "Task type classification",
                    },
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of task IDs that must complete before this task",
                    },
                    "inputs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Required inputs, files, or context",
                    },
                    "expected_outputs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Expected deliverables or artifacts",
                    },
                    "validation": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Validation commands, tests, or checks",
                    },
                },
                "required": [
                    "id",
                    "title",
                    "description",
                    "type",
                    "dependencies",
                ],
            },
        },
    },
    "required": [
        "assumptions",
        "affected_areas",
        "risks",
        "validation_strategy",
        "completion_criteria",
        "tasks",
    ],
}

# Valid task types accepted during validation
_VALID_TASK_TYPES: Set[str] = {
    "analysis",
    "implementation",
    "implement",
    "test",
    "testing",
    "refactor",
    "refactoring",
    "verification",
    "verify",
    "documentation",
    "docs",
    "doc",
    "research",
    "custom",
    "other",
}

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
    "research": TaskType.ANALYSIS,
    "custom": TaskType.OTHER,
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


def validate_plan(data: Any) -> None:
    """Validate structured plan dictionary against required schema and rules.

    Validates:
    - data is a Mapping/dict
    - required top-level fields
    - task IDs are unique and non-empty
    - task type is valid
    - dependencies reference existing task IDs
    - dependencies do not self-reference
    - required task fields have the correct shape
    - dependencies do not contain cycles

    Raises:
        PlanningError: If the plan data is malformed or invalid.
    """
    if not isinstance(data, Mapping):
        raise PlanningError(
            f"Invalid plan structure from model: structured plan must be a mapping, got {type(data).__name__}"
        )

    # Legacy support: if plan uses legacy task_ids + dependencies format
    if "tasks" not in data and "task_ids" in data:
        task_ids = data.get("task_ids")
        if not isinstance(task_ids, list):
            raise PlanningError("Invalid plan structure from model: 'task_ids' must be a list")
        seen_tids: Set[str] = set()
        for tid in task_ids:
            if not isinstance(tid, str) or not tid.strip():
                raise PlanningError("Invalid plan structure from model: task ID must be a non-empty string")
            if tid in seen_tids:
                raise PlanningError(f"Invalid plan structure from model: duplicate task ID '{tid}' in plan")
            seen_tids.add(tid)
        deps = data.get("dependencies", {})
        if not isinstance(deps, Mapping):
            raise PlanningError("Invalid plan structure from model: 'dependencies' must be a mapping")
        for tid, dep_list in deps.items():
            if tid not in seen_tids:
                raise PlanningError(f"Invalid plan structure from model: unknown task ID '{tid}' in dependencies")
            if not isinstance(dep_list, list):
                raise PlanningError(f"Invalid plan structure from model: dependencies for '{tid}' must be a list")
            for dep in dep_list:
                if dep not in seen_tids:
                    raise PlanningError(f"Invalid plan structure from model: dependency '{dep}' does not exist in plan")
                if dep == tid:
                    raise PlanningError(f"Invalid plan structure from model: task '{tid}' cannot depend on itself")
        if task_ids or deps:
            try:
                validate_plan_dependencies(task_ids, deps)
            except Exception as e:
                raise PlanningError(f"Invalid plan structure from model: {e}") from e
        return

    # Structured plan format
    # Check top-level required fields
    if "tasks" not in data:
        raise PlanningError("Invalid plan structure from model: missing required top-level field 'tasks'")

    tasks_raw = data.get("tasks")
    if not isinstance(tasks_raw, list):
        raise PlanningError(
            f"Invalid plan structure from model: 'tasks' must be a list, got {type(tasks_raw).__name__}"
        )

    # Check top-level list fields if present
    for list_field in ("assumptions", "affected_areas", "risks", "validation_strategy", "completion_criteria"):
        if list_field in data and not isinstance(data[list_field], list):
            raise PlanningError(
                f"Invalid plan structure from model: '{list_field}' must be a list, got {type(data[list_field]).__name__}"
            )

    # Validate task objects
    task_ids: List[str] = []
    seen_ids: Set[str] = set()
    dependencies_map: Dict[str, List[str]] = {}

    for idx, item in enumerate(tasks_raw):
        if not isinstance(item, Mapping):
            raise PlanningError(
                f"Malformed task object at index {idx}: expected mapping, got {type(item).__name__}"
            )

        # Check required task fields
        for req_field in ("id", "title", "description", "type", "dependencies"):
            if req_field not in item:
                raise PlanningError(
                    f"Malformed task object at index {idx}: missing required field '{req_field}'"
                )

        tid = item.get("id")
        if not isinstance(tid, str) or not tid.strip():
            raise PlanningError(
                f"Malformed task object at index {idx}: task 'id' must be a non-empty string"
            )

        if tid in seen_ids:
            raise PlanningError(f"Duplicate task ID '{tid}' in plan")
        seen_ids.add(tid)
        task_ids.append(tid)

        title = item.get("title")
        if not isinstance(title, str):
            raise PlanningError(
                f"Malformed task object '{tid}': 'title' must be a string, got {type(title).__name__}"
            )

        desc = item.get("description")
        if not isinstance(desc, str):
            raise PlanningError(
                f"Malformed task object '{tid}': 'description' must be a string, got {type(desc).__name__}"
            )

        ttype = item.get("type")
        if not isinstance(ttype, str) or ttype.lower().strip() not in _VALID_TASK_TYPES:
            raise PlanningError(
                f"Invalid task type '{ttype}' for task '{tid}'. Must be one of {sorted(_VALID_TASK_TYPES)}"
            )

        deps = item.get("dependencies")
        if not isinstance(deps, list):
            raise PlanningError(
                f"Malformed task object '{tid}': 'dependencies' must be a list, got {type(deps).__name__}"
            )
        for dep in deps:
            if not isinstance(dep, str):
                raise PlanningError(
                    f"Malformed task object '{tid}': dependency item must be a string, got {type(dep).__name__}"
                )

        dependencies_map[tid] = deps

        # Validate optional list fields if present
        for opt_list in ("inputs", "expected_outputs", "validation"):
            if opt_list in item and not isinstance(item[opt_list], list):
                raise PlanningError(
                    f"Malformed task object '{tid}': '{opt_list}' must be a list, got {type(item[opt_list]).__name__}"
                )

    # Validate dependency references
    for tid, deps in dependencies_map.items():
        for dep in deps:
            if dep not in seen_ids:
                raise PlanningError(
                    f"Task '{tid}' has dependency '{dep}' which does not exist in plan"
                )
            if dep == tid:
                raise PlanningError(f"Task '{tid}' cannot depend on itself")

    # Validate cycles
    if task_ids or dependencies_map:
        try:
            validate_plan_dependencies(task_ids, dependencies_map)
        except Exception as e:
            raise PlanningError(f"Invalid plan structure from model: {e}") from e


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON from text, supporting markdown code blocks.

    Raises PlanningError if JSON formatting is malformed.
    Returns None if no JSON structures are found.
    """
    cleaned = text.strip()

    # 1. Look for ```json ... ``` or ``` ... ``` code blocks
    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fenced_match:
        fenced_content = fenced_match.group(1).strip()
        try:
            parsed = json.loads(fenced_content)
            if isinstance(parsed, dict):
                return parsed
            raise PlanningError(
                f"Malformed JSON in fenced code block: expected JSON object mapping, got {type(parsed).__name__}"
            )
        except (json.JSONDecodeError, ValueError) as err:
            raise PlanningError(f"Malformed JSON in fenced code block: {err}") from err

    # 2. Try parsing the whole stripped string directly
    if (cleaned.startswith("{") and cleaned.endswith("}")) or (cleaned.startswith("[") and cleaned.endswith("]")):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
            raise PlanningError(
                f"Malformed JSON in model output: expected JSON object mapping, got {type(parsed).__name__}"
            )
        except (json.JSONDecodeError, ValueError) as err:
            raise PlanningError(f"Malformed JSON in model output: {err}") from err

    # 3. Find outermost { ... }
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError) as err:
            raise PlanningError(f"Malformed JSON in model output: {err}") from err

    return None


def parse_structured_plan(response: ModelResponse, strict: bool = True) -> Dict[str, Any]:
    """Parse and validate a structured plan from a ModelResponse.

    Handles both structured_output (primary) and textual fallback (fenced JSON).
    Raises PlanningError if parsing or validation fails.
    """
    if response is None:
        raise PlanningError("Model response is None")

    # 1. Primary path: structured_output or empty text
    if response.structured_output is not None or not response.text:
        if not isinstance(response.structured_output, Mapping):
            raise PlanningError(
                f"Invalid plan structure from model: structured_output must be a mapping, got {type(response.structured_output).__name__}"
            )
        data = dict(response.structured_output)
        validate_plan(data)
        return data

    # 2. Fallback path: text parsing
    text = response.text
    if text is not None and text.strip():
        data = _extract_json_from_text(text)
        if data is None:
            raise PlanningError(
                "Failed to parse structured plan from model text: malformed JSON or non-JSON output"
            )
        if not isinstance(data, Mapping):
            raise PlanningError(
                f"Invalid plan structure from model text: expected mapping, got {type(data).__name__}"
            )
        validate_plan(data)
        return dict(data)

    raise PlanningError(
        "Model response contains neither structured output nor valid plan text"
    )


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

    PLAN_SCHEMA = PLAN_SCHEMA

    def validate_plan(self, data: Any) -> None:
        """Validate a plan data dictionary."""
        validate_plan(data)

    def parse_structured_plan(self, response: ModelResponse, strict: bool = True) -> Dict[str, Any]:
        """Parse and validate structured plan from a model response."""
        return parse_structured_plan(response, strict=strict)

    def create_plan(
        self,
        workflow_id: str,
        objective: str,
        planning_level: PlanningLevel,
        context_summary: str = "",
        model_response: Optional[ModelResponse] = None,
        strict: Optional[bool] = None,
    ) -> Plan:
        """Create a Plan from an objective and optional model reasoning.

        CC-ADR-004 Section 6.3: A plan contains objective, assumptions,
        affected areas, tasks, dependencies, validation strategy, risks,
        completion criteria.

        Primary path: ModelResponse.structured_output parsed and validated.
        Fallback path: Text response parsed for JSON block and validated.
        Malformed structured or fallback JSON raises PlanningError.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"

        # If no model_response is provided, return minimal scaffold
        if model_response is None:
            return Plan(
                id=plan_id,
                workflow_id=workflow_id,
                objective=objective,
                planning_level=planning_level,
            )

        # 1. Primary path: structured_output provided or text is empty
        if model_response.structured_output is not None or not model_response.text:
            data = parse_structured_plan(model_response, strict=True)
            return self._plan_from_structured(
                plan_id, workflow_id, objective, planning_level, data
            )

        # 2. Text response handling
        text = model_response.text
        if text is not None and text.strip():
            # If strict is explicitly requested, parse strictly
            if strict is True:
                data = parse_structured_plan(model_response, strict=True)
                return self._plan_from_structured(
                    plan_id, workflow_id, objective, planning_level, data
                )

            # Check if text contains JSON markers (fences or braces)
            has_json_markers = "```" in text or ("{" in text and "}" in text)
            if has_json_markers:
                data = _extract_json_from_text(text)
                if data is not None:
                    validate_plan(data)
                    return self._plan_from_structured(
                        plan_id, workflow_id, objective, planning_level, data
                    )

            # If strict is explicitly False or not specified with no JSON markers:
            # For DIRECT level or legacy non-JSON text, return minimal scaffold
            if planning_level == PlanningLevel.DIRECT or strict is False or not has_json_markers:
                return Plan(
                    id=plan_id,
                    workflow_id=workflow_id,
                    objective=objective,
                    planning_level=planning_level,
                )

            # Otherwise, unparseable text for structured planning raises PlanningError
            raise PlanningError(
                f"Failed to parse structured plan from model text: {text[:100]}"
            )

        # If model_response has neither structured_output nor text:
        if strict is True:
            raise PlanningError("Model response contains neither structured output nor text")

        return Plan(
            id=plan_id,
            workflow_id=workflow_id,
            objective=objective,
            planning_level=planning_level,
        )

    def create_tasks_from_plan(self, plan: Plan, objective_id: str) -> List[Task]:
        """Convert a Plan's task descriptions into Task objects.

        Correction #13 & #15: Preserves all rich structured task information:
        - id
        - title
        - description
        - type
        - dependencies
        - inputs
        - expected_outputs
        - validation
        - metadata
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
        use_structured_output: bool = True,
    ) -> ModelRequest:
        """Build a ModelRequest for planning.

        CC-ADR-004 Section 6: Planning requires model reasoning.
        Correction #15: Uses ModelRequest.structured_output_schema with PLAN_SCHEMA
        when use_structured_output is True. Includes compact DAG example.
        """
        level_descriptions = {
            PlanningLevel.DIRECT: "Direct execution — minimal planning required.",
            PlanningLevel.LIGHTWEIGHT: "Lightweight planning — limited inspection.",
            PlanningLevel.STRUCTURED: "Structured planning — multiple components.",
            PlanningLevel.DEEP: "Deep planning — complex architectural changes.",
        }

        dependency_example = (
            "Task dependencies form a directed acyclic graph (DAG). Example:\n"
            "  task-1 -> task-2 -> task-3\n"
            "  task-1 -> task-4\n"
            "Dependencies must strictly reference valid task IDs defined in the plan.\n"
            "No cycles, no self-dependencies, no unknown task IDs.\n"
        )

        if use_structured_output:
            system_prompt = (
                f"You are an engineering planner. Planning level: {level_descriptions.get(planning_level, 'Structured')}\n\n"
                f"Context:\n{context_summary}\n\n"
                f"{dependency_example}\n"
                f"Produce a structured plan adhering to the output schema with:\n"
                f"  assumptions, affected_areas, risks, validation_strategy, completion_criteria, tasks.\n"
                f"Each task must include id, title, description, type, dependencies, inputs, expected_outputs, validation.\n"
            )
        else:
            system_prompt = (
                f"You are an engineering planner. Planning level: {level_descriptions.get(planning_level, 'Structured')}\n\n"
                f"Context:\n{context_summary}\n\n"
                f"{dependency_example}\n"
                f"Produce a JSON plan in a ```json code block containing:\n"
                f'{{\n'
                f'  "assumptions": ["..."],\n'
                f'  "affected_areas": ["..."],\n'
                f'  "risks": ["..."],\n'
                f'  "validation_strategy": ["..."],\n'
                f'  "completion_criteria": ["..."],\n'
                f'  "tasks": [\n'
                f'    {{\n'
                f'      "id": "task-1",\n'
                f'      "title": "Short title",\n'
                f'      "description": "What must be done",\n'
                f'      "type": "implementation",\n'
                f'      "dependencies": [],\n'
                f'      "inputs": [],\n'
                f'      "expected_outputs": [],\n'
                f'      "validation": []\n'
                f'    }}\n'
                f'  ]\n'
                f'}}\n'
            )

        return ModelRequest(
            model_id=model_id or "",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Plan this objective: {objective}"},
            ],
            structured_output_schema=PLAN_SCHEMA if use_structured_output else None,
        )

    def build_replan_request(
        self,
        objective: str,
        previous_plan: Plan,
        failure_reason: str,
        context_summary: str,
        model_id: Optional[str] = None,
        use_structured_output: bool = True,
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

        dependency_example = (
            "Task dependencies form a directed acyclic graph (DAG). Example:\n"
            "  task-1 -> task-2 -> task-3\n"
            "  task-1 -> task-4\n"
            "Dependencies must strictly reference valid task IDs defined in the plan.\n"
        )

        if use_structured_output:
            system_prompt = (
                f"You are an engineering planner performing REPLANNING.\n\n"
                f"The previous plan failed.\n"
                f"Failure reason: {failure_reason}\n\n"
                f"Previous plan:\n{previous_summary}\n"
                f"Context:\n{context_summary}\n\n"
                f"{dependency_example}\n"
                f"Produce a revised structured plan adhering to the output schema.\n"
            )
        else:
            system_prompt = (
                f"You are an engineering planner performing REPLANNING.\n\n"
                f"The previous plan failed.\n"
                f"Failure reason: {failure_reason}\n\n"
                f"Previous plan:\n{previous_summary}\n"
                f"Context:\n{context_summary}\n\n"
                f"{dependency_example}\n"
                f"Produce a revised structured JSON plan in a ```json code block.\n"
            )

        return ModelRequest(
            model_id=model_id or "",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Replan this objective: {objective}"},
            ],
            structured_output_schema=PLAN_SCHEMA if use_structured_output else None,
        )

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _try_parse_plan(self, text: str) -> Optional[Dict[str, Any]]:
        """Attempt to extract a JSON plan from model text output."""
        return _extract_json_from_text(text)

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
        """
        task_ids = list(data.get("task_ids", []))
        dependencies = dict(data.get("dependencies", {}))
        task_details: Dict[str, Dict[str, Any]] = {}

        # 1. From "tasks" list of dicts (primary structured format)
        raw_tasks = data.get("tasks", [])
        if isinstance(raw_tasks, list):
            for item in raw_tasks:
                if isinstance(item, Mapping):
                    tid = str(item.get("id") or item.get("task_id") or "").strip()
                    if tid:
                        if tid not in task_ids:
                            task_ids.append(tid)
                        deps = item.get("dependencies", [])
                        if isinstance(deps, list):
                            dependencies[tid] = [str(d) for d in deps]
                        elif tid not in dependencies:
                            dependencies[tid] = []
                        task_details[tid] = dict(item)

        # 2. From "task_details" mapping (legacy format)
        raw_task_details = data.get("task_details", {})
        if isinstance(raw_task_details, Mapping):
            for tid, details in raw_task_details.items():
                if isinstance(details, Mapping):
                    if tid not in task_ids:
                        task_ids.append(tid)
                    task_details[tid] = dict(details)

        # Validate dependency structure using centralized validation
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
            assumptions=_ensure_str_list(data.get("assumptions")),
            affected_areas=_ensure_str_list(data.get("affected_areas")),
            task_ids=task_ids,
            dependencies=dependencies,
            validation_strategy=_ensure_str_list(data.get("validation_strategy")),
            risks=_ensure_str_list(data.get("risks")),
            completion_criteria=_ensure_str_list(data.get("completion_criteria")),
            task_details=task_details,
        )
