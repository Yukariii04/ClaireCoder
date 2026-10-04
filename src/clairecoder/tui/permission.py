"""Permission confirmation surface and presentation model."""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
import re
import textwrap

from .states import TerminalMode
from .activity import DiffInfo, DiffLine
from .canvas import visible_length, visible_slice

class PermissionDecision(str, Enum):
    APPROVE = "approve"
    DENY = "deny"
    ALWAYS_SESSION = "always_session"
    DIFF = "diff"
    CANCEL = "cancel"

def sanitize_display_text(text: str) -> str:
    """Sanitizes sensitive information (passwords, tokens, API keys) for safe display."""
    if not text:
        return text
    # Pattern matching common secret assignments
    patterns = [
        (r'(?i)(bearer)\s+[a-zA-Z0-9_\-\.]{10,}', r'\1 [REDACTED]'),
        (r'(?i)(ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{20,}', r'[REDACTED_TOKEN]'),
        (r'(?i)(sk-[a-zA-Z0-9]{20,})', r'[REDACTED_KEY]'),
        (r'(?i)(password|passwd|pwd|secret|api_key|token|access_token|auth_token)\s*=\s*[\'"]?([^\s\'"]+)[\'"]?', r'\1=***'),
    ]
    sanitized = text
    for pattern, repl in patterns:
        sanitized = re.sub(pattern, repl, sanitized)
    return sanitized


def format_permission_command(tool_id: str, action: str = "", resource: str = "", command: Optional[str] = None) -> str:
    """Formats a concise, safe command string for presentation."""
    if command:
        return sanitize_display_text(command.strip())
    
    clean_tool = tool_id.strip() if tool_id else "tool"
    clean_res = sanitize_display_text(resource.strip() if resource else "")
    clean_action = action.strip() if action else ""
    
    if clean_tool in ("rm", "delete", "remove"):
        return f"rm {clean_res}".strip()
    elif clean_tool in ("write_file", "write") or clean_action == "write":
        return f"write {clean_res}".strip()
    elif clean_tool in ("read_file", "read") or clean_action == "read":
        return f"read {clean_res}".strip()
    elif clean_tool in ("pytest", "test"):
        return f"pytest {clean_res}".strip()
    elif clean_tool in ("terminal", "bash", "sh"):
        return clean_res or clean_action or clean_tool
    elif clean_action and clean_res:
        return f"{clean_tool} {clean_action} {clean_res}".strip()
    elif clean_res:
        return f"{clean_tool} {clean_res}".strip()
    return f"{clean_tool} {clean_action}".strip()

@dataclass
class PermissionRequestViewModel:
    """Presentation-safe view model for a permission confirmation request."""
    request_id: str
    tool_id: str
    action: str = ""
    resource: str = ""
    command: Optional[str] = None
    reason: Optional[str] = None
    category: Optional[str] = None
    session_id: Optional[str] = None
    diff_info: Optional[DiffInfo] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def formatted_command(self) -> str:
        return format_permission_command(self.tool_id, self.action, self.resource, self.command)

