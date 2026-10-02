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

    ALIASES = {
        "list_dir": "filesystem.list",
        "read_file": "filesystem.read",
        "write_to_file": "filesystem.write",
        "replace_file_content": "filesystem.replace",
        "delete_file": "filesystem.delete",
        "run_command": "shell.execute",
        "terminal": "shell.execute",
        "search": "search.text",
        "search_text": "search.text",
        "run_tests": "testing.run",
    }

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool. Does NOT grant execution authority."""
        self._tools[tool.metadata.id] = tool

    def unregister(self, tool_id: str) -> None:
        """Remove a tool from the registry."""
        resolved = self.ALIASES.get(tool_id, tool_id)
        if resolved in self._tools:
            del self._tools[resolved]
        elif tool_id in self._tools:
            del self._tools[tool_id]

    def get(self, tool_id: str) -> Tool:
        """Retrieve a registered tool by ID or alias.
        
        Raises ToolNotFoundError if the tool is not registered.
        Raises ToolUnavailableError if the tool is registered but not available.
        """
        resolved = self.ALIASES.get(tool_id, tool_id)
        tool = self._tools.get(resolved) or self._tools.get(tool_id)
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
        """Check if a tool or alias is registered."""
        resolved = self.ALIASES.get(tool_id, tool_id)
        return (resolved in self._tools) or (tool_id in self._tools)

    @classmethod
    def create_default(cls) -> 'ToolRegistry':
        """Create a registry pre-populated with default core tools."""
        from .core import (
            ReadFileTool, WriteFileTool, ReplaceFileContentTool,
            ListDirTool, DeleteFileTool, SearchTool, TerminalTool,
            GitStatusTool, GitCommitTool, RunTestsTool, DiagnosticsTool
        )
        registry = cls()
        for tool_cls in (
            ReadFileTool, WriteFileTool, ReplaceFileContentTool,
            ListDirTool, DeleteFileTool, SearchTool, TerminalTool,
            GitStatusTool, GitCommitTool, RunTestsTool, DiagnosticsTool
        ):
            registry.register(tool_cls())
        return registry
