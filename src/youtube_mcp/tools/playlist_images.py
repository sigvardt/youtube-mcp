"""YouTube Data API playlistImages tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false
# pyright: reportPrivateUsage=false, reportUnannotatedClassAttribute=false, reportUnusedParameter=false

from __future__ import annotations

from typing import Any, cast

from fastmcp import Context
from googleapiclient.http import MediaFileUpload
from pydantic import BaseModel, ConfigDict, Field

from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import GoogleApiError, YouTubeScope


class PlaylistImageSnippet(BaseModel):
    """Snippet fields for a playlistImage resource."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    playlist_id: str | None = Field(default=None, alias="playlistId")
    type: str | None = None
    width: int | None = None
    height: int | None = None


class PlaylistImageBody(BaseModel):
    """Stable playlistImage request body model."""

    model_config = ConfigDict(extra="forbid")

    kind: str | None = None
    id: str | None = None
    snippet: PlaylistImageSnippet | None = None


class PlaylistImageResource(PlaylistImageBody):
    """Stable playlistImage response model."""

    error: GoogleApiError | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )


class PageInfo(BaseModel):
    """Pagination information returned by list endpoints."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    total_results: int | None = Field(default=None, alias="totalResults")
    results_per_page: int | None = Field(default=None, alias="resultsPerPage")


class PlaylistImageListResponse(BaseModel):
    """Stable playlistImages.list response model."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: str | None = None
    next_page_token: str | None = Field(default=None, alias="nextPageToken")
    prev_page_token: str | None = Field(default=None, alias="prevPageToken")
    page_info: PageInfo | None = Field(default=None, alias="pageInfo")
    items: list[PlaylistImageResource] = Field(default_factory=list)
    error: GoogleApiError | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )


class EmptyResponse(BaseModel):
    """Empty response for delete endpoints."""

    model_config = ConfigDict(extra="forbid")

    error: GoogleApiError | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )


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
    name="youtube_playlistImages_list",
    api="youtube",
    method="youtube.playlistImages.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_playlistImages_list(
    account: str,
    part: str,
    parent: str | None = None,
    page_token: str | None = None,
    max_results: int | None = None,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> PlaylistImageListResponse:
    """List custom playlist cover images."""

    service = _youtube_service(account)
    response = cast(
        dict[str, Any],
        service.playlistImages()
        .list(
            part=part,
            parent=parent,
            pageToken=page_token,
            maxResults=max_results,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )
    return PlaylistImageListResponse.model_validate(response)


@youtube_tool(
    name="youtube_playlistImages_insert",
    api="youtube",
    method="youtube.playlistImages.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_playlistImages_insert(
    account: str,
    part: str,
    image_body: PlaylistImageBody,
    image_file_path: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> PlaylistImageResource:
    """Upload a custom playlist cover image."""

    service = _youtube_service(account)
    response = cast(
        dict[str, Any],
        service.playlistImages()
        .insert(
            part=part,
            body=image_body.model_dump(by_alias=True, exclude_none=True, exclude={"error"}),
            media_body=_image_upload(image_file_path),
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )
    return PlaylistImageResource.model_validate(response)


@youtube_tool(
    name="youtube_playlistImages_update",
    api="youtube",
    method="youtube.playlistImages.update",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_playlistImages_update(
    account: str,
    part: str,
    image_body: PlaylistImageBody,
    image_file_path: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> PlaylistImageResource:
    """Update a custom playlist cover image."""

    service = _youtube_service(account)
    response = cast(
        dict[str, Any],
        service.playlistImages()
        .update(
            part=part,
            body=image_body.model_dump(by_alias=True, exclude_none=True, exclude={"error"}),
            media_body=_image_upload(image_file_path),
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )
    return PlaylistImageResource.model_validate(response)


@youtube_tool(
    name="youtube_playlistImages_delete",
    api="youtube",
    method="youtube.playlistImages.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_playlistImages_delete(
    account: str,
    id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> EmptyResponse:
    """Remove a custom playlist cover image."""

    service = _youtube_service(account)
    response = service.playlistImages().delete(
        id=id,
        onBehalfOfContentOwner=on_behalf_of_content_owner,
    ).execute()
    if isinstance(response, dict):
        return EmptyResponse.model_validate(response)
    return EmptyResponse.model_validate({})
