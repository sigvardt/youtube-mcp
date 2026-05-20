"""YouTube Data API search tool."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Coroutine
from typing import Any, cast

from fastmcp import Context

from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import YouTubeScope

_SEARCH_LIST_COST = 100
_BACKGROUND_LOG_TASKS: set[asyncio.Task[None]] = set()


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


def _current_quota_percent(account: str) -> str:
    quota_tracker = _require_context().quota_tracker
    current_method = getattr(quota_tracker, "current", None)
    if not callable(current_method):
        return "unknown"

    state = current_method(account)
    units_used = getattr(state, "units_used_today", None)
    daily_limit = getattr(state, "daily_limit", None)
    if not isinstance(units_used, int) or not isinstance(daily_limit, int) or daily_limit <= 0:
        return "unknown"

    return f"{(units_used / daily_limit) * 100:.0f}%"


def _run_maybe_awaitable(result: object) -> None:
    if not inspect.isawaitable(result):
        return

    coroutine = cast(Coroutine[Any, Any, None], result)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coroutine)
    else:
        task = loop.create_task(coroutine)
        _BACKGROUND_LOG_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_LOG_TASKS.discard)


def _log_search_cost_warning(account: str, ctx: Context | None) -> None:
    if ctx is None:
        return

    message = (
        f"search.list costs {_SEARCH_LIST_COST} units - "
        f"current quota: {_current_quota_percent(account)}"
    )
    _run_maybe_awaitable(ctx.log(message, level="info"))


@youtube_tool(
    name="youtube_search_list",
    api="youtube",
    method="youtube.search.list",
    scopes=[YouTubeScope.READONLY],
    cost=_SEARCH_LIST_COST,
)
def youtube_search_list(
    account: str,
    part: str,
    channel_id: str | None = None,
    channel_type: str | None = None,
    event_type: str | None = None,
    for_content_owner: bool | None = None,
    for_developer: bool | None = None,
    for_mine: bool | None = None,
    location: str | None = None,
    location_radius: str | None = None,
    max_results: int = 5,
    on_behalf_of_content_owner: str | None = None,
    order: str | None = None,
    page_token: str | None = None,
    published_after: str | None = None,
    published_before: str | None = None,
    q: str | None = None,
    region_code: str | None = None,
    relevance_language: str | None = None,
    safe_search: str | None = None,
    topic_id: str | None = None,
    type: str | None = None,
    video_caption: str | None = None,
    video_category_id: str | None = None,
    video_definition: str | None = None,
    video_dimension: str | None = None,
    video_duration: str | None = None,
    video_embeddable: str | None = None,
    video_license: str | None = None,
    video_paid_product_placement: str | None = None,
    video_syndicated: str | None = None,
    video_type: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Search YouTube resources with supported search.list filters."""
    _log_search_cost_warning(account, ctx)
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.search()
        .list(
            part=part,
            channelId=channel_id,
            channelType=channel_type,
            eventType=event_type,
            forContentOwner=for_content_owner,
            forDeveloper=for_developer,
            forMine=for_mine,
            location=location,
            locationRadius=location_radius,
            maxResults=max_results,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            order=order,
            pageToken=page_token,
            publishedAfter=published_after,
            publishedBefore=published_before,
            q=q,
            regionCode=region_code,
            relevanceLanguage=relevance_language,
            safeSearch=safe_search,
            topicId=topic_id,
            type=type,
            videoCaption=video_caption,
            videoCategoryId=video_category_id,
            videoDefinition=video_definition,
            videoDimension=video_dimension,
            videoDuration=video_duration,
            videoEmbeddable=video_embeddable,
            videoLicense=video_license,
            videoPaidProductPlacement=video_paid_product_placement,
            videoSyndicated=video_syndicated,
            videoType=video_type,
        )
        .execute(),
    )
