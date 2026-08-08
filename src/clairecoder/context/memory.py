from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .types import MemoryRecord, MemoryScope, MemoryCategory, MemoryStatus, MemoryNotFoundError

class MemoryStore(ABC):
    """Interface for Memory Store operations (CC-PRD-008 Section 29)."""

    @abstractmethod
    def create_memory(self, record: MemoryRecord) -> None:
        """Store a new memory record."""
        pass

    @abstractmethod
    def get_memory(self, memory_id: str) -> MemoryRecord:
        """Retrieve a specific memory by ID. Raises MemoryNotFoundError if missing."""
        pass

    @abstractmethod
    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> MemoryRecord:
        """Update an existing memory record."""
        pass

    @abstractmethod
    def delete_memory(self, memory_id: str) -> None:
        """Permanently delete a memory record."""
        pass

    @abstractmethod
    def retrieve_memory(self, scope: Optional[MemoryScope] = None, 
                        category: Optional[MemoryCategory] = None,
                        status: MemoryStatus = MemoryStatus.ACTIVE,
                        project_id: Optional[str] = None,
                        session_id: Optional[str] = None) -> List[MemoryRecord]:
        """Retrieve memories based on scope, category, status, and isolation boundaries."""
        pass

    @abstractmethod
    def invalidate_memory(self, memory_id: str) -> None:
        """Mark a memory record as INVALID."""
        pass

class InMemoryStore(MemoryStore):
    """Simple in-memory implementation of the MemoryStore interface."""

    def __init__(self):
        self._records: Dict[str, MemoryRecord] = {}

    def create_memory(self, record: MemoryRecord) -> None:
        self._records[record.id] = record

    def get_memory(self, memory_id: str) -> MemoryRecord:
        if memory_id not in self._records:
            raise MemoryNotFoundError(f"Memory '{memory_id}' not found.")
        return self._records[memory_id]

    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> MemoryRecord:
        record = self.get_memory(memory_id)
        # Prevent mutation of identity and architectural fields
        immutable_fields = {"id", "category", "scope", "provenance", "created_at"}
        for key in updates:
            if key in immutable_fields:
                raise ValueError(f"Cannot update immutable field: {key}")

        # Convert frozen dataclass to dict to apply updates
        data = {
            "id": record.id,
            "category": record.category,
            "scope": record.scope,
            "content": record.content,
            "provenance": record.provenance,
            "status": record.status,
            "trust": record.trust,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "metadata": dict(record.metadata),
        }
        data.update(updates)
        
        # Ensure metadata is still a mapping proxy
        from types import MappingProxyType
        data["metadata"] = MappingProxyType(dict(data["metadata"]))
        
        new_record = MemoryRecord(**data)
        self._records[memory_id] = new_record
        return new_record

    def delete_memory(self, memory_id: str) -> None:
        if memory_id in self._records:
            del self._records[memory_id]

    def retrieve_memory(self, scope: Optional[MemoryScope] = None, 
                        category: Optional[MemoryCategory] = None,
                        status: MemoryStatus = MemoryStatus.ACTIVE,
                        project_id: Optional[str] = None,
                        session_id: Optional[str] = None) -> List[MemoryRecord]:
        results = list(self._records.values())
        if scope:
            results = [r for r in results if r.scope == scope]
        if category:
            results = [r for r in results if r.category == category]
        if status:
            results = [r for r in results if r.status == status]
            
        # Enforce explicit isolation boundaries
        if project_id is not None:
            results = [r for r in results if r.metadata.get("project_id") == project_id]
        if session_id is not None:
            results = [r for r in results if r.metadata.get("session_id") == session_id]
            
        return results

    def invalidate_memory(self, memory_id: str) -> None:
        self.update_memory(memory_id, {"status": MemoryStatus.INVALID})
