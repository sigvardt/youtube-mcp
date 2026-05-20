"""YouTube Data API playlists and playlistItems tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

from typing import Any, cast

from fastmcp import Context

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


@youtube_tool(
    name="youtube_playlists_list",
    api="youtube",
    method="youtube.playlists.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_playlists_list(
    account: str,
    part: str = "snippet,contentDetails",
    channel_id: str | None = None,
    id: str | None = None,
    mine: bool | None = None,
    hl: str | None = None,
    max_results: int = 5,
    page_token: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List playlists."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.playlists()
        .list(
            part=part,
            channelId=channel_id,
            id=id,
            mine=mine,
            hl=hl,
            maxResults=max_results,
            pageToken=page_token,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_playlists_insert",
    api="youtube",
    method="youtube.playlists.insert",
    scopes=[YouTubeScope.MANAGE],
    cost=50,
    mutating=True,
)
def youtube_playlists_insert(
    account: str,
    part: str,
    playlist_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Create a playlist."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.playlists()
        .insert(
            part=part,
            body=playlist_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_playlists_update",
    api="youtube",
    method="youtube.playlists.update",
    scopes=[YouTubeScope.MANAGE],
    cost=50,
    mutating=True,
)
def youtube_playlists_update(
    account: str,
    part: str,
    playlist_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a playlist."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.playlists()
        .update(
            part=part,
            body=playlist_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_playlists_delete",
    api="youtube",
    method="youtube.playlists.delete",
    scopes=[YouTubeScope.MANAGE],
    cost=50,
    mutating=True,
)
def youtube_playlists_delete(
    account: str,
    id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a playlist."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.playlists()
        .delete(
            id=id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_playlistItems_list",
    api="youtube",
    method="youtube.playlistItems.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_playlistItems_list(
    account: str,
    part: str = "snippet,contentDetails",
    id: str | None = None,
    playlist_id: str | None = None,
    max_results: int = 5,
    page_token: str | None = None,
    video_id: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List playlist items."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.playlistItems()
        .list(
            part=part,
            id=id,
            playlistId=playlist_id,
            maxResults=max_results,
            pageToken=page_token,
            videoId=video_id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_playlistItems_insert",
    api="youtube",
    method="youtube.playlistItems.insert",
    scopes=[YouTubeScope.MANAGE],
    cost=50,
    mutating=True,
)
def youtube_playlistItems_insert(
    account: str,
    part: str,
    item_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Add an item to a playlist."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.playlistItems()
        .insert(
            part=part,
            body=item_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_playlistItems_update",
    api="youtube",
    method="youtube.playlistItems.update",
    scopes=[YouTubeScope.MANAGE],
    cost=50,
    mutating=True,
)
def youtube_playlistItems_update(
    account: str,
    part: str,
    item_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a playlist item."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.playlistItems()
        .update(
            part=part,
            body=item_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_playlistItems_delete",
    api="youtube",
    method="youtube.playlistItems.delete",
    scopes=[YouTubeScope.MANAGE],
    cost=50,
    mutating=True,
)
def youtube_playlistItems_delete(
    account: str,
    id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Remove an item from a playlist."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.playlistItems()
        .delete(
            id=id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )
