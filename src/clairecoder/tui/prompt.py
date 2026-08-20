"""Prompt and input handling with glass visual styling."""
from typing import Callable, Optional, List
from .states import TerminalMode

class PromptInput:
    """Persistent prompt/input area abstraction with glass/translucent visual styling."""
    
    def __init__(self) -> None:
        self.content = ""
        self.cursor_pos = 0
        self.on_submit: Optional[Callable[[str], None]] = None
        self.on_escape: Optional[Callable[[], None]] = None
        self.suspended = False
        
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
        """Inserts a single character."""
        self.type_text(ch)

    def backspace(self) -> None:
        """Removes the character before the cursor."""
        if self.suspended:
            return
        if self.cursor_pos > 0:
            self.content = self.content[:self.cursor_pos - 1] + self.content[self.cursor_pos:]
            self.cursor_pos -= 1

    def handle_enter(self) -> None:
        """Submit the prompt."""
        if self.suspended:
            return
        if self.on_submit and self.content.strip():
            self.on_submit(self.content.strip())
            self.content = ""
            self.cursor_pos = 0
            
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

    def render(self, mode: TerminalMode = TerminalMode.FULL, width: int = 80,
               focused: bool = True, use_color: bool = False) -> List[str]:
        """Renders the prompt line with cursor and glass treatment."""
        cursor = "█" if (not self.suspended and focused) else ""
        if mode == TerminalMode.MINIMAL:
            return [f"> {self.content}"]
        
        # Compact and Full modes: cyan-accented glass prompt
        prefix = "> "
        if use_color:
            # Subtle cyan accent for prefix and focused prompt
            return [f"\x1b[36m{prefix}\x1b[0m{self.content}{cursor}"]
        return [f"{prefix}{self.content}{cursor}"]
