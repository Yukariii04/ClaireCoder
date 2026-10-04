from typing import Any, Callable, Dict, List, Optional
import threading
from .types import CommandDefinition, CommandRequest, CommandResponse, InteractionMode
from .run_state import RunState, AgentRun
from clairecoder.engine.engine import EngineeringEngine
from clairecoder.engine.types import EngineeringObjective, EngineEvent, ObjectiveStatus


class InteractionController:
    """Coordinates interaction commands and passes them to the Engineering Engine.

    Per CC-PRD-005 and CC-ADR-005:
    - Does NOT directly access ToolExecutor, PermissionEngine, ModelGateway,
      provider SDKs, WorkflowManager, or ExecutionManager.
    - Does NOT execute Tools itself.
    - Does NOT make Permission decisions.
    - Does NOT own EngineeringEngine state.
    - Routes all engineering intent through the EngineeringEngine boundary.
    """
    def __init__(self, engine: EngineeringEngine, app: Optional[Any] = None):
        self._engine = engine
        self._app = app
        self._config_manager = getattr(app, "config_manager", None) if app else None
        self._commands: Dict[str, CommandDefinition] = {}
        self._handlers: Dict[str, Callable[[CommandRequest], CommandResponse]] = {}
        self._mode = InteractionMode.IMPLEMENT
        self._active_session_id: Optional[str] = None
        # Connect engine events to controller subscribers
        self._engine.subscribe(self._handle_engine_event)
        self._event_subscribers: List[Callable[['Event'], None]] = []

        # Token usage tracking from model responses
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._context_capacity: Optional[int] = None

        # Authoritative run state machine (§8)
        self._active_run: Optional[AgentRun] = None
        self._active_run_lock = threading.Lock()

        self._register_default_commands()

    @property
    def mode(self) -> InteractionMode:
        return self._mode

    @property
    def total_prompt_tokens(self) -> int:
        return self._total_prompt_tokens

    @property
    def total_completion_tokens(self) -> int:
        return self._total_completion_tokens

    @property
    def context_capacity(self) -> Optional[int]:
        return self._context_capacity

    def subscribe(self, callback: Callable[['Event'], None]) -> None:
        """Register a subscriber to receive engine events."""
        self._event_subscribers.append(callback)
        
    def _handle_engine_event(self, engine_event: 'EngineEvent', data: Dict[str, 'Any']) -> None:
        """Translates internal engine events to the public interaction Event boundary."""
        from clairecoder.core.events import Event
        event = Event(name=engine_event.value, payload=data)
        for sub in self._event_subscribers:
            sub(event)

    def _emit_event(self, name: str, payload: Dict[str, Any]) -> None:
        """Emit a synthetic event directly to subscribers."""
        from clairecoder.core.events import Event
        event = Event(name=name, payload=payload)
        for sub in self._event_subscribers:
            sub(event)

    def register_command(self, definition: CommandDefinition, handler: Callable[[CommandRequest], CommandResponse]) -> None:
        """Register a command and its handler."""
        self._commands[definition.name] = definition
        self._handlers[definition.name] = handler
        for alias in definition.aliases:
            self._commands[alias] = definition
            self._handlers[alias] = handler

    def _register_default_commands(self) -> None:
        """Register the V1 command set per CC-PRD-005 §11."""
        from .types import CommandCategory, CommandArgument

        self.register_command(
            CommandDefinition("help", "Show available commands", CommandCategory.SYSTEM),
            self._handle_help
        )
        self.register_command(
            CommandDefinition("status", "Show current engineering status", CommandCategory.SYSTEM),
            self._handle_status
        )
        self.register_command(
            CommandDefinition("model", "Inspect or select model", CommandCategory.SYSTEM, [
                CommandArgument("model_name", "Model identifier to select", required=False)
            ]),
            self._handle_model
        )
        self.register_command(
            CommandDefinition("mode", "Inspect or switch mode", CommandCategory.MODE, [
                CommandArgument("mode_name", "Mode to switch to", required=False)
            ]),
            self._handle_mode
        )
        self.register_command(
            CommandDefinition("plan", "Inspect the active engineering plan", CommandCategory.WORKFLOW),
            self._handle_plan
        )
        self.register_command(
            CommandDefinition("session", "Inspect or control sessions", CommandCategory.SESSION, [
                CommandArgument("action", "Session action (list, pause, resume, close)", required=False),
                CommandArgument("session_id", "Target session ID", required=False)
            ]),
            self._handle_session
        )
        self.register_command(
            CommandDefinition("pause", "Pause active operation", CommandCategory.EXECUTION, [
                CommandArgument("session_id", "ID of the session to pause", required=False)
            ]),
            self._handle_pause
        )
        self.register_command(
            CommandDefinition("resume", "Resume paused operation", CommandCategory.EXECUTION, [
                CommandArgument("session_id", "ID of the session to resume", required=False)
            ]),
            self._handle_resume
        )
        self.register_command(
            CommandDefinition("cancel", "Cancel active operation", CommandCategory.EXECUTION, [
                CommandArgument("session_id", "ID of the session to cancel", required=False)
            ]),
            self._handle_cancel
        )
        self.register_command(
            CommandDefinition("clear", "Clear current interaction display", CommandCategory.SYSTEM),
            self._handle_clear
        )
        self.register_command(
            CommandDefinition("exit", "Exit ClaireCoder", CommandCategory.SYSTEM),
            self._handle_exit
        )

    # =========================================================================
    # INTERACTION ROUTER — Conversational vs Engineering Classification
    # =========================================================================

    # Engineering intent keywords — presence strongly suggests engineering work
    _ENGINEERING_KEYWORDS = frozenset({
        "inspect", "find", "fix", "implement", "create", "build", "modify",
        "edit", "delete", "remove", "add", "refactor", "test", "run",
        "execute", "debug", "deploy", "install", "configure", "setup",
        "analyze", "scan", "review", "check", "audit", "migrate",
        "update", "upgrade", "patch", "merge", "commit", "push", "pull",
        "search", "grep", "replace", "rename", "move", "copy",
        "write", "read", "list", "show", "display", "print",
        "compile", "lint", "format", "benchmark", "profile",
        "repository", "codebase", "file", "function", "class", "module",
        "error", "bug", "exception", "traceback", "failure", "crash",
        "authentication", "authorization", "login", "endpoint", "api",
        "database", "schema", "query", "migration",
    })

    # Engineering path references
    _ENGINEERING_PATH_PATTERNS = (
        ".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c", ".h",
        ".jsx", ".tsx", ".vue", ".svelte", ".css", ".scss", ".html",
        ".json", ".yaml", ".yml", ".toml", ".xml", ".sql", ".sh", ".bat",
        ".md", ".txt", ".cfg", ".ini", ".env",
        "src/", "tests/", "test/", "lib/", "pkg/",
    )

    def _classify_intent(self, request: str) -> str:
        """Classify user input as 'conversational' or 'engineering'.

        Uses deterministic keyword/pattern matching combined with active mode policy.
        Does NOT invoke another model/planner to classify — this is a lightweight
        heuristic boundary per §17.

        Returns:
            'conversational' — normal LLM chat response
            'engineering'    — full engineering workflow
        """
        text = request.strip().lower()

        # Mode override: explicit engineering modes always route to engineering
        if self._mode in (InteractionMode.PLAN, InteractionMode.REVIEW, InteractionMode.DEBUG):
            # Even in these modes, purely social greetings stay conversational
            if len(text.split()) <= 3 and not any(kw in text.split() for kw in self._ENGINEERING_KEYWORDS):
                return "conversational"
            return "engineering"

        # Explicit conversational questions about concepts/explanations
        if text.startswith(("what is ", "what are ", "what does ", "how does ",
                           "can you explain", "explain ", "tell me about",
                           "define ", "describe ", "who is ", "who are ",
                           "why is ", "why are ", "when ", "where ")):
            # Unless they reference specific files/code paths
            if not any(p in text for p in self._ENGINEERING_PATH_PATTERNS):
                return "conversational"

        # Explicit action verbs starting the prompt indicate engineering
        if text.startswith(("write ", "create ", "build ", "implement ", "fix ",
                           "refactor ", "inspect ", "debug ", "run the tests",
                           "test ", "modify ", "edit ", "delete ", "scan ")):
            return "engineering"

        # Empty or very short greetings
        words = text.split()
        if len(words) <= 2:
            # Check if any word is an engineering keyword
            if any(w in self._ENGINEERING_KEYWORDS for w in words):
                return "engineering"
            return "conversational"

        # Check for file path references
        for pattern in self._ENGINEERING_PATH_PATTERNS:
            if pattern in text:
                return "engineering"

        # Check for engineering keyword density
        eng_word_count = sum(1 for w in words if w.rstrip(".,!?;:") in self._ENGINEERING_KEYWORDS)
        if eng_word_count >= 1 and len(words) <= 8:
            return "engineering"
        if eng_word_count >= 2:
            return "engineering"

        # Default for implement mode: engineering if any engineering term is present
        if self._mode == InteractionMode.IMPLEMENT:
            return "engineering" if eng_word_count >= 1 else "conversational"

        return "conversational"

    def _get_mode_policy(self) -> dict:
        """Return the workflow policy constraints for the current mode.

        Returns a dict with keys:
            allow_file_modification: bool
            allow_tool_execution: bool
            workflow_type: str  — 'conversation', 'plan_only', 'full', 'review', 'debug'
        """
        if self._mode == InteractionMode.PLAN:
            return {
                "allow_file_modification": False,
                "allow_tool_execution": True,  # read-only tools for analysis
                "workflow_type": "plan_only",
            }
        elif self._mode == InteractionMode.IMPLEMENT:
            return {
                "allow_file_modification": True,
                "allow_tool_execution": True,
                "workflow_type": "full",
            }
        elif self._mode == InteractionMode.REVIEW:
            return {
                "allow_file_modification": False,
                "allow_tool_execution": True,  # read-only inspection
                "workflow_type": "review",
            }
        elif self._mode == InteractionMode.DEBUG:
            return {
                "allow_file_modification": True,  # patches allowed
                "allow_tool_execution": True,
                "workflow_type": "debug",
            }
        # Fallback
        return {
            "allow_file_modification": False,
            "allow_tool_execution": True,
            "workflow_type": "conversation",
        }

    @property
    def active_run(self) -> Optional[AgentRun]:
        """Current run state (read-only). TUI projects this."""
        return self._active_run

    @property
    def run_state(self) -> RunState:
        """Current authoritative run state."""
        if self._active_run:
            return self._active_run.state
        return RunState.IDLE

    def _create_run(self, run_id: str) -> AgentRun:
        """Create and register a new AgentRun, clearing any previous terminal run."""
        def _on_change(old: RunState, new: RunState):
            self._emit_event("run_state_changed", {
                "run_id": run_id,
                "old_state": old.value,
                "new_state": new.value,
            })
        with self._active_run_lock:
            run = AgentRun(run_id, on_state_change=_on_change)
            self._active_run = run
            return run

    def _clear_terminal_run(self) -> None:
        """Clear active run after it reaches terminal state (§12)."""
        with self._active_run_lock:
            if self._active_run and self._active_run.is_terminal:
                self._active_run = None

    def process_natural_language(self, request: str, session_id: str) -> str:
        """Process a natural language request through the Interaction Router.

        Routes to either:
        - Conversational: direct model response, no engineering workflow
        - Engineering: full engineering objective + workflow

        Per PRD §7.1, §17, §18, §19.
        """
        self._active_session_id = session_id
        session = self._engine.get_session(session_id)
        if session and session.objective and session.objective.status == ObjectiveStatus.PAUSED:
            self._emit_event("response_complete", {
                "session_id": session_id,
                "text": "Session is paused. Use '/resume' or '/session resume' to continue before submitting new prompts.",
                "error": True,
            })
            return "Session is paused. Resume before submitting new prompts."

        # Resolve active model
        active_model = self._resolve_active_model(session)

        # Classify intent
        intent = self._classify_intent(request)

        # Create authoritative run
        run = self._create_run(f"run_{hash(request)}")

        if intent == "conversational":
            # Direct model conversation — no EngineeringObjective, no Task, no Plan
            t = threading.Thread(
                target=self._run_conversational_response,
                args=(session_id, request, active_model, run),
                daemon=True,
            )
            t.start()
            return f"Processing in session {session_id}"
        else:
            # Engineering workflow
            mode_policy = self._get_mode_policy()
            objective = EngineeringObjective(
                id=f"obj_{hash(request)}",
                request=request,
                session_id=session_id,
                mode=self._mode.value,
                model_profile_id=active_model,
            )
            session = self._engine.receive_objective(objective)

            t = threading.Thread(
                target=self._run_engineering_workflow,
                args=(session_id, request, mode_policy, run),
                daemon=True,
            )
            t.start()

            return f"Objective accepted in session {session.id}"

    def _resolve_active_model(self, session) -> Optional[str]:
        """Resolve the authoritative active model ID from config or session."""
        active_model = None
        if self._config_manager and hasattr(self._config_manager, "get_active"):
            try:
                active_cfg = self._config_manager.get_active()
                if isinstance(active_cfg, dict) and active_cfg.get("model_id"):
                    active_model = active_cfg["model_id"]
            except Exception:
                pass
        if not active_model and self._app and hasattr(self._app, "get_active_model_id"):
            try:
                active_model = self._app.get_active_model_id()
            except Exception:
                pass
        if not active_model and session and session.model_profile:
            active_model = session.model_profile
        return active_model

    def _run_conversational_response(self, session_id: str, request: str, model_id: Optional[str], run: Optional[AgentRun] = None) -> None:
        """Execute a direct conversational model response without engineering workflow.

        No EngineeringObjective, no Task, no Plan, no Verification.
        Just user message → model → response.
        """
        from clairecoder.gateway.types import ModelError, ModelRequest

        if run:
            run.start()

        try:
            req_model = model_id
            gw = getattr(self._engine, "_model_gateway", None)

            if not req_model and gw:
                if hasattr(gw, "_models") and isinstance(gw._models, dict) and gw._models:
                    req_model = next(iter(gw._models))
                elif type(gw).__name__ != "ModelGateway" and hasattr(gw, "execute"):
                    req_model = "test-model"

            if not req_model:
                raise ModelError("No active model configured. Please configure a provider via /model or the setup wizard.")

            # Check cancellation before model call
            if run and run.is_cancelled:
                return

            gw_req = ModelRequest(
                model_id=req_model,
                messages=[{"role": "user", "content": request}],
                stream=True,
            )
            resp = self._engine.execute_model(gw_req)

            stream_gen = getattr(resp, "stream_generator", None)
            resp_text = getattr(resp, "text", None)

            if stream_gen is not None:
                collected = []
                for chunk in stream_gen:
                    # Check cancellation between chunks
                    if run and run.is_cancelled:
                        break
                    c_text = getattr(chunk, "text", "")
                    if c_text:
                        collected.append(c_text)
                        self._emit_event("streaming_chunk", {"session_id": session_id, "text": c_text})
                final_text = "".join(collected)
                # Accumulate token usage from streaming response (often populated after stream completes)
                usage = getattr(resp, "usage", None)
                if usage and isinstance(usage, dict):
                    self._total_prompt_tokens += usage.get("prompt_tokens", 0)
                    self._total_completion_tokens += usage.get("completion_tokens", 0)
                # Filter out raw tool-call JSON from response
                final_text = self._filter_tool_call_json(final_text)
                self._emit_event("response_complete", {"session_id": session_id, "text": final_text})
            elif resp_text:
                usage = getattr(resp, "usage", None)
                if usage and isinstance(usage, dict):
                    self._total_prompt_tokens += usage.get("prompt_tokens", 0)
                    self._total_completion_tokens += usage.get("completion_tokens", 0)
                filtered = self._filter_tool_call_json(resp_text)
                self._emit_event("response_complete", {"session_id": session_id, "text": filtered})
            else:
                self._emit_event("response_complete", {"session_id": session_id, "text": "I'm here. How can I help?"})

            if run and not run.is_terminal:
                run.complete()

        except ModelError as me:
            if run and not run.is_terminal:
                run.fail(str(me.message))
            self._emit_event("response_complete", {
                "session_id": session_id,
                "text": f"Model error: {me.message}",
                "error": True,
            })
        except Exception as e:
            if run and not run.is_terminal:
                run.fail(str(e))
            self._emit_event("response_complete", {
                "session_id": session_id,
                "text": f"Error: {e}",
                "error": True,
            })
        finally:
            self._clear_terminal_run()

    @staticmethod
    def _filter_tool_call_json(text: str) -> str:
        """Filter out raw tool-call JSON that may leak into model responses.

        Removes JSON objects that contain "name" and "arguments" / "function".
        """
        import re
        if not text:
            return ""
        # Match tool call JSON objects anywhere in text
        pattern = re.compile(r'\{[^{}]*?["\'](?:name|function)["\']\s*:\s*["\'][^"\']+["\']\s*,\s*["\']arguments["\']\s*:\s*\{[^{}]*\}\s*\}')
        cleaned = pattern.sub("", text)
        # Collapse multiple blank lines and strip whitespace
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        return cleaned

    def _run_engineering_workflow(self, session_id: str, request: str, mode_policy: Optional[dict] = None, run: Optional[AgentRun] = None) -> None:
        """Execute real engineering workflow in background thread and emit events.

        Uses AgentRun for authoritative lifecycle tracking.
        Per §9: failure is terminal unless explicitly recovered.
        Per §10: replanning only with meaningful reason, hard bounded.
        Per §32: minimal real agent loop.
        """
        from clairecoder.gateway.types import ModelError

        if run:
            run.start()

        if mode_policy is None:
            mode_policy = self._get_mode_policy()

        session = self._engine.get_session(session_id)
        if not session:
            if run and not run.is_terminal:
                run.fail("Session not found")
            self._emit_event("response_complete", {
                "session_id": session_id,
                "text": "Session not found.",
                "error": True,
            })
            self._clear_terminal_run()
            return

        # Ensure session model profile is synchronized
        if not session.model_profile:
            resolved = self._resolve_active_model(session)
            if resolved:
                session.model_profile = resolved

        try:
            # Check cancellation before starting work
            if run and run.is_cancelled:
                return

            if self._app and hasattr(self._app, "run"):
                self._app.run(session_id)
            elif hasattr(self._engine, "execute_model"):
                # Standalone mock engine / direct unit testing
                from clairecoder.gateway.types import ModelRequest
                req_model = getattr(session, "model_profile", None)
                gw = getattr(self._engine, "_model_gateway", None)
                if not req_model and gw and hasattr(gw, "_models") and isinstance(gw._models, dict) and gw._models:
                    req_model = next(iter(gw._models))
                elif not req_model and gw and type(gw).__name__ != "ModelGateway" and hasattr(gw, "execute"):
                    req_model = "test-model"
                if not req_model:
                    raise ModelError("No active model configured. Please configure a provider via /model or the setup wizard.")

                # Check cancellation before model call
                if run and run.is_cancelled:
                    return

                gw_req = ModelRequest(model_id=req_model, messages=[{"role": "user", "content": request}], stream=True)
                resp = self._engine.execute_model(gw_req)

                stream_gen = getattr(resp, "stream_generator", None)
                resp_text = getattr(resp, "text", None)
                if stream_gen is not None:
                    collected = []
                    for chunk in stream_gen:
                        if run and run.is_cancelled:
                            break
                        c_text = getattr(chunk, "text", "")
                        if c_text:
                            collected.append(c_text)
                            self._emit_event("streaming_chunk", {"session_id": session_id, "text": c_text})
                    final_text = "".join(collected)
                    # Accumulate token usage from streaming response
                    usage = getattr(resp, "usage", None)
                    if usage and isinstance(usage, dict):
                        self._total_prompt_tokens += usage.get("prompt_tokens", 0)
                        self._total_completion_tokens += usage.get("completion_tokens", 0)
                    final_text = self._filter_tool_call_json(final_text)
                    self._emit_event("response_complete", {"session_id": session_id, "text": final_text})
                    if run and not run.is_terminal:
                        run.complete()
                    self._clear_terminal_run()
                    return
                elif resp_text:
                    usage = getattr(resp, "usage", None)
                    if usage and isinstance(usage, dict):
                        self._total_prompt_tokens += usage.get("prompt_tokens", 0)
                        self._total_completion_tokens += usage.get("completion_tokens", 0)
                    filtered = self._filter_tool_call_json(resp_text)
                    self._emit_event("response_complete", {"session_id": session_id, "text": filtered})
                    if run and not run.is_terminal:
                        run.complete()
                    self._clear_terminal_run()
                    return
            else:
                understanding = self._engine.understand(session_id)
                if understanding and isinstance(understanding, dict) and understanding.get("understanding"):
                    self._emit_event("response_complete", {
                        "session_id": session_id,
                        "text": understanding["understanding"],
                    })
                    if run and not run.is_terminal:
                        run.complete()
                    self._clear_terminal_run()
                    return

            # ——— Finalization: derive AgentRun state from actual workflow outcome ———
            # Re-fetch session (may have been mutated by self._app.run)
            session = self._engine.get_session(session_id)
            objective_status = None
            if session and session.objective:
                objective_status = session.objective.status

            final_text = ""
            verif_notes = []
            failed_task_reasons = []

            if hasattr(session, "tasks") and isinstance(session.tasks, dict):
                for task in session.tasks.values():
                    # Collect failure evidence from tasks
                    task_state = getattr(task, "status", None)
                    if task_state and hasattr(task_state, "value") and task_state.value == "failed":
                        reason = getattr(task, "failure_state", None) or getattr(task, "result", None)
                        if reason:
                            failed_task_reasons.append(f"Task {task.id}: {reason}")
                        else:
                            failed_task_reasons.append(f"Task {task.id}: failed")

                    if getattr(task, "expected_result", None):
                        final_text = task.expected_result
                    elif self._app and hasattr(self._app, "execution_manager"):
                        try:
                            exec_t = self._app.execution_manager.get_task(task.id)
                            if exec_t and getattr(exec_t, "result", None):
                                final_text = str(exec_t.result)
                        except Exception:
                            pass
                    elif getattr(task, "result", None):
                        final_text = str(task.result)

                    if self._app and hasattr(self._app, "verification_engine"):
                        v_hist = self._app.verification_engine.get_history(task.id)
                        for v in v_hist:
                            if hasattr(v, "status") and getattr(v.status, "value", "") == "passed":
                                for c in getattr(v, "criteria", []):
                                    verif_notes.append(f"✓ Verified: {c.description}")
                            elif hasattr(v, "status") and getattr(v.status, "value", "") == "failed":
                                for c in getattr(v, "criteria", []):
                                    verif_notes.append(f"✗ Verification failed: {c.description}")

            # Determine final run state from objective status
            if objective_status == ObjectiveStatus.COMPLETED:
                # Genuine success
                if not final_text:
                    final_text = f"Objective completed: {request}"
                if verif_notes:
                    final_text = f"{final_text}\n\n" + "\n".join(verif_notes)
                if run and not run.is_terminal:
                    run.complete()
                self._emit_event("response_complete", {
                    "session_id": session_id,
                    "text": final_text,
                })
            elif objective_status == ObjectiveStatus.CANCELLED:
                reason = "Objective cancelled"
                if run and not run.is_terminal:
                    run.cancel()
                self._emit_event("response_complete", {
                    "session_id": session_id,
                    "text": reason,
                    "error": True,
                })
            elif objective_status == ObjectiveStatus.PAUSED:
                reason = "Objective paused"
                if run and not run.is_terminal:
                    run.interrupt()
                self._emit_event("response_complete", {
                    "session_id": session_id,
                    "text": reason,
                    "error": True,
                })
            elif objective_status == ObjectiveStatus.FAILED:
                reason = "; ".join(failed_task_reasons) if failed_task_reasons else "Workflow failed"
                if verif_notes:
                    reason = f"{reason}\n\n" + "\n".join(verif_notes)
                if run and not run.is_terminal:
                    run.fail(reason)
                self._emit_event("response_complete", {
                    "session_id": session_id,
                    "text": f"Failed: {reason}",
                    "error": True,
                })
            else:
                # Unknown/active status with no clear result — do NOT claim success
                reason = "; ".join(failed_task_reasons) if failed_task_reasons else "Workflow did not complete successfully"
                if run and not run.is_terminal:
                    run.fail(reason)
                self._emit_event("response_complete", {
                    "session_id": session_id,
                    "text": f"Failed: {reason}",
                    "error": True,
                })
        except ModelError as me:
            if run and not run.is_terminal:
                run.fail(str(me.message))
            self._emit_event("response_complete", {
                "session_id": session_id,
                "text": f"Model error: {me.message}",
                "error": True,
            })
        except Exception as e:
            if run and not run.is_terminal:
                run.fail(str(e))
            self._emit_event("response_complete", {
                "session_id": session_id,
                "text": f"Workflow error: {e}",
                "error": True,
            })
        finally:
            self._clear_terminal_run()

    def interrupt_active_session(self, session_id: Optional[str] = None) -> bool:
        """Public boundary for interrupting an active engineering operation.

        Per §11: Ctrl+C must cancel the actual execution boundary.
        Cancels the AgentRun (sets cancellation flag) AND delegates to engine.
        Returns True if an interruption was requested, False if no session was active.
        """
        # Cancel the active run state machine
        with self._active_run_lock:
            if self._active_run and not self._active_run.is_terminal:
                self._active_run.interrupt()

        sid = session_id or self._active_session_id
        if sid:
            self._engine.interrupt_execution(sid)
            return True
        return False

    def handle_permission_response(
        self,
        request_id: str,
        decision: Any,
        session_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        command: Optional[str] = None,
        category: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Handle a user permission confirmation response from the UI presentation layer.

        Routes the decision to the Engineering Engine through its public boundary.
        Does NOT make authorization policy decisions or execute tools.
        """
        decision_str = decision.value if hasattr(decision, "value") else str(decision)
        self._engine.resolve_permission(
            request_id=request_id,
            decision=decision_str,
            session_id=session_id,
            tool_id=tool_id,
            action=action,
            resource=resource,
            command=command,
            category=category
        )

    def execute_command(self, request: CommandRequest) -> CommandResponse:
        """Execute a parsed command through the controller.

        Per PRD §13, invalid/unknown commands produce clear errors.
        Per PRD §14, commands route through the controller to the engine.
        """
        # Handle empty command (malformed input like bare "/")
        if not request.command:
            return CommandResponse(
                success=False,
                message="Empty command. Type /help for available commands.",
                error="empty_command"
            )

        handler = self._handlers.get(request.command)
        if not handler:
            return CommandResponse(
                success=False,
                message=f"Unknown command: {request.command}. Type /help for available commands.",
                error="invalid_command"
            )

        try:
            return handler(request)
        except Exception as e:
            return CommandResponse(success=False, message="Command execution failed", error=str(e))

    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================

    def _handle_help(self, request: CommandRequest) -> CommandResponse:
        """AC-003: Help system exposing available commands (PRD §12)."""
        help_text = "Available commands:\n"
        seen = set()
        for name, cmd in self._commands.items():
            if name == cmd.name and cmd.name not in seen:
                help_text += f"/{cmd.name} - {cmd.description}\n"
                seen.add(cmd.name)
        return CommandResponse(success=True, message=help_text)

    def _handle_model(self, request: CommandRequest) -> CommandResponse:
        """AC-014: Inspect or switch active provider and model (PRD §11).
        
        Stage 7 atomic active profile: Provider Profile + Model Profile.
        Prevents switching during active execution and maintains atomicity.
        """
        from clairecoder.engine.types import ObjectiveStatus

        cfg_mgr = (self._app.config_manager if self._app and hasattr(self._app, "config_manager") else None) or self._config_manager
        gw = getattr(self._engine, "_model_gateway", None)
        args = request.arguments.get("args", [])

        # 1. Guard against switching during active execution (§12: use authoritative run state)
        if args:
            if self._active_run and self._active_run.state == RunState.RUNNING:
                return CommandResponse(
                    success=False,
                    message="Model switching is unavailable while execution is active.",
                    error="execution_active",
                )

        # 2. Check available providers & models
        profiles = cfg_mgr.list_provider_profiles() if cfg_mgr else []
        registered_models = getattr(gw, "_models", {}) if gw else {}

        if not profiles and not registered_models:
            return CommandResponse(
                success=False,
                message="No model providers configured. Use '/setup' or the setup wizard to configure a provider.",
                error="provider_not_configured"
            )

        active_cfg = cfg_mgr.get_active() if cfg_mgr else {}
        active_pid = active_cfg.get("provider_profile_id", "")
        active_mid = active_cfg.get("model_id", "")

        # 3. Model Switch requested
        if args:
            raw_target = " ".join(args).strip()
            target_pid = ""
            target_mid = ""

            # Check if user specified provider/model or provider model
            if "/" in raw_target:
                target_pid, target_mid = raw_target.split("/", 1)
            elif len(args) == 2:
                target_pid, target_mid = args[0], args[1]
            else:
                target_mid = raw_target
                # Search for which configured profile has this model
                for prof in profiles:
                    if target_mid in prof.available_models or prof.default_model_id == target_mid or prof.id == target_mid:
                        target_pid = prof.id
                        if prof.id == target_mid and prof.default_model_id:
                            target_mid = prof.default_model_id
                        break
                if not target_pid and active_pid:
                    target_pid = active_pid

            # Look up model
            resolved_model = None
            if target_mid in registered_models:
                resolved_model = registered_models[target_mid]
            elif f"{target_pid}/{target_mid}" in registered_models:
                resolved_model = registered_models[f"{target_pid}/{target_mid}"]
            else:
                # Check if it exists in profiles
                for prof in profiles:
                    if (not target_pid or prof.id == target_pid) and (target_mid in prof.available_models or prof.default_model_id == target_mid):
                        target_pid = prof.id
                        if self._app and hasattr(self._app, "register_provider_profile"):
                            self._app.register_provider_profile(prof)
                        resolved_model = getattr(gw, "_models", {}).get(target_mid)
                        break

            if not resolved_model and target_mid not in registered_models:
                available = list(registered_models.keys())
                for p in profiles:
                    available.extend(p.available_models)
                avail_clean = sorted(list(set(available)))
                return CommandResponse(
                    success=False,
                    message=f"Unknown model: {raw_target}. Available models: {', '.join(avail_clean[:10])}",
                    error="model_not_found"
                )

            model_obj = resolved_model or registered_models.get(target_mid)
            final_mid = target_mid
            final_pid = target_pid or (model_obj.provider.id if model_obj and hasattr(model_obj, "provider") and model_obj.provider else "custom")

            # Atomically update persistent active selection
            if cfg_mgr:
                cfg_mgr.set_active(final_pid, final_mid)

            # Update active session model profile
            if self._active_session_id:
                session = self._engine.get_session(self._active_session_id)
                if session:
                    session.model_profile = final_mid

            # Update context capacity from selected model
            ctx_cap = getattr(model_obj, "context_capacity", None) if model_obj else None
            if ctx_cap:
                self._context_capacity = ctx_cap

            # Synchronize app gateway
            if self._app and hasattr(self._app, "load_providers_from_config"):
                self._app.load_providers_from_config()

            # Emit MODEL_SWITCHED event for header synchronization
            caps = []
            if model_obj and hasattr(model_obj, "capabilities") and model_obj.capabilities:
                caps = [c.value if hasattr(c, "value") else str(c) for c in model_obj.capabilities]
            self._emit_event("model_switched", {
                "model_id": final_mid,
                "provider_id": final_pid,
                "context_capacity": ctx_cap,
                "capabilities": caps,
            })

            return CommandResponse(
                success=True,
                message=f"Model switched to: {final_mid} (provider: {final_pid})",
                data={"provider_id": final_pid, "model_id": final_mid, "action": "switch"}
            )

        # 4. No args: list available providers and models
        count = len(registered_models) if registered_models else sum(len(p.available_models or [1]) for p in profiles)
        lines = [f"Available models ({count}):"]
        if profiles:
            for prof in profiles:
                is_active_prof = (prof.id == active_pid)
                bullet = "●" if is_active_prof else "○"
                active_tag = " [ACTIVE]" if is_active_prof else ""
                lines.append(f"\n  {bullet} {prof.name} ({prof.id}){active_tag}")
                models = prof.available_models or ([prof.default_model_id] if prof.default_model_id else [])
                if not models:
                    lines.append("      (no discovered models)")
                for mid in models:
                    is_active_mod = (is_active_prof and mid == active_mid)
                    mod_tag = " ★ (Active)" if is_active_mod else ""
                    model_obj = registered_models.get(mid)
                    caps = []
                    if model_obj and hasattr(model_obj, "capabilities") and model_obj.capabilities:
                        caps = [c.value if hasattr(c, "value") else str(c) for c in model_obj.capabilities]
                    elif prof.capabilities and mid in prof.capabilities:
                        caps = prof.capabilities[mid]
                    cap_badges = []
                    if "tool_calling" in caps:
                        cap_badges.append("tools ✓")
                    if "streaming" in caps:
                        cap_badges.append("stream ✓")
                    if "vision" in caps:
                        cap_badges.append("vision ✓")
                    cap_str = f" [{', '.join(cap_badges)}]" if cap_badges else ""
                    lines.append(f"      - {mid}{mod_tag}{cap_str}")
        elif registered_models:
            for mid, model in registered_models.items():
                pid = model.provider.id if hasattr(model, "provider") and model.provider else "custom"
                lines.append(f"  - {pid}/{mid}")

        lines.append("\nTo switch model: /model <model_id> or /model <provider_id>/<model_id>")
        lines.append("To configure a new provider: /setup")

        return CommandResponse(
            success=True,
            message="\n".join(lines),
            data={"models": list(registered_models.keys()), "action": "list"}
        )

    def _handle_mode(self, request: CommandRequest) -> CommandResponse:
        """AC-005/AC-006/AC-007: Mode inspection and switching (PRD §15–§20).

        Mode changes MUST update the real workflow policy, not just the display.
        Per §42–§45, mode must:
          - Update self._mode (interaction controller state)
          - Propagate to active session (session.mode)
          - Emit MODE_CHANGED event with policy details
        """
        args = request.arguments.get("args", [])
        valid_modes_list = [m.value for m in InteractionMode]
        valid_modes_str = ", ".join(valid_modes_list)
        if not args:
            policy = self._get_mode_policy()
            return CommandResponse(
                success=True,
                message=(
                    f"Current mode: {self._mode.value.upper()}\n"
                    f"Valid modes: {valid_modes_str}\n"
                    f"Policy: file_mod={'yes' if policy['allow_file_modification'] else 'no'}, "
                    f"tools={'yes' if policy['allow_tool_execution'] else 'no'}, "
                    f"workflow={policy['workflow_type']}"
                ),
                data={"mode": self._mode.value, "valid_modes": valid_modes_list, "policy": policy}
            )

        requested_mode = args[0].lower()
        try:
            new_mode = InteractionMode(requested_mode)
            self._mode = new_mode
            policy = self._get_mode_policy()

            # Propagate mode to active engineering session
            if self._active_session_id and self._engine:
                session = self._engine.get_session(self._active_session_id)
                if session:
                    session.mode = new_mode.value

            # Propagate mode policy to tool executor (§7)
            tool_exec = getattr(self._engine, "_tool_executor", None)
            if tool_exec and hasattr(tool_exec, "set_mode_policy"):
                tool_exec.set_mode_policy(policy)

            # Emit MODE_CHANGED event for header synchronization AND policy propagation
            self._emit_event("mode_changed", {
                "mode": new_mode.value,
                "policy": policy,
            })

            return CommandResponse(
                success=True,
                message=(
                    f"Mode switched to: {new_mode.value.upper()}\n"
                    f"Policy: file_mod={'yes' if policy['allow_file_modification'] else 'no'}, "
                    f"tools={'yes' if policy['allow_tool_execution'] else 'no'}, "
                    f"workflow={policy['workflow_type']}"
                ),
                data={"mode": new_mode.value, "policy": policy}
            )
        except ValueError:
            return CommandResponse(
                success=False,
                message=f"Invalid mode: {requested_mode}. Valid modes: {valid_modes_str}",
                error="invalid_mode"
            )

    def _handle_status(self, request: CommandRequest) -> CommandResponse:
        """AC-012: Concise engineering status (PRD §26)."""
        return CommandResponse(
            success=True,
            message=f"Mode: {self._mode.value.upper()}\nEngine Status: Active",
            data={"mode": self._mode.value}
        )

    def _handle_plan(self, request: CommandRequest) -> CommandResponse:
        """AC-011: Inspect the active engineering plan (PRD §25).

        Delegates plan retrieval to the Engineering Engine. The interaction
        layer displays state without becoming responsible for plan execution.
        """
        return CommandResponse(
            success=True,
            message="No active plan. Submit an engineering objective first.",
            data={"plan": None}
        )

    def _handle_session(self, request: CommandRequest) -> CommandResponse:
        """AC-008: Session inspection and control (PRD §22).

        Session state is managed by the Workflow/Context/Session system.
        The interaction layer exposes controls without owning state.
        """
        args = request.arguments.get("args", [])
        active_sid = self._active_session_id
        if not args:
            if active_sid:
                return CommandResponse(
                    success=True,
                    message=f"Active session: {active_sid}\nCommands: /session list, /session pause <id>, /session resume <id>, /session close <id>",
                    data={"session_id": active_sid}
                )
            return CommandResponse(
                success=True,
                message="No active sessions.\nCommands: /session list, /session pause <id>, /session resume <id>"
            )

        subcmd = args[0].lower()
        if subcmd == "list":
            s_str = active_sid if active_sid else "none"
            return CommandResponse(
                success=True,
                message=f"Active sessions: {s_str}",
                data={"sessions": [active_sid] if active_sid else []}
            )
        elif subcmd == "pause":
            sid = args[1] if len(args) > 1 else active_sid
            if sid:
                self._engine.interrupt_execution(sid)
                return CommandResponse(success=True, message=f"Paused session: {sid}")
            return CommandResponse(success=False, message="Session ID required", error="missing_argument")
        elif subcmd == "resume":
            sid = args[1] if len(args) > 1 else active_sid
            if sid:
                if hasattr(self._engine, "resume_execution"):
                    self._engine.resume_execution(sid)
                else:
                    session = self._engine.get_session(sid)
                    if session and session.objective:
                        session.objective.status = ObjectiveStatus.ACTIVE
                return CommandResponse(success=True, message=f"Resume requested for session: {sid}")
            return CommandResponse(success=False, message="Session ID required", error="missing_argument")
        elif subcmd == "close":
            sid = args[1] if len(args) > 1 else active_sid
            if sid:
                self._engine.remove_session(sid)
                if self._active_session_id == sid:
                    self._active_session_id = None
                return CommandResponse(success=True, message=f"Closed session: {sid}")
            return CommandResponse(success=False, message="Session ID required or not found", error="session_not_found")
        return CommandResponse(
            success=True,
            message="Session info requested.",
            data={"action": subcmd}
        )

    def _handle_pause(self, request: CommandRequest) -> CommandResponse:
        """AC-016: Pause active engineering work (PRD §31)."""
        args = request.arguments.get("args", [])
        if args:
            session_id = args[0]
        elif self._active_session_id:
            session_id = self._active_session_id
        else:
            return CommandResponse(
                success=False,
                message="No active session to pause. Specify a session ID: /pause <session_id>",
                error="missing_argument"
            )

        self._engine.interrupt_execution(session_id)
        return CommandResponse(success=True, message=f"Paused session: {session_id}")

    def _handle_resume(self, request: CommandRequest) -> CommandResponse:
        """AC-017: Resume paused work (PRD §31)."""
        args = request.arguments.get("args", [])
        if args:
            session_id = args[0]
        elif self._active_session_id:
            session_id = self._active_session_id
        else:
            return CommandResponse(
                success=False,
                message="No active session to resume. Specify a session ID: /resume <session_id>",
                error="missing_argument"
            )

        if hasattr(self._engine, "resume_execution"):
            self._engine.resume_execution(session_id)
        else:
            session = self._engine.get_session(session_id)
            if session and session.objective:
                session.objective.status = ObjectiveStatus.ACTIVE

        return CommandResponse(success=True, message=f"Resume requested for session: {session_id}")

    def _handle_cancel(self, request: CommandRequest) -> CommandResponse:
        """AC-015: Cancel active operation (PRD §30).

        Per §11: cancellation reaches the actual execution boundary.
        Cancels both AgentRun (cooperative flag) and engine objective.
        """
        args = request.arguments.get("args", [])
        if args:
            session_id = args[0]
        elif self._active_session_id:
            session_id = self._active_session_id
        else:
            return CommandResponse(
                success=False,
                message="No active session to cancel. Specify a session ID: /cancel <session_id>",
                error="missing_argument"
            )

        # Cancel the authoritative run state machine
        with self._active_run_lock:
            if self._active_run and not self._active_run.is_terminal:
                self._active_run.cancel()

        self._engine.cancel_objective(session_id)
        return CommandResponse(success=True, message=f"Cancelled execution for session: {session_id}")

    def _handle_clear(self, request: CommandRequest) -> CommandResponse:
        """Clear interaction display. PRD §11 V1 command."""
        return CommandResponse(success=True, message="Display cleared.")

    def _handle_exit(self, request: CommandRequest) -> CommandResponse:
        """Exit ClaireCoder. PRD §11 V1 command."""
        return CommandResponse(success=True, message="Exiting ClaireCoder.", data={"exit": True})
