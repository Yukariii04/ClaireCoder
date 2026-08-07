from typing import Any, Dict, List, Optional
from .base import Skill
from .types import (
    SkillMetadata, SkillCategory, SkillAvailability,
    SkillNotFoundError, SkillUnavailableError
)

class SkillRegistry:
    """Registry for discovering and managing available Skills.
    
    Registration provides discovery but does NOT imply execution authority
    for the tools a Skill might require. Authorization remains strictly
    governed by the PermissionEngine.
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._availability: Dict[str, SkillAvailability] = {}

    def register(self, skill: Skill) -> None:
        """Register a skill. 
        
        This makes the skill discoverable but does not automatically
        enable it or grant it any Tool permissions.
        """
        skill.validate()
        self._skills[skill.metadata.id] = skill
        if skill.metadata.id not in self._availability:
            self._availability[skill.metadata.id] = SkillAvailability.INSTALLED

    def unregister(self, skill_id: str) -> None:
        """Remove a skill from the registry."""
        if skill_id in self._skills:
            del self._skills[skill_id]
        if skill_id in self._availability:
            del self._availability[skill_id]

    def get(self, skill_id: str) -> Skill:
        """Retrieve a registered skill by ID.
        
        Raises SkillNotFoundError if not registered.
        """
        if skill_id not in self._skills:
            raise SkillNotFoundError(f"Skill not found: {skill_id}")
        return self._skills[skill_id]

    def get_enabled(self, skill_id: str) -> Skill:
        """Retrieve a skill and ensure it is currently enabled.
        
        Raises SkillNotFoundError if not registered.
        Raises SkillUnavailableError if not enabled.
        """
        skill = self.get(skill_id)
        if self._availability[skill_id] != SkillAvailability.ENABLED:
            raise SkillUnavailableError(
                f"Skill '{skill_id}' is {self._availability[skill_id].value}"
            )
        return skill

    def enable(self, skill_id: str, tool_registry: Optional[Any] = None) -> None:
        """Enable a registered skill.
        
        Detects missing skill and tool dependencies before activation.
        A missing required dependency will raise SkillDependencyError
        and prevent activation.
        """
        from .types import SkillDependencyError
        
        skill = self.get(skill_id)
        
        # Check skill dependencies
        for dep_id in skill.metadata.dependencies:
            if dep_id not in self._skills:
                raise SkillDependencyError(f"Missing required skill dependency: {dep_id}")
            if self._availability[dep_id] != SkillAvailability.ENABLED:
                raise SkillDependencyError(f"Required skill dependency '{dep_id}' is not enabled.")
        
        # Check tool dependencies
        if skill.metadata.required_tools:
            if tool_registry is None:
                raise SkillDependencyError(
                    f"Skill '{skill_id}' requires tools, but no ToolRegistry "
                    "was provided to validate them."
                )
            for tool_id in skill.metadata.required_tools:
                if not tool_registry.is_registered(tool_id):
                    raise SkillDependencyError(f"Missing required tool dependency: {tool_id}")
        
        self._availability[skill_id] = SkillAvailability.ENABLED

    def disable(self, skill_id: str) -> None:
        """Disable a registered skill."""
        # Ensure it exists
        self.get(skill_id)
        self._availability[skill_id] = SkillAvailability.DISABLED

    def list_skills(self, category: Optional[SkillCategory] = None) -> List[Skill]:
        """List all registered skills, optionally filtered by category."""
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.metadata.category == category]
        return skills

    def list_enabled(self) -> List[Skill]:
        """List only skills that are currently enabled."""
        return [
            s for s_id, s in self._skills.items()
            if self._availability[s_id] == SkillAvailability.ENABLED
        ]

    def is_registered(self, skill_id: str) -> bool:
        """Check if a skill is registered."""
        return skill_id in self._skills
