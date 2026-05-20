"""YouTube Data API subscriptions tools."""

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
    name="youtube_subscriptions_list",
    api="youtube",
    method="youtube.subscriptions.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_subscriptions_list(
    account: str,
    part: str,
    channel_id: str | None = None,
    id: str | None = None,
    mine: bool | None = None,
    my_recent_subscribers: bool | None = None,
    my_subscribers: bool | None = None,
    for_channel_id: str | None = None,
    max_results: int = 5,
    on_behalf_of_content_owner: str | None = None,
    on_behalf_of_content_owner_channel: str | None = None,
    order: str | None = None,
    page_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List subscriptions."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.subscriptions()
        .list(
            part=part,
            channelId=channel_id,
            id=id,
            mine=mine,
            myRecentSubscribers=my_recent_subscribers,
            mySubscribers=my_subscribers,
            forChannelId=for_channel_id,
            maxResults=max_results,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            onBehalfOfContentOwnerChannel=on_behalf_of_content_owner_channel,
            order=order,
            pageToken=page_token,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_subscriptions_insert",
    api="youtube",
    method="youtube.subscriptions.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_subscriptions_insert(
    account: str,
    part: str,
    subscription_body: dict[str, Any],
    ctx: Context | None = None,
) -> dict[str, object]:
    """Create a subscription."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.subscriptions()
        .insert(
            part=part,
            body=subscription_body,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_subscriptions_delete",
    api="youtube",
    method="youtube.subscriptions.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_subscriptions_delete(
    account: str,
    id: str,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a subscription."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.subscriptions()
        .delete(
            id=id,
        )
        .execute(),
    )
