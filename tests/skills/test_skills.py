"""Phase 5 — Skill System test suite.

Tests cover:
- Skill abstraction (metadata, instructions, validation) (AC-016)
- Skill Registration and Discovery (AC-006, AC-019)
- Skill Enable/Disable Lifecycle (AC-013, AC-021)
- Skill Dependencies (AC-017)
- Skill Versioning (AC-018)
- Skill Source and Trust distinguishing (AC-020)
- Skill Architecture boundary (No alternate Tool execution path) (AC-023)
"""
import pytest
from clairecoder.skills.types import (
    SkillCategory, SkillAvailability, SkillMetadata,
    SkillValidationError, SkillNotFoundError, SkillUnavailableError,
    SkillDependencyError
)
from clairecoder.skills.base import Skill
from clairecoder.skills.registry import SkillRegistry
from clairecoder.tools.types import ExtensionSource, TrustLevel

# A mock Skill implementation for testing
class MockSkill(Skill):
    def __init__(self, metadata: SkillMetadata, instructions: str):
        self._metadata = metadata
        self._instructions = instructions

    @property
    def metadata(self) -> SkillMetadata:
        return self._metadata

    @property
    def instructions(self) -> str:
        return self._instructions


def test_skill_metadata_and_abstraction():
    """AC-016: Skills expose sufficient metadata."""
    meta = SkillMetadata(
        id="test.skill",
        name="Test Skill",
        description="A test skill",
        version="1.0.0",
        category=SkillCategory.ENGINEERING,
        source=ExtensionSource.LOCAL,
        trust=TrustLevel.UNVERIFIED
    )
    skill = MockSkill(meta, "Do things right.")
    
    assert skill.metadata.id == "test.skill"
    assert skill.metadata.version == "1.0.0"
    assert skill.instructions == "Do things right."
    assert skill.metadata.source == ExtensionSource.LOCAL

def test_skill_validation_missing_metadata():
    """Validation fails if required metadata is missing."""
    meta = SkillMetadata(
        id="",  # Missing ID
        name="Test",
        description="Desc",
        version="1.0",
        category=SkillCategory.ENGINEERING
    )
    skill = MockSkill(meta, "Instructions")
    with pytest.raises(SkillValidationError):
        skill.validate()

def test_skill_validation_missing_instructions():
    """Validation fails if instructions are missing."""
    meta = SkillMetadata(
        id="valid.id",
        name="Test",
        description="Desc",
        version="1.0",
        category=SkillCategory.ENGINEERING
    )
    skill = MockSkill(meta, "")  # Missing instructions
    with pytest.raises(SkillValidationError):
        skill.validate()

def test_skill_registration():
    """AC-006, AC-019: Skill registration and registry enumeration."""
    registry = SkillRegistry()
    meta = SkillMetadata(
        id="test.skill",
        name="Test Skill",
        description="Desc",
        version="1.0.0",
        category=SkillCategory.ENGINEERING
    )
    skill = MockSkill(meta, "Instructions")
    
    registry.register(skill)
    assert registry.is_registered("test.skill")
    assert len(registry.list_skills()) == 1

def test_skill_unregister():
    """AC-021: Users can remove installed skills."""
    registry = SkillRegistry()
    meta = SkillMetadata(
        id="test.skill",
        name="Test Skill",
        description="Desc",
        version="1.0.0",
        category=SkillCategory.ENGINEERING
    )
    skill = MockSkill(meta, "Instructions")
    
    registry.register(skill)
    registry.unregister("test.skill")
    assert not registry.is_registered("test.skill")

def test_skill_enable_disable_lifecycle():
    """AC-013: Installed Skills can be enabled and disabled."""
    registry = SkillRegistry()
    meta = SkillMetadata(
        id="test.skill",
        name="Test Skill",
        description="Desc",
        version="1.0.0",
        category=SkillCategory.ENGINEERING
    )
    skill = MockSkill(meta, "Instructions")
    registry.register(skill)
    
    # Enable
    registry.enable("test.skill")
    enabled_skill = registry.get_enabled("test.skill")
    assert enabled_skill.metadata.id == "test.skill"
    
    # Disable
    registry.disable("test.skill")
    
    # Try to retrieve enabled -> fails
    with pytest.raises(SkillUnavailableError):
        registry.get_enabled("test.skill")

def test_skill_not_found():
    registry = SkillRegistry()
    with pytest.raises(SkillNotFoundError):
        registry.get("missing.skill")

