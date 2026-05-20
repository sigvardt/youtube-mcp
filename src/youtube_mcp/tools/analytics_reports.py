"""YouTube Analytics API reports tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingImports=false
# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false
# pyright: reportImplicitStringConcatenation=false, reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Coroutine, Mapping
from typing import Any, cast

from fastmcp import Context

from youtube_mcp.data.analytics_dim_metric_matrix import (
    ANALYTICS_DIM_METRIC_MATRIX,
    describe_analytics_matrix,
)
from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import YouTubeScope

_BACKGROUND_WARNING_TASKS: set[asyncio.Task[None]] = set()
_ANALYTICS_REPORTS_QUERY_COST = 0

logger = logging.getLogger(__name__)


def _analytics_service(account: str) -> Any:
    framework_ctx = _require_context()
    account_manager = cast(Any, framework_ctx.account_manager)
    cache_key = (account, "youtubeAnalytics")
    cached_services = cast(
        dict[tuple[str, str], Any] | None,
        getattr(account_manager, "_services", None),
    )
    if cached_services is not None and cache_key in cached_services:
        return cached_services[cache_key]

    return account_manager.get_analytics_service(account)


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
        _BACKGROUND_WARNING_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_WARNING_TASKS.discard)


def _warn(ctx: Context | None, message: str) -> None:
    if ctx is None:
        logger.warning(message)
        return

    warning_method = cast(Any, getattr(ctx, "warning", None))
    if callable(warning_method):
        _run_maybe_awaitable(warning_method(message))
        return

    log_method = cast(Any, getattr(ctx, "log", None))
    if callable(log_method):
        _run_maybe_awaitable(log_method(message, level="warning"))
        return

    logger.warning(message)


def _csv_values(value: str | None) -> set[str]:
    if value is None:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def _report_type(ids: str) -> str:
    if ids.startswith("contentOwner=="):
        return "contentOwner"
    return "channel"


def _known_combination(ids: str, metrics: str, dimensions: str | None) -> bool:
    report_type = _report_type(ids)
    requested_metrics = _csv_values(metrics)
    requested_dimensions = _csv_values(dimensions)
    if not requested_metrics:
        return False

    for report in ANALYTICS_DIM_METRIC_MATRIX:
        if report["report_type"] != report_type:
            continue
        report_metrics = set(report["metrics"])
        report_dimensions = set(report["dimensions"])
        if requested_metrics <= report_metrics and requested_dimensions <= report_dimensions:
            return True
    return False


def _warn_if_unknown_combination(
    *,
    ids: str,
    metrics: str,
    dimensions: str | None,
    ctx: Context | None,
) -> None:
    if _known_combination(ids, metrics, dimensions):
        return

    requested_dimensions = dimensions if dimensions is not None else "<none>"
    _warn(
        ctx,
        "WARNING: youtubeAnalytics.reports.query combination is not in the bundled "
        f"{_report_type(ids)} matrix; forwarding to Google. "
        f"metrics={metrics!r}, dimensions={requested_dimensions!r}",
    )


def _query_params(
    *,
    ids: str,
    metrics: str,
    start_date: str,
    end_date: str,
    dimensions: str | None,
    filters: str | None,
    max_results: int | None,
    sort: str | None,
    start_index: int | None,
    currency: str | None,
    include_historical_channel_data: bool | None,
    extra_params: Mapping[str, object] | None,
) -> dict[str, object]:
    params: dict[str, object] = {
        "ids": ids,
        "metrics": metrics,
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "filters": filters,
        "maxResults": max_results,
        "sort": sort,
        "startIndex": start_index,
        "currency": currency,
        "includeHistoricalChannelData": include_historical_channel_data,
    }
    if extra_params is not None:
        params.update(extra_params)
    return params


@youtube_tool(
    name="youtube_analytics_reports_query",
    api="analytics",
    method="youtubeAnalytics.reports.query",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=_ANALYTICS_REPORTS_QUERY_COST,
)
def youtube_analytics_reports_query(
    account: str,
    ids: str,
    metrics: str,
    start_date: str,
    end_date: str,
    dimensions: str | None = None,
    filters: str | None = None,
    max_results: int | None = None,
    sort: str | None = None,
    start_index: int | None = None,
    currency: str | None = None,
    include_historical_channel_data: bool | None = None,
    extra_params: dict[str, object] | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Query YouTube Analytics reports for a channel or content owner."""
    _warn_if_unknown_combination(ids=ids, metrics=metrics, dimensions=dimensions, ctx=ctx)
    service = _analytics_service(account)
    return cast(
        dict[str, object],
        service.reports()
        .query(
            **_query_params(
                ids=ids,
                metrics=metrics,
                start_date=start_date,
                end_date=end_date,
                dimensions=dimensions,
                filters=filters,
                max_results=max_results,
                sort=sort,
                start_index=start_index,
                currency=currency,
                include_historical_channel_data=include_historical_channel_data,
                extra_params=extra_params,
            )
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_analytics_reports_describe",
    api="analytics",
    method="youtubeAnalytics.reports.query",
    scopes=[YouTubeScope.ANALYTICS_READONLY],
    cost=_ANALYTICS_REPORTS_QUERY_COST,
)
def youtube_analytics_reports_describe(account: str) -> dict[str, object]:
    """Describe supported YouTube Analytics dimensions and metrics."""
    return describe_analytics_matrix()
