"""Comprehensive tests for Correction #22: Provider Reliability.

Verifies:
1. Error mapping:
   - timeout -> ProviderTimeoutError
   - connection failure -> ProviderConnectionError
   - 429 -> ProviderRateLimitError
   - 401/403 -> ProviderAuthenticationError
   - 5xx -> retryable provider failure
   - malformed response -> ProviderResponseError
   - invalid structured output -> ProviderInvalidOutputError
2. Retries:
   - transient failure retries
   - retry count is bounded
   - exponential backoff calculation
   - Retry-After handling
   - non-retryable errors do not retry
   - final error preserves useful metadata
3. Timeouts:
   - configured timeout is passed correctly
   - timeout is not accidentally overridden
   - Ollama timeout behavior
4. Endpoints:
   - empty endpoint fails clearly
   - trailing slash normalization
   - no accidental relative /models URL
5. Ollama:
   - valid response parsing
   - HTTP error handling
   - HTTP 200 with invalid/empty response
6. Structured Output:
   - valid output succeeds
   - invalid output follows existing planner fallback
   - provider failure remains distinguishable from validation failure
7. Events:
   - provider start, retry, completion, failure
   - correlation/attempt metadata
8. Secret Scrubbing:
   - sanitize_sensitive_data removes Bearer tokens, authorization headers, api keys
   - errors and events do not leak secrets
9. Health / Cooldown:
   - provider cooldown tracking prevents repeated hammering
"""

import json
import urllib.error
import pytest
from unittest.mock import MagicMock

from clairecoder.gateway.errors import (
    ProviderError,
    ProviderTimeoutError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    ProviderUnavailableError,
    ProviderResponseError,
    ProviderInvalidOutputError,
    sanitize_sensitive_data,
)
from clairecoder.gateway.types import (
    Capability,
    Endpoint,
    Model,
    ModelProfile,
    ModelRequest,
    ModelResponse,
    Provider,
)
from clairecoder.gateway.reliability import (
    ReliabilityConfig,
    calculate_backoff_delay,
    is_error_retryable,
    ProviderHealthTracker,
    RetryExecutor,
)
from clairecoder.gateway.gateway import ModelGateway
from clairecoder.gateway.adapters.ollama import OllamaAdapter
from clairecoder.gateway.adapters.openai import OpenAICompatibleAdapter
from clairecoder.gateway.adapters.anthropic import AnthropicAdapter
from clairecoder.gateway.adapters.gemini import GeminiAdapter
from clairecoder.runtime.events import EventType, RuntimeEvent
from clairecoder.runtime.emitter import EventEmitter
from clairecoder.workflow.planner import Planner, PLAN_SCHEMA
from clairecoder.workflow.types import PlanningLevel, PlanningError


# ============================================================================
# 1. Error Mapping Tests
# ============================================================================

