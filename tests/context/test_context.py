import pytest
from dataclasses import FrozenInstanceError
from clairecoder.context.types import (
    ContextSource, MemoryCategory, MemoryScope, MemoryStatus, MemoryTrust,
    Provenance, MemoryRecord, EngineeringContext, ContextConstructionError,
    MemoryNotFoundError
)
from clairecoder.context.builder import ContextBuilder
from clairecoder.context.memory import InMemoryStore

def test_engineering_context_immutability():
    """AC-009: Constructed Context snapshots cannot be silently mutated."""
    builder = ContextBuilder()
    builder.with_session({"id": "s1"})
    context = builder.build()
    
    with pytest.raises(FrozenInstanceError):
        context.session_info = {"id": "s2"}
        
    # Test that mutating the original dict doesn't mutate the context
    session_info = {"id": "s1", "nested": {"val": 1}}
    builder2 = ContextBuilder().with_session(session_info)
    context2 = builder2.build()
    session_info["id"] = "s2"
    session_info["nested"]["val"] = 2
    assert context2.session_info["id"] == "s1"
    assert context2.session_info["nested"]["val"] == 1
    
    # Test nested immutability against modification via MappingProxyType access
    with pytest.raises(TypeError):
        context2.session_info["nested"]["val"] = 3

def test_memory_creation_and_update():
    """AC-002: MemoryRecord exists with explicit identity and metadata.
       AC-003: Session, Project, Decision, and Task Memory are supported."""
    store = InMemoryStore()
    prov = Provenance(source=ContextSource.USER, identity="user1")
    record = MemoryRecord(
        id="mem1",
        category=MemoryCategory.DECISION,
        scope=MemoryScope.PROJECT,
        content="Use SQLite",
        provenance=prov
    )
    store.create_memory(record)
    
    fetched = store.get_memory("mem1")
    assert fetched.id == "mem1"
    assert fetched.category == MemoryCategory.DECISION
    assert fetched.content == "Use SQLite"
    
    # Test update
    store.update_memory("mem1", {"content": "Use Postgres"})
    updated = store.get_memory("mem1")
    assert updated.content == "Use Postgres"
    
    # Test immutable fields cannot be updated
    with pytest.raises(ValueError, match="Cannot update immutable field: id"):
        store.update_memory("mem1", {"id": "mem2"})

    # Test deep immutability of metadata
    meta = {"nested": {"val": 1}}
    record_with_meta = MemoryRecord(
        id="mem2",
        category=MemoryCategory.DECISION,
        scope=MemoryScope.PROJECT,
        content="...",
        provenance=prov,
        metadata=meta
    )
    # Original dict mutation shouldn't affect record
    meta["nested"]["val"] = 2
    assert record_with_meta.metadata["nested"]["val"] == 1
    
    # Attempting to mutate via proxy should fail
    with pytest.raises(TypeError):
        record_with_meta.metadata["nested"]["val"] = 3

def test_memory_invalidation():
    """AC-011: Memory can be invalidated without necessarily being deleted."""
    store = InMemoryStore()
    prov = Provenance(source=ContextSource.SYSTEM, identity="sys")
    record = MemoryRecord(
        id="mem1",
        category=MemoryCategory.TASK,
        scope=MemoryScope.TASK,
        content="data",
        provenance=prov
    )
    store.create_memory(record)
    
    store.invalidate_memory("mem1")
    fetched = store.get_memory("mem1")
    assert fetched.status == MemoryStatus.INVALID
    
    # Verify it doesn't appear in default active retrieval
    active = store.retrieve_memory(status=MemoryStatus.ACTIVE)
    assert len(active) == 0

def test_context_construction():
    """AC-007: Context can be assembled for a specific engineering operation."""
    prov = Provenance(source=ContextSource.SYSTEM, identity="sys")
    record = MemoryRecord(
        id="mem1", category=MemoryCategory.SESSION, scope=MemoryScope.SESSION, content="data", provenance=prov
    )
    
    builder = ContextBuilder()
    builder.with_session({"session_id": "123"})
    builder.with_task({"task_id": "456"})
    builder.with_workflow({"workflow": "coding"})
    builder.with_repository_state({"git_hash": "abc"})
    builder.add_memory(record)
    builder.add_tool_result({"tool": "ls", "output": "file.py"})
    builder.add_instruction("Fix the bug")
    builder.with_metadata("priority", "high")
    
    context = builder.build()
    
    assert context.session_info["session_id"] == "123"
    assert context.task_info["task_id"] == "456"
    assert context.workflow_info["workflow"] == "coding"
    assert context.repository_state["git_hash"] == "abc"
    assert len(context.memories) == 1
    assert context.memories[0].id == "mem1"
    assert len(context.tool_results) == 1
    assert len(context.instructions) == 1
    assert context.metadata["priority"] == "high"
    assert context.id is not None

def test_security_boundary_no_execution():
    """Ensure EngineeringContext and ContextBuilder do not have execution capabilities."""
    context = ContextBuilder().build()
    assert not hasattr(context, "execute")
    assert not hasattr(context, "grant")
    assert not hasattr(context, "invoke")
    
def test_project_isolation():
    """AC-018: Project memory cannot automatically leak into unrelated projects."""
    store = InMemoryStore()
    prov = Provenance(source=ContextSource.USER, identity="sys")
    
    # Simulate Project A
    record_a = MemoryRecord(id="a1", category=MemoryCategory.PROJECT, scope=MemoryScope.PROJECT, content="A", provenance=prov, metadata={"project_id": "ProjectA"})
    store.create_memory(record_a)
    
    # Simulate Project B
    record_b = MemoryRecord(id="b1", category=MemoryCategory.PROJECT, scope=MemoryScope.PROJECT, content="B", provenance=prov, metadata={"project_id": "ProjectB"})
    store.create_memory(record_b)
    
    # Retrieval for Project A uses the isolation boundary natively
    project_a_mems = store.retrieve_memory(scope=MemoryScope.PROJECT, project_id="ProjectA")
    
    assert len(project_a_mems) == 1
    assert project_a_mems[0].id == "a1"
    
    project_b_mems = store.retrieve_memory(scope=MemoryScope.PROJECT, project_id="ProjectB")
    assert len(project_b_mems) == 1
    assert project_b_mems[0].id == "b1"

def test_tool_result_immutability():
    """Verify deep immutability of tool results, including nested structures in tuples."""
    original_tool_result = {
        "tool": "ls",
        "output": {
            "files": ["a.txt", "b.txt"],
            "nested": {"key": "value"}
        }
    }
    
    builder = ContextBuilder()
    builder.add_tool_result(original_tool_result)
    context = builder.build()
    
    # 1. Mutating original dict shouldn't affect context
    original_tool_result["tool"] = "changed"
    original_tool_result["output"]["files"].append("c.txt")
    original_tool_result["output"]["nested"]["key"] = "changed"
    
    assert context.tool_results[0]["tool"] == "ls"
    assert "c.txt" not in context.tool_results[0]["output"]["files"]
    assert context.tool_results[0]["output"]["nested"]["key"] == "value"
    
    # 2. Mutating fields on context.tool_results should fail
    with pytest.raises(TypeError):
        context.tool_results[0]["tool"] = "changed"
        
    # 3. Mutating nested structures should fail
    with pytest.raises(TypeError):
        context.tool_results[0]["output"]["nested"] = "changed"
        
    with pytest.raises(TypeError):
        context.tool_results[0]["output"]["files"][0] = "changed"

