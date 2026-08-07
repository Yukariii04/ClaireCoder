from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from clairecoder.tools.types import ExtensionSource, TrustLevel

class SkillCategory(str, Enum):
    ENGINEERING = "engineering"
    UI_UX = "ui_ux"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ANTI_SLOP = "anti_slop"
    PROJECT_SPECIFIC = "project_specific"
    COLLECTION = "collection"

class SkillAvailability(str, Enum):
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    INCOMPATIBLE = "incompatible"
    REMOVED = "removed"

@dataclass
class SkillMetadata:
    id: str
    name: str
    description: str
    version: str
    category: SkillCategory
    tags: List[str] = field(default_factory=list)
    author: Optional[str] = None
    license: Optional[str] = None
    source: ExtensionSource = ExtensionSource.BUILT_IN
    trust: TrustLevel = TrustLevel.BUILT_IN
    required_tools: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

class SkillError(Exception):
    """Base error for Skill system failures."""
    pass

class SkillValidationError(SkillError):
    """Raised when skill validation fails."""
    pass

class SkillNotFoundError(SkillError):
    """Raised when a skill is not found in the registry."""
    pass

class SkillUnavailableError(SkillError):
    """Raised when a skill is registered but not available/enabled."""
    pass

class SkillDependencyError(SkillError):
    """Raised when a skill's required dependencies are not met."""
    pass
