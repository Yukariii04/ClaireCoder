"""Comprehensive tests for Correction #12 — Runtime Event Protocol.

Tests cover:
1.  RuntimeEvent creation and field validation
2.  EventType enum completeness
3.  EventEmitter pub/sub (emit, subscribe, unsubscribe, multiple subscribers)
4.  RuntimeEvent serialization (to_dict / from_dict round-trip)
5.  Event ordering / lifecycle sequences
6.  Failure lifecycle (no false COMPLETED after FAILED)
7.  File events (FILE_READ, FILE_CREATED, FILE_EDITED, FILE_DELETED)
8.  Command events (COMMAND_STARTED, COMMAND_OUTPUT, COMMAND_COMPLETED, COMMAND_FAILED)
9.  Verification events
10. Correlation IDs (run_id, task_id, tool_call_id)
11. EngineBridge translation (EngineEvent -> RuntimeEvent)
12. TUI listener translation (RuntimeEvent -> ActivityModel)
13. Attempt / retry representation
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from clairecoder.runtime.events import RuntimeEvent, EventType, _utc_now
from clairecoder.runtime.emitter import EventEmitter
from clairecoder.runtime.bridge import EngineBridge, _is_failure_state, _extract_file_event, _extract_command_event
from clairecoder.runtime.tui_listener import RuntimeEventTuiListener, _basename, _diff_stats
from clairecoder.engine.types import EngineEvent
from clairecoder.core.types import ToolState
from clairecoder.tui.activity import ActivityType, ActivityState


# ==========================================================================
# 1. RuntimeEvent Creation
# ==========================================================================

class TestRuntimeEventCreation:
    def test_basic_creation(self):
        ev = RuntimeEvent(event_type=EventType.RUN_STARTED)
        assert ev.event_type == EventType.RUN_STARTED
        assert ev.event_id  # auto-generated
        assert isinstance(ev.timestamp, datetime)
        assert ev.timestamp.tzinfo is not None  # UTC-aware
        assert ev.run_id is None
        assert ev.objective_id is None
        assert ev.task_id is None
        assert ev.tool_call_id is None
        assert ev.payload == {}
        assert ev.attempt is None

    def test_creation_with_all_fields(self):
        ts = _utc_now()
        ev = RuntimeEvent(
            event_type=EventType.FILE_EDITED,
            event_id="evt-123",
            timestamp=ts,
            run_id="run-1",
            objective_id="obj-1",
            task_id="task-1",
            tool_call_id="tc-1",
            payload={"path": "src/main.py", "additions": 5, "deletions": 2},
            attempt=1,
        )
        assert ev.event_type == EventType.FILE_EDITED
        assert ev.event_id == "evt-123"
        assert ev.timestamp == ts
        assert ev.run_id == "run-1"
        assert ev.objective_id == "obj-1"
        assert ev.task_id == "task-1"
        assert ev.tool_call_id == "tc-1"
        assert ev.payload["path"] == "src/main.py"
        assert ev.payload["additions"] == 5
        assert ev.payload["deletions"] == 2
        assert ev.attempt == 1

    def test_unique_event_ids(self):
        ev1 = RuntimeEvent(event_type=EventType.RUN_STARTED)
        ev2 = RuntimeEvent(event_type=EventType.RUN_STARTED)
        assert ev1.event_id != ev2.event_id

    def test_timestamp_is_utc(self):
        ev = RuntimeEvent(event_type=EventType.TOOL_STARTED)
        assert ev.timestamp.tzinfo == timezone.utc


# ==========================================================================
# 2. EventType Enum Completeness
# ==========================================================================

class TestEventTypeEnum:
    def test_all_required_types_exist(self):
        required = [
            "RUN_STARTED", "RUN_COMPLETED", "RUN_FAILED", "RUN_CANCELLED",
            "PLAN_STARTED", "PLAN_CREATED", "PLAN_UPDATED",
            "TASK_STARTED", "TASK_COMPLETED", "TASK_FAILED", "TASK_RETRYING",
            "TOOL_STARTED", "TOOL_COMPLETED", "TOOL_FAILED",
            "FILE_READ", "FILE_CREATED", "FILE_EDITED", "FILE_DELETED",
            "COMMAND_STARTED", "COMMAND_OUTPUT", "COMMAND_COMPLETED", "COMMAND_FAILED",
            "VERIFICATION_STARTED", "VERIFICATION_COMPLETED", "VERIFICATION_FAILED",
            "AGENT_MESSAGE", "AGENT_ERROR",
            "PERMISSION_REQUESTED", "PERMISSION_GRANTED", "PERMISSION_DENIED",
        ]
        for name in required:
            assert hasattr(EventType, name), f"Missing EventType.{name}"

    def test_dotted_values(self):
        assert EventType.RUN_STARTED.value == "run.started"
        assert EventType.FILE_EDITED.value == "file.edited"
        assert EventType.COMMAND_FAILED.value == "command.failed"

    def test_string_enum(self):
        """EventType values can be used as strings directly."""
        assert "run.started" == EventType.RUN_STARTED


# ==========================================================================
# 3. EventEmitter
# ==========================================================================

class TestEventEmitter:
    def test_emit_to_subscriber(self):
        emitter = EventEmitter()
        received = []
        emitter.subscribe(lambda e: received.append(e))

        ev = RuntimeEvent(event_type=EventType.RUN_STARTED)
        emitter.emit(ev)

        assert len(received) == 1
        assert received[0] is ev

    def test_multiple_subscribers(self):
        emitter = EventEmitter()
        r1, r2, r3 = [], [], []
        emitter.subscribe(lambda e: r1.append(e))
        emitter.subscribe(lambda e: r2.append(e))
        emitter.subscribe(lambda e: r3.append(e))

        ev = RuntimeEvent(event_type=EventType.TOOL_STARTED)
        emitter.emit(ev)

        assert len(r1) == 1
        assert len(r2) == 1
        assert len(r3) == 1
        assert r1[0] is r2[0] is r3[0]

    def test_unsubscribe(self):
        emitter = EventEmitter()
        received = []
        listener = lambda e: received.append(e)
        emitter.subscribe(listener)

        emitter.emit(RuntimeEvent(event_type=EventType.RUN_STARTED))
        assert len(received) == 1

        emitter.unsubscribe(listener)
        emitter.emit(RuntimeEvent(event_type=EventType.RUN_COMPLETED))
        assert len(received) == 1  # No new events

    def test_subscribe_returns_unsub_callable(self):
        emitter = EventEmitter()
        received = []
        unsub = emitter.subscribe(lambda e: received.append(e))

        emitter.emit(RuntimeEvent(event_type=EventType.RUN_STARTED))
        assert len(received) == 1

        unsub()
        emitter.emit(RuntimeEvent(event_type=EventType.RUN_COMPLETED))
        assert len(received) == 1

    def test_unsubscribe_idempotent(self):
        emitter = EventEmitter()
        listener = lambda e: None
        emitter.subscribe(listener)
        emitter.unsubscribe(listener)
        emitter.unsubscribe(listener)  # Should not raise

    def test_error_in_listener_does_not_break_others(self):
        emitter = EventEmitter()
        r1, r2 = [], []

        def bad_listener(e):
            raise ValueError("Boom!")

        emitter.subscribe(bad_listener)
        emitter.subscribe(lambda e: r2.append(e))

        emitter.emit(RuntimeEvent(event_type=EventType.RUN_STARTED))
        # r2 should still receive the event despite bad_listener crashing
        assert len(r2) == 1

    def test_listener_count(self):
        emitter = EventEmitter()
        assert emitter.listener_count == 0

        l1 = lambda e: None
        l2 = lambda e: None
        emitter.subscribe(l1)
        assert emitter.listener_count == 1
        emitter.subscribe(l2)
        assert emitter.listener_count == 2
        emitter.unsubscribe(l1)
        assert emitter.listener_count == 1

    def test_no_duplicate_subscribe(self):
        emitter = EventEmitter()
        listener = lambda e: None
        emitter.subscribe(listener)
        emitter.subscribe(listener)  # duplicate
        assert emitter.listener_count == 1


# ==========================================================================
# 4. Serialization
# ==========================================================================

class TestRuntimeEventSerialization:
    def test_to_dict_basic(self):
        ev = RuntimeEvent(
            event_type=EventType.FILE_EDITED,
            event_id="e-1",
            run_id="r-1",
            task_id="t-1",
            payload={"path": "src/a.py", "additions": 3},
        )
        d = ev.to_dict()
        assert d["event_type"] == "file.edited"
        assert d["event_id"] == "e-1"
        assert d["run_id"] == "r-1"
        assert d["task_id"] == "t-1"
        assert d["payload"]["path"] == "src/a.py"
        assert d["payload"]["additions"] == 3
        assert "timestamp" in d

    def test_to_dict_omits_none_fields(self):
        ev = RuntimeEvent(event_type=EventType.RUN_STARTED)
        d = ev.to_dict()
        assert "run_id" not in d
        assert "objective_id" not in d
        assert "task_id" not in d
        assert "tool_call_id" not in d
        assert "attempt" not in d

    def test_round_trip(self):
        ev = RuntimeEvent(
            event_type=EventType.COMMAND_COMPLETED,
            event_id="evt-99",
            run_id="run-42",
            task_id="task-7",
            tool_call_id="tc-3",
            payload={"command": "pytest", "exit_code": 0, "duration_ms": 1234},
            attempt=2,
        )
        d = ev.to_dict()
        restored = RuntimeEvent.from_dict(d)

        assert restored.event_type == ev.event_type
        assert restored.event_id == ev.event_id
        assert restored.run_id == ev.run_id
        assert restored.task_id == ev.task_id
        assert restored.tool_call_id == ev.tool_call_id
        assert restored.payload == ev.payload
        assert restored.attempt == ev.attempt

    def test_from_dict_defaults(self):
        d = {"event_type": "run.started", "timestamp": _utc_now().isoformat()}
        ev = RuntimeEvent.from_dict(d)
        assert ev.event_type == EventType.RUN_STARTED
        assert ev.run_id is None
        assert ev.payload == {}


# ==========================================================================
# 5. Event Ordering / Lifecycle
# ==========================================================================

class TestEventOrdering:
    def test_normal_execution_sequence(self):
        """Verify deterministic lifecycle order."""
        emitter = EventEmitter()
        events = []
        emitter.subscribe(lambda e: events.append(e.event_type))

        # Simulate normal execution
        emitter.emit(RuntimeEvent(event_type=EventType.RUN_STARTED, run_id="r"))
        emitter.emit(RuntimeEvent(event_type=EventType.PLAN_STARTED, run_id="r"))
        emitter.emit(RuntimeEvent(event_type=EventType.PLAN_CREATED, run_id="r"))
        emitter.emit(RuntimeEvent(event_type=EventType.TASK_STARTED, run_id="r", task_id="t1"))
        emitter.emit(RuntimeEvent(event_type=EventType.TOOL_STARTED, run_id="r", task_id="t1", tool_call_id="tc1"))
        emitter.emit(RuntimeEvent(event_type=EventType.FILE_READ, run_id="r", task_id="t1", tool_call_id="tc1"))
        emitter.emit(RuntimeEvent(event_type=EventType.TOOL_COMPLETED, run_id="r", task_id="t1", tool_call_id="tc1"))
        emitter.emit(RuntimeEvent(event_type=EventType.TOOL_STARTED, run_id="r", task_id="t1", tool_call_id="tc2"))
        emitter.emit(RuntimeEvent(event_type=EventType.FILE_EDITED, run_id="r", task_id="t1", tool_call_id="tc2"))
        emitter.emit(RuntimeEvent(event_type=EventType.TOOL_COMPLETED, run_id="r", task_id="t1", tool_call_id="tc2"))
        emitter.emit(RuntimeEvent(event_type=EventType.VERIFICATION_STARTED, run_id="r", task_id="t1"))
        emitter.emit(RuntimeEvent(event_type=EventType.VERIFICATION_COMPLETED, run_id="r", task_id="t1"))
        emitter.emit(RuntimeEvent(event_type=EventType.TASK_COMPLETED, run_id="r", task_id="t1"))
        emitter.emit(RuntimeEvent(event_type=EventType.RUN_COMPLETED, run_id="r"))

        expected = [
            EventType.RUN_STARTED,
            EventType.PLAN_STARTED, EventType.PLAN_CREATED,
            EventType.TASK_STARTED,
            EventType.TOOL_STARTED, EventType.FILE_READ, EventType.TOOL_COMPLETED,
            EventType.TOOL_STARTED, EventType.FILE_EDITED, EventType.TOOL_COMPLETED,
            EventType.VERIFICATION_STARTED, EventType.VERIFICATION_COMPLETED,
            EventType.TASK_COMPLETED,
            EventType.RUN_COMPLETED,
        ]
        assert events == expected

    def test_correlation_ids_consistent(self):
        """All events in a tool call share the same correlation IDs."""
        emitter = EventEmitter()
        events = []
        emitter.subscribe(lambda e: events.append(e))

        run_id = "run_123"
        task_id = "task_001"
        tc_id = "tool_001"

        emitter.emit(RuntimeEvent(event_type=EventType.TOOL_STARTED, run_id=run_id, task_id=task_id, tool_call_id=tc_id))
        emitter.emit(RuntimeEvent(event_type=EventType.FILE_EDITED, run_id=run_id, task_id=task_id, tool_call_id=tc_id))
        emitter.emit(RuntimeEvent(event_type=EventType.TOOL_COMPLETED, run_id=run_id, task_id=task_id, tool_call_id=tc_id))

        for ev in events:
            assert ev.run_id == run_id
            assert ev.task_id == task_id
            assert ev.tool_call_id == tc_id


# ==========================================================================
# 6. Failure Lifecycle
# ==========================================================================

class TestFailureLifecycle:
    def test_tool_failure_no_completed(self):
        """TOOL_FAILED must NOT be followed by TOOL_COMPLETED."""
        emitter = EventEmitter()
        events = []
        emitter.subscribe(lambda e: events.append(e.event_type))

        # Correct failure sequence
        emitter.emit(RuntimeEvent(event_type=EventType.TOOL_STARTED))
        emitter.emit(RuntimeEvent(event_type=EventType.TOOL_FAILED))

        assert EventType.TOOL_COMPLETED not in events
        assert events == [EventType.TOOL_STARTED, EventType.TOOL_FAILED]

    def test_command_failure_sequence(self):
        emitter = EventEmitter()
        events = []
        emitter.subscribe(lambda e: events.append(e.event_type))

        emitter.emit(RuntimeEvent(event_type=EventType.COMMAND_STARTED))
        emitter.emit(RuntimeEvent(event_type=EventType.COMMAND_OUTPUT))
        emitter.emit(RuntimeEvent(event_type=EventType.COMMAND_FAILED))

        assert EventType.COMMAND_COMPLETED not in events

    def test_task_failure_propagates_to_run(self):
        emitter = EventEmitter()
        events = []
        emitter.subscribe(lambda e: events.append(e.event_type))

        emitter.emit(RuntimeEvent(event_type=EventType.RUN_STARTED))
        emitter.emit(RuntimeEvent(event_type=EventType.TASK_STARTED))
        emitter.emit(RuntimeEvent(event_type=EventType.TASK_FAILED))
        emitter.emit(RuntimeEvent(event_type=EventType.RUN_FAILED))

        assert EventType.TASK_COMPLETED not in events
        assert EventType.RUN_COMPLETED not in events

    def test_verification_failure(self):
        emitter = EventEmitter()
        events = []
        emitter.subscribe(lambda e: events.append(e.event_type))

        emitter.emit(RuntimeEvent(event_type=EventType.VERIFICATION_STARTED))
        emitter.emit(RuntimeEvent(event_type=EventType.VERIFICATION_FAILED))

        assert EventType.VERIFICATION_COMPLETED not in events


# ==========================================================================
# 7. File Events
# ==========================================================================

class TestFileEvents:
    def test_file_read_event(self):
        ev = RuntimeEvent(
            event_type=EventType.FILE_READ,
            run_id="r1",
            task_id="t1",
            tool_call_id="tc1",
            payload={"path": "src/main.py"},
        )
        assert ev.event_type == EventType.FILE_READ
        assert ev.payload["path"] == "src/main.py"
        assert ev.run_id == "r1"

    def test_file_created_event(self):
        ev = RuntimeEvent(
            event_type=EventType.FILE_CREATED,
            payload={"path": "src/new.py", "additions": 20, "deletions": 0},
        )
        assert ev.payload["additions"] == 20

    def test_file_edited_event(self):
        ev = RuntimeEvent(
            event_type=EventType.FILE_EDITED,
            payload={
                "path": "src/calc.py",
                "additions": 8,
                "deletions": 2,
                "diff": "--- a/calc.py\n+++ b/calc.py",
            },
        )
        assert ev.payload["additions"] == 8
        assert ev.payload["deletions"] == 2
        assert "diff" in ev.payload

    def test_file_deleted_event(self):
        ev = RuntimeEvent(
            event_type=EventType.FILE_DELETED,
            payload={"path": "src/old.py"},
        )
        assert ev.event_type == EventType.FILE_DELETED

    def test_file_event_serialization(self):
        ev = RuntimeEvent(
            event_type=EventType.FILE_EDITED,
            run_id="r1",
            task_id="t1",
            tool_call_id="tc1",
            payload={"path": "src/calc.py", "additions": 8, "deletions": 2},
        )
        d = ev.to_dict()
        assert d["event_type"] == "file.edited"
        assert d["payload"]["additions"] == 8

        restored = RuntimeEvent.from_dict(d)
        assert restored.event_type == EventType.FILE_EDITED
        assert restored.payload["additions"] == 8


# ==========================================================================
# 8. Command Events
# ==========================================================================

class TestCommandEvents:
    def test_command_started(self):
        ev = RuntimeEvent(
            event_type=EventType.COMMAND_STARTED,
            payload={"command": "pytest -q", "cwd": "/project"},
        )
        assert ev.payload["command"] == "pytest -q"

    def test_command_output(self):
        ev = RuntimeEvent(
            event_type=EventType.COMMAND_OUTPUT,
            payload={"output": "...\n5 passed"},
        )
        assert ev.event_type == EventType.COMMAND_OUTPUT

    def test_command_completed(self):
        ev = RuntimeEvent(
            event_type=EventType.COMMAND_COMPLETED,
            payload={"command": "pytest", "exit_code": 0, "duration_ms": 1200},
        )
        assert ev.payload["exit_code"] == 0

    def test_command_failed(self):
        ev = RuntimeEvent(
            event_type=EventType.COMMAND_FAILED,
            payload={"command": "pytest", "exit_code": 1, "duration_ms": 800},
        )
        assert ev.payload["exit_code"] == 1


# ==========================================================================
# 9. Verification Events
# ==========================================================================

class TestVerificationEvents:
    def test_verification_started(self):
        ev = RuntimeEvent(
            event_type=EventType.VERIFICATION_STARTED,
            payload={"check": "pytest"},
        )
        assert ev.payload["check"] == "pytest"

    def test_verification_completed(self):
        ev = RuntimeEvent(
            event_type=EventType.VERIFICATION_COMPLETED,
            payload={"check": "pytest", "passed": 14, "failed": 0},
        )
        assert ev.payload["passed"] == 14

    def test_verification_failed(self):
        ev = RuntimeEvent(
            event_type=EventType.VERIFICATION_FAILED,
            payload={"check": "pytest", "passed": 10, "failed": 4},
        )
        assert ev.event_type == EventType.VERIFICATION_FAILED


# ==========================================================================
# 10. Correlation IDs
# ==========================================================================

class TestCorrelation:
    def test_run_task_tool_correlation(self):
        """Events within a tool call must share run/task/tool IDs."""
        events = []
        emitter = EventEmitter()
        emitter.subscribe(lambda e: events.append(e))

        ids = {"run_id": "run_1", "task_id": "task_1", "tool_call_id": "tc_1"}

        emitter.emit(RuntimeEvent(event_type=EventType.TOOL_STARTED, **ids))
        emitter.emit(RuntimeEvent(event_type=EventType.FILE_EDITED, **ids, payload={"path": "a.py"}))
        emitter.emit(RuntimeEvent(event_type=EventType.TOOL_COMPLETED, **ids))

        for ev in events:
            assert ev.run_id == "run_1"
            assert ev.task_id == "task_1"
            assert ev.tool_call_id == "tc_1"

    def test_different_tasks_different_ids(self):
        ev1 = RuntimeEvent(event_type=EventType.TASK_STARTED, run_id="r1", task_id="t1")
        ev2 = RuntimeEvent(event_type=EventType.TASK_STARTED, run_id="r1", task_id="t2")
        assert ev1.task_id != ev2.task_id
        assert ev1.run_id == ev2.run_id


# ==========================================================================
# 11. EngineBridge
# ==========================================================================

class TestEngineBridge:
    def test_tool_requested_maps_to_tool_started(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.TOOL_REQUESTED, {
            "tool_name": "filesystem.read",
            "request_id": "req-1",
        })

        assert len(received) == 1
        assert received[0].event_type == EventType.TOOL_STARTED
        assert received[0].payload["tool"] == "filesystem.read"
        assert received[0].tool_call_id == "req-1"

    def test_tool_completed_success(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.TOOL_COMPLETED, {
            "tool_name": "filesystem.read",
            "request_id": "req-1",
            "state": ToolState.SUCCESS,
            "metadata": {"path": "src/main.py", "size": 100},
        })

        types = [e.event_type for e in received]
        assert EventType.FILE_READ in types
        assert EventType.TOOL_COMPLETED in types
        assert EventType.TOOL_FAILED not in types

    def test_tool_completed_failure(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.TOOL_COMPLETED, {
            "tool_name": "filesystem.write",
            "request_id": "req-2",
            "state": ToolState.FAILURE,
            "result": "Permission denied",
            "metadata": {},
        })

        types = [e.event_type for e in received]
        assert EventType.TOOL_FAILED in types
        assert EventType.TOOL_COMPLETED not in types

    def test_file_read_produces_file_read_event(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.TOOL_COMPLETED, {
            "tool_name": "filesystem.read",
            "request_id": "req-3",
            "state": ToolState.SUCCESS,
            "metadata": {"path": "src/calc.py", "size": 500},
        })

        file_events = [e for e in received if e.event_type == EventType.FILE_READ]
        assert len(file_events) == 1
        assert file_events[0].payload["path"] == "src/calc.py"

    def test_file_write_produces_file_created_event(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.TOOL_COMPLETED, {
            "tool_name": "filesystem.write",
            "request_id": "req-4",
            "state": ToolState.SUCCESS,
            "metadata": {
                "path": "src/new.py",
                "bytes_written": 100,
                "additions": 15,
                "deletions": 0,
                "diff": "+15 lines",
            },
        })

        file_events = [e for e in received if e.event_type == EventType.FILE_CREATED]
        assert len(file_events) == 1
        assert file_events[0].payload["additions"] == 15

    def test_file_replace_produces_file_edited_event(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.TOOL_COMPLETED, {
            "tool_name": "filesystem.replace",
            "request_id": "req-5",
            "state": ToolState.SUCCESS,
            "metadata": {
                "path": "src/calc.py",
                "additions": 8,
                "deletions": 2,
                "diff": "--- a\n+++ b",
            },
        })

        file_events = [e for e in received if e.event_type == EventType.FILE_EDITED]
        assert len(file_events) == 1
        assert file_events[0].payload["additions"] == 8
        assert file_events[0].payload["deletions"] == 2

    def test_file_delete_produces_file_deleted_event(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.TOOL_COMPLETED, {
            "tool_name": "filesystem.delete",
            "request_id": "req-6",
            "state": ToolState.SUCCESS,
            "metadata": {"path": "src/old.py"},
        })

        file_events = [e for e in received if e.event_type == EventType.FILE_DELETED]
        assert len(file_events) == 1

    def test_command_tool_produces_command_event(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.TOOL_COMPLETED, {
            "tool_name": "shell.execute",
            "request_id": "req-7",
            "state": ToolState.SUCCESS,
            "metadata": {"command": "pytest", "exit_code": 0, "cwd": "/project", "duration_ms": 1200},
        })

        cmd_events = [e for e in received if e.event_type == EventType.COMMAND_COMPLETED]
        assert len(cmd_events) == 1
        assert cmd_events[0].payload["command"] == "pytest"
        assert cmd_events[0].payload["exit_code"] == 0

    def test_command_failure(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.TOOL_COMPLETED, {
            "tool_name": "shell.execute",
            "request_id": "req-8",
            "state": ToolState.FAILURE,
            "metadata": {"command": "make build", "exit_code": 2, "cwd": "/project"},
        })

        cmd_events = [e for e in received if e.event_type == EventType.COMMAND_FAILED]
        assert len(cmd_events) == 1
        assert cmd_events[0].payload["exit_code"] == 2

    def test_run_started_mapped(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.RUN_STARTED, {"run_id": "r1"})
        assert received[0].event_type == EventType.RUN_STARTED
        assert received[0].run_id == "r1"

    def test_planning_mapped(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.PLANNING_STARTED, {"session_id": "s1"})
        bridge.on_engine_event(EngineEvent.PLANNING_COMPLETED, {"session_id": "s1"})

        types = [e.event_type for e in received]
        assert EventType.PLAN_STARTED in types
        assert EventType.PLAN_CREATED in types

    def test_verification_pass(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.VALIDATION_STARTED, {"task_id": "t1"})
        bridge.on_engine_event(EngineEvent.VALIDATION_COMPLETED, {"task_id": "t1", "passed": True})

        types = [e.event_type for e in received]
        assert EventType.VERIFICATION_STARTED in types
        assert EventType.VERIFICATION_COMPLETED in types

    def test_verification_fail(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.VALIDATION_COMPLETED, {"task_id": "t1", "passed": False})

        types = [e.event_type for e in received]
        assert EventType.VERIFICATION_FAILED in types
        assert EventType.VERIFICATION_COMPLETED not in types

    def test_permission_granted(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.PERMISSION_RESOLVED, {
            "decision": "granted",
            "tool_name": "filesystem.write",
            "request_id": "req-10",
        })

        assert received[0].event_type == EventType.PERMISSION_GRANTED

    def test_permission_denied(self):
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.PERMISSION_RESOLVED, {
            "decision": "denied",
            "tool_name": "filesystem.write",
            "request_id": "req-11",
        })

        assert received[0].event_type == EventType.PERMISSION_DENIED

    def test_internal_events_suppressed(self):
        """Streaming/model events don't produce runtime events."""
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.STREAMING_CHUNK, {"chunk": "hello"})
        bridge.on_engine_event(EngineEvent.MODEL_SWITCHED, {"model": "gpt-4"})
        bridge.on_engine_event(EngineEvent.MODE_CHANGED, {"mode": "implement"})

        assert len(received) == 0

    def test_tool_alias_file_read(self):
        """Tool aliases like 'read_file' also produce FILE_READ."""
        emitter = EventEmitter()
        bridge = EngineBridge(emitter)
        received = []
        emitter.subscribe(lambda e: received.append(e))

        bridge.on_engine_event(EngineEvent.TOOL_COMPLETED, {
            "tool_name": "read_file",
            "request_id": "req-20",
            "state": ToolState.SUCCESS,
            "metadata": {"path": "src/app.py", "size": 200},
        })

        file_events = [e for e in received if e.event_type == EventType.FILE_READ]
        assert len(file_events) == 1