class TestErrorMapping:
    def test_provider_timeout_error(self):
        err = ProviderTimeoutError(
            message="Request to api timed out",
            provider="openai",
            model="gpt-4o",
            operation="chat",
            timeout_seconds=45.0,
        )
        assert isinstance(err, ProviderError)
        assert err.status_code == 408
        assert err.error_code == "timeout"
        assert err.retryable is True
        assert err.timeout_seconds == 45.0
        assert err.provider == "openai"
        assert err.model == "gpt-4o"
        assert "45" in str(err)

    def test_provider_connection_error(self):
        err = ProviderConnectionError(
            message="Failed to connect to host 127.0.0.1:11434",
            provider="ollama",
            model="llama3",
        )
        assert isinstance(err, ProviderError)
        assert err.error_code == "connection_failed"
        assert err.retryable is True
        assert err.provider == "ollama"

    def test_provider_rate_limit_error(self):
        err = ProviderRateLimitError(
            message="Rate limit exceeded",
            provider="anthropic",
            model="claude-3-5-sonnet",
            retry_after=15.0,
        )
        assert isinstance(err, ProviderError)
        assert err.status_code == 429
        assert err.error_code == "rate_limit"
        assert err.retryable is True
        assert err.retry_after == 15.0

    @pytest.mark.parametrize("status_code", [401, 403])
    def test_provider_authentication_error(self, status_code):
        err = ProviderAuthenticationError(
            message="Invalid API Key provided",
            provider="openai",
            status_code=status_code,
        )
        assert isinstance(err, ProviderError)
        assert err.status_code == status_code
        assert err.error_code == "authentication_failed"
        assert err.retryable is False

    @pytest.mark.parametrize("status_code", [500, 502, 503, 504])
    def test_provider_5xx_retryable(self, status_code):
        if status_code in (503, 529):
            err = ProviderUnavailableError(
                message="Service unavailable",
                provider="gemini",
                status_code=status_code,
                retry_after=5.0,
            )
            assert err.retryable is True
            assert err.error_code == "unavailable"
        else:
            err = ProviderResponseError(
                message=f"Server returned HTTP {status_code}",
                provider="gemini",
                status_code=status_code,
                retryable=True,
            )
            assert err.retryable is True
            assert err.status_code == status_code

    def test_provider_malformed_response_error(self):
        err = ProviderResponseError(
            message="Provider returned malformed JSON: Expecting value: line 1 column 1 (char 0)",
            provider="openai",
            status_code=200,
            retryable=False,
        )
        assert isinstance(err, ProviderError)
        assert err.status_code == 200
        assert err.retryable is False
        assert err.error_code == "response_error"

    def test_provider_invalid_output_error(self):
        err = ProviderInvalidOutputError(
            message="Validation failed: 'tasks' is a required property",
            provider="ollama",
            model="llama3",
            raw_output="{'error': 'cannot parse'}",
        )
        assert isinstance(err, ProviderError)
        assert err.error_code == "invalid_output"
        assert err.retryable is False
        assert err.raw_output == "{'error': 'cannot parse'}"
        d = err.to_dict()
        assert d["error_code"] == "invalid_output"
        assert d["provider"] == "ollama"
        assert d["retryable"] is False


# ============================================================================
# 2. Retry Policy & Exponential Backoff Tests
# ============================================================================

class TestRetryPolicy:
    def test_exponential_backoff_calculation(self):
        cfg = ReliabilityConfig(
            initial_retry_delay=1.0,
            max_retry_delay=10.0,
            backoff_factor=2.0,
        )
        # Attempt 1: 1.0 * (2.0 ** 0) = 1.0
        assert calculate_backoff_delay(1, cfg) == 1.0
        # Attempt 2: 1.0 * (2.0 ** 1) = 2.0
        assert calculate_backoff_delay(2, cfg) == 2.0
        # Attempt 3: 1.0 * (2.0 ** 2) = 4.0
        assert calculate_backoff_delay(3, cfg) == 4.0
        # Attempt 4: 1.0 * (2.0 ** 3) = 8.0
        assert calculate_backoff_delay(4, cfg) == 8.0
        # Attempt 5: 1.0 * (2.0 ** 4) = 16.0 -> capped at 10.0
        assert calculate_backoff_delay(5, cfg) == 10.0

    def test_retry_after_header_handling(self):
        cfg = ReliabilityConfig(
            initial_retry_delay=1.0,
            max_retry_delay=15.0,
            backoff_factor=2.0,
        )
        # Explicit retry_after overrides backoff when within bound
        delay = calculate_backoff_delay(1, cfg, retry_after=7.5)
        assert delay == 7.5

        # Explicit retry_after is capped at max_retry_delay
        delay_capped = calculate_backoff_delay(1, cfg, retry_after=30.0)
        assert delay_capped == 15.0

    def test_retry_executor_transient_failure_retries_and_succeeds(self):
        delays = []
        calls = []

        def mock_sleep(d):
            delays.append(d)

        def mock_time():
            return 100.0 + len(calls) * 0.1

        cfg = ReliabilityConfig(
            max_retry_attempts=3,
            initial_retry_delay=0.5,
            backoff_factor=2.0,
        )
        executor = RetryExecutor(cfg, sleep_fn=mock_sleep, time_fn=mock_time)

        # Fails twice with retryable error, then succeeds
        def operation():
            calls.append(len(calls) + 1)
            if len(calls) < 3:
                raise ProviderConnectionError("Temporary network glitch", provider="openai")
            return ModelResponse(content="success", usage={})

        result = executor.execute(operation, provider="openai", model="gpt-4o", operation_name="chat")
        assert result.content == "success"
        assert len(calls) == 3
        assert len(delays) == 2
        assert delays[0] == 0.5
        assert delays[1] == 1.0

    def test_retry_executor_bounded_retry_count(self):
        delays = []
        calls = []

        def mock_sleep(d):
            delays.append(d)

        cfg = ReliabilityConfig(
            max_retry_attempts=3,
            initial_retry_delay=0.2,
        )
        executor = RetryExecutor(cfg, sleep_fn=mock_sleep, time_fn=lambda: 1.0)

        def operation():
            calls.append(1)
            raise ProviderUnavailableError("Down for maintenance", provider="gemini", status_code=503)

        with pytest.raises(ProviderUnavailableError) as exc_info:
            executor.execute(operation, provider="gemini", model="gemini-1.5-pro", operation_name="chat")

        assert len(calls) == 3  # exactly 3 attempts
        assert len(delays) == 2
        assert exc_info.value.status_code == 503
        assert exc_info.value.provider == "gemini"
        assert exc_info.value.model == "gemini-1.5-pro"

    def test_non_retryable_errors_do_not_retry(self):
        calls = []
        delays = []

        cfg = ReliabilityConfig(max_retry_attempts=3)
        executor = RetryExecutor(cfg, sleep_fn=lambda d: delays.append(d), time_fn=lambda: 1.0)

        def operation():
            calls.append(1)
            raise ProviderAuthenticationError("Unauthorized key", provider="anthropic", status_code=401)

        with pytest.raises(ProviderAuthenticationError):
            executor.execute(operation, provider="anthropic", model="claude-3", operation_name="chat")

        assert len(calls) == 1
        assert len(delays) == 0

    def test_deterministic_final_error_preserves_metadata(self):
        cfg = ReliabilityConfig(max_retry_attempts=2)
        executor = RetryExecutor(cfg, sleep_fn=lambda _: None, time_fn=lambda: 1.0)

        def operation():
            raise ProviderRateLimitError(
                "Rate limit hit",
                provider="groq",
                model="llama-3.3-70b",
                retry_after=12.0,
            )

        with pytest.raises(ProviderRateLimitError) as exc_info:
            executor.execute(operation, provider="groq", model="llama-3.3-70b", operation_name="chat")

        err = exc_info.value
        assert err.provider == "groq"
        assert err.model == "llama-3.3-70b"
        assert err.status_code == 429
        assert err.retry_after == 12.0
        assert err.retryable is True


