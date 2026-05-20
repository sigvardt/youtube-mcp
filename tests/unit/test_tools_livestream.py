"""Tests for the YouTube liveBroadcasts and liveStreams tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportImplicitOverride=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest

import youtube_mcp.tools.livestream as livestream
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy

BROADCAST_TOOL_NAMES = {
    "youtube_liveBroadcasts_list",
    "youtube_liveBroadcasts_insert",
    "youtube_liveBroadcasts_update",
    "youtube_liveBroadcasts_delete",
    "youtube_liveBroadcasts_bind",
    "youtube_liveBroadcasts_transition",
    "youtube_liveBroadcasts_cuepoint",
}
STREAM_TOOL_NAMES = {
    "youtube_liveStreams_list",
    "youtube_liveStreams_insert",
    "youtube_liveStreams_update",
    "youtube_liveStreams_delete",
}
LIVESTREAM_TOOL_NAMES = BROADCAST_TOOL_NAMES | STREAM_TOOL_NAMES
READONLY_TOOL_NAMES = {
    "youtube_liveBroadcasts_list",
    "youtube_liveStreams_list",
}
MUTATING_TOOL_NAMES = LIVESTREAM_TOOL_NAMES - READONLY_TOOL_NAMES
EXPECTED_QUOTA_CALLS = [
    ("primary", 1),
    ("primary", 50),
    ("primary", 50),
    ("primary", 50),
    ("primary", 50),
    ("primary", 50),
    ("primary", 50),
    ("primary", 1),
    ("primary", 50),
    ("primary", 50),
    ("primary", 50),
]


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


class FakeLiveBroadcastsResource:
    list_request: FakeYouTubeRequest
    insert_request: FakeYouTubeRequest
    update_request: FakeYouTubeRequest
    delete_request: FakeYouTubeRequest
    bind_request: FakeYouTubeRequest
    transition_request: FakeYouTubeRequest
    cuepoint_request: FakeYouTubeRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]
    bind_calls: list[dict[str, object]]
    transition_calls: list[dict[str, object]]
    cuepoint_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeYouTubeRequest({"items": [{"id": "broadcast-list-1"}]})
        self.insert_request = FakeYouTubeRequest({"id": "broadcast-insert-1"})
        self.update_request = FakeYouTubeRequest({"id": "broadcast-update-1"})
        self.delete_request = FakeYouTubeRequest({})
        self.bind_request = FakeYouTubeRequest({"id": "broadcast-bind-1"})
        self.transition_request = FakeYouTubeRequest({"status": {"lifeCycleStatus": "live"}})
        self.cuepoint_request = FakeYouTubeRequest({"id": "cuepoint-1"})
        self.list_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []
        self.bind_calls = []
        self.transition_calls = []
        self.cuepoint_calls = []

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

    def bind(self, **kwargs: object) -> FakeYouTubeRequest:
        self.bind_calls.append(dict(kwargs))
        return self.bind_request

    def transition(self, **kwargs: object) -> FakeYouTubeRequest:
        self.transition_calls.append(dict(kwargs))
        return self.transition_request

    def cuepoint(self, **kwargs: object) -> FakeYouTubeRequest:
        self.cuepoint_calls.append(dict(kwargs))
        return self.cuepoint_request


class FakeLiveStreamsResource:
    list_request: FakeYouTubeRequest
    insert_request: FakeYouTubeRequest
    update_request: FakeYouTubeRequest
    delete_request: FakeYouTubeRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeYouTubeRequest({"items": [{"id": "stream-list-1"}]})
        self.insert_request = FakeYouTubeRequest({"id": "stream-insert-1"})
        self.update_request = FakeYouTubeRequest({"id": "stream-update-1"})
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
    live_broadcasts_resource: FakeLiveBroadcastsResource
    live_streams_resource: FakeLiveStreamsResource
    live_broadcasts_calls: int
    live_streams_calls: int

    def __init__(self) -> None:
        self.live_broadcasts_resource = FakeLiveBroadcastsResource()
        self.live_streams_resource = FakeLiveStreamsResource()
        self.live_broadcasts_calls = 0
        self.live_streams_calls = 0

    def liveBroadcasts(self) -> FakeLiveBroadcastsResource:
        self.live_broadcasts_calls += 1
        return self.live_broadcasts_resource

    def liveStreams(self) -> FakeLiveStreamsResource:
        self.live_streams_calls += 1
        return self.live_streams_resource


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


def test_livestream_tools_call_mocked_discovery_client() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    broadcast_body = {"id": "broadcast-123", "snippet": {"title": "Scheduled live"}}
    stream_body = {"id": "stream-123", "snippet": {"title": "Test stream"}}
    cuepoint_body = {"cueType": "ad"}

    listed_broadcasts = livestream.youtube_liveBroadcasts_list(
        account="primary",
        part="snippet,status",
        broadcast_status="upcoming",
        broadcast_type="event",
        id="broadcast-123",
        mine=True,
        max_results=10,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
        page_token="broadcast-page-2",
    )
    inserted_broadcast = livestream.youtube_liveBroadcasts_insert(
        account="primary",
        part="snippet,status",
        broadcast_body=broadcast_body,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
    )
    updated_broadcast = livestream.youtube_liveBroadcasts_update(
        account="primary",
        part="snippet,status",
        broadcast_body=broadcast_body,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
    )
    bound_broadcast = livestream.youtube_liveBroadcasts_bind(
        account="primary",
        id="broadcast-123",
        part="id,contentDetails",
        stream_id="stream-123",
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
    )
    transitioned_broadcast = livestream.youtube_liveBroadcasts_transition(
        account="primary",
        id="broadcast-123",
        broadcast_status="live",
        part="status",
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
    )
    inserted_cuepoint = livestream.youtube_liveBroadcasts_cuepoint(
        account="primary",
        id="broadcast-123",
        cuepoint_body=cuepoint_body,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
    )
    deleted_broadcast = livestream.youtube_liveBroadcasts_delete(
        account="primary",
        id="broadcast-123",
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
    )
    listed_streams = livestream.youtube_liveStreams_list(
        account="primary",
        part="snippet,cdn,status",
        id="stream-123",
        mine=True,
        max_results=10,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
        page_token="stream-page-2",
    )
    inserted_stream = livestream.youtube_liveStreams_insert(
        account="primary",
        part="snippet,cdn,status",
        stream_body=stream_body,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
    )
    updated_stream = livestream.youtube_liveStreams_update(
        account="primary",
        part="snippet,cdn,status",
        stream_body=stream_body,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
    )
    deleted_stream = livestream.youtube_liveStreams_delete(
        account="primary",
        id="stream-123",
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
    )

    assert listed_broadcasts == {"items": [{"id": "broadcast-list-1"}]}
    assert inserted_broadcast == {"id": "broadcast-insert-1"}
    assert updated_broadcast == {"id": "broadcast-update-1"}
    assert bound_broadcast == {"id": "broadcast-bind-1"}
    assert transitioned_broadcast == {"status": {"lifeCycleStatus": "live"}}
    assert inserted_cuepoint == {"id": "cuepoint-1"}
    assert deleted_broadcast == {}
    assert listed_streams == {"items": [{"id": "stream-list-1"}]}
    assert inserted_stream == {"id": "stream-insert-1"}
    assert updated_stream == {"id": "stream-update-1"}
    assert deleted_stream == {}
    assert manager.credentials_calls == ["primary"] * 11
    assert manager.youtube_calls == ["primary"] * 11
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert guard_calls == ["primary"] * 9
    assert tracker.preflight_calls == EXPECTED_QUOTA_CALLS
    assert tracker.record_calls == EXPECTED_QUOTA_CALLS
    assert manager.service.live_broadcasts_calls == 7
    assert manager.service.live_streams_calls == 4
    assert manager.service.live_broadcasts_resource.list_calls == [
        {
            "part": "snippet,status",
            "broadcastStatus": "upcoming",
            "broadcastType": "event",
            "id": "broadcast-123",
            "mine": True,
            "maxResults": 10,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
            "pageToken": "broadcast-page-2",
        }
    ]
    assert manager.service.live_broadcasts_resource.insert_calls == [
        {
            "part": "snippet,status",
            "body": broadcast_body,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]
    assert manager.service.live_broadcasts_resource.update_calls == [
        {
            "part": "snippet,status",
            "body": broadcast_body,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]
    assert manager.service.live_broadcasts_resource.bind_calls == [
        {
            "id": "broadcast-123",
            "part": "id,contentDetails",
            "streamId": "stream-123",
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]
    assert manager.service.live_broadcasts_resource.transition_calls == [
        {
            "id": "broadcast-123",
            "broadcastStatus": "live",
            "part": "status",
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]
    assert manager.service.live_broadcasts_resource.cuepoint_calls == [
        {
            "id": "broadcast-123",
            "body": cuepoint_body,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]
    assert manager.service.live_broadcasts_resource.delete_calls == [
        {
            "id": "broadcast-123",
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]
    assert manager.service.live_streams_resource.list_calls == [
        {
            "part": "snippet,cdn,status",
            "id": "stream-123",
            "mine": True,
            "maxResults": 10,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
            "pageToken": "stream-page-2",
        }
    ]
    assert manager.service.live_streams_resource.insert_calls == [
        {
            "part": "snippet,cdn,status",
            "body": stream_body,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]
    assert manager.service.live_streams_resource.update_calls == [
        {
            "part": "snippet,cdn,status",
            "body": stream_body,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]
    assert manager.service.live_streams_resource.delete_calls == [
        {
            "id": "stream-123",
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]


def test_livestream_public_signatures_preserve_camelcase_resources() -> None:
    assert list(inspect.signature(livestream.youtube_liveBroadcasts_transition).parameters) == [
        "account",
        "id",
        "broadcast_status",
        "part",
        "on_behalf_of_content_owner",
        "on_behalf_of_content_owner_channel",
        "ctx",
    ]
    assert list(inspect.signature(livestream.youtube_liveStreams_insert).parameters) == [
        "account",
        "part",
        "stream_body",
        "on_behalf_of_content_owner",
        "on_behalf_of_content_owner_channel",
        "ctx",
    ]


@pytest.mark.asyncio
async def test_livestream_tool_names_registered() -> None:
    _ = _configure()

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert LIVESTREAM_TOOL_NAMES <= set(registered)
    for tool_name in MUTATING_TOOL_NAMES:
        assert registered[tool_name].tags == {"mutating"}
