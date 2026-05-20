"""Tests for the YouTube tool registration framework."""
# pyright: reportImplicitOverride=false, reportMissingTypeStubs=false, reportUnusedCallResult=false

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from typing import cast

import pytest
from fastmcp import Context
from googleapiclient.errors import HttpError
from httplib2 import Response  # type: ignore[import-untyped]

from youtube_mcp.tools._framework import (
    FrameworkContext,
    QuotaExhaustedError,
    ToolRegistrationError,
    configure_framework,
    youtube_tool,
)
from youtube_mcp.types import RetryPolicy, YouTubeScope


class FakeQuotaTracker:
    def __init__(self, *, enforce: bool = False, would_exceed: bool = False) -> None:
        self.enforce: bool = enforce
        self._would_exceed: bool = would_exceed
        self.preflight_calls: list[tuple[str, int]] = []
        self.record_calls: list[tuple[str, int]] = []

    def would_exceed(self, account_key: str, units: int) -> bool:
        self.preflight_calls.append((account_key, units))
        return self._would_exceed

    def record(self, account_key: str, units: int) -> None:
        self.record_calls.append((account_key, units))


class FakeAccountManager:
    def __init__(self) -> None:
        self.credentials_calls: list[str] = []
        self.youtube_calls: list[str] = []
        self.analytics_calls: list[str] = []
        self.reporting_calls: list[str] = []

    def get_credentials(self, key: str) -> object:
        self.credentials_calls.append(key)
        return object()

    def get_youtube_service(self, key: str) -> object:
        self.youtube_calls.append(key)
        return object()

    def get_analytics_service(self, key: str) -> object:
        self.analytics_calls.append(key)
        return object()

    def get_reporting_service(self, key: str) -> object:
        self.reporting_calls.append(key)
        return object()


class FakeContext:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def _retry_policy(max_attempts: int = 3) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=max_attempts,
        initial_wait=0.001,
        max_wait=0.01,
        multiplier=1.0,
        jitter=False,
    )


def _configure(
    *,
    quota: FakeQuotaTracker | None = None,
    account_manager: FakeAccountManager | None = None,
    mutating_guard: Callable[[str], None] | None = None,
    retry_policy: RetryPolicy | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    manager = account_manager or FakeAccountManager()
    tracker = quota or FakeQuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=mutating_guard or (lambda _account: None),
            retry_policy=retry_policy or _retry_policy(),
        )
    )
    return manager, tracker


def _http_error(status: int, body_reason: str, message: str = "request failed") -> HttpError:
    response = Response({"status": str(status)})
    response.reason = "HTTP Error"
    body = json.dumps(
        {"error": {"errors": [{"reason": body_reason}], "message": message}}
    ).encode("utf-8")
    return HttpError(response, body)


def test_full_pipeline() -> None:
    manager, tracker = _configure()
    calls: list[tuple[str, str | None, object | None]] = []

    @youtube_tool(
        name="youtube_framework_full_pipeline",
        api="youtube",
        method="youtube.videos.list",
        scopes=[YouTubeScope.READONLY],
    )
    def framework_tool(
        account: str, video_id: str | None = None, ctx: Context | None = None
    ) -> dict[str, object]:
        calls.append((account, video_id, ctx))
        return {"items": [{"id": video_id}]}

    result = framework_tool(account="primary", video_id="abc123")

    assert result == {"items": [{"id": "abc123"}]}
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert manager.analytics_calls == []
    assert tracker.preflight_calls == [("primary", 1)]
    assert tracker.record_calls == [("primary", 1)]
    assert calls == [("primary", "abc123", None)]


def test_empty_no_content_result_normalizes_to_empty_dict() -> None:
    _, tracker = _configure()

    @youtube_tool(
        name="youtube_framework_empty_no_content",
        api="youtube",
        method="youtube.comments.delete",
        scopes=[YouTubeScope.FORCE_SSL],
        mutating=True,
    )
    def framework_tool(account: str) -> dict[str, object]:
        _ = account
        return cast(dict[str, object], cast(object, ""))

    assert framework_tool(account="primary") == {}
    assert tracker.record_calls == [("primary", 50)]


def test_none_no_content_result_normalizes_to_empty_dict() -> None:
    _, tracker = _configure()

    @youtube_tool(
        name="youtube_framework_none_no_content",
        api="youtube",
        method="youtube.watermarks.unset",
        scopes=[YouTubeScope.FORCE_SSL],
        mutating=True,
    )
    def framework_tool(account: str) -> dict[str, object]:
        _ = account
        return cast(dict[str, object], cast(object, None))

    assert framework_tool(account="primary") == {}
    assert tracker.record_calls == [("primary", 50)]


def test_forbidden_video_deletion_method_blocked() -> None:
    forbidden_action = "delete"

    with pytest.raises(ToolRegistrationError):
        _ = youtube_tool(
            name="youtube_framework_blocked_delete",
            api="youtube",
            method=f"youtube.videos.{forbidden_action}",
            scopes=[YouTubeScope.MANAGE],
        )


