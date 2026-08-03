from dataclasses import dataclass, field
from typing import Any, Dict
from datetime import datetime, timezone

@dataclass
class Event:
    name: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
