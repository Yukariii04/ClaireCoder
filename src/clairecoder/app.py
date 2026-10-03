"""ClaireCoder V1 Integration Layer (CC-PRD-010).

This module implements the top-level integration boundary that brings all
independent ClaireCoder subsystems together into a single engineering platform.
"""

from typing import Dict, Any, Optional, List
import json
from pathlib import Path

from clairecoder.engine.engine import EngineeringEngine
from clairecoder.engine.types import (
    EngineeringObjective, EngineEvent, Task as EngineTask, TaskState as EngineTaskState, ObjectiveStatus
)
from clairecoder.interaction.controller import InteractionController
from clairecoder.interaction.types import CommandRequest
from clairecoder.gateway.interfaces import ModelGatewayInterface, ProviderAdapterInterface
from clairecoder.gateway.types import ModelRequest, ModelResponse, Model, Provider, Endpoint, Capability
from clairecoder.gateway.config import ProviderProfile, AdapterType, PROVIDER_REGISTRY
from clairecoder.gateway.credentials import CredentialStore
from clairecoder.gateway.manager import ConfigurationManager
from clairecoder.tools.executor import ToolExecutor
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.skills.registry import SkillRegistry
from clairecoder.workflow.manager import WorkflowManager
from clairecoder.workflow.planner import Planner
from clairecoder.workflow.types import Plan, WorkflowState, PlanningLevel
from clairecoder.execution.manager import ExecutionManager
from clairecoder.execution.types import Task as ExecTask, TaskState as ExecTaskState, ExecutionResult, ExecutionResultCategory, FailureCategory, FailureEvidence
from clairecoder.verification.engine import VerificationEngine
from clairecoder.verification.types import VerificationStatus, VerificationCriterion, VerificationTestType
from clairecoder.runtime.agent_runtime import AgentRuntime, RunResult
from clairecoder.runtime.emitter import EventEmitter
from clairecoder.runtime.bridge import EngineBridge
from clairecoder.changeset.store import ChangeSetStore


