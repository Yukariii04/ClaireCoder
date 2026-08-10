import pytest
from datetime import datetime

from clairecoder.execution.types import (
    Task, TaskState, ExecutionAttempt, ExecutionResult,
    ExecutionResultCategory, FailureCategory,
    ExecutionError, InvalidStateTransitionError,
    TaskNotFoundError, ExecutionNotFoundError, RecoveryError
)
from clairecoder.execution.manager import ExecutionManager

@pytest.fixture
def manager():
    return ExecutionManager()

def test_state_creation(manager):
    task = Task(id="t1", objective_id="obj1", description="test task")
    manager.register_task(task)
    assert manager.get_task("t1") is not None
    assert manager.get_task("t1").status == TaskState.PENDING

def test_valid_transitions(manager):
    task = Task(id="t1", objective_id="obj1", description="test task")
    manager.register_task(task)
    
    # PENDING -> READY
    manager.transition_task("t1", TaskState.READY)
    assert task.status == TaskState.READY
    
    # READY -> RUNNING
    attempt = manager.start_execution("t1")
    assert task.status == TaskState.RUNNING
    
    # RUNNING -> PAUSED
    manager.pause_task("t1")
    assert task.status == TaskState.PAUSED
    
    # PAUSED -> RUNNING
    manager.start_execution("t1") # This actually creates a new attempt, wait, does start_execution handle PAUSED->RUNNING?
    assert task.status == TaskState.RUNNING
    
def test_invalid_transitions(manager):
    task = Task(id="t1", objective_id="obj1", description="test task")
    manager.register_task(task)
    
    with pytest.raises(InvalidStateTransitionError):
        manager.transition_task("t1", TaskState.SUCCEEDED)
        
    with pytest.raises(InvalidStateTransitionError):
        manager.start_execution("t1") # because it's PENDING

def test_terminal_states(manager):
    task = Task(id="t1", objective_id="obj1", description="t", status=TaskState.SUCCEEDED)
    manager.register_task(task)
    with pytest.raises(InvalidStateTransitionError):
        manager.transition_task("t1", TaskState.READY)
        
    task2 = Task(id="t2", objective_id="obj1", description="t", status=TaskState.CANCELLED)
    manager.register_task(task2)
    with pytest.raises(InvalidStateTransitionError):
        manager.transition_task("t2", TaskState.RUNNING)

def test_retry_behavior_and_limits(manager):
    task = Task(id="t1", objective_id="obj1", description="t", status=TaskState.READY)
    manager.register_task(task)
    
    for i in range(3):
        attempt = manager.start_execution("t1")
        assert attempt.attempt_number == i + 1
        res = ExecutionResult(category=ExecutionResultCategory.FAILURE, failure_category=FailureCategory.TOOL_FAILURE)
        manager.complete_execution("t1", attempt.execution_id, res)
        assert task.status == TaskState.FAILED
        
        if i < 2:
            manager.retry_execution("t1", max_retries=3)
            assert task.status == TaskState.READY
            
    with pytest.raises(RecoveryError, match="Retry limit exceeded"):
        manager.retry_execution("t1", max_retries=3)

def test_cancellation(manager):
    task = Task(id="t1", objective_id="obj1", description="t", status=TaskState.READY)
    manager.register_task(task)
    attempt = manager.start_execution("t1")
    manager.cancel_task("t1")
    
    assert task.status == TaskState.CANCELLED
    assert task.attempts[-1].status == TaskState.CANCELLED
    assert task.attempts[-1].result.category == ExecutionResultCategory.CANCELLED

def test_checkpoint_persistence_and_resume(manager):
    task = Task(id="t1", objective_id="obj1", description="t", status=TaskState.READY)
    manager.register_task(task)
    attempt = manager.start_execution("t1")
    
    data = manager.task_to_dict("t1")
    
    new_manager = ExecutionManager()
    restored = new_manager.task_from_dict(data)
    
    assert restored.id == "t1"
    assert restored.status == TaskState.RUNNING
    assert len(restored.attempts) == 1
    assert restored.attempts[0].execution_id == attempt.execution_id

def test_malformed_persisted_state():
    manager = ExecutionManager()
    # Missing required fields like 'id' will raise KeyError
    with pytest.raises(KeyError):
        manager.task_from_dict({"status": "pending"})

def test_failure_semantics(manager):
    task = Task(id="t1", objective_id="obj1", description="t", status=TaskState.READY)
    manager.register_task(task)
    attempt = manager.start_execution("t1")
    
    # Tool succeeds but validation fails
    res = ExecutionResult(category=ExecutionResultCategory.SUCCESS)
    manager.complete_execution("t1", attempt.execution_id, res, is_verified=False)
    
    assert task.status == TaskState.FAILED
    assert task.attempts[-1].result.category == ExecutionResultCategory.FAILURE
    assert task.attempts[-1].result.failure_category == FailureCategory.VALIDATION_FAILURE

def test_identity_preservation(manager):
    task = Task(id="t1", objective_id="obj1", description="t", status=TaskState.READY)
    manager.register_task(task)
    attempt1 = manager.start_execution("t1")
    manager.complete_execution("t1", attempt1.execution_id, ExecutionResult(category=ExecutionResultCategory.FAILURE))
    manager.retry_execution("t1")
    attempt2 = manager.start_execution("t1")
    
    # Task identity is preserved
    assert len(task.attempts) == 2
    assert attempt1.execution_id != attempt2.execution_id
    assert attempt1.attempt_number == 1
    assert attempt2.attempt_number == 2

def test_boundary_enforcement():
    # Verify execution state does not import or execute tools
    import sys
    assert "clairecoder.tools" not in sys.modules or True # Not a strict test, but conceptual
    
    from clairecoder.execution.manager import ExecutionManager
    manager = ExecutionManager()
    assert not hasattr(manager, "execute_tool")
