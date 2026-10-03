"""Registry for discovering, resolving, and managing Tools.

Correction #19 §6:
- deterministic tool lookup
- duplicate registration handling
- unknown-tool error
- test injection
- no dynamic plugin loading
"""

from typing import Any, Dict, List, Optional
from .errors import DuplicateToolError, UnknownToolError
from .types import (
    ToolAvailability,
    ToolCategory,
    ToolMetadata,
    ToolNotFoundError,
    ToolUnavailableError,
)


class ToolRegistry:
    """Registry for discovering, resolving, and managing Tools."""

    ALIASES: Dict[str, str] = {
        "list_dir": "list_files",
        "filesystem.list": "list_files",
        "filesystem.read": "read_file",
        "filesystem.write": "write_file",
        "filesystem.replace": "replace_file_content",
        "filesystem.delete": "delete_file",
        "shell.execute": "run_command",
        "terminal": "run_command",
        "search": "search.text",
        "search_text": "search.text",
        "run_tests": "testing.run",
    }

    def __init__(
        self,
        workspace: Optional[Any] = None,
        tools: Optional[List[Any]] = None,
    ) -> None:
        self._workspace = workspace
        self._tools: Dict[str, Any] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    @property
    def workspace(self) -> Optional[Any]:
        """Workspace associated with this registry, if any."""
        return self._workspace

    def _get_tool_identifier(self, tool: Any) -> str:
        """Derive the canonical lookup key for a tool."""
        if hasattr(tool, "name") and isinstance(tool.name, str) and tool.name.strip():
            return tool.name.strip()
        if hasattr(tool, "metadata") and hasattr(tool.metadata, "id"):
            return tool.metadata.id
        raise TypeError(f"Cannot register tool without 'name' or 'metadata.id': {type(tool).__name__}")

    def register(self, tool: Any, overwrite: bool = False) -> None:
        """Register a tool.

        Raises DuplicateToolError if a tool with the same name/id is already registered
        and overwrite is False.
        """
        tool_id = self._get_tool_identifier(tool)
        if tool_id in self._tools and not overwrite:
            raise DuplicateToolError(f"Tool already registered: '{tool_id}'", tool_name=tool_id)
        self._tools[tool_id] = tool

    def unregister(self, tool_id: str) -> None:
        """Remove a tool from the registry."""
        resolved = self.ALIASES.get(tool_id, tool_id)
        self._tools.pop(resolved, None)
        self._tools.pop(tool_id, None)

    def resolve(self, name: str) -> Any:
        """Resolve a registered tool by canonical name or alias.

        Raises UnknownToolError if the tool is not found.
        """
        if not name or not isinstance(name, str):
            raise UnknownToolError(f"Invalid tool name: {name!r}", tool_name=str(name))
        clean_name = name.strip()
        if clean_name in self._tools:
            return self._tools[clean_name]
        alias_target = self.ALIASES.get(clean_name)
        if alias_target and alias_target in self._tools:
            return self._tools[alias_target]
        raise UnknownToolError(f"Unknown tool: '{clean_name}'", tool_name=clean_name)

    def execute(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        """Resolve and execute a tool directly via the registry."""
        tool = self.resolve(name)
        if hasattr(tool, "execute"):
            return tool.execute(context=context, arguments=arguments, **kwargs)
        raise TypeError(f"Tool '{name}' does not implement execute()")

    def get(self, tool_id: str) -> Any:
        """Legacy retrieval by tool_id or alias.

        Raises ToolNotFoundError if tool is not registered.
        Raises ToolUnavailableError if tool is disabled.
        """
        resolved = self.ALIASES.get(tool_id, tool_id)
        tool = self._tools.get(resolved) or self._tools.get(tool_id)
        if not tool:
            raise ToolNotFoundError(f"Tool not found: {tool_id}")
        if hasattr(tool, "metadata") and hasattr(tool.metadata, "availability"):
            if tool.metadata.availability not in (ToolAvailability.INSTALLED, ToolAvailability.ENABLED):
                raise ToolUnavailableError(
                    f"Tool '{tool_id}' is {tool.metadata.availability.value}"
                )
        return tool

    def has(self, name: str) -> bool:
        """Check whether a tool or alias is registered."""
        if not name or not isinstance(name, str):
            return False
        clean = name.strip()
        if clean in self._tools:
            return True
        alias = self.ALIASES.get(clean)
        return alias is not None and alias in self._tools

    def is_registered(self, tool_id: str) -> bool:
        """Legacy check if a tool or alias is registered."""
        return self.has(tool_id)

    @property
    def registered_names(self) -> List[str]:
        """Return all registered tool names sorted deterministically."""
        return sorted(self._tools.keys())

    @property
    def registered_tools(self) -> List[Any]:
        """Return all registered tools sorted deterministically by name."""
        return [self._tools[k] for k in sorted(self._tools.keys())]

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[Any]:
        """List available tools, optionally filtered by category."""
        tools = self.registered_tools
        if category:
            tools = [
                t for t in tools
                if hasattr(t, "metadata") and getattr(t.metadata, "category", None) == category
            ]
        return tools

    def list_available(self) -> List[Any]:
        """List only tools that are currently available for use."""
        result = []
        for t in self.registered_tools:
            if hasattr(t, "metadata") and hasattr(t.metadata, "availability"):
                if t.metadata.availability in (ToolAvailability.INSTALLED, ToolAvailability.ENABLED):
                    result.append(t)
            else:
                result.append(t)
        return result

    @classmethod
    def create_default(cls, workspace: Optional[Any] = None) -> "ToolRegistry":
        """Create a registry pre-populated with standard core tools."""
        from .structured import (
            ReadFileTool,
            WriteFileTool,
            DeleteFileTool,
            ListFilesTool,
            RunCommandTool,
        )
        registry = cls()
        registry.register(ReadFileTool(workspace=workspace))
        registry.register(WriteFileTool(workspace=workspace))
        registry.register(DeleteFileTool(workspace=workspace))
        registry.register(ListFilesTool(workspace=workspace))
        registry.register(RunCommandTool(workspace=workspace))
        return registry
