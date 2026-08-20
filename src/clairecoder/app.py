"""ClaireCoder V1 Integration Layer (CC-PRD-010).

This module implements the top-level integration boundary that brings all
independent ClaireCoder subsystems together into a single engineering platform.
"""

from typing import Dict, Any, Optional
import json
from pathlib import Path

from clairecoder.engine.engine import EngineeringEngine, EngineeringObjective
from clairecoder.workflow.types import Task as EngineTask, TaskState as EngineTaskState
from clairecoder.interaction.controller import InteractionController
from clairecoder.interaction.types import CommandRequest
from clairecoder.gateway.interfaces import ModelGatewayInterface
from clairecoder.tools.executor import ToolExecutor
from clairecoder.permissions.engine import PermissionEngine
from clairecoder.skills.registry import SkillRegistry
from clairecoder.workflow.manager import WorkflowManager
from clairecoder.workflow.planner import Planner
from clairecoder.workflow.types import Plan, WorkflowState, PlanningLevel
from clairecoder.execution.manager import ExecutionManager
from clairecoder.execution.types import Task as ExecTask, TaskState as ExecTaskState, ExecutionResult, ExecutionResultCategory, FailureCategory
from clairecoder.verification.engine import VerificationEngine
from clairecoder.verification.types import VerificationStatus, VerificationCriterion, VerificationTestType

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
        verification_engine: Optional[VerificationEngine] = None
    ):
        from clairecoder.gateway.gateway import ModelGateway
        from clairecoder.tools.registry import ToolRegistry

        self.model_gateway = model_gateway if model_gateway is not None else ModelGateway()
        self.permission_engine = permission_engine if permission_engine is not None else PermissionEngine()
        self.tool_executor = tool_executor if tool_executor is not None else ToolExecutor(ToolRegistry(), self.permission_engine)
        self.skill_registry = skill_registry if skill_registry is not None else SkillRegistry()
        self.workflow_manager = workflow_manager if workflow_manager is not None else WorkflowManager()
        self.execution_manager = execution_manager if execution_manager is not None else ExecutionManager()
        self.verification_engine = verification_engine if verification_engine is not None else VerificationEngine()
        
        # Core engineering orchestrator
        self.engineering_engine = EngineeringEngine(
            model_gateway=self.model_gateway,
            tool_executor=self.tool_executor,
            skill_registry=self.skill_registry
        )
        
        # Interaction Layer
        self.interaction_controller = InteractionController(engine=self.engineering_engine)
        self.planner = Planner()

    @classmethod
    def create_default(cls, model_gateway: Optional[ModelGatewayInterface] = None) -> 'ClaireCoderV1':
        """Factory method to construct a default ClaireCoderV1 application instance."""
        return cls(model_gateway=model_gateway)
        
    def create_session(self, session_id: str) -> str:
        """Create a new engineering session."""
        objective = EngineeringObjective(
            id=f"obj_{session_id}",
            request="Initialize session",
            session_id=session_id
        )
        session = self.engineering_engine.receive_objective(objective)
        return session.id

    def check_configuration_status(self) -> str:
        """Determine application configuration state: 'configured', 'not_configured', or 'needs_repair'.
        
        Per CC-PRD-011 and Stage 6 architecture:
        Provides an authoritative status query without making TUI state authoritative.
        """
        if not hasattr(self.model_gateway, "_providers") or not self.model_gateway._providers:
            return "not_configured"
        return "configured"

    def submit_objective(self, session_id: str, objective_text: str) -> str:
        """Process a natural language request by creating an objective for the engine."""
        return self.interaction_controller.process_natural_language(objective_text, session_id)
        
    def execute_command(self, command: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Execute an interaction command (e.g., /status, /pause)."""
        request = CommandRequest(command=command, arguments=arguments or {})
        return self.interaction_controller.execute_command(request)

    def run(self, session_id: str, max_cycles: int = 10) -> None:
        """Run the engineering loop for a session until complete or paused.
        
        End-to-End Flow: Objective -> Understand -> Plan -> Execute -> Verify -> Complete
        """
        session = self.engineering_engine.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
            
        workflow_id = f"wf_{session_id}"
        
        # 1. Assembly Context and Understand Objective
        understanding = self.engineering_engine.understand(session_id)
        
        # 2. Planning - Delegate to WorkflowManager
        workflow = self.workflow_manager.get_workflow(workflow_id)
        if not workflow:
            workflow = self.workflow_manager.create_workflow(workflow_id, session.objective.id, "Main workflow")
            
        cycles = 0
        while workflow.state not in (WorkflowState.COMPLETE, WorkflowState.CANCELLED, WorkflowState.BLOCKED, WorkflowState.PAUSED):
            if cycles >= max_cycles:
                print("Max cycles reached in run loop.")
                break
            cycles += 1
            
            if workflow.state in (WorkflowState.CREATED, WorkflowState.REPLANNING):
                context_summary = "Planning phase"
                if workflow.state == WorkflowState.CREATED:
                    req = self.planner.build_planning_request(
                        objective=session.objective.request,
                        planning_level=PlanningLevel.STRUCTURED,
                        context_summary=context_summary,
                        model_id=session.model_profile or "default-model"
                    )
                else:
                    active_plan = self.workflow_manager.get_active_plan(workflow_id)
                    req = self.planner.build_replan_request(
                        objective=session.objective.request,
                        previous_plan=active_plan,
                        failure_reason="Execution or validation failed",
                        context_summary=context_summary,
                        model_id=session.model_profile or "default-model"
                    )
                
                resp = self.engineering_engine.execute_model(req)
                plan = self.planner.create_plan(
                    workflow_id=workflow_id,
                    objective=session.objective.id,
                    planning_level=PlanningLevel.STRUCTURED,
                    model_response=resp
                )
                tasks = self.planner.create_tasks_from_plan(plan, session.objective.id)
                
                self.engineering_engine.plan_tasks(session_id, tasks)
                self.workflow_manager.add_plan(plan)
                self.workflow_manager.transition_state(workflow_id, WorkflowState.PLANNED)
                
            if workflow.state == WorkflowState.PLANNED:
                self.workflow_manager.transition_state(workflow_id, WorkflowState.ACTIVE)
                
            # 3. Model & Tool Interaction Loop (Execution)
            if workflow.state == WorkflowState.ACTIVE:
                ready_tasks = self.workflow_manager.get_ready_tasks(list(session.tasks.values()))
                
                for eng_task in ready_tasks:
                    task_id = eng_task.id
                    
                    # Setup ExecutionManager
                    exec_task = self.execution_manager.get_task(task_id)
                    if not exec_task:
                        exec_task = ExecTask(
                            id=task_id,
                            objective_id=eng_task.objective_id,
                            description=eng_task.description,
                            workflow_id=workflow_id
                        )
                        self.execution_manager.register_task(exec_task)
                    
                    if exec_task.status in (ExecTaskState.PENDING, ExecTaskState.FAILED):
                        self.execution_manager.transition_task(task_id, ExecTaskState.READY)
                    
                    if exec_task.status in (ExecTaskState.READY, ExecTaskState.PAUSED):
                        attempt = self.execution_manager.start_execution(task_id)
                        
                        # Use EngineeringEngine to update task status
                        self.engineering_engine.start_task(session_id, task_id)
                        
                        try:
                            exec_result = self.engineering_engine.interaction_loop(session_id, task_id, max_iterations=5)
                        except Exception as e:
                            print(f"Exception in interaction_loop: {e}")
                            exec_result = ExecutionResult(
                                category=ExecutionResultCategory.FAILURE,
                                failure_category=FailureCategory.UNKNOWN_FAILURE,
                                error_message=str(e)
                            )
                            
                        # 4. Verification
                        if exec_result.category.value == "success":
                            self.workflow_manager.transition_state(workflow_id, WorkflowState.VALIDATING)
                            if eng_task.validation_requirements:
                                criteria = [
                                    VerificationCriterion(
                                        id=f"{task_id}:{index}",
                                        description=req,
                                        test_type=VerificationTestType.UNIT
                                    )
                                    for index, req in enumerate(eng_task.validation_requirements)
                                ]
                            else:
                                criteria = []

                            if criteria:
                                self.verification_engine.create_verification(f"v_{task_id}_{attempt.attempt_number}", task_id, criteria)
                                self.verification_engine.start_verification(f"v_{task_id}_{attempt.attempt_number}")
                                v_result = self.verification_engine.execute_verification(f"v_{task_id}_{attempt.attempt_number}")
                                passed = (v_result.status == VerificationStatus.PASSED)
                            else:
                                passed = True
                            
                            if passed:
                                self.execution_manager.complete_execution(task_id, attempt.execution_id, exec_result, is_verified=True)
                                self.engineering_engine.validate_task(session_id, task_id, passed=True)
                            else:
                                exec_result.category = ExecutionResultCategory.FAILURE
                                exec_result.failure_category = FailureCategory.VALIDATION_FAILURE
                                self.execution_manager.complete_execution(task_id, attempt.execution_id, exec_result, is_verified=False)
                                self.engineering_engine.validate_task(session_id, task_id, passed=False, failure_reason="Verification failed")
                                
                        else:
                            self.execution_manager.complete_execution(task_id, attempt.execution_id, exec_result, is_verified=False)
                            self.engineering_engine.fail_task(session_id, task_id, failure_reason=exec_result.error_message)

                # Check overall status via WorkflowManager
                # Only check tasks for the active plan
                active_plan = self.workflow_manager.get_active_plan(workflow_id)
                active_task_ids = active_plan.task_ids if active_plan else []
                active_tasks = [t for t in session.tasks.values() if t.id in active_task_ids]
                
                # Gather satisfied requirements from verified tasks
                satisfied_reqs = []
                for t in active_tasks:
                    history = self.verification_engine.get_history(t.id)
                    for v in history:
                        if v.status == VerificationStatus.PASSED:
                            for c in v.criteria:
                                satisfied_reqs.append(c.description)
                
                is_complete = self.workflow_manager.check_completion(
                    workflow_id,
                    active_tasks,
                    satisfied_criteria=satisfied_reqs,
                    satisfied_validations=satisfied_reqs
                )
                any_failed = any(t.status == EngineTaskState.FAILED for t in active_tasks)
                
                if is_complete and active_tasks:
                    # State is already VALIDATING from the verification step if it succeeded
                    if workflow.state != WorkflowState.VALIDATING:
                        self.workflow_manager.transition_state(workflow_id, WorkflowState.VALIDATING)
                    self.workflow_manager.transition_state(workflow_id, WorkflowState.COMPLETE)
                    self.engineering_engine.complete_objective(session_id)
                elif any_failed:
                    self.workflow_manager.transition_state(workflow_id, WorkflowState.FAILED)
                    self.workflow_manager.transition_state(workflow_id, WorkflowState.REPLANNING)
                    # We do NOT fail the objective here because we are replanning
                    # self.engineering_engine.fail_objective(session_id)

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