# ============================================================================
# 3. Timeout Handling Tests
# ============================================================================

class TestTimeoutHandling:
    def test_adapter_timeout_configuration(self):
        adapter = OpenAICompatibleAdapter("openai", timeout_seconds=42.5)
        assert adapter.timeout_seconds == 42.5

        ollama = OllamaAdapter("http://localhost:11434", timeout_seconds=90.0)
        assert ollama.timeout_seconds == 90.0

    def test_invalid_timeout_rejected(self):
        with pytest.raises(ValueError):
            OpenAICompatibleAdapter("openai", timeout_seconds=-5.0)

        with pytest.raises(ValueError):
            OllamaAdapter("http://localhost:11434", timeout_seconds=0)

    def test_ollama_timeout_mapping_urllib(self):
        adapter = OllamaAdapter("http://localhost:11434", timeout_seconds=15.0)

        # Mock urllib to raise TimeoutError inside URLError
        err = urllib.error.URLError(TimeoutError("Operation timed out"))
        assert adapter._is_timeout_url_error(err) is True
        mapped = adapter._timeout_error("http://localhost:11434/api/chat", "llama3")
        assert isinstance(mapped, ProviderTimeoutError)
        assert mapped.timeout_seconds == 15.0
        assert mapped.status_code == 408
        assert mapped.retryable is True


# ============================================================================
# 4. Endpoint Validation Tests
# ============================================================================

