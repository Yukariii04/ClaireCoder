"""TUI presentation and input states."""
from enum import Enum, auto

class InputState(Enum):
    NORMAL = auto()
    STREAMING = auto()
    CONFIRMATION = auto()
    OVERLAY = auto()
    INTERRUPTED = auto()
    EXITING = auto()

class TerminalMode(Enum):
    FULL = auto()
    COMPACT = auto()
    MINIMAL = auto()
