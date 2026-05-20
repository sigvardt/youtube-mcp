"""Tests for the YouTube subscriptions tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportImplicitOverride=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast

import pytest

import youtube_mcp.tools.subscriptions as subscriptions
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy

SUBSCRIPTION_TOOL_NAMES = {
    "youtube_subscriptions_list",
    "youtube_subscriptions_insert",
    "youtube_subscriptions_delete",
}
MUTATING_TOOL_NAMES = {
    "youtube_subscriptions_insert",
    "youtube_subscriptions_delete",
}


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


class FakeSubscriptionsRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeSubscriptionsResource:
    list_request: FakeSubscriptionsRequest
    insert_request: FakeSubscriptionsRequest
    delete_request: FakeSubscriptionsRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeSubscriptionsRequest({"items": [{"id": "subscription-list-1"}]})
        self.insert_request = FakeSubscriptionsRequest({"id": "subscription-insert-1"})
        self.delete_request = FakeSubscriptionsRequest({})
        self.list_calls = []
        self.insert_calls = []
        self.delete_calls = []

    def list(self, **kwargs: object) -> FakeSubscriptionsRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeSubscriptionsRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def delete(self, **kwargs: object) -> FakeSubscriptionsRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakeYouTubeService:
    subscriptions_resource: FakeSubscriptionsResource
    subscriptions_calls: int

    def __init__(self) -> None:
        self.subscriptions_resource = FakeSubscriptionsResource()
        self.subscriptions_calls = 0

    def subscriptions(self) -> FakeSubscriptionsResource:
        self.subscriptions_calls += 1
        return self.subscriptions_resource


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


def test_subscriptions_tools_call_mocked_discovery_client() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    subscription_body = {"snippet": {"resourceId": {"channelId": "UC-target"}}}

    listed = subscriptions.youtube_subscriptions_list(
        account="primary",
        part="snippet,contentDetails,subscriberSnippet",
        channel_id="UC123",
        id="subscription-1",
        mine=True,
        my_recent_subscribers=False,
        my_subscribers=True,
        for_channel_id="UC-target",
        max_results=25,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="UC-owner",
        order="alphabetical",
        page_token="next-token",
    )
    inserted = subscriptions.youtube_subscriptions_insert(
        account="primary",
        part="snippet",
        subscription_body=subscription_body,
    )
    deleted = subscriptions.youtube_subscriptions_delete(
        account="primary",
        id="subscription-1",
    )

    assert listed == {"items": [{"id": "subscription-list-1"}]}
    assert inserted == {"id": "subscription-insert-1"}
    assert deleted == {}
    assert manager.credentials_calls == ["primary", "primary", "primary"]
    assert manager.youtube_calls == ["primary", "primary", "primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert guard_calls == ["primary", "primary"]
    assert tracker.preflight_calls == [
        ("primary", 1),
        ("primary", 50),
        ("primary", 50),
    ]
    assert tracker.record_calls == tracker.preflight_calls
    assert manager.service.subscriptions_calls == 3
    assert manager.service.subscriptions_resource.list_calls == [
        {
            "part": "snippet,contentDetails,subscriberSnippet",
            "channelId": "UC123",
            "id": "subscription-1",
            "mine": True,
            "myRecentSubscribers": False,
            "mySubscribers": True,
            "forChannelId": "UC-target",
            "maxResults": 25,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "UC-owner",
            "order": "alphabetical",
            "pageToken": "next-token",
        }
    ]
    assert manager.service.subscriptions_resource.insert_calls == [
        {"part": "snippet", "body": subscription_body}
    ]
    assert manager.service.subscriptions_resource.delete_calls == [{"id": "subscription-1"}]
    assert manager.service.subscriptions_resource.list_request.execute_calls == 1
    assert manager.service.subscriptions_resource.insert_request.execute_calls == 1
    assert manager.service.subscriptions_resource.delete_request.execute_calls == 1


@pytest.mark.asyncio
async def test_subscription_tool_names_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(subscriptions.youtube_subscriptions_list).parameters) == [
        "account",
        "part",
        "channel_id",
        "id",
        "mine",
        "my_recent_subscribers",
        "my_subscribers",
        "for_channel_id",
        "max_results",
        "on_behalf_of_content_owner",
        "on_behalf_of_content_owner_channel",
        "order",
        "page_token",
        "ctx",
    ]
    assert list(inspect.signature(subscriptions.youtube_subscriptions_insert).parameters) == [
        "account",
        "part",
        "subscription_body",
        "ctx",
    ]
    assert list(inspect.signature(subscriptions.youtube_subscriptions_delete).parameters) == [
        "account",
        "id",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert SUBSCRIPTION_TOOL_NAMES <= registered.keys()
    assert registered["youtube_subscriptions_list"].parameters["required"] == [
        "account",
        "part",
    ]
    assert registered["youtube_subscriptions_insert"].parameters["required"] == [
        "account",
        "part",
        "subscription_body",
    ]
    assert registered["youtube_subscriptions_delete"].parameters["required"] == [
        "account",
        "id",
    ]

    list_meta = cast(dict[str, object], registered["youtube_subscriptions_list"].meta)
    assert list_meta["method"] == "youtube.subscriptions.list"
    assert list_meta["scopes"] == ["https://www.googleapis.com/auth/youtube.readonly"]
    assert list_meta["cost"] == 1
    assert "ctx" not in registered["youtube_subscriptions_list"].parameters["properties"]

    for tool_name in MUTATING_TOOL_NAMES:
        tool = registered[tool_name]
        tool_meta = cast(dict[str, object], tool.meta)
        assert tool.tags == {"mutating"}
        assert tool_meta["method"] == f"youtube.subscriptions.{tool_name.rsplit('_', 1)[1]}"
        assert tool_meta["scopes"] == ["https://www.googleapis.com/auth/youtube.force-ssl"]
        assert tool_meta["cost"] == 50
        assert "ctx" not in tool.parameters["properties"]
