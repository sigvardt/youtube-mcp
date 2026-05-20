"""YouTube Data API liveBroadcasts and liveStreams tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

from typing import Any, Literal, cast

from fastmcp import Context

from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import YouTubeScope

LiveBroadcastTransitionStatus = Literal["testing", "live", "complete"]


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
    name="youtube_liveBroadcasts_list",
    api="youtube",
    method="youtube.liveBroadcasts.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_liveBroadcasts_list(
    account: str,
    part: str = "id,snippet,contentDetails,status",
    broadcast_status: str | None = None,
    broadcast_type: str | None = None,
    id: str | None = None,
    mine: bool | None = None,
    max_results: int = 5,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    page_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List live broadcasts."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveBroadcasts()
        .list(
            part=part,
            broadcastStatus=broadcast_status,
            broadcastType=broadcast_type,
            id=id,
            mine=mine,
            maxResults=max_results,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
            pageToken=page_token,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveBroadcasts_insert",
    api="youtube",
    method="youtube.liveBroadcasts.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveBroadcasts_insert(
    account: str,
    part: str,
    broadcast_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Create a live broadcast."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveBroadcasts()
        .insert(
            part=part,
            body=broadcast_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveBroadcasts_update",
    api="youtube",
    method="youtube.liveBroadcasts.update",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveBroadcasts_update(
    account: str,
    part: str,
    broadcast_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a live broadcast."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveBroadcasts()
        .update(
            part=part,
            body=broadcast_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveBroadcasts_delete",
    api="youtube",
    method="youtube.liveBroadcasts.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveBroadcasts_delete(
    account: str,
    id: str,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a live broadcast."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveBroadcasts()
        .delete(
            id=id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveBroadcasts_bind",
    api="youtube",
    method="youtube.liveBroadcasts.bind",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveBroadcasts_bind(
    account: str,
    id: str,
    part: str,
    stream_id: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Bind a live broadcast to a stream."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveBroadcasts()
        .bind(
            id=id,
            part=part,
            streamId=stream_id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveBroadcasts_transition",
    api="youtube",
    method="youtube.liveBroadcasts.transition",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveBroadcasts_transition(
    account: str,
    id: str,
    broadcast_status: LiveBroadcastTransitionStatus,
    part: str,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Transition a live broadcast to a new status."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveBroadcasts()
        .transition(
            id=id,
            broadcastStatus=broadcast_status,
            part=part,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveBroadcasts_cuepoint",
    api="youtube",
    method="youtube.liveBroadcasts.cuepoint",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveBroadcasts_cuepoint(
    account: str,
    id: str,
    cuepoint_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Insert a cuepoint into a live broadcast."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveBroadcasts()
        .cuepoint(
            id=id,
            body=cuepoint_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveStreams_list",
    api="youtube",
    method="youtube.liveStreams.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_liveStreams_list(
    account: str,
    part: str = "id,snippet,cdn,status",
    id: str | None = None,
    mine: bool | None = None,
    max_results: int = 5,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    page_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List live streams."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveStreams()
        .list(
            part=part,
            id=id,
            mine=mine,
            maxResults=max_results,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
            pageToken=page_token,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveStreams_insert",
    api="youtube",
    method="youtube.liveStreams.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveStreams_insert(
    account: str,
    part: str,
    stream_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Create a live stream."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveStreams()
        .insert(
            part=part,
            body=stream_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveStreams_update",
    api="youtube",
    method="youtube.liveStreams.update",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveStreams_update(
    account: str,
    part: str,
    stream_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a live stream."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveStreams()
        .update(
            part=part,
            body=stream_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveStreams_delete",
    api="youtube",
    method="youtube.liveStreams.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveStreams_delete(
    account: str,
    id: str,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a live stream."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveStreams()
        .delete(
            id=id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )
