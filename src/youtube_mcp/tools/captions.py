"""YouTube Data API captions tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

from typing import Any, cast

from fastmcp import Context
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

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


def _media_upload(caption_file_path: str) -> Any:
    return MediaFileUpload(caption_file_path, resumable=False)


def _update_body(caption_id: str, caption_body: dict[str, Any] | None) -> dict[str, Any]:
    body = dict(caption_body or {})
    body["id"] = caption_id
    return body


def _report_download_progress(ctx: Context | None, status: Any) -> None:
    if ctx is None or status is None:
        return

    progress_method = getattr(status, "progress", None)
    progress_value = progress_method() if callable(progress_method) else 0.0
    progress = float(progress_value) if isinstance(progress_value, int | float) else 0.0
    _ = ctx.report_progress(progress=progress, total=1.0)


@youtube_tool(
    name="youtube_captions_list",
    api="youtube",
    method="youtube.captions.list",
    scopes=[YouTubeScope.READONLY],
    cost=50,
)
def youtube_captions_list(
    account: str,
    part: str,
    video_id: str,
    id: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List captions for a video."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.captions()
        .list(
            part=part,
            videoId=video_id,
            id=id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOf=on_behalf_of,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_captions_insert",
    api="youtube",
    method="youtube.captions.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=400,
    mutating=True,
)
def youtube_captions_insert(
    account: str,
    part: str,
    caption_body: dict[str, Any],
    caption_file_path: str,
    sync: bool | None = None,
    on_behalf_of: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Upload a caption track for a video."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.captions()
        .insert(
            part=part,
            body=caption_body,
            media_body=_media_upload(caption_file_path),
            sync=sync,
            onBehalfOf=on_behalf_of,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_captions_update",
    api="youtube",
    method="youtube.captions.update",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=450,
    mutating=True,
)
def youtube_captions_update(
    account: str,
    part: str,
    caption_id: str,
    caption_body: dict[str, Any] | None = None,
    caption_file_path: str | None = None,
    sync: bool | None = None,
    on_behalf_of: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a caption track's metadata or file."""
    service = _youtube_service(account)
    media_body = _media_upload(caption_file_path) if caption_file_path is not None else None
    return cast(
        dict[str, object],
        service.captions()
        .update(
            part=part,
            body=_update_body(caption_id, caption_body),
            media_body=media_body,
            sync=sync,
            onBehalfOf=on_behalf_of,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_captions_download",
    api="youtube",
    method="youtube.captions.download",
    scopes=[YouTubeScope.READONLY],
    cost=200,
)
def youtube_captions_download(
    account: str,
    caption_id: str,
    tfmt: str | None = None,
    tlang: str | None = None,
    on_behalf_of: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    *,
    output_path: str,
    ctx: Context | None = None,
) -> str:
    """Download a caption track to a local file."""
    service = _youtube_service(account)
    request = service.captions().download_media(
        id=caption_id,
        tfmt=tfmt,
        tlang=tlang,
        onBehalfOf=on_behalf_of,
        onBehalfOfContentOwner=on_behalf_of_content_owner,
    )

    with open(output_path, "wb") as output_file:
        downloader = MediaIoBaseDownload(output_file, request)
        done = False
        while not done:
            status, done = cast(tuple[Any, bool], downloader.next_chunk())
            _report_download_progress(ctx, status)

    return output_path


@youtube_tool(
    name="youtube_captions_delete",
    api="youtube",
    method="youtube.captions.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_captions_delete(
    account: str,
    caption_id: str,
    on_behalf_of: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a caption track."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.captions()
        .delete(
            id=caption_id,
            onBehalfOf=on_behalf_of,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )
