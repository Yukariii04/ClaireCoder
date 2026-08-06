from typing import Dict, List, Optional
from .base import Tool
from .types import (
    ToolMetadata, ToolCategory, ToolAvailability, 
    ToolNotFoundError, ToolUnavailableError
)

class ToolRegistry:
    """Registry for discovering and managing available Tools.
    
    The registry provides the Engineering Engine with a discoverable set
    of capabilities. Registration does NOT grant execution authority;
    authorization is handled by the Permission Engine through the ToolExecutor.
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool. Does NOT grant execution authority."""
        self._tools[tool.metadata.id] = tool

    def unregister(self, tool_id: str) -> None:
        """Remove a tool from the registry."""
        if tool_id in self._tools:
            del self._tools[tool_id]

    def get(self, tool_id: str) -> Tool:
        """Retrieve a registered tool by ID.
        
        Raises ToolNotFoundError if the tool is not registered.
        Raises ToolUnavailableError if the tool is registered but not available.
        """
        tool = self._tools.get(tool_id)
        if not tool:
            raise ToolNotFoundError(f"Tool not found: {tool_id}")
        if tool.metadata.availability not in (ToolAvailability.INSTALLED, ToolAvailability.ENABLED):
            raise ToolUnavailableError(
                f"Tool '{tool_id}' is {tool.metadata.availability.value}"
            )
        return tool

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[Tool]:
        """List available tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.metadata.category == category]
        return tools

    def list_available(self) -> List[Tool]:
        """List only tools that are currently available for use."""
        return [
            t for t in self._tools.values()
            if t.metadata.availability in (ToolAvailability.INSTALLED, ToolAvailability.ENABLED)
        ]

    def is_registered(self, tool_id: str) -> bool:
        """Check if a tool is registered."""
        return tool_id in self._tools
