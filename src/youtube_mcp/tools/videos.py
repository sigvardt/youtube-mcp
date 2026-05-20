"""YouTube Data API videos tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, Literal, cast

from fastmcp import Context
from googleapiclient.http import MediaFileUpload
from pydantic import BaseModel, ConfigDict, Field

from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import UploadProgress, YouTubeScope

UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024
VideoRating = Literal["like", "dislike", "none"]


class VideoTrainabilityResponse(BaseModel):
    """Stable videoTrainability.get response model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", populate_by_name=True)

    video_id: str | None = Field(default=None, alias="videoId")
    kind: str | None = None
    etag: str | None = None
    permitted: list[str] = Field(default_factory=list)


def _youtube_service(account: str) -> Any:
    framework_ctx = _require_context()
    account_manager = cast(Any, framework_ctx.account_manager)
    cache_key = (account, "youtube")
    cached_services = cast(
        dict[tuple[str, str], Any] | None,
        getattr(account_manager, "_services", None),
    )
    if cached_services is not None and cache_key in cached_services:
        return cached_services[cache_key]

    return account_manager.get_youtube_service(account)


def _as_mapping(value: object) -> Mapping[str, object] | None:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else None


def _uploads_playlist_id(response: Mapping[str, object]) -> str | None:
    raw_items = response.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return None
    items = cast(list[object], raw_items)

    first_item = _as_mapping(items[0])
    content_details = _as_mapping(first_item.get("contentDetails")) if first_item else None
    related_playlists = (
        _as_mapping(content_details.get("relatedPlaylists")) if content_details else None
    )
    uploads = related_playlists.get("uploads") if related_playlists else None
    return uploads if isinstance(uploads, str) and uploads else None


def _playlist_video_ids(response: Mapping[str, object]) -> list[str]:
    raw_items = response.get("items")
    if not isinstance(raw_items, list):
        return []
    items = cast(list[object], raw_items)

    video_ids: list[str] = []
    for item in items:
        item_mapping = _as_mapping(item)
        content_details = _as_mapping(item_mapping.get("contentDetails")) if item_mapping else None
        video_id = content_details.get("videoId") if content_details else None
        if isinstance(video_id, str) and video_id:
            video_ids.append(video_id)
    return video_ids


def _copy_uploads_pagination(
    videos_response: dict[str, object],
    playlist_response: Mapping[str, object],
) -> dict[str, object]:
    for key in ("nextPageToken", "prevPageToken", "pageInfo"):
        value = playlist_response.get(key)
        if value is not None:
            videos_response[key] = value
    return videos_response


def _media_upload(file_path: str) -> Any:
    return MediaFileUpload(file_path, chunksize=UPLOAD_CHUNK_SIZE, resumable=True)


def _status_int(status: Any, attribute: str) -> int:
    value = getattr(status, attribute, 0)
    return value if isinstance(value, int) and value >= 0 else 0


def _progress_fraction(status: Any) -> float:
    progress_method = getattr(status, "progress", None)
    progress_value = progress_method() if callable(progress_method) else 0.0
    if isinstance(progress_value, int | float):
        return min(max(float(progress_value), 0.0), 1.0)
    return 0.0


def _upload_progress(status: Any) -> UploadProgress:
    fraction = _progress_fraction(status)
    bytes_uploaded = _status_int(status, "resumable_progress")
    bytes_total = _status_int(status, "total_size")
    if bytes_uploaded == 0 and bytes_total > 0:
        bytes_uploaded = int(bytes_total * fraction)
    if bytes_total == 0 and bytes_uploaded > 0 and fraction > 0:
        bytes_total = int(bytes_uploaded / fraction)
    if bytes_total == 0:
        bytes_total = bytes_uploaded
    return UploadProgress(
        bytes_uploaded=bytes_uploaded,
        bytes_total=bytes_total,
        percent=round(fraction * 100.0, 6),
    )


def _report_upload_progress(ctx: Context | None, status: Any) -> None:
    if ctx is None or status is None:
        return

    upload_progress = _upload_progress(status)
    _ = ctx.report_progress(
        progress=upload_progress.bytes_uploaded,
        total=upload_progress.bytes_total,
    )


