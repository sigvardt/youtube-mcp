"""Tests for the YouTube playlistImages tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportImplicitOverride=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from typing import ClassVar, cast

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response  # type: ignore[import-untyped]

import youtube_mcp.tools.playlist_images as playlist_images
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import GoogleApiError, RetryPolicy, YouTubeScope

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
    error: HttpError | None
    execute_calls: int

    def __init__(self, response: object, *, error: HttpError | None = None) -> None:
        self.response = response
        self.error = error
        self.execute_calls = 0

    def execute(self) -> object:
        self.execute_calls += 1
        if self.error is not None:
            raise self.error
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


def _http_error(status: int, body_reason: str, message: str) -> HttpError:
    response = Response({"status": str(status)})
    response.reason = "HTTP Error"
    body = json.dumps(
        {"error": {"errors": [{"reason": body_reason}], "message": message}}
    ).encode("utf-8")
    return HttpError(response, body)


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
    image_body = playlist_images.PlaylistImageBody(
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


def test_playlistImages_direct_resource_subclass_input_does_not_forward_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeMediaFileUpload.instances = []
    monkeypatch.setattr(playlist_images, "MediaFileUpload", FakeMediaFileUpload)
    manager, _ = _configure()
    image_body = playlist_images.PlaylistImageResource(
        snippet=playlist_images.PlaylistImageSnippet.model_validate(
            {"playlistId": "PL123", "type": "hero"}
        ),
        error=GoogleApiError(status=404, reason="notFound", message="ignored"),
    )

    _ = playlist_images.youtube_playlistImages_insert(
        account="primary",
        part="snippet",
        image_body=image_body,
        image_file_path="/tmp/cover.png",
    )

    assert manager.service.playlist_images_resource.insert_calls[0]["body"] == {
        "snippet": {"playlistId": "PL123", "type": "hero"}
    }


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


def test_playlistImages_response_models_accept_framework_error_envelope() -> None:
    error_body: dict[str, object] = {
        "error": {"status": 404, "reason": "notFound", "message": "Image not found"}
    }

    listed = playlist_images.PlaylistImageListResponse.model_validate(error_body)
    image = playlist_images.PlaylistImageResource.model_validate(error_body)
    empty = playlist_images.EmptyResponse.model_validate(error_body)

    assert listed.error is not None
    assert listed.error.status == 404
    assert listed.error.reason == "notFound"
    assert listed.items == []
    assert image.error is not None
    assert image.error.message == "Image not found"
    assert empty.error is not None
    assert empty.error.status == 404
    list_dump = playlist_images.PlaylistImageListResponse().model_dump(mode="json")
    resource_dump = playlist_images.PlaylistImageResource().model_dump(mode="json")
    assert "error" not in list_dump
    assert list_dump["items"] == []
    assert "error" not in resource_dump
    assert playlist_images.EmptyResponse().model_dump(mode="json") == {}


def test_playlistImages_body_rejects_framework_error_envelope() -> None:
    with pytest.raises(ValueError):
        _ = playlist_images.PlaylistImageBody.model_validate(
            {"error": {"status": 404, "reason": "notFound", "message": "Image not found"}}
        )


@pytest.mark.asyncio
async def test_playlistImages_list_http_error_matches_registered_output_schema() -> None:
    manager, tracker = _configure()
    manager.service.playlist_images_resource.list_request.error = _http_error(
        404,
        "notFound",
        "Image not found",
    )

    result = await mcp.call_tool(
        "youtube_playlistImages_list",
        {"account": "primary", "part": "snippet"},
    )

    assert result.structured_content == {
        "error": {"status": 404, "reason": "notFound", "message": "Image not found"}
    }
    assert tracker.record_calls == []


@pytest.mark.asyncio
async def test_playlistImages_list_success_omits_error_keys_from_structured_content() -> None:
    _manager, _tracker = _configure()

    result = await mcp.call_tool(
        "youtube_playlistImages_list",
        {"account": "primary", "part": "snippet"},
    )

    assert result.structured_content is not None
    assert "error" not in result.structured_content
    items = cast(list[object], result.structured_content["items"])
    first_item = cast(dict[str, object], items[0])
    assert "error" not in first_item


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
    assert '"error"' not in json.dumps(registered["youtube_playlistImages_insert"].parameters)
    assert '"error"' not in json.dumps(registered["youtube_playlistImages_update"].parameters)
    for tool_name in PLAYLIST_IMAGE_TOOL_NAMES:
        output_schema = registered[tool_name].output_schema
        assert output_schema is not None
        assert "error" in output_schema["properties"]
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
