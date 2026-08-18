"""File tree overlay conforming to ClaireCoder-TUI-Design-V1-others.png slice 4."""
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from .states import TerminalMode

@dataclass
class FileTreeItem:
    path: str
    status: str = ""  # 'M', '+', ''

class FileTreeOverlay:
    """File tree view overlay conforming to TUI-DESIGN.md §12."""

    DEFAULT_ITEMS = [
        FileTreeItem("claire-speech-engine/"),
        FileTreeItem("└─ src/"),
        FileTreeItem("   ├─ decoder.py", "M"),
        FileTreeItem("   ├─ tokenizer.py"),
        FileTreeItem("   ├─ router.py", "+"),
        FileTreeItem("   └─ utils.py"),
        FileTreeItem("└─ tests/"),
        FileTreeItem("   ├─ test_decoder.py", "M"),
        FileTreeItem("   └─ test_router.py"),
        FileTreeItem("└─ docs/"),
        FileTreeItem("README.md"),
        FileTreeItem("pyproject.toml"),
    ]

    def __init__(self, items: Optional[List[FileTreeItem]] = None) -> None:
        self.items = items or list(self.DEFAULT_ITEMS)
        self.selected_index = 0
        self.on_close: Optional[Callable[[], None]] = None

    def handle_key(self, key: str) -> bool:
        clean_key = key.strip().lower() if isinstance(key, str) else ""
        if key in ("\x1b", "Esc", "esc", "escape", "Escape") or clean_key in ("q", "back"):
            if self.on_close:
                self.on_close()
            return True
        if clean_key in ("up", "k", "\x1b[A"):
            if self.items:
                self.selected_index = (self.selected_index - 1) % len(self.items)
            return True
        if clean_key in ("down", "j", "\x1b[B"):
            if self.items:
                self.selected_index = (self.selected_index + 1) % len(self.items)
            return True
        return False

    def render(self, mode: TerminalMode = TerminalMode.FULL, width: int = 58) -> List[str]:
        """Renders the file tree overlay card."""
        card_w = max(40, min(width, 58))
        inner_w = card_w - 4

        def frame_line(content: str = "") -> str:
            safe = content[:inner_w]
            return f"│ {safe}".ljust(card_w - 1) + "│"

        lines: List[str] = []

        # Top border
        top_bar = f"╭─ Files " + ("─" * max(0, card_w - 14)) + " x ─╮"
        lines.append(top_bar)
        lines.append(frame_line(""))

        for item in self.items:
            if item.status:
                pad = max(2, inner_w - len(item.path) - len(item.status) - 2)
                row_str = f"{item.path}{' ' * pad}{item.status}"
            else:
                row_str = item.path
            lines.append(frame_line(row_str))

        lines.append(frame_line(""))
        legend = "M modified   + new   plain = untouched"
        lines.append(frame_line(legend))
        lines.append("╰" + ("─" * (card_w - 2)) + "╯")

        return lines
