"""Task / Workflow view overlay conforming to ClaireCoder-TUI-Design-V1-others.png slice 6."""
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from .states import TerminalMode
from .canvas import visible_length, visible_slice


@dataclass
class WorkflowTaskItem:
    number: int
    title: str
    marker: str  # '✓', '▶', '○', '✗'


class TaskViewOverlay:
    """Task and workflow progress overlay conforming to TUI-DESIGN.md §14 and CC-PRD-004.
    
    Guarantees:
      - Objective is never hard-cropped (multiline word-wrapped).
      - Fixed card geometry (height = 16 rows) so outer TUI frame never grows.
      - Internal bounded vertical scrolling (Up/Down/PgUp/PgDn/Home/End).
      - Coherent lifecycle: No active workflow shows Objective: None.
    """

    DEFAULT_TASKS = [
        WorkflowTaskItem(1, "Understand objective", "✓"),
        WorkflowTaskItem(2, "Plan changes", "✓"),
        WorkflowTaskItem(3, "Implement changes", "▶"),
        WorkflowTaskItem(4, "Verify", "○"),
        WorkflowTaskItem(5, "Complete", "○"),
    ]

    def __init__(
        self,
        tasks: Optional[List[WorkflowTaskItem]] = None,
        progress_pct: int = 0,
        objective: str = "",
        status: str = "Idle",
        failure_reason: Optional[str] = None,
    ) -> None:
        self.tasks: List[WorkflowTaskItem] = tasks if tasks is not None else []
        self.progress_pct: int = progress_pct
        self.objective: str = objective
        self.status: str = status
        self.failure_reason: Optional[str] = failure_reason
        self.viewport_offset: int = 0
        self.card_height: int = 16  # Fixed total card height
        self.on_close: Optional[Callable[[], None]] = None

    def reset(self) -> None:
        """Reset task view state when no workflow is active."""
        self.tasks = []
        self.progress_pct = 0
        self.objective = ""
        self.status = "Idle"
        self.failure_reason = None
        self.viewport_offset = 0

    def handle_key(self, key: str) -> bool:
        """Handle keyboard input in task view overlay."""
        clean_key = key.strip().lower() if isinstance(key, str) else ""

        if key in ("\x1b", "Esc", "esc", "escape", "Escape") or clean_key in ("q", "back"):
            if self.on_close:
                self.on_close()
            return True

        # Scrolling keys
        if clean_key in ("up", "k"):
            self.viewport_offset = max(0, self.viewport_offset - 1)
            return True
        elif clean_key in ("down", "j"):
            self.viewport_offset = self.viewport_offset + 1
            return True
        elif clean_key in ("pageup", "pgup"):
            self.viewport_offset = max(0, self.viewport_offset - 6)
            return True
        elif clean_key in ("pagedown", "pgdn"):
            self.viewport_offset = self.viewport_offset + 6
            return True
        elif clean_key == "home":
            self.viewport_offset = 0
            return True
        elif clean_key == "end":
            self.viewport_offset = 999  # Bounded during render
            return True

        return True  # Absorb all input while overlay is open

    def render(self, mode: TerminalMode = TerminalMode.FULL, width: int = 58) -> List[str]:
        """Renders the task / workflow overlay card with bounded vertical scrolling."""
        card_w = max(42, min(width, 58))
        inner_w = card_w - 4
        body_h = self.card_height - 3  # Top border (1) + bottom border (1) + footer hint (1)

        def frame_line(content: str = "") -> str:
            vis = visible_length(content)
            if vis > inner_w:
                content = visible_slice(content, 0, inner_w)
                vis = visible_length(content)
            pad = max(0, inner_w - vis)
            return f"│ {content}{' ' * pad} │"

        # 1. Build unconstrained virtual body rows
        body_rows: List[str] = [""]

        # Tasks section
        if self.tasks:
            for t in self.tasks:
                marker = t.marker
                # Human readable title
                title = t.title
                avail_title_w = max(10, inner_w - 6 - len(marker))
                if visible_length(title) > avail_title_w:
                    title = visible_slice(title, 0, avail_title_w - 2) + ".."
                pad_sp = max(2, inner_w - 4 - visible_length(title) - len(marker))
                body_rows.append(f"{t.number:<3} {title}{' ' * pad_sp}{marker}")
        else:
            body_rows.append("No active workflow tasks.")

        body_rows.append("")
        body_rows.append(f"Task Progress: {self.status}")

        # Progress bar
        bar_w = max(10, inner_w - 8)
        filled_count = int(bar_w * self.progress_pct / 100)
        empty_count = max(0, bar_w - filled_count)
        bar_str = ("█" * filled_count) + ("░" * empty_count) + f"  {self.progress_pct}%"
        body_rows.append(bar_str)
        body_rows.append("")

        # Objective section with full multiline word-wrapping
        if self.objective:
            body_rows.append("Objective:")
            # Word wrap objective text
            words = self.objective.replace("\r\n", "\n").replace("\n", " \n ").split(" ")
            cur_line = "  "
            for w in words:
                if w == "\n":
                    body_rows.append(cur_line)
                    cur_line = "  "
                    continue
                if not w:
                    continue
                test_line = f"{cur_line} {w}" if cur_line != "  " else f"{cur_line}{w}"
                if visible_length(test_line) <= inner_w - 2:
                    cur_line = test_line
                else:
                    body_rows.append(cur_line)
                    cur_line = f"  {w}"
            if cur_line.strip():
                body_rows.append(cur_line)
        else:
            body_rows.append("Objective: None")

        if self.failure_reason:
            body_rows.append("")
            body_rows.append(f"Error: {self.failure_reason}")

        # 2. Apply vertical scrolling
        max_offset = max(0, len(body_rows) - body_h)
        self.viewport_offset = min(self.viewport_offset, max_offset)

        visible_rows = body_rows[self.viewport_offset : self.viewport_offset + body_h]

        # 3. Assemble framed lines
        lines: List[str] = []
        top_bar = "╭─ Current Workflow " + ("─" * max(0, card_w - 25)) + " x ─╮"
        lines.append(top_bar)

        for row in visible_rows:
            lines.append(frame_line(row))

        while len(lines) < self.card_height - 2:
            lines.append(frame_line(""))

        # Footer with scroll hints if scrollable
        if max_offset > 0:
            lines.append(frame_line("↑/↓ scroll   PgUp/PgDn   Esc back"))
        else:
            lines.append(frame_line("Esc back"))

        lines.append("╰" + ("─" * (card_w - 2)) + "╯")

        return lines