# ==========================================================================
# 12. TUI Listener
# ==========================================================================

class TestTuiListener:
    def test_task_started_activity(self):
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.TASK_STARTED,
            task_id="t1",
            payload={"description": "implement calculator"},
        ))
        assert activity is not None
        assert activity.state == ActivityState.RUNNING
        assert "implement calculator" in activity.title

    def test_tool_started_activity(self):
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.TOOL_STARTED,
            tool_call_id="tc1",
            payload={"tool": "filesystem.read"},
        ))
        assert activity is not None
        assert activity.state == ActivityState.RUNNING
        assert "filesystem.read" in activity.title

    def test_file_edited_activity(self):
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.FILE_EDITED,
            payload={"path": "src/calculator.py", "additions": 8, "deletions": 2},
        ))
        assert activity is not None
        assert activity.state == ActivityState.COMPLETED
        assert "calculator.py" in activity.title
        assert "+8" in activity.title
        assert "-2" in activity.title

    def test_file_read_activity(self):
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.FILE_READ,
            payload={"path": "src/main.py"},
        ))
        assert activity is not None
        assert "Read" in activity.title
        assert "main.py" in activity.title

    def test_file_deleted_activity(self):
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.FILE_DELETED,
            payload={"path": "src/old.py"},
        ))
        assert activity is not None
        assert "Deleted" in activity.title

    def test_command_completed_activity(self):
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.COMMAND_COMPLETED,
            payload={"command": "pytest"},
        ))
        assert activity is not None
        assert activity.state == ActivityState.COMPLETED
        assert "pytest" in activity.title

    def test_command_failed_activity(self):
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.COMMAND_FAILED,
            payload={"command": "make build", "exit_code": 1},
        ))
        assert activity is not None
        assert activity.state == ActivityState.FAILED
        assert "exit code 1" in (activity.detail or "")

    def test_verification_completed_activity(self):
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.VERIFICATION_COMPLETED,
            payload={"check": "pytest"},
        ))
        assert activity is not None
        assert activity.state == ActivityState.COMPLETED
        assert "passed" in activity.title.lower()

    def test_verification_failed_activity(self):
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.VERIFICATION_FAILED,
            payload={"check": "pytest"},
        ))
        assert activity is not None
        assert activity.state == ActivityState.FAILED

    def test_permission_requested_activity(self):
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.PERMISSION_REQUESTED,
            payload={"tool": "filesystem.write"},
        ))
        assert activity is not None
        assert activity.type == ActivityType.PERMISSION
        assert activity.state == ActivityState.APPROVAL_REQUIRED

    def test_run_started_returns_none(self):
        """RUN_STARTED doesn't need a visible activity entry."""
        activity = RuntimeEventTuiListener.event_to_activity(RuntimeEvent(
            event_type=EventType.RUN_STARTED,
        ))
        assert activity is None

    def test_callback_invoked(self):
        received = []
        listener = RuntimeEventTuiListener(activity_callback=lambda a: received.append(a))

        listener.on_event(RuntimeEvent(
            event_type=EventType.FILE_EDITED,
            payload={"path": "src/a.py", "additions": 3},
        ))

        assert len(received) == 1
        assert "Edited" in received[0].title


