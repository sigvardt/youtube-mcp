"""YouTube Data API channelSections tools."""

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
    name="youtube_channelSections_list",
    api="youtube",
    method="youtube.channelSections.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_channelSections_list(
    account: str,
    part: str,
    channel_id: str | None = None,
    id: str | None = None,
    mine: bool | None = None,
    hl: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List channel sections.

    Deprecated by Google: `hl`.
    """
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.channelSections()
        .list(
            part=part,
            channelId=channel_id,
            id=id,
            mine=mine,
            hl=hl,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_channelSections_insert",
    api="youtube",
    method="youtube.channelSections.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_channelSections_insert(
    account: str,
    part: str,
    section_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Create a channel section."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.channelSections()
        .insert(
            part=part,
            body=section_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_channelSections_update",
    api="youtube",
    method="youtube.channelSections.update",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_channelSections_update(
    account: str,
    part: str,
    section_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a channel section."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.channelSections()
        .update(
            part=part,
            body=section_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_channelSections_delete",
    api="youtube",
    method="youtube.channelSections.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_channelSections_delete(
    account: str,
    id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a channel section."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.channelSections()
        .delete(
            id=id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )
