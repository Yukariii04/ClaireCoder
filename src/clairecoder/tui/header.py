"""Header and status presentation layer conforming to TUI-DESIGN.md."""
from dataclasses import dataclass
from typing import Optional

@dataclass
class StatusModel:
    directory: str = ""
    model_name: str = ""
    mode_name: str = ""
    session_id: str = ""
    task_info: str = ""
    context_usage: str = ""

class HeaderStatus:
    """Renders the persistent status/header area conforming to TUI-DESIGN.md §4, §5."""
    
    def __init__(self) -> None:
        self._model = StatusModel()
        
    @property
    def status_model(self) -> StatusModel:
        return self._model

    @status_model.setter
    def status_model(self, model: StatusModel) -> None:
        self._model = model

    @property
    def directory(self) -> str:
        return self._model.directory

    @directory.setter
    def directory(self, val: str) -> None:
        self._model.directory = val

    @property
    def model(self) -> str:
        return self._model.model_name

    @model.setter
    def model(self, val: str) -> None:
        self._model.model_name = val

    @property
    def mode(self) -> str:
        return self._model.mode_name

    @mode.setter
    def mode(self, val: str) -> None:
        self._model.mode_name = val

    @property
    def session_id(self) -> str:
        return self._model.session_id

    @session_id.setter
    def session_id(self, val: str) -> None:
        self._model.session_id = val

    @property
    def task_progress(self) -> str:
        return self._model.task_info

    @task_progress.setter
    def task_progress(self, val: str) -> None:
        self._model.task_info = val

    @property
    def context_usage(self) -> str:
        return self._model.context_usage

    @context_usage.setter
    def context_usage(self, val: str) -> None:
        self._model.context_usage = val

    def update(self, model: StatusModel) -> None:
        """Update the presentation model."""
        self._model = model
        
    def render(self, width: int = 80) -> str:
        """Returns header representation."""
        if not (self._model.directory or self._model.model_name or self._model.mode_name or self._model.session_id):
            return ""
            
        if width >= 70:
            top_border = f"╭─ ClaireCoder " + ("─" * max(0, width - 26)) + " ● v0.1.0 ─╮"
            line1 = f"│ dir: {self._model.directory}   model: {self._model.model_name}   mode: {self._model.mode_name}   session: {self._model.session_id}".ljust(width - 1) + "│"
            line2 = f"│ task: {self._model.task_info}   context: {self._model.context_usage}".ljust(width - 1) + "│"
            div = "├" + ("─" * (width - 2)) + "┤"
            return f"{top_border}\n{line1}\n{line2}\n{div}"
            
        return (f"dir: {self._model.directory} | model: {self._model.model_name} | "
                f"mode: {self._model.mode_name} | session: {self._model.session_id} | "
                f"task: {self._model.task_info} | context: {self._model.context_usage}")
