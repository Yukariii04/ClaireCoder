"""Command palette overlay conforming to CC-PRD-011 and TUI-DESIGN.md §15."""
from dataclasses import dataclass
from typing import List, Optional, Callable
from .states import TerminalMode
from .canvas import visible_length

@dataclass
class CommandPaletteItem:
    name: str
    description: str
    category: str
    is_ui_command: bool = False

PaletteCommandItem = CommandPaletteItem

class CommandPalette:
    """Direct selectable command palette overlay conforming to TUI-DESIGN.md §15."""

    DEFAULT_COMMANDS = [
        # APPLICATION / INTERACTION
        CommandPaletteItem("/help", "Show help", "APPLICATION / INTERACTION", is_ui_command=False),
        CommandPaletteItem("/status", "Show status", "APPLICATION / INTERACTION", is_ui_command=False),
        CommandPaletteItem("/model", "Switch model", "APPLICATION / INTERACTION", is_ui_command=False),
        CommandPaletteItem("/mode", "Switch mode", "APPLICATION / INTERACTION", is_ui_command=False),
        CommandPaletteItem("/session", "Session menu", "APPLICATION / INTERACTION", is_ui_command=False),
        CommandPaletteItem("/plan", "Show current plan", "APPLICATION / INTERACTION", is_ui_command=False),
        CommandPaletteItem("/pause", "Pause execution", "APPLICATION / INTERACTION", is_ui_command=False),
        CommandPaletteItem("/resume", "Resume execution", "APPLICATION / INTERACTION", is_ui_command=False),
        CommandPaletteItem("/cancel", "Cancel current operation", "APPLICATION / INTERACTION", is_ui_command=False),
        CommandPaletteItem("/clear", "Clear transcript", "APPLICATION / INTERACTION", is_ui_command=False),
        CommandPaletteItem("/exit", "Exit ClaireCoder", "APPLICATION / INTERACTION", is_ui_command=False),
        # UI / PRESENTATION
        CommandPaletteItem("/tree", "Open file tree", "UI / PRESENTATION", is_ui_command=True),
        CommandPaletteItem("/review", "Open review diff overlay", "UI / PRESENTATION", is_ui_command=True),
    ]

    def __init__(self, commands: Optional[List[CommandPaletteItem]] = None) -> None:
        self.commands: List[CommandPaletteItem] = list(commands) if commands is not None else list(self.DEFAULT_COMMANDS)
        self.selected_index: int = 0
        self.on_close: Optional[Callable[[], None]] = None
        self.on_select: Optional[Callable[[CommandPaletteItem], None]] = None

    @property
    def filtered_commands(self) -> List[CommandPaletteItem]:
        """Backward compatibility property returning the complete command list."""
        return self.commands

    @property
    def selected_command(self) -> Optional[CommandPaletteItem]:
        """Returns the currently selected command item."""
        return self.get_selected_command()

    def handle_key(self, key: str) -> bool:
        """Handles keyboard input while command palette owns focus."""
        clean_key = key.strip().lower() if isinstance(key, str) else ""

        if key in ("\x1b", "Esc", "esc", "escape", "Escape"):
            if self.on_close:
                self.on_close()
            return False

        if clean_key in ("up", "k", "\x1b[a"):
            if self.commands:
                self.selected_index = (self.selected_index - 1) % len(self.commands)
            return True

        if clean_key in ("down", "j", "\x1b[b"):
            if self.commands:
                self.selected_index = (self.selected_index + 1) % len(self.commands)
            return True

        if clean_key in ("pageup", "page_up", "pgup"):
            if self.commands:
                self.selected_index = max(0, self.selected_index - 5)
            return True

        if clean_key in ("pagedown", "page_down", "pgdn"):
            if self.commands:
                self.selected_index = min(len(self.commands) - 1, self.selected_index + 5)
            return True

        if clean_key == "home":
            self.selected_index = 0
            return True

        if clean_key == "end":
            if self.commands:
                self.selected_index = len(self.commands) - 1
            return True

        if clean_key in ("enter", "return"):
            if self.commands and 0 <= self.selected_index < len(self.commands):
                selected = self.commands[self.selected_index]
                if self.on_select:
                    self.on_select(selected)
            return True

        return False

    def get_selected_command(self) -> Optional[CommandPaletteItem]:
        if self.commands and 0 <= self.selected_index < len(self.commands):
            return self.commands[self.selected_index]
        return None

    def render(self, mode: TerminalMode = TerminalMode.FULL, width: int = 80) -> List[str]:
        """Renders the command palette card conforming to TUI-DESIGN.md §15."""
        if mode == TerminalMode.MINIMAL:
            return self._render_minimal()
        elif mode == TerminalMode.COMPACT:
            return self._render_compact(width)
        else:
            return self._render_full(width)

    def _render_full(self, width: int) -> List[str]:
        card_w = max(52, min(width - 4, 60))
        inner_w = card_w - 4

        pad_top = max(0, card_w - len("╭─ Commands ") - len(" x ─╮"))
        top_border = f"╭─ Commands " + ("─" * pad_top) + " x ─╮"
        bot_border = "╰" + ("─" * (card_w - 2)) + "╯"

        def box_line(content: str = "") -> str:
            vis = visible_length(content)
            if vis > inner_w:
                content = content[:inner_w]
                vis = visible_length(content)
            pad = max(0, inner_w - vis)
            return f"│ {content}{' ' * pad} │"

        lines = [top_border, box_line("")]

        categories = ["APPLICATION / INTERACTION", "UI / PRESENTATION"]
        global_idx = 0
        for cat in categories:
            lines.append(box_line(cat))
            cat_items = [c for c in self.commands if c.category == cat]
            for item in cat_items:
                cursor = "  ▶ " if global_idx == self.selected_index else "    "
                cmd_line = f"{cursor}{item.name:<14} {item.description}"
                lines.append(box_line(cmd_line))
                global_idx += 1
            if cat != categories[-1]:
                lines.append(box_line(""))

        lines.append(box_line(""))
        lines.append(box_line("  ↑/↓ select   Enter open   Esc back"))
        lines.append(bot_border)
        return lines

    def _render_compact(self, width: int) -> List[str]:
        card_w = max(44, min(width - 2, 54))
        inner_w = card_w - 4
        pad_top = max(0, card_w - len("╭─ Commands ") - 1)
        top_border = f"╭─ Commands " + ("─" * pad_top) + "╮"
        bot_border = "╰" + ("─" * (card_w - 2)) + "╯"

        def box_line_c(content: str = "") -> str:
            vis = visible_length(content)
            if vis > inner_w:
                content = content[:inner_w]
                vis = visible_length(content)
            pad = max(0, inner_w - vis)
            return f"│ {content}{' ' * pad} │"

        lines = [top_border]
        for idx, item in enumerate(self.commands):
            cursor = "▶" if idx == self.selected_index else " "
            lines.append(box_line_c(f"{cursor} {item.name:<12} {item.description}"))
        lines.append(box_line_c("  ↑/↓ select  Enter open  Esc back"))
        lines.append(bot_border)
        return lines

    def _render_minimal(self) -> List[str]:
        lines = ["=== Available Commands ==="]
        for idx, c in enumerate(self.commands):
            cursor = "▶ " if idx == self.selected_index else "  "
            lines.append(f"{cursor}{c.name:<12} - {c.description}")
        return lines
