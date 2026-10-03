import json
import re
import platform
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


_MODEL_TOOL_NAMES = {
    "filesystem.read": "read_file",
    "filesystem.write": "write_file",
    "filesystem.replace": "replace_file_content",
    "filesystem.list": "list_files",
    "filesystem.delete": "delete_file",
    "search.text": "search_text",
    "shell.execute": "run_command",
    "git.status": "git_status",
    "git.commit": "git_commit",
    "testing.run": "run_tests",
    "diagnostics.lint": "run_diagnostics",
}


def _model_tool_name(tool_id: str) -> str:
    """Return a provider-safe function name while preserving the registry ID."""
    known_name = _MODEL_TOOL_NAMES.get(tool_id)
    if known_name:
        return known_name
    return re.sub(r"[^a-zA-Z0-9_-]", "_", tool_id)[:64] or "tool"


def _extract_single_code_block(text: str) -> Optional[str]:
    """Return one complete fenced code block, avoiding guesses from prose."""
    blocks = re.findall(r"```[^\r\n]*\r?\n(.*?)```", text or "", flags=re.DOTALL)
    if len(blocks) != 1:
        return None
    content = blocks[0].strip("\r\n")
    return content if content.strip() else None


def _infer_new_code_path(objective: str, expected_outputs: List[str]) -> Optional[str]:
    """Resolve a safe requested filename or choose one for a simple code task."""
    path_pattern = re.compile(r"(?:[A-Za-z0-9_.-]+[/\\])*[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8}")
    for source in [*expected_outputs, objective]:
        for match in path_pattern.findall(str(source or "")):
            normalized = match.replace("\\", "/")
            path = Path(normalized)
            if not path.is_absolute() and all(part not in (".", "..") for part in path.parts):
                return path.as_posix()

    text = (objective or "").lower()
    if not re.search(r"\b(write|create|generate|make)\b", text) or not re.search(r"\b(code|program|script)\b", text):
        return None

    extensions = {
        "python": "py", "javascript": "js", "typescript": "ts", "java": "java",
        "rust": "rs", "golang": "go", "go": "go", "ruby": "rb", "php": "php",
        "c++": "cpp", "c#": "cs", "kotlin": "kt", "swift": "swift",
    }
    extension = next(
        (
            ext for language, ext in extensions.items()
            if re.search(
                rf"(?<![a-z0-9]){re.escape(language)}(?![a-z0-9])",
                text,
            )
        ),
        None,
    )
    if not extension:
        return None

    ignored = {
        "write", "create", "generate", "make", "code", "program", "script", "function",
        "class", "file", "for", "in", "using", "with", "a", "an", "the", "to",
        *extensions.keys(),
    }
    words = re.findall(r"[a-z0-9]+", text)
    stem_words = [word for word in words if word not in ignored]
    stem = "-".join(stem_words[:3]) or "main"
    return f"{stem}.{extension}"

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
        sess_id = data.get("id") or data.get("session_id") or ""
        session = cls(sess_id)
        
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
        model_id = self._objective.model_profile_id
        if not model_id:
            gw = getattr(self._engine, "_model_gateway", None)
            if gw and hasattr(gw, "_models") and isinstance(gw._models, dict) and gw._models:
                model_id = next(iter(gw._models.keys()))
            elif gw and type(gw).__name__ != "ModelGateway" and hasattr(gw, "execute"):
                model_id = "test-model"
            else:
                from clairecoder.gateway.types import ModelError
                raise ModelError("No active model configured. Please configure a provider via /model or the setup wizard.")
        request = ModelRequest(
            model_id=model_id,
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
        self._event_subscribers: List[Callable[[EngineEvent, Dict[str, Any]], None]] = []
        self.permission_wait_timeout_seconds = 300.0
        if event_callback:
            self._event_subscribers.append(event_callback)
        self._sessions: Dict[str, EngineeringSession] = {}
        
    def subscribe(self, callback: Callable[[EngineEvent, Dict[str, Any]], None]) -> None:
        """Register a public event subscriber."""
        if callback not in self._event_subscribers:
            self._event_subscribers.append(callback)
            
    def unsubscribe(self, callback: Callable[[EngineEvent, Dict[str, Any]], None]) -> None:
        """Remove a public event subscriber."""
        if callback in self._event_subscribers:
            self._event_subscribers.remove(callback)

    def _emit(self, event: EngineEvent, data: Dict[str, Any] = None):
        """Emit a structured progress event to the Interaction Layer."""
        for callback in self._event_subscribers:
            callback(event, data or {})

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
        if objective.model_profile_id:
            session.model_profile = objective.model_profile_id
        elif not session.model_profile:
            gw = self._model_gateway
            if hasattr(gw, "_models") and isinstance(gw._models, dict) and gw._models:
                session.model_profile = next(iter(gw._models.keys()))
            elif gw and type(gw).__name__ != "ModelGateway" and hasattr(gw, "execute"):
                session.model_profile = "test-model"
            
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
        
        model_id = session.model_profile or getattr(session.objective, "model_profile_id", None)
        if not model_id:
            gw = self._model_gateway
            if hasattr(gw, "_models") and isinstance(gw._models, dict) and gw._models:
                model_id = next(iter(gw._models.keys()))
            elif gw and type(gw).__name__ != "ModelGateway" and hasattr(gw, "execute"):
                model_id = "test-model"
            else:
                from clairecoder.gateway.types import ModelError
                raise ModelError("No active model configured. Please configure a provider via /model or the setup wizard.")

        # The model request includes relevant assembled context
        request = ModelRequest(
            model_id=model_id,
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
        tool_call_id: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """Coordinate ToolExecutor invocation with correct context propagation."""
        import uuid
        request_id = tool_call_id or str(uuid.uuid4())
        self._emit(EngineEvent.TOOL_REQUESTED, {
            "tool_id": tool_id,
            "tool_name": tool_id,
            "request_id": request_id,
            "tool_call_id": request_id,
            # Expose only safe operation targets for live TUI activity labels;
            # never copy file contents or arbitrary argument payloads here.
            "path": kwargs.get("path"),
            "command": kwargs.get("command"),
            "target": kwargs.get("target"),
        })
        
        # We forward the context to the ToolExecutor boundary (which passes it to PermissionEngine)
        result = self._tool_executor.invoke(
            tool_id, 
            session_id=session_id, 
            workflow_id=workflow_id, 
            task_id=task_id, 
            tool_call_id=request_id,
            **kwargs
        )
        
        if result.state == ToolState.DENIED and result.metadata.get("requires_confirmation"):
            permission_request_id = result.metadata.get("request_id", request_id)
            self._emit(EngineEvent.PERMISSION_REQUESTED, {
                "tool_id": tool_id, 
                "tool_name": tool_id,
                "request_id": permission_request_id,
                "tool_call_id": request_id,
                "action": result.metadata.get("action"), 
                "resource": result.metadata.get("resource"),
                "command": result.metadata.get("command"),
                "reason": result.metadata.get("reason"),
                "category": result.metadata.get("category"),
                "session_id": session_id,
                "metadata": result.metadata
            })
            
        completion_request_id = (
            result.metadata.get("request_id", request_id)
            if result.metadata.get("requires_confirmation")
            else request_id
        )
        self._emit(EngineEvent.TOOL_COMPLETED, {
            "tool_id": tool_id, 
            "tool_name": tool_id,
            "request_id": completion_request_id,
            "tool_call_id": request_id,
            "session_id": session_id,
            "action": result.metadata.get("action"),
            "resource": result.metadata.get("resource"),
            "state": result.state,
            "result": result.output if result.state == ToolState.SUCCESS else result.error,
            "metadata": result.metadata
        })
        return result


    def grant_session_permission(
        self,
        session_id: str,
        tool_id: Optional[str] = None,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        category: Optional[str] = None,
        resource_scope: Optional[str] = None,
        priority: int = 50
    ) -> Any:
        """Public method to grant session-scoped authorization via ToolExecutor -> PermissionEngine."""
        from clairecoder.permissions.types import PermissionCategory, ResourceScope
        cat_enum = PermissionCategory(category) if category else None
        scope_enum = ResourceScope(resource_scope) if resource_scope else None
        return self._tool_executor.grant_session_permission(
            session_id=session_id,
            tool_id=tool_id,
            operation=operation,
            resource=resource,
            category=cat_enum,
            resource_scope=scope_enum,
            priority=priority
        )

    def resolve_permission(
        self,
        request_id: str,
        decision: str,
        session_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        command: Optional[str] = None,
        category: Optional[str] = None
    ) -> ToolResult:
        """Resolve a permission and execute its stored invocation when approved."""
        norm_decision = str(decision).lower()
        permission_tool = self._tool_executor.get_pending(request_id)
        result = self._tool_executor.resolve_permission(request_id, norm_decision)

        resolved_decision = "granted" if norm_decision in (
            "always", "always_session", "approve", "granted", "yes", "y"
        ) else "denied" if norm_decision in ("deny", "denied", "no", "n") else "cancelled"
        event_data = {
            "request_id": request_id,
            "decision": resolved_decision,
            "scope": "session" if norm_decision in ("always", "always_session") else "once",
            "session_id": session_id or getattr(permission_tool, "session_id", None),
            "tool_id": tool_id or getattr(permission_tool, "tool_id", None),
            "tool_name": tool_id or getattr(permission_tool, "tool_id", None),
            "task_id": getattr(permission_tool, "task_id", None),
            "tool_call_id": getattr(permission_tool, "tool_call_id", None),
            "action": action or getattr(permission_tool, "action", None),
            "resource": resource or getattr(permission_tool, "resource", None),
            "command": command,
        }
        if permission_tool is not None:
            self._emit(EngineEvent.TOOL_COMPLETED, {
                **event_data,
                "request_id": getattr(permission_tool, "tool_call_id", None) or request_id,
                "state": result.state,
                "result": result.output if result.state == ToolState.SUCCESS else result.error,
                "metadata": result.metadata,
            })
        self._emit(EngineEvent.PERMISSION_RESOLVED, event_data)
        return result


    def interaction_loop(self, session_id: str, task_id: str, max_iterations: int = 12) -> "ExecutionResult":
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
        task_type = getattr(task.type, "value", str(task.type))
        objective_text = session.objective.request if session.objective else task.description
        task_brief = (
            f"Overall objective: {objective_text}\n"
            f"Task title: {task.title or task.id}\n"
            f"Task type: {task_type}\n"
            f"Task: {task.description}\n"
            f"Expected outputs: {task.expected_outputs}\n"
            f"Validation requirements: {task.validation or task.validation_requirements}"
        )
        implementation_task = task_type in {"implementation", "refactor", "documentation"}
        workspace_root = None
        try:
            from clairecoder.tools.core import get_workspace_root
            workspace_root = str(get_workspace_root())
        except Exception:
            pass
        platform_name = platform.system() or "unknown"
        shell_name = "Windows PowerShell" if platform_name == "Windows" else "POSIX shell"
        system_prompt = (
            "You are ClaireCoder, the engineering agent working inside the user's project workspace. "
            "Use the available tools to inspect files and carry out the task. Keep all file changes "
            f"inside the workspace ({workspace_root or 'the configured project directory'}). "
            f"The execution platform is {platform_name}; shell commands use {shell_name} syntax. "
            "Use filesystem tools to inspect files and the provided workspace context instead of "
            "running shell commands just to discover the current directory. Tool results, including "
            "permission decisions, are authoritative. "
            "Do not claim that a file changed unless a file tool reports success.\n\n"
        )
        if implementation_task:
            system_prompt += (
                "This is an implementation task. Read the relevant project files, make the requested "
                "code or documentation changes with the file tools, then run relevant checks with the "
                "available command tools. If the request does not name a file, choose a clear conventional "
                "file name in the workspace. Call the file tools; a prose proposal alone does not complete "
                "the task."
            )
        else:
            system_prompt += (
                "This task is not classified as implementation. Inspect and report as requested; "
                "do not edit files unless the task explicitly requires it."
            )
        interaction_history = [{"role": "user", "content": task_brief}]
        successful_mutation = False
        tool_operation_blocked = False
        no_tool_response_retries = 0
        
        # Build tool definitions from available tools in registry
        tools_decl = []
        tool_name_to_id: Dict[str, str] = {}
        if self._tool_executor and hasattr(self._tool_executor, "_registry") and self._tool_executor._registry:
            for tool in self._tool_executor._registry.list_available():
                registry_id = tool.metadata.id
                model_name = _model_tool_name(registry_id)
                tool_name_to_id[model_name] = registry_id
                tool_name_to_id[registry_id] = registry_id
                props = {}
                req_fields = []
                for k, v in tool.metadata.input_schema.items():
                    if isinstance(v, dict):
                        props[k] = {"type": v.get("type", "string"), "description": v.get("description", k)}
                        if v.get("required"):
                            req_fields.append(k)
                    else:
                        props[k] = {"type": "string"}
                tools_decl.append({
                    "type": "function",
                    "function": {
                        "name": model_name,
                        "description": tool.metadata.description,
                        "parameters": {
                            "type": "object",
                            "properties": props,
                            "required": req_fields,
                        }
                    }
                })

        model_id = session.model_profile or getattr(session.objective, "model_profile_id", None)
        if not model_id:
            gw = self._model_gateway
            if hasattr(gw, "_models") and isinstance(gw._models, dict) and gw._models:
                model_id = next(iter(gw._models.keys()))
            elif gw and type(gw).__name__ != "ModelGateway" and hasattr(gw, "execute"):
                model_id = "test-model"
            else:
                from clairecoder.gateway.types import ModelError
                raise ModelError("No active model configured. Please configure a provider via /model or the setup wizard.")

        for _ in range(max_iterations):
            # Check cancellation / pause state before model execution
            if session.objective and session.objective.status in (ObjectiveStatus.PAUSED, ObjectiveStatus.CANCELLED, ObjectiveStatus.FAILED):
                return ExecutionResult(
                    category=ExecutionResultCategory.CANCELLED,
                    failure_category=FailureCategory.USER_CANCELLATION,
                    error_message="Execution interrupted or cancelled by user",
                )

            # Assemble immutable context snapshot for this iteration
            context = self.assemble_context(session_id, task_id)
            
            # Combine assembled context with the interaction history
            messages = [
                {"role": "system", "content": f"{system_prompt}\n\nContext: {context.session_info}\nSkills: {context.instructions}"}
            ] + interaction_history
            
            request = ModelRequest(
                model_id=model_id,
                messages=messages,
                tools=tools_decl if tools_decl else None
            )
            response = self.execute_model(request)
            
            if response.tool_calls:
                # Keep assistant content and tool calls in one message. This is
                # required by OpenAI-compatible tool-call history formats.
                import uuid
                normalized_calls = []
                for tc in response.tool_calls:
                    call = dict(tc) if isinstance(tc, dict) else {"name": str(tc), "arguments": {}}
                    if not call.get("id"):
                        call["id"] = str(uuid.uuid4())
                    normalized_calls.append(call)
                interaction_history.append({
                    "role": "assistant",
                    "content": response.text or "",
                    "tool_calls": normalized_calls,
                })
                
                tool_results_for_history = []
                
                for tc in normalized_calls:
                    # Check cancellation before each tool call
                    if session.objective and session.objective.status in (ObjectiveStatus.PAUSED, ObjectiveStatus.CANCELLED, ObjectiveStatus.FAILED):
                        return ExecutionResult(
                            category=ExecutionResultCategory.CANCELLED,
                            failure_category=FailureCategory.USER_CANCELLATION,
                            error_message="Execution interrupted or cancelled by user",
                        )

                    if isinstance(tc, dict):
                        fn = tc.get("function", {})
                        model_tool_name = tc.get("name") or fn.get("name")
                        raw_args = tc.get("arguments") or fn.get("arguments")
                        if isinstance(raw_args, str):
                            try:
                                kwargs_dict = json.loads(raw_args)
                            except Exception:
                                kwargs_dict = {}
                        elif isinstance(raw_args, dict):
                            kwargs_dict = raw_args
                        else:
                            kwargs_dict = {}
                    else:
                        model_tool_name = str(tc)
                        kwargs_dict = {}

                    tool_name = tool_name_to_id.get(model_tool_name, model_tool_name)
                    tool_call_id = tc.get("id") or tc.get("tool_call_id")
                    tool_res = self.request_tool(
                        tool_id=tool_name,
                        session_id=session_id,
                        workflow_id=session.current_workflow,
                        task_id=task_id,
                        tool_call_id=tool_call_id,
                        **kwargs_dict
                    )

                    if tool_res.state == ToolState.DENIED and tool_res.metadata.get("requires_confirmation"):
                        permission_request_id = tool_res.metadata.get("request_id")
                        wait_for_permission = getattr(self._tool_executor, "wait_for_permission", None)
                        if permission_request_id and callable(wait_for_permission):
                            resolved_result = wait_for_permission(
                                permission_request_id,
                                timeout=self.permission_wait_timeout_seconds,
                            )
                            if resolved_result is None:
                                expire_permission = getattr(self._tool_executor, "expire_permission", None)
                                if callable(expire_permission):
                                    expire_permission(permission_request_id)
                                return ExecutionResult(
                                    category=ExecutionResultCategory.FAILURE,
                                    failure_category=FailureCategory.TIMEOUT,
                                    error_message=(
                                        "No permission decision was received for a requested tool. "
                                        "Run ClaireCoder in an interactive terminal to approve file and command actions."
                                    ),
                                    task_id=task_id,
                                )
                            tool_res = resolved_result

                    if tool_res.state == ToolState.SUCCESS:
                        try:
                            resolved_tool = self._tool_executor._registry.resolve(tool_name)
                            successful_mutation = successful_mutation or any(
                                req.action in {"write", "create", "delete", "modify_repository"}
                                for req in getattr(resolved_tool, "required_permissions", [])
                            )
                        except Exception:
                            pass
                    elif tool_res.state in {ToolState.DENIED, ToolState.CANCELLED}:
                        tool_operation_blocked = True
                    
                    # Store tool result for the next iteration model continuation
                    content_str = str(tool_res.output) if tool_res.state == ToolState.SUCCESS else str(tool_res.error)
                    tool_results_for_history.append({
                        "role": "tool",
                        "name": model_tool_name,
                        "tool_call_id": tool_call_id,
                        "content": content_str
                    })
                    
                # Feed ToolResults back into interaction history
                interaction_history.extend(tool_results_for_history)
            else:
                # No tools requested, model considers task done
                last_text = response.text or ""
                if implementation_task and not successful_mutation:
                    if no_tool_response_retries < 1:
                        no_tool_response_retries += 1
                        interaction_history.append({"role": "assistant", "content": last_text})
                        interaction_history.append({
                            "role": "user",
                            "content": (
                                "The project has not been changed yet. Continue the implementation now by "
                                "calling the available filesystem tools. Read relevant files first, then "
                                "create or edit the requested file. Do not answer with a proposal or code "
                                "in chat. After a successful file change, run an appropriate check."
                            ),
                        })
                        continue
                    fallback_code = _extract_single_code_block(last_text)
                    fallback_path = _infer_new_code_path(
                        objective_text,
                        task.expected_outputs or [],
                    )
                    if fallback_code and fallback_path and self._tool_executor and not tool_operation_blocked:
                        try:
                            from clairecoder.tools.core import get_workspace_root
                            from clairecoder.tools.workspace import resolve_workspace_path

                            target_path = resolve_workspace_path(
                                get_workspace_root(),
                                fallback_path,
                            )
                        except Exception as exc:
                            return ExecutionResult(
                                category=ExecutionResultCategory.FAILURE,
                                failure_category=FailureCategory.UNKNOWN_FAILURE,
                                error_message=f"Could not resolve the proposed file inside the workspace: {exc}",
                                tool_result=last_text,
                                task_id=task_id,
                            )

                        if target_path.exists():
                            return ExecutionResult(
                                category=ExecutionResultCategory.FAILURE,
                                failure_category=FailureCategory.UNKNOWN_FAILURE,
                                error_message=(
                                    f"The model returned code but did not use file tools; "
                                    f"{fallback_path} already exists, so it was left unchanged."
                                ),
                                tool_result=last_text,
                                task_id=task_id,
                            )

                        tool_res = self.request_tool(
                            "filesystem.write",
                            session_id=session_id,
                            workflow_id=session.current_workflow,
                            task_id=task_id,
                            path=fallback_path,
                            content=fallback_code,
                        )
                        if tool_res.state == ToolState.DENIED and tool_res.metadata.get("requires_confirmation"):
                            permission_request_id = tool_res.metadata.get("request_id")
                            wait_for_permission = getattr(self._tool_executor, "wait_for_permission", None)
                            if permission_request_id and callable(wait_for_permission):
                                resolved_result = wait_for_permission(
                                    permission_request_id,
                                    timeout=self.permission_wait_timeout_seconds,
                                )
                                if resolved_result is None:
                                    expire_permission = getattr(self._tool_executor, "expire_permission", None)
                                    if callable(expire_permission):
                                        expire_permission(permission_request_id)
                                    return ExecutionResult(
                                        category=ExecutionResultCategory.FAILURE,
                                        failure_category=FailureCategory.TIMEOUT,
                                        error_message=(
                                            "No permission decision was received for the proposed file write. "
                                            "Run ClaireCoder in an interactive terminal to approve file changes."
                                        ),
                                        task_id=task_id,
                                    )
                                tool_res = resolved_result

                        if tool_res.state == ToolState.SUCCESS:
                            return ExecutionResult(
                                category=ExecutionResultCategory.SUCCESS,
                                tool_result=str(tool_res.output or f"Created {fallback_path}"),
                                task_id=task_id,
                            )

                        return ExecutionResult(
                            category=ExecutionResultCategory.FAILURE,
                            failure_category=FailureCategory.UNKNOWN_FAILURE,
                            error_message=(
                                f"Could not create {fallback_path} from the model's code response: "
                                f"{tool_res.error or tool_res.state.value}."
                            ),
                            tool_result=last_text,
                            task_id=task_id,
                        )
                    return ExecutionResult(
                        category=ExecutionResultCategory.FAILURE,
                        failure_category=FailureCategory.UNKNOWN_FAILURE,
                        error_message=(
                            "Implementation was not applied: "
                            + (
                                "a requested tool operation was denied or blocked, so no additional write was attempted."
                                if tool_operation_blocked
                                else "the model did not make a successful file change after being asked to use workspace tools. "
                                "Confirm that this model supports tool calling or provide a concrete file path."
                            )
                        ),
                        tool_result=last_text,
                        task_id=task_id,
                    )
                if not implementation_task and not task.expected_result:
                    task.expected_result = last_text
                return ExecutionResult(
                    category=ExecutionResultCategory.SUCCESS,
                    tool_result=last_text,
                    task_id=task_id,
                )
                
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
        # A session can host several objectives. Keep prior tasks only while
        # replanning the same objective; otherwise stale failures from an older
        # prompt leak into the next run's final status and verification summary.
        current_objective_id = session.objective.id if session.objective else None
        if current_objective_id:
            session.tasks = {
                task_id: task
                for task_id, task in session.tasks.items()
                if task.objective_id == current_objective_id
            }
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
            # Note: Do NOT emit REPLANNING_STARTED here — the decision to replan
            # belongs to app.py's workflow loop, not the engine validation.

    def fail_task(self, session_id: str, task_id: str, failure_reason: str) -> None:
        """Mark task as failed and trigger replanning."""
        session = self._sessions.get(session_id)
        if session and task_id in session.tasks:
            task = session.tasks[task_id]
            task.status = TaskState.FAILED
            task.failure_state = failure_reason
            # Note: Do NOT emit REPLANNING_STARTED here — the replan decision
            # belongs to app.py's workflow loop, not the engine.

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
        """Interrupt active execution and mark objective as paused."""
        session = self._sessions.get(session_id)
        if session and session.objective:
            session.objective.status = ObjectiveStatus.PAUSED
        self._emit(EngineEvent.EXECUTION_PAUSED, {"session_id": session_id})

    def resume_execution(self, session_id: str) -> None:
        """Resume paused execution."""
        session = self._sessions.get(session_id)
        if session and session.objective:
            session.objective.status = ObjectiveStatus.ACTIVE
        self._emit(EngineEvent.EXECUTION_RESUMED, {"session_id": session_id})
        
    def cancel_objective(self, session_id: str) -> None:
        """Cancel execution entirely."""
        session = self._sessions.get(session_id)
        if session and session.objective:
            session.objective.status = ObjectiveStatus.CANCELLED
            self._emit(EngineEvent.EXECUTION_CANCELLED, {"objective_id": session.objective.id})
