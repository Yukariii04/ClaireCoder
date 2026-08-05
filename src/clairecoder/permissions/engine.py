from typing import List, Any, Optional
from clairecoder.core.interfaces import PermissionEngineInterface
from clairecoder.core.types import PermissionState
from .types import (
    PermissionRequest, PermissionRule, AutonomyLevel, 
    PermissionDeniedError, PermissionRequiredError,
    PermissionCategory, ResourceScope
)

class PermissionEngine(PermissionEngineInterface):
    def __init__(self, autonomy_level: AutonomyLevel = AutonomyLevel.SUPERVISED):
        self._rules: List[PermissionRule] = []
        self._autonomy_level = autonomy_level

    @property
    def autonomy_level(self) -> AutonomyLevel:
        return self._autonomy_level

    @autonomy_level.setter
    def autonomy_level(self, level: AutonomyLevel) -> None:
        self._autonomy_level = level

    def add_rule(self, rule: PermissionRule) -> None:
        self._rules.append(rule)
        # Sort by priority descending (higher priority evaluated first)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def revoke_rule(self, rule: PermissionRule) -> None:
        if rule in self._rules:
            self._rules.remove(rule)

    def _matches(self, rule: PermissionRule, request: PermissionRequest) -> bool:
        if rule.tool_id and rule.tool_id != request.tool_id: return False
        if rule.operation and rule.operation != request.operation: return False
        if rule.resource and rule.resource != request.resource: return False
        if rule.category and rule.category != request.category: return False
        if rule.resource_scope and rule.resource_scope != request.resource_scope: return False
        if rule.session_id and rule.session_id != request.session_id: return False
        if rule.workflow_id and rule.workflow_id != request.workflow_id: return False
        
        if rule.autonomy_level and rule.autonomy_level != self._autonomy_level:
            return False
            
        return True

    def evaluate_request(self, request: PermissionRequest) -> PermissionState:
        # 1. Check explicit rules based on priority
        for rule in self._rules:
            if self._matches(rule, request):
                return rule.decision
                
        # 2. Base Autonomy Logic (Default Policies)
        if request.category == PermissionCategory.ACCESS_CREDENTIAL:
            return PermissionState.DENY
            
        if self._autonomy_level == AutonomyLevel.SUPERVISED:
            return PermissionState.ASK
            
        if self._autonomy_level == AutonomyLevel.ASSISTED:
            # Low risk operations ALLOW, others ASK
            if request.category == PermissionCategory.READ:
                return PermissionState.ALLOW
            return PermissionState.ASK
            
        if self._autonomy_level == AutonomyLevel.AUTONOMOUS:
            # Many operations ALLOW within workspace boundaries, but high risk might still ASK
            if request.category in (PermissionCategory.READ, PermissionCategory.WRITE, PermissionCategory.CREATE, PermissionCategory.NETWORK):
                return PermissionState.ALLOW
            if request.category == PermissionCategory.DELETE:
                return PermissionState.ASK
            return PermissionState.ASK
            
        if self._autonomy_level == AutonomyLevel.YOLO:
            # Dangerous, allows everything except explicit deny
            return PermissionState.ALLOW

        return PermissionState.ASK

    # Compatibility with core interface
    def check_permission(self, action: str, target: str, **kwargs: Any) -> PermissionState:
        cat_str = kwargs.get("category", "read")
        category = PermissionCategory(cat_str) if cat_str else PermissionCategory.READ
        
        scope_str = kwargs.get("resource_scope", "project")
        resource_scope = ResourceScope(scope_str) if scope_str else ResourceScope.PROJECT

        req = PermissionRequest(
            tool_id=kwargs.get("tool_id", "unknown"),
            operation=action,
            resource=target,
            category=category,
            resource_scope=resource_scope
        )
        return self.evaluate_request(req)
        
    def enforce(self, request: PermissionRequest) -> None:
        """Helper to evaluate and raise if denied or confirmation required."""
        state = self.evaluate_request(request)
        if state == PermissionState.DENY:
            raise PermissionDeniedError(f"Operation {request.operation} on {request.resource} is DENIED.")
        elif state == PermissionState.ASK:
            raise PermissionRequiredError(f"Operation {request.operation} on {request.resource} requires CONFIRMATION.")
