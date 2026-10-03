"""Structured Provider Error Hierarchy for ClaireCoder Gateway.

Correction #22: Provider Reliability.

This module provides normalized, structured errors for all provider and model execution
failures, ensuring callers never have to parse provider-specific exception payloads or
risk exposing sensitive credentials.
"""
from enum import Enum
import re
from typing import Any, Dict, Optional

from clairecoder.gateway.types import ErrorCategory, ModelError


# Regex patterns for scrubbing sensitive tokens, keys, and authorization headers
_RE_BEARER_AUTH = re.compile(r"(Authorization\s*[:=]\s*Bearer\s+)\S+", re.IGNORECASE)
_RE_AUTH_HEADER = re.compile(r"((?:x-api-key|authorization)\s*[:=]\s*['\"]?)(?!Bearer\b|\[REDACTED\])[^\s'\",;]+(['\"]?)", re.IGNORECASE)
_RE_BEARER = re.compile(r"(\bBearer\s+)(?!\[REDACTED\])[^\s'\",;]+", re.IGNORECASE)
_RE_TOKEN_KEYVAL = re.compile(r"((?:api[_-]?key|auth[_-]?token|secret(?:[_-]?key)?|password)\s*[:=]\s*['\"]?)(?!\[REDACTED\])[^\s'\",;]+(['\"]?)", re.IGNORECASE)
_RE_KEY_PAIR = re.compile(r"(\bkey\s*[:=]\s*['\"]?)(?!\[REDACTED\])[^\s'\",;]+(['\"]?)", re.IGNORECASE)
_RE_API_KEY_QUERY = re.compile(r"([?&]key=)(?!\[REDACTED\])[^&\s]+", re.IGNORECASE)


def sanitize_sensitive_data(text: Optional[str]) -> str:
    """Sanitize secrets, auth tokens, and API keys from error messages and logs."""
    if not text:
        return ""
    s = str(text)
    s = _RE_BEARER_AUTH.sub(r"\1[REDACTED]", s)
    s = _RE_AUTH_HEADER.sub(r"\1[REDACTED]\2", s)
    s = _RE_BEARER.sub(r"\1[REDACTED]", s)
    s = _RE_TOKEN_KEYVAL.sub(r"\1[REDACTED]\2", s)
    s = _RE_KEY_PAIR.sub(r"\1[REDACTED]\2", s)
    s = _RE_API_KEY_QUERY.sub(r"\1[REDACTED]", s)
    return s


class ProviderError(ModelError):
    """Base exception for all normalized provider and model gateway errors.
    
    Inherits from ModelError to preserve backward compatibility across all
    existing subsystems and test suites.
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        operation: Optional[str] = "execute",
        retryable: bool = False,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        retry_after: Optional[float] = None,
        category: Any = ErrorCategory.UNKNOWN,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        sanitized_msg = sanitize_sensitive_data(message)
        super().__init__(
            category=category,
            message=sanitized_msg,
            provider_id=provider,
            model_id=model,
            is_recoverable=retryable,
            provider_specific=details or {},
        )
        self.message = sanitized_msg
        self.provider = provider
        self.model = model
        self.operation = operation
        self.retryable = retryable
        self.status_code = status_code
        self.error_code = error_code or "provider_error"
        self.retry_after = retry_after
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to a safe serializable dictionary without secrets."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "provider": self.provider,
            "model": self.model,
            "operation": self.operation,
            "retryable": self.retryable,
            "status_code": self.status_code,
            "retry_after": self.retry_after,
        }

    def __str__(self) -> str:
        parts = [f"[{self.error_code}] {self.message}"]
        if self.provider:
            parts.append(f"(provider: {self.provider})")
        if self.model:
            parts.append(f"(model: {self.model})")
        if self.status_code:
            parts.append(f"(status: {self.status_code})")
        return " ".join(parts)


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request times out during connection, read, or stream."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        operation: Optional[str] = "execute",
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        merged_details = dict(details or {})
        if timeout_seconds is not None:
            merged_details["timeout_seconds"] = timeout_seconds
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            operation=operation,
            retryable=True,
            status_code=408,
            error_code="timeout",
            category=ErrorCategory.TIMEOUT,
            details=merged_details,
        )
        self.timeout_seconds = timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["timeout_seconds"] = self.timeout_seconds
        return d

    def __str__(self) -> str:
        base = super().__str__()
        if self.timeout_seconds is not None:
            return f"{base} (timeout: {self.timeout_seconds:g}s)"
        return base


class ProviderConnectionError(ProviderError):
    """Raised when unable to connect, resolve DNS, or establish a socket connection."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        operation: Optional[str] = "execute",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            operation=operation,
            retryable=True,
            error_code="connection_failed",
            category=ErrorCategory.NETWORK_FAILURE,
            details=details,
        )


class ProviderRateLimitError(ProviderError):
    """Raised when a provider rejects requests due to quota or concurrency limits (HTTP 429)."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        operation: Optional[str] = "execute",
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            operation=operation,
            retryable=True,
            status_code=429,
            error_code="rate_limit",
            retry_after=retry_after,
            category=ErrorCategory.RATE_LIMITING,
            details=details,
        )


class ProviderAuthenticationError(ProviderError):
    """Raised when API credentials are missing, expired, or rejected (HTTP 401, 403)."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        operation: Optional[str] = "execute",
        status_code: int = 401,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            operation=operation,
            retryable=False,
            status_code=status_code,
            error_code="authentication_failed",
            category=ErrorCategory.AUTHENTICATION,
            details=details,
        )


class ProviderUnavailableError(ProviderError):
    """Raised when a provider is down, overloaded, or in cooldown (HTTP 503, 529, cooldown)."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        operation: Optional[str] = "execute",
        status_code: int = 503,
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            operation=operation,
            retryable=True,
            status_code=status_code,
            error_code="unavailable",
            retry_after=retry_after,
            category=ErrorCategory.ENDPOINT_FAILURE,
            details=details,
        )


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an unexpected HTTP error code or malformed body."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        operation: Optional[str] = "execute",
        status_code: Optional[int] = None,
        retryable: Optional[bool] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        # 5xx errors are typically retryable; 4xx errors are not (unless 429 handled separately)
        is_retryable = retryable if retryable is not None else (status_code is not None and status_code >= 500)
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            operation=operation,
            retryable=is_retryable,
            status_code=status_code,
            error_code="response_error",
            category=ErrorCategory.ENDPOINT_FAILURE,
            details=details,
        )


class ProviderInvalidOutputError(ProviderError):
    """Raised when a provider response is received with 200 OK but its content is invalid or missing."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        operation: Optional[str] = "execute",
        raw_output: Optional[str] = None,
        category: Any = ErrorCategory.ENDPOINT_FAILURE,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        merged_details = dict(details or {})
        if raw_output:
            merged_details["raw_output_snippet"] = sanitize_sensitive_data(raw_output[:200])
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            operation=operation,
            retryable=False,
            error_code="invalid_output",
            category=category,
            details=merged_details,
        )
        self.raw_output = raw_output
