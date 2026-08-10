import pytest
from clairecoder.interaction.types import InteractionMode, CommandRequest, CommandCategory
from clairecoder.interaction.parser import CommandParser
from clairecoder.interaction.controller import InteractionController
from clairecoder.engine.engine import EngineeringEngine
from clairecoder.gateway.interfaces import ModelGatewayInterface
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.registry import ToolRegistry
from clairecoder.permissions.engine import PermissionEngine

class MockGateway(ModelGatewayInterface):
    def register_adapter(self, adapter): pass
    def register_model(self, model): pass
    def register_profile(self, profile): pass
    def resolve_profile(self, profile_id): return None
    def get_model(self, model_id): return None
    def check_capability(self, model_id, cap): return False
    def execute(self, request): return None


# =============================================================================
# PARSER TESTS
# =============================================================================

def test_command_parser_identifies_commands():
    """AC-002: The developer can issue explicit commands."""
    assert CommandParser.is_command("/help") is True
    assert CommandParser.is_command(" /status ") is True
    assert CommandParser.is_command("Add authentication") is False
    assert CommandParser.is_command("") is False

def test_command_parser_parses_arguments():
    """Command arguments are parsed correctly."""
    req = CommandParser.parse("/mode implement")
    assert req is not None
    assert req.command == "mode"
    assert req.arguments["args"] == ["implement"]

def test_command_parser_bare_slash():
    """PRD §13: Bare '/' SHALL NOT be silently treated as natural language."""
    req = CommandParser.parse("/")
    assert req is not None
    assert req.command == ""

def test_command_parser_non_command_returns_none():
    """Non-command input returns None (natural language path)."""
    assert CommandParser.parse("Add authentication") is None
    assert CommandParser.parse("") is None

def test_command_parser_preserves_raw_input():
    """Raw input is preserved in the CommandRequest."""
    req = CommandParser.parse("/mode review")
    assert req.raw_input == "/mode review"

def test_command_parser_case_insensitive():
    """Commands are lowercased during parsing."""
    req = CommandParser.parse("/HELP")
    assert req.command == "help"


# =============================================================================
# MODE TESTS
# =============================================================================

def test_interaction_mode_enum_matches_prd():
    """PRD §16: V1 Modes are PLAN, IMPLEMENT, REVIEW, DEBUG exactly."""
    mode_values = {m.value for m in InteractionMode}
    assert mode_values == {"plan", "implement", "review", "debug"}

def test_interaction_mode_default_is_implement():
    """Default mode is IMPLEMENT per PRD §16."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))
    assert controller._mode == InteractionMode.IMPLEMENT

def test_interaction_mode_switching():
    """AC-005, AC-006, AC-007: Modes can be inspected and switched."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    # Inspect current mode — default is IMPLEMENT
    req1 = CommandParser.parse("/mode")
    res1 = controller.execute_command(req1)
    assert res1.success is True
    assert "IMPLEMENT" in res1.message

    # Switch mode to REVIEW
    req2 = CommandParser.parse("/mode review")
    res2 = controller.execute_command(req2)
    assert res2.success is True
    assert "REVIEW" in res2.message

    # Switch mode to PLAN
    req3 = CommandParser.parse("/mode plan")
    res3 = controller.execute_command(req3)
    assert res3.success is True
    assert "PLAN" in res3.message

    # Switch mode to DEBUG
    req4 = CommandParser.parse("/mode debug")
    res4 = controller.execute_command(req4)
    assert res4.success is True
    assert "DEBUG" in res4.message

    # Invalid mode
    req5 = CommandParser.parse("/mode invalid_mode")
    res5 = controller.execute_command(req5)
    assert res5.success is False
    assert res5.error == "invalid_mode"

def test_mode_switching_does_not_destroy_state():
    """PRD §19 / ADR §16: Mode switching SHALL NOT destroy plan/session/context."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    engine = EngineeringEngine(gateway, executor)
    controller = InteractionController(engine)

    # Create an objective
    controller.process_natural_language("Test objective", "sess_mode")
    session_before = engine.get_session("sess_mode")
    assert session_before is not None

    # Switch mode
    controller.execute_command(CommandParser.parse("/mode debug"))

    # Session still exists
    session_after = engine.get_session("sess_mode")
    assert session_after is not None
    assert session_after.objective.request == "Test objective"


# =============================================================================
# NATURAL LANGUAGE TESTS
# =============================================================================

def test_interaction_controller_natural_language():
    """AC-001: The developer can provide normal engineering requests."""
    gateway = MockGateway()
    registry = ToolRegistry()
    perm_engine = PermissionEngine()
    executor = ToolExecutor(registry, perm_engine)
    engine = EngineeringEngine(gateway, executor)

    controller = InteractionController(engine)
    response = controller.process_natural_language("Add authentication", "session-1")

    assert "Objective accepted" in response
    session = engine.get_session("session-1")
    assert session is not None
    assert session.objective.request == "Add authentication"


# =============================================================================
# COMMAND TESTS (V1 command set: PRD §11)
# =============================================================================

def test_interaction_controller_help_command():
    """AC-003: The developer can discover available commands."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    req = CommandParser.parse("/help")
    res = controller.execute_command(req)

    assert res.success is True
    # All V1 commands must appear in help
    for cmd_name in ["help", "status", "mode", "plan", "session", "pause", "resume", "cancel", "clear", "exit"]:
        assert f"/{cmd_name}" in res.message