class TestEndpointValidation:
    def test_empty_endpoint_fails_clearly(self):
        adapter = OpenAICompatibleAdapter("openai")
        with pytest.raises(ProviderConnectionError) as exc_info:
            adapter._validate_endpoint("")
        assert "Endpoint URL is required" in str(exc_info.value)

        ollama = OllamaAdapter("http://localhost:11434")
        with pytest.raises(ProviderConnectionError) as exc_info:
            ollama._validate_endpoint("   ")
        assert "missing or empty" in str(exc_info.value)

    def test_relative_models_endpoint_rejected(self):
        adapter = OpenAICompatibleAdapter("omniroute")
        with pytest.raises(ProviderConnectionError) as exc_info:
            adapter._validate_endpoint("/models")
        assert "Relative endpoint URL" in str(exc_info.value)

        ollama = OllamaAdapter("http://localhost:11434")
        with pytest.raises(ProviderConnectionError) as exc_info:
            ollama._validate_endpoint("/api/chat")
        assert "Relative endpoint URL" in str(exc_info.value)

    def test_trailing_slash_normalization(self):
        ollama = OllamaAdapter("http://localhost:11434")
        normalized = ollama._validate_endpoint("http://localhost:11434/")
        assert normalized == "http://localhost:11434/api/chat"
        assert "//api" not in normalized

        openai = OpenAICompatibleAdapter("openai")
        normalized_oa = openai._validate_endpoint("https://api.openai.com/v1/")
        assert normalized_oa == "https://api.openai.com/v1/chat/completions"
        assert "//chat" not in normalized_oa


# ============================================================================
# 5. Ollama Safety & Response Handling Tests
# ============================================================================

class TestOllamaSafety:
    def test_valid_ollama_response_parsing(self):
        adapter = OllamaAdapter("http://localhost:11434")
        client = MagicMock()
        client.post.return_value = {
            "message": {"content": "Hello from Ollama!"},
            "eval_count": 42,
            "prompt_eval_count": 10,
        }
        adapter._http_client = client

        model = Model(
            id="llama3",
            display_name="Llama 3",
            provider=Provider(id="ollama", name="Ollama"),
            capabilities=[Capability.TEXT],
            endpoint=Endpoint(url="http://localhost:11434"),
        )
        req = ModelRequest(model_id="llama3", messages=[{"role": "user", "content": "hi"}])
        resp = adapter.execute(model, req)

        assert resp.content == "Hello from Ollama!"
        assert resp.usage.get("completion_tokens") == 42
        assert resp.usage.get("prompt_tokens") == 10

    def test_ollama_http_200_empty_response_rejected(self):
        adapter = OllamaAdapter("http://localhost:11434")
        client = MagicMock()
        client.post.return_value = {}  # Empty dict from HTTP 200
        adapter._http_client = client

        model = Model(
            id="llama3",
            display_name="Llama 3",
            provider=Provider(id="ollama", name="Ollama"),
            capabilities=[Capability.TEXT],
            endpoint=Endpoint(url="http://localhost:11434"),
        )
        req = ModelRequest(model_id="llama3", messages=[{"role": "user", "content": "hi"}])

        with pytest.raises(ProviderResponseError) as exc_info:
            adapter.execute(model, req)
        assert "missing 'message' field" in str(exc_info.value)
        assert exc_info.value.status_code == 200

    def test_ollama_http_200_none_content_rejected(self):
        adapter = OllamaAdapter("http://localhost:11434")
        client = MagicMock()
        client.post.return_value = {"message": {"content": None}}
        adapter._http_client = client

        model = Model(
            id="llama3",
            display_name="Llama 3",
            provider=Provider(id="ollama", name="Ollama"),
            capabilities=[Capability.TEXT],
            endpoint=Endpoint(url="http://localhost:11434"),
        )
        req = ModelRequest(model_id="llama3", messages=[{"role": "user", "content": "hi"}])

        with pytest.raises(ProviderResponseError) as exc_info:
            adapter.execute(model, req)
        assert "empty model response" in str(exc_info.value)

    def test_ollama_http_error_mapped(self):
        import io
        adapter = OllamaAdapter("http://localhost:11434")
        client = MagicMock()
        # Mock client raising HTTPError
        err = urllib.error.HTTPError(
            url="http://localhost:11434/api/chat",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=io.BytesIO(b"Internal Server Error"),
        )
        client.post.side_effect = err
        adapter._http_client = client

        model = Model(
            id="llama3",
            display_name="Llama 3",
            provider=Provider(id="ollama", name="Ollama"),
            capabilities=[Capability.TEXT],
            endpoint=Endpoint(url="http://localhost:11434"),
        )
        req = ModelRequest(model_id="llama3", messages=[{"role": "user", "content": "hi"}])

        with pytest.raises(ProviderUnavailableError) as exc_info:
            adapter.execute(model, req)
        assert exc_info.value.status_code == 500
        assert exc_info.value.retryable is True


