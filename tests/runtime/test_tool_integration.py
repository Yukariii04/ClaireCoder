r"""Tests for Tool and Workspace integration with AgentRuntime and ChangeSet (Correction #19).

Validates:
- AgentRuntime can invoke tools through the registry
- Workspace mutations reach ChangeSet
- Tool events are emitted (TOOL_STARTED, TOOL_COMPLETED, TOOL_FAILED)
- Existing execution behavior remains compatible
- ImplementerRole integration with ToolRegistry
- Failure isolation during tool calls
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from clairecoder.workspace import Workspace
from clairecoder.core.types import ToolResult
from clairecoder.runtime.agent_runtime import AgentRuntime
from clairecoder.runtime.events import EventType, RuntimeEvent
from clairecoder.runtime.emitter import EventEmitter
from clairecoder.runtime.roles import Role, RoleContext, RoleResult, RoleRegistry, ImplementerRole
from clairecoder.tools import Tool, ToolContext, ToolRegistry, WriteFileTool, ReadFileTool
from clairecoder.changeset import ChangeTracker, ChangeSetStore, ChangeSetStatus


class TestRuntimeToolIntegration:
    """Tests AgentRuntime tool execution and event emission."""

    @pytest.fixture
    def workspace_dir(self, tmp_path: Path) -> Path:
        ws_dir = tmp_path / "workspace"
        ws_dir.mkdir()
        return ws_dir

    @pytest.fixture
    def event_collector(self) -> tuple[EventEmitter, List[RuntimeEvent]]:
        emitter = EventEmitter()
        events: List[RuntimeEvent] = []
        emitter.subscribe(lambda ev: events.append(ev))
        return emitter, events

    def test_runtime_invokes_tools_through_registry(self, workspace_dir: Path, event_collector):
        emitter, events = event_collector
        runtime = AgentRuntime(
            workspace_root=str(workspace_dir),
            event_emitter=emitter,
        )

        assert runtime.workspace is not None
        assert runtime.tool_registry is not None
        assert runtime.workspace.root == workspace_dir.resolve()

        # Execute write_file tool
        write_res = runtime.execute_tool(
            "write_file",
            arguments={"path": "src/hello.py", "content": "print('hello world')"},
            run_id="run_123",
            task_id="task_456",
        )

        assert write_res.success is True
        assert (workspace_dir / "src" / "hello.py").exists()
        assert (workspace_dir / "src" / "hello.py").read_text(encoding="utf-8") == "print('hello world')"

        # Execute read_file tool
        read_res = runtime.execute_tool(
            "read_file",
            arguments={"path": "src/hello.py"},
            run_id="run_123",
            task_id="task_456",
        )

        assert read_res.success is True
        assert read_res.output == "print('hello world')"

        # Check emitted events
        event_types = [e.event_type for e in events]
        assert EventType.TOOL_STARTED in event_types
        assert EventType.TOOL_COMPLETED in event_types

        # Verify TOOL_STARTED payload
        started_events = [e for e in events if e.event_type == EventType.TOOL_STARTED]
        assert len(started_events) >= 2
        assert started_events[0].payload["tool"] == "write_file"
        assert started_events[0].run_id == "run_123"
        assert started_events[0].task_id == "task_456"

        # Verify TOOL_COMPLETED payload
        completed_events = [e for e in events if e.event_type == EventType.TOOL_COMPLETED]
        assert len(completed_events) >= 2
        assert completed_events[0].payload["tool"] == "write_file"
        assert completed_events[0].payload["success"] is True

    def test_runtime_emits_tool_failed_on_error(self, workspace_dir: Path, event_collector):
        emitter, events = event_collector
        runtime = AgentRuntime(
            workspace_root=str(workspace_dir),
            event_emitter=emitter,
        )

        # Attempt to read nonexistent file
        res = runtime.execute_tool(
            "read_file",
            arguments={"path": "missing.txt"},
            run_id="run_fail",
        )

        assert res.success is False
        assert "not found" in res.error.lower()

        failed_events = [e for e in events if e.event_type == EventType.TOOL_FAILED]
        assert len(failed_events) == 1
        assert failed_events[0].payload["tool"] == "read_file"
        assert failed_events[0].payload["success"] is False
        assert failed_events[0].run_id == "run_fail"

    def test_runtime_emits_tool_failed_for_unknown_tool(self, workspace_dir: Path, event_collector):
        emitter, events = event_collector
        runtime = AgentRuntime(
            workspace_root=str(workspace_dir),
            event_emitter=emitter,
        )

        res = runtime.execute_tool("unknown_tool_xyz", arguments={})

        assert res.success is False
        assert "unknown tool" in res.error.lower()

        failed_events = [e for e in events if e.event_type == EventType.TOOL_FAILED]
        assert len(failed_events) == 1
        assert failed_events[0].payload["tool"] == "unknown_tool_xyz"

    def test_workspace_mutations_reach_changeset(self, workspace_dir: Path):
        runtime = AgentRuntime(workspace_root=str(workspace_dir))
        tracker = runtime.workspace.create_tracker()
        assert tracker is not None

        tracker.capture_before()

        # Use tool to mutate workspace
        res = runtime.execute_tool(
            "write_file",
            arguments={"path": "feature.py", "content": "def run(): pass"},
        )
        assert res.success is True

        changeset = tracker.capture_after(task_id="t_feature", run_id="r_main")
        assert changeset is not None
        assert "feature.py" in changeset.modified_paths

        # Check recorded into ChangeSetStore
        changeset_store = runtime.changeset_store
        changeset_store.record_changeset(changeset)
        retrieved = changeset_store.get_changeset(changeset.id)
        assert retrieved is not None
        assert retrieved.id == changeset.id
        assert "feature.py" in retrieved.modified_paths

    def test_implementer_role_delegates_to_tool_registry(self, workspace_dir: Path):
        ws = Workspace(workspace_dir)
        reg = ToolRegistry.create_default(workspace=ws)
        role = ImplementerRole(reg)

        ctx = RoleContext(
            run_id="run_role",
            objective="Write file",
            metadata={
                "tool_name": "write_file",
                "arguments": {"path": "role_test.txt", "content": "from role"},
            },
        )
        result = role.execute(ctx)

        assert result.success is True
        assert (workspace_dir / "role_test.txt").exists()
        assert (workspace_dir / "role_test.txt").read_text(encoding="utf-8") == "from role"
