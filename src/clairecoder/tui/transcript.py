"""Transcript and scrollback presentation layer."""
from typing import List, Dict, Optional
from .activity import ActivityModel, ActivityState
from .renderer import ActivityRenderer

class TranscriptView:
    """Bounded transcript abstraction suitable for long-running agent sessions."""
    
    def __init__(self) -> None:
        self.activities: List[ActivityModel] = []
        self._activity_map: Dict[str, ActivityModel] = {}
        self._correlation_map: Dict[str, ActivityModel] = {}
        self.scroll_position: int = 0
        self.height: int = 10
        self.render_width: int = 68  # Updated by TUI on resize
        self._follow_tail: bool = True
        self._next_order: int = 0

    def get_activities(self) -> List[ActivityModel]:
        """Returns list of activities in transcript."""
        return list(self.activities)

    def _max_scroll(self) -> int:
        """Returns the maximum scroll position for current activities and height."""
        total = len(self._get_rendered_lines())
        return max(0, total - self.height)
        
    def append_activity(self, activity: ActivityModel) -> None:
        """Appends a new activity to the transcript."""
        activity.order_index = self._next_order
        self._next_order += 1
        self.activities.append(activity)
        self._activity_map[activity.id] = activity
        if activity.correlation_key:
            self._correlation_map[activity.correlation_key] = activity
        if self._follow_tail:
            self.scroll_to_bottom()
        else:
            self.scroll_position = min(self.scroll_position, self._max_scroll())
        
    def update_activity(self, updated_activity: ActivityModel) -> None:
        """Update an existing activity in place to support streaming using correlation_key."""
        existing = None
        if updated_activity.correlation_key and updated_activity.correlation_key in self._correlation_map:
            existing = self._correlation_map[updated_activity.correlation_key]
        elif updated_activity.id in self._activity_map:
            existing = self._activity_map[updated_activity.id]
            
        if existing:
            existing.type = updated_activity.type
            existing.state = updated_activity.state
            existing.title = updated_activity.title
            existing.detail = updated_activity.detail
            existing.expandable_content = updated_activity.expandable_content
            existing.diff_info = updated_activity.diff_info
            existing.expanded = updated_activity.expanded
            existing.metadata = updated_activity.metadata
            if self._follow_tail:
                self.scroll_to_bottom()
            else:
                self.scroll_position = min(self.scroll_position, self._max_scroll())
        else:
            self.append_activity(updated_activity)

    def complete_activity(self, activity_id: str, detail: Optional[str] = None) -> None:
        """Marks an activity as completed."""
        if activity_id in self._activity_map:
            act = self._activity_map[activity_id]
            act.state = ActivityState.COMPLETED
            if detail:
                act.detail = detail
            if self._follow_tail:
                self.scroll_to_bottom()
            else:
                self.scroll_position = min(self.scroll_position, self._max_scroll())

    def fail_activity(self, activity_id: str, detail: Optional[str] = None) -> None:
        """Marks an activity as failed."""
        if activity_id in self._activity_map:
            act = self._activity_map[activity_id]
            act.state = ActivityState.FAILED
            if detail:
                act.detail = detail
            if self._follow_tail:
                self.scroll_to_bottom()
            else:
                self.scroll_position = min(self.scroll_position, self._max_scroll())

    def toggle_expand(self, activity_id: str) -> None:
        """Toggles the expanded state of an activity."""
        if activity_id in self._activity_map:
            act = self._activity_map[activity_id]
            act.expanded = not act.expanded
            if self._follow_tail:
                self.scroll_to_bottom()
            else:
                self.scroll_position = min(self.scroll_position, self._max_scroll())
            
    def _get_rendered_lines(self) -> List[str]:
        lines = []
        for act in self.activities:
            lines.extend(ActivityRenderer.render(act, width=self.render_width))
        return lines
        
    def get_visible_lines(self, padded: bool = False) -> List[str]:
        """Returns the lines currently visible based on scroll position and viewport height."""
        lines = self._get_rendered_lines()
        start = self.scroll_position
        end = start + self.height
        visible = lines[start:end]
        if padded:
            while len(visible) < self.height:
                visible.append("")
        return visible

    def scroll_to_bottom(self) -> None:
        """Scrolls to the end of the transcript and engages follow-tail."""
        self.scroll_position = self._max_scroll()
        self._follow_tail = True
            
    def scroll_to_top(self) -> None:
        """Scrolls to the beginning of the transcript."""
        self.scroll_position = 0
        if self._max_scroll() > 0:
            self._follow_tail = False
        else:
            self._follow_tail = True

    def is_at_bottom(self) -> bool:
        """Returns True if the transcript view is scrolled to the bottom / follow-tail is active."""
        return self._follow_tail or self.scroll_position >= self._max_scroll()

    def scroll_up(self, amount: int = 1) -> None:
        """Scrolls up by amount, disengaging follow-tail if scrolled away from bottom."""
        self._follow_tail = False
        self.scroll_position = max(0, self.scroll_position - amount)
        
    def scroll_down(self, amount: int = 1) -> None:
        """Scrolls down by amount, re-engaging follow-tail if reaching bottom."""
        max_scroll = self._max_scroll()
        self.scroll_position = min(max_scroll, self.scroll_position + amount)
        if self.scroll_position >= max_scroll:
            self._follow_tail = True

    def page_up(self) -> None:
        """Scrolls up by one page (viewport height)."""
        self.scroll_up(max(1, self.height - 1))

    def page_down(self) -> None:
        """Scrolls down by one page (viewport height)."""
        self.scroll_down(max(1, self.height - 1))

    def resize(self, height: int) -> None:
        """Handles viewport resize."""
        self.height = max(1, height)
        if self._follow_tail:
            self.scroll_to_bottom()
        else:
            self.scroll_position = min(self.scroll_position, self._max_scroll())
