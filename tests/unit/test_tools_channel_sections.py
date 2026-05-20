"""Tests for the YouTube channelSections tools."""

# pyright: reportMissingTypeStubs=false, reportRedeclaration=false, reportUnannotatedClassAttribute=false
# pyright: reportImplicitOverride=false

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest

from youtube_mcp.server import mcp
from youtube_mcp.tools import channel_sections
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy


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


class FakeChannelSectionsRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeChannelSectionsResource:
    list_request: FakeChannelSectionsRequest
    insert_request: FakeChannelSectionsRequest
    update_request: FakeChannelSectionsRequest
    delete_request: FakeChannelSectionsRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeChannelSectionsRequest({"items": [{"id": "section-list-1"}]})
        self.insert_request = FakeChannelSectionsRequest({"id": "section-insert-1"})
        self.update_request = FakeChannelSectionsRequest({"id": "section-update-1"})
        self.delete_request = FakeChannelSectionsRequest({})
        self.list_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []

    def list(self, **kwargs: object) -> FakeChannelSectionsRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeChannelSectionsRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def update(self, **kwargs: object) -> FakeChannelSectionsRequest:
        self.update_calls.append(dict(kwargs))
        return self.update_request

    def delete(self, **kwargs: object) -> FakeChannelSectionsRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakeYouTubeService:
    channel_sections_resource: FakeChannelSectionsResource
    channel_sections_calls: int

    def __init__(self) -> None:
        self.channel_sections_resource = FakeChannelSectionsResource()
        self.channel_sections_calls = 0

    def channelSections(self) -> FakeChannelSectionsResource:
        self.channel_sections_calls += 1
        return self.channel_sections_resource


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


def test_tool_calls_channel_sections_list_with_mocked_discovery_client() -> None:
    manager, tracker = _configure()

    result = channel_sections.youtube_channelSections_list(
        account="primary",
        part="snippet,contentDetails",
        channel_id="UC123",
        id="section-123",
        mine=True,
        hl="en_US",
        on_behalf_of_content_owner="owner-1",
    )

    assert result == {"items": [{"id": "section-list-1"}]}
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 1)]
    assert tracker.record_calls == [("primary", 1)]
    assert manager.service.channel_sections_calls == 1
    assert manager.service.channel_sections_resource.list_calls == [
        {
            "part": "snippet,contentDetails",
            "channelId": "UC123",
            "id": "section-123",
            "mine": True,
            "hl": "en_US",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.channel_sections_resource.list_request.execute_calls == 1


def test_tool_calls_channel_sections_insert_with_mocked_discovery_client() -> None:
    events: list[str] = []

    def guard(account: str) -> None:
        events.append(f"guard:{account}")

    manager, tracker = _configure(mutating_guard=guard)
    body = {"snippet": {"type": "singlePlaylist", "position": 1}}

    result = channel_sections.youtube_channelSections_insert(
        account="primary",
        part="snippet,contentDetails",
        section_body=body,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
    )

    assert result == {"id": "section-insert-1"}
    assert events == ["guard:primary"]
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert manager.service.channel_sections_calls == 1
    assert manager.service.channel_sections_resource.insert_calls == [
        {
            "part": "snippet,contentDetails",
            "body": body,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]
    assert manager.service.channel_sections_resource.insert_request.execute_calls == 1


def test_tool_calls_channel_sections_update_with_mocked_discovery_client() -> None:
    events: list[str] = []

    def guard(account: str) -> None:
        events.append(f"guard:{account}")

    manager, tracker = _configure(mutating_guard=guard)
    body = {"id": "section-123", "snippet": {"type": "multiplePlaylists", "position": 2}}

    result = channel_sections.youtube_channelSections_update(
        account="primary",
        part="snippet,contentDetails",
        section_body=body,
        on_behalf_of_content_owner="owner-1",
    )

    assert result == {"id": "section-update-1"}
    assert events == ["guard:primary"]
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert manager.service.channel_sections_calls == 1
    assert manager.service.channel_sections_resource.update_calls == [
        {
            "part": "snippet,contentDetails",
            "body": body,
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.channel_sections_resource.update_request.execute_calls == 1


def test_tool_calls_channel_sections_delete_with_mocked_discovery_client() -> None:
    events: list[str] = []

    def guard(account: str) -> None:
        events.append(f"guard:{account}")

    manager, tracker = _configure(mutating_guard=guard)

    result = channel_sections.youtube_channelSections_delete(
        account="primary",
        id="section-123",
        on_behalf_of_content_owner="owner-1",
    )

    assert result == {}
    assert events == ["guard:primary"]
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert manager.service.channel_sections_calls == 1
    assert manager.service.channel_sections_resource.delete_calls == [
        {
            "id": "section-123",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.channel_sections_resource.delete_request.execute_calls == 1


@pytest.mark.asyncio
async def test_channel_sections_tools_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(channel_sections.youtube_channelSections_list).parameters) == [
        "account",
        "part",
        "channel_id",
        "id",
        "mine",
        "hl",
        "on_behalf_of_content_owner",
        "ctx",
    ]
    assert list(inspect.signature(channel_sections.youtube_channelSections_insert).parameters) == [
        "account",
        "part",
        "section_body",
        "on_behalf_of_content_owner",
        "on_behalf_of_content_owner_channel",
        "ctx",
    ]
    assert list(inspect.signature(channel_sections.youtube_channelSections_update).parameters) == [
        "account",
        "part",
        "section_body",
        "on_behalf_of_content_owner",
        "ctx",
    ]
    assert list(inspect.signature(channel_sections.youtube_channelSections_delete).parameters) == [
        "account",
        "id",
        "on_behalf_of_content_owner",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert "youtube_channelSections_list" in registered
    assert "youtube_channelSections_insert" in registered
    assert "youtube_channelSections_update" in registered
    assert "youtube_channelSections_delete" in registered

    list_tool = registered["youtube_channelSections_list"]
    insert_tool = registered["youtube_channelSections_insert"]
    update_tool = registered["youtube_channelSections_update"]
    delete_tool = registered["youtube_channelSections_delete"]

    assert list_tool.parameters["required"] == ["account", "part"]
    assert "ctx" not in list_tool.parameters["properties"]
    assert insert_tool.tags == {"mutating"}
    assert insert_tool.parameters["required"] == ["account", "part", "section_body"]
    assert "ctx" not in insert_tool.parameters["properties"]
    assert update_tool.tags == {"mutating"}
    assert update_tool.parameters["required"] == ["account", "part", "section_body"]
    assert "ctx" not in update_tool.parameters["properties"]
    assert delete_tool.tags == {"mutating"}
    assert delete_tool.parameters["required"] == ["account", "id"]
    assert "ctx" not in delete_tool.parameters["properties"]
