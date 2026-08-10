from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

class InteractionMode(str, Enum):
    """Operational modes for ClaireCoder as defined in CC-PRD-005 §16.

    V1 Modes:
        PLAN      — Focuses on understanding the objective and producing a plan.
        IMPLEMENT — Focuses on executing the approved engineering work.
        REVIEW    — Focuses on examining implementation quality and correctness.
        DEBUG     — Focuses on diagnosing and resolving failures.
    """
    PLAN = "plan"
    IMPLEMENT = "implement"
    REVIEW = "review"
    DEBUG = "debug"

class CommandCategory(str, Enum):
    """Command categories per CC-PRD-005 §10 and CC-ADR-005 §8."""
    AGENT = "agent"
    SESSION = "session"
    MODEL = "model"
    MODE = "mode"
    SKILL = "skill"
    TOOL = "tool"
    SYSTEM = "system"
    EXECUTION = "execution"
    WORKFLOW = "workflow"
    TASK = "task"

@dataclass
class CommandArgument:
    name: str
    description: str
    required: bool = False
    default: Any = None

@dataclass
class CommandDefinition:
    name: str
    description: str
    category: CommandCategory
    arguments: List[CommandArgument] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)

@dataclass
class CommandRequest:
    command: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    raw_input: str = ""

@dataclass
class CommandResponse:
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
