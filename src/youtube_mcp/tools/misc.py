"""YouTube Data API miscellaneous tools."""

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
    name="youtube_abuseReports_insert",
    api="youtube",
    method="youtube.abuseReports.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_abuseReports_insert(
    account: str,
    part: str,
    abuse_report_body: dict[str, Any],
    ctx: Context | None = None,
) -> dict[str, object]:
    """Submit an abuse report."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.abuseReports()
        .insert(
            part=part,
            body=abuse_report_body,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_tests_insert",
    api="youtube",
    method="youtube.tests.insert",
    scopes=[YouTubeScope.READONLY],
    cost=0,
    mutating=True,
)
def youtube_tests_insert(
    account: str,
    part: str,
    test_body: dict[str, Any],
    external_channel_id: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Run a YouTube API auth smoke-test request."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.tests()
        .insert(
            part=part,
            body=test_body,
            externalChannelId=external_channel_id,
        )
        .execute(),
    )
