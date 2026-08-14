import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from .types import EngineeringObjective, Task, TaskState, ObjectiveStatus, EngineEvent
from clairecoder.gateway.interfaces import ModelGatewayInterface
from clairecoder.gateway.types import ModelRequest, ModelResponse
from clairecoder.tools.executor import ToolExecutor
from clairecoder.core.types import ToolResult, ToolState, PermissionState
from clairecoder.context.builder import ContextBuilder
from clairecoder.context.types import EngineeringContext
from clairecoder.skills.registry import SkillRegistry

class EngineeringSession:
    """Represents the persistent state of an engineering task."""
    def __init__(self, id: str):
        self.id = id
        self.objective: Optional[EngineeringObjective] = None
        self.tasks: Dict[str, Task] = {}
        self.current_workflow: Optional[str] = None
        self.mode: Optional[str] = None
        self.model_profile: Optional[str] = None
        self.validation_state: str = "none"
        self.unresolved_issues: List[str] = []
        self.active_skills: List[str] = []

    def update_task(self, task: Task) -> None:
        self.tasks[task.id] = task

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "objective": {
                "id": self.objective.id,
                "request": self.objective.request,
                "session_id": self.objective.session_id,
                "mode": self.objective.mode,
                "model_profile_id": self.objective.model_profile_id,
                "constraints": self.objective.constraints,
                "status": self.objective.status.value,
                "workflow_id": self.objective.workflow_id,
                "completion_criteria": self.objective.completion_criteria
            } if self.objective else None,
            "tasks": {
                tid: {
                    "id": t.id,
                    "objective_id": t.objective_id,
                    "description": t.description,
                    "status": t.status.value,
                    "dependencies": t.dependencies,
                    "expected_result": t.expected_result,
                    "required_skills": t.required_skills,
                    "required_tools": t.required_tools,
                    "validation_requirements": t.validation_requirements,
                    "context_references": t.context_references
                } for tid, t in self.tasks.items()
            },
            "current_workflow": self.current_workflow,
            "mode": self.mode,
            "model_profile": self.model_profile,
            "validation_state": self.validation_state,
            "unresolved_issues": self.unresolved_issues,
            "active_skills": self.active_skills
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EngineeringSession':
        session = cls(data["id"])
        
        obj_data = data.get("objective")
        if obj_data:
            session.objective = EngineeringObjective(
                id=obj_data["id"],
                request=obj_data["request"],
                session_id=obj_data["session_id"],
                mode=obj_data.get("mode"),
                model_profile_id=obj_data.get("model_profile_id"),
                constraints=obj_data.get("constraints", []),
                status=ObjectiveStatus(obj_data["status"]),
                workflow_id=obj_data.get("workflow_id"),
                completion_criteria=obj_data.get("completion_criteria", [])
            )
            
        tasks_data = data.get("tasks", {})
        for tid, t_data in tasks_data.items():
            session.tasks[tid] = Task(
                id=t_data["id"],
                objective_id=t_data["objective_id"],
                description=t_data["description"],
                status=TaskState(t_data["status"]),
                dependencies=t_data.get("dependencies", []),
                expected_result=t_data.get("expected_result"),
                required_skills=t_data.get("required_skills", []),
                required_tools=t_data.get("required_tools", []),
                validation_requirements=t_data.get("validation_requirements", []),
                context_references=t_data.get("context_references", [])
            )
            
        session.current_workflow = data.get("current_workflow")
        session.mode = data.get("mode")
        session.model_profile = data.get("model_profile")
        session.validation_state = data.get("validation_state", "none")
        session.unresolved_issues = data.get("unresolved_issues", [])
        session.active_skills = data.get("active_skills", [])
        return session


