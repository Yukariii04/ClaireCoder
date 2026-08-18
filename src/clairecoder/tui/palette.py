"""Command palette overlay conforming to ClaireCoder-TUI-Design-V1-others.png slice 7."""
from dataclasses import dataclass
from typing import List, Optional, Callable
from .states import TerminalMode

@dataclass
class CommandPaletteItem:
    name: str
    description: str
    category: str
    is_ui_command: bool = False

PaletteCommandItem = CommandPaletteItem

class CommandPalette:
    """Live searchable command palette overlay conforming to TUI-DESIGN.md §15."""

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
        CommandPaletteItem("/compact", "Switch to compact mode", "UI / PRESENTATION", is_ui_command=True),
    ]

    def __init__(self, commands: Optional[List[CommandPaletteItem]] = None) -> None:
        self.commands: List[CommandPaletteItem] = commands or list(self.DEFAULT_COMMANDS)
        self.filter_text: str = ""
        self.selected_index: int = 0
        self.on_close: Optional[Callable[[], None]] = None
        self.on_select: Optional[Callable[[CommandPaletteItem], None]] = None

    def type_filter(self, char_or_str: str) -> None:
        """Appends character or query string to filter."""
        self.filter_text += char_or_str
        self.selected_index = 0

    def backspace_filter(self) -> None:
        """Removes the last character from the filter."""
        if self.filter_text:
            self.filter_text = self.filter_text[:-1]
            self.selected_index = 0

    @property
    def filtered_commands(self) -> List[CommandPaletteItem]:
        """Returns commands filtered by filter_text."""
        if not self.filter_text:
            return self.commands
        q = self.filter_text.lower()
        return [c for c in self.commands if q in c.name.lower() or q in c.description.lower()]

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
            matches = self.filtered_commands
            if matches:
                self.selected_index = (self.selected_index - 1) % len(matches)
            return True

        if clean_key in ("down", "j", "\x1b[b"):
            matches = self.filtered_commands
            if matches:
                self.selected_index = (self.selected_index + 1) % len(matches)
            return True

        if clean_key in ("enter", "return"):
            matches = self.filtered_commands
            if matches and 0 <= self.selected_index < len(matches):
                selected = matches[self.selected_index]
                if self.on_select:
                    self.on_select(selected)
            return True

        if key in ("backspace", "\x7f", "\x08"):
            self.backspace_filter()
            return True

        if len(key) == 1 and key.isprintable():
            self.type_filter(key)
            return True

        return False

    def get_selected_command(self) -> Optional[CommandPaletteItem]:
        matches = self.filtered_commands
        if matches and 0 <= self.selected_index < len(matches):
            return matches[self.selected_index]
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

        top_border = f"╭─ Commands " + ("─" * max(0, card_w - 17)) + " x ─╮"
        bot_border = "╰" + ("─" * (card_w - 2)) + "╯"

        def box_line(content: str = "") -> str:
            return f"│ {content}".ljust(card_w - 1) + "│"

        lines = [top_border, box_line("")]

        if self.filter_text:
            lines.append(box_line(f"Filter: {self.filter_text}█"))
            lines.append(box_line("─" * (card_w - 4)))

        matches = self.filtered_commands
        if not matches:
            lines.append(box_line(f"No commands matching '{self.filter_text}'"))
        else:
            # Group commands by category when not searching, or show list directly
            if not self.filter_text:
                categories = ["APPLICATION / INTERACTION", "UI / PRESENTATION"]
                global_idx = 0
                for cat in categories:
                    lines.append(box_line(cat))
                    cat_items = [c for c in matches if c.category == cat]
                    for item in cat_items:
                        cursor = "▶ " if global_idx == self.selected_index else "  "
                        cmd_line = f"{cursor}{item.name:<14} {item.description}"
                        lines.append(box_line(cmd_line))
                        global_idx += 1
                    lines.append(box_line(""))
            else:
                for idx, item in enumerate(matches):
                    cursor = "▶ " if idx == self.selected_index else "  "
                    lines.append(box_line(f"{cursor}{item.name:<14} {item.description} ({item.category})"))

        lines.append(box_line("       Type / or ? to open this menu"))
        lines.append(bot_border)
        return lines

    def _render_compact(self, width: int) -> List[str]:
        card_w = max(40, min(width - 2, 54))
        top_border = f"╭─ Commands ({len(self.filtered_commands)}) " + ("─" * max(0, card_w - 18)) + "╮"
        bot_border = "╰" + ("─" * (card_w - 2)) + "╯"

        lines = [top_border]
        if self.filter_text:
            lines.append(f"│ Search: {self.filter_text}".ljust(card_w - 1) + "│")

        for idx, item in enumerate(self.filtered_commands[:8]):
            cursor = ">" if idx == self.selected_index else " "
            lines.append(f"│ {cursor} {item.name:<12} {item.description}".ljust(card_w - 1) + "│")
        lines.append(f"│ [enter: run | esc: close]".ljust(card_w - 1) + "│")
        lines.append(bot_border)
        return lines

    def _render_minimal(self) -> List[str]:
        lines = ["=== Available Commands ==="]
        for c in self.filtered_commands:
            lines.append(f"{c.name:<12} - {c.description}")
        return lines
