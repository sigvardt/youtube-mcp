"""YouTube Reporting API jobs and reportTypes tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from fastmcp import Context

from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import YouTubeScope
from youtube_mcp.utils.cache import cached


def _reporting_service(account: str) -> Any:
    framework_ctx = _require_context()
    account_manager = cast(Any, framework_ctx.account_manager)
    cache_key = (account, "youtubereporting")
    cached_services = cast(
        dict[tuple[str, str], Any] | None,
        getattr(account_manager, "_services", None),
    )
    if cached_services is not None and cache_key in cached_services:
        return cached_services[cache_key]

    return account_manager.get_reporting_service(account)


@youtube_tool(
    name="youtube_reporting_jobs_list",
    api="reporting",
    method="youtubeReporting.jobs.list",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=1,
)
def youtube_reporting_jobs_list(
    account: str,
    include_system_managed: bool | None = None,
    on_behalf_of_content_owner: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List YouTube Reporting jobs."""
    service = _reporting_service(account)
    return cast(
        dict[str, object],
        service.jobs()
        .list(
            includeSystemManaged=include_system_managed,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            pageSize=page_size,
            pageToken=page_token,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_reporting_jobs_create",
    api="reporting",
    method="youtubeReporting.jobs.create",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=1,
    mutating=True,
)
def youtube_reporting_jobs_create(
    account: str,
    job_body: dict[str, Any],
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Create a YouTube Reporting job."""
    service = _reporting_service(account)
    return cast(
        dict[str, object],
        service.jobs()
        .create(
            body=job_body,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_reporting_jobs_delete",
    api="reporting",
    method="youtubeReporting.jobs.delete",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=1,
    mutating=True,
)
def youtube_reporting_jobs_delete(
    account: str,
    job_id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a YouTube Reporting job."""
    service = _reporting_service(account)
    return cast(
        dict[str, object],
        service.jobs()
        .delete(
            jobId=job_id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_reporting_jobs_get",
    api="reporting",
    method="youtubeReporting.jobs.get",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=1,
)
def youtube_reporting_jobs_get(
    account: str,
    job_id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Get a YouTube Reporting job by id."""

    service = _reporting_service(account)
    return cast(
        dict[str, object],
        service.jobs()
        .get(
            jobId=job_id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


def _report_types_cache_key(
    account: str,
    include_system_managed: bool | None = None,
    on_behalf_of_content_owner: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
) -> str:
    return (
        f"{account}:{include_system_managed!r}:{on_behalf_of_content_owner!r}:"
        f"{page_size!r}:{page_token!r}"
    )


@cached(_report_types_cache_key, ttl=timedelta(hours=24))
def _youtube_reporting_reportTypes_list_cached(
    account: str,
    include_system_managed: bool | None = None,
    on_behalf_of_content_owner: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
) -> dict[str, object]:
    service = _reporting_service(account)
    return cast(
        dict[str, object],
        service.reportTypes()
        .list(
            includeSystemManaged=include_system_managed,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            pageSize=page_size,
            pageToken=page_token,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_reporting_reportTypes_list",
    api="reporting",
    method="youtubeReporting.reportTypes.list",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=1,
)
def youtube_reporting_reportTypes_list(
    account: str,
    include_system_managed: bool | None = None,
    on_behalf_of_content_owner: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List available YouTube Reporting report types."""
    return _youtube_reporting_reportTypes_list_cached(
        account,
        include_system_managed,
        on_behalf_of_content_owner,
        page_size,
        page_token,
    )