class SubagentEngine:
    """A bounded interface for executing a sub-task."""
    def __init__(
        self,
        engine: 'EngineeringEngine',
        objective: EngineeringObjective,
        context: EngineeringContext
    ):
        self._engine = engine
        self._parent_context = context
        
        # Enforce boundary: Subagent runs in an ephemeral/isolated session 
        # so it doesn't mutate parent's objective/session by sharing ID.
        self._session_id = f"subagent_{objective.id}"
        
        # Create an isolated objective copy for the subagent
        self._objective = EngineeringObjective(
            id=f"{objective.id}_sub",
            request=objective.request,
            session_id=self._session_id,
            mode=objective.mode,
            model_profile_id=objective.model_profile_id,
            workflow_id=objective.workflow_id
        )
        self._session = self._engine.receive_objective(self._objective)

    def request_tool(self, tool_id: str, **kwargs) -> ToolResult:
        """Bounded tool request passing through the parent Engine."""
        # Note: Must pass the subagent's session/workflow info, not mutate parent.
        return self._engine.request_tool(
            tool_id,
            session_id=self._session_id,
            workflow_id=self._objective.workflow_id,
            **kwargs
        )

    def execute_model(self, task_description: str) -> ModelResponse:
        """Bounded model execution enforcing objective and context."""
        # We don't take an arbitrary ModelRequest. We construct it from the subagent's bounded state.
        context_str = (
            f"Subagent Objective: {self._objective.request}\n"
            f"Session Info: {self._parent_context.session_info}\n"
            f"Workflow Info: {self._parent_context.workflow_info}\n"
            f"Task Info: {self._parent_context.task_info}\n"
            f"Repository State: {self._parent_context.repository_state}\n"
            f"Memories: {self._parent_context.memories}\n"
            f"Tool Results: {self._parent_context.tool_results}\n"
            f"Skills: {self._parent_context.instructions}"
        )
        request = ModelRequest(
            model_id=self._objective.model_profile_id or "default-model",
            messages=[
                {
                    "role": "system",
                    "content": context_str
                },
                {
                    "role": "user",
                    "content": f"Execute Subtask: {task_description}"
                }
            ]
        )
        return self._engine.execute_model(request)


