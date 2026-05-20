"""YouTube Analytics API groups and groupItems tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

from typing import Any, cast

from fastmcp import Context

from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import YouTubeScope


def _analytics_service(account: str) -> Any:
    framework_ctx = _require_context()
    account_manager = cast(Any, framework_ctx.account_manager)
    cache_key = (account, "youtubeAnalytics")
    cached_services = cast(
        dict[tuple[str, str], Any] | None,
        getattr(account_manager, "_services", None),
    )
    if cached_services is not None and cache_key in cached_services:
        return cached_services[cache_key]

    return account_manager.get_analytics_service(account)


@youtube_tool(
    name="youtube_analytics_groups_list",
    api="analytics",
    method="youtubeAnalytics.groups.list",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=1,
)
def youtube_analytics_groups_list(
    account: str,
    id: str | None = None,
    mine: bool | None = None,
    page_token: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List YouTube Analytics groups."""
    service = _analytics_service(account)
    return cast(
        dict[str, object],
        service.groups()
        .list(
            id=id,
            mine=mine,
            pageToken=page_token,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_analytics_groups_insert",
    api="analytics",
    method="youtubeAnalytics.groups.insert",
    scopes=[YouTubeScope.MANAGE],
    cost=1,
    mutating=True,
)
def youtube_analytics_groups_insert(
    account: str,
    group_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Create a YouTube Analytics group."""
    service = _analytics_service(account)
    return cast(
        dict[str, object],
        service.groups()
        .insert(
            body=group_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_analytics_groups_update",
    api="analytics",
    method="youtubeAnalytics.groups.update",
    scopes=[YouTubeScope.MANAGE],
    cost=1,
    mutating=True,
)
def youtube_analytics_groups_update(
    account: str,
    group_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a YouTube Analytics group."""
    service = _analytics_service(account)
    return cast(
        dict[str, object],
        service.groups()
        .update(
            body=group_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_analytics_groups_delete",
    api="analytics",
    method="youtubeAnalytics.groups.delete",
    scopes=[YouTubeScope.MANAGE],
    cost=1,
    mutating=True,
)
def youtube_analytics_groups_delete(
    account: str,
    id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a YouTube Analytics group."""
    service = _analytics_service(account)
    return cast(
        dict[str, object],
        service.groups()
        .delete(
            id=id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_analytics_groupItems_list",
    api="analytics",
    method="youtubeAnalytics.groupItems.list",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=1,
)
def youtube_analytics_groupItems_list(
    account: str,
    group_id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List items in a YouTube Analytics group."""
    service = _analytics_service(account)
    return cast(
        dict[str, object],
        service.groupItems()
        .list(
            groupId=group_id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_analytics_groupItems_insert",
    api="analytics",
    method="youtubeAnalytics.groupItems.insert",
    scopes=[YouTubeScope.MANAGE],
    cost=1,
    mutating=True,
)
def youtube_analytics_groupItems_insert(
    account: str,
    group_item_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Add an item to a YouTube Analytics group."""
    service = _analytics_service(account)
    return cast(
        dict[str, object],
        service.groupItems()
        .insert(
            body=group_item_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_analytics_groupItems_delete",
    api="analytics",
    method="youtubeAnalytics.groupItems.delete",
    scopes=[YouTubeScope.MANAGE],
    cost=1,
    mutating=True,
)
def youtube_analytics_groupItems_delete(
    account: str,
    id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Remove an item from a YouTube Analytics group."""
    service = _analytics_service(account)
    return cast(
        dict[str, object],
        service.groupItems()
        .delete(
            id=id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )
