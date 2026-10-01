"""Canonical provider-neutral agent message representation.

Per §11 — Model/tool history must not exist only as a temporary local list.
Per §12 — Provider-specific transforms remain in adapters.

This module provides the canonical AgentMessage that all providers
transform to/from, and the ToolCallAccumulator for streaming.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json


@dataclass
class AgentMessage:
    """Provider-neutral representation of a conversation message.

    Preserves:
      - user messages
      - assistant text
      - assistant tool calls
      - tool results
      - permission results
      - verification results
    """
    role: str  # "user", "assistant", "tool", "system"
    content: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a provider-neutral dict."""
        d: Dict[str, Any] = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.name is not None:
            d["name"] = self.name
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Deserialize from a provider-neutral dict."""
        return cls(
            role=data["role"],
            content=data.get("content"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
            name=data.get("name"),
            metadata=data.get("metadata", {}),
        )


class ToolCallAccumulator:
    """Accumulates streaming tool-call fragments into complete calls.

    Per §13 — Streaming tool-call fragments must be accumulated before
    becoming a complete normalized tool call.

    Handles:
      - Fragmented arguments across multiple chunks
      - Multiple tool calls in one stream
      - Text + tool call in same stream
      - Malformed fragments
    """

    def __init__(self):
        self._calls: Dict[int, Dict[str, Any]] = {}
        self._text_parts: List[str] = []

    def add_delta(self, delta: Dict[str, Any]) -> None:
        """Process a streaming delta chunk."""
        # Accumulate text content
        text = delta.get("content")
        if text:
            self._text_parts.append(text)

        # Accumulate tool calls
        tool_calls = delta.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                idx = tc.get("index", 0)
                if idx not in self._calls:
                    self._calls[idx] = {
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": "",
                            "arguments": "",
                        },
                    }
                existing = self._calls[idx]
                if tc.get("id"):
                    existing["id"] = tc["id"]
                if tc.get("type"):
                    existing["type"] = tc["type"]
                fn = tc.get("function", {})
                if fn.get("name"):
                    existing["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    existing["function"]["arguments"] += fn["arguments"]

    def get_text(self) -> Optional[str]:
        """Get accumulated text content, or None if empty."""
        return "".join(self._text_parts) if self._text_parts else None

    def get_tool_calls(self) -> Optional[List[Dict[str, Any]]]:
        """Get finalized tool calls, or None if none accumulated."""
        if not self._calls:
            return None
        return [self._calls[idx] for idx in sorted(self._calls.keys())]

    def has_tool_calls(self) -> bool:
        """Check if any tool calls have been accumulated."""
        return bool(self._calls)

    def finalize(self) -> Dict[str, Any]:
        """Return accumulated text and tool calls."""
        return {
            "text": self.get_text(),
            "tool_calls": self.get_tool_calls(),
        }

    def reset(self) -> None:
        """Clear accumulated state."""
        self._calls.clear()
        self._text_parts.clear()


@dataclass
class PendingToolInvocation:
    """Stores the exact pending tool invocation for permission resume.

    Per §4 — The pending invocation must retain all context needed
    to execute the exact original Tool invocation upon approval.
    """
    request_id: str
    tool_id: str
    kwargs: Dict[str, Any]
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    tool_call_id: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    category: Optional[str] = None


@dataclass(frozen=True)
class ModePolicy:
    """Mode-specific execution policy.

    Per §16 — Mode policy must affect actual Tool execution.
    Enforcement point is ToolExecutor / permission boundary.
    """
    allow_file_read: bool = True
    allow_file_modification: bool = True
    allow_tool_execution: bool = True
    allow_network: bool = True
    allow_repository_modification: bool = True

    @classmethod
    def for_mode(cls, mode: str) -> "ModePolicy":
        """Create a ModePolicy from mode name."""
        mode = mode.lower()
        if mode == "plan":
            return cls(
                allow_file_read=True,
                allow_file_modification=False,
                allow_tool_execution=False,
                allow_network=False,
                allow_repository_modification=False,
            )
        elif mode == "review":
            return cls(
                allow_file_read=True,
                allow_file_modification=False,
                allow_tool_execution=True,  # read-only execution like tests
                allow_network=False,
                allow_repository_modification=False,
            )
        elif mode == "implement":
            return cls(
                allow_file_read=True,
                allow_file_modification=True,
                allow_tool_execution=True,
                allow_network=True,
                allow_repository_modification=True,
            )
        elif mode == "debug":
            return cls(
                allow_file_read=True,
                allow_file_modification=True,
                allow_tool_execution=True,
                allow_network=True,
                allow_repository_modification=True,
            )
        else:
            # Default: implement-like
            return cls()


@dataclass
class AgentBudget:
    """Unified execution budget.

    Per §18 — One coherent runtime budget preventing nested loop multiplication.
    """
    max_turns: int = 20
    max_tool_calls: int = 40
    max_retries: int = 3
    max_replans: int = 2
    timeout_seconds: int = 600

    # Consumption tracking
    turns_used: int = 0
    tool_calls_used: int = 0
    retries_used: int = 0
    replans_used: int = 0

    def can_turn(self) -> bool:
        return self.turns_used < self.max_turns

    def can_tool_call(self) -> bool:
        return self.tool_calls_used < self.max_tool_calls

    def can_retry(self) -> bool:
        return self.retries_used < self.max_retries

    def can_replan(self) -> bool:
        return self.replans_used < self.max_replans

    def use_turn(self) -> None:
        self.turns_used += 1

    def use_tool_call(self) -> None:
        self.tool_calls_used += 1

    def use_retry(self) -> None:
        self.retries_used += 1

    def use_replan(self) -> None:
        self.replans_used += 1

    def exceeded_reason(self) -> Optional[str]:
        """Return the reason if any budget is exceeded, else None."""
        if self.turns_used >= self.max_turns:
            return f"turn budget exceeded ({self.turns_used}/{self.max_turns})"
        if self.tool_calls_used >= self.max_tool_calls:
            return f"tool-call budget exceeded ({self.tool_calls_used}/{self.max_tool_calls})"
        if self.retries_used >= self.max_retries:
            return f"retry budget exhausted ({self.retries_used}/{self.max_retries})"
        if self.replans_used >= self.max_replans:
            return f"replan budget exhausted ({self.replans_used}/{self.max_replans})"
        return None


@dataclass
class NormalizedToolResult:
    """Bounded, normalized tool result for model context.

    Per §23 — Tool outputs must be bounded before entering model context.
    """
    state: str
    summary: str
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    truncated: bool = False
    original_size: int = 0

    MAX_CONTENT_SIZE = 8000  # Characters before truncation

    @classmethod
    def from_tool_result(cls, result: Any, tool_id: str = "") -> "NormalizedToolResult":
        """Create a normalized result from a ToolResult."""
        from clairecoder.core.types import ToolResult as TR

        state_str = result.state.value if hasattr(result.state, "value") else str(result.state)
        output_str = str(result.output) if result.output else ""
        error_str = str(result.error) if result.error else ""
        original_size = len(output_str)

        # Build summary
        if result.error:
            summary = f"[{state_str}] {error_str[:200]}"
        elif output_str:
            summary = f"[{state_str}] {output_str[:200]}"
        else:
            summary = f"[{state_str}]"

        # Truncate content if needed
        content = output_str or error_str
        truncated = len(content) > cls.MAX_CONTENT_SIZE
        if truncated:
            content = content[:cls.MAX_CONTENT_SIZE] + "\n... (truncated)"

        return cls(
            state=state_str,
            summary=summary,
            content=content if content else None,
            metadata=dict(result.metadata) if result.metadata else {},
            truncated=truncated,
            original_size=original_size,
        )


def action_signature(tool_id: str, kwargs: dict) -> str:
    """Create a normalized signature for loop detection.

    Per §19 — Prevent repeated unsuccessful actions.
    """
    return json.dumps(
        {"tool": tool_id, "arguments": kwargs},
        sort_keys=True,
        default=str,
    )


@dataclass
class CapabilityState:
    """Model capability verification state.

    Per §14 — unknown != supported.
    """
    name: str
    status: str = "unknown"  # "advertised", "validated", "supported", "unsupported", "unknown"
    reason: Optional[str] = None

    @property
    def is_supported(self) -> bool:
        return self.status in ("validated", "supported")

    @property
    def is_unknown(self) -> bool:
        return self.status == "unknown"


def model_key(provider_id: str, model_id: str) -> str:
    """Create unambiguous provider+model identity.

    Per §15 — Two providers may expose the same model ID.
    """
    return f"{provider_id}/{model_id}"
