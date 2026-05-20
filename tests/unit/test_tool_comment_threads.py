"""Tests for the YouTube commentThreads tool."""

# pyright: reportMissingTypeStubs=false, reportRedeclaration=false, reportUnannotatedClassAttribute=false
# pyright: reportImplicitOverride=false

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest

from youtube_mcp.server import mcp
from youtube_mcp.tools import comment_threads
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy


class FakeQuotaTracker:
    enforce: bool
    preflight_calls: list[tuple[str, int]]
    record_calls: list[tuple[str, int]]

    def __init__(self) -> None:
        self.enforce = False
        self.preflight_calls = []
        self.record_calls = []

    def would_exceed(self, account_key: str, units: int) -> bool:
        self.preflight_calls.append((account_key, units))
        return False

    def record(self, account_key: str, units: int) -> None:
        self.record_calls.append((account_key, units))


class FakeCommentThreadsRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeCommentThreadsResource:
    list_request: FakeCommentThreadsRequest
    insert_request: FakeCommentThreadsRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]

    def __init__(
        self,
        list_response: dict[str, object],
        insert_response: dict[str, object],
    ) -> None:
        self.list_request = FakeCommentThreadsRequest(list_response)
        self.insert_request = FakeCommentThreadsRequest(insert_response)
        self.list_calls = []
        self.insert_calls = []

    def list(self, **kwargs: object) -> FakeCommentThreadsRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeCommentThreadsRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request


class FakeYouTubeService:
    comment_threads_resource: FakeCommentThreadsResource
    comment_threads_calls: int

    def __init__(
        self,
        list_response: dict[str, object],
        insert_response: dict[str, object],
    ) -> None:
        self.comment_threads_resource = FakeCommentThreadsResource(list_response, insert_response)
        self.comment_threads_calls = 0

    def commentThreads(self) -> FakeCommentThreadsResource:
        self.comment_threads_calls += 1
        return self.comment_threads_resource


class FakeAccountManager:
    service: FakeYouTubeService
    _services: dict[tuple[str, str], object]
    credentials_calls: list[str]
    youtube_calls: list[str]
    analytics_calls: list[str]
    reporting_calls: list[str]

    def __init__(self, service: FakeYouTubeService) -> None:
        self.service = service
        self._services = {}
        self.credentials_calls = []
        self.youtube_calls = []
        self.analytics_calls = []
        self.reporting_calls = []

    def get_credentials(self, key: str) -> object:
        self.credentials_calls.append(key)
        return object()

    def get_youtube_service(self, key: str) -> FakeYouTubeService:
        self.youtube_calls.append(key)
        self._services[(key, "youtube")] = self.service
        return self.service

    def get_analytics_service(self, key: str) -> object:
        self.analytics_calls.append(key)
        return object()

    def get_reporting_service(self, key: str) -> object:
        self.reporting_calls.append(key)
        return object()


def _retry_policy(max_attempts: int = 3) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=max_attempts,
        initial_wait=0.001,
        max_wait=0.01,
        multiplier=1.0,
        jitter=False,
    )


def _configure(
    *,
    service: FakeYouTubeService | None = None,
    mutating_guard: Callable[[str], None] | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeYouTubeService(
        {"items": [{"id": "thread-list-1"}]},
        {"id": "thread-insert-1"},
    )
    manager = FakeAccountManager(fake_service)
    tracker = FakeQuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=mutating_guard or (lambda _account: None),
            retry_policy=_retry_policy(),
        )
    )
    return manager, tracker


def test_tool_calls_comment_threads_list_with_mocked_discovery_client() -> None:
    manager, tracker = _configure()

    result = comment_threads.youtube_commentThreads_list(
        account="primary",
        id="thread-123",
        channel_id="UC123",
        video_id="vid-456",
        all_threads_related_to_channel_id="UC999",
        search_terms="hello world",
        moderation_status="published",
        order="time",
        text_format="plainText",
        max_results=7,
        page_token="next-token",
    )

    assert result == {"items": [{"id": "thread-list-1"}]}
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 1)]
    assert tracker.record_calls == [("primary", 1)]
    assert manager.service.comment_threads_calls == 1
    assert manager.service.comment_threads_resource.list_calls == [
        {
            "part": "snippet,replies",
            "id": "thread-123",
            "channelId": "UC123",
            "videoId": "vid-456",
            "allThreadsRelatedToChannelId": "UC999",
            "searchTerms": "hello world",
            "moderationStatus": "published",
            "order": "time",
            "textFormat": "plainText",
            "maxResults": 7,
            "pageToken": "next-token",
        }
    ]
    assert manager.service.comment_threads_resource.list_request.execute_calls == 1


def test_tool_calls_comment_threads_insert_with_mocked_discovery_client() -> None:
    events: list[str] = []

    class EventAccountManager(FakeAccountManager):
        def get_credentials(self, key: str) -> object:
            events.append(f"credentials:{key}")
            return super().get_credentials(key)

        def get_youtube_service(self, key: str) -> FakeYouTubeService:
            events.append(f"service:{key}")
            return super().get_youtube_service(key)

    def guard(account: str) -> None:
        events.append(f"guard:{account}")

    fake_service = FakeYouTubeService({"items": []}, {"id": "thread-insert-1"})
    manager = EventAccountManager(fake_service)
    tracker = FakeQuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=guard,
            retry_policy=_retry_policy(),
        )
    )

    body = {"snippet": {"topLevelComment": {"snippet": {"textOriginal": "hello"}}}}

    result = comment_threads.youtube_commentThreads_insert(
        account="primary",
        thread_body=body,
        part="snippet",
    )

    assert result == {"id": "thread-insert-1"}
    assert events == ["credentials:primary", "guard:primary", "service:primary"]
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert manager.service.comment_threads_calls == 1
    assert manager.service.comment_threads_resource.insert_calls == [
        {
            "part": "snippet",
            "body": body,
        }
    ]
    assert manager.service.comment_threads_resource.insert_request.execute_calls == 1


@pytest.mark.asyncio
async def test_tool_is_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(comment_threads.youtube_commentThreads_list).parameters) == [
        "account",
        "part",
        "id",
        "channel_id",
        "video_id",
        "all_threads_related_to_channel_id",
        "search_terms",
        "moderation_status",
        "order",
        "text_format",
        "max_results",
        "page_token",
        "ctx",
    ]
    assert list(inspect.signature(comment_threads.youtube_commentThreads_insert).parameters) == [
        "account",
        "thread_body",
        "part",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    list_tool = registered["youtube_commentThreads_list"]
    insert_tool = registered["youtube_commentThreads_insert"]

    assert list_tool.parameters["required"] == ["account"]
    assert "ctx" not in list_tool.parameters["properties"]
    assert insert_tool.tags == {"mutating"}
    assert insert_tool.parameters["required"] == ["account", "thread_body"]
    assert "ctx" not in insert_tool.parameters["properties"]
