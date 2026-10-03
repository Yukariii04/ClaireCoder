"""Provider reliability policies, retry orchestration, and health tracking.

Correction #22: Provider Reliability.
"""
from dataclasses import dataclass, field
import logging
import math
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar

from clairecoder.gateway.errors import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderError,
    ProviderInvalidOutputError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    sanitize_sensitive_data,
)

logger = logging.getLogger("clairecoder.gateway.reliability")

T = TypeVar("T")


@dataclass
class ReliabilityConfig:
    """Configurable settings for provider request reliability, retries, and timeouts."""
    request_timeout: float = 60.0
    max_retry_attempts: int = 3
    initial_retry_delay: float = 1.0
    max_retry_delay: float = 30.0
    backoff_factor: float = 2.0
    enable_cooldown: bool = True
    cooldown_seconds: float = 30.0
    failure_threshold_for_cooldown: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_timeout": self.request_timeout,
            "max_retry_attempts": self.max_retry_attempts,
            "initial_retry_delay": self.initial_retry_delay,
            "max_retry_delay": self.max_retry_delay,
            "backoff_factor": self.backoff_factor,
            "enable_cooldown": self.enable_cooldown,
            "cooldown_seconds": self.cooldown_seconds,
            "failure_threshold_for_cooldown": self.failure_threshold_for_cooldown,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReliabilityConfig":
        if not isinstance(data, dict):
            return cls()
        return cls(
            request_timeout=float(data.get("request_timeout", 60.0)),
            max_retry_attempts=max(1, int(data.get("max_retry_attempts", 3))),
            initial_retry_delay=max(0.0, float(data.get("initial_retry_delay", 1.0))),
            max_retry_delay=max(0.0, float(data.get("max_retry_delay", 30.0))),
            backoff_factor=max(1.0, float(data.get("backoff_factor", 2.0))),
            enable_cooldown=bool(data.get("enable_cooldown", True)),
            cooldown_seconds=max(0.0, float(data.get("cooldown_seconds", 30.0))),
            failure_threshold_for_cooldown=max(1, int(data.get("failure_threshold_for_cooldown", 3))),
        )


def calculate_backoff_delay(
    attempt: int,
    config: ReliabilityConfig,
    retry_after: Optional[float] = None,
) -> float:
    """Calculate the backoff delay for a retry attempt.
    
    If retry_after is provided and positive, it takes precedence (bounded by max_retry_delay).
    Otherwise, applies exponential backoff: initial_delay * (backoff_factor ** (attempt - 1)).
    """
    if retry_after is not None and retry_after > 0:
        return min(float(retry_after), config.max_retry_delay)

    # attempt 1 failed -> retry 1 uses attempt_index 0: initial_delay * (backoff ** 0)
    attempt_index = max(0, attempt - 1)
    delay = config.initial_retry_delay * math.pow(config.backoff_factor, attempt_index)
    return min(delay, config.max_retry_delay)


def is_error_retryable(error: Exception) -> bool:
    """Determine whether an error is transient and safe to retry automatically."""
    if isinstance(error, (ProviderAuthenticationError, ProviderInvalidOutputError)):
        return False
    if isinstance(error, (ProviderTimeoutError, ProviderConnectionError, ProviderRateLimitError, ProviderUnavailableError)):
        return True
    if isinstance(error, ProviderResponseError):
        # 5xx responses or explicit retryable flag
        return bool(error.retryable)
    if isinstance(error, ProviderError):
        return bool(error.retryable)
    return False


