"""Reviewable, width-safe session changes overlay."""
from typing import List, Optional, Callable

from .activity import DiffLine, truncate_path
from .canvas import visible_length, visible_slice
from .diff import FileDiff
from .states import TerminalMode


class ReviewOverlay:
    """Session change review surface conforming to TUI-DESIGN.md §13."""

    def __init__(self, files: Optional[List[FileDiff]] = None) -> None:
        self.files: List[FileDiff] = files or []
        self.selected_index: int = 0
        self.showing_diff: bool = False
        self.diff_offset: int = 0
        self._diff_page_size: int = 8
        self.on_close: Optional[Callable[[], None]] = None
        self.on_commit: Optional[Callable[[], None]] = None

    def set_files(self, files: List[FileDiff]) -> None:
        """Replace the list and return to its first file."""
        self.files = list(files)
        self.selected_index = 0
        self.showing_diff = False
        self.diff_offset = 0

    def update_files(self, files: List[FileDiff]) -> None:
        """Refresh session data without losing the current file or view."""
        selected_path = self.selected_file.file_path if self.selected_file else None
        was_showing_diff = self.showing_diff
        self.files = list(files)
        if selected_path:
            self.selected_index = next(
                (index for index, item in enumerate(self.files) if item.file_path == selected_path),
                min(self.selected_index, max(0, len(self.files) - 1)),
            )
        else:
            self.selected_index = min(self.selected_index, max(0, len(self.files) - 1))
        self.showing_diff = was_showing_diff and self.selected_file is not None
        self.diff_offset = 0 if not self.showing_diff else self.diff_offset

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

        if clean_key in ("escape", "esc", "q", "back"):
            if self.showing_diff:
                self.showing_diff = False
                self.diff_offset = 0
                return True
            if self.on_close:
                self.on_close()
            return True

        if self.showing_diff:
            if clean_key in ("up", "k"):
                self.diff_offset = max(0, self.diff_offset - 1)
                return True
            if clean_key in ("down", "j"):
                self.diff_offset += 1
                return True
            if clean_key in ("pageup", "pgup"):
                self.diff_offset = max(0, self.diff_offset - self._diff_page_size)
                return True
            if clean_key in ("pagedown", "pgdn"):
                self.diff_offset += self._diff_page_size
                return True
            if clean_key == "home":
                self.diff_offset = 0
                return True
            if clean_key == "end":
                self.diff_offset = 10**9
                return True
            if clean_key in ("enter", "return", " "):
                self.showing_diff = False
                self.diff_offset = 0
                return True
            return True

        if clean_key in ("up", "k"):
            if self.files:
                self.selected_index = (self.selected_index - 1) % len(self.files)
            return True
        if clean_key in ("down", "j"):
            if self.files:
                self.selected_index = (self.selected_index + 1) % len(self.files)
            return True
        if clean_key in ("enter", "return", " "):
            if self.files:
                self.showing_diff = True
                self.diff_offset = 0
            return True
        if clean_key == "c":
            if self.on_commit:
                self.on_commit()
            return True
        return True

    def render(
        self,
        mode: TerminalMode = TerminalMode.FULL,
        width: int = 80,
        height: Optional[int] = None,
    ) -> List[str]:
        """Render a bounded overlay whose borders always fit the terminal."""
        if height is not None and height < 4:
            return self._render_minimal(width=width, height=height)
        if mode == TerminalMode.MINIMAL or width < 26:
            return self._render_minimal(width=width, height=height)
        if mode == TerminalMode.COMPACT or width < 36:
            return self._render_compact(width=width, height=height)
        if height is not None and height < 12:
            return self._render_compact(width=width, height=height)
        return self._render_full(width=width, height=height)

    @staticmethod
    def _fit(text: str, width: int) -> str:
        return visible_slice(text, 0, max(0, width))

    def _render_full(self, width: int, height: Optional[int]) -> List[str]:
        card_w = max(34, min(width - 2, 64))
        inner_w = card_w - 4

        def box_line(content: str = "") -> str:
            content = self._fit(content, inner_w)
            pad = max(0, inner_w - visible_length(content))
            return f"│ {content}{' ' * pad} │"

        top_prefix = "╭─ Changes this session "
        top_suffix = " x ─╮"
        top_border = top_prefix + ("─" * max(0, card_w - len(top_prefix) - len(top_suffix))) + top_suffix
        bottom_border = "╰" + ("─" * (card_w - 2)) + "╯"
        divider = box_line("─" * inner_w)
        height_limit = max(4, height) if height is not None else None
        lines = [top_border, box_line("")]

        if self.showing_diff and self.selected_file:
            selected = self.selected_file
            tag = " (new)" if selected.is_new else (" (deleted)" if selected.is_deleted else "")
            lines.extend([
                box_line(f"Diff for: {selected.file_path}{tag}"),
                box_line(f"Changes: +{selected.additions} -{selected.deletions}"),
                divider,
            ])
            diff_lines = selected.lines or [DiffLine("context", "No line-level diff details.")]
            capacity = len(diff_lines) if height_limit is None else max(1, height_limit - len(lines) - 3)
            self._diff_page_size = capacity
            max_offset = max(0, len(diff_lines) - capacity)
            self.diff_offset = min(self.diff_offset, max_offset)
            start = self.diff_offset
            visible_diff = diff_lines[start : start + capacity]
            for item in visible_diff:
                prefix = "+" if item.type == "add" else ("-" if item.type == "remove" else " ")
                lines.append(box_line(f"  {prefix} {item.content}"))
            if len(diff_lines) > capacity:
                end = start + len(visible_diff)
                footer = f"Lines {start + 1}-{end}/{len(diff_lines)}  ↑/↓ scroll   [enter/q] back"
            else:
                footer = "[enter/q] back to file list"
            lines.extend([divider, box_line(footer)])
        elif not self.files:
            lines.append(box_line("No changes this session."))
        else:
            fixed_rows = 12
            if height_limit is None:
                file_capacity = len(self.files)
            else:
                file_capacity = max(1, height_limit - fixed_rows - (1 if len(self.files) > height_limit - fixed_rows else 0))
            start_index = 0
            if len(self.files) > file_capacity:
                start_index = min(
                    max(0, self.selected_index - file_capacity + 1),
                    len(self.files) - file_capacity,
                )
            visible_files = self.files[start_index : start_index + file_capacity]
            for offset, file in enumerate(visible_files, start=start_index):
                cursor = "▶ " if offset == self.selected_index else "  "
                suffix = f"+{file.additions} -{file.deletions}"
                if file.is_new:
                    suffix += " (new)"
                elif file.is_deleted:
                    suffix += " (deleted)"
                path_width = max(1, inner_w - visible_length(cursor) - visible_length(suffix) - 2)
                path = truncate_path(file.file_path, max_len=path_width)
                lines.append(box_line(f"{cursor}{path.ljust(path_width)} {suffix}"))
            if len(self.files) > len(visible_files):
                lines.append(box_line(f"Showing {start_index + 1}-{start_index + len(visible_files)} of {len(self.files)} files"))

            lines.extend([
                box_line(""),
                divider,
                box_line(f"{self.total_files_changed} files changed"),
                box_line(f"{self.total_insertions} insertions(+)"),
                box_line(f"{self.total_deletions} deletions(-)"),
                box_line(""),
                box_line("[↑/↓] select   [enter] view diff   [c] commit   [q] back"),
                box_line(""),
                box_line("Press enter on a file to view its diff"),
            ])

        if height_limit is not None and len(lines) + 1 > height_limit:
            # Keep the header and footer visible even when the terminal is short.
            available = max(0, height_limit - 4)
            content = lines[2 : 2 + available]
            lines = [top_border, box_line("")] + content
            lines.append(box_line("↑/↓ scroll   q back"))
        lines.append(bottom_border)
        return lines

    def _render_compact(self, width: int, height: Optional[int]) -> List[str]:
        card_w = max(24, min(width - 2, 60))
        inner_w = card_w - 4

        def box_line(content: str = "") -> str:
            content = self._fit(content, inner_w)
            return f"│ {content}{' ' * max(0, inner_w - visible_length(content))} │"

        title = self._fit(f" Changes ({len(self.files)} files) ", card_w - 2)
        top = "╭" + title + ("─" * max(0, card_w - visible_length(title) - 2)) + "╮"
        bottom = "╰" + ("─" * (card_w - 2)) + "╯"
        lines = [top]

        if self.showing_diff and self.selected_file:
            selected = self.selected_file
            lines.append(box_line(f"Diff: {selected.file_path}"))
            diff_lines = selected.lines or [DiffLine("context", "No line-level diff details.")]
            capacity = len(diff_lines) if height is None else max(1, height - 4)
            self._diff_page_size = capacity
            self.diff_offset = min(self.diff_offset, max(0, len(diff_lines) - capacity))
            start = self.diff_offset
            visible = diff_lines[start : start + capacity]
            for item in visible:
                prefix = "+" if item.type == "add" else ("-" if item.type == "remove" else " ")
                lines.append(box_line(f"{prefix} {item.content}"))
            lines.append(box_line("↑/↓ scroll   [enter/q] back"))
        else:
            rows = self.files
            capacity = len(rows) if height is None else max(1, height - 4)
            start = min(max(0, self.selected_index - capacity + 1), max(0, len(rows) - capacity))
            for index, item in enumerate(rows[start : start + capacity], start=start):
                cursor = ">" if index == self.selected_index else " "
                suffix = f" +{item.additions} -{item.deletions}"
                path = truncate_path(item.file_path, max_len=max(1, inner_w - len(suffix) - 4))
                lines.append(box_line(f"{cursor} {path}{suffix}"))
            lines.append(box_line(f"{self.total_files_changed} files | +{self.total_insertions} -{self.total_deletions}"))
            lines.append(box_line("[↑/↓] select   [enter] diff   [q] back"))

        lines.append(bottom)
        if height is not None and len(lines) > height:
            lines = lines[: max(1, height - 1)] + [bottom]
        return lines

    def _render_minimal(self, width: int, height: Optional[int]) -> List[str]:
        lines = [f"=== Changes this session ({self.total_files_changed} files: +{self.total_insertions} -{self.total_deletions}) ==="]
        if self.showing_diff and self.selected_file:
            selected = self.selected_file
            lines.append(f"Diff for {selected.file_path}:")
            diff_lines = selected.lines or [DiffLine("context", "No line-level diff details.")]
            capacity = len(diff_lines) if height is None else max(1, height - 3)
            self._diff_page_size = capacity
            self.diff_offset = min(self.diff_offset, max(0, len(diff_lines) - capacity))
            start = self.diff_offset
            visible_diff = diff_lines[start : start + capacity]
            for item in visible_diff:
                prefix = "+" if item.type == "add" else ("-" if item.type == "remove" else " ")
                lines.append(f" {prefix} {item.content}")
            if len(diff_lines) > capacity:
                lines.append(f"Lines {start + 1}-{start + len(visible_diff)}/{len(diff_lines)} · ↑/↓ scroll · q back")
            else:
                lines.append("(Press Enter/q to return)")
        else:
            capacity = len(self.files) if height is None else max(1, height - 2)
            start = min(
                max(0, self.selected_index - capacity + 1),
                max(0, len(self.files) - capacity),
            )
            visible_files = self.files[start : start + capacity]
            for index, file in enumerate(visible_files, start=start):
                cursor = ">" if index == self.selected_index else " "
                lines.append(f"{cursor} {file.file_path} (+{file.additions} -{file.deletions})")
            if len(visible_files) < len(self.files):
                lines.append(f"Showing {start + 1}-{start + len(visible_files)} of {len(self.files)} files")
            lines.append("[enter: view diff | q: back]")
        if width > 0:
            lines = [self._fit(line, width) for line in lines]
        if height is not None and len(lines) > height:
            lines = lines[: max(0, height - 1)] + ["↑/↓ scroll   q back"]
        return lines
