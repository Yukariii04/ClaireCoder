"""Verification Runner interface per CC-PRD-009.

Defines how verification/test execution requests are represented.
Does not make permission decisions, does not bypass ToolExecutor,
and does not execute privileged tools directly.
"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional
from .types import VerificationCriterion, VerificationTestResult, Evidence

class VerificationRunner(ABC):
    """Abstract interface for executing verification criteria.
    
    The actual execution must remain routed through the existing authorized
    architecture (ToolExecutor, PermissionEngine, EngineeringEngine).
    """

    @abstractmethod
    def run(
        self, criterion: VerificationCriterion, execution_id: str
    ) -> Tuple[Optional[VerificationTestResult], Optional[Evidence]]:
        """Execute a verification criterion and return results and evidence.
        
        Args:
            criterion: The verification criterion to evaluate.
            execution_id: The execution context ID to associate with the result.
            
        Returns:
            A tuple of (VerificationTestResult, Evidence). At least one must
            be provided to avoid a BLOCKED outcome due to lack of evidence.
        """
        pass
