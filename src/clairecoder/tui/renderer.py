"""Renders activity models into displayable lines conforming to TUI-DESIGN.md visual language."""
from typing import List, Optional
from .activity import ActivityModel, ActivityState, ActivityType


def _wrap_text(text: str, width: int, indent: str = "  ") -> List[str]:
    """Wrap a single logical line into multiple display rows respecting terminal width.

    Uses word-boundary wrapping.  Falls back to character wrapping for words
    exceeding width.  Never hard-truncates semantic content.
    """
    if width <= 0:
        width = 80
    avail = max(10, width - len(indent))
    result: List[str] = []

    for line in text.splitlines():
        if not line.strip():
            result.append("")
            continue
        words = line.split(" ")
        cur = indent
        for w in words:
            if not w:
                continue
            test = f"{cur} {w}" if cur != indent else f"{cur}{w}"
            if len(test) <= width:
                cur = test
            else:
                if cur.strip():
                    result.append(cur)
                # Handle single word longer than avail: character-wrap
                if len(indent + w) > width:
                    while w:
                        chunk = w[:avail]
                        w = w[avail:]
                        result.append(f"{indent}{chunk}")
                    cur = indent
                else:
                    cur = f"{indent}{w}"
        if cur.strip():
            result.append(cur)
    return result if result else [""]


class ActivityRenderer:
    """Renders activities with consistent markers and rhythm matching the locked design."""

    @staticmethod
    def render(activity: ActivityModel, width: int = 68, use_color: bool = False) -> List[str]:
        # Check for Claire assistant message (text persona)
        if activity.type == ActivityType.MESSAGE and activity.title.lower() in ("claire", "assistant", "clairecoder"):
            return ActivityRenderer._render_claire_message(activity, width=width, use_color=use_color)
        elif activity.type == ActivityType.MESSAGE and activity.title.lower() in ("user", "human"):
            detail_lines = activity.detail.splitlines() if activity.detail else [""]
            lines = [f"> {detail_lines[0]}"]
            for l in detail_lines[1:]:
                lines.append(f"  {l}")
            # Wrap long user lines
            wrapped: List[str] = []
            for ln in lines:
                if len(ln) > width and width > 10:
                    wrapped.extend(_wrap_text(ln, width, indent="  "))
                else:
                    wrapped.append(ln)
            return wrapped

        # Direct ActivityEvent rendering (Correction #20)
        if getattr(activity, "activity_event", None) is not None:
            raw_lines = activity.activity_event.render_lines(
                width=width,
                include_diff=activity.expanded,
            )
            wrapped: List[str] = []
            for ln in raw_lines:
                if len(ln) > width and width > 10:
                    wrapped.extend(_wrap_text(ln, width, indent="  "))
                else:
                    wrapped.append(ln)
            return wrapped

        # Direct ChangeSummary rendering (Correction #20)
        if getattr(activity, "change_summary", None) is not None:
            raw_lines = activity.change_summary.format_summary(width=width)
            wrapped: List[str] = []
            for ln in raw_lines:
                if len(ln) > width and width > 10:
                    wrapped.extend(_wrap_text(ln, width, indent="  "))
                else:
                    wrapped.append(ln)
            return wrapped

        # Check if title already begins with modern activity marker (●, ✓, ✗)
        title_text = activity.title
        if title_text.startswith(("●", "✓", "✗")):
            lines = [title_text]
            if activity.detail:
                for dl in activity.detail.splitlines():
                    if dl.strip():
                        lines.append(f"  {dl.strip()}")
            wrapped = []
            for ln in lines:
                if len(ln) > width and width > 10:
                    wrapped.extend(_wrap_text(ln, width, indent="  "))
                else:
                    wrapped.append(ln)
            return wrapped

        # Standard agent activity
        marker = "◌"
        if activity.state == ActivityState.COMPLETED:
            if activity.type in (ActivityType.EDITING, ActivityType.TEST, ActivityType.TOOL):
                marker = "●"
            else:
                marker = "✓"
        elif activity.state == ActivityState.RUNNING:
            marker = "●"
        elif activity.state == ActivityState.FAILED:
            marker = "✗"
        elif activity.state in (ActivityState.APPROVAL_REQUIRED, ActivityState.BLOCKED):
            marker = "⚠"

        # If title doesn't start with marker, prepend it
        if not title_text.startswith((">", "●", "✓", "✗", "◌", "⚠")):
            header_line = f"{marker} {title_text}"
        else:
            header_line = title_text

        lines = [header_line]

        # Expandable content (e.g. tool output) stays out of the feed until asked for.
        if activity.expanded and activity.expandable_content:
            for exp_line in activity.expandable_content.splitlines():
                lines.append(f"  {exp_line}")
        elif activity.detail:
            detail_lines = activity.detail.splitlines()
            detail_chars = sum(len(line) for line in detail_lines)
            if not activity.expanded and (len(detail_lines) > 4 or detail_chars > 320):
                preview = detail_lines[:2]
                if len(preview) == 1 and len(preview[0]) > 240:
                    preview[0] = preview[0][:237] + "..."
                for detail_line in preview:
                    lines.append(f"  {detail_line}")
                hidden_lines = max(0, len(detail_lines) - len(preview))
                suffix = f"{hidden_lines} more lines" if hidden_lines else "more output"
                lines.append(f"  … {suffix} · Ctrl+O to expand")
            else:
                for detail_line in detail_lines:
                    lines.append(f"  {detail_line}")

        if not activity.expanded and activity.expandable_content:
            if not activity.detail:
                lines.append("  Output hidden · Ctrl+O to expand")
            elif len(activity.detail.splitlines()) <= 4 and len(activity.detail) <= 320:
                lines.append("  More output · Ctrl+O to expand")

        if activity.expanded and activity.diff_info:
            inner_w = max(30, width - 6)
            lines.append(f"  ┌{'─' * inner_w}┐")
            for d_line in activity.diff_info.lines[:12]:
                prefix = "+" if d_line.type == "add" else ("-" if d_line.type == "remove" else " ")
                content = f"{prefix} {d_line.content}"
                if len(content) > inner_w:
                    content = content[:inner_w - 1] + "…"
                pad = max(0, inner_w - len(content))
                lines.append(f"  │{content}{' ' * pad}│")
            lines.append(f"  └{'─' * inner_w}┘")
            if len(activity.diff_info.lines) > 12:
                lines.append("  …")

        # Wrap any line that exceeds terminal width
        wrapped: List[str] = []
        for ln in lines:
            if len(ln) > width and width > 10:
                wrapped.extend(_wrap_text(ln, width, indent="  "))
            else:
                wrapped.append(ln)
        return wrapped

    @staticmethod
    def _render_claire_message(activity: ActivityModel, width: int = 68, use_color: bool = False) -> List[str]:
        """Renders the Claire message text persona matching TUI-DESIGN.md Section 4 & 9."""
        header_text = "Claire:"
        lines: List[str] = [header_text]

        msg_lines = activity.detail.splitlines() if activity.detail else []
        if not msg_lines:
            return lines  # No content — don't fabricate placeholder text

        for line in msg_lines:
            raw = f"  {line}"
            if len(raw) > width and width > 10:
                lines.extend(_wrap_text(line, width, indent="  "))
            else:
                lines.append(raw)

        return lines

