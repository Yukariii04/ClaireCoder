"""Verification History per CC-PRD-009.

Responsible for recording and retrieving verification outcomes.
Maintains history independently of workflow/execution authority.
"""
from typing import Dict, List, Optional
from .types import Verification

class VerificationHistory:
    """Stores verification outcomes and preserves verification identity."""

    def __init__(self):
        # Maps task_id -> list of verifications for that task
        self._history: Dict[str, List[Verification]] = {}
        # Fast lookup by verification_id
        self._verifications: Dict[str, Verification] = {}

    def record(self, verification: Verification) -> None:
        """Record a verification outcome."""
        self._verifications[verification.verification_id] = verification
        
        if verification.task_id not in self._history:
            self._history[verification.task_id] = []
            
        # Avoid duplicate entries if the same verification is recorded multiple times
        # (e.g. state updates)
        existing = [v for v in self._history[verification.task_id] 
                   if v.verification_id == verification.verification_id]
        if not existing:
            self._history[verification.task_id].append(verification)

    def get_verification(self, verification_id: str) -> Optional[Verification]:
        """Retrieve a specific verification record by ID."""
        return self._verifications.get(verification_id)

    def get_history(self, task_id: str) -> List[Verification]:
        """Retrieve all verification records for a given task (§49)."""
        return self._history.get(task_id, [])