class EngineeringEngine:
    """Central orchestration layer of ClaireCoder."""
    
    def __init__(
        self,
        model_gateway: ModelGatewayInterface,
        tool_executor: ToolExecutor,
        skill_registry: Optional[SkillRegistry] = None,
        event_callback: Optional[Callable[[EngineEvent, Dict[str, Any]], None]] = None
    ):
        self._model_gateway = model_gateway
        self._tool_executor = tool_executor
        self._skill_registry = skill_registry
        self._event_callback = event_callback
        self._sessions: Dict[str, EngineeringSession] = {}
        
    def _emit(self, event: EngineEvent, data: Dict[str, Any] = None):
        """Emit a structured progress event to the Interaction Layer."""
        if self._event_callback:
            self._event_callback(event, data or {})

    # =========================================================================
    # SESSION MANAGEMENT (PERSISTENCE & RESUMPTION)
    # =========================================================================

    def receive_objective(self, objective: EngineeringObjective) -> EngineeringSession:
        """Intake an engineering objective and create/update session."""
        session = self._sessions.get(objective.session_id)
        if not session:
            session = EngineeringSession(objective.session_id)
            self._sessions[objective.session_id] = session
            
        session.objective = objective
        session.mode = objective.mode
        session.model_profile = objective.model_profile_id
        
        self._emit(EngineEvent.OBJECTIVE_STARTED, {"objective_id": objective.id})
        return session

    def save_session(self, session_id: str, directory: str = ".clairecoder/sessions") -> None:
        """Persist an EngineeringSession to local storage."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        file_path = path / f"{session_id}.json"
        
        with file_path.open("w") as f:
            json.dump(session.to_dict(), f)

    def resume_session(self, session_id: str, directory: str = ".clairecoder/sessions") -> EngineeringSession:
        """Load and resume a persisted EngineeringSession."""
        path = Path(directory) / f"{session_id}.json"
        if not path.exists():
            raise ValueError(f"No persisted session found for {session_id}")
            
        with path.open("r") as f:
            data = json.load(f)
            
        session = EngineeringSession.from_dict(data)
        self._sessions[session_id] = session
        return session
        
    def get_session(self, session_id: str) -> Optional[EngineeringSession]:
        """Retrieve an existing session."""
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        """Remove a session from memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]

    # =========================================================================
    # SUBAGENT BOUNDARY
    # =========================================================================
    
    def create_subagent(self, objective: EngineeringObjective, context: EngineeringContext) -> SubagentEngine:
        """Create a bounded subagent for a specific objective and context."""
        return SubagentEngine(self, objective, context)

    # =========================================================================
    # SKILL INTEGRATION
    # =========================================================================

    def load_skill(self, session_id: str, skill_id: str) -> None:
        """Activate a skill for the given session using SkillRegistry."""
        if not self._skill_registry:
            raise RuntimeError("SkillRegistry is not configured in EngineeringEngine")
            
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
            
        # This will raise if skill doesn't exist or is not enabled
        # according to the registry's own mechanisms
        skill = self._skill_registry.get_enabled(skill_id)
        if skill_id not in session.active_skills:
            session.active_skills.append(skill_id)

    # =========================================================================
    # CONTEXT INTEGRATION
    # =========================================================================

    def assemble_context(self, session_id: str, task_id: Optional[str] = None) -> EngineeringContext:
        """Assemble context using ContextBuilder."""
        session = self._sessions.get(session_id)
        builder = ContextBuilder()
        builder.with_session({"session_id": session_id})
        
        if session:
            if session.objective:
                builder.with_session({"objective_id": session.objective.id})
                
            for skill_id in session.active_skills:
                # Retrieve skill context if registry is available
                if self._skill_registry:
                    skill = self._skill_registry.get_enabled(skill_id)
                    builder.add_instruction(skill.instructions)
                        
        if task_id:
            builder.with_task({"task_id": task_id})
            
        return builder.build()

    # =========================================================================
    # UNDERSTAND STAGE
    # =========================================================================

    def understand(self, session_id: str) -> Dict[str, Any]:
        """Transform an objective + context into a plan/understanding via Model Gateway."""
        session = self.get_session(session_id)
        if not session or not session.objective:
            raise ValueError("Session or objective missing")
            
        context = self.assemble_context(session_id)
        
        # The model request includes relevant assembled context
        request = ModelRequest(
            model_id=session.model_profile or "default-model",
            messages=[
                {"role": "system", "content": f"Understand Objective: {session.objective.request}\nContext Information: {context.session_info}\nSkills/Instructions: {context.instructions}"},
                {"role": "user", "content": "Analyze objective and prepare understanding."}
            ]
        )
        response = self.execute_model(request)
        
        return {"understanding": response.text, "structured_output": response.structured_output}

    # =========================================================================
    # MODEL & TOOL INTERACTION LOOP
    # =========================================================================

    def execute_model(self, request: ModelRequest) -> ModelResponse:
        """Interact with the Model Gateway."""
        return self._model_gateway.execute(request)

    def request_tool(
        self, tool_id: str, session_id: Optional[str] = None, 
        workflow_id: Optional[str] = None, task_id: Optional[str] = None, 
        **kwargs
    ) -> ToolResult:
        """Coordinate ToolExecutor invocation with correct context propagation."""
        self._emit(EngineEvent.TOOL_REQUESTED, {"tool_id": tool_id})
        
        # We forward the context to the ToolExecutor boundary (which passes it to PermissionEngine)
        result = self._tool_executor.invoke(
            tool_id, 
            session_id=session_id, 
            workflow_id=workflow_id, 
            task_id=task_id, 
            **kwargs
        )
        
        if result.state == ToolState.DENIED and result.metadata.get("requires_confirmation"):
            self._emit(EngineEvent.PERMISSION_REQUESTED, {
                "tool_id": tool_id, 
                "action": result.metadata.get("action"), 
                "resource": result.metadata.get("resource")
            })
            
        self._emit(EngineEvent.TOOL_COMPLETED, {"tool_id": tool_id, "state": result.state})
        return result

    def interaction_loop(self, session_id: str, task_id: str, max_iterations: int = 5) -> "ExecutionResult":
        """A complete Phase 7 Model Interaction Loop (Model -> Tool -> Result -> Model).
        
        Tool results must not be discarded. They are fed back into the next model request.
        """
        from clairecoder.execution.types import ExecutionResult, ExecutionResultCategory, FailureCategory
        
        session = self.get_session(session_id)
        if not session or task_id not in session.tasks:
            return ExecutionResult(
                category=ExecutionResultCategory.FAILURE,
                failure_category=FailureCategory.UNKNOWN_FAILURE,
                error_message="Task or session not found"
            )
            
        task = session.tasks[task_id]
        
        # Maintain execution history within the loop
        interaction_history = [
            {"role": "user", "content": f"Task: {task.description}"}
        ]
        
        for _ in range(max_iterations):
            # Assemble immutable context snapshot for this iteration
            context = self.assemble_context(session_id, task_id)
            
            # Combine assembled context with the interaction history
            messages = [
                {"role": "system", "content": f"Context: {context.session_info}\nSkills: {context.instructions}"}
            ] + interaction_history
            
            request = ModelRequest(
                model_id=session.model_profile or "default-model",
                messages=messages
            )
            response = self.execute_model(request)
            
            # Record model's response in history
            if response.text:
                interaction_history.append({"role": "assistant", "content": response.text})
            
            if response.tool_calls:
                # Add tool_calls array to the interaction history (conceptually)
                interaction_history.append({"role": "assistant", "tool_calls": response.tool_calls})
                
                tool_results_for_history = []
                
                for tc in response.tool_calls:
                    tool_res = self.request_tool(
                        tool_id=tc.get("name"),
                        session_id=session_id,
                        workflow_id=session.current_workflow,
                        task_id=task_id,
                        **tc.get("arguments", {})
                    )
                    
                    # Store tool result for the next iteration model continuation
                    tool_results_for_history.append({
                        "role": "tool",
                        "name": tc.get("name"),
                        "content": str(tool_res.output) if tool_res.state == ToolState.SUCCESS else str(tool_res.error)
                    })
                    
                # Feed ToolResults back into interaction history
                interaction_history.extend(tool_results_for_history)
            else:
                # No tools requested, model considers task done
                return ExecutionResult(category=ExecutionResultCategory.SUCCESS)
                
        return ExecutionResult(
            category=ExecutionResultCategory.TIMEOUT,
            failure_category=FailureCategory.TIMEOUT,
            error_message=f"Interaction loop exceeded max iterations ({max_iterations})"
        )

    # =========================================================================
    # PLANNING AND STATE (BOUNDED TO PRD-001)
    # =========================================================================

    def plan_tasks(self, session_id: str, tasks: List[Task]) -> None:
        """Coordinate a planning stage."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
            
        self._emit(EngineEvent.PLANNING_STARTED, {"session_id": session_id})
        for task in tasks:
            session.update_task(task)
        self._emit(EngineEvent.PLANNING_COMPLETED, {"session_id": session_id, "tasks": [t.id for t in tasks]})

    def start_task(self, session_id: str, task_id: str) -> None:
        """Transition a task to RUNNING."""
        session = self._sessions.get(session_id)
        if session and task_id in session.tasks:
            task = session.tasks[task_id]
            task.status = TaskState.RUNNING
            self._emit(EngineEvent.TASK_STARTED, {"task_id": task_id})

    def validate_task(self, session_id: str, task_id: str, passed: bool, failure_reason: Optional[str] = None) -> None:
        """Coordinate validation and update task state accordingly."""
        session = self._sessions.get(session_id)
        if not session or task_id not in session.tasks:
            return
            
        self._emit(EngineEvent.VALIDATION_STARTED, {"task_id": task_id})
        task = session.tasks[task_id]
        if passed:
            task.status = TaskState.SUCCEEDED
            self._emit(EngineEvent.VALIDATION_COMPLETED, {"task_id": task_id, "passed": True})
            self._emit(EngineEvent.TASK_COMPLETED, {"task_id": task_id})
        else:
            task.status = TaskState.FAILED
            task.failure_state = failure_reason
            self._emit(EngineEvent.VALIDATION_COMPLETED, {"task_id": task_id, "passed": False})
            
            # Boundary signal: Replanning is required. (Phase 7 does not implement the Workflow Replanner)
            self._emit(EngineEvent.REPLANNING_STARTED, {"task_id": task_id})

    def fail_task(self, session_id: str, task_id: str, failure_reason: str) -> None:
        """Mark task as failed and trigger replanning."""
        session = self._sessions.get(session_id)
        if session and task_id in session.tasks:
            task = session.tasks[task_id]
            task.status = TaskState.FAILED
            task.failure_state = failure_reason
            self._emit(EngineEvent.REPLANNING_STARTED, {"task_id": task_id})

    def complete_objective(self, session_id: str) -> None:
        """Mark objective as complete."""
        session = self._sessions.get(session_id)
        if session and session.objective:
            session.objective.status = ObjectiveStatus.COMPLETED
            self._emit(EngineEvent.OBJECTIVE_COMPLETED, {"objective_id": session.objective.id})

    def fail_objective(self, session_id: str) -> None:
        """Mark objective as failed."""
        session = self._sessions.get(session_id)
        if session and session.objective:
            session.objective.status = ObjectiveStatus.FAILED
            self._emit(EngineEvent.EXECUTION_FAILED, {"objective_id": session.objective.id})

    def interrupt_execution(self, session_id: str) -> None:
        """Interrupt active execution."""
        self._emit(EngineEvent.EXECUTION_PAUSED, {"session_id": session_id})
        
    def cancel_objective(self, session_id: str) -> None:
        """Cancel execution entirely."""
        session = self._sessions.get(session_id)
        if session and session.objective:
            session.objective.status = ObjectiveStatus.CANCELLED
            self._emit(EngineEvent.EXECUTION_CANCELLED, {"objective_id": session.objective.id})
