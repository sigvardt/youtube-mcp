"""Tests for the YouTube playlistImages tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportImplicitOverride=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import ClassVar, cast

import pytest

import youtube_mcp.tools.playlist_images as playlist_images
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy, YouTubeScope

PLAYLIST_IMAGE_TOOL_NAMES = {
    "youtube_playlistImages_list",
    "youtube_playlistImages_insert",
    "youtube_playlistImages_update",
    "youtube_playlistImages_delete",
}
MUTATING_TOOL_NAMES = PLAYLIST_IMAGE_TOOL_NAMES - {"youtube_playlistImages_list"}


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
    response: object
    execute_calls: int

    def __init__(self, response: object) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> object:
        self.execute_calls += 1
        return self.response


class FakeMediaFileUpload:
    instances: ClassVar[list[FakeMediaFileUpload]] = []

    def __init__(self, filename: str, resumable: bool = False) -> None:
        self.filename = filename
        self.resumable = resumable
        self.instances.append(self)


class FakePlaylistImagesResource:
    list_request: FakeYouTubeRequest
    insert_request: FakeYouTubeRequest
    update_request: FakeYouTubeRequest
    delete_request: FakeYouTubeRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        image: dict[str, object] = {
            "id": "PL-hero",
            "snippet": {"playlistId": "PL123", "type": "hero"},
        }
        self.list_request = FakeYouTubeRequest({"items": [image]})
        self.insert_request = FakeYouTubeRequest(image)
        self.update_request = FakeYouTubeRequest(image)
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
    playlist_images_resource: FakePlaylistImagesResource
    playlist_images_calls: int

    def __init__(self) -> None:
        self.playlist_images_resource = FakePlaylistImagesResource()
        self.playlist_images_calls = 0

    def playlistImages(self) -> FakePlaylistImagesResource:
        self.playlist_images_calls += 1
        return self.playlist_images_resource


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

    def get_youtube_service(self, key: str) -> FakeYouTubeService:
        self.youtube_calls.append(key)
        self._services[(key, "youtube")] = self.service
        return self.service

    def get_analytics_service(self, key: str) -> object:
        _ = key
        return object()

    def get_reporting_service(self, key: str) -> object:
        _ = key
        return object()


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(max_attempts=3, initial_wait=0.001, max_wait=0.01, jitter=False)


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


def test_playlist_images_tools_call_mocked_discovery_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeMediaFileUpload.instances = []
    monkeypatch.setattr(playlist_images, "MediaFileUpload", FakeMediaFileUpload)
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    image_body = playlist_images.PlaylistImageResource(
        snippet=playlist_images.PlaylistImageSnippet.model_validate(
            {"playlistId": "PL123", "type": "hero"}
        )
    )

    listed = cast(
        playlist_images.PlaylistImageListResponse,
        playlist_images.youtube_playlistImages_list(
        account="primary",
        part="snippet",
        parent="playlists/PL123",
        page_token="page-2",
        max_results=5,
        on_behalf_of_content_owner="owner-1",
        ),
    )
    inserted = cast(
        playlist_images.PlaylistImageResource,
        playlist_images.youtube_playlistImages_insert(
        account="primary",
        part="snippet",
        image_body=image_body,
        image_file_path="/tmp/cover.png",
        on_behalf_of_content_owner="owner-1",
        ),
    )
    updated = cast(
        playlist_images.PlaylistImageResource,
        playlist_images.youtube_playlistImages_update(
        account="primary",
        part="snippet",
        image_body=image_body,
        image_file_path="/tmp/cover2.png",
        on_behalf_of_content_owner="owner-1",
        ),
    )
    deleted = cast(
        playlist_images.EmptyResponse,
        playlist_images.youtube_playlistImages_delete(
        account="primary",
        id="PL-hero",
        on_behalf_of_content_owner="owner-1",
        ),
    )

    assert listed.items[0].id == "PL-hero"
    assert inserted.id == "PL-hero"
    assert updated.id == "PL-hero"
    assert deleted == playlist_images.EmptyResponse()
    assert guard_calls == ["primary", "primary", "primary"]
    assert tracker.preflight_calls == [
        ("primary", 1),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
    ]
    assert manager.service.playlist_images_calls == 4
    assert FakeMediaFileUpload.instances[0].filename == "/tmp/cover.png"
    assert FakeMediaFileUpload.instances[1].filename == "/tmp/cover2.png"
    assert manager.service.playlist_images_resource.list_calls == [
        {
            "part": "snippet",
            "parent": "playlists/PL123",
            "pageToken": "page-2",
            "maxResults": 5,
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.playlist_images_resource.insert_calls == [
        {
            "part": "snippet",
            "body": {"snippet": {"playlistId": "PL123", "type": "hero"}},
            "media_body": FakeMediaFileUpload.instances[0],
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.playlist_images_resource.update_calls == [
        {
            "part": "snippet",
            "body": {"snippet": {"playlistId": "PL123", "type": "hero"}},
            "media_body": FakeMediaFileUpload.instances[1],
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.playlist_images_resource.delete_calls == [
        {
            "id": "PL-hero",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]


@pytest.mark.parametrize("empty_body", ["", None])
def test_playlistImages_delete_normalizes_empty_response_body(
    empty_body: object,
) -> None:
    manager, _ = _configure()
    manager.service.playlist_images_resource.delete_request.response = empty_body

    result = playlist_images.youtube_playlistImages_delete(
        account="primary",
        id="PL-hero",
        on_behalf_of_content_owner="owner-1",
    )

    assert result == playlist_images.EmptyResponse()


def test_playlistImages_update_does_not_forward_on_behalf_of_content_owner_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeMediaFileUpload.instances = []
    monkeypatch.setattr(playlist_images, "MediaFileUpload", FakeMediaFileUpload)
    manager, _ = _configure()
    image_body = playlist_images.PlaylistImageResource(
        snippet=playlist_images.PlaylistImageSnippet.model_validate(
            {"playlistId": "PL123", "type": "hero"}
        )
    )

    result = cast(
        playlist_images.PlaylistImageResource,
        playlist_images.youtube_playlistImages_update(
        account="primary",
        part="snippet",
        image_body=image_body,
        image_file_path="/tmp/cover2.png",
        on_behalf_of_content_owner="owner-1",
        ),
    )

    assert result.id == "PL-hero"
    assert (
        "onBehalfOfContentOwnerChannel"
        not in manager.service.playlist_images_resource.update_calls[0]
    )


def test_playlistImages_delete_does_not_forward_on_behalf_of_content_owner_channel(
) -> None:
    manager, _ = _configure()

    result = playlist_images.youtube_playlistImages_delete(
        account="primary",
        id="PL-hero",
        on_behalf_of_content_owner="owner-1",
    )

    assert result == playlist_images.EmptyResponse()
    assert (
        "onBehalfOfContentOwnerChannel"
        not in manager.service.playlist_images_resource.delete_calls[0]
    )


@pytest.mark.asyncio
async def test_registered() -> None:
    _ = _configure()

    assert list(inspect.signature(playlist_images.youtube_playlistImages_list).parameters) == [
        "account",
        "part",
        "parent",
        "page_token",
        "max_results",
        "on_behalf_of_content_owner",
        "ctx",
    ]
    assert list(inspect.signature(playlist_images.youtube_playlistImages_insert).parameters) == [
        "account",
        "part",
        "image_body",
        "image_file_path",
        "on_behalf_of_content_owner",
        "ctx",
    ]
    assert list(inspect.signature(playlist_images.youtube_playlistImages_update).parameters) == [
        "account",
        "part",
        "image_body",
        "image_file_path",
        "on_behalf_of_content_owner",
        "ctx",
    ]
    assert list(inspect.signature(playlist_images.youtube_playlistImages_delete).parameters) == [
        "account",
        "id",
        "on_behalf_of_content_owner",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert PLAYLIST_IMAGE_TOOL_NAMES <= registered.keys()
    assert registered["youtube_playlistImages_list"].tags == set()
    for tool_name in MUTATING_TOOL_NAMES:
        tool = registered[tool_name]
        assert tool.tags == {"mutating"}
        assert "ctx" not in tool.parameters["properties"]
    assert registered["youtube_playlistImages_list"].meta == {
        "api": "youtube",
        "method": "youtube.playlistImages.list",
        "scopes": [YouTubeScope.READONLY.value],
        "cost": 1,
    }
