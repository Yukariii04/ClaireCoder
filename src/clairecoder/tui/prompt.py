"""Prompt and input handling with cursor-aware viewport and glass visual styling."""
from typing import Callable, Optional, List
from .states import TerminalMode
from .canvas import visible_length, visible_slice


class PromptInput:
    """Persistent prompt/input area abstraction with cursor-aware horizontal viewport."""
    
    def __init__(self) -> None:
        self.content: str = ""
        self.cursor_pos: int = 0
        self.on_submit: Optional[Callable[[str], None]] = None
        self.on_escape: Optional[Callable[[], None]] = None
        self.suspended: bool = False
        
    def get_text(self) -> str:
        """Gets current text content."""
        return self.content

    def set_text(self, text: str) -> None:
        """Sets the content of the prompt."""
        self.content = text
        self.cursor_pos = len(text)

    def clear(self) -> None:
        """Clears the prompt content."""
        self.content = ""
        self.cursor_pos = 0

    def type_text(self, text: str) -> None:
        """Simulate user typing text."""
        if self.suspended:
            return
        self.content = self.content[:self.cursor_pos] + text + self.content[self.cursor_pos:]
        self.cursor_pos += len(text)

    def insert_char(self, ch: str) -> None:
        """Inserts a single character at cursor."""
        self.type_text(ch)

    def backspace(self) -> None:
        """Removes the character before the cursor."""
        if self.suspended:
            return
        if self.cursor_pos > 0:
            self.content = self.content[:self.cursor_pos - 1] + self.content[self.cursor_pos:]
            self.cursor_pos -= 1

    def delete_char(self) -> None:
        """Removes the character at current cursor position (Delete key)."""
        if self.suspended:
            return
        if self.cursor_pos < len(self.content):
            self.content = self.content[:self.cursor_pos] + self.content[self.cursor_pos + 1:]

    def move_cursor_left(self, n: int = 1) -> None:
        """Move cursor left by n positions."""
        self.cursor_pos = max(0, self.cursor_pos - n)

    def move_cursor_right(self, n: int = 1) -> None:
        """Move cursor right by n positions."""
        self.cursor_pos = min(len(self.content), self.cursor_pos + n)

    def move_cursor_home(self) -> None:
        """Move cursor to beginning of prompt."""
        self.cursor_pos = 0

    def move_cursor_end(self) -> None:
        """Move cursor to end of prompt."""
        self.cursor_pos = len(self.content)

    def handle_enter(self) -> None:
        """Submit the prompt."""
        if self.suspended:
            return
        if self.on_submit and self.content.strip():
            submitted = self.content.strip()
            self.content = ""
            self.cursor_pos = 0
            self.on_submit(submitted)
            
    def handle_escape(self) -> None:
        """UI-level cancellation."""
        if self.on_escape:
            self.on_escape()
            
    def suspend(self) -> None:
        """Suspends the prompt (e.g. during an overlay or confirmation)."""
        self.suspended = True
        
    def resume(self) -> None:
        """Resumes the prompt."""
        self.suspended = False

    def render_line(self, available_width: int = 80, focused: bool = True) -> str:
        """Render prompt text within available width using a cursor-following horizontal viewport."""
        prefix = "> "
        prefix_len = visible_length(prefix)
        cursor_glyph = "█" if (not self.suspended and focused) else ""

        # Available space for text + cursor
        avail_text_w = max(5, available_width - prefix_len - 1)
        total_len = len(self.content)

        if total_len <= avail_text_w:
            # Entire text fits: place cursor at cursor_pos
            before_cursor = self.content[:self.cursor_pos]
            after_cursor = self.content[self.cursor_pos:]
            return f"{prefix}{before_cursor}{cursor_glyph}{after_cursor}"

        # Text exceeds available width: compute cursor-following sliding window
        # Ensure cursor_pos is within [view_start, view_start + avail_text_w]
        view_start = max(0, min(self.cursor_pos - avail_text_w + 3, total_len - avail_text_w))
        view_end = view_start + avail_text_w
        visible_slice_text = self.content[view_start:view_end]
        rel_cursor_pos = max(0, min(self.cursor_pos - view_start, len(visible_slice_text)))

        before_cursor = visible_slice_text[:rel_cursor_pos]
        after_cursor = visible_slice_text[rel_cursor_pos:]
        return f"{prefix}{before_cursor}{cursor_glyph}{after_cursor}"

    def render(self, mode: TerminalMode = TerminalMode.FULL, width: int = 80,
               focused: bool = True, use_color: bool = False) -> List[str]:
        """Renders the prompt line for COMPACT or MINIMAL modes."""
        return [self.render_line(available_width=width, focused=focused)]
