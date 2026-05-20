"""Tests for the YouTube activities tool."""

# pyright: reportMissingTypeStubs=false, reportRedeclaration=false, reportUnannotatedClassAttribute=false

from __future__ import annotations

import inspect

import pytest

from youtube_mcp.server import mcp
from youtube_mcp.tools import activities
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy


class FakeQuotaTracker:
    enforce: bool
    preflight_calls: list[tuple[str, int]]
    record_calls: list[tuple[str, int]]

    def __init__(self) -> None:
        self.enforce = False
        self.preflight_calls: list[tuple[str, int]] = []
        self.record_calls: list[tuple[str, int]] = []

    def would_exceed(self, account_key: str, units: int) -> bool:
        self.preflight_calls.append((account_key, units))
        return False

    def record(self, account_key: str, units: int) -> None:
        self.record_calls.append((account_key, units))


class FakeActivitiesRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeActivitiesResource:
    request: FakeActivitiesRequest
    list_calls: list[dict[str, object]]

    def __init__(self, response: dict[str, object]) -> None:
        self.request = FakeActivitiesRequest(response)
        self.list_calls: list[dict[str, object]] = []

    def list(self, **kwargs: object) -> FakeActivitiesRequest:
        self.list_calls.append(dict(kwargs))
        return self.request


class FakeYouTubeService:
    activities_resource: FakeActivitiesResource
    activities_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.activities_resource = FakeActivitiesResource(response)
        self.activities_calls = 0

    def activities(self) -> FakeActivitiesResource:
        self.activities_calls += 1
        return self.activities_resource


class FakeAccountManager:
    service: FakeYouTubeService
    _services: dict[tuple[str, str], object]
    credentials_calls: list[str]
    youtube_calls: list[str]
    analytics_calls: list[str]
    reporting_calls: list[str]

    def __init__(self, service: FakeYouTubeService) -> None:
        self.service = service
        self._services: dict[tuple[str, str], object] = {}
        self.credentials_calls: list[str] = []
        self.youtube_calls: list[str] = []
        self.analytics_calls: list[str] = []
        self.reporting_calls: list[str] = []

    def get_credentials(self, key: str) -> object:
        self.credentials_calls.append(key)
        return object()

    def get_youtube_service(self, key: str) -> object:
        self.youtube_calls.append(key)
        self._services[(key, "youtube")] = self.service
        return self.service

    def get_analytics_service(self, key: str) -> object:
        self.analytics_calls.append(key)
        return self.service

    def get_reporting_service(self, key: str) -> object:
        self.reporting_calls.append(key)
        return self.service


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
    fake_service = service or FakeYouTubeService({"items": [{"id": "activity-1"}]})
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


def test_tool_calls_activities_list_with_mocked_discovery_client() -> None:
    manager, tracker = _configure()

    result = activities.youtube_activities_list(
        account="primary",
        part="snippet,contentDetails",
        channel_id="UC123",
        mine=True,
        home=False,
        max_results=7,
        page_token="next-token",
        published_after="2026-01-01T00:00:00Z",
        published_before="2026-02-01T00:00:00Z",
        region_code="NO",
    )

    assert result == {"items": [{"id": "activity-1"}]}
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 1)]
    assert tracker.record_calls == [("primary", 1)]
    assert manager.service.activities_calls == 1
    assert manager.service.activities_resource.list_calls == [
        {
            "part": "snippet,contentDetails",
            "channelId": "UC123",
            "home": False,
            "mine": True,
            "maxResults": 7,
            "pageToken": "next-token",
            "publishedAfter": "2026-01-01T00:00:00Z",
            "publishedBefore": "2026-02-01T00:00:00Z",
            "regionCode": "NO",
        }
    ]
    assert manager.service.activities_resource.request.execute_calls == 1


@pytest.mark.asyncio
async def test_tool_is_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(activities.youtube_activities_list).parameters) == [
        "account",
        "part",
        "channel_id",
        "mine",
        "home",
        "max_results",
        "page_token",
        "published_after",
        "published_before",
        "region_code",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    tool = registered["youtube_activities_list"]

    assert tool.parameters["required"] == ["account"]
    assert "ctx" not in tool.parameters["properties"]
