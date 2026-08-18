"""Task / Workflow view overlay conforming to ClaireCoder-TUI-Design-V1-others.png slice 6."""
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from .states import TerminalMode

@dataclass
class WorkflowTaskItem:
    number: int
    title: str
    marker: str  # '✓', '▶', '○'

class TaskViewOverlay:
    """Task and workflow progress overlay conforming to TUI-DESIGN.md §14."""

    DEFAULT_TASKS = [
        WorkflowTaskItem(1, "Understand objective", "✓"),
        WorkflowTaskItem(2, "Plan changes", "✓"),
        WorkflowTaskItem(3, "Implement changes", "▶"),
        WorkflowTaskItem(4, "Verify", "○"),
        WorkflowTaskItem(5, "Complete", "○"),
    ]

    def __init__(self, tasks: Optional[List[WorkflowTaskItem]] = None, progress_pct: int = 40, objective: str = "") -> None:
        self.tasks = tasks or list(self.DEFAULT_TASKS)
        self.progress_pct = progress_pct
        self.objective = objective or "Add streaming decode support with fallback to greedy decoding"
        self.on_close: Optional[Callable[[], None]] = None

    def handle_key(self, key: str) -> bool:
        clean_key = key.strip().lower() if isinstance(key, str) else ""
        if key in ("\x1b", "Esc", "esc", "escape", "Escape") or clean_key in ("q", "back"):
            if self.on_close:
                self.on_close()
            return True
        return False

    def render(self, mode: TerminalMode = TerminalMode.FULL, width: int = 58) -> List[str]:
        """Renders the task / workflow overlay card."""
        card_w = max(40, min(width, 58))
        inner_w = card_w - 4

        def frame_line(content: str = "") -> str:
            safe = content[:inner_w]
            return f"│ {safe}".ljust(card_w - 1) + "│"

        lines: List[str] = []

        # Top border
        top_bar = f"╭─ Current Workflow " + ("─" * max(0, card_w - 25)) + " x ─╮"
        lines.append(top_bar)
        lines.append(frame_line(""))

        # Task list
        for t in self.tasks:
            pad = max(2, inner_w - 4 - len(t.title) - len(t.marker) - 2)
            row_str = f"{t.number:<3} {t.title}{' ' * pad}{t.marker}"
            lines.append(frame_line(row_str))

        lines.append(frame_line(""))
        lines.append(frame_line("Task Progress"))

        # Progress bar
        bar_w = max(10, inner_w - 8)
        filled_count = int(bar_w * self.progress_pct / 100)
        empty_count = bar_w - filled_count
        bar_str = ("█" * filled_count) + ("░" * empty_count) + f"  {self.progress_pct}%"
        lines.append(frame_line(bar_str))

        lines.append(frame_line(""))
        lines.append(frame_line("Objective:"))
        for obj_line in self.objective.splitlines():
            lines.append(frame_line(obj_line))

        lines.append(frame_line(""))
        lines.append("╰" + ("─" * (card_w - 2)) + "╯")

        return lines
