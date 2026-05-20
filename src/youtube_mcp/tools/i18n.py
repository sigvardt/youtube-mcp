"""YouTube Data API i18n tools."""

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


def _i18n_cache_key(account: str, part: str = "snippet", hl: str | None = None) -> str:
    return f"{account}:{part}:{hl!r}"


@cached(_i18n_cache_key, ttl=timedelta(hours=24))
def _youtube_i18nLanguages_list_cached(
    account: str,
    part: str = "snippet",
    hl: str | None = None,
) -> dict[str, object]:
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.i18nLanguages().list(part=part, hl=hl).execute(),
    )


@youtube_tool(
    name="youtube_i18nLanguages_list",
    api="youtube",
    method="youtube.i18nLanguages.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_i18nLanguages_list(
    account: str,
    part: str = "snippet",
    hl: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List supported interface languages."""
    return _youtube_i18nLanguages_list_cached(account, part, hl)


@cached(_i18n_cache_key, ttl=timedelta(hours=24))
def _youtube_i18nRegions_list_cached(
    account: str,
    part: str = "snippet",
    hl: str | None = None,
) -> dict[str, object]:
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.i18nRegions().list(part=part, hl=hl).execute(),
    )


@youtube_tool(
    name="youtube_i18nRegions_list",
    api="youtube",
    method="youtube.i18nRegions.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_i18nRegions_list(
    account: str,
    part: str = "snippet",
    hl: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List supported content regions."""
    return _youtube_i18nRegions_list_cached(account, part, hl)
