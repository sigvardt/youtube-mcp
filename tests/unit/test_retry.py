# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUntypedFunctionDecorator=false

"""Tests for youtube_mcp.utils.retry."""

from __future__ import annotations

import json
import logging
import socket

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response, ServerNotFoundError  # type: ignore[import-untyped]

from youtube_mcp.types import RetryPolicy
from youtube_mcp.utils.retry import is_retryable_http_error, retry_with_backoff


def _http_error(status: int, reason: str, *, body_reason: str) -> HttpError:
    response = Response({"status": str(status)})
    response.reason = reason
    body = json.dumps({"error": {"errors": [{"reason": body_reason}]}}).encode("utf-8")
    return HttpError(response, body)


def _retry_policy(*, max_attempts: int = 3) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=max_attempts,
        initial_wait=0.001,
        max_wait=0.01,
        multiplier=1.0,
        jitter=False,
    )


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retryable_statuses_are_true(status: int) -> None:
    err = _http_error(status, "transient", body_reason="backendError")

    assert is_retryable_http_error(err)


@pytest.mark.parametrize("status", [400, 401, 404])
def test_client_statuses_are_false(status: int) -> None:
    err = _http_error(status, "client error", body_reason="backendError")

    assert not is_retryable_http_error(err)


def test_403_normal_reason_is_false() -> None:
    err = _http_error(403, "forbidden", body_reason="backendError")

    assert not is_retryable_http_error(err)


def test_403_quota_exceeded_is_true() -> None:
    err = _http_error(403, "forbidden", body_reason="quotaExceeded")

    assert is_retryable_http_error(err)


def test_403_daily_limit_is_false() -> None:
    err = _http_error(403, "forbidden", body_reason="dailyLimitExceeded")

    assert not is_retryable_http_error(err)


def test_quota_exceeded_content_fallback() -> None:
    err = _http_error(403, "forbidden", body_reason="quotaExceeded")
    err.error_details = ""

    assert is_retryable_http_error(err)


def test_daily_limit_content_fallback() -> None:
    err = _http_error(403, "forbidden", body_reason="dailyLimitExceeded")
    err.error_details = ""

    assert not is_retryable_http_error(err)


def test_503_retries_then_succeeds() -> None:
    policy = _retry_policy(max_attempts=4)
    attempts = 0

    @retry_with_backoff(policy)
    def fetch_value() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 4:
            raise _http_error(503, "service unavailable", body_reason="backendError")
        return "ok"

    assert fetch_value() == "ok"
    assert attempts == 4


def test_403_quota_exceeded_retries() -> None:
    policy = _retry_policy()
    attempts = 0

    @retry_with_backoff(policy)
    def fetch_value() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _http_error(403, "forbidden", body_reason="quotaExceeded")
        return "ok"

    assert fetch_value() == "ok"
    assert attempts == 3


def test_403_no_retry() -> None:
    policy = _retry_policy()
    attempts = 0

    @retry_with_backoff(policy)
    def fetch_value() -> None:
        nonlocal attempts
        attempts += 1
        raise _http_error(403, "forbidden", body_reason="backendError")

    with pytest.raises(HttpError):
        fetch_value()

    assert attempts == 1


def test_daily_limit_no_retry() -> None:
    policy = _retry_policy()
    attempts = 0

    @retry_with_backoff(policy)
    def fetch_value() -> None:
        nonlocal attempts
        attempts += 1
        raise _http_error(403, "forbidden", body_reason="dailyLimitExceeded")

    with pytest.raises(HttpError):
        fetch_value()

    assert attempts == 1


@pytest.mark.parametrize(
    "exception_factory",
    [ConnectionError, socket.timeout, ServerNotFoundError],
)
def test_network_errors_retry(exception_factory: type[BaseException]) -> None:
    policy = _retry_policy()
    attempts = 0

    @retry_with_backoff(policy)
    def fetch_value() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise exception_factory("temporary failure")
        return "ok"

    assert fetch_value() == "ok"
    assert attempts == 3


def test_stops_at_max_attempts() -> None:
    policy = _retry_policy()
    attempts = 0
    final_error = _http_error(503, "service unavailable", body_reason="backendError")

    @retry_with_backoff(policy)
    def fetch_value() -> None:
        nonlocal attempts
        attempts += 1
        raise final_error

    with pytest.raises(HttpError) as exc_info:
        fetch_value()

    assert exc_info.value is final_error
    assert attempts == policy.max_attempts


def test_logs_retries_at_warning(caplog: pytest.LogCaptureFixture) -> None:
    policy = _retry_policy()
    attempts = 0

    @retry_with_backoff(policy)
    def fetch_value() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionError("temporary failure")
        return "ok"

    with caplog.at_level(logging.WARNING, logger="youtube_mcp.retry"):
        assert fetch_value() == "ok"

    assert any(record.levelno == logging.WARNING for record in caplog.records)
