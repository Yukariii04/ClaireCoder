"""Tests for Stage 7 Setup Wizard State Machine, Geometry, UX, and Error Containment."""
import pytest
from unittest.mock import MagicMock
from clairecoder.tui.wizard import SetupWizard, WizardStage, WizardCardGeometry
from clairecoder.tui.canvas import visible_length
from clairecoder.gateway.config import PROVIDER_REGISTRY


def test_wizard_initial_state():
    """Verify wizard starts in PROVIDER_SELECT stage with non-empty grouped provider list."""
    wizard = SetupWizard()
    assert wizard.stage == WizardStage.PROVIDER_SELECT
    assert wizard.is_active is True
    assert wizard.is_complete is False
    assert len(wizard._provider_list) > 0

    headers = [item for item in wizard._provider_list if item.get("type") == "header"]
    assert len(headers) >= 3  # HOSTED, LOCAL, CUSTOM


def test_wizard_provider_selection_navigation():
    """Test Up/Down navigation skips header rows and selects providers."""
    wizard = SetupWizard()
    selectable = wizard._selectable_indices()

    # Initial selection should be first selectable item
    assert wizard.selected_index == selectable[0]

    # Move down
    wizard.handle_key("down")
    assert wizard.selected_index == selectable[1]

    # Move up
    wizard.handle_key("up")
    assert wizard.selected_index == selectable[0]

    # Enter chooses provider and advances to CREDENTIAL_ENTRY
    wizard.handle_key("enter")
    assert wizard.stage == WizardStage.CREDENTIAL_ENTRY
    assert wizard.selected_provider is not None
    assert wizard.selected_provider["id"] == "openai"


def test_wizard_credential_entry_and_validation():
    """Test typing credential, masking, validation trigger and callbacks."""
    wizard = SetupWizard()
    wizard.handle_key("enter")  # Selects OpenAI -> CREDENTIAL_ENTRY
    assert wizard.stage == WizardStage.CREDENTIAL_ENTRY

    # Type credential characters
    for ch in "sk-testkey123":
        wizard.handle_key(ch)
    assert wizard.credential_input == "sk-testkey123"

    # Test backspace
    wizard.handle_key("backspace")
    assert wizard.credential_input == "sk-testkey12"

    # Wire validation callback
    mock_validate = MagicMock()
    wizard.on_validate = mock_validate

    # Press enter to validate
    wizard.handle_key("enter")
    assert wizard.stage == WizardStage.VALIDATING
    mock_validate.assert_called_once()

    # Simulate validation success and model discovery
    wizard.complete_validation(success=True)
    assert wizard.stage == WizardStage.DISCOVERING

    mock_models = [
        {"id": "gpt-4o", "display_name": "GPT-4o", "capabilities": ["text", "tool_calling", "streaming"]},
        {"id": "gpt-4o-mini", "display_name": "GPT-4o Mini", "capabilities": ["text", "streaming"]},
    ]
    wizard.complete_discovery(mock_models)
    assert wizard.stage == WizardStage.MODEL_SELECT
    assert len(wizard.discovered_models) == 2


def test_wizard_model_selection_and_capabilities():
    """Test model picker scrolling, capabilities view, and skill selection."""
    wizard = SetupWizard()
    wizard.stage = WizardStage.MODEL_SELECT
    wizard.discovered_models = [
        {"id": f"model-{i}", "display_name": f"Model {i}", "capabilities": ["text", "tool_calling"]}
        for i in range(15)
    ]
    wizard.model_selected_index = 0

    # Down navigation
    wizard.handle_key("down")
    assert wizard.model_selected_index == 1

    # Select model -> CAPABILITY_VIEW
    wizard.handle_key("enter")
    assert wizard.stage == WizardStage.CAPABILITY_VIEW
    assert wizard.selected_model["id"] == "model-1"

    # Enter continues to SKILL_SELECT
    wizard.handle_key("enter")
    assert wizard.stage == WizardStage.SKILL_SELECT

    # Toggle skill with Enter/Space
    initial_enabled = wizard.available_skills[0]["enabled"]
    wizard.handle_key("enter")
    assert wizard.available_skills[0]["enabled"] != initial_enabled

    # Tab moves to SUMMARY
    wizard.handle_key("tab")
    assert wizard.stage == WizardStage.SUMMARY


def test_wizard_summary_and_save_lifecycle():
    """Test summary view, save callback execution, and completion."""
    wizard = SetupWizard()
    wizard.stage = WizardStage.SUMMARY
    wizard.selected_provider = {"id": "openai", "name": "OpenAI", "category": "hosted"}
    wizard.selected_model = {"id": "gpt-4o"}
    wizard.credential_input = "sk-test"

    mock_save = MagicMock()
    wizard.on_save = mock_save

    wizard.handle_key("enter")
    assert wizard.stage == WizardStage.SAVING
    mock_save.assert_called_once()

    # Complete save
    wizard.complete_save(profile_id="openai-main")
    assert wizard.stage == WizardStage.COMPLETE
    assert wizard.is_complete is True
    assert wizard.saved_profile_id == "openai-main"


