"""Tests for the TUI presentation adapter."""
import pytest
from clairecoder.core.events import Event
from clairecoder.tui.adapter import PresentationAdapter
from clairecoder.tui.activity import ActivityType, ActivityState

def test_tool_execution_events():
    event = Event("TOOL_REQUESTED", {"tool_name": "pytest"})
    act = PresentationAdapter.event_to_activity(event)
    assert act.type == ActivityType.TOOL
    assert act.state == ActivityState.RUNNING
    assert "pytest" in act.title
    
    event2 = Event("TOOL_COMPLETED", {"tool_name": "pytest", "result": "Passed"})
    act2 = PresentationAdapter.event_to_activity(event2)
    assert act2.state == ActivityState.COMPLETED
    assert act2.expandable_content == "Passed"

    event3 = Event("EXECUTION_FAILED", {"tool_name": "pytest", "error": "Crash", "failure_category": "TOOL_FAILURE"})
    act3 = PresentationAdapter.event_to_activity(event3)
    assert act3.state == ActivityState.FAILED
    assert act3.detail == "Crash"

def test_verification_events():
    event = Event("VALIDATION_STARTED", {})
    act = PresentationAdapter.event_to_activity(event)
    assert act.type == ActivityType.VERIFICATION
    assert act.state == ActivityState.RUNNING
    
    event2 = Event("VALIDATION_COMPLETED", {})
    act2 = PresentationAdapter.event_to_activity(event2)
    assert act2.state == ActivityState.COMPLETED

    event3 = Event("VALIDATION_FAILED", {"failures": ["c1", "c2"]})
    act3 = PresentationAdapter.event_to_activity(event3)
    assert act3.state == ActivityState.FAILED
    assert "2 criteria failed" in act3.detail

def test_permission_events():
    event = Event("PERMISSION_REQUESTED", {"tool_name": "write_file"})
    act = PresentationAdapter.event_to_activity(event)
    assert act.type == ActivityType.PERMISSION
    assert act.state == ActivityState.APPROVAL_REQUIRED
    assert "write_file" in act.detail
