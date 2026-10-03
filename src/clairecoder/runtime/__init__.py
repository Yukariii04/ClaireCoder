"""ClaireCoder Runtime Event Protocol.

Correction #12: Structured runtime event stream for real-time
activity reporting, trajectory recording, and debugging.

Correction #18: Agent Roles / Subagent architecture.
"""

from .events import RuntimeEvent, EventType
from .emitter import EventEmitter
from .bridge import EngineBridge
from .tui_listener import RuntimeEventTuiListener
from .agent_runtime import AgentRuntime, RunResult
from .roles import (
    Role,
    RoleContext,
    RoleResult,
    AgentRole,
    PlannerRole,
    ImplementerRole,
    VerifierRole,
    RecoveryRole,
    RecoveryDecision,
    RoleRegistry,
)

__all__ = [
    "RuntimeEvent",
    "EventType",
    "EventEmitter",
    "EngineBridge",
    "RuntimeEventTuiListener",
    "AgentRuntime",
    "RunResult",
    "Role",
    "RoleContext",
    "RoleResult",
    "AgentRole",
    "PlannerRole",
    "ImplementerRole",
    "VerifierRole",
    "RecoveryRole",
    "RecoveryDecision",
    "RoleRegistry",
]
