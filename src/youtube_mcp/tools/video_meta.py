"""YouTube Data API video metadata tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from fastmcp import Context

from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import YouTubeScope
from youtube_mcp.utils.cache import cached


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


def _video_categories_cache_key(
    account: str,
    part: str = "snippet",
    hl: str | None = None,
    id: str | None = None,
    region_code: str | None = None,
) -> str:
    return f"{account}:{part}:{hl!r}:{id!r}:{region_code!r}"


@cached(_video_categories_cache_key, ttl=timedelta(hours=24))
def _youtube_videoCategories_list_cached(
    account: str,
    part: str = "snippet",
    hl: str | None = None,
    id: str | None = None,
    region_code: str | None = None,
) -> dict[str, object]:
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.videoCategories()
        .list(
            part=part,
            hl=hl,
            id=id,
            regionCode=region_code,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_videoCategories_list",
    api="youtube",
    method="youtube.videoCategories.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_videoCategories_list(
    account: str,
    part: str = "snippet",
    hl: str | None = None,
    id: str | None = None,
    region_code: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List video categories."""
    return _youtube_videoCategories_list_cached(account, part, hl, id, region_code)


def _video_abuse_report_reasons_cache_key(
    account: str,
    part: str = "snippet",
    hl: str | None = None,
) -> str:
    return f"{account}:{part}:{hl!r}"


@cached(_video_abuse_report_reasons_cache_key, ttl=timedelta(hours=24))
def _youtube_videoAbuseReportReasons_list_cached(
    account: str,
    part: str = "snippet",
    hl: str | None = None,
) -> dict[str, object]:
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.videoAbuseReportReasons().list(part=part, hl=hl).execute(),
    )


@youtube_tool(
    name="youtube_videoAbuseReportReasons_list",
    api="youtube",
    method="youtube.videoAbuseReportReasons.list",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=1,
)
def youtube_videoAbuseReportReasons_list(
    account: str,
    part: str = "snippet",
    hl: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List video abuse report reasons."""
    return _youtube_videoAbuseReportReasons_list_cached(account, part, hl)
