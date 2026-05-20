"""Tests for the YouTube search tool."""

# pyright: reportImplicitOverride=false, reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnannotatedClassAttribute=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast

import pytest
from fastmcp import Context

import youtube_mcp.tools.search as search
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy


class FakeQuotaState:
    units_used_today: int
    daily_limit: int

    def __init__(self, units_used_today: int = 2_500, daily_limit: int = 10_000) -> None:
        self.units_used_today = units_used_today
        self.daily_limit = daily_limit


class FakeQuotaTracker:
    enforce: bool
    preflight_calls: list[tuple[str, int]]
    record_calls: list[tuple[str, int]]
    current_calls: list[str]

    def __init__(self) -> None:
        self.enforce = False
        self.preflight_calls = []
        self.record_calls = []
        self.current_calls = []

    def would_exceed(self, account_key: str, units: int) -> bool:
        self.preflight_calls.append((account_key, units))
        return False

    def record(self, account_key: str, units: int) -> None:
        self.record_calls.append((account_key, units))

    def current(self, account_key: str) -> FakeQuotaState:
        self.current_calls.append(account_key)
        return FakeQuotaState()


class FakeSearchRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeSearchResource:
    request: FakeSearchRequest
    list_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.request = FakeSearchRequest(
            {"items": [{"id": {"kind": "youtube#video", "videoId": "video-1"}}]}
        )
        self.list_calls = []

    def list(self, **kwargs: object) -> FakeSearchRequest:
        self.list_calls.append(dict(kwargs))
        return self.request


class FakeYouTubeService:
    search_resource: FakeSearchResource
    search_calls: int

    def __init__(self) -> None:
        self.search_resource = FakeSearchResource()
        self.search_calls = 0

    def search(self) -> FakeSearchResource:
        self.search_calls += 1
        return self.search_resource


class FakeAccountManager:
    service: FakeYouTubeService
    _services: dict[tuple[str, str], object]
    credentials_calls: list[str]
    youtube_calls: list[str]
    analytics_calls: list[str]
    reporting_calls: list[str]

    def __init__(self, service: FakeYouTubeService) -> None:
        self.service = service
        self._services = {}
        self.credentials_calls = []
        self.youtube_calls = []
        self.analytics_calls = []
        self.reporting_calls = []

    def get_credentials(self, key: str) -> object:
        self.credentials_calls.append(key)
        return object()

    def get_youtube_service(self, key: str) -> FakeYouTubeService:
        self.youtube_calls.append(key)
        self._services[(key, "youtube")] = self.service
        return self.service

    def get_analytics_service(self, key: str) -> object:
        self.analytics_calls.append(key)
        return object()

    def get_reporting_service(self, key: str) -> object:
        self.reporting_calls.append(key)
        return object()


class FakeContext:
    log_calls: list[tuple[str, str | None]]

    def __init__(self) -> None:
        self.log_calls = []

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
    service: FakeYouTubeService | None = None,
    mutating_guard: Callable[[str], None] | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeYouTubeService()
    manager = FakeAccountManager(fake_service)
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


