"""Structured Tool abstraction (Correction #19 §3).

Defines the Tool interface producing structured ToolResult instances:
    Tool
        name: str
        description: str
        execute(context, arguments) -> ToolResult
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union

from clairecoder.core.types import ToolResult, ToolState
from clairecoder.workspace.workspace import Workspace


@dataclass
class ToolContext:
    """Execution context provided to a tool during invocation."""

    run_id: Optional[str] = None
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    workspace: Optional[Workspace] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.run_id is not None:
            d["run_id"] = self.run_id
        if self.task_id is not None:
            d["task_id"] = self.task_id
        if self.session_id is not None:
            d["session_id"] = self.session_id
        if self.metadata:
            d["metadata"] = self.metadata
        return d


def normalize_tool_call(
    context: Optional[Any] = None,
    arguments: Optional[Dict[str, Any]] = None,
    kwargs: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[ToolContext], Dict[str, Any]]:
    """Normalize flexible execute() call signatures into (context, arguments).

    Supports:
        execute(context, arguments)
        execute(arguments)
        execute(path="...")
        execute(context, path="...")
    """
    kw = dict(kwargs) if kwargs else {}

    # Case 1: First argument is dict (called as execute({"path": "foo"}))
    if isinstance(context, dict) and arguments is None:
        merged = dict(context)
        merged.update(kw)
        return None, merged

    # Case 2: First argument is ToolContext or object
    ctx: Optional[ToolContext] = None
    if isinstance(context, ToolContext):
        ctx = context
    elif context is not None:
        # Wrap arbitrary object or preserve if has attrs
        ctx = ToolContext(
            run_id=getattr(context, "run_id", None),
            task_id=getattr(context, "task_id", None),
            session_id=getattr(context, "session_id", None),
            workspace=getattr(context, "workspace", None),
            metadata=getattr(context, "metadata", {}),
        )

    # Merge arguments and kwargs
    args: Dict[str, Any] = {}
    if isinstance(arguments, dict):
        args.update(arguments)
    args.update(kw)

    return ctx, args


class Tool(ABC):
    """Abstract base class for all structured ClaireCoder tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The tool's canonical unique identifier (e.g., 'read_file')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool performs."""
        ...

    @abstractmethod
    def execute(
        self,
        context: Optional[Any] = None,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute the tool's capability and return a structured ToolResult.

        Must NOT raise uncaught exceptions; errors should be captured
        into ToolResult(success=False, error=...).
        """
        ...
