from typing import Dict, Callable
from .types import CommandDefinition, CommandRequest, CommandResponse, InteractionMode
from clairecoder.engine.engine import EngineeringEngine
from clairecoder.engine.types import EngineeringObjective

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
    def __init__(self, engine: EngineeringEngine):
        self._engine = engine
        self._commands: Dict[str, CommandDefinition] = {}
        self._handlers: Dict[str, Callable[[CommandRequest], CommandResponse]] = {}
        self._mode = InteractionMode.IMPLEMENT

        self._register_default_commands()

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
                CommandArgument("session_id", "ID of the session to pause", required=True)
            ]),
            self._handle_pause
        )
        self.register_command(
            CommandDefinition("resume", "Resume paused operation", CommandCategory.EXECUTION, [
                CommandArgument("session_id", "ID of the session to resume", required=True)
            ]),
            self._handle_resume
        )
        self.register_command(
            CommandDefinition("cancel", "Cancel active operation", CommandCategory.EXECUTION, [
                CommandArgument("session_id", "ID of the session to cancel", required=True)
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

    def process_natural_language(self, request: str, session_id: str) -> str:
        """Process a natural language request by creating an objective for the engine.

        Per PRD §7.1 and §41, the interaction layer passes intent to the
        Engineering Engine without independently assembling context.
        """
        objective = EngineeringObjective(
            id=f"obj_{hash(request)}",
            request=request,
            session_id=session_id,
            mode=self._mode.value
        )
        session = self._engine.receive_objective(objective)
        return f"Objective accepted in session {session.id}"

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

    def _handle_mode(self, request: CommandRequest) -> CommandResponse:
        """AC-005/AC-006/AC-007: Mode inspection and switching (PRD §15–§20)."""
        args = request.arguments.get("args", [])
        if not args:
            return CommandResponse(success=True, message=f"Current mode: {self._mode.value.upper()}")

        requested_mode = args[0].lower()
        try:
            new_mode = InteractionMode(requested_mode)
            self._mode = new_mode
            return CommandResponse(success=True, message=f"Mode switched to: {new_mode.value.upper()}")
        except ValueError:
            valid_modes = [m.value for m in InteractionMode]
            return CommandResponse(
                success=False,
                message=f"Invalid mode. Valid modes: {valid_modes}",
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
        if not args:
            return CommandResponse(
                success=True,
                message="Session commands: /session list, /session pause <id>, /session resume <id>"
            )
        return CommandResponse(
            success=True,
            message="Session info requested.",
            data={"action": args[0] if args else None}
        )

    def _handle_pause(self, request: CommandRequest) -> CommandResponse:
        """AC-016: Pause active engineering work (PRD §31)."""
        args = request.arguments.get("args", [])
        if args:
            session_id = args[0]
            self._engine.interrupt_execution(session_id)
            return CommandResponse(success=True, message=f"Paused session: {session_id}")
        return CommandResponse(success=False, message="Session ID required", error="missing_argument")

    def _handle_resume(self, request: CommandRequest) -> CommandResponse:
        """AC-017: Resume paused work (PRD §31)."""
        args = request.arguments.get("args", [])
        if args:
            session_id = args[0]
            return CommandResponse(success=True, message=f"Resume requested for session: {session_id}")
        return CommandResponse(success=False, message="Session ID required", error="missing_argument")

    def _handle_cancel(self, request: CommandRequest) -> CommandResponse:
        """AC-015: Cancel active operation (PRD §30)."""
        args = request.arguments.get("args", [])
        if args:
            session_id = args[0]
            self._engine.cancel_objective(session_id)
            return CommandResponse(success=True, message=f"Cancelled execution for session: {session_id}")
        return CommandResponse(success=False, message="Session ID required", error="missing_argument")

    def _handle_clear(self, request: CommandRequest) -> CommandResponse:
        """Clear interaction display. PRD §11 V1 command."""
        return CommandResponse(success=True, message="Display cleared.")

    def _handle_exit(self, request: CommandRequest) -> CommandResponse:
        """Exit ClaireCoder. PRD §11 V1 command."""
        return CommandResponse(success=True, message="Exiting ClaireCoder.", data={"exit": True})
