# pyright: reportMissingTypeStubs=false

"""Retry helpers for transient YouTube API failures."""

from __future__ import annotations

import json
import logging
import socket
from collections.abc import Callable, Mapping
from typing import ParamSpec, TypeVar, cast

from googleapiclient.errors import HttpError
from httplib2 import ServerNotFoundError  # type: ignore[import-untyped]
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
)
from tenacity.wait import wait_base

from youtube_mcp.types import RetryPolicy

logger = logging.getLogger("youtube_mcp.retry")

_RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
_NON_RETRYABLE_HTTP_STATUSES = {400, 401, 404}
_RETRYABLE_REASONS = {"quotaExceeded"}

P = ParamSpec("P")
R = TypeVar("R")


def _json_payload(content: bytes) -> object | None:
    try:
        return cast(object, json.loads(content.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _collect_reasons(value: object) -> set[str]:
    reasons: set[str] = set()

    if value is None:
        return reasons

    if isinstance(value, bytes):
        return _collect_reasons(value.decode("utf-8", errors="ignore"))

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return reasons
        if text in _RETRYABLE_REASONS or text == "dailyLimitExceeded":
            reasons.add(text)
            return reasons
        parsed = _json_payload(text.encode("utf-8"))
        if parsed is not None:
            reasons.update(_collect_reasons(parsed))
        return reasons

    if isinstance(value, list):
        for item in cast(list[object], value):
            reasons.update(_collect_reasons(item))
        return reasons

    if isinstance(value, dict):
        mapping = cast(Mapping[str, object], value)

        reason = mapping.get("reason")
        if isinstance(reason, str):
            reasons.add(reason)

        for key in ("error", "errors", "details", "detail", "message"):
            nested = mapping.get(key)
            if nested is not None:
                reasons.update(_collect_reasons(nested))

    return reasons


def _http_error_reasons(err: HttpError) -> set[str]:
    reasons = _collect_reasons(cast(object, err.error_details))
    payload = _json_payload(err.content)
    if payload is not None:
        reasons.update(_collect_reasons(payload))
    return reasons


def _http_status(err: HttpError) -> int | None:
    response = cast(object, err.resp)
    status = getattr(response, "status", None)
    if isinstance(status, int):
        return status
    if isinstance(status, str) and status.isdigit():
        return int(status)
    return None


def is_retryable_http_error(err: HttpError) -> bool:
    """Return True when an HttpError is safe to retry."""

    status = _http_status(err)
    reasons = _http_error_reasons(err)

    if status in _NON_RETRYABLE_HTTP_STATUSES:
        return False

    if status == 403:
        return "quotaExceeded" in reasons

    if "quotaExceeded" in reasons:
        return True

    return status in _RETRYABLE_HTTP_STATUSES


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, HttpError):
        return is_retryable_http_error(exc)

    return isinstance(exc, (ServerNotFoundError, socket.timeout, ConnectionError))


def _wait_strategy(policy: RetryPolicy) -> wait_base:
    if policy.jitter:
        return wait_random_exponential(
            multiplier=policy.multiplier,
            min=policy.initial_wait,
            max=policy.max_wait,
        )

    return wait_exponential(
        multiplier=policy.multiplier,
        min=policy.initial_wait,
        max=policy.max_wait,
    )


def retry_with_backoff(policy: RetryPolicy) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorate a callable with HTTP-aware tenacity retries."""

    retry_decorator = retry(
        retry=retry_if_exception(_is_retryable_exception),
        wait=_wait_strategy(policy),
        stop=stop_after_attempt(policy.max_attempts),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        return retry_decorator(func)

    return decorator


__all__ = ["is_retryable_http_error", "retry_with_backoff"]
