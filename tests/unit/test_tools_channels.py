"""Tests for the YouTube channels, channelBanners, and thirdPartyLinks tools."""

# pyright: reportImplicitOverride=false, reportMissingTypeStubs=false, reportRedeclaration=false, reportUnannotatedClassAttribute=false

from __future__ import annotations

from collections.abc import Callable

import pytest

from youtube_mcp.server import mcp
from youtube_mcp.tools import channels
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


class FakeRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeChannelsResource:
    list_request: FakeRequest
    update_request: FakeRequest
    list_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeRequest({"items": [{"id": "UC123"}]})
        self.update_request = FakeRequest({"id": "UC123", "kind": "youtube#channel"})
        self.list_calls = []
        self.update_calls = []

    def list(self, **kwargs: object) -> FakeRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def update(self, **kwargs: object) -> FakeRequest:
        self.update_calls.append(dict(kwargs))
        return self.update_request


class FakeChannelBannersResource:
    insert_request: FakeRequest
    insert_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.insert_request = FakeRequest({"url": "https://example.test/banner.png"})
        self.insert_calls = []

    def insert(self, **kwargs: object) -> FakeRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request


class FakeThirdPartyLinksResource:
    list_request: FakeRequest
    insert_request: FakeRequest
    update_request: FakeRequest
    delete_request: FakeRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeRequest({"items": [{"linkingToken": "token-1"}]})
        self.insert_request = FakeRequest({"linkingToken": "token-2"})
        self.update_request = FakeRequest({"linkingToken": "token-3"})
        self.delete_request = FakeRequest({})
        self.list_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []

    def list(self, **kwargs: object) -> FakeRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def update(self, **kwargs: object) -> FakeRequest:
        self.update_calls.append(dict(kwargs))
        return self.update_request

    def delete(self, **kwargs: object) -> FakeRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakeYouTubeService:
    channels_resource: FakeChannelsResource
    channel_banners_resource: FakeChannelBannersResource
    third_party_links_resource: FakeThirdPartyLinksResource
    channels_calls: int
    channel_banners_calls: int
    third_party_links_calls: int

    def __init__(self) -> None:
        self.channels_resource = FakeChannelsResource()
        self.channel_banners_resource = FakeChannelBannersResource()
        self.third_party_links_resource = FakeThirdPartyLinksResource()
        self.channels_calls = 0
        self.channel_banners_calls = 0
        self.third_party_links_calls = 0

    def channels(self) -> FakeChannelsResource:
        self.channels_calls += 1
        return self.channels_resource

    def channelBanners(self) -> FakeChannelBannersResource:
        self.channel_banners_calls += 1
        return self.channel_banners_resource

    def thirdPartyLinks(self) -> FakeThirdPartyLinksResource:
        self.third_party_links_calls += 1
        return self.third_party_links_resource


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


class FakeMediaFileUpload:
    path: str

    def __init__(self, path: str) -> None:
        self.path = path


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


def test_channels_list_calls_mocked_discovery_client() -> None:
    manager, tracker = _configure()

    result = channels.youtube_channels_list(
        account="primary",
        part="snippet,contentDetails",
        category_id="GC123",
        for_handle="@example",
        for_username="legacy-user",
        id="UC123",
        managed_by_me=True,
        mine=False,
        hl="en_US",
        max_results=7,
        on_behalf_of_content_owner="owner-1",
        page_token="next-token",
    )

    assert result == {"items": [{"id": "UC123"}]}
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 1)]
    assert tracker.record_calls == [("primary", 1)]
    assert manager.service.channels_calls == 1
    assert manager.service.channels_resource.list_calls == [
        {
            "part": "snippet,contentDetails",
            "categoryId": "GC123",
            "forHandle": "@example",
            "forUsername": "legacy-user",
            "id": "UC123",
            "managedByMe": True,
            "mine": False,
            "hl": "en_US",
            "maxResults": 7,
            "onBehalfOfContentOwner": "owner-1",
            "pageToken": "next-token",
        }
    ]
    assert manager.service.channels_resource.list_request.execute_calls == 1


