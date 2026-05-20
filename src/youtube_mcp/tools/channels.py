"""YouTube Data API channels, channelBanners, and thirdPartyLinks tools."""

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


@youtube_tool(
    name="youtube_channels_list",
    api="youtube",
    method="youtube.channels.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_channels_list(
    account: str,
    part: str = "snippet,contentDetails,statistics",
    category_id: str | None = None,
    for_handle: str | None = None,
    for_username: str | None = None,
    id: str | None = None,
    managed_by_me: bool | None = None,
    mine: bool | None = None,
    hl: str | None = None,
    max_results: int = 5,
    on_behalf_of_content_owner: str | None = None,
    page_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List channel metadata and statistics."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.channels()
        .list(
            part=part,
            categoryId=category_id,
            forHandle=for_handle,
            forUsername=for_username,
            id=id,
            managedByMe=managed_by_me,
            mine=mine,
            hl=hl,
            maxResults=max_results,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            pageToken=page_token,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_channels_update",
    api="youtube",
    method="youtube.channels.update",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_channels_update(
    account: str,
    part: str,
    channel_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a channel's branding or settings."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.channels()
        .update(
            part=part,
            body=channel_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_channel_banners_insert",
    api="youtube",
    method="youtube.channelBanners.insert",
    scopes=[YouTubeScope.UPLOAD],
    cost=50,
    mutating=True,
)
def youtube_channel_banners_insert(
    account: str,
    banner_file_path: str,
    channel_id: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Upload a channel banner image."""
    service = _youtube_service(account)
    media_body = MediaFileUpload(banner_file_path)
    return cast(
        dict[str, object],
        service.channelBanners()
        .insert(
            media_body=media_body,
            channelId=channel_id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_third_party_links_list",
    api="youtube",
    method="youtube.thirdPartyLinks.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_third_party_links_list(
    account: str,
    part: str = "snippet,status,linkingToken",
    linking_token: str | None = None,
    type: str | None = None,
    external_channel_id: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List third-party links for a channel."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.thirdPartyLinks()
        .list(
            part=part,
            linkingToken=linking_token,
            type=type,
            externalChannelId=external_channel_id,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_third_party_links_insert",
    api="youtube",
    method="youtube.thirdPartyLinks.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_third_party_links_insert(
    account: str,
    part: str,
    link_body: dict[str, Any],
    external_channel_id: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Create a third-party link for a channel."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.thirdPartyLinks()
        .insert(
            part=part,
            body=link_body,
            externalChannelId=external_channel_id,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_third_party_links_update",
    api="youtube",
    method="youtube.thirdPartyLinks.update",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_third_party_links_update(
    account: str,
    part: str,
    link_body: dict[str, Any],
    external_channel_id: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a third-party link for a channel."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.thirdPartyLinks()
        .update(
            part=part,
            body=link_body,
            externalChannelId=external_channel_id,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_third_party_links_delete",
    api="youtube",
    method="youtube.thirdPartyLinks.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_third_party_links_delete(
    account: str,
    linking_token: str,
    type: str,
    external_channel_id: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a third-party link for a channel."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.thirdPartyLinks()
        .delete(
            linkingToken=linking_token,
            type=type,
            externalChannelId=external_channel_id,
        )
        .execute(),
    )
