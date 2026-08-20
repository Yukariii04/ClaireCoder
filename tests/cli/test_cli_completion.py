"""Tests for CLI Completion (Stage 6 & Stage 6 Correction #1)."""
from unittest.mock import MagicMock, patch

import pytest

from clairecoder.app import ClaireCoderV1
from clairecoder.cli.main import run_cli, run_direct, run_interactive
from clairecoder.gateway.interfaces import ModelGatewayInterface
from clairecoder.gateway.types import ErrorCategory, ModelError, ModelRequest, ModelResponse


class MockTestGateway(ModelGatewayInterface):
    """Mock gateway used strictly for testing the application boundary."""

    def __init__(self):
        self.requests = []
        self.responses = []

    def register_adapter(self, adapter) -> None:
        pass

    def register_model(self, model) -> None:
        pass

    def register_profile(self, profile) -> None:
        pass

    def resolve_profile(self, profile_id):
        pass

    def get_model(self, model_id):
        pass

    def check_capability(self, model_id, capability):
        pass

    def execute(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.responses:
            return self.responses.pop(0)
        return ModelResponse(
            text="Mock plan",
            structured_output={"task_ids": ["t1"], "completion_criteria": ["Done"]},
        )


def test_cli_version(capsys):
    """Test --version flag returns 0 and prints version."""
    exit_code = run_cli(["--version"])
    assert exit_code == 0
    out, err = capsys.readouterr()
    assert "ClaireCoder 0.1.0" in out


def test_cli_help(capsys):
    """Test help flag via argparse."""
    exit_code = run_cli(["--help"])
    assert exit_code == 0
    out, err = capsys.readouterr()
    assert "ClaireCoder V1 Developer CLI" in out
    assert "objective" in out


def test_cli_interactive_persistent_lifecycle():
    """Test that interactive mode enters a persistent lifecycle and processes scripted commands."""
    mock_gateway = MockTestGateway()
    app = ClaireCoderV1(model_gateway=mock_gateway)

    # Scripted input stream: status -> clear -> exit
    inputs = ["status", "clear", "exit"]
    exit_code = run_interactive(session_id="test_sess", app=app, input_source=inputs)

    assert exit_code == 0


def test_cli_interactive_shortcuts_and_overlays():
    """Test interactive lifecycle handling overlay shortcuts and closing them."""
    mock_gateway = MockTestGateway()
    app = ClaireCoderV1(model_gateway=mock_gateway)

    # Scripted input: open file tree -> close overlay via escape -> exit
    inputs = ["ctrl+t", "escape", "exit"]
    exit_code = run_interactive(session_id="test_tree_sess", app=app, input_source=inputs)

    assert exit_code == 0


def test_cli_interactive_natural_language_submission():
    """Test submitting natural language objective inside interactive TUI."""
    mock_gateway = MockTestGateway()
    app = ClaireCoderV1(model_gateway=mock_gateway)

    inputs = ["Fix the parser bug in module X", "/exit"]
    exit_code = run_interactive(session_id="test_nl_sess", app=app, input_source=inputs)

    assert exit_code == 0
    status = app.status("test_nl_sess")
    assert status["objective"]["request"] == "Fix the parser bug in module X"


def test_cli_direct_objective_success(capsys):
    """Test direct non-interactive objective execution through real application boundary."""
    mock_gateway = MockTestGateway()
    app = ClaireCoderV1(model_gateway=mock_gateway)

    with patch("clairecoder.app.ClaireCoderV1.run") as mock_run:
        with patch("clairecoder.app.ClaireCoderV1.status", return_value={"objective": {"status": "completed"}}):
            exit_code = run_direct("Fix authentication", session_id="s1", app=app)
            assert exit_code == 0
            out, err = capsys.readouterr()
            assert "Executing objective: Fix authentication" in out
            assert "Execution finished with status: completed" in out
            mock_run.assert_called_once()


def test_cli_direct_objective_failure_exit_code(capsys):
    """Test direct non-interactive failure produces exit code 1."""
    mock_gateway = MockTestGateway()
    app = ClaireCoderV1(model_gateway=mock_gateway)

    with patch("clairecoder.app.ClaireCoderV1.run"):
        with patch("clairecoder.app.ClaireCoderV1.status", return_value={"objective": {"status": "failed"}}):
            exit_code = run_direct("Fail task", session_id="s1", app=app)
            assert exit_code == 1
            out, err = capsys.readouterr()
            assert "Execution finished with status: failed" in out


def test_cli_direct_unconfigured_provider_error_reporting(capsys):
    """Test that without Stage 7 providers, direct mode reports provider configuration requirement."""
    # Real default ClaireCoderV1 with default ModelGateway (no configured models)
    app = ClaireCoderV1()
    exit_code = run_direct("Fix something without provider", session_id="s_no_prov", app=app)
    assert exit_code == 1
    out, err = capsys.readouterr()
    assert "Stage 7 provider configuration is required for live external model execution." in err


def test_cli_direct_keyboard_interrupt(capsys):
    """Test SIGINT / Ctrl+C in direct mode interrupts execution and returns 130."""
    app = ClaireCoderV1(model_gateway=MockTestGateway())
    with patch("clairecoder.app.ClaireCoderV1.run", side_effect=KeyboardInterrupt()):
        exit_code = run_direct("Interrupt task", session_id="s_int", app=app)
        assert exit_code == 130
        out, err = capsys.readouterr()
        assert "Operation interrupted by user (Ctrl+C)." in err


def test_cli_architectural_guardrails():
    """Verify CLI does not define any fake ModelGateway or provider configuration."""
    import inspect
    import clairecoder.cli.main as cli_main

    source = inspect.getsource(cli_main)
    assert "class DefaultGateway" not in source
    assert "Temporary provider stand-in" not in source
    assert "Direct objective acknowledged via CLI" not in source
    assert "Interactive terminal delegated to TUI" not in source

    # Ensure CLI does not own private engine or tools
    assert not hasattr(cli_main, "ToolExecutor")
    assert not hasattr(cli_main, "PermissionEngine")
    assert not hasattr(cli_main, "WorkflowManager")


def test_cli_subprocess_interactive_exit():
    """Test running CLI as an actual subprocess with scripted stdin exit."""
    import os
    import subprocess
    import sys

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(
        [sys.executable, "-m", "clairecoder"],
        input="status\nexit\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "ClaireCoder" in proc.stdout

