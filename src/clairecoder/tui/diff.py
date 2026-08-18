"""Diff presentation foundation and renderer for the TUI."""
from dataclasses import dataclass, field
from typing import List, Optional
from .states import TerminalMode
from .activity import DiffLine, DiffInfo

@dataclass
class FileDiff:
    """Represents changes in a single file for presentation."""
    file_path: str
    additions: int = 0
    deletions: int = 0
    is_new: bool = False
    is_deleted: bool = False
    lines: List[DiffLine] = field(default_factory=list)
    summary: str = ""

    @property
    def formatted_summary(self) -> str:
        tag = " (new)" if self.is_new else (" (deleted)" if self.is_deleted else "")
        return f"{self.file_path:<28} +{self.additions} -{self.deletions}{tag}"

class DiffRenderer:
    """Renders diff models to terminal-safe text lines conforming to TUI-DESIGN.md."""

    @staticmethod
    def render_inline_diff(
        diff: DiffInfo,
        file_path: str = "",
        mode: TerminalMode = TerminalMode.FULL,
        width: int = 80,
        expanded: bool = True
    ) -> List[str]:
        """Renders an inline diff block."""
        if not diff or not diff.lines:
            summary = diff.summary if diff else "No changes"
            return [f"{file_path}   {summary}".strip()]

        # If collapsed, return only the summary line
        if not expanded:
            summary = diff.summary or f"{file_path}   changes"
            return [summary]

        if mode == TerminalMode.MINIMAL:
            return DiffRenderer._render_minimal(diff, file_path)
        elif mode == TerminalMode.COMPACT:
            return DiffRenderer._render_compact(diff, file_path, width)
        else:
            return DiffRenderer._render_full(diff, file_path, width)

    @staticmethod
    def _render_full(diff: DiffInfo, file_path: str, width: int) -> List[str]:
        box_w = max(40, min(width - 4, 80))
        lines: List[str] = []

        if file_path:
            summary = diff.summary or ""
            lines.append(f"{file_path}   {summary}".strip())

        top_border = "╭" + ("─" * (box_w - 2)) + "╮"
        bot_border = "╰" + ("─" * (box_w - 2)) + "╯"

        lines.append(top_border)
        line_num = 42
        for d in diff.lines:
            prefix = " "
            if d.type == "add":
                prefix = "+"
            elif d.type == "remove":
                prefix = "-"

            # Format line content with line number
            content_w = box_w - 10
            safe_content = d.content[:content_w]
            formatted = f"│ {line_num:>3} {prefix} {safe_content}".ljust(box_w - 1) + "│"
            lines.append(formatted)
            if d.type != "remove":
                line_num += 1

        lines.append(bot_border)
        return lines

    @staticmethod
    def _render_compact(diff: DiffInfo, file_path: str, width: int) -> List[str]:
        lines: List[str] = []
        if file_path:
            lines.append(f"{file_path} {diff.summary or ''}".strip())

        for d in diff.lines:
            prefix = "+" if d.type == "add" else ("-" if d.type == "remove" else " ")
            lines.append(f"  {prefix} {d.content}")
        return lines

    @staticmethod
    def _render_minimal(diff: DiffInfo, file_path: str) -> List[str]:
        lines: List[str] = []
        if file_path:
            lines.append(f"{file_path}:")
        for d in diff.lines:
            prefix = "+" if d.type == "add" else ("-" if d.type == "remove" else " ")
            lines.append(f" {prefix} {d.content}")
        return lines
