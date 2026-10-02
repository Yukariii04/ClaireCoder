"""Tests for Stage 7 Real /model Command (Discovery-backed model inspection and switching)."""
import pytest
from clairecoder.gateway.types import (
    Model, Provider, Endpoint, Capability
)
from clairecoder.gateway.gateway import ModelGateway
from clairecoder.interaction.controller import InteractionController
from clairecoder.interaction.types import CommandRequest
from clairecoder.interaction.parser import CommandParser
from clairecoder.engine.engine import EngineeringEngine
from clairecoder.tools.executor import ToolExecutor
from clairecoder.tools.registry import ToolRegistry
from clairecoder.permissions.engine import PermissionEngine


def test_model_command_list_available_models():
    """Verify /model lists real registered models with their capabilities."""
    gateway = ModelGateway()
    p = Provider(id="groq", name="Groq")
    ep = Endpoint(url="https://api.groq.com")

    m1 = Model(id="llama-3.3-70b", display_name="Llama 3.3 70B", provider=p, endpoint=ep, capabilities=[Capability.TEXT, Capability.TOOL_CALLING])
    m2 = Model(id="mixtral-8x7b", display_name="Mixtral 8x7B", provider=p, endpoint=ep, capabilities=[Capability.TEXT, Capability.STREAMING])
    gateway.register_model(m1)
    gateway.register_model(m2)

    engine = EngineeringEngine(model_gateway=gateway, tool_executor=ToolExecutor(ToolRegistry(), PermissionEngine()))
    controller = InteractionController(engine=engine)

    req = CommandParser.parse("/model")
    resp = controller.execute_command(req)

    assert resp.success is True
    assert "Available models (2):" in resp.message
    assert "llama-3.3-70b" in resp.message
    assert "mixtral-8x7b" in resp.message
    assert "llama-3.3-70b" in resp.data["models"]


def test_model_command_switch_model():
    """Verify /model <model_id> switches to a valid registered model."""
    gateway = ModelGateway()
    p = Provider(id="openai", name="OpenAI")
    ep = Endpoint(url="https://api.openai.com")
    m1 = Model(id="gpt-4o", display_name="GPT-4o", provider=p, endpoint=ep)
    gateway.register_model(m1)

    engine = EngineeringEngine(model_gateway=gateway, tool_executor=ToolExecutor(ToolRegistry(), PermissionEngine()))
    controller = InteractionController(engine=engine)

    # Valid model switch
    req = CommandParser.parse("/model gpt-4o")
    resp = controller.execute_command(req)
    assert resp.success is True
    assert "Model switched to: gpt-4o" in resp.message
    assert resp.data["model_id"] == "gpt-4o"

    # Unknown model switch
    req_unknown = CommandParser.parse("/model nonexistent-model")
    resp_unknown = controller.execute_command(req_unknown)
    assert resp_unknown.success is False
    assert "Unknown model: nonexistent-model" in resp_unknown.message
    assert resp_unknown.error == "model_not_found"


def test_model_switching_blocked_during_active_execution():
    """Verify /model refuses to switch models underneath an actively executing engineering task."""
    from clairecoder.engine.types import EngineeringObjective, ObjectiveStatus

    gateway = ModelGateway()
    p = Provider(id="ollama", name="Ollama")
    ep = Endpoint(url="http://localhost:11434")
    m1 = Model(id="qwen2.5-coder:3b", display_name="Qwen", provider=p, endpoint=ep)
    m2 = Model(id="llama3.2:3b", display_name="Llama", provider=p, endpoint=ep)
    gateway.register_model(m1)
    gateway.register_model(m2)

    engine = EngineeringEngine(model_gateway=gateway, tool_executor=ToolExecutor(ToolRegistry(), PermissionEngine()))
    controller = InteractionController(engine=engine)

    # Create active session with an active objective
    obj = EngineeringObjective(
        id="obj_active",
        request="Writing code...",
        session_id="sess_active_test",
        status=ObjectiveStatus.ACTIVE,
        model_profile_id="qwen2.5-coder:3b",
    )
    sess = engine.receive_objective(obj)
    controller._active_session_id = sess.id

    # Set up an active AgentRun in RUNNING state (§8: authoritative run state)
    from clairecoder.interaction.run_state import AgentRun
    run = AgentRun("test_run")
    run.start()
    controller._active_run = run

    # Attempt to switch model during active execution
    req = CommandParser.parse("/model llama3.2:3b")
    resp = controller.execute_command(req)

    assert resp.success is False
    assert "unavailable while execution is active" in resp.message
    assert resp.error == "execution_active"
    assert sess.model_profile == "qwen2.5-coder:3b"

    # Complete the run → switching should be unlocked
    run.complete()
    controller._active_run = None
    resp_idle = controller.execute_command(req)
    assert resp_idle.success is True
    assert "llama3.2:3b" in resp_idle.message
    assert sess.model_profile == "llama3.2:3b"