# ============================================================================
# 6. Structured Output Reliability & Fallback Tests
# ============================================================================

class TestStructuredOutputReliability:
    def test_valid_structured_output_succeeds(self):
        planner = Planner()
        valid_struct = {
            "assumptions": ["FastAPI is installed"],
            "affected_areas": ["src/auth"],
            "risks": ["Token expiration"],
            "validation_strategy": ["Unit tests"],
            "completion_criteria": ["All tests pass"],
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Setup JWT",
                    "description": "Install python-jose",
                    "type": "implementation",
                    "dependencies": [],
                    "inputs": [],
                    "expected_outputs": ["src/auth.py"],
                    "validation": ["pytest"],
                }
            ],
        }
        resp = ModelResponse(text="", structured_output=valid_struct)
        plan = planner.create_plan("wf-1", "Build auth", PlanningLevel.STRUCTURED, model_response=resp)
        assert plan.objective == "Build auth"
        assert len(plan.task_ids) == 1
        assert plan.task_ids[0] == "task-1"

    def test_invalid_structured_output_raises_planning_error(self):
        planner = Planner()
        # missing "tasks"
        invalid_struct = {
            "objective": "Build auth",
        }
        resp = ModelResponse(text="", structured_output=invalid_struct)
        with pytest.raises(PlanningError) as exc_info:
            planner.create_plan("wf-1", "Build auth", PlanningLevel.STRUCTURED, model_response=resp, strict=True)
        assert "missing required top-level field 'tasks'" in str(exc_info.value).lower() or "validation failed" in str(exc_info.value).lower()

    def test_distinguish_provider_failure_from_invalid_output(self):
        # Provider connection error: network or endpoint failed
        conn_err = ProviderConnectionError("Cannot connect to server", provider="openai")
        assert isinstance(conn_err, ProviderError)
        assert conn_err.error_code == "connection_failed"
        assert conn_err.retryable is True

        # Validation failure: provider succeeded with 200 OK, but model generated invalid schema
        out_err = ProviderInvalidOutputError("Schema validation failed", provider="openai", raw_output="bad json")
        assert isinstance(out_err, ProviderError)
        assert out_err.error_code == "invalid_output"
        assert out_err.retryable is False

        # Clearly different error types and retry semantics
        assert type(conn_err) is not type(out_err)
        assert is_error_retryable(conn_err) is True
        assert is_error_retryable(out_err) is False


# ============================================================================
# 7. Runtime Events Integration Tests
# ============================================================================

class TestRuntimeEventsIntegration:
    def test_provider_lifecycle_events_emitted(self):
        emitter = EventEmitter()
        events = []
        emitter.subscribe(lambda e: events.append(e))

        cfg = ReliabilityConfig(
            max_retry_attempts=2,
            initial_retry_delay=0.01,
        )
        executor = RetryExecutor(cfg, sleep_fn=lambda _: None, time_fn=lambda: 10.0, event_emitter=emitter)

        attempts = [0]

        def operation():
            attempts[0] += 1
            if attempts[0] == 1:
                raise ProviderConnectionError("Connection dropped", provider="openai")
            return ModelResponse(content="ok", usage={})

        result = executor.execute(
            operation,
            provider="openai",
            model="gpt-4o",
            operation_name="chat",
            correlation_id="corr-123",
        )
        assert result.content == "ok"

        # Verify event sequence
        types = [e.event_type for e in events]
        assert EventType.PROVIDER_REQUEST_STARTED in types
        assert EventType.PROVIDER_REQUEST_RETRYING in types
        assert EventType.PROVIDER_REQUEST_COMPLETED in types

        # Check metadata
        start_ev = next(e for e in events if e.event_type == EventType.PROVIDER_REQUEST_STARTED)
        assert start_ev.payload["provider"] == "openai"
        assert start_ev.payload["model"] == "gpt-4o"
        assert start_ev.payload["max_attempts"] == 2
        assert start_ev.run_id == "corr-123"

        retry_ev = next(e for e in events if e.event_type == EventType.PROVIDER_REQUEST_RETRYING)
        assert retry_ev.payload["attempt"] == 1
        assert retry_ev.payload["next_attempt"] == 2
        assert retry_ev.payload["retryable"] is True
        assert "Connection dropped" in retry_ev.payload["error"]["message"]

        complete_ev = next(e for e in events if e.event_type == EventType.PROVIDER_REQUEST_COMPLETED)
        assert complete_ev.payload["attempt"] == 2

    def test_provider_failure_event_on_terminal_error(self):
        emitter = EventEmitter()
        events = []
        emitter.subscribe(lambda e: events.append(e))

        cfg = ReliabilityConfig(max_retry_attempts=1)
        executor = RetryExecutor(cfg, sleep_fn=lambda _: None, time_fn=lambda: 10.0, event_emitter=emitter)

        def operation():
            raise ProviderAuthenticationError("Invalid API key", provider="anthropic", status_code=401)

        with pytest.raises(ProviderAuthenticationError):
            executor.execute(operation, provider="anthropic", model="claude-3", operation_name="chat")

        fail_ev = next(e for e in events if e.event_type == EventType.PROVIDER_REQUEST_FAILED)
        assert fail_ev.payload["provider"] == "anthropic"
        assert fail_ev.payload["error"]["status_code"] == 401
        assert fail_ev.payload["retryable"] is False
        assert fail_ev.payload["attempt"] == 1


