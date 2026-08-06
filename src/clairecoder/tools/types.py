from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

class ToolCategory(str, Enum):
    FILESYSTEM = "filesystem"
    REPOSITORY = "repository"
    SHELL = "shell"
    SEARCH = "search"
    TESTING = "testing"
    BUILD = "build"
    VERSION_CONTROL = "version_control"
    BROWSER = "browser"
    WEB = "web"
    IMAGE_VISION = "image_vision"
    PROCESS = "process"
    PACKAGE_MANAGEMENT = "package_management"
    DIAGNOSTICS = "diagnostics"
    PROJECT_SPECIFIC = "project_specific"
    MCP = "mcp"

class ToolAvailability(str, Enum):
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    INCOMPATIBLE = "incompatible"
    BLOCKED = "blocked"

class ExtensionSource(str, Enum):
    BUILT_IN = "built_in"
    LOCAL = "local"
    GITHUB = "github"
    COLLECTION = "collection"
    THIRD_PARTY = "third_party"
    USER_CREATED = "user_created"

class TrustLevel(str, Enum):
    BUILT_IN = "built_in"
    TRUSTED = "trusted"
    COMMUNITY = "community"
    UNVERIFIED = "unverified"
    BLOCKED = "blocked"

@dataclass
class ToolMetadata:
    id: str
    name: str
    description: str
    version: str
    category: ToolCategory
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    platform_requirements: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    source: ExtensionSource = ExtensionSource.BUILT_IN
    trust: TrustLevel = TrustLevel.BUILT_IN
    availability: ToolAvailability = ToolAvailability.ENABLED

class ToolError(Exception):
    """Base error for Tool system failures."""
    pass

class ToolValidationError(ToolError):
    """Raised when tool input validation fails."""
    pass

class ToolExecutionError(ToolError):
    """Raised when tool execution fails."""
    pass

class ToolNotFoundError(ToolError):
    """Raised when a tool is not found in the registry."""
    pass

class ToolUnavailableError(ToolError):
    """Raised when a tool is registered but not available."""
    pass