def test_search_list_calls_mocked_discovery_client_with_all_params() -> None:
    manager, tracker = _configure()

    result = search.youtube_search_list(
        account="primary",
        part="snippet",
        channel_id="UC123",
        channel_type="any",
        event_type="live",
        for_content_owner=True,
        for_developer=False,
        for_mine=True,
        location="37.42307,-122.08427",
        location_radius="10km",
        max_results=25,
        on_behalf_of_content_owner="owner-1",
        order="date",
        page_token="next-token",
        published_after="2026-01-01T00:00:00Z",
        published_before="2026-02-01T00:00:00Z",
        q="music",
        region_code="US",
        relevance_language="en",
        safe_search="moderate",
        topic_id="/m/04rlf",
        type="video",
        video_caption="closedCaption",
        video_category_id="10",
        video_definition="high",
        video_dimension="2d",
        video_duration="short",
        video_embeddable="true",
        video_license="creativeCommon",
        video_paid_product_placement="true",
        video_syndicated="true",
        video_type="movie",
    )

    assert result == {"items": [{"id": {"kind": "youtube#video", "videoId": "video-1"}}]}
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 100)]
    assert tracker.record_calls == [("primary", 100)]
    assert manager.service.search_calls == 1
    assert manager.service.search_resource.list_calls == [
        {
            "part": "snippet",
            "channelId": "UC123",
            "channelType": "any",
            "eventType": "live",
            "forContentOwner": True,
            "forDeveloper": False,
            "forMine": True,
            "location": "37.42307,-122.08427",
            "locationRadius": "10km",
            "maxResults": 25,
            "onBehalfOfContentOwner": "owner-1",
            "order": "date",
            "pageToken": "next-token",
            "publishedAfter": "2026-01-01T00:00:00Z",
            "publishedBefore": "2026-02-01T00:00:00Z",
            "q": "music",
            "regionCode": "US",
            "relevanceLanguage": "en",
            "safeSearch": "moderate",
            "topicId": "/m/04rlf",
            "type": "video",
            "videoCaption": "closedCaption",
            "videoCategoryId": "10",
            "videoDefinition": "high",
            "videoDimension": "2d",
            "videoDuration": "short",
            "videoEmbeddable": "true",
            "videoLicense": "creativeCommon",
            "videoPaidProductPlacement": "true",
            "videoSyndicated": "true",
            "videoType": "movie",
        }
    ]
    assert manager.service.search_resource.request.execute_calls == 1


def test_search_list_does_not_forward_related_to_video_id_when_omitted() -> None:
    manager, tracker = _configure()

    result = search.youtube_search_list(
        account="primary",
        part="snippet",
        q="cats",
    )

    assert result == {"items": [{"id": {"kind": "youtube#video", "videoId": "video-1"}}]}
    assert tracker.preflight_calls == [("primary", 100)]
    assert tracker.record_calls == [("primary", 100)]
    assert "relatedToVideoId" not in manager.service.search_resource.list_calls[0]
    assert manager.service.search_resource.request.execute_calls == 1


def test_quota_warning_logged() -> None:
    manager, tracker = _configure()
    ctx = FakeContext()

    result = search.youtube_search_list(
        account="primary",
        part="snippet",
        q="quota",
        ctx=cast(Context, cast(object, ctx)),
    )

    assert result == {"items": [{"id": {"kind": "youtube#video", "videoId": "video-1"}}]}
    assert ctx.log_calls == [("search.list costs 100 units - current quota: 25%", "info")]
    assert tracker.current_calls == ["primary"]
    assert tracker.preflight_calls == [("primary", 100)]
    assert tracker.record_calls == [("primary", 100)]
    assert manager.service.search_resource.request.execute_calls == 1


@pytest.mark.asyncio
async def test_search_tool_is_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(search.youtube_search_list).parameters) == [
        "account",
        "part",
        "channel_id",
        "channel_type",
        "event_type",
        "for_content_owner",
        "for_developer",
        "for_mine",
        "location",
        "location_radius",
        "max_results",
        "on_behalf_of_content_owner",
        "order",
        "page_token",
        "published_after",
        "published_before",
        "q",
        "region_code",
        "relevance_language",
        "safe_search",
        "topic_id",
        "type",
        "video_caption",
        "video_category_id",
        "video_definition",
        "video_dimension",
        "video_duration",
        "video_embeddable",
        "video_license",
        "video_paid_product_placement",
        "video_syndicated",
        "video_type",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    tool = registered["youtube_search_list"]
    tool_meta = cast(dict[str, object], tool.meta)

    assert tool.parameters["required"] == ["account", "part"]
    assert "ctx" not in tool.parameters["properties"]
    assert "q" in tool.parameters["properties"]
    assert "video_duration" in tool.parameters["properties"]
    assert tool_meta["method"] == "youtube.search.list"
    assert tool_meta["scopes"] == ["https://www.googleapis.com/auth/youtube.readonly"]
    assert tool_meta["cost"] == 100
