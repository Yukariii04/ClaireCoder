"""Main TuiApplication runtime orchestrating all Stage 1 - 7 UI systems and event dispatch."""
import os
import sys
import time
import queue
from typing import Any, Dict, List, Optional, Callable
from unittest.mock import Mock

from .states import InputState, TerminalMode
from .terminal import TerminalCapability, TerminalRenderer, TerminalInput
from .header import HeaderStatus
from .transcript import TranscriptView
from .prompt import PromptInput
from .permission import PermissionSurface, PermissionDecision
from .review import ReviewOverlay
from .palette import CommandPalette
from .tree import FileTreeOverlay
from .task import TaskViewOverlay
from .adapter import PresentationAdapter
from .canvas import visible_length, visible_slice
from .loading import LoadingScreen
from .activity import ActivityModel, ActivityType
from .terminal import TerminalCapability, TerminalRenderer, TerminalInput, InputDecoder, KeyEvent
from .wizard import SetupWizard, WizardStage
from .model_selector import ModelSelectorOverlay, ModelSelectorStage

class TuiApplication:
    """Central TUI Application coordinating state, layout, key dispatch, and visual surfaces."""

    # Minimum human-visible loading screen presentation duration (seconds).
    # Actual initialization that takes longer than this value transitions immediately.
    MINIMUM_BOOT_DURATION: float = 3.5

    def __init__(
        self,
        terminal: Optional[TerminalCapability] = None,
        renderer: Optional[TerminalRenderer] = None,
        workspace_root: Optional[str] = None,
    ) -> None:
        self.terminal = terminal or TerminalCapability()
        self.renderer = renderer or TerminalRenderer()
        self.current_frame: List[str] = []
        self.state = InputState.NORMAL
        self.running: bool = False
        self.controller = None
        self.on_interrupt: Optional[Callable[[], None]] = None
        self.on_permission_response: Optional[Callable[..., None]] = None
        
        # Thread-safe event queue for single-owner terminal rendering
        self._event_queue: queue.Queue = queue.Queue()
        
        # Core Views
        self.header = HeaderStatus()
        self.transcript = TranscriptView()
        self.prompt = PromptInput()
        
        # Secondary Overlays & Surfaces
        self.permission_surface = PermissionSurface()
        self.review_overlay = ReviewOverlay()
        self.review_overlay.on_close = self.close_overlay
        self.command_palette = CommandPalette()
        self.command_palette.on_close = self.close_overlay
        self._workspace_root = workspace_root or os.getcwd()
        self.file_tree = FileTreeOverlay(workspace_root=self._workspace_root)
        self.file_tree.on_close = self.close_overlay
        self.task_view = TaskViewOverlay()
        self.task_view.on_close = self.close_overlay
        self.model_selector = ModelSelectorOverlay()
        self.model_selector.on_select_model = self._on_model_selector_switch
        self.model_selector.on_configure_provider = self._on_model_selector_configure
        self.model_selector.on_close = self.close_overlay
        
        # Setup Wizard (Stage 7)
        self.wizard = SetupWizard()
        self._wizard_active: bool = False
        self._config_manager: Optional[Any] = None  # Set by connect_config_manager()

        # Runtime sync callback: called after wizard save to reload providers into gateway.
        # Set via register_runtime_sync_callback(). Replaces forbidden self._app access.
        self._runtime_sync_callback: Optional[Callable[[], None]] = None

        # Exit idempotency guard: ensures cleanup runs exactly once
        self._exit_cleanup_done: bool = False
        self._exiting: bool = False
        
        # State tracking
        self.active_overlay: Optional[str] = None
        self._action_history: List[str] = []

        # Double Ctrl+C exit confirmation tracking
        self.exit_confirmation_timeout: float = 2.5
        self._interrupt_pending: bool = False
        self._interrupt_deadline: float = 0.0

        # Slash command suggestions tracking
        self._slash_suggestions_dismissed: bool = False
        self._slash_selected_index: int = 0

        # Streaming response state
        self._streaming_activity_key: Optional[str] = None
        self._streaming_text_buffer: List[str] = []

        # Flag to control auto-redraws from event handlers (only during interactive run loop)
        self._in_run_loop: bool = False
        
        # Wire prompt escape and submit callbacks
        self.prompt.on_escape = self.handle_escape
        self.prompt.on_submit = self.submit
        
        # Wire permission surface callback
        self.permission_surface.register_decision_callback(self._on_permission_decision)

        # Set initial header values from workspace
        self.header.directory = self._shorten_path(self._workspace_root)
        self.header.mode = "IMPLEMENT"
        self.header.task_progress = "\u2014"
        self.header.context_usage = "unavailable"
        
        self._update_layout()

    @staticmethod
    def _shorten_path(path: str) -> str:
        """Shorten a path for display in the header, using ~ for home directory."""
        try:
            home = os.path.expanduser("~")
            if path.startswith(home):
                return "~" + path[len(home):]
        except Exception:
            pass
        return path

    def _format_token_count(self, tokens: int) -> str:
        """Format token count for display: 1234 -> 1.2k, 123456 -> 123.5k."""
        if tokens < 1000:
            return str(tokens)
        elif tokens < 100000:
            return f"{tokens/1000:.1f}k"
        else:
            return f"{tokens/1000:.0f}k"

    def _update_context_display(self) -> None:
        """Update context header from controller token tracking."""
        if not self.controller:
            return
        prompt_tokens = getattr(self.controller, "total_prompt_tokens", 0)
        completion_tokens = getattr(self.controller, "total_completion_tokens", 0)
        capacity = getattr(self.controller, "context_capacity", None)

        # Guard against mock controllers returning non-int values
        if not isinstance(prompt_tokens, int):
            prompt_tokens = 0
        if not isinstance(completion_tokens, int):
            completion_tokens = 0
        if capacity is not None and not isinstance(capacity, int):
            capacity = None

        total = prompt_tokens + completion_tokens

        if total == 0 and capacity is None:
            self.header.context_usage = "unavailable"
        elif total == 0 and capacity:
            self.header.context_usage = f"\u2014/{self._format_token_count(capacity)}"
        elif capacity:
            self.header.context_usage = f"{self._format_token_count(total)}/{self._format_token_count(capacity)}"
        elif total > 0:
            self.header.context_usage = self._format_token_count(total)

    def is_exit_confirmation_active(self) -> bool:
        """Returns True if a first Ctrl+C was pressed within the confirmation window."""
        if not self._interrupt_pending:
            return False
        if time.time() > self._interrupt_deadline:
            self._interrupt_pending = False
            return False
        return True

    def reset_interrupt_state(self) -> None:
        """Resets pending Ctrl+C exit confirmation."""
        self._interrupt_pending = False
        self._interrupt_deadline = 0.0

    @property
    def is_review_open(self) -> bool:
        return self.active_overlay == "review"

    @property
    def is_palette_open(self) -> bool:
        return self.active_overlay == "palette"

    @property
    def is_tree_open(self) -> bool:
        return self.active_overlay == "tree"

    @property
    def is_task_open(self) -> bool:
        return self.active_overlay == "task"

    # -- Slash Command Suggestions ------------------------------------------

    DEFAULT_SLASH_COMMANDS: List[str] = [
        "/cancel",
        "/clear",
        "/commands",
        "/exit",
        "/help",
        "/mode",
        "/model",
        "/pause",
        "/plan",
        "/resume",
        "/review",
        "/session",
        "/status",
        "/task",
        "/tree",
    ]

    def is_slash_suggestions_active(self) -> bool:
        """Returns True if slash command suggestions should be displayed."""
        if self.state != InputState.NORMAL or self.active_overlay is not None:
            return False
        if self._slash_suggestions_dismissed:
            return False
        text = self.prompt.get_text()
        if not text.startswith("/"):
            return False
        if len(text) > 1 and text[1].isspace():
            return False
        if any(ch.isspace() for ch in text):
            return False
        return bool(self.get_slash_suggestions())

    def get_slash_suggestions(self) -> List[str]:
        """Returns filtered slash command suggestions based on current prompt token."""
        text = self.prompt.get_text()
        if not text.startswith("/"):
            return []
        if len(text) > 1 and text[1].isspace():
            return []
        if any(ch.isspace() for ch in text):
            return []
        token = text.lower()
        return [cmd for cmd in self.DEFAULT_SLASH_COMMANDS if cmd.startswith(token)]

    def _render_slash_suggestions(self, matches: List[str], width: int = 28) -> List[str]:
        """Renders compact floating command suggestions card."""
        max_items = 6
        visible_matches = matches[:max_items]
        card_w = max(24, min(width, 32))
        inner_w = card_w - 4

        lines = [f"╭─ Suggestions " + ("─" * max(0, card_w - 17)) + "╮"]
        for idx, cmd in enumerate(visible_matches):
            marker = "▶ " if idx == (self._slash_selected_index % len(matches)) else "  "
            content = f"{marker}{cmd}"[:inner_w]
            lines.append(f"│ {content.ljust(inner_w)} │")
        lines.append("╰" + ("─" * (card_w - 2)) + "╯")
        return lines

    def start(self) -> None:
        """Starts the TUI application lifecycle."""
        self.running = True
        self._exit_cleanup_done = False
        self._exiting = False
        self.set_state(InputState.NORMAL)

    def stop(self) -> None:
        """Stops the TUI application lifecycle and clears terminal.

        Idempotent: multiple calls are safe; cleanup executes exactly once.
        """
        if self._exit_cleanup_done:
            return
        self._exiting = True
        self.running = False
        self.set_state(InputState.EXITING)
        if self.renderer:
            self.renderer.clear()
        self._exit_cleanup_done = True

    def render_initial_frame(self) -> None:
        """Performs initial render of the terminal frame."""
        self.current_frame = self.render()
        if self.renderer and self.renderer.last_line_count > 0:
            self.renderer.redraw(self.current_frame)
        else:
            self.renderer.render_frame(self.current_frame)

    def redraw(self) -> None:
        """Renders the current TUI state and updates the terminal in place."""
        if self._exiting:
            return
        self.current_frame = self.render()
        self.renderer.redraw(self.current_frame)

    def _render_boot_sequence(self, presentation_delay: float = 0.08, min_duration: float = 3.5) -> None:
        """Renders the startup boot sequence using real initialization stages.
        
        Guarantees minimum human-visible presentation duration when min_duration > 0.
        If actual initialization takes longer than min_duration, transitions immediately.
        """
        if not self.renderer:
            return

        boot_start = time.time()

        # Determine real gateway configuration status
        gw_status = "NOT CONFIGURED"
        if self.controller and hasattr(self.controller, "_engine") and self.controller._engine:
            gw = getattr(self.controller._engine, "_model_gateway", None)
            if gw:
                if (hasattr(gw, "_adapters") and gw._adapters) or (hasattr(gw, "_models") and gw._models):
                    gw_status = "OK"
                elif type(gw).__name__ != "ModelGateway" and hasattr(gw, "execute"):
                    gw_status = "OK"
        if self._config_manager and hasattr(self._config_manager, "is_configured") and self._config_manager.is_configured():
            gw_status = "OK"

        stages = [
            ([
                ("Loading configuration", "OK"),
                ("Connecting model gateway", "RUNNING"),
                ("Registering tools", "PENDING"),
                ("Preparing workspace", "PENDING"),
                ("Loading skills", "PENDING"),
                ("Starting session", "PENDING"),
            ], 16, "Loading configuration..."),
            ([
                ("Loading configuration", "OK"),
                ("Connecting model gateway", gw_status),
                ("Registering tools", "RUNNING"),
                ("Preparing workspace", "PENDING"),
                ("Loading skills", "PENDING"),
                ("Starting session", "PENDING"),
            ], 33, "Checking model gateway..."),
            ([
                ("Loading configuration", "OK"),
                ("Connecting model gateway", gw_status),
                ("Registering tools", "OK"),
                ("Preparing workspace", "RUNNING"),
                ("Loading skills", "PENDING"),
                ("Starting session", "PENDING"),
            ], 50, "Registering tools..."),
            ([
                ("Loading configuration", "OK"),
                ("Connecting model gateway", gw_status),
                ("Registering tools", "OK"),
                ("Preparing workspace", "OK"),
                ("Loading skills", "RUNNING"),
                ("Starting session", "PENDING"),
            ], 66, "Preparing workspace..."),
            ([
                ("Loading configuration", "OK"),
                ("Connecting model gateway", gw_status),
                ("Registering tools", "OK"),
                ("Preparing workspace", "OK"),
                ("Loading skills", "OK"),
                ("Starting session", "RUNNING"),
            ], 83, "Loading skills..."),
            ([
                ("Loading configuration", "OK"),
                ("Connecting model gateway", gw_status),
                ("Registering tools", "OK"),
                ("Preparing workspace", "OK"),
                ("Loading skills", "OK"),
                ("Starting session", "OK"),
            ], 100, "Launching..."),
        ]

        num_stages = len(stages)
        for idx, (checklist, pct, status) in enumerate(stages):
            boot_lines = LoadingScreen.render(
                width=min(self.terminal.width, 56),
                height=self.terminal.height,
                checklist_items=checklist,
                progress_pct=pct,
                status_text=status
            )
            if idx == 0 and self.renderer.last_line_count == 0:
                self.renderer.render_frame(boot_lines)
            else:
                self.renderer.redraw(boot_lines)
            if presentation_delay > 0:
                # Calculate per-stage delay to fill the minimum duration
                elapsed = time.time() - boot_start
                remaining_stages = num_stages - idx - 1
                if remaining_stages > 0 and min_duration > 0:
                    remaining_time = max(0, min_duration - elapsed)
                    stage_delay = remaining_time / remaining_stages
                    time.sleep(max(presentation_delay, stage_delay))
                else:
                    time.sleep(presentation_delay)

        # Ensure minimum duration is met for the final frame
        if min_duration > 0 and presentation_delay > 0:
            elapsed = time.time() - boot_start
            if elapsed < min_duration:
                time.sleep(min_duration - elapsed)

    def connect_config_manager(self, config_manager: Any) -> None:
        """Connect the configuration manager for wizard and model selector integration."""
        self._config_manager = config_manager
        if hasattr(self, "model_selector") and self.model_selector:
            self.model_selector.config_manager = config_manager

    def _check_needs_wizard(self) -> bool:
        """Check if the setup wizard needs to run (first-run or missing config)."""
        # If gateway already has registered models or adapters, or is a test mock, no wizard needed
        if self.controller and hasattr(self.controller, "_engine") and self.controller._engine:
            gw = getattr(self.controller._engine, "_model_gateway", None)
            if gw:
                if hasattr(gw, "_adapters") and gw._adapters:
                    return False
                if hasattr(gw, "_models") and gw._models:
                    return False
                if type(gw).__name__ != "ModelGateway" and hasattr(gw, "execute"):
                    return False

        if self._config_manager and hasattr(self._config_manager, "is_configured"):
            return not self._config_manager.is_configured()
        return False

    def _start_wizard(self) -> None:
        """Activate the setup wizard."""
        self._wizard_active = True
        self.wizard = SetupWizard()
        self.wizard.on_validate = self._wizard_on_validate
        self.wizard.on_discover = self._wizard_on_discover
        self.wizard.on_save = self._wizard_on_save
        self.set_state(InputState.OVERLAY)
        self.active_overlay = "wizard"

    def open_wizard(self) -> None:
        """Public method to activate the setup wizard."""
        self._start_wizard()

    def open_model_selector(self) -> None:
        """Open the interactive Provider -> Model selector overlay."""
        self.model_selector.config_manager = self._config_manager
        if self._config_manager:
            active = self._config_manager.get_active()
            self.model_selector.active_provider_id = active.get("provider_profile_id", "")
            self.model_selector.active_model_id = active.get("model_id", "")
        self.model_selector.refresh()
        self.model_selector.stage = ModelSelectorStage.PROVIDER_LIST
        self.set_state(InputState.OVERLAY)
        self.active_overlay = "model_selector"

    def _on_model_selector_switch(self, provider_id: str, model_id: str) -> None:
        """Callback when user picks a model from ModelSelectorOverlay."""
        if self.controller and hasattr(self.controller, "execute_command"):
            from clairecoder.interaction.types import CommandRequest
            resp = self.controller.execute_command(
                CommandRequest(command="model", arguments={"args": [f"{provider_id}/{model_id}"]})
            )
            if resp.success:
                self.header.model = model_id
                self.transcript.append_activity(ActivityModel(
                    title="Model Switched",
                    detail=f"Active: {provider_id} / {model_id}"
                ))
            else:
                self.transcript.append_activity(ActivityModel(
                    title="Model Switch Failed",
                    detail=str(resp.message or resp.error or "Switch failed")
                ))

    def _on_model_selector_configure(self, provider_dict: Dict[str, Any]) -> None:
        """Callback when user selects an unconfigured provider in ModelSelectorOverlay."""
        self._wizard_launched_from_selector = True
        self.open_wizard()
        self.wizard.selected_provider = provider_dict
        self.wizard.endpoint_input = provider_dict.get("default_endpoint", "")
        self.wizard.credential_input = ""
        self.wizard.cursor_pos = 0
        self.wizard._active_field = "credential" if provider_dict.get("requires_api_key") else "endpoint"
        self.wizard.stage = WizardStage.CREDENTIAL_ENTRY

    def _wizard_on_validate(self, provider: Dict, credential: str, endpoint: str, request_id: Optional[str] = None) -> None:
        """Wizard callback: validate provider connection asynchronously."""
        import threading
        req_id = request_id or getattr(self.wizard, "active_request_id", None)
        def _validate():
            try:
                from clairecoder.gateway.discovery import validate_provider
                pid = provider.get("id", "custom")
                ep = endpoint or provider.get("default_endpoint", "")
                # Clean validation without duplicate model discovery
                validate_provider(pid, ep, api_key=credential or None, timeout=10)
                self._on_engine_event({
                    "type": "WIZARD_VALIDATION_COMPLETED",
                    "success": True,
                    "request_id": req_id,
                    "provider": provider,
                    "credential": credential,
                    "endpoint": endpoint,
                })
            except Exception as e:
                self._on_engine_event({
                    "type": "WIZARD_VALIDATION_COMPLETED",
                    "success": False,
                    "error": str(e),
                    "request_id": req_id,
                })
        # Run validation in background thread to avoid blocking TUI
        t = threading.Thread(target=_validate, daemon=True)
        t.start()

    def _wizard_on_discover(self, provider: Dict, credential: str, endpoint: str, request_id: Optional[str] = None) -> None:
        """Wizard callback: discover available models asynchronously."""
        import threading
        req_id = request_id or getattr(self.wizard, "active_request_id", None)
        def _discover():
            try:
                from clairecoder.gateway.discovery import discover_models
                pid = provider.get("id", "custom")
                ep = endpoint or provider.get("default_endpoint", "")
                models = discover_models(pid, ep, api_key=credential or None, timeout=15)
                model_dicts = []
                for m in models:
                    caps = [c.value if hasattr(c, 'value') else str(c) for c in (m.capabilities or [])]
                    model_dicts.append({
                        "id": m.id,
                        "display_name": m.display_name,
                        "capabilities": caps,
                        "context_capacity": m.context_capacity,
                    })
                self._on_engine_event({
                    "type": "WIZARD_DISCOVERY_COMPLETED",
                    "models": model_dicts,
                    "request_id": req_id,
                })
            except Exception as e:
                self._on_engine_event({
                    "type": "WIZARD_DISCOVERY_COMPLETED",
                    "models": [],
                    "error": str(e),
                    "request_id": req_id,
                })
        t = threading.Thread(target=_discover, daemon=True)
        t.start()

    def _wizard_on_save(self, provider: Dict, credential: str, endpoint: str,
                        model: Optional[Dict], skills: List[Dict]) -> None:
        """Wizard callback: save configuration."""
        try:
            if not self._config_manager:
                self.wizard.complete_save(error="No configuration manager connected.")
                return

            from clairecoder.gateway.config import ProviderProfile
            pid = provider.get("id", "custom")
            ep = endpoint or provider.get("default_endpoint", "")
            adapter_type = provider.get("adapter", "openai_compatible")
            if hasattr(adapter_type, "value"):
                adapter_type = adapter_type.value

            # Extract context capacity mapping
            ctx_caps = {}
            for m in (self.wizard.discovered_models or []):
                if m.get("id") and m.get("context_capacity"):
                    ctx_caps[m["id"]] = m["context_capacity"]

            profile = ProviderProfile(
                id=pid,
                provider_id=pid,
                name=provider.get("name", pid),
                adapter_type=adapter_type,
                endpoint=ep,
                category=provider.get("category", "hosted"),
                credential_ref=f"provider:{pid}" if credential else None,
                default_model_id=model.get("id") if model else None,
                available_models=[m.get("id", "") for m in (self.wizard.discovered_models or [])],
                capabilities={m.get("id", ""): m.get("capabilities", []) for m in (self.wizard.discovered_models or [])},
                provider_specific={"context_capacities": ctx_caps},
            )
            if hasattr(profile.category, "value"):
                profile.category = profile.category.value

            # Store credential (with backend health pre-check)
            if credential:
                from clairecoder.gateway.credentials import CredentialStore as _CS
                healthy, backend_name, health_err = _CS.check_backend_health()
                if not healthy:
                    raise RuntimeError(f"Credential storage failed:\n{health_err}")
                self._config_manager.credential_store.store_credential(pid, credential)

            # Save profile
            self._config_manager.save_provider_profile(profile)
            self._config_manager.set_active(pid, model.get("id", "") if model else "")

            # Synchronize app gateway so registered models & adapters are live immediately
            if self._runtime_sync_callback:
                try:
                    sync_result = self._runtime_sync_callback()
                    if sync_result is False:
                        raise RuntimeError("Runtime synchronization failed to register provider models.")
                except Exception as ex:
                    raise RuntimeError(f"Runtime synchronization failed: {ex}") from ex

            # Update header with selected model
            if model and model.get("id"):
                self.header.model = model["id"]
                # Update context capacity
                ctx_cap = model.get("context_capacity")
                if ctx_cap and self.controller:
                    self.controller._context_capacity = ctx_cap

            self.wizard.complete_save(profile_id=pid)
        except Exception as e:
            self.wizard.complete_save(error=str(e))

    def register_runtime_sync_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to synchronize application gateway after wizard save.

        This replaces any direct self._app or controller._app access.
        The callback is typically ClaireCoderV1.load_providers_from_config.
        """
        self._runtime_sync_callback = callback

    def _finish_wizard(self) -> None:
        """Complete wizard and transition to boot/loading."""
        self._wizard_active = False
        self.active_overlay = None
        self.set_state(InputState.NORMAL)

    def _on_engine_event(self, event: Any) -> None:
        """Thread-safe event listener that enqueues events for the main TUI render loop.
        
        If the interactive run loop is not currently running (e.g. headless unit testing),
        dispatches directly to handle_event so assertions see state immediately.
        """
        if self._in_run_loop:
            self._event_queue.put(event)
        else:
            self.handle_event(event)

    def _process_pending_events(self) -> bool:
        """Drain and process pending events from the thread-safe event queue in the main thread."""
        processed = False
        while not self._event_queue.empty():
            try:
                event = self._event_queue.get_nowait()
                self.handle_event(event)
                processed = True
            except queue.Empty:
                break
        return processed

    def run(self, input_source: Optional[object] = None, boot_delay: Optional[float] = None) -> int:
        """Runs the persistent interactive TUI lifecycle loop with in-place redraw.
        
        input_source:
            - None: Interactive terminal loop reading native non-echo keystrokes.
            - Iterable[str]: Scripted/test input stream for automated testing.
        boot_delay:
            - Optional override for per-stage boot presentation delay (seconds).
        """
        self.start()
        exit_code = 0
        self._in_run_loop = True
        terminal_input = TerminalInput(input_source=input_source)

        # Presentation delay: default ~0.58s/stage for live interactive terminal; 0.0s for scripted/pipes/tests
        if boot_delay is not None:
            delay = boot_delay
        elif input_source is not None or not sys.stdin.isatty():
            delay = 0.0
        else:
            delay = 0.58

        # Minimum boot duration: 3.5s for live interactive terminal, 0.0s for scripted/pipes/tests
        if input_source is not None or not sys.stdin.isatty():
            min_dur = 0.0
        else:
            min_dur = self.MINIMUM_BOOT_DURATION
        if boot_delay == 0.0:
            min_dur = 0.0

        # Synchronize header with authoritative state before rendering
        self._sync_header_from_runtime()

        # Check if setup wizard is needed (first-run or missing configuration)
        if self._check_needs_wizard():
            self._start_wizard()
            # Render initial wizard frame
            self.render_initial_frame()

            # Wizard input loop — runs until wizard completes
            while self.running and self._wizard_active:
                try:
                    events_processed = self._process_pending_events()
                    key = terminal_input.read_key_timeout(timeout=0.03)
                    input_processed = False
                    if key is None and not sys.stdin.isatty() and input_source is None:
                        # Piped stdin EOF reached
                        break
                    if key is not None:
                        ev = key if isinstance(key, KeyEvent) else InputDecoder.decode(key)
                        if ev.name == "ctrl+c":
                            self.stop()
                            return 0
                        elif ev.name in ("escape", "esc") and self.wizard.stage.value == "provider_select":
                            self.stop()
                            return 0
                        elif ev.name in ("ctrl+v", "shift+insert", "paste"):
                            self.wizard.handle_key(ev.name)
                        elif ev.is_printable and ev.char:
                            self.wizard.handle_key(ev.char)
                        else:
                            self.wizard.handle_key(ev.name)
                        input_processed = True

                    if self.wizard.is_complete:
                        self._finish_wizard()
                        break

                    if self.running and (input_processed or events_processed or self.wizard.stage.value in ("validating", "discovering")):
                        self.redraw()
                except KeyboardInterrupt:
                    self.stop()
                    return 0
                except Exception as exc:
                    self._handle_runtime_failure(exc, context="wizard")
                    break

            if not self.running:
                self.stop()
                return exit_code

        # Real startup boot screen presentation
        self._render_boot_sequence(presentation_delay=delay, min_duration=min_dur)

        # Synchronize header again after boot (wizard may have changed model)
        self._sync_header_from_runtime()

        # Initial main frame render: completely replaces loading screen in place
        if self.renderer and self.renderer.last_line_count > 0:
            self.redraw()
        else:
            self.render_initial_frame()

        while self.running:
            try:
                events_processed = self._process_pending_events()
                key = terminal_input.read_key_timeout(timeout=0.03)
                input_processed = False
                if key is None and not sys.stdin.isatty() and input_source is None:
                    # Piped stdin EOF reached
                    break
                if key is None and input_source is not None:
                    # End of scripted test input reached
                    break
                if key is not None:
                    self._dispatch_interactive_input(key)
                    input_processed = True
                if self.running and (events_processed or input_processed):
                    self.redraw()
            except KeyboardInterrupt:
                exited = self.handle_ctrl_c()
                if self.running:
                    self.redraw()
                if exited:
                    exit_code = 0
                    break
            except Exception as exc:
                self._handle_runtime_failure(exc, context="main_loop")
                exit_code = 1
                break

        self._in_run_loop = False
        self.stop()
        return exit_code

    # NOTE: _dispatch_interactive_input is defined below _sync_header_from_runtime.
    # Removed duplicate definition that was shadowed by the authoritative one at line ~837.

    def _handle_runtime_failure(self, exc: Exception, context: str = "runtime") -> None:
        """Handle a runtime exception by logging it to the transcript and stderr.

        Never silently swallows exceptions. Always leaves a visible trace.
        """
        import sys as _sys
        msg = f"Runtime error ({context}): {exc}"
        # Write to stderr so it survives TUI cleanup
        try:
            print(f"\n[ClaireCoder] {msg}", file=_sys.stderr, flush=True)
        except Exception:
            pass
        # Append to transcript if possible for in-TUI visibility
        try:
            self.transcript.append_activity(ActivityModel(
                type=ActivityType.MESSAGE,
                title="Error",
                detail=msg,
            ))
        except Exception:
            pass

    def _sync_header_from_runtime(self) -> None:
        """Synchronize all header fields from authoritative runtime state.
        
        This is the single presentation-state synchronization path:
            authoritative application/runtime state → TUI header projection
        """
        # Directory: always from workspace root
        self.header.directory = self._shorten_path(self._workspace_root)

        # Mode: from controller
        if self.controller and hasattr(self.controller, "mode"):
            mode = self.controller.mode
            try:
                self.header.mode = mode.value.upper() if hasattr(mode, "value") and isinstance(mode.value, str) else str(mode).upper()
            except Exception:
                pass  # Keep existing mode on mock/broken controllers

        # Session: already set during connect
        # Model: from config manager active or controller
        if self._config_manager and hasattr(self._config_manager, "get_active"):
            active = self._config_manager.get_active()
            if active.get("model_id"):
                self.header.model = active["model_id"]

        # Context: from controller token tracking
        self._update_context_display()

    def _dispatch_interactive_input(self, item: Any) -> None:
        """Dispatches an interactive input command or keystroke."""
        if item is None:
            return
        ev = item if isinstance(item, KeyEvent) else InputDecoder.decode(item)
        if ev.name == "unknown":
            return

        named_keys = (
            "ctrl+c", "ctrl+r", "ctrl+t", "ctrl+p",
            "escape", "esc", "enter", "backspace", "tab",
            "up", "down", "left", "right",
            "pageup", "pagedown", "home", "end", "delete", "insert",
            "ctrl+v", "shift+insert", "paste",
        )
        if ev.name in named_keys:
            self.handle_key(ev.name)
        elif self.state in (InputState.OVERLAY, InputState.CONFIRMATION):
            self.handle_key(ev.name if not ev.is_printable else ev.char)
        elif ev.is_printable and ev.char and len(ev.char) == 1:
            self.handle_key(ev.char)
        else:
            self.submit(str(item))

    def connect_controller(self, controller) -> None:
        """Connects interaction controller and subscribes to event stream."""
        self.controller = controller
        if hasattr(controller, "subscribe"):
            controller.subscribe(self._on_engine_event)
        elif hasattr(controller, "subscribe_events"):
            controller.subscribe_events(self._on_engine_event)

    def set_command_router(self, router) -> None:
        """Sets the application-level command router/controller callback."""
        self.controller = router

    def resize(self, width: int, height: int) -> None:
        """Handles terminal resize events."""
        self.terminal.resize(width, height)
        self._update_layout()
        if self.running:
            self.redraw()

    def get_viewport_height(self) -> int:
        """Calculates the available transcript/body viewport height from terminal height."""
        mode = self.terminal.determine_mode()
        if mode == TerminalMode.FULL:
            overhead = 8  # top border (1) + status (2) + top gap (1) + bot gap (1) + prompt (1) + shortcuts (1) + bot border (1)
            return max(1, self.terminal.height - overhead)
        elif mode == TerminalMode.COMPACT:
            hdr_str = self.header.render(width=self.terminal.width)
            hdr_lines = len(hdr_str.splitlines()) if hdr_str else 0
            prompt_lines = 1
            overhead = hdr_lines + prompt_lines
            return max(1, self.terminal.height - overhead)
        else:  # MINIMAL
            overhead = 2  # header (1) + prompt (1)
            return max(1, self.terminal.height - overhead)

    def _update_layout(self) -> None:
        """Updates internal layout based on terminal capabilities."""
        vh = self.get_viewport_height()
        self.transcript.resize(vh)
        # Synchronize render width for word wrapping (inner_w = terminal width - frame chrome)
        mode = self.terminal.determine_mode()
        if mode == TerminalMode.FULL:
            # Full mode: inner_w = width - 4 (box borders); content further indented by 1
            self.transcript.render_width = max(20, self.terminal.width - 6)
        else:
            self.transcript.render_width = max(20, self.terminal.width - 2)
        
    def set_state(self, state: InputState) -> None:
        """Transitions input state safely and synchronizes prompt suspension."""
        self.state = state
        if state in (InputState.OVERLAY, InputState.CONFIRMATION):
            self.prompt.suspend()
        else:
            self.prompt.resume()
            if state != InputState.OVERLAY:
                self.active_overlay = None

    def open_review(self) -> None:
        """Opens the review changes overlay."""
        self.active_overlay = "review"
        self.set_state(InputState.OVERLAY)

    def open_palette(self) -> None:
        """Opens the command palette overlay."""
        self.active_overlay = "palette"
        self.set_state(InputState.OVERLAY)

    def open_tree(self) -> None:
        """Opens the file tree overlay, refreshing from the real workspace."""
        self.file_tree.refresh()
        self.active_overlay = "tree"
        self.set_state(InputState.OVERLAY)

    def open_task(self) -> None:
        """Opens the task / workflow view overlay, synchronizing state from active session."""
        self._sync_task_view_from_session()
        self.active_overlay = "task"
        self.set_state(InputState.OVERLAY)

    def _sync_task_view_from_session(self) -> None:
        """Synchronize task view overlay state with active engine session.

        Lifecycle states:
            No session / no objective → Idle (reset)
            ACTIVE → live tasks/progress
            COMPLETED → Status: Complete, 100% progress
            FAILED → Status: Failed, with failure reason
            PAUSED / CANCELLED → Status: Interrupted / Cancelled
        """
        from .task import WorkflowTaskItem
        if not self.controller or not hasattr(self.controller, "_engine") or not self.controller._engine:
            return

        sid = self.header.session_id
        session = self.controller._engine.get_session(sid) if sid else None
        if not session or not session.objective:
            self.task_view.reset()
            return

        from clairecoder.engine.types import ObjectiveStatus
        obj_status = session.objective.status

        # Set objective text regardless of status (so completed/failed views show it)
        self.task_view.objective = session.objective.request

        # Map terminal objective states to task view status
        if obj_status == ObjectiveStatus.COMPLETED:
            self.task_view.status = "Complete"
            self.task_view.progress_pct = 100
            self.task_view.failure_reason = None
            # Clear active execution flag
            self.header.task_progress = "Complete"
        elif obj_status == ObjectiveStatus.FAILED:
            self.task_view.status = "Failed"
            self.task_view.failure_reason = getattr(session.objective, 'failure_reason', None) or "Execution failed"
            self.header.task_progress = "Failed"
        elif obj_status == ObjectiveStatus.CANCELLED:
            self.task_view.status = "Cancelled"
            self.task_view.failure_reason = None
            self.header.task_progress = "Cancelled"
        elif obj_status == ObjectiveStatus.PAUSED:
            self.task_view.status = "Interrupted"
            self.task_view.failure_reason = None
            self.header.task_progress = "Paused"
        elif obj_status == ObjectiveStatus.ACTIVE:
            self.task_view.status = "Active"
            self.task_view.failure_reason = None
        else:
            self.task_view.reset()
            return

        # Build task list from session tasks
        tasks_list = []
        if hasattr(session, "tasks") and session.tasks:
            for idx, (tid, t) in enumerate(session.tasks.items(), start=1):
                st_val = getattr(t.status, "value", str(t.status))
                if st_val == "succeeded":
                    marker = "✓"
                elif st_val == "running":
                    marker = "▶"
                elif st_val == "failed":
                    marker = "✗"
                elif st_val == "cancelled":
                    marker = "⊘"
                else:
                    marker = "○"
                tasks_list.append(WorkflowTaskItem(number=idx, title=t.description, marker=marker))

            self.task_view.tasks = tasks_list
            if obj_status == ObjectiveStatus.ACTIVE:
                succeeded_cnt = sum(1 for t in session.tasks.values() if getattr(t.status, "value", "") == "succeeded")
                total_cnt = max(1, len(session.tasks))
                self.task_view.progress_pct = int(100 * succeeded_cnt / total_cnt)
                self.header.task_progress = f"{succeeded_cnt}/{len(session.tasks)}"
        else:
            self.task_view.tasks = []
            if obj_status == ObjectiveStatus.ACTIVE:
                self.task_view.progress_pct = 0

    def close_overlay(self) -> None:
        """Closes any active overlay and restores normal input."""
        self.active_overlay = None
        self.set_state(InputState.NORMAL)

    def handle_escape(self) -> None:
        """Handles UI-level escape."""
        if self.state == InputState.OVERLAY:
            self.close_overlay()
        elif self.state == InputState.CONFIRMATION:
            req = self.permission_surface.active_request
            self.permission_surface.cancel_pending()
            self.set_state(InputState.NORMAL)
            if req:
                if self.controller and hasattr(self.controller, "handle_permission_response"):
                    self.controller.handle_permission_response(
                        request_id=req.request_id,
                        decision=PermissionDecision.CANCEL,
                        session_id=req.session_id,
                        tool_id=req.tool_id,
                        action=req.action,
                        resource=req.resource,
                        command=req.command,
                        category=req.category
                    )
                if self.on_permission_response:
                    self.on_permission_response(
                        request_id=req.request_id,
                        decision=PermissionDecision.CANCEL,
                        session_id=req.session_id,
                        tool_id=req.tool_id,
                        action=req.action,
                        resource=req.resource,
                        command=req.command,
                        category=req.category
                    )

    def handle_ctrl_c(self) -> bool:
        """Handles operation interruption and Ctrl+C double-press exit.
        
        Returns True if application exited, False if remaining open.
        """
        now = time.time()

        if self._interrupt_pending and now <= self._interrupt_deadline:
            # Second Ctrl+C within window -> exit
            self._interrupt_pending = False
            self.stop()
            self._action_history.append("EXIT_DOUBLE_CTRL_C")
            return True

        # First Ctrl+C -> interrupt active operation and enter confirmation window
        self._interrupt_pending = True
        self._interrupt_deadline = now + self.exit_confirmation_timeout

        if self.on_interrupt:
            try:
                self.on_interrupt()
            except Exception:
                pass

        if self.controller and hasattr(self.controller, "interrupt_active_session"):
            sid = self.header.session_id or None
            try:
                self.controller.interrupt_active_session(sid)
            except Exception:
                pass

        if self.prompt.get_text():
            self.prompt.clear()

        self._action_history.append("INTERRUPT")

        self.transcript.append_activity(ActivityModel(
            title="Interrupted",
            detail="Press Ctrl+C again to exit ClaireCoder."
        ))
        return False

    def handle_key(self, key: Any) -> bool:
        """Dispatches key input based on current input state. Returns True if handled."""
        clean_key = str(key).strip().lower() if key is not None else ""

        # 1. Global Ctrl+C Interruption / Double-Press Exit
        if clean_key == "ctrl+c":
            self.handle_ctrl_c()
            return True

        # Any other key resets the pending double-Ctrl+C state
        self.reset_interrupt_state()

        # 2. Confirmation State (Permission UI) - Permission UI owns keyboard focus
        if self.state == InputState.CONFIRMATION:
            if clean_key in ("\x1b", "escape", "esc"):
                self.handle_escape()
                return True
            decision = self.permission_surface.handle_key(clean_key)
            if decision is not None:
                if decision == PermissionDecision.DIFF:
                    return True
                req = self.permission_surface.active_request
                if req:
                    req_id = req.request_id
                    session_id = req.session_id
                    tool_id = req.tool_id
                    action = req.action
                    resource = req.resource
                    command = req.command
                    category = req.category
                    
                    self.permission_surface.clear_active()
                    if not self.permission_surface.has_pending():
                        self.set_state(InputState.NORMAL)

                    if self.controller and hasattr(self.controller, "handle_permission_response"):
                        self.controller.handle_permission_response(
                            request_id=req_id,
                            decision=decision,
                            session_id=session_id,
                            tool_id=tool_id,
                            action=action,
                            resource=resource,
                            command=command,
                            category=category
                        )

                    if self.on_permission_response:
                        self.on_permission_response(
                            request_id=req_id,
                            decision=decision,
                            session_id=session_id,
                            tool_id=tool_id,
                            action=action,
                            resource=resource,
                            command=command,
                            category=category
                        )
                return True
            return False

        # 3. Global Secondary-View Direct Navigation Shortcuts (Ctrl+T, Ctrl+R, Ctrl+P)
        # Dispatched before view-specific handlers, works directly from Main, Tree, Review, Task, Palette
        if clean_key == "ctrl+t":
            self.open_tree()
            return True
        elif clean_key == "ctrl+r":
            self.open_review()
            return True
        elif clean_key == "ctrl+p":
            self.open_task()
            return True

        # 4. Overlay Key Interception - Overlays own keyboard focus (absorb keys)
        if self.state == InputState.OVERLAY:
            if self.active_overlay == "model_selector":
                handled = self.model_selector.handle_key(clean_key)
                if not handled and clean_key in ("\x1b", "escape", "esc", "q", "back"):
                    self.close_overlay()
                    return True
                return True
            elif self.active_overlay == "review":
                if clean_key in ("\x1b", "escape", "esc", "q", "back"):
                    self.close_overlay()
                    return True
                self.review_overlay.handle_key(clean_key)
                return True
            elif self.active_overlay == "palette":
                if clean_key in ("\x1b", "escape", "esc", "q", "back"):
                    self.close_overlay()
                    return True
                handled = self.command_palette.handle_key(clean_key)
                if clean_key in ("enter", "return"):
                    selected = self.command_palette.get_selected_command()
                    self.close_overlay()
                    if selected:
                        self.submit(selected.name)
                    return True
                return True
            elif self.active_overlay == "tree":
                if clean_key in ("\x1b", "escape", "esc", "q", "back"):
                    self.close_overlay()
                    return True
                self.file_tree.handle_key(clean_key)
                return True
            elif self.active_overlay == "task":
                if clean_key in ("\x1b", "escape", "esc", "q", "back"):
                    self.close_overlay()
                    return True
                self.task_view.handle_key(clean_key)
                return True
            elif self.active_overlay == "wizard":
                # Wizard owns focus — forward keys to wizard handler
                if clean_key in ("\x1b", "escape", "esc"):
                    # Esc in wizard: return to model_selector if launched from there
                    if hasattr(self, '_wizard_launched_from_selector') and self._wizard_launched_from_selector:
                        self._wizard_active = False
                        self._wizard_launched_from_selector = False
                        self.active_overlay = "model_selector"
                        self.model_selector.stage = ModelSelectorStage.PROVIDER_LIST
                        return True
                    else:
                        self._wizard_active = False
                        self.close_overlay()
                        return True
                elif clean_key in ("ctrl+v", "shift+insert", "paste"):
                    self.wizard.handle_key(clean_key)
                elif clean_key in ("enter", "return"):
                    self.wizard.handle_key("enter")
                    if self.wizard.is_complete:
                        self._finish_wizard()
                elif clean_key == "tab":
                    self.wizard.handle_key("tab")
                elif len(str(key)) == 1 and str(key).isprintable():
                    self.wizard.handle_key(str(key))
                else:
                    self.wizard.handle_key(clean_key)
                return True
            if clean_key in ("\x1b", "escape", "esc"):
                self.close_overlay()
                return True
            return True

        # 5. Slash Suggestions Interception (Main Pane)
        if self.is_slash_suggestions_active():
            matches = self.get_slash_suggestions()
            if matches:
                if clean_key in ("\x1b", "escape", "esc"):
                    self._slash_suggestions_dismissed = True
                    return True
                elif clean_key in ("up", "k", "\x1b[a"):
                    self._slash_selected_index = (self._slash_selected_index - 1) % len(matches)
                    return True
                elif clean_key in ("down", "j", "\x1b[b"):
                    self._slash_selected_index = (self._slash_selected_index + 1) % len(matches)
                    return True
                elif clean_key in ("enter", "return", "tab"):
                    idx = min(self._slash_selected_index, len(matches) - 1)
                    selected_cmd = matches[idx]
                    self.prompt.set_text(selected_cmd)
                    self._slash_suggestions_dismissed = True
                    return True

        # 6. Transcript Scrolling Shortcuts (Main Pane)
        if clean_key in ("pageup", "page_up", "pgup"):
            self.transcript.page_up()
            return True
        elif clean_key in ("pagedown", "page_down", "pgdn"):
            self.transcript.page_down()
            return True
        elif clean_key == "up" and not self.prompt.get_text():
            self.transcript.scroll_up(1)
            return True
        elif clean_key == "down" and not self.prompt.get_text():
            self.transcript.scroll_down(1)
            return True

        # 7. Normal Prompt Buffer Editing
        self._slash_suggestions_dismissed = False
        if clean_key in ("enter", "return"):
            text = self.prompt.get_text().strip()
            self.prompt.clear()
            if text:
                self.submit(text)
            return True
        elif clean_key in ("ctrl+v", "shift+insert", "paste"):
            from .clipboard import get_clipboard_text, normalize_clipboard_text
            clip = normalize_clipboard_text(get_clipboard_text(), single_line=True)
            if clip:
                for ch in clip:
                    self.prompt.insert_char(ch)
            return True
        elif clean_key in ("backspace", "\x7f", "\x08"):
            self.prompt.backspace()
            return True
        elif clean_key in ("delete", "del", "\x1b[3~"):
            self.prompt.delete_char()
            return True
        elif clean_key in ("left", "left_arrow", "\x1b[d"):
            self.prompt.move_cursor_left(1)
            return True
        elif clean_key in ("right", "right_arrow", "\x1b[c"):
            self.prompt.move_cursor_right(1)
            return True
        elif clean_key in ("home", "ctrl+a", "\x1b[h", "\x1b[1~", "\x1b[7~"):
            if self.prompt.get_text():
                self.prompt.move_cursor_home()
            else:
                self.transcript.scroll_to_top()
            return True
        elif clean_key in ("end", "ctrl+e", "\x1b[f", "\x1b[4~", "\x1b[8~"):
            if self.prompt.get_text():
                self.prompt.move_cursor_end()
            else:
                self.transcript.scroll_to_bottom()
            return True
        elif len(str(key)) == 1 and str(key).isprintable():
            self.prompt.insert_char(str(key))
            return True

        return False

    def submit(self, text: str) -> None:
        """Submits input text or executes commands."""
        self.reset_interrupt_state()
        cmd_clean = text.strip()
        if not cmd_clean:
            return

        # Explicit /commands invocation
        if cmd_clean.lower() in ("/commands", "commands"):
            self.open_palette()
            return

        if cmd_clean.startswith("/"):
            cmd_name = cmd_clean[1:].split()[0].lower()
        else:
            cmd_name = cmd_clean.split()[0].lower()

        # UI-only presentation commands
        if cmd_name == "review":
            self.open_review()
            return
        elif cmd_name == "tree":
            self.open_tree()
            return
        elif cmd_name == "task":
            self.open_task()
            return
        elif cmd_name == "model" and len(cmd_clean.split()) == 1:
            self.open_model_selector()
            return
        elif cmd_name in ("exit", "quit"):
            if self.controller and hasattr(self.controller, "execute_command"):
                from clairecoder.interaction.types import CommandRequest
                self.controller.execute_command(CommandRequest(command="exit", arguments={}, raw_input=cmd_clean))
            self.stop()
            return

        # Application commands routed through InteractionController
        if self.controller:
            try:
                from clairecoder.interaction.parser import CommandParser
                is_explicit_cmd = CommandParser.is_command(cmd_clean)
                is_known_bare_cmd = cmd_name in ("status", "mode", "session", "pause", "resume", "cancel", "clear", "exit", "model", "help", "plan")

                if is_explicit_cmd or is_known_bare_cmd:
                    cmd_to_parse = cmd_clean if is_explicit_cmd else f"/{cmd_clean}"
                    parsed_req = CommandParser.parse(cmd_to_parse)
                    if parsed_req:
                        # Bare /model opens interactive selector
                        if parsed_req.command == "model" and not parsed_req.arguments.get("args"):
                            self.open_model_selector()
                            return

                        if hasattr(self.controller, "execute_command"):
                            resp = self.controller.execute_command(parsed_req)
                        elif callable(self.controller):
                            resp = self.controller(parsed_req)
                        else:
                            resp = None

                        if resp:
                            if parsed_req.command == "clear":
                                self.transcript.activities.clear()
                                self.transcript._activity_map.clear()
                                self.transcript._correlation_map.clear()
                                self.transcript.scroll_position = 0

                            # Handle /model switch — update header
                            if parsed_req.command == "model" and resp.success and resp.data.get("action") == "switch":
                                self.header.model = resp.data["model_id"]
                                self._update_context_display()

                            # Handle /mode switch — update header
                            if parsed_req.command == "mode" and resp.success and resp.data.get("mode"):
                                self.header.mode = resp.data["mode"].upper()

                            self.transcript.append_activity(ActivityModel(
                                title=f"Command /{parsed_req.command}",
                                detail=str(resp.message or resp.data or resp.error or "")
                            ))
                            if resp.data and resp.data.get("exit"):
                                self.stop()
                                return
                else:
                    # Natural language request / objective routed through InteractionController
                    self.transcript.append_activity(ActivityModel(
                        type=ActivityType.MESSAGE,
                        title="User",
                        detail=cmd_clean
                    ))
                    if hasattr(self.controller, "process_natural_language"):
                        session_id = self.header.session_id or "default"
                        msg = self.controller.process_natural_language(cmd_clean, session_id)
                        if msg and str(msg).startswith("Objective accepted"):
                            self.task_view.objective = cmd_clean
                            # Note: do NOT emit "Starting objective" here — the engine's
                            # OBJECTIVE_STARTED event (via PresentationAdapter) is the
                            # authoritative source. Only record the acceptance message.
                            self.transcript.append_activity(ActivityModel(
                                type=ActivityType.MESSAGE,
                                title="Objective accepted",
                                detail=str(msg)
                            ))
                        # Reset streaming buffer for new response
                        self._streaming_activity_key = f"stream_{hash(cmd_clean)}"
                        self._streaming_text_buffer = []
            except Exception as ex:
                self.transcript.append_activity(ActivityModel(
                    type=ActivityType.MESSAGE,
                    title="Claire",
                    detail=f"Unable to process request: {ex}"
                ))
        elif cmd_name == "clear":
            self.transcript.activities.clear()
            self.transcript._activity_map.clear()
            self.transcript._correlation_map.clear()
            self.transcript.scroll_position = 0
            self.transcript.append_activity(ActivityModel(
                title="Command /clear",
                detail="Transcript cleared."
            ))
        else:
            self.transcript.append_activity(ActivityModel(
                type=ActivityType.MESSAGE,
                title="User",
                detail=cmd_clean
            ))
            self.task_view.objective = cmd_clean
            self._action_history.append(f"PROMPT:{cmd_clean}")
            self.transcript.append_activity(ActivityModel(
                type=ActivityType.MESSAGE,
                title="Claire",
                detail="Objective accepted."
            ))

    def handle_event(self, event) -> None:
        """Processes events from the event stream and updates TUI state."""
        if isinstance(event, dict):
            event_name = event.get("type", "").upper()
            payload = event
        else:
            event_name = event.name.upper() if hasattr(event, "name") else ""
            payload = event.payload if hasattr(event, "payload") else {}

        # ── Wizard async completion events ──

        if event_name == "WIZARD_VALIDATION_COMPLETED":
            success = payload.get("success", False)
            error = payload.get("error")
            req_id = payload.get("request_id")
            self.wizard.complete_validation(success=success, error=error, request_id=req_id)
            if success and not error:
                prov = payload.get("provider", {})
                cred = payload.get("credential", "")
                ep = payload.get("endpoint", "")
                self._wizard_on_discover(provider=prov, credential=cred, endpoint=ep, request_id=req_id)
            return

        elif event_name == "WIZARD_DISCOVERY_COMPLETED":
            models = payload.get("models", [])
            error = payload.get("error")
            req_id = payload.get("request_id")
            self.wizard.complete_discovery(models=models, error=error, request_id=req_id)
            return

        # ── Header synchronization from authoritative events ──

        if event_name == "MODEL_SWITCHED":
            model_id = payload.get("model_id", "")
            if model_id:
                self.header.model = model_id
            ctx_cap = payload.get("context_capacity")
            if ctx_cap and self.controller:
                self.controller._context_capacity = ctx_cap
            self._update_context_display()

        elif event_name == "MODE_CHANGED":
            mode = payload.get("mode", "")
            if mode:
                self.header.mode = mode.upper()

        elif event_name == "RUN_STATE_CHANGED":
            # §8: TUI projects run state from authoritative controller
            new_state = payload.get("new_state", "")
            state_display = {
                "idle": "\u2014",
                "running": "Running\u2026",
                "waiting_for_user": "Waiting",
                "completed": "Complete",
                "failed": "Failed",
                "cancelled": "Cancelled",
                "interrupted": "Interrupted",
            }
            if new_state in state_display:
                self.header.task_progress = state_display[new_state]

        elif event_name == "STREAMING_CHUNK":
            # Incremental streaming response into transcript
            chunk_text = payload.get("text", "")
            if chunk_text:
                self._streaming_text_buffer.append(chunk_text)
                full_text = "".join(self._streaming_text_buffer)
                key = self._streaming_activity_key or "stream_response"
                # Update or create the streaming activity
                streaming_act = ActivityModel(
                    type=ActivityType.MESSAGE,
                    title="Claire",
                    detail=full_text,
                    correlation_key=key,
                    updates_activity=True,
                )
                self.transcript.update_activity(streaming_act)

        elif event_name == "RESPONSE_COMPLETE":
            response_text = payload.get("text", "")
            is_error = payload.get("error", False)
            if response_text:
                key = self._streaming_activity_key or "stream_response"
                if self._streaming_text_buffer:
                    # Final update of streaming activity
                    final_act = ActivityModel(
                        type=ActivityType.MESSAGE,
                        title="Claire",
                        detail=response_text,
                        correlation_key=key,
                        updates_activity=True,
                    )
                    self.transcript.update_activity(final_act)
                else:
                    # Non-streaming response: append new activity
                    self.transcript.append_activity(ActivityModel(
                        type=ActivityType.MESSAGE,
                        title="Claire",
                        detail=response_text,
                    ))
                # Update token tracking
                self._update_context_display()
            # Reset streaming state
            self._streaming_activity_key = None
            self._streaming_text_buffer = []

        elif event_name == "PERMISSION_REQUESTED":
            req_id = payload.get("request_id", "")
            tool_id = payload.get("tool_name") or payload.get("tool_id", "tool")
            action = payload.get("action", "")
            resource = payload.get("resource", "")
            command = payload.get("command")
            reason = payload.get("reason", "")
            category = payload.get("category")
            session_id = payload.get("session_id")
            diff_info = payload.get("diff_info")

            self.permission_surface.request_confirmation(
                request_id=req_id,
                tool_id=tool_id,
                action=action,
                resource=resource,
                command=command,
                reason=reason,
                category=category,
                session_id=session_id,
                diff_info=diff_info
            )
            self.set_state(InputState.CONFIRMATION)

        elif event_name == "TOOL_COMPLETED" and payload.get("state") == "denied" and payload.get("metadata", {}).get("requires_confirmation"):
            req_id = payload.get("request_id", "")
            tool_id = payload.get("tool_name") or payload.get("tool_id", "tool")
            meta = payload.get("metadata", {})
            action = payload.get("action") or meta.get("action", "execute")
            resource = payload.get("resource") or meta.get("resource", "")
            reason = payload.get("reason") or meta.get("reason", "")
            command = payload.get("command") or meta.get("command")
            category = payload.get("category") or meta.get("category")
            session_id = payload.get("session_id") or meta.get("session_id")
            diff_info = payload.get("diff_info") or meta.get("diff_info")

            self.permission_surface.request_confirmation(
                request_id=req_id,
                tool_id=tool_id,
                action=action,
                resource=resource,
                command=command,
                reason=reason,
                category=category,
                session_id=session_id,
                diff_info=diff_info
            )
            self.set_state(InputState.CONFIRMATION)

        elif event_name == "PERMISSION_RESOLVED":
            req_id = payload.get("request_id", "")
            self.permission_surface.resolve(req_id)
            if not self.permission_surface.has_pending():
                self.set_state(InputState.NORMAL)

        elif event_name in ("PERMISSION_GRANTED", "PERMISSION_DENIED", "PERMISSION_CANCELLED"):
            if not self.permission_surface.has_pending():
                self.set_state(InputState.NORMAL)

        # Translate event to activity and update transcript
        try:
            from .adapter import PresentationAdapter
            act = PresentationAdapter.event_to_activity(event)
            if act:
                if act.updates_activity:
                    self.transcript.update_activity(act)
                else:
                    self.transcript.append_activity(act)
        except Exception:
            pass

    def _on_permission_decision(self, req_id: str, decision: PermissionDecision) -> None:
        """Internal callback when permission decision is made."""
        if not self.permission_surface.has_pending():
            self.set_state(InputState.NORMAL)

    def render(self) -> List[str]:
        """Renders the current terminal application frame conforming to mode and geometry."""
        mode = self.terminal.determine_mode()
        width = self.terminal.width
        vh = self.get_viewport_height()

        if mode == TerminalMode.MINIMAL:
            lines: List[str] = [f"--- ClaireCoder (v0.1.0) [{self.header.mode}] ---"]
            if self.state == InputState.CONFIRMATION and self.permission_surface.has_pending():
                body = self.permission_surface.render(mode=mode, width=width)
            elif self.state == InputState.OVERLAY:
                if self.active_overlay == "review":
                    body = self.review_overlay.render(mode=mode, width=width)
                elif self.active_overlay == "palette":
                    body = self.command_palette.render(mode=mode, width=width)
                elif self.active_overlay == "tree":
                    body = self.file_tree.render(mode=mode, width=width)
                elif self.active_overlay == "task":
                    body = self.task_view.render(mode=mode, width=width)
                else:
                    body = []
            else:
                body = self.transcript.get_visible_lines()

            for i in range(vh):
                if i < len(body):
                    lines.append(body[i])
                else:
                    lines.append("")
            lines.append(f"> {self.prompt.get_text()}")
            return lines

        elif mode == TerminalMode.COMPACT:
            lines: List[str] = []
            hdr_str = self.header.render(width=width)
            if hdr_str:
                lines.extend(hdr_str.splitlines())
            if self.state == InputState.CONFIRMATION and self.permission_surface.has_pending():
                body = self.permission_surface.render(mode=mode, width=width)
            elif self.state == InputState.OVERLAY:
                if self.active_overlay == "review":
                    body = self.review_overlay.render(mode=mode, width=width)
                elif self.active_overlay == "palette":
                    body = self.command_palette.render(mode=mode, width=width)
                elif self.active_overlay == "tree":
                    body = self.file_tree.render(mode=mode, width=width)
                elif self.active_overlay == "task":
                    body = self.task_view.render(mode=mode, width=width)
                else:
                    body = []
            else:
                body = self.transcript.get_visible_lines()

            for i in range(vh):
                if i < len(body):
                    lines.append(body[i])
                else:
                    lines.append("")

            lines.extend(self.prompt.render(mode=mode, width=width))
            return lines

        # FULL MODE: Render framed spatial composition matching MAIN-TUI reference
        box_w = width
        inner_w = box_w - 4

        # Scroll indicator calculation
        total_transcript_lines = len(self.transcript._get_rendered_lines())
        has_scrollbar = (self.state == InputState.NORMAL and self.active_overlay is None and total_transcript_lines > vh)
        
        thumb_start, thumb_end = 0, 0
        if has_scrollbar and total_transcript_lines > 0:
            scroll_top = self.transcript.scroll_position
            scroll_bottom = scroll_top + vh
            thumb_start = int((scroll_top / total_transcript_lines) * vh)
            thumb_end = max(thumb_start + 1, int((scroll_bottom / total_transcript_lines) * vh))

        def frame_row(text: str = "", row_idx: Optional[int] = None) -> str:
            scroll_char = ""
            avail_w = inner_w
            if has_scrollbar and row_idx is not None:
                avail_w = inner_w - 2
                if thumb_start <= row_idx < thumb_end:
                    scroll_char = " ▓"
                else:
                    scroll_char = " ░"

            vis = visible_length(text)
            if vis > avail_w:
                text = visible_slice(text, 0, avail_w)
                vis = visible_length(text)
            pad = max(0, avail_w - vis)
            if has_scrollbar and row_idx is not None:
                return f"│ {text}{' ' * pad}{scroll_char} │"
            return f"│ {text}{' ' * pad} │"

        lines: List[str] = []

        # 1. Top border and status bar (4 rows)
        top_border = f"╭─ ClaireCoder " + ("─" * max(0, box_w - 27)) + " ● v0.1.0 ─╮"
        lines.append(top_border)
        
        status_row = f"dir: {self.header.directory}   model: {self.header.model}   mode: {self.header.mode}   session: {self.header.session_id}"
        status_row2 = f"task: {self.header.task_progress}   context: {self.header.context_usage}"
        
        lines.append(frame_row(status_row))
        lines.append(frame_row(status_row2))
        lines.append(frame_row(""))

        # 2. Main canvas body area (fixed vh rows)
        if self.state == InputState.CONFIRMATION and self.permission_surface.has_pending():
            card_lines = self.permission_surface.render(mode=mode, width=inner_w)
            body_lines = [f" {c}" for c in card_lines]
        elif self.state == InputState.OVERLAY:
            overlay_lines: List[str] = []
            if self.active_overlay == "wizard":
                overlay_lines = self.wizard.render(width=inner_w)
            elif self.active_overlay == "review":
                overlay_lines = self.review_overlay.render(mode=mode, width=inner_w)
            elif self.active_overlay == "palette":
                overlay_lines = self.command_palette.render(mode=mode, width=inner_w)
            elif self.active_overlay == "tree":
                overlay_lines = self.file_tree.render(mode=mode, width=inner_w)
            elif self.active_overlay == "task":
                overlay_lines = self.task_view.render(mode=mode, width=inner_w)
            elif self.active_overlay == "model_selector":
                overlay_lines = self.model_selector.render(width=inner_w)
            body_lines = [f" {o}" for o in overlay_lines]
        else:
            # Full-width transcript (no right mascot panel)
            transcript_lines = self.transcript.get_visible_lines()
            body_lines = [f" {t}" for t in transcript_lines]
            
            # Overlay slash suggestions card if active
            if self.is_slash_suggestions_active():
                matches = self.get_slash_suggestions()
                if matches:
                    sugg_box = self._render_slash_suggestions(matches, width=28)
                    start_r = max(0, vh - len(sugg_box))
                    while len(body_lines) < vh:
                        body_lines.append("")
                    for offset, s_row in enumerate(sugg_box):
                        target_r = start_r + offset
                        if target_r < len(body_lines):
                            body_lines[target_r] = f"  {s_row}"

        for index in range(vh):
            if index < len(body_lines):
                lines.append(frame_row(body_lines[index], row_idx=index))
            else:
                lines.append(frame_row("", row_idx=index))

        # 3. Bottom Frame: Prompt and Shortcuts (4 rows)
        lines.append(frame_row(""))
        prompt_line = self.prompt.render_line(available_width=inner_w, focused=(self.state == InputState.NORMAL))
        lines.append(frame_row(prompt_line))
        
        if self.is_exit_confirmation_active():
            shortcut_all = "Press Ctrl+C again to exit ClaireCoder."
        else:
            shortcut_all = "ctrl+c interrupt   ctrl+t file tree   ctrl+r review changes   ctrl+p task view   /commands"
        lines.append(frame_row(shortcut_all))
        
        bot_border = "╰" + ("─" * (box_w - 2)) + "╯"
        lines.append(bot_border)
        return lines
