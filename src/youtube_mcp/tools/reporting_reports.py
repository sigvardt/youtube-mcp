"""YouTube Reporting API report tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false
# pyright: reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

from fastmcp import Context
from googleapiclient.http import HttpRequest, MediaIoBaseDownload

from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import YouTubeScope

_DOWNLOAD_CHUNK_SIZE = 1024 * 1024


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


def _pass_through_response(_response: Any, content: bytes) -> bytes:
    return content


def _report_download_progress(ctx: Context | None, status: Any) -> None:
    if ctx is None or status is None:
        return

    bytes_downloaded = getattr(status, "resumable_progress", None)
    bytes_total = getattr(status, "total_size", None)
    if isinstance(bytes_downloaded, int | float) and isinstance(bytes_total, int | float):
        _ = ctx.report_progress(progress=float(bytes_downloaded), total=float(bytes_total))
        return

    progress_method = getattr(status, "progress", None)
    progress_value = progress_method() if callable(progress_method) else 0.0
    progress = float(progress_value) if isinstance(progress_value, int | float) else 0.0
    _ = ctx.report_progress(progress=progress, total=1.0)


@youtube_tool(
    name="youtube_reporting_reports_list",
    api="reporting",
    method="youtubeReporting.reports.list",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=1,
)
def youtube_reporting_reports_list(
    account: str,
    job_id: str,
    created_after: str | None = None,
    start_time_at_or_after: str | None = None,
    start_time_before: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List generated reports for a reporting job."""
    service = _reporting_service(account)
    return cast(
        dict[str, object],
        service.jobs()
        .reports()
        .list(
            jobId=job_id,
            createdAfter=created_after,
            startTimeAtOrAfter=start_time_at_or_after,
            startTimeBefore=start_time_before,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
            pageSize=page_size,
            pageToken=page_token,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_reporting_reports_get",
    api="reporting",
    method="youtubeReporting.reports.get",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=1,
)
def youtube_reporting_reports_get(
    account: str,
    job_id: str,
    report_id: str,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Get reporting report metadata by report ID."""
    service = _reporting_service(account)
    return cast(
        dict[str, object],
        service.jobs()
        .reports()
        .get(
            jobId=job_id,
            reportId=report_id,
            onBehalfOfContentOwner=on_behalf_of_content_owner,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_reporting_reports_download",
    api="reporting",
    method="youtubeReporting.reports.download",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=0,
)
def youtube_reporting_reports_download(
    account: str,
    download_url: str,
    output_path: str,
    ctx: Context | None = None,
) -> str:
    """Download a reporting report to a local file."""
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing output_path: {output_path}")

    service = _reporting_service(account)
    request = HttpRequest(
        http=service._http,
        postproc=_pass_through_response,
        uri=download_url,
        method="GET",
        methodId="youtubeReporting.reports.download",
    )

    with destination.open("wb") as output_file:
        downloader = MediaIoBaseDownload(output_file, request, chunksize=_DOWNLOAD_CHUNK_SIZE)
        done = False
        while not done:
            status, done = cast(tuple[Any, bool], downloader.next_chunk())
            _report_download_progress(ctx, status)

    return str(destination)


@youtube_tool(
    name="youtube_reporting_wait_for_next_report",
    api="reporting",
    method="youtubeReporting.reports.waitForNext",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=0,
)
def youtube_reporting_wait_for_next_report(
    account: str,
    job_id: str,
    since: str,
    timeout_seconds: int = 86400,
    poll_interval_seconds: int = 300,
    on_behalf_of_content_owner: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Poll reports.list until a newer report appears."""

    deadline = time.monotonic() + timeout_seconds
    service = _reporting_service(account)
    while True:
        response = cast(
            dict[str, object],
            service.jobs()
            .reports()
            .list(
                jobId=job_id,
                createdAfter=since,
                onBehalfOfContentOwner=on_behalf_of_content_owner,
                pageSize=1,
            )
            .execute(),
        )
        reports = response.get("reports")
        if isinstance(reports, list) and reports:
            first_report = cast(object, reports[0])
            if isinstance(first_report, dict):
                return cast(dict[str, object], first_report)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"No report for job {job_id!r} appeared after {timeout_seconds} seconds"
            )

        if ctx is not None:
            elapsed = max(timeout_seconds - remaining, 0.0)
            _ = ctx.report_progress(progress=elapsed, total=float(timeout_seconds))
        time.sleep(min(poll_interval_seconds, remaining))
