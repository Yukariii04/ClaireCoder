"""Tests for mode policy enforcement at the ToolExecutor level."""
import pytest
from unittest.mock import Mock
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.registry import ToolRegistry
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.core.types import ToolState
from clairecoder.core.agent_types import ModePolicy


class TestModePolicyEnforcement:
    """§7/§16: Mode constraints block file modifications at the execution boundary."""

    def _make_executor(self):
        registry = ToolRegistry()
        perm_engine = PermissionEngine()
        return ToolExecutor(registry, perm_engine)

    def test_default_policy_allows_everything(self):
        executor = self._make_executor()
        # Default mode policy is None (no restrictions)
        assert executor._mode_policy is None

    def test_set_mode_policy_from_dict(self):
        executor = self._make_executor()
        policy = {"allow_file_modification": False, "allow_tool_execution": True}
        executor.set_mode_policy(policy)
        assert executor._mode_policy is not None
        assert executor._mode_policy.allow_file_modification is False
        assert executor._mode_policy.allow_tool_execution is True

    def test_set_mode_policy_from_mode_policy(self):
        executor = self._make_executor()
        policy = ModePolicy.for_mode("plan")
        executor.set_mode_policy(policy)
        assert executor._mode_policy is not None
        assert executor._mode_policy.allow_file_modification is False

    def test_plan_mode_blocks_write_tool(self):
        executor = self._make_executor()
        executor.set_mode_policy(ModePolicy.for_mode("plan"))
        
        # Register a tool that requires write permission
        from clairecoder.tools.base import Tool
        class WriteFileTool(Tool):
            @property
            def id(self):
                return "write_file"
            @property
            def description(self):
                return "Write to a file"
            @property
            def metadata(self):
                from clairecoder.tools.types import ToolMetadata, ToolCategory
                return ToolMetadata(
                    id="write_file", name="write_file",
                    description="Write to a file", version="1.0",
                    category=ToolCategory.FILESYSTEM
                )
            @property
            def required_permissions(self):
                from clairecoder.core.types import PermissionRequirement
                return [PermissionRequirement(action="write", resource="test.py", scope="file")]
            def validate_input(self, **kwargs):
                pass
            def _execute(self, **kwargs):
                from clairecoder.core.types import ToolResult
                return ToolResult(state=ToolState.SUCCESS, output="written")

        executor._registry.register(WriteFileTool())
        result = executor.invoke("write_file", content="test")
        assert result.state == ToolState.DENIED
        assert "Mode policy forbids file modification" in result.error

    def test_implement_mode_allows_write_tool(self):
        executor = self._make_executor()
        executor.set_mode_policy(ModePolicy.for_mode("implement"))
        assert executor._mode_policy.allow_file_modification is True

    def test_set_none_policy_clears(self):
        executor = self._make_executor()
        executor.set_mode_policy(ModePolicy.for_mode("plan"))
        executor.set_mode_policy(None)
        assert executor._mode_policy is None

    def test_review_mode_blocks_modification(self):
        """§16: Review mode blocks file modification."""
        executor = self._make_executor()
        executor.set_mode_policy(ModePolicy.for_mode("review"))
        assert executor._mode_policy.allow_file_read is True
        assert executor._mode_policy.allow_file_modification is False

    def test_debug_mode_allows_all(self):
        """§16: Debug mode allows everything."""
        executor = self._make_executor()
        executor.set_mode_policy(ModePolicy.for_mode("debug"))
        assert executor._mode_policy.allow_file_modification is True
        assert executor._mode_policy.allow_tool_execution is True
