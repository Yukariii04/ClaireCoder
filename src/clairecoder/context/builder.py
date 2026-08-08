import uuid
from typing import Any, Dict, List, Optional
from .types import EngineeringContext, MemoryRecord, ContextConstructionError

class ContextBuilder:
    """Builds immutable EngineeringContext snapshots."""
    
    def __init__(self):
        self._session_info: Dict[str, Any] = {}
        self._workflow_info: Dict[str, Any] = {}
        self._task_info: Dict[str, Any] = {}
        self._repository_state: Dict[str, Any] = {}
        self._memories: List[MemoryRecord] = []
        self._tool_results: List[Dict[str, Any]] = []
        self._instructions: List[str] = []
        self._metadata: Dict[str, Any] = {}

    def with_session(self, session_info: Dict[str, Any]) -> 'ContextBuilder':
        self._session_info.update(session_info)
        return self

    def with_workflow(self, workflow_info: Dict[str, Any]) -> 'ContextBuilder':
        self._workflow_info.update(workflow_info)
        return self

    def with_task(self, task_info: Dict[str, Any]) -> 'ContextBuilder':
        self._task_info.update(task_info)
        return self

    def with_repository_state(self, repository_state: Dict[str, Any]) -> 'ContextBuilder':
        self._repository_state.update(repository_state)
        return self

    def add_memory(self, memory: MemoryRecord) -> 'ContextBuilder':
        self._memories.append(memory)
        return self

    def add_tool_result(self, tool_result: Dict[str, Any]) -> 'ContextBuilder':
        self._tool_results.append(tool_result)
        return self

    def add_instruction(self, instruction: str) -> 'ContextBuilder':
        self._instructions.append(instruction)
        return self
        
    def with_metadata(self, key: str, value: Any) -> 'ContextBuilder':
        self._metadata[key] = value
        return self

    def build(self) -> EngineeringContext:
        """Construct an immutable EngineeringContext snapshot.
        
        This satisfies CC-PRD-008 Section 22 and 23.
        The resulting object and its collections are frozen/tuples.
        """
        # EngineeringContext.__post_init__ will deeply freeze these structures.
        return EngineeringContext(
            id=str(uuid.uuid4()),
            session_info=dict(self._session_info),
            workflow_info=dict(self._workflow_info),
            task_info=dict(self._task_info),
            repository_state=dict(self._repository_state),
            memories=tuple(self._memories),
            tool_results=tuple(dict(tr) for tr in self._tool_results),
            instructions=tuple(self._instructions),
            metadata=dict(self._metadata)
        )
