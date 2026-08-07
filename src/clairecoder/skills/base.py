from abc import ABC, abstractmethod
from typing import List
from .types import SkillMetadata, SkillValidationError

class Skill(ABC):
    """Base class for all ClaireCoder skills.
    
    A Skill is reusable engineering expertise. It provides instructions,
    methodology, and references. It influences agent behavior but is NOT
    an executable operation itself.
    
    Skills MUST NOT orchestrate tools by bypassing the PermissionEngine.
    Skill declares expertise, instructions, references, examples, and
    requirements.
    Skill does not execute Tools.
    Higher-level orchestration is responsible for using ToolExecutor.
    
    Architectural Guarantee (CC-PRD-003 Section 17, CC-ADR-003 Section 7):
    Skills provide context and instructions; they do not contain an
    alternate execution path for capabilities.
    """

    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """Return the skill's metadata including id, name, required_tools, etc."""
        pass

    @property
    @abstractmethod
    def instructions(self) -> str:
        """The core engineering expertise/instructions provided by this skill."""
        pass

    @property
    def references(self) -> List[str]:
        """Optional supporting references or URIs."""
        return []

    @property
    def examples(self) -> List[str]:
        """Optional examples of the methodology applied."""
        return []

    def validate(self) -> None:
        """Validate the skill's structure and metadata.
        
        Raises SkillValidationError if invalid.
        """
        if not self.metadata.id or not self.metadata.name:
            raise SkillValidationError("Skill must have an id and name.")
        if not self.instructions:
            raise SkillValidationError("Skill must provide instructions.")
