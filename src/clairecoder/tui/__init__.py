"""ClaireCoder TUI foundation."""
from .app import TuiApplication
from .states import InputState, TerminalMode
from .terminal import TerminalCapability, TerminalRenderer, TerminalInput, InputDecoder, KeyEvent
from .activity import ActivityModel, ActivityState, ActivityType, DiffInfo, DiffLine
from .permission import PermissionSurface, PermissionDecision, PermissionRequestViewModel
from .diff import FileDiff, DiffRenderer
from .review import ReviewOverlay
from .palette import CommandPalette, PaletteCommandItem
from .loading import LoadingScreen
from .header import HeaderStatus, StatusModel
from .prompt import PromptInput
from .transcript import TranscriptView
from .tree import FileTreeOverlay, FileTreeItem, scan_workspace
from .task import TaskViewOverlay
from .renderer import ActivityRenderer
from .canvas import Canvas, VisualNode, visible_length, visible_slice

__all__ = [
    "TuiApplication",
    "InputState",
    "TerminalMode",
    "TerminalCapability",
    "TerminalRenderer",
    "TerminalInput",
    "InputDecoder",
    "KeyEvent",
    "ActivityModel",
    "ActivityState",
    "ActivityType",
    "DiffInfo",
    "DiffLine",
    "PermissionSurface",
    "PermissionDecision",
    "PermissionRequestViewModel",
    "FileDiff",
    "DiffRenderer",
    "ReviewOverlay",
    "CommandPalette",
    "PaletteCommandItem",
    "LoadingScreen",
    "HeaderStatus",
    "StatusModel",
    "PromptInput",
    "TranscriptView",
    "FileTreeOverlay",
    "FileTreeItem",
    "scan_workspace",
    "TaskViewOverlay",
    "ActivityRenderer",
    "Canvas",
    "VisualNode",
    "visible_length",
    "visible_slice",
]
