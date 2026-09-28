"""Global test fixtures and configuration for ClaireCoder V1 test suite."""
import os
import pytest
from unittest.mock import Mock

from clairecoder.gateway.types import Model, Provider, Endpoint, Capability, ModelResponse
from clairecoder.tui.terminal import TerminalCapability, TerminalRenderer


@pytest.fixture
def mock_terminal_capability():
    """Returns a deterministic TerminalCapability with ANSI color enabled."""
    return TerminalCapability(has_color=True, has_unicode=True, width=120, height=35)


@pytest.fixture
def mock_terminal_renderer():
    """Returns a TerminalRenderer with in-memory stream."""
    import io
    stream = io.StringIO()
    return TerminalRenderer(stream=stream, enable_ansi=True)


@pytest.fixture
def sample_provider_models():
    """Returns standard mock models for provider selection testing."""
    provider = Provider(id="ollama", name="Ollama")
    ep = Endpoint(url="http://localhost:11434")

    model1 = Model(
        id="qwen2.5-coder:3b",
        display_name="Qwen 2.5 Coder 3B",
        provider=provider,
        endpoint=ep,
        capabilities=[Capability.TEXT, Capability.STREAMING, Capability.TOOL_CALLING],
        context_capacity=32768,
    )
    model2 = Model(
        id="llama3.2:3b",
        display_name="Llama 3.2 3B",
        provider=provider,
        endpoint=ep,
        capabilities=[Capability.TEXT, Capability.STREAMING],
        context_capacity=131072,
    )
    return {"qwen2.5-coder:3b": model1, "llama3.2:3b": model2}