class ProviderHealthTracker:
    """Lightweight in-memory provider health and cooldown state.
    
    Prevents repeatedly hammering external endpoints that are clearly down
    without introducing complex distributed circuit breakers.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        max_consecutive_failures: Optional[int] = None,
        time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self.failure_threshold = max_consecutive_failures if max_consecutive_failures is not None else failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._time_fn = time_fn or time.time
        self._consecutive_failures: Dict[str, int] = {}
        self._cooldown_until: Dict[str, float] = {}

    def is_available(self, provider_id: str) -> bool:
        """Check if provider is currently outside of its cooldown window."""
        until = self._cooldown_until.get(provider_id, 0.0)
        return self._time_fn() >= until

    def get_remaining_cooldown(self, provider_id: str) -> float:
        """Return the remaining cooldown in seconds (or 0.0 if available)."""
        until = self._cooldown_until.get(provider_id, 0.0)
        now = self._time_fn()
        return max(0.0, until - now)

    def record_failure(self, provider_id: str, is_hard_failure: bool = False) -> None:
        """Record an execution failure against the provider."""
        count = self._consecutive_failures.get(provider_id, 0) + 1
        self._consecutive_failures[provider_id] = count
        if is_hard_failure or count >= self.failure_threshold:
            now = self._time_fn()
            self._cooldown_until[provider_id] = now + self.cooldown_seconds

    def record_success(self, provider_id: str) -> None:
        """Record a successful execution, resetting failure counts and cooldown."""
        self._consecutive_failures[provider_id] = 0
        self._cooldown_until.pop(provider_id, None)

    def reset(self, provider_id: Optional[str] = None) -> None:
        """Reset tracking state for a specific provider or all providers."""
        if provider_id:
            self._consecutive_failures.pop(provider_id, None)
            self._cooldown_until.pop(provider_id, None)
        else:
            self._consecutive_failures.clear()
            self._cooldown_until.clear()


class RetryExecutor:
    """Orchestrates bounded retry execution with exponential backoff and event emission."""

    def __init__(
        self,
        config: Optional[ReliabilityConfig] = None,
        health_tracker: Optional[ProviderHealthTracker] = None,
        event_emitter: Optional[Any] = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
        time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self.config = config or ReliabilityConfig()
        self.health_tracker = health_tracker or ProviderHealthTracker(
            failure_threshold=self.config.failure_threshold_for_cooldown,
            cooldown_seconds=self.config.cooldown_seconds,
            time_fn=time_fn,
        )
        self.event_emitter = event_emitter
        self._sleep_fn = sleep_fn or time.sleep
        self._time_fn = time_fn or time.time
        self.recorded_delays: List[float] = []

    def _emit(self, event_type_val: Any, payload: Dict[str, Any], correlation_id: Optional[str] = None) -> None:
        """Emit a RuntimeEvent if an event emitter is configured."""
        if not self.event_emitter:
            return
        try:
            from clairecoder.runtime.events import EventType, RuntimeEvent
            etype = EventType(event_type_val) if isinstance(event_type_val, str) else event_type_val
            event = RuntimeEvent(
                event_type=etype,
                run_id=correlation_id,
                payload=payload,
            )
            self.event_emitter.emit(event)
        except Exception as e:
            logger.debug("Failed emitting provider event %s: %s", event_type_val, e)

    def execute(
        self,
        func: Callable[[], T],
        provider: str = "",
        model: str = "",
        operation_name: str = "chat",
        correlation_id: Optional[str] = None,
    ) -> T:
        """Convenience alias for execute_with_retry."""
        return self.execute_with_retry(
            provider_id=provider,
            model_id=model,
            operation=operation_name,
            func=func,
            correlation_id=correlation_id,
        )

    def execute_with_retry(
        self,
        provider_id: str,
        model_id: str,
        operation: str,
        func: Callable[[], T],
        correlation_id: Optional[str] = None,
    ) -> T:
        """Execute a provider call with bounded retry handling and health checks."""
        # 1. Check provider availability / cooldown
        if self.config.enable_cooldown and not self.health_tracker.is_available(provider_id):
            remaining = self.health_tracker.get_remaining_cooldown(provider_id)
            err = ProviderUnavailableError(
                message=f"Provider '{provider_id}' is temporarily unavailable (cooldown active: {remaining:.1f}s remaining)",
                provider=provider_id,
                model=model_id,
                operation=operation,
                retry_after=remaining,
            )
            self._emit(
                "provider.request.failed",
                {
                    "provider": provider_id,
                    "model": model_id,
                    "operation": operation,
                    "attempt": 0,
                    "retryable": True,
                    "error": err.to_dict(),
                    "duration": 0.0,
                },
                correlation_id=correlation_id,
            )
            raise err

        max_attempts = self.config.max_retry_attempts
        start_time = self._time_fn()

        # Emit PROVIDER_REQUEST_STARTED
        self._emit(
            "provider.request.started",
            {
                "provider": provider_id,
                "model": model_id,
                "operation": operation,
                "max_attempts": max_attempts,
            },
            correlation_id=correlation_id,
        )

        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            attempt_start = self._time_fn()
            try:
                result = func()
                duration = self._time_fn() - attempt_start
                total_duration = self._time_fn() - start_time

                # Success: update health tracker & latency
                self.health_tracker.record_success(provider_id)
                if hasattr(result, "latency") and getattr(result, "latency") is None:
                    try:
                        setattr(result, "latency", duration)
                    except Exception:
                        pass
                if hasattr(result, "provider") and not getattr(result, "provider"):
                    try:
                        setattr(result, "provider", provider_id)
                    except Exception:
                        pass
                if hasattr(result, "model") and not getattr(result, "model"):
                    try:
                        setattr(result, "model", model_id)
                    except Exception:
                        pass

                self._emit(
                    "provider.request.completed",
                    {
                        "provider": provider_id,
                        "model": model_id,
                        "operation": operation,
                        "attempt": attempt,
                        "duration": duration,
                        "total_duration": total_duration,
                    },
                    correlation_id=correlation_id,
                )
                return result

            except Exception as e:
                duration = self._time_fn() - attempt_start
                last_error = e

                # Enrich error with model and provider if not already set
                if hasattr(e, "model") and getattr(e, "model") is None and model_id:
                    try:
                        e.model = model_id
                    except Exception:
                        pass
                if hasattr(e, "provider") and getattr(e, "provider") is None and provider_id:
                    try:
                        e.provider = provider_id
                    except Exception:
                        pass

                # Determine retryable status
                retryable = is_error_retryable(e)
                status_code = getattr(e, "status_code", None)
                retry_after = getattr(e, "retry_after", None)

                # Check if we should retry
                can_retry = retryable and (attempt < max_attempts)

                if can_retry:
                    delay = calculate_backoff_delay(attempt, self.config, retry_after=retry_after)
                    self.recorded_delays.append(delay)

                    logger.info(
                        "Provider %s (%s) attempt %d/%d failed with %s; retrying in %.2fs (status: %s)",
                        provider_id, model_id, attempt, max_attempts, e.__class__.__name__, delay, status_code,
                    )

                    self._emit(
                        "provider.request.retrying",
                        {
                            "provider": provider_id,
                            "model": model_id,
                            "operation": operation,
                            "attempt": attempt,
                            "next_attempt": attempt + 1,
                            "delay": delay,
                            "retryable": True,
                            "error": getattr(e, "to_dict", lambda: {"message": sanitize_sensitive_data(str(e))})(),
                            "duration": duration,
                        },
                        correlation_id=correlation_id,
                    )

                    self._sleep_fn(delay)
                    continue

                # Not retrying: mark health tracker if retryable exhausted or hard failure
                if self.config.enable_cooldown:
                    is_hard = isinstance(e, (ProviderConnectionError, ProviderUnavailableError))
                    self.health_tracker.record_failure(provider_id, is_hard_failure=is_hard)

                total_duration = self._time_fn() - start_time
                self._emit(
                    "provider.request.failed",
                    {
                        "provider": provider_id,
                        "model": model_id,
                        "operation": operation,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "retryable": retryable,
                        "error": getattr(e, "to_dict", lambda: {"message": sanitize_sensitive_data(str(e))})(),
                        "duration": duration,
                        "total_duration": total_duration,
                    },
                    correlation_id=correlation_id,
                )
                raise e

        # If loop terminated without returning or raising
        if last_error:
            raise last_error
        raise ProviderError("Execution ended without response", provider=provider_id, model=model_id)
