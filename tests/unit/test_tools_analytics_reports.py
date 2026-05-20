"""Tests for the YouTube Analytics reports tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false
# pyright: reportImplicitStringConcatenation=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast

import pytest
from fastmcp import Context

import youtube_mcp.tools.analytics_reports as analytics_reports
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy, YouTubeScope


class FakeQuotaTracker:
    enforce: bool
    preflight_calls: list[tuple[str, int]]
    record_calls: list[tuple[str, int]]

    def __init__(self) -> None:
        self.enforce = False
        self.preflight_calls = []
        self.record_calls = []

    def would_exceed(self, account_key: str, units: int) -> bool:
        self.preflight_calls.append((account_key, units))
        return False

    def record(self, account_key: str, units: int) -> None:
        self.record_calls.append((account_key, units))


class FakeCredentials:
    scopes: list[str]

    def __init__(self, scopes: list[str]) -> None:
        self.scopes = scopes


class FakeAnalyticsRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeReportsResource:
    request: FakeAnalyticsRequest
    query_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.request = FakeAnalyticsRequest(
            {
                "columnHeaders": [
                    {"name": "day", "columnType": "DIMENSION", "dataType": "STRING"},
                    {"name": "views", "columnType": "METRIC", "dataType": "INTEGER"},
                ],
                "rows": [["2026-05-12", 10]],
            }
        )
        self.query_calls = []

    def query(self, **kwargs: object) -> FakeAnalyticsRequest:
        self.query_calls.append(dict(kwargs))
        return self.request


class FakeAnalyticsService:
    reports_resource: FakeReportsResource
    reports_calls: int

    def __init__(self) -> None:
        self.reports_resource = FakeReportsResource()
        self.reports_calls = 0

    def reports(self) -> FakeReportsResource:
        self.reports_calls += 1
        return self.reports_resource


class FakeAccountManager:
    service: FakeAnalyticsService
    _services: dict[tuple[str, str], object]
    credentials_calls: list[str]
    youtube_calls: list[str]
    analytics_calls: list[str]
    reporting_calls: list[str]
    credentials_scopes: list[str]

    def __init__(
        self,
        service: FakeAnalyticsService,
        *,
        credentials_scopes: list[str] | None = None,
    ) -> None:
        self.service = service
        self._services = {}
        self.credentials_calls = []
        self.youtube_calls = []
        self.analytics_calls = []
        self.reporting_calls = []
        self.credentials_scopes = (
            credentials_scopes
            if credentials_scopes is not None
            else [YouTubeScope.ANALYTICS_READONLY.value]
        )

    def get_credentials(self, key: str) -> object:
        self.credentials_calls.append(key)
        return FakeCredentials(self.credentials_scopes)

    def get_youtube_service(self, key: str) -> object:
        self.youtube_calls.append(key)
        return object()

    def get_analytics_service(self, key: str) -> FakeAnalyticsService:
        self.analytics_calls.append(key)
        self._services[(key, "youtubeAnalytics")] = self.service
        return self.service

    def get_reporting_service(self, key: str) -> object:
        self.reporting_calls.append(key)
        return object()


class FakeContext:
    warnings: list[str]
    log_calls: list[tuple[str, str | None]]

    def __init__(self) -> None:
        self.warnings = []
        self.log_calls = []

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def log(self, message: str, level: str | None = None) -> None:
        self.log_calls.append((message, level))


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=3,
        initial_wait=0.001,
        max_wait=0.01,
        multiplier=1.0,
        jitter=False,
    )


def _configure(
    *,
    service: FakeAnalyticsService | None = None,
    mutating_guard: Callable[[str], None] | None = None,
    credentials_scopes: list[str] | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeAnalyticsService()
    manager = FakeAccountManager(fake_service, credentials_scopes=credentials_scopes)
    tracker = FakeQuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=mutating_guard or (lambda _account: None),
            retry_policy=_retry_policy(),
        )
    )
    return manager, tracker


def test_reports_query_calls_mocked_analytics_discovery_client_with_all_params() -> None:
    manager, tracker = _configure()

    result = analytics_reports.youtube_analytics_reports_query(
        account="primary",
        ids="channel==MINE",
        metrics="views,estimatedMinutesWatched",
        start_date="2026-05-12",
        end_date="2026-05-18",
        dimensions="day",
        filters="country==US",
        max_results=25,
        sort="-views",
        start_index=2,
        currency="USD",
        include_historical_channel_data=True,
        extra_params={"futureParam": "future-value"},
    )

    assert result == {
        "columnHeaders": [
            {"name": "day", "columnType": "DIMENSION", "dataType": "STRING"},
            {"name": "views", "columnType": "METRIC", "dataType": "INTEGER"},
        ],
        "rows": [["2026-05-12", 10]],
    }
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == []
    assert manager.analytics_calls == ["primary"]
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 0)]
    assert tracker.record_calls == [("primary", 0)]
    assert manager.service.reports_calls == 1
    assert manager.service.reports_resource.query_calls == [
        {
            "ids": "channel==MINE",
            "metrics": "views,estimatedMinutesWatched",
            "startDate": "2026-05-12",
            "endDate": "2026-05-18",
            "dimensions": "day",
            "filters": "country==US",
            "maxResults": 25,
            "sort": "-views",
            "startIndex": 2,
            "currency": "USD",
            "includeHistoricalChannelData": True,
            "futureParam": "future-value",
        }
    ]
    assert manager.service.reports_resource.request.execute_calls == 1


def test_reports_query_estimated_revenue_proceeds_without_local_scope_gate() -> None:
    manager, tracker = _configure(
        credentials_scopes=[YouTubeScope.ANALYTICS_READONLY.value],
    )

    result = analytics_reports.youtube_analytics_reports_query(
        account="primary",
        ids="channel==MINE",
        metrics="estimatedRevenue",
        start_date="2026-05-12",
        end_date="2026-05-18",
        dimensions="day",
    )

    assert result == {
        "columnHeaders": [
            {"name": "day", "columnType": "DIMENSION", "dataType": "STRING"},
            {"name": "views", "columnType": "METRIC", "dataType": "INTEGER"},
        ],
        "rows": [["2026-05-12", 10]],
    }
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == []
    assert manager.analytics_calls == ["primary"]
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 0)]
    assert tracker.record_calls == [("primary", 0)]
    assert manager.service.reports_calls == 1
    assert manager.service.reports_resource.query_calls == [
        {
            "ids": "channel==MINE",
            "metrics": "estimatedRevenue",
            "startDate": "2026-05-12",
            "endDate": "2026-05-18",
            "dimensions": "day",
            "filters": None,
            "maxResults": None,
            "sort": None,
            "startIndex": None,
            "currency": None,
            "includeHistoricalChannelData": None,
        }
    ]
    assert manager.service.reports_resource.request.execute_calls == 1


def test_unknown_combo_warns_without_blocking() -> None:
    manager, tracker = _configure()
    ctx = FakeContext()

    result = analytics_reports.youtube_analytics_reports_query(
        account="primary",
        ids="channel==MINE",
        metrics="notARealMetric",
        start_date="2026-05-12",
        end_date="2026-05-18",
        dimensions="day",
        ctx=cast(Context, cast(object, ctx)),
    )

    assert result["rows"] == [["2026-05-12", 10]]
    assert ctx.warnings == [
        "WARNING: youtubeAnalytics.reports.query combination is not in the bundled channel "
        "matrix; forwarding to Google. metrics='notARealMetric', dimensions='day'"
    ]
    assert ctx.log_calls == []
    assert tracker.preflight_calls == [("primary", 0)]
    assert tracker.record_calls == [("primary", 0)]
    assert manager.service.reports_resource.request.execute_calls == 1


def test_reports_describe_returns_curated_matrix() -> None:
    manager, tracker = _configure()

    result = analytics_reports.youtube_analytics_reports_describe(account="primary")

    reports = cast(list[dict[str, object]], result["reports"])
    report_types = {report["report_type"] for report in reports}
    assert report_types == {"channel", "contentOwner"}
    sources = cast(list[str], result["sources"])
    assert "https://developers.google.com/youtube/analytics/channel_reports" in sources
    assert manager.credentials_calls == ["primary"]
    assert manager.analytics_calls == ["primary"]
    assert tracker.preflight_calls == [("primary", 0)]
    assert tracker.record_calls == [("primary", 0)]
    assert manager.service.reports_calls == 0


@pytest.mark.asyncio
async def test_analytics_reports_tools_are_registered_with_fastmcp() -> None:
    _ = _configure()

    query_signature = inspect.signature(analytics_reports.youtube_analytics_reports_query)
    describe_signature = inspect.signature(analytics_reports.youtube_analytics_reports_describe)

    assert list(query_signature.parameters) == [
        "account",
        "ids",
        "metrics",
        "start_date",
        "end_date",
        "dimensions",
        "filters",
        "max_results",
        "sort",
        "start_index",
        "currency",
        "include_historical_channel_data",
        "extra_params",
        "ctx",
    ]
    assert list(describe_signature.parameters) == ["account"]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    query_tool = registered["youtube_analytics_reports_query"]
    describe_tool = registered["youtube_analytics_reports_describe"]
    query_meta = cast(dict[str, object], query_tool.meta)
    describe_meta = cast(dict[str, object], describe_tool.meta)

    assert query_tool.parameters["required"] == [
        "account",
        "ids",
        "metrics",
        "start_date",
        "end_date",
    ]
    assert describe_tool.parameters["required"] == ["account"]
    assert "ctx" not in query_tool.parameters["properties"]
    assert query_meta["api"] == "analytics"
    assert query_meta["method"] == "youtubeAnalytics.reports.query"
    assert query_meta["scopes"] == ["https://www.googleapis.com/auth/yt-analytics.readonly"]
    assert query_meta["cost"] == 0
    assert describe_meta["api"] == "analytics"
    assert describe_meta["method"] == "youtubeAnalytics.reports.query"
    assert describe_meta["cost"] == 0