def test_wizard_error_handling_and_retry():
    """Test validation error display and retry navigation."""
    wizard = SetupWizard()
    wizard.stage = WizardStage.VALIDATING
    wizard.complete_validation(success=False, error="Invalid API Key (HTTP 401)")

    assert wizard.stage == WizardStage.ERROR
    assert "Invalid API Key" in wizard.validation_error

    # Press enter to retry -> returns to CREDENTIAL_ENTRY
    wizard.handle_key("enter")
    assert wizard.stage == WizardStage.CREDENTIAL_ENTRY
    assert wizard.validation_error is None


def test_wizard_card_geometry_mathematical_invariant():
    """Verify len(top_border) == len(body_row) == len(bottom_border) == card_width <= available_width.
    
    Tests widths from 40 to 160 across all wizard rendering modes.
    """
    wizard = SetupWizard()
    wizard.selected_provider = {"id": "groq", "name": "Groq Cloud", "category": "hosted", "requires_api_key": True}
    wizard.selected_model = {"id": "llama-3.3-70b-versatile", "display_name": "Llama 3.3 70B", "capabilities": ["tool_calling"]}
    wizard.discovered_models = [wizard.selected_model]
    wizard.credential_input = "gsk_test1234567890"

    test_widths = [40, 50, 60, 70, 74, 80, 100, 120, 160]
    stages_to_test = [
        WizardStage.PROVIDER_SELECT,
        WizardStage.CREDENTIAL_ENTRY,
        WizardStage.VALIDATING,
        WizardStage.DISCOVERING,
        WizardStage.MODEL_SELECT,
        WizardStage.CAPABILITY_VIEW,
        WizardStage.SKILL_SELECT,
        WizardStage.SUMMARY,
        WizardStage.ERROR,
    ]

    for stage in stages_to_test:
        wizard.stage = stage
        if stage == WizardStage.ERROR:
            wizard.validation_error = "Connection failed: HTTP 403 Forbidden"

        for w in test_widths:
            lines = wizard.render(width=w)
            assert len(lines) > 0, f"Empty render for stage {stage} at width {w}"
            
            # Find the card border rows (first is top border, last is bottom border)
            top_len = visible_length(lines[0])
            bot_len = visible_length(lines[-1])
            
            # Every row in the card must have the exact same visible length
            for idx, row in enumerate(lines):
                row_len = visible_length(row)
                assert row_len == top_len, (
                    f"Row {idx} length ({row_len}) != top border length ({top_len}) "
                    f"in stage {stage} at width {w}:\nRow: {row}\nTop: {lines[0]}"
                )
                assert row_len <= w, (
                    f"Row {idx} length ({row_len}) exceeds available width ({w}) "
                    f"in stage {stage}"
                )
            assert bot_len == top_len


def test_wizard_groq_403_error_containment(capsys):
    """Verify Groq 403 error is cleanly formatted and contained inside the wizard card without stderr leak."""
    wizard = SetupWizard()
    wizard.selected_provider = {"id": "groq", "name": "Groq Cloud"}
    wizard.stage = WizardStage.VALIDATING

    raw_error = "Model discovery failed for groq: HTTP Error 403: Forbidden\nTraceback (most recent call last):\n  File 'discovery.py', line 74"
    wizard.complete_validation(success=False, error=raw_error)

    assert wizard.stage == WizardStage.ERROR
    assert "403" in wizard.validation_error or "Forbidden" in wizard.validation_error
    assert "Traceback" not in wizard.validation_error

    # Ensure rendered card lines remain strictly bounded
    card_lines = wizard.render(width=80)
    for line in card_lines:
        assert visible_length(line) <= 80
        assert "Traceback" not in line

    # Verify no unhandled prints leaked to capsys
    out, err = capsys.readouterr()
    assert "Traceback" not in err
    assert "Traceback" not in out


