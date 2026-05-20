"""Tests for the YouTube video metadata tools."""

# pyright: reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportMissingImports=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
from typing import cast

import pytest

import youtube_mcp.tools.video_meta as video_meta
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


class FakeVideoMetaRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeVideoMetaResource:
    request: FakeVideoMetaRequest
    list_calls: list[dict[str, object]]

    def __init__(self, response: dict[str, object]) -> None:
        self.request = FakeVideoMetaRequest(response)
        self.list_calls = []

    def list(self, **kwargs: object) -> FakeVideoMetaRequest:
        self.list_calls.append(dict(kwargs))
        return self.request


class FakeYouTubeService:
    video_categories_resource: FakeVideoMetaResource
    video_abuse_report_reasons_resource: FakeVideoMetaResource
    video_categories_calls: int
    video_abuse_report_reasons_calls: int

    def __init__(self) -> None:
        self.video_categories_resource = FakeVideoMetaResource(
            {"items": [{"id": "22", "snippet": {"title": "People & Blogs"}}]}
        )
        self.video_abuse_report_reasons_resource = FakeVideoMetaResource(
            {"items": [{"id": "V", "snippet": {"label": "Violence"}}]}
        )
        self.video_categories_calls = 0
        self.video_abuse_report_reasons_calls = 0

    def videoCategories(self) -> FakeVideoMetaResource:
        self.video_categories_calls += 1
        return self.video_categories_resource

    def videoAbuseReportReasons(self) -> FakeVideoMetaResource:
        self.video_abuse_report_reasons_calls += 1
        return self.video_abuse_report_reasons_resource


class FakeAccountManager:
    service: FakeYouTubeService
    _services: dict[tuple[str, str], object]
    credentials_calls: list[str]
    youtube_calls: list[str]

    def __init__(self, service: FakeYouTubeService) -> None:
        self.service = service
        self._services = {}
        self.credentials_calls = []
        self.youtube_calls = []

    def get_credentials(self, key: str) -> object:
        self.credentials_calls.append(key)
        return object()

    def get_youtube_service(self, key: str) -> object:
        cache_key = (key, "youtube")
        cached_service = self._services.get(cache_key)
        if cached_service is not None:
            return cached_service

        self.youtube_calls.append(key)
        self._services[cache_key] = self.service
        return self.service

    def get_analytics_service(self, key: str) -> object:
        _ = key
        return object()

    def get_reporting_service(self, key: str) -> object:
        _ = key
        return object()


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=3,
        initial_wait=0.001,
        max_wait=0.01,
        multiplier=1.0,
        jitter=False,
    )


def _configure(
    service: FakeYouTubeService | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeYouTubeService()
    manager = FakeAccountManager(fake_service)
    tracker = FakeQuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=lambda _account: None,
            retry_policy=_retry_policy(),
        )
    )
    return manager, tracker


def test_video_meta_tools_cache_hits_and_misses() -> None:
    manager, tracker = _configure()
    account = "video-meta-cache"

    categories_first = video_meta.youtube_videoCategories_list(
        account=account,
        hl="en",
        region_code="US",
    )
    categories_second = video_meta.youtube_videoCategories_list(
        account=account,
        hl="en",
        region_code="US",
    )
    categories_miss = video_meta.youtube_videoCategories_list(
        account=account,
        hl="en",
        region_code="CA",
    )
    reasons_first = video_meta.youtube_videoAbuseReportReasons_list(account=account, hl="en")
    reasons_second = video_meta.youtube_videoAbuseReportReasons_list(account=account, hl="en")

    assert categories_first == {"items": [{"id": "22", "snippet": {"title": "People & Blogs"}}]}
    assert categories_second == categories_first
    assert categories_miss == categories_first
    assert reasons_first == {"items": [{"id": "V", "snippet": {"label": "Violence"}}]}
    assert reasons_second == reasons_first
    assert manager.credentials_calls == [account, account, account, account, account]
    assert manager.youtube_calls == [account]
    expected_quota_calls = [(account, 1)] * 5
    assert tracker.preflight_calls == expected_quota_calls
    assert tracker.record_calls == expected_quota_calls
    assert manager.service.video_categories_calls == 2
    assert manager.service.video_abuse_report_reasons_calls == 1
    assert manager.service.video_categories_resource.list_calls == [
        {"part": "snippet", "hl": "en", "id": None, "regionCode": "US"},
        {"part": "snippet", "hl": "en", "id": None, "regionCode": "CA"},
    ]
    assert manager.service.video_abuse_report_reasons_resource.list_calls == [
        {"part": "snippet", "hl": "en"}
    ]
    assert manager.service.video_categories_resource.request.execute_calls == 2
    assert manager.service.video_abuse_report_reasons_resource.request.execute_calls == 1


@pytest.mark.asyncio
async def test_video_meta_tools_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(video_meta.youtube_videoCategories_list).parameters) == [
        "account",
        "part",
        "hl",
        "id",
        "region_code",
        "ctx",
    ]
    assert list(inspect.signature(video_meta.youtube_videoAbuseReportReasons_list).parameters) == [
        "account",
        "part",
        "hl",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert "youtube_videoCategories_list" in registered
    assert "youtube_videoAbuseReportReasons_list" in registered
    assert registered["youtube_videoCategories_list"].parameters["required"] == ["account"]
    assert registered["youtube_videoAbuseReportReasons_list"].parameters["required"] == ["account"]

    categories_meta = cast(dict[str, object], registered["youtube_videoCategories_list"].meta)
    reasons_meta = cast(dict[str, object], registered["youtube_videoAbuseReportReasons_list"].meta)
    assert categories_meta["method"] == "youtube.videoCategories.list"
    assert categories_meta["scopes"] == [YouTubeScope.READONLY.value]
    assert categories_meta["cost"] == 1
    assert reasons_meta["method"] == "youtube.videoAbuseReportReasons.list"
    assert reasons_meta["scopes"] == [YouTubeScope.FORCE_SSL.value]
    assert reasons_meta["cost"] == 1