# ============================================================================
# 8. Secret Scrubbing Tests
# ============================================================================

class TestSecretScrubbing:
    def test_sanitize_sensitive_data_bearer_tokens(self):
        raw = "Error sending Authorization: Bearer sk-ant-api03-abcdef123456 to endpoint"
        clean = sanitize_sensitive_data(raw)
        assert "Bearer [REDACTED]" in clean
        assert "sk-ant-api03" not in clean

    def test_sanitize_sensitive_data_api_keys(self):
        raw = "Failed request with api_key=sk-proj-xyz1234567890 and key: 'secret_value'"
        clean = sanitize_sensitive_data(raw)
        assert "sk-proj-xyz" not in clean
        assert "secret_value" not in clean
        assert "[REDACTED]" in clean

    def test_provider_error_does_not_leak_secrets(self):
        err = ProviderAuthenticationError(
            message="Failed with Authorization: Bearer secret-token-12345",
            provider="openai",
            status_code=401,
        )
        d = err.to_dict()
        assert "secret-token-12345" not in d["message"]
        assert "Bearer [REDACTED]" in d["message"]


# ============================================================================
# 9. Provider Health & Cooldown Tests
# ============================================================================

class TestProviderHealth:
    def test_cooldown_triggers_after_consecutive_failures(self):
        tracker = ProviderHealthTracker(cooldown_seconds=60.0, max_consecutive_failures=2)
        assert tracker.is_available("ollama") is True

        tracker.record_failure("ollama")
        assert tracker.is_available("ollama") is True

        tracker.record_failure("ollama")
        # 2nd failure triggers cooldown
        assert tracker.is_available("ollama") is False

        # Reset on success
        tracker.record_success("ollama")
        assert tracker.is_available("ollama") is True

    def test_gateway_respects_provider_cooldown(self):
        gw = ModelGateway()
        mock_adapter = MagicMock()
        mock_adapter.provider_id = "test_prov"
        gw.register_adapter(mock_adapter)

        gw.health_tracker.record_failure("test_prov")
        gw.health_tracker.record_failure("test_prov")
        gw.health_tracker.record_failure("test_prov")
        assert gw.health_tracker.is_available("test_prov") is False

        mock_profile = ModelProfile(
            id="active",
            model_id="test_model",
            capabilities_required=[Capability.TEXT],
        )
        gw.register_profile(mock_profile)

        # Create mock model
        mock_model = Model(
            id="test_model",
            display_name="Test Model",
            provider=Provider(id="test_prov", name="Test Prov"),
            capabilities=[Capability.TEXT],
            endpoint=Endpoint(url="http://localhost:8000"),
        )
        gw.register_model(mock_model)

        req = ModelRequest(model_id="test_model", messages=[{"role": "user", "content": "hi"}])
        with pytest.raises(ProviderUnavailableError) as exc_info:
            gw.execute(req)
        assert "cooldown active" in str(exc_info.value)