def test_wizard_stale_event_protection():
    """Verify that rapid provider switching ignores stale validation/discovery completions."""
    wizard = SetupWizard()
    wizard.selected_provider = {"id": "openai", "name": "OpenAI"}
    wizard.stage = WizardStage.CREDENTIAL_ENTRY
    wizard.handle_key("enter")  # starts validation for OpenAI -> active_request_id = req_openai_1
    req1 = wizard.active_request_id
    assert "openai" in req1

    # User immediately escapes and switches to Ollama
    wizard.stage = WizardStage.PROVIDER_SELECT
    wizard.selected_provider = {"id": "ollama", "name": "Ollama"}
    wizard.stage = WizardStage.CREDENTIAL_ENTRY
    wizard.handle_key("enter")  # starts validation for Ollama -> active_request_id = req_ollama_2
    req2 = wizard.active_request_id
    assert "ollama" in req2
    assert req2 != req1

    # Stale completion for OpenAI arrives late
    wizard.complete_validation(success=True, request_id=req1)
    # Wizard should still be validating Ollama, NOT discovering with OpenAI's request
    assert wizard.stage == WizardStage.VALIDATING
    assert wizard.active_request_id == req2

    # Fresh completion for Ollama arrives
    wizard.complete_validation(success=True, request_id=req2)
    assert wizard.stage == WizardStage.DISCOVERING


def test_wizard_secret_masking():
    """Verify that credentials are fully masked with asterisks in the render output."""
    wizard = SetupWizard()
    wizard.stage = WizardStage.CREDENTIAL_ENTRY
    wizard.selected_provider = {"id": "openai", "name": "OpenAI", "requires_api_key": True}
    wizard.credential_input = "sk-proj-secret1234567890"

    rendered = "\n".join(wizard.render(width=80))
    assert "sk-proj-secret" not in rendered
    assert "**********************" in rendered or "••••" in rendered or "*" in rendered


def test_wizard_validation_and_discovery_state_machine():
    """Verify the setup wizard progresses cleanly through validation and discovery."""
    wizard = SetupWizard()
    wizard.stage = WizardStage.CREDENTIAL_ENTRY
    wizard.selected_provider = {"id": "ollama", "name": "Ollama", "default_endpoint": "http://localhost:11434"}

    validated = False
    discovered = False

    def mock_on_validate(provider, credential, endpoint, **kwargs):
        nonlocal validated
        validated = True
        wizard.complete_validation(success=True)

    def mock_on_discover(provider, credential, endpoint, **kwargs):
        nonlocal discovered
        discovered = True
        wizard.complete_discovery([
            {"id": "qwen2.5-coder:3b", "display_name": "Qwen 2.5 Coder 3B", "capabilities": ["tool_calling"]}
        ])

    wizard.on_validate = mock_on_validate
    wizard.on_discover = mock_on_discover

    # Press Enter on credential screen -> begins validation
    wizard.handle_key("enter")

    assert validated is True
    assert discovered is True
    assert wizard.stage == WizardStage.MODEL_SELECT


def test_wizard_save_uses_runtime_sync_callback():
    """Verify _wizard_on_save uses register_runtime_sync_callback without referencing _app."""
    from clairecoder.tui.app import TuiApplication
    from clairecoder.gateway.manager import ConfigurationManager
    from clairecoder.gateway.config import ProviderProfile, AdapterType
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = ConfigurationManager(workspace_root=tmpdir)
        app = TuiApplication(workspace_root=tmpdir)
        app.connect_config_manager(cfg)

        sync_called = False
        def mock_sync():
            nonlocal sync_called
            sync_called = True

        app.register_runtime_sync_callback(mock_sync)

        # Configure wizard
        app.wizard.selected_provider = {
            "id": "ollama",
            "name": "Ollama",
            "category": "local",
            "adapter_type": "ollama",
            "default_endpoint": "http://localhost:11434",
        }
        app.wizard.selected_model = {"id": "qwen2.5-coder:3b", "context_capacity": 32768}
        app.wizard.discovered_models = [
            {"id": "qwen2.5-coder:3b", "capabilities": ["tool_calling"], "context_capacity": 32768}
        ]

        # Trigger save
        app._wizard_on_save(
            provider=app.wizard.selected_provider,
            credential="",
            endpoint="http://localhost:11434",
            model=app.wizard.selected_model,
            skills=[],
        )

        assert sync_called is True
        assert app.wizard.stage == WizardStage.COMPLETE
        assert app.wizard.saved_profile_id == "ollama"
        assert app.header.model == "qwen2.5-coder:3b"


def test_wizard_save_credential_backend_failure_contained():
    """Verify that when keyring backend is unavailable, wizard enters ERROR stage with clear message."""
    from clairecoder.tui.app import TuiApplication
    from clairecoder.gateway.manager import ConfigurationManager
    from unittest.mock import patch
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = ConfigurationManager(workspace_root=tmpdir)
        app = TuiApplication(workspace_root=tmpdir)
        app.connect_config_manager(cfg)

        app.wizard.selected_provider = {
            "id": "groq",
            "name": "Groq Cloud",
            "category": "hosted",
            "adapter_type": "openai",
            "requires_api_key": True,
        }
        app.wizard.selected_model = {"id": "llama-3.3-70b-versatile"}

        # Simulate keyring failure
        with patch("clairecoder.gateway.credentials.CredentialStore.check_backend_health",
                   return_value=(False, "fail.Keyring", "No recommended backend was available.")):
            app._wizard_on_save(
                provider=app.wizard.selected_provider,
                credential="gsk_testkey123",
                endpoint="https://api.groq.com/openai/v1",
                model=app.wizard.selected_model,
                skills=[],
            )

        assert app.wizard.stage == WizardStage.ERROR
        assert "No recommended backend" in app.wizard.validation_error or "Credential storage failed" in app.wizard.validation_error


