"""Central EventEmitter for the runtime event protocol.

Correction #12 — Standalone pub/sub emitter decoupled from Engine.

Architecture:
    Agent / Engine
          |
          | emit()
          v
     EventEmitter
          |
          +---------> TUI
          |
          +---------> Logger
          |
          +---------> Future Recorder

Design decisions:
- Thread-safe via a copied listener list on emit (listeners may be modified
  during emission — e.g. unsubscribe within a callback).
- Errors in individual listeners are caught so one bad listener doesn't
  break the entire event stream.
- subscribe() returns a callable for convenient unsubscription.
"""

import logging
from typing import Callable, List

from .events import RuntimeEvent

logger = logging.getLogger(__name__)

# Type alias for event listener callbacks
EventListener = Callable[[RuntimeEvent], None]


class EventEmitter:
    """Central pub/sub hub for RuntimeEvent distribution."""

    def __init__(self) -> None:
        self._listeners: List[EventListener] = []

    def emit(self, event: RuntimeEvent) -> None:
        """Emit an event to all registered listeners.

        Errors in individual listeners are logged but do not propagate.
        """
        # Snapshot listener list to allow subscribe/unsubscribe during emit
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                logger.exception("Error in RuntimeEvent listener %r", listener)

    def subscribe(self, listener: EventListener) -> Callable[[], None]:
        """Register a listener. Returns an unsubscribe callable."""
        if listener not in self._listeners:
            self._listeners.append(listener)

        def _unsub() -> None:
            self.unsubscribe(listener)

        return _unsub

    def unsubscribe(self, listener: EventListener) -> None:
        """Remove a previously registered listener."""
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass  # Already removed — idempotent

    @property
    def listener_count(self) -> int:
        """Number of currently registered listeners."""
        return len(self._listeners)
