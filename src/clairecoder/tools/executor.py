from threading import Condition
from typing import Any, Dict, Optional
from clairecoder.core.types import PermissionState, ToolResult, ToolState
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.permissions.types import (
    PermissionRequest, PermissionCategory, ResourceScope,
    PermissionDeniedError, PermissionRequiredError
)
from clairecoder.core.agent_types import PendingToolInvocation, ModePolicy
from .base import Tool
from .registry import ToolRegistry
from .types import ToolExecutionError

class ToolExecutor:
    """Executes tools through the Permission Engine boundary.

    This is the ONLY authorized execution path. All tool invocations
    MUST pass through this executor to ensure Permission Engine evaluation.

    §4 — Pending invocations are stored for permission resume.
    §5 — Permission requests identify the real target.
    §16 — ModePolicy controls actual execution.
    """

    def __init__(self, registry: ToolRegistry, permission_engine: PermissionEngine):
        self._registry = registry
        self._permission_engine = permission_engine
        self._mode_policy: Optional[ModePolicy] = None
        # §4: Pending permission invocations
        self._pending_permissions: Dict[str, PendingToolInvocation] = {}
        self._permission_condition = Condition()
        self._resolved_permissions: Dict[str, ToolResult] = {}

    def set_mode_policy(self, policy: Any) -> None:
        """Set the active mode policy for tool execution.

        Accepts either a ModePolicy instance or a legacy dict.
        """
        if isinstance(policy, ModePolicy):
            self._mode_policy = policy
        elif isinstance(policy, dict) and policy:
            self._mode_policy = ModePolicy(
                allow_file_read=policy.get("allow_file_read", True),
                allow_file_modification=policy.get("allow_file_modification", True),
                allow_tool_execution=policy.get("allow_tool_execution", True),
                allow_network=policy.get("allow_network", True),
                allow_repository_modification=policy.get("allow_repository_modification", True),
            )
        else:
            self._mode_policy = None

    def clear_mode_policy(self) -> None:
        """Clear the active mode policy."""
        self._mode_policy = None

    def invoke(self, tool_id: str, session_id: Optional[str] = None,
               workflow_id: Optional[str] = None, task_id: Optional[str] = None,
               tool_call_id: Optional[str] = None,
               **kwargs: Any) -> ToolResult:
        """Invoke a tool through the permission boundary.

        Returns ToolResult with appropriate state:
        - SUCCESS/FAILURE from tool execution
        - DENIED if permission check returns DENY or mode policy blocks
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

        # 1a. Mode policy enforcement (§16)
        if self._mode_policy:
            block_reason = self._check_mode_policy(tool)
            if block_reason:
                return ToolResult(
                    state=ToolState.DENIED,
                    output=None,
                    error=block_reason
                )

        # 2. Check permissions for every declared requirement
        for req in tool.required_permissions:
            # §5: Build rich permission metadata identifying the real target
            category = self._map_category(req.action)
            scope = self._map_scope(req.scope)

            # Build real resource identification
            resource_desc = self._describe_resource(tool_id, req, kwargs)

            perm_request = PermissionRequest(
                tool_id=tool_id,
                operation=req.action,
                resource=resource_desc,
                category=category,
                resource_scope=scope,
                session_id=session_id,
                workflow_id=workflow_id,
                task_id=task_id,
                metadata=self._build_permission_metadata(tool_id, req, kwargs),
            )

            decision = self._permission_engine.evaluate_request(perm_request)

            if decision == PermissionState.DENY:
                return ToolResult(
                    state=ToolState.DENIED,
                    output=None,
                    error=f"Permission denied: {req.action} on {resource_desc}"
                )
            elif decision == PermissionState.ASK:
                # §4: Store pending invocation for later resume
                import uuid
                request_id = str(uuid.uuid4())
                pending = PendingToolInvocation(
                    request_id=request_id,
                    tool_id=tool_id,
                    kwargs=dict(kwargs),
                    session_id=session_id,
                    workflow_id=workflow_id,
                    task_id=task_id,
                    tool_call_id=tool_call_id,
                    action=req.action,
                    resource=resource_desc,
                    category=category.value if category else None,
                )
                with self._permission_condition:
                    self._pending_permissions[request_id] = pending

                return ToolResult(
                    state=ToolState.DENIED,
                    output=None,
                    error=f"Permission requires confirmation: {req.action} on {resource_desc}",
                    metadata={
                        "requires_confirmation": True,
                        "request_id": request_id,
                        "action": req.action,
                        "resource": resource_desc,
                        "category": category.value if category else None,
                        "tool_id": tool_id,
                        "session_id": session_id,
                    }
                )

        # 3. Execute the tool (all permissions granted)
        return self._execute_tool(tool, kwargs)

    def resolve_permission(self, request_id: str, decision: str) -> ToolResult:
        """Resolve a pending permission and execute/deny the exact original invocation.

        §4 — Approval executes the exact pending invocation.
        """
        with self._permission_condition:
            pending = self._pending_permissions.pop(request_id, None)

        if pending is None:
            result = ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=f"Unknown permission request: {request_id}",
            )
        else:
            decision = decision.lower()

            if decision in ("granted", "approve", "yes", "y"):
                result = self._execute_pending(pending)
            elif decision in ("always", "always_session"):
                # "Always this session" means this tool/action/category for the
                # rest of this session. Keeping the original resource here made
                # the grant apply only to one exact command or file, so every
                # later operation prompted again.
                if pending.session_id:
                    category = PermissionCategory(pending.category) if pending.category else None
                    self._permission_engine.grant_session_permission(
                        session_id=pending.session_id,
                        tool_id=pending.tool_id,
                        operation=pending.action,
                        resource=None,
                        category=category,
                    )
                result = self._execute_pending(pending)
            elif decision in ("denied", "deny", "no", "n"):
                result = ToolResult(
                    state=ToolState.DENIED,
                    output=None,
                    error="User denied tool execution",
                )
            elif decision in ("cancelled", "cancel", "escape", "esc"):
                result = ToolResult(
                    state=ToolState.CANCELLED,
                    output=None,
                    error="User cancelled tool execution",
                )
            else:
                result = ToolResult(
                    state=ToolState.FAILURE,
                    output=None,
                    error=f"Unknown permission decision: {decision}",
                )

        with self._permission_condition:
            self._resolved_permissions[request_id] = result
            self._permission_condition.notify_all()
        return result

    def wait_for_permission(
        self,
        request_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[ToolResult]:
        """Wait for a user decision, including decisions made before this call."""
        with self._permission_condition:
            ready = self._permission_condition.wait_for(
                lambda: request_id in self._resolved_permissions,
                timeout=timeout,
            )
            if not ready:
                return None
            return self._resolved_permissions.pop(request_id)

    def expire_permission(self, request_id: str) -> None:
        """Discard an unanswered request after the interaction timeout."""
        with self._permission_condition:
            self._pending_permissions.pop(request_id, None)

    def cleanup_pending(self) -> None:
        """Clean up all pending permission entries.

        §4 — Called on run completion, failure, cancellation, Ctrl+C.
        """
        with self._permission_condition:
            self._pending_permissions.clear()
            self._resolved_permissions.clear()

    def get_pending(self, request_id: str) -> Optional[PendingToolInvocation]:
        """Get a pending invocation by request_id."""
        with self._permission_condition:
            return self._pending_permissions.get(request_id)

    def has_pending(self) -> bool:
        """Check if there are any pending permission requests."""
        with self._permission_condition:
            return bool(self._pending_permissions)

    def _execute_pending(self, pending: PendingToolInvocation) -> ToolResult:
        """Execute a pending tool invocation exactly as originally requested."""
        try:
            tool = self._registry.get(pending.tool_id)
        except Exception as e:
            return ToolResult(
                state=ToolState.UNAVAILABLE,
                output=None,
                error=str(e),
            )
        return self._execute_tool(tool, pending.kwargs)

    def _execute_tool(self, tool: Tool, kwargs: dict) -> ToolResult:
        """Execute a tool with validation and error handling."""
        try:
            tool.validate_input(**kwargs)
            return tool._execute(**kwargs)
        except Exception as e:
            return ToolResult(
                state=ToolState.FAILURE,
                output=None,
                error=str(e)
            )

    def _check_mode_policy(self, tool: Tool) -> Optional[str]:
        """Check if mode policy blocks this tool. Returns reason string if blocked."""
        if not self._mode_policy:
            return None

        write_actions = {"write", "create", "delete", "modify_repository"}
        execute_actions = {"execute"}

        for req in tool.required_permissions:
            if req.action in write_actions and not self._mode_policy.allow_file_modification:
                return f"Mode policy forbids file modification ({req.action} on {req.resource})"
            if req.action in execute_actions and not self._mode_policy.allow_tool_execution:
                return f"Mode policy forbids tool execution ({req.action} on {req.resource})"
            if req.action == "network" and not self._mode_policy.allow_network:
                return f"Mode policy forbids network access ({req.action} on {req.resource})"
            if req.action == "modify_repository" and not self._mode_policy.allow_repository_modification:
                return f"Mode policy forbids repository modification ({req.action} on {req.resource})"

        return None

    def _describe_resource(self, tool_id: str, req: Any, kwargs: dict) -> str:
        """Build a human-readable resource description for permission display.

        §5 — Identify the actual operation and target.
        """
        if "path" in kwargs:
            return str(kwargs["path"])
        if "command" in kwargs:
            return str(kwargs["command"])
        if "query" in kwargs:
            return f"search: {kwargs['query']}"
        if "message" in kwargs:
            return f"commit: {kwargs['message'][:50]}"
        if "target" in kwargs:
            return str(kwargs["target"])
        return req.resource

    def _build_permission_metadata(self, tool_id: str, req: Any, kwargs: dict) -> dict:
        """Build rich metadata for permission requests.

        §5 — Include actual paths, commands, etc.
        """
        meta: dict = {}
        if "path" in kwargs:
            from pathlib import Path
            try:
                meta["path"] = str(kwargs["path"])
                meta["resolved_path"] = str(Path(kwargs["path"]).resolve())
            except Exception:
                meta["path"] = str(kwargs["path"])
        if "command" in kwargs:
            meta["command"] = str(kwargs["command"])
        if "cwd" in kwargs:
            meta["cwd"] = str(kwargs["cwd"])
        return meta

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
