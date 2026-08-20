"""File tree overlay conforming to CC-PRD-011, CC-ADR-007, and TUI-DESIGN.md §12.

Correction #10:
- Real workspace filesystem discovery replaces hard-coded demo data.
- Normalised FileTreeItem model (name, path, is_directory, children, status, expanded).
- Interactive navigation: expand/collapse, cursor selection, viewport scrolling.
- Selection marker: visible triangle '▶ ' for the active row.
- Directory expansion glyphs: '▾ ' when expanded, '├─ ' / '└─ ' when collapsed.
- Fixed internal viewport height with scrolling (outer TUI frame never grows).
- Visual footer communicating navigation keys.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Callable
from .states import TerminalMode

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FileTreeItem:
    """Normalised filesystem entry — no presentation strings stored."""
    name: str
    path: str
    is_directory: bool = False
    children: List["FileTreeItem"] = field(default_factory=list)
    status: str = ""  # 'M', '+', '' — reserved for git-status
    expanded: bool = False


# ---------------------------------------------------------------------------
# Workspace scanner
# ---------------------------------------------------------------------------

# Directories silently skipped during scanning
_IGNORED_DIRS = frozenset({
    "__pycache__", ".git", ".hg", ".svn", "node_modules",
    ".mypy_cache", ".pytest_cache", ".tox", ".eggs",
    "*.egg-info", "venv", ".venv", "env", ".env",
    ".clairecoder",
})

# Hard safety caps
_MAX_ENTRIES_PER_DIR = 200
_MAX_DEPTH = 8


def _should_ignore(name: str) -> bool:
    """Return True if *name* matches the ignore set."""
    lower = name.lower()
    if lower in _IGNORED_DIRS:
        return True
    if lower.endswith(".egg-info"):
        return True
    return False


def scan_workspace(root: Path, *, depth: int = 0) -> List[FileTreeItem]:
    """Recursively scan *root* and return a sorted list of ``FileTreeItem``.

    Ordering: directories first, then files — both alphabetical.
    Child directories default to ``expanded = False``.
    """
    if depth >= _MAX_DEPTH:
        return []

    try:
        entries = list(root.iterdir())
    except (PermissionError, OSError):
        return []

    dirs: List[FileTreeItem] = []
    files: List[FileTreeItem] = []

    # Sort entries alphabetically (case-insensitive)
    entries.sort(key=lambda p: p.name.lower())

    count = 0
    for entry in entries:
        if count >= _MAX_ENTRIES_PER_DIR:
            break
        if _should_ignore(entry.name):
            continue
        count += 1

        try:
            if entry.is_dir():
                children = scan_workspace(entry, depth=depth + 1)
                dirs.append(FileTreeItem(
                    name=entry.name,
                    path=str(entry),
                    is_directory=True,
                    children=children,
                    expanded=False,
                ))
            else:
                files.append(FileTreeItem(
                    name=entry.name,
                    path=str(entry),
                    is_directory=False,
                ))
        except (PermissionError, OSError):
            continue

    return dirs + files


# ---------------------------------------------------------------------------
# Flat display row
# ---------------------------------------------------------------------------

@dataclass
class _FlatRow:
    """One visible row in the flattened tree derived from expansion state."""
    item: FileTreeItem
    display: str
    status: str = ""
    is_directory: bool = False
    depth: int = 0
    parent_index: Optional[int] = None


# ---------------------------------------------------------------------------
# Overlay
# ---------------------------------------------------------------------------

class FileTreeOverlay:
    """Interactive File Tree overlay conforming to TUI-DESIGN.md §12.

    Maintains:
      - selected_index: 0-based index of the selected visible row
      - scroll_position: 0-based index of the top visible row
      - viewport_height: fixed number of visible content rows
      - expanded directories: visible rows dynamically derived from expansion state
    """

    def __init__(
        self,
        items: Optional[List[FileTreeItem]] = None,
        workspace_root: Optional[str] = None,
        viewport_height: int = 10,
    ) -> None:
        self._workspace_root = workspace_root
        self.viewport_height = max(4, viewport_height)
        self.selected_index: int = 0
        self.scroll_position: int = 0
        self.on_close: Optional[Callable[[], None]] = None

        self._root_item: Optional[FileTreeItem] = None
        if workspace_root is not None:
            root_name = Path(workspace_root).name or workspace_root
            self._root_item = FileTreeItem(
                name=root_name,
                path=workspace_root,
                is_directory=True,
                expanded=True,
            )

        if items is not None:
            self._tree = items
            if self._root_item:
                self._root_item.children = items
        elif workspace_root is not None:
            self._tree = self._scan(workspace_root)
            if self._root_item:
                self._root_item.children = self._tree
        else:
            self._tree = []

        self._flat: List[_FlatRow] = []
        self._flatten()

    # -- public helpers ------------------------------------------------------

    @property
    def items(self) -> List[_FlatRow]:
        """Flat display rows currently visible based on expansion state."""
        return self._flat

    @property
    def selected_item(self) -> Optional[FileTreeItem]:
        """Returns the currently selected FileTreeItem."""
        if self._flat and 0 <= self.selected_index < len(self._flat):
            return self._flat[self.selected_index].item
        return None

    def refresh(self) -> None:
        """Re-scan the workspace and rebuild the flat display list."""
        if self._workspace_root is not None:
            self._tree = self._scan(self._workspace_root)
            if self._root_item:
                self._root_item.children = self._tree
        self._flatten()

    # -- private -------------------------------------------------------------

    @staticmethod
    def _scan(root_path: str) -> List[FileTreeItem]:
        root = Path(root_path)
        if not root.is_dir():
            return []
        return scan_workspace(root)

    def _flatten(self) -> None:
        """Derive the visible flattened tree rows from the current expansion state."""
        self._flat = []
        if not self._tree:
            self.selected_index = 0
            self.scroll_position = 0
            return

        if self._root_item is not None:
            self._flat.append(_FlatRow(
                item=self._root_item,
                display=f"{self._root_item.name}/",
                status=self._root_item.status,
                is_directory=True,
                depth=0,
                parent_index=None,
            ))
            if self._root_item.expanded:
                self._walk_visible(self._tree, depth=1, prefix="  ", parent_idx=0)
        else:
            self._walk_visible(self._tree, depth=0, prefix="", parent_idx=None)

        self._ensure_visible()

    def _walk_visible(
        self,
        items: List[FileTreeItem],
        depth: int,
        prefix: str,
        parent_idx: Optional[int],
    ) -> None:
        """Recursively build flat rows for currently expanded items."""
        for i, item in enumerate(items):
            is_last = (i == len(items) - 1)
            connector = "└─ " if is_last else "├─ "

            if item.is_directory:
                if item.expanded:
                    display = f"{prefix}▾ {item.name}/"
                else:
                    display = f"{prefix}{connector}{item.name}/"
            else:
                display = f"{prefix}{connector}{item.name}"

            current_idx = len(self._flat)
            self._flat.append(_FlatRow(
                item=item,
                display=display,
                status=item.status,
                is_directory=item.is_directory,
                depth=depth,
                parent_index=parent_idx,
            ))

            if item.is_directory and item.expanded and item.children:
                child_prefix = prefix + ("   " if is_last else "│  ")
                self._walk_visible(
                    item.children,
                    depth=depth + 1,
                    prefix=child_prefix,
                    parent_idx=current_idx,
                )

    def _ensure_visible(self) -> None:
        """Clamp selected_index and scroll_position to valid visible bounds."""
        if not self._flat:
            self.selected_index = 0
            self.scroll_position = 0
            return

        self.selected_index = max(0, min(self.selected_index, len(self._flat) - 1))
        max_scroll = max(0, len(self._flat) - self.viewport_height)

        if self.selected_index < self.scroll_position:
            self.scroll_position = self.selected_index
        elif self.selected_index >= self.scroll_position + self.viewport_height:
            self.scroll_position = self.selected_index - self.viewport_height + 1

        self.scroll_position = max(0, min(self.scroll_position, max_scroll))

    # -- key handling --------------------------------------------------------

    def handle_key(self, key: str) -> bool:
        """Handles keyboard navigation within the File Tree overlay."""
        clean_key = key.strip().lower() if isinstance(key, str) else ""

        if key in ("\x1b", "Esc", "esc", "escape", "Escape") or clean_key in ("q", "back"):
            if self.on_close:
                self.on_close()
            return True

        if not self._flat:
            return False

        if clean_key in ("up", "k", "\x1b[a"):
            self.selected_index = max(0, self.selected_index - 1)
            self._ensure_visible()
            return True

        if clean_key in ("down", "j", "\x1b[b"):
            self.selected_index = min(len(self._flat) - 1, self.selected_index + 1)
            self._ensure_visible()
            return True

        if clean_key in ("pageup", "page_up", "pgup"):
            self.selected_index = max(0, self.selected_index - self.viewport_height)
            self._ensure_visible()
            return True

        if clean_key in ("pagedown", "page_down", "pgdn"):
            self.selected_index = min(len(self._flat) - 1, self.selected_index + self.viewport_height)
            self._ensure_visible()
            return True

        if clean_key == "home":
            self.selected_index = 0
            self._ensure_visible()
            return True

        if clean_key == "end":
            self.selected_index = max(0, len(self._flat) - 1)
            self._ensure_visible()
            return True

        if clean_key in ("enter", "return", " "):
            selected_row = self._flat[self.selected_index]
            if selected_row.item.is_directory:
                selected_row.item.expanded = not selected_row.item.expanded
                self._flatten()
            return True

        if clean_key in ("right", "l", "\x1b[c"):
            selected_row = self._flat[self.selected_index]
            if selected_row.item.is_directory:
                if not selected_row.item.expanded:
                    selected_row.item.expanded = True
                    self._flatten()
                elif selected_row.item.children and self.selected_index + 1 < len(self._flat):
                    self.selected_index += 1
                    self._ensure_visible()
            return True

        if clean_key in ("left", "h", "\x1b[d"):
            selected_row = self._flat[self.selected_index]
            if selected_row.item.is_directory and selected_row.item.expanded:
                selected_row.item.expanded = False
                self._flatten()
            elif selected_row.parent_index is not None:
                self.selected_index = selected_row.parent_index
                self._ensure_visible()
            return True

        return False

    # -- rendering -----------------------------------------------------------

    def render(self, mode: TerminalMode = TerminalMode.FULL, width: int = 58) -> List[str]:
        """Renders the fixed-height file tree overlay card."""
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

        if not self._flat:
            lines.append(frame_line("(no files discovered)"))
            for _ in range(self.viewport_height - 1):
                lines.append(frame_line(""))
        else:
            visible_rows = self._flat[self.scroll_position : self.scroll_position + self.viewport_height]
            for offset, row in enumerate(visible_rows):
                actual_idx = self.scroll_position + offset
                marker = "▶ " if actual_idx == self.selected_index else "  "
                line_content = f"{marker}{row.display}"
                if row.status:
                    pad = max(2, inner_w - len(line_content) - len(row.status) - 2)
                    row_str = f"{line_content}{' ' * pad}{row.status}"
                else:
                    row_str = line_content
                lines.append(frame_line(row_str))

            for _ in range(self.viewport_height - len(visible_rows)):
                lines.append(frame_line(""))

        lines.append(frame_line(""))
        lines.append(frame_line("↑/↓ select  Enter expand/collapse  ←/→ tree"))
        lines.append(frame_line("PgUp/PgDn scroll   Esc back"))
        lines.append("╰" + ("─" * (card_w - 2)) + "╯")

        return lines
