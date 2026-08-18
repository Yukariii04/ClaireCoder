"""Review changes overlay conforming to ClaireCoder-TUI-Design-V1-others.png slice 5."""
from typing import List, Optional, Callable
from .states import TerminalMode
from .diff import FileDiff

class ReviewOverlay:
    """Session change review surface conforming to TUI-DESIGN.md §13."""

    def __init__(self, files: Optional[List[FileDiff]] = None) -> None:
        self.files: List[FileDiff] = files or []
        self.selected_index: int = 0
        self.showing_diff: bool = False
        self.on_close: Optional[Callable[[], None]] = None
        self.on_commit: Optional[Callable[[], None]] = None

    def set_files(self, files: List[FileDiff]) -> None:
        """Sets the files in the review session."""
        self.files = files
        self.selected_index = 0
        self.showing_diff = False

    @property
    def total_files_changed(self) -> int:
        return len(self.files)

    @property
    def total_insertions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions for f in self.files)

    @property
    def selected_file(self) -> Optional[FileDiff]:
        if 0 <= self.selected_index < len(self.files):
            return self.files[self.selected_index]
        return None

    def handle_key(self, key: str) -> bool:
        """Handles keyboard input while review overlay owns focus."""
        clean_key = key.strip().lower() if isinstance(key, str) else ""

        if key in ("\x1b", "Esc", "esc", "escape", "Escape"):
            if self.showing_diff:
                self.showing_diff = False
                return True
            if self.on_close:
                self.on_close()
            return False

        if clean_key in ("q", "back"):
            if self.showing_diff:
                self.showing_diff = False
                return True
            if self.on_close:
                self.on_close()
            return False

        if clean_key in ("up", "k", "\x1b[A"):
            if self.files and not self.showing_diff:
                self.selected_index = (self.selected_index - 1) % len(self.files)
            return True

        if clean_key in ("down", "j", "\x1b[B"):
            if self.files and not self.showing_diff:
                self.selected_index = (self.selected_index + 1) % len(self.files)
            return True

        if clean_key in ("enter", "return", " "):
            if self.files:
                self.showing_diff = not self.showing_diff
            return True

        if clean_key == "c":
            if self.on_commit:
                self.on_commit()
            return True

        return False

    def render(self, mode: TerminalMode = TerminalMode.FULL, width: int = 80) -> List[str]:
        """Renders the review overlay based on active terminal mode."""
        if mode == TerminalMode.MINIMAL:
            return self._render_minimal()
        elif mode == TerminalMode.COMPACT:
            return self._render_compact(width)
        else:
            return self._render_full(width)

    def _render_full(self, width: int) -> List[str]:
        card_w = max(50, min(width - 4, 64))
        inner_w = card_w - 4

        top_border = f"╭─ Changes this session " + ("─" * max(0, card_w - 29)) + " x ─╮"
        bot_border = "╰" + ("─" * (card_w - 2)) + "╯"
        divider = "│ " + ("─" * (card_w - 4)) + " │"

        def box_line(content: str = "") -> str:
            return f"│ {content}".ljust(card_w - 1) + "│"

        lines = [top_border, box_line("")]

        if self.showing_diff and self.selected_file:
            # Render selected file diff view
            sel = self.selected_file
            tag = " (new)" if sel.is_new else (" (deleted)" if sel.is_deleted else "")
            lines.append(box_line(f"Diff for: {sel.file_path}{tag}"))
            lines.append(box_line(f"Changes: +{sel.additions} -{sel.deletions}"))
            lines.append(divider)
            if sel.lines:
                for d in sel.lines:
                    prefix = "+" if d.type == "add" else ("-" if d.type == "remove" else " ")
                    lines.append(box_line(f"  {prefix} {d.content[:inner_w - 4]}"))
            else:
                lines.append(box_line("  No line-level diff details."))
            lines.append(divider)
            lines.append(box_line("[enter/q] back to file list"))
        else:
            if not self.files:
                lines.append(box_line("No changes this session."))
            else:
                for idx, f in enumerate(self.files):
                    prefix = "▶ " if idx == self.selected_index else "  "
                    tag = " (new)" if f.is_new else (" (deleted)" if f.is_deleted else "")
                    file_info = f"{f.file_path:<24} +{f.additions} -{f.deletions}{tag}"
                    lines.append(box_line(f"{prefix}{file_info}"))

                lines.append(box_line(""))
                lines.append(divider)
                lines.append(box_line(f"{self.total_files_changed} files changed"))
                lines.append(box_line(f"{self.total_insertions} insertions(+)"))
                lines.append(box_line(f"{self.total_deletions} deletions(-)"))
                lines.append(box_line(""))
                lines.append(box_line("[enter] view diff   [c] commit   [q] back"))
                lines.append(box_line(""))
                lines.append(box_line("Press enter on a file to view full diff"))

        lines.append(bot_border)
        return lines

    def _render_compact(self, width: int) -> List[str]:
        card_w = max(40, min(width - 2, 60))
        top_border = f"╭─ Changes ({len(self.files)} files) " + ("─" * max(0, card_w - 22)) + "╮"
        bot_border = "╰" + ("─" * (card_w - 2)) + "╯"

        lines = [top_border]
        if self.showing_diff and self.selected_file:
            sel = self.selected_file
            lines.append(f"│ Diff: {sel.file_path}".ljust(card_w - 1) + "│")
            for d in sel.lines:
                prefix = "+" if d.type == "add" else ("-" if d.type == "remove" else " ")
                lines.append(f"│  {prefix} {d.content}".ljust(card_w - 1) + "│")
            lines.append(f"│ [enter/q] back".ljust(card_w - 1) + "│")
        else:
            for idx, f in enumerate(self.files):
                cursor = ">" if idx == self.selected_index else " "
                lines.append(f"│ {cursor} {f.file_path:<20} +{f.additions} -{f.deletions}".ljust(card_w - 1) + "│")
            lines.append(f"│ {self.total_files_changed} files | +{self.total_insertions} -{self.total_deletions}".ljust(card_w - 1) + "│")
            lines.append(f"│ [enter] diff  [q] back".ljust(card_w - 1) + "│")
        lines.append(bot_border)
        return lines

    def _render_minimal(self) -> List[str]:
        lines = [f"=== Changes this session ({self.total_files_changed} files: +{self.total_insertions} -{self.total_deletions}) ==="]
        if self.showing_diff and self.selected_file:
            sel = self.selected_file
            lines.append(f"Diff for {sel.file_path}:")
            for d in sel.lines:
                prefix = "+" if d.type == "add" else ("-" if d.type == "remove" else " ")
                lines.append(f" {prefix} {d.content}")
            lines.append("(Press Enter/q to return)")
        else:
            for idx, f in enumerate(self.files):
                cursor = ">" if idx == self.selected_index else " "
                lines.append(f"{cursor} {f.file_path} (+{f.additions} -{f.deletions})")
            lines.append("[enter: view diff | q: back]")
        return lines
