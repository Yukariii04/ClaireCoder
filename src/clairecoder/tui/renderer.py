"""Renders activity models into displayable lines conforming to TUI-DESIGN.md visual language."""
from typing import List, Optional
from .activity import ActivityModel, ActivityState, ActivityType

class ActivityRenderer:
    """Renders activities with consistent markers and rhythm matching the locked design."""

    @staticmethod
    def render(activity: ActivityModel, width: int = 68, use_color: bool = False) -> List[str]:
        # Check for Claire assistant message (text persona)
        if activity.type == ActivityType.MESSAGE and activity.title.lower() in ("claire", "assistant", "clairecoder"):
            return ActivityRenderer._render_claire_message(activity, width=width, use_color=use_color)

        # Standard agent activity
        marker = "> ◌"
        if activity.state == ActivityState.COMPLETED:
            if activity.type in (ActivityType.EDITING, ActivityType.TEST, ActivityType.TOOL):
                marker = "> ●"
            else:
                marker = "> ✓"
        elif activity.state == ActivityState.RUNNING:
            marker = "> ●"
        elif activity.state == ActivityState.FAILED:
            marker = "> ✗"
        elif activity.state in (ActivityState.APPROVAL_REQUIRED, ActivityState.BLOCKED):
            marker = "> ⚠"

        title_text = activity.title
        # If title doesn't start with marker, prepend it
        if not title_text.startswith(">"):
            header_line = f"{marker} {title_text}"
        else:
            header_line = title_text

        lines = [header_line]

        # Expandable content (e.g. inline diff)
        if activity.expanded and activity.expandable_content:
            for exp_line in activity.expandable_content.splitlines():
                lines.append(f"  {exp_line}")
        elif activity.detail:
            for detail_line in activity.detail.splitlines():
                lines.append(f"  {detail_line}")

        if activity.expanded and activity.diff_info:
            for d_line in activity.diff_info.lines:
                prefix = "+" if d_line.type == "add" else ("-" if d_line.type == "remove" else " ")
                lines.append(f"  {prefix} {d_line.content}")

        return lines

    @staticmethod
    def _render_claire_message(activity: ActivityModel, width: int = 68, use_color: bool = False) -> List[str]:
        """Renders the Claire message text persona matching TUI-DESIGN.md Section 4 & 9."""
        header_text = "Claire:"
        lines: List[str] = [header_text]

        msg_lines = activity.detail.splitlines() if activity.detail else []
        if not msg_lines:
            msg_lines = [
                "Streaming decode support added with a safe fallback.",
                "All tests are passing.",
                "What would you like to work on next?"
            ]

        for line in msg_lines:
            lines.append(f"  {line}")

        return lines
