"""Presentation adapter translating core events to activity models."""
from typing import Optional, Any, Dict
from clairecoder.core.events import Event
from .activity import ActivityModel, ActivityType, ActivityState, DiffInfo, DiffLine


class PresentationAdapter:
    """Adapts application events/state to presentation activities.
    
    Does NOT infer from text.
    Relies on semantic event data.
    """
    
    @staticmethod
    def event_to_activity(event: Event) -> ActivityModel:
        event_name = event.name.upper()
        activity = ActivityModel(title=f"Event {event_name}")
        
        # Tool Activity mapping
        if event_name == "TOOL_REQUESTED":
            activity.type = ActivityType.TOOL
            activity.state = ActivityState.RUNNING
            tool_name = event.payload.get("tool_name", "tool")
            activity.title = f"Running {tool_name}"
            activity.correlation_key = f"tool_{event.payload.get('request_id')}"
            
        elif event_name == "TOOL_COMPLETED":
            activity.type = ActivityType.TOOL
            tool_state = event.payload.get("state")
            tool_name = event.payload.get("tool_name", "tool")
            
            if tool_state == "failure":
                activity.state = ActivityState.FAILED
                activity.title = f"Failed {tool_name}"
            elif tool_state == "denied":
                metadata = event.payload.get("metadata", {})
                if metadata.get("requires_confirmation"):
                    activity.state = ActivityState.APPROVAL_REQUIRED
                    activity.title = "Approval required"
                    activity.type = ActivityType.PERMISSION
                    activity.detail = f"ClaireCoder wants to run: {tool_name}"
                else:
                    activity.state = ActivityState.FAILED
                    activity.title = f"Denied {tool_name}"
            else:
                activity.state = ActivityState.COMPLETED
                activity.title = f"Completed {tool_name}"
                
            result = event.payload.get("result")
            if result:
                activity.expandable_content = str(result)
            # Use detail for error message if it's a failure
            if tool_state == "failure" and result:
                activity.detail = str(result)
                
            activity.correlation_key = f"tool_{event.payload.get('request_id')}"
            activity.updates_activity = True
            
        elif event_name == "EXECUTION_FAILED" and event.payload.get("failure_category") == "TOOL_FAILURE":
            activity.type = ActivityType.TOOL
            activity.state = ActivityState.FAILED
            tool_name = event.payload.get("tool_name", "tool")
            activity.title = f"Failed {tool_name}"
            activity.detail = event.payload.get("error", "Unknown error")
            activity.correlation_key = f"tool_{event.payload.get('request_id')}"
            activity.updates_activity = True
            
        # Permission Activity mapping
        elif event_name == "PERMISSION_REQUESTED":
            activity.type = ActivityType.PERMISSION
            activity.state = ActivityState.APPROVAL_REQUIRED
            activity.title = "Approval required"
            tool = event.payload.get("tool_name") or event.payload.get("tool_id") or "tool"
            command = event.payload.get("command")
            if command:
                activity.detail = f"ClaireCoder wants to run:\n    $ {command}"
            else:
                action = event.payload.get("action", "")
                resource = event.payload.get("resource", "")
                if action and resource:
                    activity.detail = f"ClaireCoder wants to run:\n    $ {tool} {action} {resource}"
                else:
                    activity.detail = f"ClaireCoder wants to run: {tool}"
            
            diff_data = event.payload.get("diff_info")
            if diff_data:
                if isinstance(diff_data, DiffInfo):
                    activity.diff_info = diff_data
                elif isinstance(diff_data, dict):
                    lines = [DiffLine(type=l.get("type", "context"), content=l.get("content", "")) for l in diff_data.get("lines", [])]
                    activity.diff_info = DiffInfo(summary=diff_data.get("summary", ""), lines=lines)
            
            activity.correlation_key = f"tool_{event.payload.get('request_id')}"
            activity.updates_activity = True
            activity.metadata = event.payload

        elif event_name in ("PERMISSION_RESOLVED", "PERMISSION_GRANTED", "PERMISSION_APPROVED"):
            decision = event.payload.get("decision", "granted")
            activity.type = ActivityType.PERMISSION
            activity.correlation_key = f"tool_{event.payload.get('request_id')}"
            activity.updates_activity = True
            activity.metadata = event.payload
            tool = event.payload.get("tool_name") or event.payload.get("tool_id") or "tool"
            command = event.payload.get("command")
            target = command or tool
            
            if decision in ("granted", "approved", "always", "session"):
                activity.state = ActivityState.COMPLETED
                scope = event.payload.get("scope")
                if scope == "session":
                    activity.title = "Permission approved (session-scoped)"
                else:
                    activity.title = "Permission approved"
                activity.detail = f"Running {target}"
            elif decision in ("denied", "no"):
                activity.state = ActivityState.FAILED
                activity.title = "Permission denied"
                activity.detail = "Command was not executed."
            elif decision in ("cancelled", "cancel"):
                activity.state = ActivityState.BLOCKED
                activity.title = "Permission cancelled"
                activity.detail = "Request closed without authorization."
            else:
                activity.state = ActivityState.COMPLETED
                activity.title = f"Permission {decision}"
                activity.detail = f"Status: {decision}"

        elif event_name == "PERMISSION_DENIED":
            activity.type = ActivityType.PERMISSION
            activity.state = ActivityState.FAILED
            activity.title = "Permission denied"
            activity.detail = "Command was not executed."
            activity.correlation_key = f"tool_{event.payload.get('request_id')}"
            activity.updates_activity = True
            activity.metadata = event.payload

        elif event_name == "PERMISSION_CANCELLED":
            activity.type = ActivityType.PERMISSION
            activity.state = ActivityState.BLOCKED
            activity.title = "Permission cancelled"
            activity.detail = "Request closed without authorization."
            activity.correlation_key = f"tool_{event.payload.get('request_id')}"
            activity.updates_activity = True
            activity.metadata = event.payload

            
        # Verification Activity mapping
        elif event_name == "VALIDATION_STARTED":
            activity.type = ActivityType.VERIFICATION
            activity.state = ActivityState.RUNNING
            activity.title = "Verification running"
            activity.correlation_key = f"val_{event.payload.get('task_id')}"
            
        elif event_name == "VALIDATION_COMPLETED":
            activity.type = ActivityType.VERIFICATION
            activity.state = ActivityState.COMPLETED
            activity.title = "Verification passed"
            if event.payload.get("passed", True):
                activity.detail = "All required criteria satisfied."
            else:
                activity.state = ActivityState.FAILED
                activity.title = "Verification failed"
            activity.correlation_key = f"val_{event.payload.get('task_id')}"
            activity.updates_activity = True
            
        elif event_name == "VALIDATION_FAILED":
            activity.type = ActivityType.VERIFICATION
            activity.state = ActivityState.FAILED
            activity.title = "Verification failed"
            failures = event.payload.get("failures", [])
            activity.detail = f"{len(failures)} criteria failed."
            activity.correlation_key = f"val_{event.payload.get('task_id')}"
            activity.updates_activity = True
            
        # Objective Mapping
        elif event_name == "OBJECTIVE_STARTED":
            activity.type = ActivityType.THINKING
            activity.state = ActivityState.RUNNING
            activity.title = "Starting objective"
            activity.correlation_key = f"obj_{event.payload.get('objective_id')}"
            
        elif event_name == "OBJECTIVE_COMPLETED":
            activity.type = ActivityType.SUCCESS
            activity.state = ActivityState.COMPLETED
            activity.title = "Objective completed"
            activity.correlation_key = f"obj_{event.payload.get('objective_id')}"
            activity.updates_activity = True
            
        elif event_name == "EXECUTION_CANCELLED":
            activity.type = ActivityType.WARNING
            activity.state = ActivityState.COMPLETED
            activity.title = "Execution cancelled"
            activity.correlation_key = f"obj_{event.payload.get('objective_id')}"
            activity.updates_activity = True
            
        elif event_name == "EXECUTION_FAILED" and event.payload.get("failure_category") != "TOOL_FAILURE":
            activity.type = ActivityType.ERROR
            activity.state = ActivityState.FAILED
            activity.title = "Execution failed"
            activity.correlation_key = f"obj_{event.payload.get('objective_id')}"
            activity.updates_activity = True

        # Planning Mapping
        elif event_name == "PLANNING_STARTED":
            activity.type = ActivityType.THINKING
            activity.state = ActivityState.RUNNING
            activity.title = "Planning changes"
            activity.correlation_key = f"plan_{event.payload.get('session_id')}"
            
        elif event_name == "PLANNING_COMPLETED":
            activity.type = ActivityType.MESSAGE
            activity.state = ActivityState.COMPLETED
            activity.title = "Plan ready"
            activity.correlation_key = f"plan_{event.payload.get('session_id')}"
            activity.updates_activity = True
            
        elif event_name == "REPLANNING_STARTED":
            activity.type = ActivityType.THINKING
            activity.state = ActivityState.RUNNING
            activity.title = "Replanning"
            activity.correlation_key = f"replan_{event.payload.get('task_id')}"
            
        # Task Mapping
        elif event_name == "TASK_STARTED":
            activity.type = ActivityType.MESSAGE
            activity.state = ActivityState.RUNNING
            activity.title = f"Working on task {event.payload.get('task_id')}"
            activity.correlation_key = f"task_{event.payload.get('task_id')}"
            
        elif event_name == "TASK_COMPLETED":
            activity.type = ActivityType.MESSAGE
            activity.state = ActivityState.COMPLETED
            activity.title = f"Completed task {event.payload.get('task_id')}"
            activity.correlation_key = f"task_{event.payload.get('task_id')}"
            activity.updates_activity = True

        # Execution Mapping
        elif event_name == "EXECUTION_PAUSED":
            activity.type = ActivityType.WARNING
            activity.state = ActivityState.BLOCKED
            activity.title = "Execution paused"
            activity.correlation_key = f"pause_{event.payload.get('session_id')}"
            
        return activity