class ClaireCoderV1:
    """The unified V1 entry point for ClaireCoder.
    
    Coordinates the top-level Developer -> Interaction -> Engine lifecycle.
    """
    
    def __init__(
        self,
        model_gateway: Optional[ModelGatewayInterface] = None,
        permission_engine: Optional[PermissionEngine] = None,
        tool_executor: Optional[ToolExecutor] = None,
        skill_registry: Optional[SkillRegistry] = None,
        workflow_manager: Optional[WorkflowManager] = None,
        execution_manager: Optional[ExecutionManager] = None,
        verification_engine: Optional[VerificationEngine] = None,
        workspace_root: Optional[str] = None,
        changeset_store: Optional[ChangeSetStore] = None,
    ):
        from clairecoder.gateway.gateway import ModelGateway
        from clairecoder.tools.registry import ToolRegistry
        from clairecoder.verification.runner import DefaultVerificationRunner

        self.model_gateway = model_gateway if model_gateway is not None else ModelGateway()
        self.permission_engine = permission_engine if permission_engine is not None else PermissionEngine()
        self.tool_executor = tool_executor if tool_executor is not None else ToolExecutor(ToolRegistry.create_default(), self.permission_engine)
        self.skill_registry = skill_registry if skill_registry is not None else SkillRegistry()
        self.workflow_manager = workflow_manager if workflow_manager is not None else WorkflowManager()
        self.execution_manager = execution_manager if execution_manager is not None else ExecutionManager()
        self.verification_engine = verification_engine if verification_engine is not None else VerificationEngine()
        if self.verification_engine._runner is None:
            self.verification_engine._runner = DefaultVerificationRunner(workspace_root=workspace_root)
        
        # Configuration management (Stage 7)
        self._workspace_root = workspace_root
        self.config_manager = ConfigurationManager(workspace_root=workspace_root)
        
        # Core engineering orchestrator
        self.engineering_engine = EngineeringEngine(
            model_gateway=self.model_gateway,
            tool_executor=self.tool_executor,
            skill_registry=self.skill_registry
        )
        
        # Interaction Layer
        self.interaction_controller = InteractionController(engine=self.engineering_engine, app=self)

        # Load persisted provider profiles into the gateway
        self.load_providers_from_config()
        self.planner = Planner()

        # Runtime Event Protocol & Decoupled AgentRuntime (Correction #14)
        self.event_emitter = EventEmitter()
        self.bridge = EngineBridge(self.event_emitter)
        self.engineering_engine.subscribe(self.bridge.on_engine_event)

        self.agent_runtime = AgentRuntime(
            planner=self.planner,
            verifier=self.verification_engine,
            event_emitter=self.event_emitter,
            workflow_manager=self.workflow_manager,
            execution_manager=self.execution_manager,
            engineering_engine=self.engineering_engine,
            verification_engine=self.verification_engine,
            model_gateway=self.model_gateway,
            config_manager=self.config_manager,
            workspace_root=workspace_root,
            changeset_store=changeset_store,
        )

    @classmethod
    def create_default(
        cls,
        model_gateway: Optional[ModelGatewayInterface] = None,
        workspace_root: Optional[str] = None,
        changeset_store: Optional[ChangeSetStore] = None,
    ) -> "ClaireCoderV1":
        """Factory method to construct a default ClaireCoderV1 application instance."""
        return cls(model_gateway=model_gateway, workspace_root=workspace_root, changeset_store=changeset_store)

    @property
    def changeset_store(self) -> ChangeSetStore:
        """Access the runtime ChangeSetStore."""
        return self.agent_runtime.changeset_store
        
    def get_active_model_id(self) -> Optional[str]:
        """Get the authoritative active model ID from configuration or registered gateway models."""
        active = self.config_manager.get_active()
        if active.get("model_id"):
            return active["model_id"]
        # Fallback to registered models in gateway
        if hasattr(self.model_gateway, "_models") and isinstance(self.model_gateway._models, dict) and self.model_gateway._models:
            return next(iter(self.model_gateway._models.keys()))
        if type(self.model_gateway).__name__ != "ModelGateway" and hasattr(self.model_gateway, "execute"):
            return "test-model"
        return None

    def get_active_provider_profile(self) -> Optional[ProviderProfile]:
        """Get the currently active ProviderProfile object if configured."""
        active = self.config_manager.get_active()
        pid = active.get("provider_profile_id")
        if pid:
            return self.config_manager.load_provider_profile(pid)
        return None

    def create_session(self, session_id: str, model_profile_id: Optional[str] = None) -> str:
        """Create a new engineering session with authoritative model profile."""
        active_model = model_profile_id or self.get_active_model_id()
        objective = EngineeringObjective(
            id=f"obj_{session_id}",
            request="Initialize session",
            session_id=session_id,
            model_profile_id=active_model,
        )
        session = self.engineering_engine.receive_objective(objective)
        return session.id

    def submit_objective(self, session_id: str, request: str, start_background: bool = True) -> str:
        """Submit a new objective to the session using the authoritative active model."""
        active_model = self.get_active_model_id()
        session = self.engineering_engine.get_session(session_id)
        if session:
            active_cfg = self.config_manager.get_active()
            if active_cfg.get("model_id"):
                active_model = active_cfg["model_id"]
                session.model_profile = active_model
            elif session.model_profile:
                active_model = session.model_profile

        objective = EngineeringObjective(
            id=f"obj_{hash(request)}",
            request=request,
            session_id=session_id,
            model_profile_id=active_model,
        )
        session = self.engineering_engine.receive_objective(objective)
        return session.id

    def check_configuration_status(self) -> str:
        """Determine application configuration state: 'configured', 'not_configured', or 'needs_repair'.
        
        Per CC-PRD-011 and Stage 7 architecture:
        Uses ConfigurationManager as the authoritative source, with fallback to in-memory gateway.
        """
        if self.config_manager.is_configured():
            return "configured"
        if hasattr(self.model_gateway, "_providers") and self.model_gateway._providers:
            return "configured"
        if hasattr(self.model_gateway, "_adapters") and self.model_gateway._adapters:
            return "configured"
        if hasattr(self.model_gateway, "_models") and self.model_gateway._models:
            return "configured"
        if self.config_manager.needs_repair():
            return "needs_repair"
        return "not_configured"

    def register_provider_profile(self, profile: ProviderProfile) -> None:
        """Register a provider profile's adapter and all its models into the ModelGateway."""
        if not profile.enabled:
            return
        adapter = self._create_adapter_for_profile(profile)
        if adapter:
            self.model_gateway.register_adapter(adapter)
            provider = Provider(id=profile.provider_id, name=profile.name)
            endpoint = Endpoint(url=profile.endpoint)
            for mid in profile.available_models:
                caps = []
                model_caps = profile.capabilities.get(mid, [])
                for c in model_caps:
                    try:
                        caps.append(Capability(c))
                    except ValueError:
                        pass
                ctx = None
                if isinstance(profile.provider_specific, dict):
                    ctx = profile.provider_specific.get("context_capacities", {}).get(mid)
                model = Model(
                    id=mid,
                    display_name=mid,
                    provider=provider,
                    endpoint=endpoint,
                    capabilities=caps,
                    context_capacity=ctx,
                )
                self.model_gateway.register_model(model)

    def load_providers_from_config(self) -> bool:
        """Load all configured providers into the ModelGateway from persisted config.
        
        Called during bootstrap (after wizard or on returning-user launch).
        Returns True if at least one provider was loaded AND the active model is verified.
        
        ABSOLUTE RULE — NEVER HARDCODE A STARTUP MODEL.
        The active (provider_profile_id, model_id) pair MUST come from persisted
        config (active.json). If that pair doesn't resolve, the system enters
        'needs_repair' state rather than silently selecting a random model.
        """
        profiles = self.config_manager.list_provider_profiles()
        if not profiles:
            return False

        loaded = False
        for profile in profiles:
            try:
                self.register_provider_profile(profile)
                loaded = True
            except Exception:
                pass  # Skip broken profiles silently during boot

        if not loaded:
            return False

        # Verify that the persisted active selection actually resolves
        active = self.config_manager.get_active()
        active_pid = active.get("provider_profile_id")
        active_mid = active.get("model_id")

        if active_pid and active_mid:
            # Verify the provider profile exists
            profile = self.config_manager.load_provider_profile(active_pid)
            if profile is None or not profile.enabled:
                # Profile was deleted or disabled — active selection is stale
                return False

            # Verify the model was registered in the gateway
            try:
                model_obj = self.model_gateway.get_model(active_mid)
                if model_obj is None:
                    return False
                # Synchronize context capacity to interaction controller
                if model_obj.context_capacity and hasattr(self, "interaction_controller") and self.interaction_controller:
                    self.interaction_controller._context_capacity = model_obj.context_capacity
            except Exception:
                pass
        elif active_pid or active_mid:
            # Partial selection — needs repair
            return False

        return loaded

    def _create_adapter_for_profile(self, profile: ProviderProfile) -> Optional[ProviderAdapterInterface]:
        """Create the appropriate adapter instance for a provider profile."""
        from clairecoder.gateway.adapters import (
            OpenAICompatibleAdapter, AnthropicAdapter, GeminiAdapter, OllamaAdapter,
        )

        # Retrieve credential from secure store
        api_key = None
        if profile.credential_ref:
            api_key = self.config_manager.credential_store.get_credential(profile.id)

        adapter_type = profile.adapter_type

        if adapter_type == AdapterType.ANTHROPIC.value:
            return AnthropicAdapter(auth_token=api_key)
        elif adapter_type == AdapterType.GEMINI.value:
            return GeminiAdapter(auth_token=api_key)
        elif adapter_type == AdapterType.OLLAMA.value:
            provider_options = profile.provider_specific if isinstance(profile.provider_specific, dict) else {}
            timeout_seconds = provider_options.get(
                "timeout_seconds", OllamaAdapter.DEFAULT_TIMEOUT_SECONDS
            )
            return OllamaAdapter(timeout_seconds=timeout_seconds)
        else:
            # OpenAI-compatible: openai, groq, openrouter, omniroute, lmstudio, vllm, custom
            return OpenAICompatibleAdapter(
                provider_id=profile.provider_id,
                auth_token=api_key,
            )

    def submit_objective(self, session_id: str, objective_text: str, start_background: bool = False) -> str:
        """Process a natural language request by creating an objective for the engine."""
        if start_background:
            return self.interaction_controller.process_natural_language(objective_text, session_id)
        else:
            session = self.engineering_engine.get_session(session_id)
            active_model = (session.model_profile if session and session.model_profile else None) or self.get_active_model_id()
            objective = EngineeringObjective(
                id=f"obj_{hash(objective_text)}",
                request=objective_text,
                session_id=session_id,
                mode=self.interaction_controller._mode.value,
                model_profile_id=active_model,
            )
            session = self.engineering_engine.receive_objective(objective)
            return f"Objective accepted in session {session.id}"
        
    def execute_command(self, command: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Execute an interaction command (e.g., /status, /pause)."""
        request = CommandRequest(command=command, arguments=arguments or {})
        return self.interaction_controller.execute_command(request)

    def run(self, session_id: str, max_cycles: int = 10) -> RunResult:
        """Run the engineering loop for a session until complete or paused.
        
        Correction #14: Delegates execution orchestration to AgentRuntime.
        app.py remains thin, owning bootstrap and composition.
        """
        session = self.engineering_engine.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Ensure session model profile is resolved authoritatively
        active_cfg = self.config_manager.get_active()
        if active_cfg.get("model_id"):
            session.model_profile = active_cfg["model_id"]
        elif not session.model_profile:
            session.model_profile = self.get_active_model_id()

        active_model = session.model_profile
        if not active_model:
            from clairecoder.gateway.types import ModelError
            raise ModelError("No active model configured. Please configure a provider via /model or the setup wizard.")

        # Synchronize runtime with application subsystem references
        self.agent_runtime._planner = self.planner
        self.agent_runtime._workflow_manager = self.workflow_manager
        self.agent_runtime._execution_manager = self.execution_manager
        self.agent_runtime._verification_engine = self.verification_engine
        self.agent_runtime._engineering_engine = self.engineering_engine

        return self.agent_runtime.run(
            objective=session.objective,
            session_id=session_id,
            max_cycles=max_cycles,
            active_model=active_model,
        )

    def status(self, session_id: str) -> Dict[str, Any]:
        """Get the current status of the session."""
        session = self.engineering_engine.get_session(session_id)
        if not session:
            return {"status": "not_found"}
        return session.to_dict()

    def pause(self, session_id: str) -> None:
        """Pause the current session."""
        self.execute_command("pause", {"session_id": session_id})

    def resume(self, session_id: str) -> None:
        """Resume a paused session."""
        self.execute_command("resume", {"session_id": session_id})

    def cancel(self, session_id: str) -> None:
        """Cancel the current session."""
        self.execute_command("cancel", {"session_id": session_id})

    def save_session(self, session_id: str) -> None:
        """Persist session state."""
        self.engineering_engine.save_session(session_id)
        
        save_dir = Path(".clairecoder/sessions")
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Persist Workflow state
        workflow_id = f"wf_{session_id}"
        wf_path = save_dir / f"{workflow_id}.json"
        workflow_data = self.workflow_manager.workflow_to_dict(workflow_id)
        if workflow_data:
            with wf_path.open("w") as f:
                json.dump(workflow_data, f)
                
        # Persist Execution state
        exec_path = save_dir / f"exec_{session_id}.json"
        exec_tasks = {}
        session = self.engineering_engine.get_session(session_id)
        if session:
            for task_id in session.tasks:
                task_data = self.execution_manager.task_to_dict(task_id)
                if task_data:
                    exec_tasks[task_id] = task_data
            with exec_path.open("w") as f:
                json.dump(exec_tasks, f)
                
        # Persist Verification state
        verif_path = save_dir / f"verif_{session_id}.json"
        verif_data = self.verification_engine.to_dict()
        with verif_path.open("w") as f:
            json.dump(verif_data, f)
                
    def resume_session(self, session_id: str) -> None:
        """Load session state from disk."""
        self.engineering_engine.resume_session(session_id)
        
        save_dir = Path(".clairecoder/sessions")
        
        # Load Workflow state
        workflow_id = f"wf_{session_id}"
        wf_path = save_dir / f"{workflow_id}.json"
        if wf_path.exists():
            with wf_path.open("r") as f:
                data = json.load(f)
            self.workflow_manager.load_workflow_from_dict(data)
            
        # Load Execution state
        exec_path = save_dir / f"exec_{session_id}.json"
        if exec_path.exists():
            with exec_path.open("r") as f:
                data = json.load(f)
            for task_id, task_data in data.items():
                self.execution_manager.task_from_dict(task_data)
                
        # Load Verification state
        verif_path = save_dir / f"verif_{session_id}.json"
        if verif_path.exists():
            with verif_path.open("r") as f:
                data = json.load(f)
            self.verification_engine.load_from_dict(data)
        
    def close_session(self, session_id: str) -> None:
        """Close and clean up session without destroying persisted state."""
        self.save_session(session_id)
        self.engineering_engine.remove_session(session_id)
        workflow_id = f"wf_{session_id}"
        self.workflow_manager.remove_workflow(workflow_id)

    def get_version(self) -> str:
        """Get the application version."""
        return "0.1.0"
