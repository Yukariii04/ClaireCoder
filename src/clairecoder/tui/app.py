"""Main TuiApplication runtime orchestrating all Stage 1 - 5 UI systems and event dispatch."""
import os
from typing import Dict, List, Optional, Callable
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

class TuiApplication:
    """Central TUI Application coordinating state, layout, key dispatch, and visual surfaces."""

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
        
        # Core Views
        self.header = HeaderStatus()
        self.transcript = TranscriptView()
        self.prompt = PromptInput()
        
        # Secondary Overlays & Surfaces
        self.permission_surface = PermissionSurface()
        self.review_overlay = ReviewOverlay()
        self.command_palette = CommandPalette()
        self._workspace_root = workspace_root or os.getcwd()
        self.file_tree = FileTreeOverlay(workspace_root=self._workspace_root)
        self.task_view = TaskViewOverlay()
        
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
        
        # Wire prompt escape and submit callbacks
        self.prompt.on_escape = self.handle_escape
        self.prompt.on_submit = self.submit
        
        # Wire permission surface callback
        self.permission_surface.register_decision_callback(self._on_permission_decision)
        
        self._update_layout()

    def is_exit_confirmation_active(self) -> bool:
        """Returns True if a first Ctrl+C was pressed within the confirmation window."""
        import time
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
        self.set_state(InputState.NORMAL)

    def stop(self) -> None:
        """Stops the TUI application lifecycle and clears terminal."""
        self.running = False
        self.set_state(InputState.EXITING)
        if self.renderer:
            self.renderer.clear()

    def render_initial_frame(self) -> None:
        """Performs initial render of the terminal frame."""
        self.current_frame = self.render()
        if self.renderer and self.renderer.last_line_count > 0:
            self.renderer.redraw(self.current_frame)
        else:
            self.renderer.render_frame(self.current_frame)

    def redraw(self) -> None:
        """Renders the current TUI state and updates the terminal in place."""
        self.current_frame = self.render()
        self.renderer.redraw(self.current_frame)

    def _render_boot_sequence(self, presentation_delay: float = 0.08) -> None:
        """Renders the startup boot sequence using real initialization stages."""
        if not self.renderer:
            return

        # Determine real gateway configuration status
        gw_status = "NOT CONFIGURED"
        if self.controller and hasattr(self.controller, "_engine") and self.controller._engine:
            gw = getattr(self.controller._engine, "_model_gateway", None)
            if gw and hasattr(gw, "_providers") and gw._providers:
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

        import time
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
                time.sleep(presentation_delay)

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
        terminal_input = TerminalInput(input_source=input_source)

        # Presentation delay: default 0.08s for live interactive terminal; 0.0s for scripted/tests
        if boot_delay is not None:
            delay = boot_delay
        elif input_source is not None:
            delay = 0.0
        else:
            delay = 0.08

        # Real startup boot screen presentation
        self._render_boot_sequence(presentation_delay=delay)

        # Initial main frame render: completely replaces loading screen in place
        if self.renderer and self.renderer.last_line_count > 0:
            self.redraw()
        else:
            self.render_initial_frame()

        while self.running:
            try:
                key = terminal_input.read_key()
                if key is None:
                    break
                self._dispatch_interactive_input(key)
                if self.running:
                    self.redraw()
            except KeyboardInterrupt:
                exited = self.handle_ctrl_c()
                if self.running:
                    self.redraw()
                if exited:
                    exit_code = 0
                    break
            except Exception:
                break

        self.stop()
        return exit_code

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
            "pageup", "pagedown", "home", "end", "delete", "insert"
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
            controller.subscribe(self.handle_event)
        elif hasattr(controller, "subscribe_events"):
            controller.subscribe_events(self.handle_event)

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
        """Opens the task / workflow view overlay."""
        self.active_overlay = "task"
        self.set_state(InputState.OVERLAY)

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
        import time
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

        from .activity import ActivityModel
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
            if clean_key in ("\x1b", "escape", "esc"):
                self.close_overlay()
                return True
            if self.active_overlay == "review":
                handled = self.review_overlay.handle_key(clean_key)
                if not handled and clean_key in ("q", "back"):
                    self.close_overlay()
                    return True
                return True
            elif self.active_overlay == "palette":
                handled = self.command_palette.handle_key(clean_key)
                if clean_key in ("enter", "return"):
                    selected = self.command_palette.get_selected_command()
                    self.close_overlay()
                    if selected:
                        self.submit(selected.name)
                    return True
                if not handled and clean_key in ("q", "back"):
                    self.close_overlay()
                    return True
                return True
            elif self.active_overlay == "tree":
                handled = self.file_tree.handle_key(clean_key)
                if not handled and clean_key in ("q", "back"):
                    self.close_overlay()
                    return True
                return True
            elif self.active_overlay == "task":
                handled = self.task_view.handle_key(clean_key)
                if not handled and clean_key in ("q", "back"):
                    self.close_overlay()
                    return True
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
        elif clean_key == "up":
            self.transcript.scroll_up(1)
            return True
        elif clean_key == "down":
            self.transcript.scroll_down(1)
            return True
        elif clean_key == "home":
            self.transcript.scroll_to_top()
            return True
        elif clean_key == "end":
            self.transcript.scroll_to_bottom()
            return True

        # 7. Normal Prompt Buffer Editing
        self._slash_suggestions_dismissed = False
        if clean_key in ("enter", "return"):
            text = self.prompt.get_text().strip()
            self.prompt.clear()
            if text:
                self.submit(text)
            return True
        elif clean_key in ("backspace", "\x7f", "\x08"):
            self.prompt.backspace()
            return True
        elif clean_key in ("left", "right"):
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
                            from .activity import ActivityModel
                            self.transcript.append_activity(ActivityModel(
                                title=f"Command /{parsed_req.command}",
                                detail=str(resp.message or resp.data or resp.error or "")
                            ))
                            if resp.data and resp.data.get("exit"):
                                self.stop()
                                return
                else:
                    # Natural language request / objective routed through InteractionController
                    from .activity import ActivityModel, ActivityType
                    self.transcript.append_activity(ActivityModel(
                        type=ActivityType.MESSAGE,
                        title="User",
                        detail=cmd_clean
                    ))
                    self.task_view.objective = cmd_clean
                    if hasattr(self.controller, "process_natural_language"):
                        session_id = self.header.session_id or "default"
                        msg = self.controller.process_natural_language(cmd_clean, session_id)
                        if msg:
                            self.transcript.append_activity(ActivityModel(
                                type=ActivityType.MESSAGE,
                                title="Claire",
                                detail=str(msg)
                            ))
            except Exception as ex:
                from .activity import ActivityModel, ActivityType
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
            from .activity import ActivityModel
            self.transcript.append_activity(ActivityModel(
                title="Command /clear",
                detail="Transcript cleared."
            ))
        else:
            from .activity import ActivityModel, ActivityType
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
        event_name = event.name.upper() if hasattr(event, "name") else ""
        payload = event.payload if hasattr(event, "payload") else {}

        if event_name == "PERMISSION_REQUESTED":
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
        box_w = max(104, width)
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
        
        dir_info = f"dir: {self.header.directory}"
        model_info = f"model: {self.header.model}"
        mode_info = f"mode: {self.header.mode}"
        session_info = f"session: {self.header.session_id}"
        task_info = f"task: {self.header.task_progress}"
        ctx_info = f"context: {self.header.context_usage}"
        status_row = f"{dir_info:<36} {model_info:<20} {mode_info:<18} {session_info}"
        status_row2 = f"{task_info:<36} {ctx_info}"
        
        lines.append(frame_row(status_row))
        lines.append(frame_row(status_row2))
        lines.append(frame_row(""))

        # 2. Main canvas body area (fixed vh rows)
        if self.state == InputState.CONFIRMATION and self.permission_surface.has_pending():
            card_lines = self.permission_surface.render(mode=mode, width=inner_w)
            body_lines = [f" {c}" for c in card_lines]
        elif self.state == InputState.OVERLAY:
            overlay_lines: List[str] = []
            if self.active_overlay == "review":
                overlay_lines = self.review_overlay.render(mode=mode, width=inner_w)
            elif self.active_overlay == "palette":
                overlay_lines = self.command_palette.render(mode=mode, width=inner_w)
            elif self.active_overlay == "tree":
                overlay_lines = self.file_tree.render(mode=mode, width=inner_w)
            elif self.active_overlay == "task":
                overlay_lines = self.task_view.render(mode=mode, width=inner_w)
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
        cursor = "█" if (self.state == InputState.NORMAL and not self.prompt.suspended) else ""
        prompt_text = f"> {self.prompt.get_text()}{cursor}"
        lines.append(frame_row(prompt_text))
        
        if self.is_exit_confirmation_active():
            shortcut_all = "Press Ctrl+C again to exit ClaireCoder."
        else:
            shortcut_all = "ctrl+c interrupt   ctrl+t file tree   ctrl+r review changes   ctrl+p task view   /commands"
        lines.append(frame_row(shortcut_all))
        
        bot_border = "╰" + ("─" * (box_w - 2)) + "╯"
        lines.append(bot_border)
        return lines