class PermissionSurface:
    """Permission confirmation surface conforming to TUI-DESIGN.md."""

    def __init__(self) -> None:
        self.active_request: Optional[PermissionRequestViewModel] = None
        self.pending_requests: List[PermissionRequestViewModel] = []
        self.diff_expanded: bool = False
        self.diff_message: Optional[str] = None
        self.on_decision: Optional[Callable[[str, PermissionDecision, PermissionRequestViewModel], None]] = None

    def request_confirmation(
        self,
        request_id: str,
        tool_id: str,
        action: str = "",
        resource: str = "",
        command: Optional[str] = None,
        reason: Optional[str] = None,
        category: Optional[str] = None,
        session_id: Optional[str] = None,
        diff_info: Optional[DiffInfo] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PermissionRequestViewModel:
        """Add or update a permission confirmation request."""
        req = PermissionRequestViewModel(
            request_id=request_id,
            tool_id=tool_id,
            action=action,
            resource=resource,
            command=command,
            reason=reason,
            category=category,
            session_id=session_id,
            diff_info=diff_info,
            metadata=metadata or {}
        )

        if self.active_request is None:
            self.active_request = req
            self.diff_expanded = False
            self.diff_message = None
        elif self.active_request.request_id == request_id:
            self.active_request = req
        else:
            # Check if already in pending queue
            for i, p in enumerate(self.pending_requests):
                if p.request_id == request_id:
                    self.pending_requests[i] = req
                    return req
            self.pending_requests.append(req)

        return req

    def has_pending(self) -> bool:
        """Returns True if there are any active or pending confirmation requests."""
        return self.active_request is not None or len(self.pending_requests) > 0

    def clear_active(self) -> Optional[PermissionRequestViewModel]:
        """Clears the active request and advances the pending queue."""
        resolved = self.active_request
        if self.pending_requests:
            self.active_request = self.pending_requests.pop(0)
            self.diff_expanded = False
            self.diff_message = None
        else:
            self.active_request = None
            self.diff_expanded = False
    def resolve(self, request_id: str) -> Optional[PermissionRequestViewModel]:
        """Resolves/removes a request by ID and advances the pending queue."""
        if self.active_request and self.active_request.request_id == request_id:
            return self.clear_active()
        for i, p in enumerate(self.pending_requests):
            if p.request_id == request_id:
                return self.pending_requests.pop(i)
        return None

    def register_decision_callback(self, cb: Callable[[str, PermissionDecision], None]) -> None:
        """Registers a decision callback."""
        self._decision_callback = cb

    def approve_active(self) -> Optional[PermissionRequestViewModel]:
        """Approves active request."""
        return self.clear_active()

    def deny_active(self) -> Optional[PermissionRequestViewModel]:
        """Denies active request."""
        return self.clear_active()

    def always_active(self) -> Optional[PermissionRequestViewModel]:
        """Always approves for session."""
        return self.clear_active()

    def cancel_pending(self) -> Optional[PermissionRequestViewModel]:
        """Cancels active and clears pending requests."""
        req = self.clear_active()
        self.pending_requests.clear()
        return req

    def toggle_diff(self) -> None:
        """Toggles the diff/review view for the active request."""
        self.diff_expanded = not self.diff_expanded
        if self.diff_expanded:
            if not self.active_request or not self.active_request.diff_info or not self.active_request.diff_info.lines:
                self.diff_message = "No diff is available for this request."
            else:
                self.diff_message = None

    def handle_key(self, key: str) -> Optional[PermissionDecision]:
        """Handles keyboard input while confirmation owns focus."""
        if not self.active_request:
            return None

        clean_key = key.strip() if isinstance(key, str) else ""

        if clean_key in ("y", "Y"):
            return PermissionDecision.APPROVE
        elif clean_key in ("n", "N"):
            return PermissionDecision.DENY
        elif clean_key in ("a", "A"):
            return PermissionDecision.ALWAYS_SESSION
        elif clean_key in ("d", "D"):
            self.toggle_diff()
            return PermissionDecision.DIFF
        elif clean_key in ("\x1b", "Esc", "esc", "escape", "Escape"):
            return PermissionDecision.CANCEL

        return None

    def render(
        self,
        mode: TerminalMode = TerminalMode.FULL,
        width: int = 80,
        height: Optional[int] = None,
    ) -> List[str]:
        """Renders the confirmation surface based on terminal mode."""
        if not self.active_request:
            return []

        req = self.active_request
        cmd_str = req.formatted_command

        if mode == TerminalMode.MINIMAL:
            lines = self._render_minimal(req, cmd_str)
        elif mode == TerminalMode.COMPACT:
            lines = self._render_compact(req, cmd_str, width)
        else:
            lines = self._render_full(req, cmd_str, width)
        return self._fit_height(lines, height)

    @staticmethod
    def _fit_height(lines: List[str], height: Optional[int]) -> List[str]:
        """Preserve the card's top and bottom borders when details exceed the viewport."""
        if height is None or len(lines) <= height or height <= 0:
            return lines
        if height == 1:
            return ["… permission details"]
        if len(lines) < 2 or height == 2:
            if lines and lines[0].startswith("╭") and lines[-1].startswith("╰"):
                return [lines[0], lines[-1]]
            return lines[:height]

        top = lines[0]
        bottom = lines[-1]
        if not top.startswith("╭") or not bottom.startswith("╰"):
            message = "… permission details shortened"
            return [*lines[: max(0, height - 1)], message]
        card_width = visible_length(top)
        inner_width = max(0, card_width - 4)
        message = visible_slice("… details shortened to fit terminal", 0, inner_width)
        message_line = f"│ {message}{' ' * max(0, inner_width - visible_length(message))} │"
        content_slots = max(0, height - 3)
        return [top, *lines[1 : 1 + content_slots], message_line, bottom][:height]

    def _render_minimal(self, req: PermissionRequestViewModel, cmd_str: str) -> List[str]:
        lines = [
            f"[!] Permission Required: ClaireCoder wants to run: $ {cmd_str}",
            "[y] yes  [n] no  [a] yes, always this sess  [d] diff  (Esc to cancel)"
        ]
        if self.diff_expanded:
            if self.diff_message:
                lines.append(f"  {self.diff_message}")
            elif req.diff_info:
                lines.append("  Diff:")
                for d_line in req.diff_info.lines:
                    prefix = "+" if d_line.type == "add" else ("-" if d_line.type == "remove" else " ")
                    lines.append(f"    {prefix} {d_line.content}")
        return lines

    def _render_compact(self, req: PermissionRequestViewModel, cmd_str: str, width: int) -> List[str]:
        if width < 26:
            return self._render_minimal(req, cmd_str)
        card_w = min(width - 2, 70)
        inner_w = card_w - 4

        def box_line(content: str = "") -> str:
            vis = visible_length(content)
            if vis > inner_w:
                content = visible_slice(content, 0, inner_w)
                vis = visible_length(content)
            pad = max(0, inner_w - vis)
            return f"│ {content}{' ' * pad} │"

        header_title = " Permission Required "
        top_inner = visible_slice(f"─{header_title.strip()} ", 0, card_w - 2)
        top_border = f"╭{top_inner}{'─' * max(0, card_w - 2 - visible_length(top_inner))}╮"
        bot_border = "╰" + ("─" * (card_w - 2)) + "╯"

        lines = [top_border, box_line("ClaireCoder wants to run:")]
        command_rows = textwrap.wrap(
            f"  $ {cmd_str}",
            width=max(1, inner_w),
            subsequent_indent="    ",
            break_long_words=True,
            break_on_hyphens=False,
        ) or ["  $"]
        lines.extend(box_line(row) for row in command_rows)
        lines.append(box_line("[y] yes  [n] no  [a] always  [d] diff  (Esc cancel)"))

        if self.diff_expanded:
            if self.diff_message:
                lines.append(box_line(f"{self.diff_message}"))
            elif req.diff_info:
                lines.append(box_line("Diff:"))
                for d_line in req.diff_info.lines:
                    prefix = "+" if d_line.type == "add" else ("-" if d_line.type == "remove" else " ")
                    lines.append(box_line(f"  {prefix} {d_line.content}"))

        lines.append(bot_border)
        return lines

    def _render_full(self, req: PermissionRequestViewModel, cmd_str: str, width: int) -> List[str]:
        if width < 58:
            return self._render_compact(req, cmd_str, width)
        card_w = min(56, width - 2)
        inner_w = card_w - 4

        def box_line(content: str = "") -> str:
            vis = visible_length(content)
            if vis > inner_w:
                content = visible_slice(content, 0, inner_w)
                vis = visible_length(content)
            pad = max(0, inner_w - vis)
            return f"│ {content}{' ' * pad} │"

        header_title = " Permission Required "
        top_inner = visible_slice(f"─{header_title.strip()} ", 0, card_w - 2)
        top_border = f"╭{top_inner}{'─' * max(0, card_w - 2 - visible_length(top_inner))}╮"
        bot_border = "╰" + ("─" * (card_w - 2)) + "╯"

        lines = [
            top_border,
            box_line(""),
            box_line("ClaireCoder wants to run:"),
        ]
        command_rows = textwrap.wrap(
            f"  $ {cmd_str}",
            width=max(1, inner_w),
            subsequent_indent="    ",
            break_long_words=True,
            break_on_hyphens=False,
        ) or ["  $"]
        lines.extend(box_line(row) for row in command_rows)
        lines.extend([
            box_line(""),
            box_line("╭─────────╮   ╭─────────╮"),
            box_line("│ [y] yes │   │ [n] no  │"),
            box_line("╰─────────╯   ╰─────────╯"),
            box_line("╭───────────────────────────╮   ╭──────────╮"),
            box_line("│ [a] yes, always this sess │   │ [d] diff │"),
            box_line("╰───────────────────────────╯   ╰──────────╯"),
            box_line(""),
            box_line("Claire:"),
        ])

        if req.reason:
            for r_line in req.reason.splitlines():
                wrapped_reason = textwrap.wrap(
                    f"  {r_line}",
                    width=max(1, inner_w),
                    subsequent_indent="    ",
                    break_long_words=True,
                    break_on_hyphens=False,
                ) or ["  "]
                lines.extend(box_line(row) for row in wrapped_reason)
            lines.append(box_line("  Are you sure?"))
        else:
            lines.append(box_line("  Are you sure you want to proceed with this"))
            lines.append(box_line("  operation?"))

        lines.append(box_line(""))
        lines.append(box_line("             (Esc to cancel)"))

        if self.diff_expanded:
            lines.append(box_line(""))
            lines.append(box_line("─" * inner_w))
            if self.diff_message:
                lines.append(box_line(f"  {self.diff_message}"))
            elif req.diff_info:
                lines.append(box_line(f"  Diff ({req.diff_info.summary or 'changes'}):"))
                for d_line in req.diff_info.lines:
                    prefix = "+" if d_line.type == "add" else ("-" if d_line.type == "remove" else " ")
                    lines.append(box_line(f"    {prefix} {d_line.content}"))

        lines.append(bot_border)
        return lines