def test_channels_update_calls_mutating_guard_before_mocked_discovery_client() -> None:
    events: list[str] = []

    class EventAccountManager(FakeAccountManager):
        def get_credentials(self, key: str) -> object:
            events.append(f"credentials:{key}")
            return super().get_credentials(key)

        def get_youtube_service(self, key: str) -> FakeYouTubeService:
            events.append(f"service:{key}")
            return super().get_youtube_service(key)

    def guard(account: str) -> None:
        events.append(f"guard:{account}")

    fake_service = FakeYouTubeService()
    manager = EventAccountManager(fake_service)
    tracker = FakeQuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=guard,
            retry_policy=_retry_policy(),
        )
    )
    body = {"id": "UC123", "snippet": {"title": "Updated"}}

    result = channels.youtube_channels_update(
        account="primary",
        part="snippet",
        channel_body=body,
        on_behalf_of_content_owner="owner-1",
    )

    assert result == {"id": "UC123", "kind": "youtube#channel"}
    assert events == ["credentials:primary", "guard:primary", "service:primary"]
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert manager.service.channels_resource.update_calls == [
        {"part": "snippet", "body": body, "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.channels_resource.update_request.execute_calls == 1


def test_channel_banners_insert_uses_media_file_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(channels, "MediaFileUpload", FakeMediaFileUpload)
    manager, tracker = _configure()

    result = channels.youtube_channel_banners_insert(
        account="primary",
        banner_file_path="/tmp/banner.png",
        channel_id="UC123",
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="UC999",
    )

    assert result == {"url": "https://example.test/banner.png"}
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert manager.service.channel_banners_calls == 1
    insert_call = manager.service.channel_banners_resource.insert_calls[0]
    assert insert_call["channelId"] == "UC123"
    assert insert_call["onBehalfOfContentOwner"] == "owner-1"
    assert insert_call["onBehalfOfContentOwnerChannel"] == "UC999"
    assert isinstance(insert_call["media_body"], FakeMediaFileUpload)
    assert insert_call["media_body"].path == "/tmp/banner.png"
    assert manager.service.channel_banners_resource.insert_request.execute_calls == 1


def test_third_party_links_tools_call_mocked_discovery_client() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    body = {"snippet": {"type": "channelToStoreLink"}}

    list_result = channels.youtube_third_party_links_list(
        account="primary",
        part="snippet,status,linkingToken",
        linking_token="token-1",
        type="channelToStoreLink",
        external_channel_id="UC999",
    )
    insert_result = channels.youtube_third_party_links_insert(
        account="primary",
        part="snippet,status",
        link_body=body,
        external_channel_id="UC999",
    )
    update_result = channels.youtube_third_party_links_update(
        account="primary",
        part="snippet,status",
        link_body=body,
        external_channel_id="UC999",
    )
    delete_result = channels.youtube_third_party_links_delete(
        account="primary",
        linking_token="token-1",
        type="channelToStoreLink",
        external_channel_id="UC999",
    )

    assert list_result == {"items": [{"linkingToken": "token-1"}]}
    assert insert_result == {"linkingToken": "token-2"}
    assert update_result == {"linkingToken": "token-3"}
    assert delete_result == {}
    assert guard_calls == ["primary", "primary", "primary"]
    assert tracker.preflight_calls == [
        ("primary", 1),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
    ]
    assert tracker.record_calls == [
        ("primary", 1),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
    ]
    assert manager.service.third_party_links_resource.list_calls == [
        {
            "part": "snippet,status,linkingToken",
            "linkingToken": "token-1",
            "type": "channelToStoreLink",
            "externalChannelId": "UC999",
        }
    ]
    assert manager.service.third_party_links_resource.insert_calls == [
        {"part": "snippet,status", "body": body, "externalChannelId": "UC999"}
    ]
    assert manager.service.third_party_links_resource.update_calls == [
        {"part": "snippet,status", "body": body, "externalChannelId": "UC999"}
    ]
    assert manager.service.third_party_links_resource.delete_calls == [
        {
            "linkingToken": "token-1",
            "type": "channelToStoreLink",
            "externalChannelId": "UC999",
        }
    ]
    assert manager.service.third_party_links_resource.list_request.execute_calls == 1
    assert manager.service.third_party_links_resource.insert_request.execute_calls == 1
    assert manager.service.third_party_links_resource.update_request.execute_calls == 1
    assert manager.service.third_party_links_resource.delete_request.execute_calls == 1


@pytest.mark.asyncio
async def test_all_channel_tools_are_registered_with_fastmcp() -> None:
    _ = _configure()

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    expected_names = {
        "youtube_channels_list",
        "youtube_channels_update",
        "youtube_channel_banners_insert",
        "youtube_third_party_links_list",
        "youtube_third_party_links_insert",
        "youtube_third_party_links_update",
        "youtube_third_party_links_delete",
    }

    assert expected_names <= registered.keys()
    assert registered["youtube_channels_list"].parameters["required"] == ["account"]
    assert registered["youtube_channels_update"].tags == {"mutating"}
    assert registered["youtube_channel_banners_insert"].tags == {"mutating"}
    assert registered["youtube_third_party_links_list"].parameters["required"] == ["account"]
    assert registered["youtube_third_party_links_insert"].tags == {"mutating"}
    assert registered["youtube_third_party_links_update"].tags == {"mutating"}
    assert registered["youtube_third_party_links_delete"].tags == {"mutating"}
