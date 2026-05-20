"""Tests for the YouTube thumbnails and watermarks tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportImplicitOverride=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import ClassVar

import pytest

import youtube_mcp.tools.video_assets as video_assets
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy, YouTubeScope

VIDEO_ASSET_TOOL_NAMES = {
    "youtube_thumbnails_set",
    "youtube_watermarks_set",
    "youtube_watermarks_unset",
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


class FakeThumbnailsResource:
    set_request: FakeYouTubeRequest
    set_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.set_request = FakeYouTubeRequest({"items": [{"default": {"url": "thumb.jpg"}}]})
        self.set_calls = []

    def set(self, **kwargs: object) -> FakeYouTubeRequest:
        self.set_calls.append(dict(kwargs))
        return self.set_request


class FakeWatermarksResource:
    set_request: FakeYouTubeRequest
    unset_request: FakeYouTubeRequest
    set_calls: list[dict[str, object]]
    unset_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.set_request = FakeYouTubeRequest({"kind": "youtube#watermark"})
        self.unset_request = FakeYouTubeRequest({"status": "unset"})
        self.set_calls = []
        self.unset_calls = []

    def set(self, **kwargs: object) -> FakeYouTubeRequest:
        self.set_calls.append(dict(kwargs))
        return self.set_request

    def unset(self, **kwargs: object) -> FakeYouTubeRequest:
        self.unset_calls.append(dict(kwargs))
        return self.unset_request


class FakeYouTubeService:
    thumbnails_resource: FakeThumbnailsResource
    watermarks_resource: FakeWatermarksResource
    thumbnails_calls: int
    watermarks_calls: int

    def __init__(self) -> None:
        self.thumbnails_resource = FakeThumbnailsResource()
        self.watermarks_resource = FakeWatermarksResource()
        self.thumbnails_calls = 0
        self.watermarks_calls = 0

    def thumbnails(self) -> FakeThumbnailsResource:
        self.thumbnails_calls += 1
        return self.thumbnails_resource

    def watermarks(self) -> FakeWatermarksResource:
        self.watermarks_calls += 1
        return self.watermarks_resource


class FakeAccountManager:
    service: FakeYouTubeService
    _services: dict[tuple[str, str], FakeYouTubeService]
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
    calls: ClassVar[list[dict[str, object]]] = []
    filename: str
    resumable: bool

    def __init__(self, filename: str, resumable: bool = False) -> None:
        self.filename = filename
        self.resumable = resumable
        self.calls.append({"filename": filename, "resumable": resumable})


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


def test_thumbnails_set_uses_media_file_upload_and_mocked_discovery_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    FakeMediaFileUpload.calls = []
    monkeypatch.setattr(video_assets, "MediaFileUpload", FakeMediaFileUpload)

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

    result = video_assets.youtube_thumbnails_set(
        account="primary",
        video_id="video-123",
        image_file_path="/tmp/thumbnail.gif",
        on_behalf_of_content_owner="owner-1",
    )

    assert result == {"items": [{"default": {"url": "thumb.jpg"}}]}
    assert events == ["credentials:primary", "guard:primary", "service:primary"]
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert FakeMediaFileUpload.calls == [{"filename": "/tmp/thumbnail.gif", "resumable": True}]
    assert manager.service.thumbnails_calls == 1
    set_call = manager.service.thumbnails_resource.set_calls[0]
    assert set_call["videoId"] == "video-123"
    assert set_call["onBehalfOfContentOwner"] == "owner-1"
    assert isinstance(set_call["media_body"], FakeMediaFileUpload)
    assert manager.service.thumbnails_resource.set_request.execute_calls == 1


def test_watermarks_set_uses_body_and_media_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeMediaFileUpload.calls = []
    monkeypatch.setattr(video_assets, "MediaFileUpload", FakeMediaFileUpload)
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    body = {"timing": {"type": "offsetFromStart", "offsetMs": "1000"}}

    result = video_assets.youtube_watermarks_set(
        account="primary",
        channel_id="UC123",
        watermark_body=body,
        image_file_path="/tmp/watermark.png",
        on_behalf_of_content_owner="owner-1",
    )

    assert result == {"kind": "youtube#watermark"}
    assert guard_calls == ["primary"]
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert FakeMediaFileUpload.calls == [{"filename": "/tmp/watermark.png", "resumable": True}]
    assert manager.service.watermarks_calls == 1
    set_call = manager.service.watermarks_resource.set_calls[0]
    assert set_call["channelId"] == "UC123"
    assert set_call["body"] == body
    assert set_call["onBehalfOfContentOwner"] == "owner-1"
    assert isinstance(set_call["media_body"], FakeMediaFileUpload)
    assert manager.service.watermarks_resource.set_request.execute_calls == 1


def test_watermarks_unset_calls_mocked_discovery_client_without_media() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)

    result = video_assets.youtube_watermarks_unset(
        account="primary",
        channel_id="UC123",
        on_behalf_of_content_owner="owner-1",
    )

    assert result == {"status": "unset"}
    assert guard_calls == ["primary"]
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert manager.service.watermarks_calls == 1
    assert manager.service.watermarks_resource.unset_calls == [
        {"channelId": "UC123", "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.watermarks_resource.unset_request.execute_calls == 1


@pytest.mark.asyncio
async def test_all_video_asset_tools_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(video_assets.youtube_thumbnails_set).parameters) == [
        "account",
        "video_id",
        "image_file_path",
        "on_behalf_of_content_owner",
        "ctx",
    ]
    assert list(inspect.signature(video_assets.youtube_watermarks_set).parameters) == [
        "account",
        "channel_id",
        "watermark_body",
        "image_file_path",
        "on_behalf_of_content_owner",
        "ctx",
    ]
    assert list(inspect.signature(video_assets.youtube_watermarks_unset).parameters) == [
        "account",
        "channel_id",
        "on_behalf_of_content_owner",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert VIDEO_ASSET_TOOL_NAMES <= registered.keys()
    for tool_name in VIDEO_ASSET_TOOL_NAMES:
        assert registered[tool_name].tags == {"mutating"}
        assert "ctx" not in registered[tool_name].parameters["properties"]
    assert registered["youtube_thumbnails_set"].parameters["required"] == [
        "account",
        "video_id",
        "image_file_path",
    ]
    assert registered["youtube_watermarks_set"].parameters["required"] == [
        "account",
        "channel_id",
        "watermark_body",
        "image_file_path",
    ]
    assert registered["youtube_watermarks_unset"].parameters["required"] == [
        "account",
        "channel_id",
    ]
    assert registered["youtube_thumbnails_set"].meta == {
        "api": "youtube",
        "method": "youtube.thumbnails.set",
        "scopes": [YouTubeScope.FORCE_SSL.value],
        "cost": 50,
    }
    assert registered["youtube_watermarks_set"].meta == {
        "api": "youtube",
        "method": "youtube.watermarks.set",
        "scopes": [YouTubeScope.FORCE_SSL.value],
        "cost": 50,
    }
    assert registered["youtube_watermarks_unset"].meta == {
        "api": "youtube",
        "method": "youtube.watermarks.unset",
        "scopes": [YouTubeScope.FORCE_SSL.value],
        "cost": 50,
    }
