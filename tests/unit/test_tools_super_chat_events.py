"""Tests for the YouTube superChatEvents tool."""

# pyright: reportMissingTypeStubs=false, reportRedeclaration=false, reportUnannotatedClassAttribute=false

from __future__ import annotations

import importlib
import inspect
from typing import Protocol, cast

import pytest

from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy, YouTubeScope


class SuperChatEventsModule(Protocol):
    def youtube_superChatEvents_list(
        self,
        account: str,
        part: str,
        hl: str | None = None,
        max_results: int = 5,
        page_token: str | None = None,
        ctx: object | None = None,
    ) -> dict[str, object]:
        ...


super_chat_events_module = importlib.import_module("youtube_mcp.tools.super_chat_events")
super_chat_events = cast(SuperChatEventsModule, cast(object, super_chat_events_module))


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


class FakeSuperChatEventsRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeSuperChatEventsResource:
    request: FakeSuperChatEventsRequest
    list_calls: list[dict[str, object]]

    def __init__(self, response: dict[str, object]) -> None:
        self.request = FakeSuperChatEventsRequest(response)
        self.list_calls = []

    def list(self, **kwargs: object) -> FakeSuperChatEventsRequest:
        self.list_calls.append(dict(kwargs))
        return self.request


class FakeYouTubeService:
    super_chat_events_resource: FakeSuperChatEventsResource
    super_chat_events_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.super_chat_events_resource = FakeSuperChatEventsResource(response)
        self.super_chat_events_calls = 0

    def superChatEvents(self) -> FakeSuperChatEventsResource:
        self.super_chat_events_calls += 1
        return self.super_chat_events_resource


class FakeAccountManager:
    service: FakeYouTubeService
    _services: dict[tuple[str, str], FakeYouTubeService]
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

    def get_youtube_service(self, key: str) -> FakeYouTubeService:
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
        max_attempts=2,
        initial_wait=0.001,
        max_wait=0.01,
        multiplier=1.0,
        jitter=False,
    )


def _configure(
    service: FakeYouTubeService | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeYouTubeService({"items": [{"id": "super-chat-event-1"}]})
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


def test_super_chat_events_tool_calls_mocked_discovery_client() -> None:
    manager, tracker = _configure()

    result = super_chat_events.youtube_superChatEvents_list(
        account="primary",
        part="snippet",
        hl="en",
        max_results=7,
        page_token="next-token",
    )

    assert result == {"items": [{"id": "super-chat-event-1"}]}
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert tracker.preflight_calls == [("primary", 1)]
    assert tracker.record_calls == [("primary", 1)]
    assert manager.service.super_chat_events_calls == 1
    assert manager.service.super_chat_events_resource.list_calls == [
        {
            "part": "snippet",
            "hl": "en",
            "maxResults": 7,
            "pageToken": "next-token",
        }
    ]
    assert manager.service.super_chat_events_resource.request.execute_calls == 1


@pytest.mark.asyncio
async def test_super_chat_events_tool_is_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(super_chat_events.youtube_superChatEvents_list).parameters) == [
        "account",
        "part",
        "hl",
        "max_results",
        "page_token",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    tool = registered["youtube_superChatEvents_list"]

    assert tool.parameters["required"] == ["account", "part"]
    assert "ctx" not in tool.parameters["properties"]
    assert tool.meta == {
        "api": "youtube",
        "method": "youtube.superChatEvents.list",
        "scopes": [YouTubeScope.READONLY.value],
        "cost": 1,
    }
