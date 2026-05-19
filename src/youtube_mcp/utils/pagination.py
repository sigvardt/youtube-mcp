"""Pagination helpers for YouTube list responses."""

# pyright: reportExplicitAny=false

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterator
from typing import Any, ClassVar, cast

from pydantic import BaseModel, ConfigDict

DEFAULT_PAGE_SIZE: int = 50
DEFAULT_MAX_PAGES: int = 10


class PageResult(BaseModel):
    """Normalized YouTube pagination metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    items: list[Any]
    next_page_token: str | None = None
    prev_page_token: str | None = None
    total_results: int | None = None
    results_per_page: int | None = None


def extract_page(api_response: dict[str, Any]) -> PageResult:
    """Extract the standard YouTube pagination fields from a response."""

    page_info: dict[str, object] = cast(dict[str, object], api_response.get("pageInfo") or {})

    return PageResult(
        items=cast(list[Any], api_response.get("items", [])),
        next_page_token=cast(str | None, api_response.get("nextPageToken")),
        prev_page_token=cast(str | None, api_response.get("prevPageToken")),
        total_results=cast(int | None, page_info.get("totalResults")),
        results_per_page=cast(int | None, page_info.get("resultsPerPage")),
    )


def iter_pages(
    request_factory: Callable[[str | None], dict[str, Any]],
    max_pages: int | None = None,
    ctx: Any | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield raw response pages while capping pagination to protect quota."""

    page_limit = DEFAULT_MAX_PAGES if max_pages is None else max_pages
    if max_pages is None:
        warnings.warn(
            "max_pages=None is capped at DEFAULT_MAX_PAGES=10 to avoid unbounded pagination.",
            UserWarning,
            stacklevel=2,
        )

    page_token: str | None = None
    for current_page in range(1, page_limit + 1):
        response = request_factory(page_token)
        if ctx is not None:
            ctx_obj = cast(object, ctx)
        else:
            ctx_obj = None

        if ctx_obj is not None and hasattr(ctx_obj, "report_progress"):
            report_progress: object | None = getattr(ctx_obj, "report_progress", None)
            if callable(report_progress):
                _ = report_progress(progress=current_page, total=page_limit)
        yield response

        page_token = extract_page(response).next_page_token
        if page_token is None:
            break
