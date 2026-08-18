from typing import Any, Optional
from clairecoder.core.types import PermissionState, ToolResult, ToolState
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.permissions.types import (
    PermissionRequest, PermissionCategory, ResourceScope,
    PermissionDeniedError, PermissionRequiredError
)
from .base import Tool
from .registry import ToolRegistry
from .types import ToolExecutionError

class ToolExecutor:
    """Executes tools through the Permission Engine boundary.
    
    This is the ONLY authorized execution path. All tool invocations
    MUST pass through this executor to ensure Permission Engine evaluation.
    
    The executor:
    1. Looks up the tool in the registry
    2. Builds permission requests from the tool's declared requirements
    3. Evaluates each requirement against the Permission Engine
    4. Executes the tool only if ALL permissions are ALLOW
    5. Returns structured ToolResult in all cases
    """

    def __init__(self, registry: ToolRegistry, permission_engine: PermissionEngine):
        self._registry = registry
        self._permission_engine = permission_engine

    def invoke(self, tool_id: str, session_id: Optional[str] = None,
               workflow_id: Optional[str] = None, task_id: Optional[str] = None,
               **kwargs: Any) -> ToolResult:
        """Invoke a tool through the permission boundary.
        
        Returns ToolResult with appropriate state:
        - SUCCESS/FAILURE from tool execution
        - DENIED if permission check returns DENY
        - UNAVAILABLE if tool not found or unavailable
        """
        # 1. Retrieve tool from registry
        try:
            tool = self._registry.get(tool_id)
        except Exception as e:
            return ToolResult(
                state=ToolState.UNAVAILABLE,
                output=None,
                error=str(e)
            )

        # 2. Check permissions for every declared requirement
        for req in tool.required_permissions:
            # Map tool permission requirements to Permission Engine requests
            category = self._map_category(req.action)
            scope = self._map_scope(req.scope)

            perm_request = PermissionRequest(
                tool_id=tool_id,
                operation=req.action,
                resource=req.resource,
                category=category,
                resource_scope=scope,
                session_id=session_id,
                workflow_id=workflow_id,
                task_id=task_id
            )

            decision = self._permission_engine.evaluate_request(perm_request)

            if decision == PermissionState.DENY:
                return ToolResult(
                    state=ToolState.DENIED,
                    output=None,
                    error=f"Permission denied: {req.action} on {req.resource}"
                )
            elif decision == PermissionState.ASK:
                # ASK means confirmation is required — tool must NOT silently execute
                return ToolResult(
                    state=ToolState.DENIED,
                    output=None,
                    error=f"Permission requires confirmation: {req.action} on {req.resource}",
                    metadata={"requires_confirmation": True, "action": req.action, "resource": req.resource}
                )

        # 3. Execute the tool (all permissions granted)
        try:
            tool.validate_input(**kwargs)
            return tool._execute(**kwargs)
        except Exception as e:
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=str(e)
            )

    def _map_category(self, action: str) -> PermissionCategory:
        """Map a tool's declared action string to a PermissionCategory."""
        mapping = {
            "read": PermissionCategory.READ,
            "write": PermissionCategory.WRITE,
            "create": PermissionCategory.CREATE,
            "delete": PermissionCategory.DELETE,
            "execute": PermissionCategory.EXECUTE,
            "network": PermissionCategory.NETWORK,
            "install": PermissionCategory.INSTALL,
            "modify_repository": PermissionCategory.MODIFY_REPOSITORY,
            "access_credential": PermissionCategory.ACCESS_CREDENTIAL,
        }
        return mapping.get(action, PermissionCategory.EXECUTE)

    def _map_scope(self, scope: str) -> ResourceScope:
        """Map a tool's declared scope string to a ResourceScope."""
        mapping = {
            "project": ResourceScope.PROJECT,
            "repository": ResourceScope.REPOSITORY,
            "directory": ResourceScope.DIRECTORY,
            "file": ResourceScope.FILE,
            "command": ResourceScope.COMMAND,
            "network_resource": ResourceScope.NETWORK_RESOURCE,
            "credential": ResourceScope.CREDENTIAL,
            "external_service": ResourceScope.EXTERNAL_SERVICE,
        }
        return mapping.get(scope, ResourceScope.PROJECT)

    def grant_session_permission(
        self,
        session_id: str,
        tool_id: Optional[str] = None,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        category: Optional[PermissionCategory] = None,
        resource_scope: Optional[ResourceScope] = None,
        priority: int = 50
    ) -> Any:
        """Grant session-scoped permission through the Permission Engine."""
        return self._permission_engine.grant_session_permission(
            session_id=session_id,
            tool_id=tool_id,
            operation=operation,
            resource=resource,
            category=category,
            resource_scope=resource_scope,
            priority=priority
        )

