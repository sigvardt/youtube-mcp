"""YouTube Data API commentThreads tool."""

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
    name="youtube_commentThreads_list",
    api="youtube",
    method="youtube.commentThreads.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_commentThreads_list(
    account: str,
    part: str = "snippet,replies",
    id: str | None = None,
    channel_id: str | None = None,
    video_id: str | None = None,
    all_threads_related_to_channel_id: str | None = None,
    search_terms: str | None = None,
    moderation_status: str | None = None,
    order: str | None = None,
    text_format: str | None = None,
    max_results: int = 20,
    page_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List top-level comment threads."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.commentThreads()
        .list(
            part=part,
            id=id,
            channelId=channel_id,
            videoId=video_id,
            allThreadsRelatedToChannelId=all_threads_related_to_channel_id,
            searchTerms=search_terms,
            moderationStatus=moderation_status,
            order=order,
            textFormat=text_format,
            maxResults=max_results,
            pageToken=page_token,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_commentThreads_insert",
    api="youtube",
    method="youtube.commentThreads.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_commentThreads_insert(
    account: str,
    thread_body: dict[str, Any],
    part: str = "snippet",
    ctx: Context | None = None,
) -> dict[str, object]:
    """Create a top-level comment thread."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.commentThreads()
        .insert(
            part=part,
            body=thread_body,
        )
        .execute(),
    )