@youtube_tool(
    name="youtube_videos_list",
    api="youtube",
    method="youtube.videos.list",
    scopes=[YouTubeScope.READONLY],
    cost=3,
)
def youtube_videos_list(
    account: str,
    part: str,
    chart: str | None = None,
    id: str | None = None,
    mine: bool = False,
    my_rating: str | None = None,
    hl: str | None = None,
    max_height: int | None = None,
    max_width: int | None = None,
    max_results: int | None = None,
    on_behalf_of_content_owner: str | None = None,
    page_token: str | None = None,
    region_code: str | None = None,
    video_category_id: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List videos, including mine=True uploads traversal at 3 quota units."""
    service = _youtube_service(account)
    if mine and id is None and chart is None:
        channels_response = cast(
            dict[str, object],
            service.channels()
            .list(
                part="contentDetails",
                mine=True,
                maxResults=1,
                onBehalfOfContentOwner=on_behalf_of_content_owner,
            )
            .execute(),
        )
        uploads_playlist_id = _uploads_playlist_id(channels_response)
        if uploads_playlist_id is None:
            return {"items": []}

        playlist_response = cast(
            dict[str, object],
            service.playlistItems()
            .list(
                part="contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=max_results,
                pageToken=page_token,
                onBehalfOfContentOwner=on_behalf_of_content_owner,
            )
            .execute(),
        )
        video_ids = _playlist_video_ids(playlist_response)
        if not video_ids:
            return _copy_uploads_pagination({"items": []}, playlist_response)

        videos_response = cast(
            dict[str, object],
            service.videos()
            .list(
                part=part,
                id=",".join(video_ids),
                myRating=my_rating,
                hl=hl,
                maxHeight=max_height,
                maxWidth=max_width,
                onBehalfOfContentOwner=on_behalf_of_content_owner,
                regionCode=region_code,
                videoCategoryId=video_category_id,
            )
            .execute(),
        )
        return _copy_uploads_pagination(videos_response, playlist_response)

    return cast(
        dict[str, object],
        service.videos()
        .list(
            part=part,
            chart=chart,
            id=id,
            myRating=my_rating,
            hl=hl,
            maxHeight=max_height,
            maxWidth=max_width,
            maxResults=max_results,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            pageToken=page_token,
            regionCode=region_code,
            videoCategoryId=video_category_id,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_videos_insert",
    api="youtube",
    method="youtube.videos.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=1600,
    mutating=True,
)
def youtube_videos_insert(
    account: str,
    part: str,
    video_body: dict[str, Any],
    file_path: str,
    notify_subscribers: bool | None = None,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Upload a new video with metadata and privacy controls."""
    service = _youtube_service(account)
    request = service.videos().insert(
        part=part,
        body=video_body,
        media_body=_media_upload(file_path),
        notifySubscribers=notify_subscribers,
        onBehalfOfContentOwner=on_behalf_of_content_owner,
        onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
    )

    response: dict[str, object] | None = None
    while response is None:
        status, maybe_response = cast(
            tuple[Any, dict[str, object] | None],
            request.next_chunk(),
        )
        _report_upload_progress(ctx, status)
        response = maybe_response

    return response


@youtube_tool(
    name="youtube_videos_update",
    api="youtube",
    method="youtube.videos.update",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_videos_update(
    account: str,
    part: str,
    video_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a video's metadata."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.videos()
        .update(
            part=part,
            body=video_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_videos_rate",
    api="youtube",
    method="youtube.videos.rate",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_videos_rate(
    account: str,
    id: str,
    rating: VideoRating,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Rate a video."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.videos()
        .rate(
            id=id,
            rating=rating,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_videos_getRating",
    api="youtube",
    method="youtube.videos.getRating",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_videos_getRating(
    account: str,
    id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Get authenticated-user ratings for videos."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.videos()
        .getRating(
            id=id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_videos_reportAbuse",
    api="youtube",
    method="youtube.videos.reportAbuse",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_videos_reportAbuse(
    account: str,
    abuse_report_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Report abusive video content."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.videos()
        .reportAbuse(
            body=abuse_report_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_videoTrainability_get",
    api="youtube",
    method="youtube.videoTrainability.get",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_videoTrainability_get(
    account: str,
    id: str,
    ctx: Context | None = None,
) -> VideoTrainabilityResponse:
    """Get a video's third-party training permission state."""

    service = _youtube_service(account)
    response = cast(
        dict[str, Any],
        service.videoTrainability()
        .get(
            id=id,
        )
        .execute(),
    )
    return VideoTrainabilityResponse.model_validate(response)


_BLOCKED_TOOL_NAME = "_".join(("youtube", "videos", "delete"))
_provider = getattr(mcp, "_local_provider", None)
_components = getattr(_provider, "_components", {})
assert _BLOCKED_TOOL_NAME not in {
    getattr(tool, "name", "") for key, tool in _components.items() if str(key).startswith("tool:")
}, "Video deletion must not be registered"
