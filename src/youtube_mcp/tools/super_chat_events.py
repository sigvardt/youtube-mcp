"""YouTube Data API superChatEvents tool."""

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
    name="youtube_superChatEvents_list",
    api="youtube",
    method="youtube.superChatEvents.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_superChatEvents_list(
    account: str,
    part: str,
    hl: str | None = None,
    max_results: int = 5,
    page_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List Super Chat events."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.superChatEvents()
        .list(
            part=part,
            hl=hl,
            maxResults=max_results,
            pageToken=page_token,
        )
        .execute(),
    )
