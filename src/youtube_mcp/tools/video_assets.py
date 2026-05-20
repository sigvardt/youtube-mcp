"""YouTube Data API thumbnails and watermarks tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

from typing import Any, cast

from fastmcp import Context
from googleapiclient.http import MediaFileUpload

from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import YouTubeScope


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


def _image_upload(image_file_path: str) -> Any:
    return MediaFileUpload(image_file_path, resumable=True)


@youtube_tool(
    name="youtube_thumbnails_set",
    api="youtube",
    method="youtube.thumbnails.set",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_thumbnails_set(
    account: str,
    video_id: str,
    image_file_path: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Set a video's custom thumbnail."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.thumbnails()
        .set(
            videoId=video_id,
            media_body=_image_upload(image_file_path),
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_watermarks_set",
    api="youtube",
    method="youtube.watermarks.set",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_watermarks_set(
    account: str,
    channel_id: str,
    watermark_body: dict[str, Any],
    image_file_path: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Set a channel watermark."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.watermarks()
        .set(
            channelId=channel_id,
            body=watermark_body,
            media_body=_image_upload(image_file_path),
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_watermarks_unset",
    api="youtube",
    method="youtube.watermarks.unset",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_watermarks_unset(
    account: str,
    channel_id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Remove a channel watermark."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.watermarks()
        .unset(
            channelId=channel_id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )
