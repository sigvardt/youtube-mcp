"""Tests for the YouTube videos tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportImplicitOverride=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import ClassVar, cast
from unittest.mock import Mock

import pytest
from fastmcp import Context
from googleapiclient.errors import HttpError
from httplib2 import Response  # type: ignore[import-untyped]

import youtube_mcp.tools.videos as videos
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy, YouTubeScope

VIDEO_TOOL_NAMES = {
    "youtube_videos_list",
    "youtube_videos_insert",
    "youtube_videos_update",
    "youtube_videos_rate",
    "youtube_videos_getRating",
    "youtube_videos_reportAbuse",
    "youtube_videoTrainability_get",
}
MUTATING_TOOL_NAMES = {
    "youtube_videos_insert",
    "youtube_videos_update",
    "youtube_videos_rate",
    "youtube_videos_reportAbuse",
}
BLOCKED_PARTS = ("youtube", "videos", "delete")


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
    error: HttpError | None
    execute_calls: int

    def __init__(self, response: dict[str, object], *, error: HttpError | None = None) -> None:
        self.response = response
        self.error = error
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        if self.error is not None:
            raise self.error
        return self.response


class FakeUploadStatus:
    resumable_progress: int
    total_size: int

    def __init__(self, resumable_progress: int, total_size: int) -> None:
        self.resumable_progress = resumable_progress
        self.total_size = total_size

    def progress(self) -> float:
        return self.resumable_progress / self.total_size


class FakeUploadRequest:
    chunks: list[tuple[FakeUploadStatus, dict[str, object] | None]]
    next_chunk_calls: int

    def __init__(self, chunks: list[tuple[FakeUploadStatus, dict[str, object] | None]]) -> None:
        self.chunks = chunks
        self.next_chunk_calls = 0

    def next_chunk(self) -> tuple[FakeUploadStatus, dict[str, object] | None]:
        chunk = self.chunks[self.next_chunk_calls]
        self.next_chunk_calls += 1
        return chunk


class FakeMediaFileUpload:
    instances: ClassVar[list[FakeMediaFileUpload]] = []
    calls: ClassVar[list[dict[str, object]]] = []

    def __init__(self, filename: str, chunksize: int = -1, resumable: bool = False) -> None:
        self.filename = filename
        self.chunksize = chunksize
        self.resumable = resumable
        self.instances.append(self)
        self.calls.append(
            {
                "filename": filename,
                "chunksize": chunksize,
                "resumable": resumable,
            }
        )


class FakeVideosResource:
    list_request: FakeYouTubeRequest
    insert_request: FakeUploadRequest
    update_request: FakeYouTubeRequest
    rate_request: FakeYouTubeRequest
    get_rating_request: FakeYouTubeRequest
    report_abuse_request: FakeYouTubeRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    rate_calls: list[dict[str, object]]
    get_rating_calls: list[dict[str, object]]
    report_abuse_calls: list[dict[str, object]]

    def __init__(self) -> None:
        total_size = 3 * 1024 * 1024
        self.list_request = FakeYouTubeRequest({"items": [{"id": "video-list-1"}]})
        self.insert_request = FakeUploadRequest(
            [
                (FakeUploadStatus(1024 * 1024, total_size), None),
                (FakeUploadStatus(2 * 1024 * 1024, total_size), None),
                (FakeUploadStatus(total_size, total_size), {"id": "video-insert-1"}),
            ]
        )
        self.update_request = FakeYouTubeRequest({"id": "video-update-1"})
        self.rate_request = FakeYouTubeRequest({})
        self.get_rating_request = FakeYouTubeRequest({"items": [{"videoId": "video-123"}]})
        self.report_abuse_request = FakeYouTubeRequest({})
        self.list_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.rate_calls = []
        self.get_rating_calls = []
        self.report_abuse_calls = []

    def list(self, **kwargs: object) -> FakeYouTubeRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeUploadRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def update(self, **kwargs: object) -> FakeYouTubeRequest:
        self.update_calls.append(dict(kwargs))
        return self.update_request

    def rate(self, **kwargs: object) -> FakeYouTubeRequest:
        self.rate_calls.append(dict(kwargs))
        return self.rate_request

    def getRating(self, **kwargs: object) -> FakeYouTubeRequest:
        self.get_rating_calls.append(dict(kwargs))
        return self.get_rating_request

    def reportAbuse(self, **kwargs: object) -> FakeYouTubeRequest:
        self.report_abuse_calls.append(dict(kwargs))
        return self.report_abuse_request


class FakeChannelsResource:
    list_request: FakeYouTubeRequest
    list_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeYouTubeRequest(
            {
                "items": [
                    {
                        "contentDetails": {
                            "relatedPlaylists": {"uploads": "uploads-playlist-1"}
                        }
                    }
                ]
            }
        )
        self.list_calls = []

    def list(self, **kwargs: object) -> FakeYouTubeRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request


class FakePlaylistItemsResource:
    list_request: FakeYouTubeRequest
    list_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeYouTubeRequest(
            {
                "items": [
                    {"contentDetails": {"videoId": "video-upload-1"}},
                    {"contentDetails": {"videoId": "video-upload-2"}},
                ],
                "nextPageToken": "next-upload-page",
                "pageInfo": {"totalResults": 2, "resultsPerPage": 2},
            }
        )
        self.list_calls = []

    def list(self, **kwargs: object) -> FakeYouTubeRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request


class FakeVideoTrainabilityResource:
    get_request: FakeYouTubeRequest
    get_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.get_request = FakeYouTubeRequest(
            {"videoId": "video-123", "kind": "youtube#videoTrainability", "permitted": ["all"]}
        )
        self.get_calls = []

    def get(self, **kwargs: object) -> FakeYouTubeRequest:
        self.get_calls.append(dict(kwargs))
        return self.get_request


class FakeYouTubeService:
    videos_resource: FakeVideosResource
    channels_resource: FakeChannelsResource
    playlist_items_resource: FakePlaylistItemsResource
    video_trainability_resource: FakeVideoTrainabilityResource
    videos_calls: int
    channels_calls: int
    playlist_items_calls: int
    video_trainability_calls: int

    def __init__(self) -> None:
        self.videos_resource = FakeVideosResource()
        self.channels_resource = FakeChannelsResource()
        self.playlist_items_resource = FakePlaylistItemsResource()
        self.video_trainability_resource = FakeVideoTrainabilityResource()
        self.videos_calls = 0
        self.channels_calls = 0
        self.playlist_items_calls = 0
        self.video_trainability_calls = 0

    def videos(self) -> FakeVideosResource:
        self.videos_calls += 1
        return self.videos_resource

    def channels(self) -> FakeChannelsResource:
        self.channels_calls += 1
        return self.channels_resource

    def playlistItems(self) -> FakePlaylistItemsResource:
        self.playlist_items_calls += 1
        return self.playlist_items_resource

    def videoTrainability(self) -> FakeVideoTrainabilityResource:
        self.video_trainability_calls += 1
        return self.video_trainability_resource


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


def _blocked_tool_name() -> str:
    return "_".join(BLOCKED_PARTS)


def _blocked_method() -> str:
    return ".".join(BLOCKED_PARTS)


def test_videos_tools_call_mocked_discovery_client() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    video_body = {"id": "video-123", "snippet": {"title": "Updated title"}}
    abuse_body = {"videoId": "video-123", "reasonId": "V"}

    listed = videos.youtube_videos_list(
        account="primary",
        part="snippet,contentDetails,status",
        chart="mostPopular",
        id="video-123",
        my_rating="like",
        hl="en",
        max_height=1080,
        max_width=1920,
        max_results=25,
        on_behalf_of_content_owner="owner-1",
        page_token="page-2",
        region_code="US",
        video_category_id="22",
    )
    updated = videos.youtube_videos_update(
        account="primary",
        part="snippet,status",
        video_body=video_body,
        on_behalf_of_content_owner="owner-1",
    )
    rated = videos.youtube_videos_rate(account="primary", id="video-123", rating="like")
    rating = videos.youtube_videos_getRating(
        account="primary",
        id="video-123",
        on_behalf_of_content_owner="owner-1",
    )
    reported = videos.youtube_videos_reportAbuse(
        account="primary",
        abuse_report_body=abuse_body,
        on_behalf_of_content_owner="owner-1",
    )
    trainability = cast(
        videos.VideoTrainabilityResponse,
        videos.youtube_videoTrainability_get(account="primary", id="video-123"),
    )

    assert listed == {"items": [{"id": "video-list-1"}]}
    assert updated == {"id": "video-update-1"}
    assert rated == {}
    assert rating == {"items": [{"videoId": "video-123"}]}
    assert reported == {}
    assert trainability.video_id == "video-123"
    assert trainability.permitted == ["all"]
    assert manager.credentials_calls == [
        "primary",
        "primary",
        "primary",
        "primary",
        "primary",
        "primary",
    ]
    assert manager.youtube_calls == [
        "primary",
        "primary",
        "primary",
        "primary",
        "primary",
        "primary",
    ]
    assert guard_calls == ["primary", "primary", "primary"]
    assert tracker.preflight_calls == [
        ("primary", 3),
        ("primary", 50),
        ("primary", 50),
        ("primary", 1),
        ("primary", 50),
        ("primary", 1),
    ]
    assert tracker.record_calls == tracker.preflight_calls
    assert manager.service.videos_calls == 5
    assert manager.service.video_trainability_calls == 1
    assert manager.service.videos_resource.list_calls == [
        {
            "part": "snippet,contentDetails,status",
            "chart": "mostPopular",
            "id": "video-123",
            "myRating": "like",
            "hl": "en",
            "maxHeight": 1080,
            "maxWidth": 1920,
            "maxResults": 25,
            "onBehalfOfContentOwner": "owner-1",
            "pageToken": "page-2",
            "regionCode": "US",
            "videoCategoryId": "22",
        }
    ]
    assert manager.service.videos_resource.update_calls == [
        {"part": "snippet,status", "body": video_body, "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.videos_resource.rate_calls == [
        {"id": "video-123", "rating": "like"}
    ]
    assert manager.service.videos_resource.get_rating_calls == [
        {"id": "video-123", "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.videos_resource.report_abuse_calls == [
        {"body": abuse_body, "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.video_trainability_resource.get_calls == [
        {"id": "video-123"}
    ]


def test_videos_list_mine_traverses_uploads_playlist() -> None:
    manager, tracker = _configure()

    listed = videos.youtube_videos_list(
        account="primary",
        part="snippet,status",
        mine=True,
        max_results=2,
        page_token="uploads-page-2",
        on_behalf_of_content_owner="owner-1",
    )

    assert listed == {
        "items": [{"id": "video-list-1"}],
        "nextPageToken": "next-upload-page",
        "pageInfo": {"totalResults": 2, "resultsPerPage": 2},
    }
    assert tracker.preflight_calls == [("primary", 3)]
    assert tracker.record_calls == [("primary", 3)]
    assert manager.service.channels_resource.list_calls == [
        {
            "part": "contentDetails",
            "mine": True,
            "maxResults": 1,
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.playlist_items_resource.list_calls == [
        {
            "part": "contentDetails",
            "playlistId": "uploads-playlist-1",
            "maxResults": 2,
            "pageToken": "uploads-page-2",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.videos_resource.list_calls == [
        {
            "part": "snippet,status",
            "id": "video-upload-1,video-upload-2",
            "myRating": None,
            "hl": None,
            "maxHeight": None,
            "maxWidth": None,
            "onBehalfOfContentOwner": "owner-1",
            "regionCode": None,
            "videoCategoryId": None,
        }
    ]


def test_videos_list_mine_returns_empty_items_when_no_channel() -> None:
    fake_service = FakeYouTubeService()
    fake_service.channels_resource.list_request = FakeYouTubeRequest({"items": []})
    manager, tracker = _configure(service=fake_service)

    listed = videos.youtube_videos_list(account="primary", part="snippet,status", mine=True)

    assert listed == {"items": []}
    assert tracker.preflight_calls == [("primary", 3)]
    assert tracker.record_calls == [("primary", 3)]
    assert manager.service.channels_resource.list_calls == [
        {
            "part": "contentDetails",
            "mine": True,
            "maxResults": 1,
            "onBehalfOfContentOwner": None,
        }
    ]
    assert manager.service.playlist_items_resource.list_calls == []
    assert manager.service.videos_resource.list_calls == []


def test_videos_list_mine_returns_empty_items_when_uploads_playlist_missing() -> None:
    fake_service = FakeYouTubeService()
    fake_service.channels_resource.list_request = FakeYouTubeRequest(
        {"items": [{"contentDetails": {"relatedPlaylists": {}}}]}
    )
    manager, tracker = _configure(service=fake_service)

    listed = videos.youtube_videos_list(account="primary", part="snippet,status", mine=True)

    assert listed == {"items": []}
    assert tracker.preflight_calls == [("primary", 3)]
    assert tracker.record_calls == [("primary", 3)]
    assert manager.service.playlist_items_resource.list_calls == []
    assert manager.service.videos_resource.list_calls == []


def test_upload_progress(monkeypatch: pytest.MonkeyPatch) -> None:
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

    FakeMediaFileUpload.instances = []
    FakeMediaFileUpload.calls = []
    monkeypatch.setattr(videos, "MediaFileUpload", FakeMediaFileUpload)
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
    body = {"snippet": {"title": "Upload title"}, "status": {"privacyStatus": "private"}}
    report_progress = Mock()
    ctx = cast(Context, cast(object, SimpleNamespace(report_progress=report_progress)))

    result = videos.youtube_videos_insert(
        account="primary",
        part="snippet,status",
        video_body=body,
        file_path="/tmp/video.mp4",
        notify_subscribers=False,
        on_behalf_of_content_owner="owner-1",
        on_behalf_of_content_owner_channel="channel-1",
        ctx=ctx,
    )

    assert result == {"id": "video-insert-1"}
    assert events == ["credentials:primary", "guard:primary", "service:primary"]
    assert tracker.preflight_calls == [("primary", 1600)]
    assert tracker.record_calls == [("primary", 1600)]
    assert FakeMediaFileUpload.calls == [
        {"filename": "/tmp/video.mp4", "chunksize": 8 * 1024 * 1024, "resumable": True}
    ]
    assert fake_service.videos_resource.insert_calls == [
        {
            "part": "snippet,status",
            "body": body,
            "media_body": FakeMediaFileUpload.instances[0],
            "notifySubscribers": False,
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOfContentOwnerChannel": "channel-1",
        }
    ]
    assert fake_service.videos_resource.insert_request.next_chunk_calls == 3
    assert report_progress.call_args_list[0].kwargs == {
        "progress": 1024 * 1024,
        "total": 3 * 1024 * 1024,
    }
    assert report_progress.call_args_list[1].kwargs == {
        "progress": 2 * 1024 * 1024,
        "total": 3 * 1024 * 1024,
    }
    assert report_progress.call_args_list[2].kwargs == {
        "progress": 3 * 1024 * 1024,
        "total": 3 * 1024 * 1024,
    }


def test_videoTrainability_response_model_accepts_framework_error_envelope() -> None:
    response = videos.VideoTrainabilityResponse.model_validate(
        {"error": {"status": 404, "reason": "notFound", "message": "Video not found"}}
    )

    assert response.error is not None
    assert response.error.status == 404
    assert response.error.reason == "notFound"
    assert response.permitted == []
    success_dump = videos.VideoTrainabilityResponse().model_dump(mode="json", by_alias=True)
    assert "error" not in success_dump
    assert success_dump["permitted"] == []


@pytest.mark.asyncio
async def test_videoTrainability_http_error_matches_registered_output_schema() -> None:
    manager, tracker = _configure()
    manager.service.video_trainability_resource.get_request.error = _http_error(
        404,
        "notFound",
        "Video not found",
    )

    result = await mcp.call_tool(
        "youtube_videoTrainability_get",
        {"account": "primary", "id": "video-missing"},
    )

    assert result.structured_content == {
        "error": {"status": 404, "reason": "notFound", "message": "Video not found"}
    }
    assert tracker.record_calls == []


@pytest.mark.asyncio
async def test_videoTrainability_success_omits_error_from_structured_content() -> None:
    _manager, _tracker = _configure()

    result = await mcp.call_tool(
        "youtube_videoTrainability_get",
        {"account": "primary", "id": "video-123"},
    )

    assert result.structured_content is not None
    assert "error" not in result.structured_content
    assert result.structured_content["videoId"] == "video-123"


@pytest.mark.asyncio
async def test_all_video_tool_names_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(videos.youtube_videos_list).parameters) == [
        "account",
        "part",
        "chart",
        "id",
        "mine",
        "my_rating",
        "hl",
        "max_height",
        "max_width",
        "max_results",
        "on_behalf_of_content_owner",
        "page_token",
        "region_code",
        "video_category_id",
        "ctx",
    ]
    assert list(inspect.signature(videos.youtube_videos_insert).parameters) == [
        "account",
        "part",
        "video_body",
        "file_path",
        "notify_subscribers",
        "on_behalf_of_content_owner",
        "on_behalf_of_content_owner_channel",
        "ctx",
    ]
    assert list(inspect.signature(videos.youtube_videos_getRating).parameters) == [
        "account",
        "id",
        "on_behalf_of_content_owner",
        "ctx",
    ]
    assert list(inspect.signature(videos.youtube_videos_reportAbuse).parameters) == [
        "account",
        "abuse_report_body",
        "on_behalf_of_content_owner",
        "ctx",
    ]
    assert list(inspect.signature(videos.youtube_videoTrainability_get).parameters) == [
        "account",
        "id",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert VIDEO_TOOL_NAMES <= registered.keys()
    for tool_name in MUTATING_TOOL_NAMES:
        assert registered[tool_name].tags == {"mutating"}
    assert registered["youtube_videos_list"].tags == set()
    assert registered["youtube_videos_getRating"].tags == set()
    assert registered["youtube_videoTrainability_get"].tags == set()
    output_schema = registered["youtube_videoTrainability_get"].output_schema
    assert output_schema is not None
    assert "error" in output_schema["properties"]
    assert registered["youtube_videos_insert"].parameters["required"] == [
        "account",
        "part",
        "video_body",
        "file_path",
    ]
    assert "ctx" not in registered["youtube_videos_insert"].parameters["properties"]
    assert registered["youtube_videos_insert"].meta == {
        "api": "youtube",
        "method": "youtube.videos.insert",
        "scopes": [YouTubeScope.FORCE_SSL.value],
        "cost": 1600,
    }


@pytest.mark.asyncio
async def test_blocked_video_endpoint_is_absent_from_module_and_registry() -> None:
    _ = _configure()
    blocked_name = _blocked_tool_name()
    blocked_method = _blocked_method()

    assert blocked_name not in vars(videos)
    assert not hasattr(videos, blocked_name)

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    registered_methods = {
        tool.meta["method"] for tool in tools if tool.meta is not None and "method" in tool.meta
    }

    assert blocked_name not in registered
    assert blocked_method not in registered_methods