def test_tui_app_stop_idempotency_and_render_guard():
    """Verify stop() is idempotent and does not execute multiple clear calls or render extra frames."""
    from clairecoder.tui.app import TuiApplication
    from clairecoder.tui.terminal import TerminalRenderer
    import io

    stream = io.StringIO()
    renderer = TerminalRenderer(stream=stream, enable_ansi=True)
    app = TuiApplication(renderer=renderer)
    app.start()

    # Initial frame
    app.render_initial_frame()
    frames_before = renderer.rendered_frames_count

    # First stop
    app.stop()
    assert app.running is False
    assert app._exit_cleanup_done is True
    assert app._exiting is True

    # Redraw while exiting is a no-op
    app.redraw()
    assert renderer.rendered_frames_count == frames_before

    # Second stop is safe and idempotent
    app.stop()
    assert app._exit_cleanup_done is True


def test_tui_app_runtime_failure_handling(capsys):
    """Verify _handle_runtime_failure logs to transcript and stderr without crashing."""
    from clairecoder.tui.app import TuiApplication

    app = TuiApplication()
    app.start()

    test_exc = ValueError("Test explosion in engine")
    app._handle_runtime_failure(test_exc, context="unit_test")

    # Stderr has diagnostic
    out, err = capsys.readouterr()
    assert "Test explosion in engine" in err
    assert "unit_test" in err

    # Transcript has error activity
    acts = app.transcript.activities
    assert any(a.title in ("Runtime Error", "Error") for a in acts)


def test_wizard_save_success_with_runtime_sync(tmp_path):
    """Wizard save completes when runtime sync succeeds."""
    from clairecoder.gateway.manager import ConfigurationManager
    from clairecoder.tui.app import TuiApplication
    cm = ConfigurationManager(workspace_root=str(tmp_path))
    tui = TuiApplication(workspace_root=str(tmp_path))
    tui.connect_config_manager(cm)

    sync_called = []
    def mock_sync():
        sync_called.append(True)
        return True

    tui.register_runtime_sync_callback(mock_sync)

    tui.open_wizard()
    tui.wizard.stage = WizardStage.SUMMARY
    tui.wizard.discovered_models = [
        {"id": "deepseek-coder", "capabilities": ["code_generation"], "context_capacity": 64000}
    ]

    tui._wizard_on_save(
        provider={"id": "openrouter", "name": "OpenRouter", "adapter": "openai_compatible", "default_endpoint": "https://openrouter.ai/api/v1"},
        credential="test-key",
        endpoint="https://openrouter.ai/api/v1",
        model={"id": "deepseek-coder", "context_capacity": 64000},
        skills=[],
    )

    assert sync_called == [True]
    assert tui.wizard.stage == WizardStage.COMPLETE
    assert tui.wizard.saved_profile_id == "openrouter"

    active = cm.get_active()
    assert active.get("provider_profile_id") == "openrouter"
    assert active.get("model_id") == "deepseek-coder"


def test_wizard_save_fails_when_runtime_sync_fails(tmp_path):
    """Wizard save rolls back / surfaces error if runtime sync raises exception."""
    from clairecoder.gateway.manager import ConfigurationManager
    from clairecoder.tui.app import TuiApplication
    cm = ConfigurationManager(workspace_root=str(tmp_path))
    tui = TuiApplication(workspace_root=str(tmp_path))
    tui.connect_config_manager(cm)

    def failing_sync():
        raise RuntimeError("Gateway adapter failed to initialize")

    tui.register_runtime_sync_callback(failing_sync)

    tui.open_wizard()
    tui.wizard.stage = WizardStage.SUMMARY
    tui.wizard.discovered_models = [{"id": "model-1", "capabilities": ["text"]}]

    tui._wizard_on_save(
        provider={"id": "broken_prov", "name": "Broken", "adapter": "openai_compatible"},
        credential="key",
        endpoint="http://localhost:9999",
        model={"id": "model-1"},
        skills=[],
    )

    assert tui.wizard.stage == WizardStage.ERROR
    assert "Gateway adapter failed to initialize" in tui.wizard.validation_error
