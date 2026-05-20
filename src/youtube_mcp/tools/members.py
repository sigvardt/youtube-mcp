"""YouTube Data API channel memberships tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false
# pyright: reportPrivateUsage=false, reportUnusedParameter=false

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
    name="youtube_members_list",
    api="youtube",
    method="youtube.members.list",
    scopes=[YouTubeScope.CHANNEL_MEMBERSHIPS_CREATOR],
    cost=1,
)
def youtube_members_list(
    account: str,
    part: str,
    mode: str | None = None,
    max_results: int | None = None,
    page_token: str | None = None,
    has_access_to_level: str | None = None,
    filter_by_member_channel_id: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List channel members for an eligible Memberships-enabled account."""

    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.members()
        .list(
            part=part,
            mode=mode,
            maxResults=max_results,
            pageToken=page_token,
            hasAccessToLevel=has_access_to_level,
            filterByMemberChannelId=filter_by_member_channel_id,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_membershipsLevels_list",
    api="youtube",
    method="youtube.membershipsLevels.list",
    scopes=[YouTubeScope.CHANNEL_MEMBERSHIPS_CREATOR],
    cost=1,
)
def youtube_membershipsLevels_list(
    account: str,
    part: str,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List Memberships levels for an eligible Memberships-enabled account."""

    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.membershipsLevels().list(part=part).execute(),
    )