def test_http_error_mapping_and_non_retryable_403() -> None:
    _, tracker = _configure(retry_policy=_retry_policy(max_attempts=3))
    attempts = 0

    @youtube_tool(
        name="youtube_framework_http_error",
        api="youtube",
        method="youtube.videos.list",
        scopes=[YouTubeScope.READONLY],
    )
    def framework_tool(account: str) -> dict[str, object]:
        _ = account
        nonlocal attempts
        attempts += 1
        raise _http_error(403, "forbidden", "token ya29.secret-value rejected")

    result = framework_tool(account="primary")

    assert result == {
        "error": {
            "status": 403,
            "reason": "forbidden",
            "message": "token [redacted] rejected",
        }
    }
    assert attempts == 1
    assert tracker.record_calls == []


def test_retryable_500_retries_then_records_quota() -> None:
    _, tracker = _configure(retry_policy=_retry_policy(max_attempts=3))
    attempts = 0

    @youtube_tool(
        name="youtube_framework_retry_500",
        api="youtube",
        method="youtube.videos.list",
        scopes=[YouTubeScope.READONLY],
    )
    def framework_tool(account: str) -> dict[str, str]:
        _ = account
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _http_error(500, "backendError")
        return {"status": "ok"}

    assert framework_tool(account="primary") == {"status": "ok"}
    assert attempts == 3
    assert tracker.record_calls == [("primary", 1)]


def test_quota_preflight_enforced_raises_before_api_call() -> None:
    manager, tracker = _configure(quota=FakeQuotaTracker(enforce=True, would_exceed=True))
    calls = 0

    @youtube_tool(
        name="youtube_framework_quota_enforced",
        api="youtube",
        method="youtube.search.list",
        scopes=[YouTubeScope.READONLY],
    )
    def framework_tool(account: str) -> dict[str, object]:
        _ = account
        nonlocal calls
        calls += 1
        return {}

    with pytest.raises(QuotaExhaustedError):
        framework_tool(account="primary")

    assert calls == 0
    assert manager.youtube_calls == []
    assert tracker.preflight_calls == [("primary", 100)]
    assert tracker.record_calls == []


def test_quota_preflight_warns_when_not_enforced() -> None:
    _, tracker = _configure(quota=FakeQuotaTracker(would_exceed=True))
    ctx = FakeContext()

    @youtube_tool(
        name="youtube_framework_quota_warn",
        api="youtube",
        method="youtube.search.list",
        scopes=[YouTubeScope.READONLY],
    )
    def framework_tool(account: str, ctx: Context | None = None) -> dict[str, bool]:
        _ = (account, ctx)
        return {"ok": True}

    assert framework_tool(account="primary", ctx=cast(Context, cast(object, ctx))) == {"ok": True}
    assert tracker.record_calls == [("primary", 100)]
    warning_message = (
        "WARNING: quota cost 100 for account primary would exceed daily limit; continuing because "
        "quota enforcement is disabled"
    )
    assert ctx.warnings == [warning_message]


def test_mutating_guard_runs_before_service_and_call() -> None:
    events: list[str] = []

    class EventAccountManager(FakeAccountManager):
        def get_credentials(self, key: str) -> object:
            events.append(f"credentials:{key}")
            return super().get_credentials(key)

        def get_youtube_service(self, key: str) -> object:
            events.append(f"service:{key}")
            return super().get_youtube_service(key)

    def guard(account: str) -> None:
        events.append(f"guard:{account}")

    _ = _configure(account_manager=EventAccountManager(), mutating_guard=guard)

    @youtube_tool(
        name="youtube_framework_mutating_guard",
        api="youtube",
        method="youtube.comments.insert",
        scopes=[YouTubeScope.FORCE_SSL],
        mutating=True,
    )
    def framework_tool(account: str) -> dict[str, bool]:
        events.append(f"call:{account}")
        return {"ok": True}

    assert framework_tool(account="primary") == {"ok": True}
    assert events == ["credentials:primary", "guard:primary", "service:primary", "call:primary"]


def test_api_selects_analytics_and_reporting_services() -> None:
    manager, _ = _configure()

    @youtube_tool(
        name="analytics_framework_reports_query",
        api="analytics",
        method="youtubeAnalytics.reports.query",
        scopes=[YouTubeScope.ANALYTICS_READONLY],
    )
    def analytics_tool(account: str) -> dict[str, bool]:
        _ = account
        return {"ok": True}

    @youtube_tool(
        name="reporting_framework_jobs_create",
        api="reporting",
        method="youtubeReporting.jobs.create",
        scopes=[YouTubeScope.REPORTING],
    )
    def reporting_tool(account: str) -> dict[str, bool]:
        _ = account
        return {"ok": True}

    assert analytics_tool(account="primary") == {"ok": True}
    assert reporting_tool(account="secondary") == {"ok": True}
    assert manager.analytics_calls == ["primary"]
    assert manager.reporting_calls == ["secondary"]


@pytest.mark.asyncio
async def test_fastmcp_registration_preserves_signature_and_tags() -> None:
    _ = _configure()

    @youtube_tool(
        name="youtube_framework_registered_schema",
        api="youtube",
        method="youtube.comments.insert",
        scopes=[YouTubeScope.FORCE_SSL],
        mutating=True,
    )
    def framework_tool(account: str, text: str, ctx: Context | None = None) -> dict[str, str]:
        _ = (account, ctx)
        return {"text": text}

    assert list(inspect.signature(framework_tool).parameters) == ["account", "text", "ctx"]

    from youtube_mcp.server import mcp

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    tool = registered["youtube_framework_registered_schema"]

    assert tool.tags == {"mutating"}
    assert tool.parameters["required"] == ["account", "text"]
    assert "ctx" not in tool.parameters["properties"]