def test_skill_architectural_boundary():
    """AC-023: Skill implementations remain outside the Engineering Engine.
    Also ensures Skills do not possess public Tool execution methods.
    """
    meta = SkillMetadata(
        id="test.skill",
        name="Test Skill",
        description="Desc",
        version="1.0.0",
        category=SkillCategory.ENGINEERING
    )
    skill = MockSkill(meta, "Instructions")
    
    # A skill is declarative, not executable. It has no execute method.
    assert not hasattr(skill, "execute")
    assert not hasattr(skill, "_execute")
    assert not hasattr(skill, "engineering_engine")
    
def test_skill_dependencies():
    """AC-017: Required Skill dependencies can be detected."""
    meta = SkillMetadata(
        id="test.skill",
        name="Test Skill",
        description="Desc",
        version="1.0.0",
        category=SkillCategory.ENGINEERING,
        required_tools=["filesystem.read", "filesystem.write"]
    )
    skill = MockSkill(meta, "Instructions")
    
    assert "filesystem.read" in skill.metadata.required_tools
    assert "filesystem.write" in skill.metadata.required_tools

def test_skill_trust_distinction():
    """AC-020: External extensions are distinguishable from built-in extensions."""
    built_in_meta = SkillMetadata(
        id="builtin.skill", name="B", description="D", version="1", category=SkillCategory.ENGINEERING,
        source=ExtensionSource.BUILT_IN, trust=TrustLevel.BUILT_IN
    )
    third_party_meta = SkillMetadata(
        id="thirdparty.skill", name="T", description="D", version="1", category=SkillCategory.ENGINEERING,
        source=ExtensionSource.GITHUB, trust=TrustLevel.UNVERIFIED
    )
    
    s1 = MockSkill(built_in_meta, "Inst")
    s2 = MockSkill(third_party_meta, "Inst")
    
    assert s1.metadata.trust == TrustLevel.BUILT_IN
    assert s2.metadata.trust == TrustLevel.UNVERIFIED

def test_skill_missing_skill_dependency_prevents_activation():
    """AC-017: Missing Skill dependency prevents activation."""
    registry = SkillRegistry()
    meta = SkillMetadata(
        id="test.skill", name="Test", description="Desc", version="1.0", category=SkillCategory.ENGINEERING,
        dependencies=["missing.skill"]
    )
    skill = MockSkill(meta, "Inst")
    registry.register(skill)
    
    with pytest.raises(SkillDependencyError):
        registry.enable("test.skill")

def test_skill_missing_tool_dependency_prevents_activation():
    """AC-017: Missing Tool dependency prevents activation."""
    class DummyToolRegistry:
        def is_registered(self, tool_id: str) -> bool:
            return False

    registry = SkillRegistry()
    meta = SkillMetadata(
        id="test.skill", name="Test", description="Desc", version="1.0", category=SkillCategory.ENGINEERING,
        required_tools=["missing.tool"]
    )
    skill = MockSkill(meta, "Inst")
    registry.register(skill)
    
    tool_registry = DummyToolRegistry()
    with pytest.raises(SkillDependencyError):
        registry.enable("test.skill", tool_registry=tool_registry)

def test_skill_tool_dependency_cannot_be_checked():
    """AC-017: If Tool registry is not provided and tools are required, activation fails."""
    registry = SkillRegistry()
    meta = SkillMetadata(
        id="test.skill", name="Test", description="Desc", version="1.0", category=SkillCategory.ENGINEERING,
        required_tools=["some.tool"]
    )
    skill = MockSkill(meta, "Inst")
    registry.register(skill)
    
    with pytest.raises(SkillDependencyError, match="no ToolRegistry was provided"):
        registry.enable("test.skill")

def test_skill_dependencies_met_allows_activation():
    """AC-017: All dependencies met allows activation."""
    class DummyToolRegistry:
        def is_registered(self, tool_id: str) -> bool:
            return True

    registry = SkillRegistry()
    
    # Register and enable the dependency skill
    dep_meta = SkillMetadata(
        id="dep.skill", name="Dep", description="Desc", version="1.0", category=SkillCategory.ENGINEERING
    )
    registry.register(MockSkill(dep_meta, "Inst"))
    registry.enable("dep.skill")
    
    # Register the main skill
    meta = SkillMetadata(
        id="test.skill", name="Test", description="Desc", version="1.0", category=SkillCategory.ENGINEERING,
        dependencies=["dep.skill"],
        required_tools=["existing.tool"]
    )
    registry.register(MockSkill(meta, "Inst"))
    
    tool_registry = DummyToolRegistry()
    # Should succeed without raising SkillDependencyError
    registry.enable("test.skill", tool_registry=tool_registry)
    
    assert registry.get_enabled("test.skill").metadata.id == "test.skill"
