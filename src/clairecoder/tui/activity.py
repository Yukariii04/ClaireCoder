"""Presentation activity model for the TUI transcript (Correction #20).

Provides:
- Structured ActivityEvent model (status, operation, target, details, additions, deletions)
- Compact ChangeSet execution summaries (file count, additions, deletions, per-file diffs)
- ActivityModel backwards-compatible presentation object
- Clean visual markers: ● (running), ✓ (completed), ✗ (failed)
"""

from enum import Enum, auto
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
import uuid
import time


# =============================================================================
# ENUMS
# =============================================================================

class ActivityType(Enum):
    MESSAGE = auto()
    READING = auto()
    EDITING = auto()
    TOOL = auto()
    TEST = auto()
    VERIFICATION = auto()
    PERMISSION = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()
    THINKING = auto()


class ActivityState(Enum):
    RUNNING = auto()
    COMPLETED = auto()
    APPROVAL_REQUIRED = auto()
    FAILED = auto()
    BLOCKED = auto()


class ActivityStatus(str, Enum):
    """Lifecycle status for an activity item."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ActivityOperation(str, Enum):
    """Semantic operation performed by the agent or tool."""
    READING = "reading"
    EDITING = "editing"
    CREATING = "creating"
    DELETING = "deleting"
    RUNNING = "running"
    VERIFYING = "verifying"
    PLANNING = "planning"
    MESSAGE = "message"


# =============================================================================
# PATH UTILITIES
# =============================================================================

def truncate_path(path: str, max_len: int = 36) -> str:
    """Safely truncate a file path keeping root context and filename."""
    if not path or len(path) <= max_len:
        return path or ""
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if len(parts) <= 2:
        return path[:max_len - 3] + "..." if len(path) > max_len else path

    first = parts[0]
    last = parts[-1]
    candidate = f"{first}/.../{last}"
    if len(candidate) <= max_len:
        return candidate
    return f".../{last}"[:max_len]


# =============================================================================
# DIFF & CHANGE SUMMARY MODELS
# =============================================================================

@dataclass
class DiffLine:
    type: str  # 'add', 'remove', 'context'
    content: str


@dataclass
class DiffInfo:
    summary: str
    lines: List[DiffLine] = field(default_factory=list)


@dataclass
class ChangeSummaryItem:
    """Individual file mutation summary."""
    path: str
    additions: int = 0
    deletions: int = 0
    status: str = "modified"  # modified, created, deleted


@dataclass
class ExecutionChangeSummary:
    """Compact aggregate summary of ChangeSet mutations."""
    file_count: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    files: List[ChangeSummaryItem] = field(default_factory=list)

    def format_summary(self, width: int = 68) -> List[str]:
        """Format compact change summary according to reference UX.

        Example:
        3 files changed  +84  -21   Review
        src/engine.py        +32 -11
        tests/test_engine.py +52
        """
        count = self.file_count or len(self.files)
        f_word = "file" if count == 1 else "files"
        header = f"{count} {f_word} changed  +{self.total_additions}  -{self.total_deletions}   Review"
        lines = [header]

        if self.files:
            max_p_len = min(36, max(len(f.path) for f in self.files))
            for f in self.files:
                p = truncate_path(f.path, max_len=36)
                diff_parts = []
                if f.additions > 0:
                    diff_parts.append(f"+{f.additions}")
                if f.deletions > 0:
                    diff_parts.append(f"-{f.deletions}")
                diff_str = " ".join(diff_parts) if diff_parts else "0"
                lines.append(f"{p.ljust(max_p_len + 4)}{diff_str}")

        return lines


# =============================================================================
# ACTIVITY EVENT MODEL (Section 1)
# =============================================================================

@dataclass
class ActivityEvent:
    """TUI-facing structured activity representation derived from RuntimeEvents / ToolEvents."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ActivityStatus = ActivityStatus.RUNNING
    operation: ActivityOperation = ActivityOperation.RUNNING
    target: str = ""
    details: Optional[str] = None
    file_path: Optional[str] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None
    duration: Optional[float] = None
    correlation_key: Optional[str] = None
    change_summary: Optional[ExecutionChangeSummary] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_running(self) -> bool:
        return self.status == ActivityStatus.RUNNING

    @property
    def is_completed(self) -> bool:
        return self.status == ActivityStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == ActivityStatus.FAILED

    def render_lines(self, width: int = 68) -> List[str]:
        """Render activity into display lines matching reference UX."""
        if self.change_summary is not None:
            return self.change_summary.format_summary(width=width)

        # Status marker:
        if self.status == ActivityStatus.RUNNING:
            marker = "●"
        elif self.status == ActivityStatus.COMPLETED:
            marker = "✓"
        else:
            marker = "✗"

        op = self.operation
        tgt = truncate_path(self.target, max_len=min(45, width - 15)) if self.file_path else self.target

        # Operation title formatting
        if op == ActivityOperation.READING:
            if self.status == ActivityStatus.RUNNING:
                header = f"{marker} Reading {tgt}"
            elif self.status == ActivityStatus.COMPLETED:
                if self.details and ("line" in self.details.lower() or "read " in self.details.lower()):
                    det = self.details if self.details.lower().startswith("read ") else f"Read {self.details}"
                    header = f"{marker} {det}"
                else:
                    header = f"{marker} Read {tgt}"
            else:
                header = f"{marker} Reading {tgt}"

        elif op == ActivityOperation.EDITING:
            header = f"{marker} Editing {tgt}"

        elif op == ActivityOperation.CREATING:
            header = f"{marker} Creating {tgt}"

        elif op == ActivityOperation.DELETING:
            if self.status == ActivityStatus.COMPLETED:
                header = f"{marker} Deleted {tgt}"
            else:
                header = f"{marker} Deleting {tgt}"

        elif op == ActivityOperation.RUNNING:
            header = f"{marker} Running {tgt}"

        elif op == ActivityOperation.VERIFYING:
            if self.status == ActivityStatus.RUNNING:
                header = f"{marker} Verification running"
            elif self.status == ActivityStatus.COMPLETED:
                header = f"{marker} Verification passed"
            else:
                header = f"{marker} Verification failed"

        elif op == ActivityOperation.PLANNING:
            if self.status == ActivityStatus.RUNNING:
                header = f"{marker} Planning changes"
            elif self.status == ActivityStatus.COMPLETED:
                header = f"{marker} Plan ready"
            else:
                header = f"{marker} Planning failed"

        else:
            header = f"{marker} {tgt or 'Activity'}"

        lines = [header]

        # Additions / Deletions line
        if self.additions is not None or self.deletions is not None:
            parts = []
            if self.additions is not None and self.additions > 0:
                parts.append(f"+{self.additions}")
            if self.deletions is not None and self.deletions > 0:
                parts.append(f"-{self.deletions}")
            if parts:
                lines.append(f"  {' '.join(parts)}")

        # Details / sub-lines
        if self.details:
            # Skip if details was already inlined in the header line
            if not (op == ActivityOperation.READING and self.status == ActivityStatus.COMPLETED and self.details in header):
                for line in str(self.details).splitlines():
                    if line.strip():
                        lines.append(f"  {line.strip()}")

        return lines

    def to_activity_model(self) -> "ActivityModel":
        """Convert this ActivityEvent into an ActivityModel for TUI compatibility."""
        if self.status == ActivityStatus.RUNNING:
            st = ActivityState.RUNNING
        elif self.status == ActivityStatus.COMPLETED:
            st = ActivityState.COMPLETED
        else:
            st = ActivityState.FAILED

        op_to_type = {
            ActivityOperation.READING: ActivityType.READING,
            ActivityOperation.EDITING: ActivityType.EDITING,
            ActivityOperation.CREATING: ActivityType.EDITING,
            ActivityOperation.DELETING: ActivityType.TOOL,
            ActivityOperation.RUNNING: ActivityType.TOOL,
            ActivityOperation.VERIFYING: ActivityType.VERIFICATION,
            ActivityOperation.PLANNING: ActivityType.THINKING,
            ActivityOperation.MESSAGE: ActivityType.MESSAGE,
        }
        act_type = op_to_type.get(self.operation, ActivityType.TOOL)

        rendered = self.render_lines()
        title = rendered[0] if rendered else ""
        detail = "\n".join(rendered[1:]) if len(rendered) > 1 else None

        return ActivityModel(
            id=self.id,
            type=act_type,
            state=st,
            title=title,
            detail=detail,
            correlation_key=self.correlation_key,
            updates_activity=(self.status != ActivityStatus.RUNNING),
            timestamp=self.timestamp,
            metadata=self.metadata,
            activity_event=self,
            additions=self.additions,
            deletions=self.deletions,
            change_summary=self.change_summary,
        )


# =============================================================================
# ACTIVITY MODEL (Legacy / Transcript integration)
# =============================================================================

@dataclass
class ActivityModel:
    """Presentation activity model for the TUI transcript."""
    type: ActivityType = ActivityType.MESSAGE
    state: ActivityState = ActivityState.RUNNING
    title: str = ""
    detail: Optional[str] = None
    expandable_content: Optional[str] = None
    diff_info: Optional[DiffInfo] = None
    correlation_key: Optional[str] = None
    updates_activity: bool = False
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    expanded: bool = False
    order_index: int = 0

    # Correction #20: ActivityEvent & ChangeSet presentation bridges
    activity_event: Optional[ActivityEvent] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None
    change_summary: Optional[ExecutionChangeSummary] = None

    @property
    def starts_new_activity(self) -> bool:
        return not self.updates_activity