def test_interaction_controller_invalid_command():
    """AC-004: Invalid commands produce clear errors."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    req = CommandParser.parse("/does_not_exist")
    res = controller.execute_command(req)

    assert res.success is False
    assert res.error == "invalid_command"
    assert "Unknown command" in res.message

def test_interaction_controller_empty_command():
    """PRD §13: Bare '/' produces a clear error, not silent natural language."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    req = CommandParser.parse("/")
    res = controller.execute_command(req)

    assert res.success is False
    assert res.error == "empty_command"

def test_interaction_controller_status_command():
    """AC-012: /status provides concise engineering status."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    req = CommandParser.parse("/status")
    res = controller.execute_command(req)

    assert res.success is True
    assert "Mode" in res.message
    assert "IMPLEMENT" in res.message
    assert res.data["mode"] == "implement"

def test_interaction_controller_plan_command():
    """AC-011: /plan inspects the active plan."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    req = CommandParser.parse("/plan")
    res = controller.execute_command(req)

    assert res.success is True
    assert "plan" in res.message.lower()

def test_interaction_controller_session_command():
    """AC-008: /session inspects and controls sessions."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    req = CommandParser.parse("/session")
    res = controller.execute_command(req)

    assert res.success is True

def test_interaction_controller_clear_command():
    """PRD §11: /clear clears the interaction display."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    req = CommandParser.parse("/clear")
    res = controller.execute_command(req)
    assert res.success is True

def test_interaction_controller_exit_command():
    """PRD §11: /exit exits ClaireCoder."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    req = CommandParser.parse("/exit")
    res = controller.execute_command(req)
    assert res.success is True
    assert res.data.get("exit") is True


# =============================================================================
# PAUSE / CANCEL / RESUME TESTS
# =============================================================================

def test_interaction_pause_cancel_commands():
    """AC-015, AC-016: Cancellation and pause can be requested."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    engine = EngineeringEngine(gateway, executor)
    controller = InteractionController(engine)

    # Need an objective to cancel/pause
    controller.process_natural_language("test", "sess_1")

    # Pause
    req_pause = CommandParser.parse("/pause sess_1")
    res_pause = controller.execute_command(req_pause)
    assert res_pause.success is True

    # Cancel
    req_cancel = CommandParser.parse("/cancel sess_1")
    res_cancel = controller.execute_command(req_cancel)
    assert res_cancel.success is True

    sess = engine.get_session("sess_1")
    from clairecoder.engine.types import ObjectiveStatus
    assert sess.objective.status == ObjectiveStatus.CANCELLED

def test_interaction_resume_command():
    """AC-017: Resume paused work."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    engine = EngineeringEngine(gateway, executor)
    controller = InteractionController(engine)

    controller.process_natural_language("test", "sess_resume")

    req = CommandParser.parse("/resume sess_resume")
    res = controller.execute_command(req)
    assert res.success is True
    assert "Resume requested" in res.message

def test_pause_missing_session_id():
    """Missing argument produces clear error."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    req = CommandParser.parse("/pause")
    res = controller.execute_command(req)
    assert res.success is False
    assert res.error == "missing_argument"

def test_cancel_missing_session_id():
    """Missing argument produces clear error."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    controller = InteractionController(EngineeringEngine(gateway, executor))

    req = CommandParser.parse("/cancel")
    res = controller.execute_command(req)
    assert res.success is False
    assert res.error == "missing_argument"


# =============================================================================
# ARCHITECTURAL BOUNDARY TESTS
# =============================================================================

def test_interaction_boundary_delegation():
    """Interaction cannot directly execute tools, bypass permissions, or access SDKs."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    engine = EngineeringEngine(gateway, executor)
    controller = InteractionController(engine)

    # The interaction controller does NOT have a reference to ToolExecutor or PermissionEngine directly
    assert not hasattr(controller, "_tool_executor")
    assert not hasattr(controller, "_permission_engine")
    assert not hasattr(controller, "_model_gateway")
    assert not hasattr(controller, "_workflow_manager")
    assert not hasattr(controller, "_execution_manager")

    # It only has a reference to the Engine
    assert hasattr(controller, "_engine")

def test_interaction_does_not_own_engine_state():
    """The Interaction Layer does not own EngineeringEngine state (ADR §32)."""
    gateway = MockGateway()
    executor = ToolExecutor(ToolRegistry(), PermissionEngine())
    engine = EngineeringEngine(gateway, executor)
    controller = InteractionController(engine)

    # Controller has no session storage of its own
    assert not hasattr(controller, "_sessions")

def test_command_category_enum_covers_prd():
    """PRD §10 and ADR §8: All required command categories exist."""
    category_values = {c.value for c in CommandCategory}
    # PRD §10: Session, Workflow, Task, Mode, System, Execution
    for required in ["session", "workflow", "task", "mode", "system", "execution"]:
        assert required in category_values
    # ADR §8 additions: agent, model, skill, tool
    for adr_cat in ["agent", "model", "skill", "tool"]:
        assert adr_cat in category_values
