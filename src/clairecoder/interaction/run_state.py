"""Authoritative agent run state machine.

Provides a single RunState enum and AgentRun class that owns the
lifecycle of any execution (conversation or engineering).

Per §8 — exactly one authoritative owner of run state.
Per §9 — failure is terminal unless explicitly recovered.
Per §11 — cancellation reaches actual execution boundary.
"""

from enum import Enum
from typing import Optional, Callable
import threading


class RunState(str, Enum):
    """Authoritative lifecycle states for an agent run."""
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


# Terminal states — no new work may be started after entering these.
_TERMINAL_STATES = frozenset({
    RunState.COMPLETED,
    RunState.FAILED,
    RunState.CANCELLED,
    RunState.INTERRUPTED,
})


class AgentRun:
    """Single authoritative owner of execution lifecycle.

    Tracks:
      - current RunState
      - attempt number (for bounded recovery)
      - cancellation flag checked by tools/model calls
      - optional failure reason

    After any terminal state, no new planner call, no new task,
    no new tool, no replan, no verification, no new model request
    may be started.
    """

    MAX_ATTEMPTS = 3  # Hard bound on recovery attempts

    def __init__(self, run_id: str, on_state_change: Optional[Callable] = None):
        self.run_id = run_id
        self._state = RunState.IDLE
        self._lock = threading.Lock()
        self._cancelled = threading.Event()
        self.attempt_number: int = 0
        self.failure_reason: Optional[str] = None
        self._on_state_change = on_state_change

    @property
    def state(self) -> RunState:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in _TERMINAL_STATES

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def can_start_work(self) -> bool:
        """Returns True only if new work (tool/model/plan) is permitted."""
        return self._state == RunState.RUNNING and not self._cancelled.is_set()

    def start(self) -> None:
        """Transition from IDLE → RUNNING.  Increments attempt counter."""
        with self._lock:
            if self._state not in (RunState.IDLE, RunState.FAILED):
                raise RuntimeError(
                    f"Cannot start run from state {self._state.value}"
                )
            if self.attempt_number >= self.MAX_ATTEMPTS:
                self._transition(RunState.FAILED)
                self.failure_reason = f"Max attempts ({self.MAX_ATTEMPTS}) exceeded"
                return
            self.attempt_number += 1
            self._cancelled.clear()
            self._transition(RunState.RUNNING)

    def complete(self) -> None:
        """Transition → COMPLETED (terminal)."""
        with self._lock:
            if self._state in _TERMINAL_STATES:
                return  # Already terminal — idempotent
            self._transition(RunState.COMPLETED)

    def fail(self, reason: Optional[str] = None) -> None:
        """Transition → FAILED (terminal unless explicitly recovered)."""
        with self._lock:
            if self._state in _TERMINAL_STATES:
                return
            self.failure_reason = reason
            self._transition(RunState.FAILED)

    def cancel(self) -> None:
        """Request cancellation and transition → CANCELLED.

        Sets the cancellation event so running tools/model calls
        can check `is_cancelled` and abort cooperatively.
        """
        self._cancelled.set()
        with self._lock:
            if self._state in _TERMINAL_STATES:
                return
            self._transition(RunState.CANCELLED)

    def interrupt(self) -> None:
        """Ctrl+C interruption → INTERRUPTED (terminal)."""
        self._cancelled.set()
        with self._lock:
            if self._state in _TERMINAL_STATES:
                return
            self._transition(RunState.INTERRUPTED)

    def wait_for_user(self) -> None:
        """Transition → WAITING_FOR_USER (e.g. permission prompt)."""
        with self._lock:
            if self._state != RunState.RUNNING:
                return
            self._transition(RunState.WAITING_FOR_USER)

    def resume_from_wait(self) -> None:
        """Transition WAITING_FOR_USER → RUNNING."""
        with self._lock:
            if self._state != RunState.WAITING_FOR_USER:
                return
            self._transition(RunState.RUNNING)

    def reset(self) -> None:
        """Reset to IDLE for new work. Only valid from terminal states."""
        with self._lock:
            if self._state not in _TERMINAL_STATES and self._state != RunState.IDLE:
                raise RuntimeError(
                    f"Cannot reset from non-terminal state {self._state.value}"
                )
            self._cancelled.clear()
            self.failure_reason = None
            self.attempt_number = 0
            self._transition(RunState.IDLE)

    def _transition(self, new_state: RunState) -> None:
        """Internal state transition with optional callback."""
        old = self._state
        self._state = new_state
        if self._on_state_change and old != new_state:
            try:
                self._on_state_change(old, new_state)
            except Exception:
                pass  # Never let callback failure corrupt state machine
