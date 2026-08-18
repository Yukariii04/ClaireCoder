"""Spatial canvas and layout composition engine for ClaireCoder TUI."""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

def visible_length(s: str) -> int:
    """Returns visible character length ignoring ANSI escape codes."""
    return len(ANSI_ESCAPE.sub("", s))

def visible_slice(s: str, start: int, max_width: int) -> str:
    """Slices a string by visible character length, preserving ANSI escapes."""
    if not ANSI_ESCAPE.search(s):
        return s[start:start + max_width]

    result = []
    vis_count = 0
    in_range = False
    tokens = re.split(r"(\x1b\[[0-9;]*[a-zA-Z])", s)

    for token in tokens:
        if not token:
            continue
        if ANSI_ESCAPE.match(token):
            result.append(token)
        else:
            token_len = len(token)
            if vis_count + token_len <= start:
                vis_count += token_len
                continue

            # Overlaps start
            char_start = max(0, start - vis_count)
            char_end = min(token_len, char_start + (max_width - len("".join([t for t in result if not ANSI_ESCAPE.match(t)]))))
            sliced = token[char_start:char_end]
            result.append(sliced)
            vis_count += token_len
            if len("".join([t for t in result if not ANSI_ESCAPE.match(t)])) >= max_width:
                break

    return "".join(result)


@dataclass
class VisualNode:
    """A spatial render node representing a visual region."""
    x: int
    y: int
    width: int
    height: int
    lines: List[str] = field(default_factory=list)
    z_index: int = 0
    transparent: bool = True


class Canvas:
    """2D Spatial Compositor for terminal frames conforming to Section 20-22."""

    def __init__(self, width: int, height: int, bg_char: str = " ") -> None:
        self.width = width
        self.height = height
        self.bg_char = bg_char
        self.nodes: List[VisualNode] = []

    def place(
        self,
        node_or_lines: "VisualNode | List[str] | str",
        x: int = 0,
        y: int = 0,
        width: Optional[int] = None,
        height: Optional[int] = None,
        z_index: int = 0,
        transparent: bool = True
    ) -> VisualNode:
        """Places a node or list of lines onto the canvas."""
        if isinstance(node_or_lines, VisualNode):
            node = node_or_lines
            if x != node.x or y != node.y:
                node.x = x
                node.y = y
            if z_index != node.z_index:
                node.z_index = z_index
        else:
            if isinstance(node_or_lines, str):
                lines = node_or_lines.splitlines()
            else:
                lines = list(node_or_lines)
            
            calc_w = width if width is not None else max((visible_length(l) for l in lines), default=0)
            calc_h = height if height is not None else len(lines)
            node = VisualNode(
                x=x,
                y=y,
                width=calc_w,
                height=calc_h,
                lines=lines,
                z_index=z_index,
                transparent=transparent
            )
        self.nodes.append(node)
        return node

    def render(self) -> List[str]:
        """Composites all nodes onto the canvas and returns final terminal rows."""
        # Sort nodes by z_index
        sorted_nodes = sorted(self.nodes, key=lambda n: n.z_index)

        # Initialize canvas grid: list of list of (char_or_ansi_string)
        # To handle ANSI and characters properly, each row is built spatially
        output_rows: List[str] = []

        for row_y in range(self.height):
            # Collect row fragments from nodes covering row_y
            row_fragments: List[Tuple[int, int, str, int]] = []  # (x, width, content, z_index)

            for node in sorted_nodes:
                if node.y <= row_y < node.y + node.height:
                    line_idx = row_y - node.y
                    if line_idx < len(node.lines):
                        content = node.lines[line_idx]
                        vis_w = visible_length(content)
                        row_fragments.append((node.x, vis_w, content, node.z_index))

            if not row_fragments:
                output_rows.append(self.bg_char * self.width)
                continue

            # Composite the line fragments
            # We build the line from left to right
            # If multiple fragments overlap, the higher z_index wins
            row_str = self._composite_line(row_fragments, self.width)
            output_rows.append(row_str)

        return output_rows

    def _composite_line(self, fragments: List[Tuple[int, int, str, int]], total_width: int) -> str:
        """Composites multiple horizontal fragments for a single row."""
        # Sort fragments by z_index ascending
        frags = sorted(fragments, key=lambda f: f[3])

        # If only one fragment and it starts at 0, fast path
        if len(frags) == 1:
            x, w, content, _ = frags[0]
            left_pad = " " * max(0, x)
            vis_w = visible_length(content)
            right_pad = " " * max(0, total_width - (x + vis_w))
            return (left_pad + content + right_pad)[:total_width * 5]  # allow ANSI escapes

        # Multiple fragments: merge left to right
        # For terminal display, we can slice and join non-overlapping regions
        # e.g., Left content and Right content
        frags_by_x = sorted(frags, key=lambda f: f[0])
        line_parts: List[str] = []
        curr_x = 0

        for x, w, content, z in frags_by_x:
            if x > curr_x:
                line_parts.append(" " * (x - curr_x))
                curr_x = x
            line_parts.append(content)
            curr_x = x + visible_length(content)

        if curr_x < total_width:
            line_parts.append(" " * (total_width - curr_x))

        return "".join(line_parts)