# ==========================================================================
# 13. Attempt / Retry Representation
# ==========================================================================

class TestAttemptTracking:
    def test_retry_sequence(self):
        """Task retries are distinguishable via attempt number."""
        emitter = EventEmitter()
        events = []
        emitter.subscribe(lambda e: events.append(e))

        # Attempt 1 — fails
        emitter.emit(RuntimeEvent(event_type=EventType.TASK_STARTED, run_id="r", task_id="t1", attempt=1))
        emitter.emit(RuntimeEvent(event_type=EventType.TASK_FAILED, run_id="r", task_id="t1", attempt=1))

        # Attempt 2 — succeeds
        emitter.emit(RuntimeEvent(event_type=EventType.TASK_RETRYING, run_id="r", task_id="t1", attempt=2))
        emitter.emit(RuntimeEvent(event_type=EventType.TASK_STARTED, run_id="r", task_id="t1", attempt=2))
        emitter.emit(RuntimeEvent(event_type=EventType.TASK_COMPLETED, run_id="r", task_id="t1", attempt=2))

        emitter.emit(RuntimeEvent(event_type=EventType.RUN_COMPLETED, run_id="r"))

        assert events[0].attempt == 1
        assert events[1].attempt == 1
        assert events[2].attempt == 2
        assert events[3].attempt == 2
        assert events[4].attempt == 2

    def test_attempt_serialization(self):
        ev = RuntimeEvent(event_type=EventType.TASK_STARTED, attempt=3)
        d = ev.to_dict()
        assert d["attempt"] == 3

        restored = RuntimeEvent.from_dict(d)
        assert restored.attempt == 3


# ==========================================================================
# 14. Helpers
# ==========================================================================

class TestHelpers:
    def test_basename(self):
        assert _basename("src/main.py") == "main.py"
        assert _basename("src\\main.py") == "main.py"
        assert _basename("main.py") == "main.py"
        assert _basename("") == "file"

    def test_diff_stats(self):
        assert _diff_stats(8, 2) == " +8 -2"
        assert _diff_stats(5, None) == " +5"
        assert _diff_stats(None, 3) == " -3"
        assert _diff_stats(None, None) == ""
        assert _diff_stats(0, 0) == ""

    def test_is_failure_state(self):
        assert _is_failure_state(ToolState.FAILURE)
        assert _is_failure_state(ToolState.DENIED)
        assert _is_failure_state(ToolState.TIMEOUT)
        assert not _is_failure_state(ToolState.SUCCESS)
        assert _is_failure_state("failure")
        assert not _is_failure_state("success")
