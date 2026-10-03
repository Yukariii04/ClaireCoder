"""Workflow & Planning subsystem.

CC-PRD-004: Workflow, Context & Engineering Session System.
CC-ADR-004: Workflow, Context & Engineering Session Architecture.

Correction #13: Exports TaskGraph, TaskType, TaskGraphError.
"""

from .types import (
    Workflow,
    WorkflowState,
    Plan,
    PlanningLevel,
    Task,
    TaskState,
    TaskStatus,
    TaskType,
    WorkflowError,
    WorkflowStateError,
    DependencyCycleError,
    DependencyNotFoundError,
    InvalidDependencyError,
    PlanningError,
    TaskGraphError,
)
from .manager import WorkflowManager
from .planner import Planner, PLAN_SCHEMA, validate_plan, parse_structured_plan
from .task_graph import TaskGraph
from .dependencies import (
    validate_dependencies,
    topological_order,
    get_ready_tasks,
)

__all__ = [
    "Workflow",
    "WorkflowState",
    "Plan",
    "PlanningLevel",
    "Task",
    "TaskState",
    "TaskStatus",
    "TaskType",
    "WorkflowError",
    "WorkflowStateError",
    "DependencyCycleError",
    "DependencyNotFoundError",
    "InvalidDependencyError",
    "PlanningError",
    "TaskGraphError",
    "WorkflowManager",
    "Planner",
    "PLAN_SCHEMA",
    "validate_plan",
    "parse_structured_plan",
    "TaskGraph",
    "validate_dependencies",
    "topological_order",
    "get_ready_tasks",
]
