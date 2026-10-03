"""Dependency validation for task graphs.

CC-PRD-004 Section 9: Task Dependencies.
CC-ADR-004 Section 8: Task Dependencies.

Validates dependency existence, invalid references, ordering, and cycles.
"""

from typing import Dict, List, Set

from .types import (
    DependencyCycleError,
    DependencyNotFoundError,
    InvalidDependencyError,
    Task,
    TaskState,
)


def validate_dependencies(tasks: List[Task]) -> None:
    """Validate a set of tasks for dependency correctness.

    Checks:
    1. All referenced dependencies exist within the task set.
    2. No task depends on itself.
    3. No cycles exist in the dependency graph.

    Raises:
        DependencyNotFoundError: A dependency references a non-existent task.
        InvalidDependencyError: A task depends on itself.
        DependencyCycleError: A cycle is detected.
    """
    task_ids: Set[str] = {t.id for t in tasks}

    for task in tasks:
        for dep_id in task.dependencies:
            if dep_id not in task_ids:
                raise DependencyNotFoundError(
                    f"Task '{task.id}' depends on '{dep_id}' which does not exist"
                )
            if dep_id == task.id:
                raise InvalidDependencyError(
                    f"Task '{task.id}' cannot depend on itself"
                )

    # Cycle detection via topological sort (Kahn's algorithm)
    _detect_cycles(tasks, task_ids)


def _detect_cycles(tasks: List[Task], task_ids: Set[str]) -> None:
    """Detect cycles using Kahn's algorithm for topological sorting."""
    adjacency: Dict[str, List[str]] = {t.id: [] for t in tasks}
    in_degree: Dict[str, int] = {t.id: 0 for t in tasks}

    for task in tasks:
        for dep_id in task.dependencies:
            # dep_id → task.id  (dep must complete before task)
            adjacency[dep_id].append(task.id)
            in_degree[task.id] += 1

    queue: List[str] = [tid for tid, deg in in_degree.items() if deg == 0]
    visited_count = 0

    while queue:
        node = queue.pop(0)
        visited_count += 1
        for neighbour in adjacency[node]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if visited_count != len(task_ids):
        raise DependencyCycleError("Dependency cycle detected in task graph")


def topological_order(tasks: List[Task]) -> List[str]:
    """Return task IDs in valid dependency order.

    Precondition: validate_dependencies() has already passed.
    """
    task_map = {t.id: t for t in tasks}
    in_degree: Dict[str, int] = {t.id: 0 for t in tasks}
    adjacency: Dict[str, List[str]] = {t.id: [] for t in tasks}

    for task in tasks:
        for dep_id in task.dependencies:
            adjacency[dep_id].append(task.id)
            in_degree[task.id] += 1

    queue: List[str] = [tid for tid, deg in in_degree.items() if deg == 0]
    result: List[str] = []

    while queue:
        # Sort to provide deterministic ordering among independent tasks
        queue.sort()
        node = queue.pop(0)
        result.append(node)
        for neighbour in adjacency[node]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    return result


def get_ready_tasks(tasks: List[Task]) -> List[Task]:
    """Return tasks whose dependencies are all COMPLETE.

    CC-PRD-004 Section 9: A dependent Task SHALL not become executable
    until its required dependencies are satisfied.

    Correction #13: Also returns tasks already in READY state.
    """
    completed_ids: Set[str] = {
        t.id for t in tasks if t.status == TaskState.SUCCEEDED
    }

    ready: List[Task] = []
    for task in tasks:
        # Already READY — include directly
        if task.status == TaskState.READY:
            ready.append(task)
            continue
        # PENDING with all deps satisfied — promote to ready
        if task.status == TaskState.PENDING:
            if all(dep_id in completed_ids for dep_id in task.dependencies):
                ready.append(task)

    return ready


def validate_plan_dependencies(
    task_ids: list, dependencies: dict
) -> None:
    """Validate a Plan's dependency structure before it becomes active.

    Performs all dependency checks (existence, self-reference, cycles) by
    constructing minimal temporary Task representations and delegating to
    validate_dependencies().

    Also validates structural integrity:
    - task_ids must be a list of strings
    - dependencies must be a dict mapping strings to lists of strings
    - dependency keys must correspond to task_ids
    - dependency values must reference task_ids

    Raises:
        InvalidDependencyError: Structural issues (wrong types, unknown keys).
        DependencyNotFoundError: A dependency references a non-existent task.
        DependencyCycleError: A cycle is detected.
    """
    # Structural type checks
    if not isinstance(task_ids, list):
        raise InvalidDependencyError(
            f"task_ids must be a list, got {type(task_ids).__name__}"
        )
    for tid in task_ids:
        if not isinstance(tid, str):
            raise InvalidDependencyError(
                f"task_ids entries must be strings, got {type(tid).__name__}"
            )

    if len(task_ids) != len(set(task_ids)):
        raise InvalidDependencyError("Duplicate task IDs are not allowed in a plan")

    if not isinstance(dependencies, dict):
        raise InvalidDependencyError(
            f"dependencies must be a dict, got {type(dependencies).__name__}"
        )

    task_id_set = set(task_ids)

    # Validate dependency keys belong to task_ids
    for key in dependencies:
        if not isinstance(key, str):
            raise InvalidDependencyError(
                f"dependency keys must be strings, got {type(key).__name__}"
            )
        if key not in task_id_set:
            raise InvalidDependencyError(
                f"dependency key '{key}' does not correspond to any task_id"
            )
        dep_list = dependencies[key]
        if not isinstance(dep_list, list):
            raise InvalidDependencyError(
                f"dependency values must be lists, got {type(dep_list).__name__} for key '{key}'"
            )
        for dep in dep_list:
            if not isinstance(dep, str):
                raise InvalidDependencyError(
                    f"dependency entries must be strings, got {type(dep).__name__}"
                )

    # Build temporary Task objects and delegate to centralized validation
    temp_tasks = []
    for tid in task_ids:
        deps = dependencies.get(tid, [])
        temp_tasks.append(
            Task(id=tid, objective_id="_plan_validation", description=tid, dependencies=deps)
        )

    validate_dependencies(temp_tasks)

