"""Tests for the YouTube playlists and playlistItems tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportImplicitOverride=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest

import youtube_mcp.tools.playlists as playlists
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy

PLAYLIST_TOOL_NAMES = {
    "youtube_playlists_list",
    "youtube_playlists_insert",
    "youtube_playlists_update",
    "youtube_playlists_delete",
}
PLAYLIST_ITEM_TOOL_NAMES = {
    "youtube_playlistItems_list",
    "youtube_playlistItems_insert",
    "youtube_playlistItems_update",
    "youtube_playlistItems_delete",
}
MUTATING_TOOL_NAMES = (PLAYLIST_TOOL_NAMES | PLAYLIST_ITEM_TOOL_NAMES) - {
    "youtube_playlists_list",
    "youtube_playlistItems_list",
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


class FakeYouTubeRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakePlaylistsResource:
    list_request: FakeYouTubeRequest
    insert_request: FakeYouTubeRequest
    update_request: FakeYouTubeRequest
    delete_request: FakeYouTubeRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeYouTubeRequest({"items": [{"id": "PL-list"}]})
        self.insert_request = FakeYouTubeRequest({"id": "PL-insert"})
        self.update_request = FakeYouTubeRequest({"id": "PL-update"})
        self.delete_request = FakeYouTubeRequest({})
        self.list_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []

    def list(self, **kwargs: object) -> FakeYouTubeRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeYouTubeRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def update(self, **kwargs: object) -> FakeYouTubeRequest:
        self.update_calls.append(dict(kwargs))
        return self.update_request

    def delete(self, **kwargs: object) -> FakeYouTubeRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakePlaylistItemsResource:
    list_request: FakeYouTubeRequest
    insert_request: FakeYouTubeRequest
    update_request: FakeYouTubeRequest
    delete_request: FakeYouTubeRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeYouTubeRequest({"items": [{"id": "PLI-list"}]})
        self.insert_request = FakeYouTubeRequest({"id": "PLI-insert"})
        self.update_request = FakeYouTubeRequest({"id": "PLI-update"})
        self.delete_request = FakeYouTubeRequest({})
        self.list_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []

    def list(self, **kwargs: object) -> FakeYouTubeRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeYouTubeRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def update(self, **kwargs: object) -> FakeYouTubeRequest:
        self.update_calls.append(dict(kwargs))
        return self.update_request

    def delete(self, **kwargs: object) -> FakeYouTubeRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakeYouTubeService:
    playlists_resource: FakePlaylistsResource
    playlist_items_resource: FakePlaylistItemsResource
    playlists_calls: int
    playlist_items_calls: int

    def __init__(self) -> None:
        self.playlists_resource = FakePlaylistsResource()
        self.playlist_items_resource = FakePlaylistItemsResource()
        self.playlists_calls = 0
        self.playlist_items_calls = 0

    def playlists(self) -> FakePlaylistsResource:
        self.playlists_calls += 1
        return self.playlists_resource

    def playlistItems(self) -> FakePlaylistItemsResource:
        self.playlist_items_calls += 1
        return self.playlist_items_resource


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


def test_playlist_tools_call_mocked_discovery_client() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    playlist_body = {"snippet": {"title": "Test playlist"}}

    listed = playlists.youtube_playlists_list(
        account="primary",
        part="snippet,status",
        channel_id="UC123",
        id="PL123",
        mine=True,
        hl="en",
        max_results=10,
        page_token="next-token",
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="UC-owner",
    )
    inserted = playlists.youtube_playlists_insert(
        account="primary",
        part="snippet,status",
        playlist_body=playlist_body,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="UC-owner",
    )
    updated = playlists.youtube_playlists_update(
        account="primary",
        part="snippet,status",
        playlist_body=playlist_body,
        on_behalf_of_content_owner="owner-1",
    )
    deleted = playlists.youtube_playlists_delete(
        account="primary",
        id="PL123",
        on_behalf_of_content_owner="owner-1",
    )

    assert listed == {"items": [{"id": "PL-list"}]}
    assert inserted == {"id": "PL-insert"}
    assert updated == {"id": "PL-update"}
    assert deleted == {}
    assert manager.credentials_calls == ["primary", "primary", "primary", "primary"]
    assert manager.youtube_calls == ["primary", "primary", "primary", "primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert guard_calls == ["primary", "primary", "primary"]
    assert tracker.preflight_calls == [
        ("primary", 1),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
    ]
    assert tracker.record_calls == tracker.preflight_calls
    assert manager.service.playlists_calls == 4
    assert manager.service.playlists_resource.list_calls == [
        {
            "part": "snippet,status",
            "channelId": "UC123",
            "id": "PL123",
            "mine": True,
            "hl": "en",
            "maxResults": 10,
            "pageToken": "next-token",
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "UC-owner",
        }
    ]
    assert manager.service.playlists_resource.insert_calls == [
        {
            "part": "snippet,status",
            "body": playlist_body,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "UC-owner",
        }
    ]
    assert manager.service.playlists_resource.update_calls == [
        {
            "part": "snippet,status",
            "body": playlist_body,
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.playlists_resource.delete_calls == [
        {"id": "PL123", "onBehalfOfContentOwner": "owner-1"}
    ]


def test_playlistItems_tools_call_mocked_discovery_client() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    item_body = {"snippet": {"playlistId": "PL123", "position": 1}}

    listed = playlists.youtube_playlistItems_list(
        account="primary",
        part="snippet,contentDetails,status",
        id="PLI123",
        playlist_id="PL123",
        max_results=25,
        page_token="next-token",
        video_id="video-1",
        on_behalf_of_content_owner="owner-1",
    )
    inserted = playlists.youtube_playlistItems_insert(
        account="primary",
        part="snippet,contentDetails",
        item_body=item_body,
        on_behalf_of_content_owner="owner-1",
    )
    updated = playlists.youtube_playlistItems_update(
        account="primary",
        part="snippet,contentDetails",
        item_body=item_body,
        on_behalf_of_content_owner="owner-1",
    )
    deleted = playlists.youtube_playlistItems_delete(
        account="primary",
        id="PLI123",
        on_behalf_of_content_owner="owner-1",
    )

    assert listed == {"items": [{"id": "PLI-list"}]}
    assert inserted == {"id": "PLI-insert"}
    assert updated == {"id": "PLI-update"}
    assert deleted == {}
    assert manager.credentials_calls == ["primary", "primary", "primary", "primary"]
    assert manager.youtube_calls == ["primary", "primary", "primary", "primary"]
    assert guard_calls == ["primary", "primary", "primary"]
    assert tracker.preflight_calls == [
        ("primary", 1),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
    ]
    assert tracker.record_calls == tracker.preflight_calls
    assert manager.service.playlist_items_calls == 4
    assert manager.service.playlist_items_resource.list_calls == [
        {
            "part": "snippet,contentDetails,status",
            "id": "PLI123",
            "playlistId": "PL123",
            "maxResults": 25,
            "pageToken": "next-token",
            "videoId": "video-1",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.playlist_items_resource.insert_calls == [
        {
            "part": "snippet,contentDetails",
            "body": item_body,
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.playlist_items_resource.update_calls == [
        {
            "part": "snippet,contentDetails",
            "body": item_body,
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.playlist_items_resource.delete_calls == [
        {"id": "PLI123", "onBehalfOfContentOwner": "owner-1"}
    ]


@pytest.mark.asyncio
async def test_all_playlist_tool_names_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(playlists.youtube_playlists_list).parameters) == [
        "account",
        "part",
        "channel_id",
        "id",
        "mine",
        "hl",
        "max_results",
        "page_token",
        "on_behalf_of_content_owner",
        "on_behalf_of_content_owner_channel",
        "ctx",
    ]
    assert list(inspect.signature(playlists.youtube_playlistItems_list).parameters) == [
        "account",
        "part",
        "id",
        "playlist_id",
        "max_results",
        "page_token",
        "video_id",
        "on_behalf_of_content_owner",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    expected_names = PLAYLIST_TOOL_NAMES | PLAYLIST_ITEM_TOOL_NAMES

    assert expected_names <= registered.keys()
    for tool_name in MUTATING_TOOL_NAMES:
        assert registered[tool_name].tags == {"mutating"}
    assert registered["youtube_playlists_insert"].parameters["required"] == [
        "account",
        "part",
        "playlist_body",
    ]
    assert registered["youtube_playlistItems_insert"].parameters["required"] == [
        "account",
        "part",
        "item_body",
    ]
    assert "ctx" not in registered["youtube_playlists_list"].parameters["properties"]
    assert "ctx" not in registered["youtube_playlistItems_list"].parameters["properties"]
