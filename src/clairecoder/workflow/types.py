"""Workflow & Planning type definitions.

CC-PRD-004 Section 6–10: Workflow, Task, dependency, and state representation.
CC-ADR-004 Section 5–8: Workflow architecture, adaptive planning, task model.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# =============================================================================
# WORKFLOW STATE  (CC-PRD-004 Section 7)
# =============================================================================

class WorkflowState(str, Enum):
    """Lifecycle states for a Workflow.

    CC-PRD-004 Section 7:
        CREATED → PLANNED → ACTIVE → VALIDATING → COMPLETE / FAILED → REPLANNING → ACTIVE
    """
    CREATED = "created"
    PLANNED = "planned"
    ACTIVE = "active"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"
    REPLANNING = "replanning"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    INTERRUPTED = "interrupted"


# =============================================================================
# PLANNING LEVEL  (CC-ADR-004 Section 6.2)
# =============================================================================

class PlanningLevel(int, Enum):
    """Adaptive planning depth.

    CC-ADR-004 Section 6.2:
        LEVEL 0 — Direct (simple, well-defined operations)
        LEVEL 1 — Lightweight (limited repository inspection)
        LEVEL 2 — Structured (multiple files/components)
        LEVEL 3 — Deep (complex architectural / multi-stage)
    """
    DIRECT = 0
    LIGHTWEIGHT = 1
    STRUCTURED = 2
    DEEP = 3


# =============================================================================
# WORKFLOW  (CC-PRD-004 Section 6, CC-ADR-004 Section 5.1)
# =============================================================================

@dataclass
class Workflow:
    """A structured engineering process.

    CC-PRD-004 Section 6: A Workflow represents the structured process through
    which an engineering objective is completed.

    CC-ADR-004 Section 5.1: Examples include implementation, debugging, review,
    research, testing, refactoring.
    """
    id: str
    objective_id: str
    description: str
    state: WorkflowState = WorkflowState.CREATED
    task_ids: List[str] = field(default_factory=list)
    completion_criteria: List[str] = field(default_factory=list)
    validation_requirements: List[str] = field(default_factory=list)
    relevant_skills: List[str] = field(default_factory=list)
    relevant_tools: List[str] = field(default_factory=list)
    context_requirements: List[str] = field(default_factory=list)
    planning_level: PlanningLevel = PlanningLevel.STRUCTURED
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# PLAN  (CC-ADR-004 Section 6.3)
# =============================================================================

@dataclass
class Plan:
    """A planning artifact produced by the Planner.

    CC-ADR-004 Section 6.3: A plan SHOULD contain objective, assumptions,
    affected areas, tasks, dependencies, validation strategy, risks,
    completion criteria.

    The plan SHALL be persistable inside the Engineering Session.
    """
    id: str
    workflow_id: str
    objective: str
    planning_level: PlanningLevel
    assumptions: List[str] = field(default_factory=list)
    affected_areas: List[str] = field(default_factory=list)
    task_ids: List[str] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    validation_strategy: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    completion_criteria: List[str] = field(default_factory=list)
    is_superseded: bool = False
    superseded_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# ERRORS
# =============================================================================

class WorkflowError(Exception):
    """Base error for Workflow system failures."""
    pass


class WorkflowStateError(WorkflowError):
    """Raised when an invalid workflow state transition is attempted."""
    pass


class DependencyCycleError(WorkflowError):
    """Raised when a dependency cycle is detected in a task graph."""
    pass


class DependencyNotFoundError(WorkflowError):
    """Raised when a dependency references a non-existent task."""
    pass


class InvalidDependencyError(WorkflowError):
    """Raised when a dependency relationship is malformed or invalid."""
    pass


class PlanningError(WorkflowError):
    """Raised when planning fails."""
    pass
