"""Tests for youtube_mcp.utils.pagination."""

# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from youtube_mcp.utils.pagination import (
    DEFAULT_MAX_PAGES,
    DEFAULT_PAGE_SIZE,
    PageResult,
    extract_page,
    iter_pages,
)


def test_page_result_defaults_are_public_constants() -> None:
    """Public pagination constants should match the plan."""

    assert DEFAULT_PAGE_SIZE == 50
    assert DEFAULT_MAX_PAGES == 10
    assert PageResult is not None


def test_extract_page_standard_response() -> None:
    """extract_page should normalize standard YouTube pagination fields."""

    response = {
        "items": [{"id": "video-1"}],
        "nextPageToken": "token-2",
        "prevPageToken": "token-0",
        "pageInfo": {"totalResults": 123, "resultsPerPage": 50},
    }

    page = extract_page(response)

    assert page.items == [{"id": "video-1"}]
    assert page.next_page_token == "token-2"
    assert page.prev_page_token == "token-0"
    assert page.total_results == 123
    assert page.results_per_page == 50


def test_extract_page_empty_response() -> None:
    """extract_page should handle empty responses cleanly."""

    page = extract_page({})

    assert page.items == []
    assert page.next_page_token is None
    assert page.prev_page_token is None
    assert page.total_results is None
    assert page.results_per_page is None


def test_iter_pages_respects_max_pages() -> None:
    """iter_pages should stop at the requested page cap."""

    seen_tokens: list[str | None] = []

    def request_factory(page_token: str | None) -> dict[str, object]:
        seen_tokens.append(page_token)
        response: dict[str, object] = {"items": [], "nextPageToken": "still-more"}
        return response

    pages = list(iter_pages(request_factory, max_pages=3))

    assert len(pages) == 3
    assert seen_tokens == [None, "still-more", "still-more"]


def test_iter_pages_stops_when_token_absent() -> None:
    """iter_pages should end when the response has no next page token."""

    responses: list[dict[str, object]] = [
        {"items": [{"id": 1}], "nextPageToken": "page-2"},
        {"items": [{"id": 2}], "nextPageToken": "page-3"},
        {"items": [{"id": 3}]},
    ]
    seen_tokens: list[str | None] = []

    def request_factory(page_token: str | None) -> dict[str, object]:
        seen_tokens.append(page_token)
        return responses[len(seen_tokens) - 1]

    pages = list(iter_pages(request_factory, max_pages=10))

    assert len(pages) == 3
    assert seen_tokens == [None, "page-2", "page-3"]
    assert pages[-1]["items"] == [{"id": 3}]


def test_iter_pages_reports_progress() -> None:
    """iter_pages should report progress to an attached context object."""

    report_progress = Mock()
    ctx = SimpleNamespace(report_progress=report_progress)

    def request_factory(_page_token: str | None) -> dict[str, object]:
        if _page_token is None:
            return {"items": [], "nextPageToken": "page-2"}
        return {"items": []}

    pages = list(iter_pages(request_factory, max_pages=4, ctx=ctx))

    assert len(pages) == 2
    assert report_progress.call_count == 2
    assert report_progress.call_args_list[0].kwargs == {"progress": 1, "total": 4}
    assert report_progress.call_args_list[1].kwargs == {"progress": 2, "total": 4}


def test_iter_pages_warns_and_caps_when_max_pages_is_none() -> None:
    """iter_pages should not allow unbounded pagination when max_pages is omitted."""

    def request_factory(_page_token: str | None) -> dict[str, object]:
        response: dict[str, object] = {"items": [], "nextPageToken": "still-more"}
        return response

    with pytest.warns(UserWarning, match="DEFAULT_MAX_PAGES=10"):
        pages = list(iter_pages(request_factory))

    assert len(pages) == DEFAULT_MAX_PAGES
