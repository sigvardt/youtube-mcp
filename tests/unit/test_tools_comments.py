"""Tests for the YouTube comments tools."""

# pyright: reportMissingTypeStubs=false, reportRedeclaration=false, reportUnannotatedClassAttribute=false
# pyright: reportImplicitOverride=false
# pyright: reportAttributeAccessIssue=false, reportMissingImports=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast

import pytest
from pydantic import ValidationError

from youtube_mcp.server import mcp
from youtube_mcp.tools import comments
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


class FakeCommentsRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeCommentsResource:
    list_request: FakeCommentsRequest
    insert_request: FakeCommentsRequest
    update_request: FakeCommentsRequest
    set_moderation_status_request: FakeCommentsRequest
    mark_as_spam_request: FakeCommentsRequest
    delete_request: FakeCommentsRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    set_moderation_status_calls: list[dict[str, object]]
    mark_as_spam_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeCommentsRequest({"items": [{"id": "comment-list-1"}]})
        self.insert_request = FakeCommentsRequest({"id": "comment-insert-1"})
        self.update_request = FakeCommentsRequest({"id": "comment-update-1"})
        self.set_moderation_status_request = FakeCommentsRequest({"id": "comment-moderated-1"})
        self.mark_as_spam_request = FakeCommentsRequest({"id": "comment-spam-1"})
        self.delete_request = FakeCommentsRequest({"deleted": True})
        self.list_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.set_moderation_status_calls = []
        self.mark_as_spam_calls = []
        self.delete_calls = []

    def list(self, **kwargs: object) -> FakeCommentsRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeCommentsRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def update(self, **kwargs: object) -> FakeCommentsRequest:
        self.update_calls.append(dict(kwargs))
        return self.update_request

    def setModerationStatus(self, **kwargs: object) -> FakeCommentsRequest:
        self.set_moderation_status_calls.append(dict(kwargs))
        return self.set_moderation_status_request

    def markAsSpam(self, **kwargs: object) -> FakeCommentsRequest:
        self.mark_as_spam_calls.append(dict(kwargs))
        return self.mark_as_spam_request

    def delete(self, **kwargs: object) -> FakeCommentsRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakeYouTubeService:
    comments_resource: FakeCommentsResource
    comments_calls: int

    def __init__(self) -> None:
        self.comments_resource = FakeCommentsResource()
        self.comments_calls = 0

    def comments(self) -> FakeCommentsResource:
        self.comments_calls += 1
        return self.comments_resource


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


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=3,
        initial_wait=0.001,
        max_wait=0.01,
        multiplier=1.0,
        jitter=False,
    )


def _configure(
    *,
    service: FakeYouTubeService | None = None,
    mutating_guard: Callable[[str], None] | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker, list[str]]:
    fake_service = service or FakeYouTubeService()
    manager = FakeAccountManager(fake_service)
    tracker = FakeQuotaTracker()
    guard_calls: list[str] = []

    def guard(account: str) -> None:
        guard_calls.append(account)

    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=mutating_guard or guard,
            retry_policy=_retry_policy(),
        )
    )
    return manager, tracker, guard_calls


def test_comments_tools_call_mocked_discovery_client() -> None:
    manager, tracker, guard_calls = _configure()
    insert_body = {"snippet": {"parentId": "parent-1", "textOriginal": "hello"}}
    update_body = {"id": "comment-1", "snippet": {"textOriginal": "updated"}}

    list_result = comments.youtube_comments_list(
        account="primary",
        part="snippet",
        id="comment-1",
        parent_id="parent-1",
        max_results=7,
        page_token="next-token",
        text_format="plainText",
    )
    insert_result = comments.youtube_comments_insert(
        account="primary",
        part="snippet",
        comment_body=insert_body,
    )
    update_result = comments.youtube_comments_update(
        account="primary",
        part="snippet",
        comment_body=update_body,
    )
    moderation_result = comments.youtube_comments_setModerationStatus(
        account="primary",
        id=["comment-1"],
        moderation_status="rejected",
        ban_author=True,
    )
    spam_result = comments.youtube_comments_markAsSpam(
        account="primary",
        id=["comment-2"],
    )
    delete_result = comments.youtube_comments_delete(account="primary", id="comment-3")

    assert list_result == {"items": [{"id": "comment-list-1"}]}
    assert insert_result == {"id": "comment-insert-1"}
    assert update_result == {"id": "comment-update-1"}
    assert moderation_result == {"id": "comment-moderated-1"}
    assert spam_result == {"id": "comment-spam-1"}
    assert delete_result == {"deleted": True}
    assert manager.credentials_calls == ["primary"] * 6
    assert manager.youtube_calls == ["primary"] * 6
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [
        ("primary", 1),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
    ]
    assert tracker.record_calls == tracker.preflight_calls
    assert guard_calls == ["primary"] * 5
    assert manager.service.comments_calls == 6
    assert manager.service.comments_resource.list_calls == [
        {
            "part": "snippet",
            "id": "comment-1",
            "textFormat": "plainText",
        }
    ]
    assert manager.service.comments_resource.insert_calls == [
        {
            "part": "snippet",
            "body": insert_body,
        }
    ]
    assert manager.service.comments_resource.update_calls == [
        {
            "part": "snippet",
            "body": update_body,
        }
    ]
    assert manager.service.comments_resource.set_moderation_status_calls == [
        {
            "id": ["comment-1"],
            "moderationStatus": "rejected",
            "banAuthor": True,
        }
    ]
    assert manager.service.comments_resource.mark_as_spam_calls == [{"id": ["comment-2"]}]
    assert manager.service.comments_resource.delete_calls == [{"id": "comment-3"}]


def test_comments_list_with_parent_forwards_pagination() -> None:
    manager, tracker, _guard_calls = _configure()

    result = comments.youtube_comments_list(
        account="primary",
        part="snippet",
        parent_id="parent-1",
        max_results=7,
        page_token="next-token",
        text_format="plainText",
    )

    assert result == {"items": [{"id": "comment-list-1"}]}
    assert tracker.preflight_calls == [("primary", 1)]
    assert tracker.record_calls == [("primary", 1)]
    assert manager.service.comments_resource.list_calls == [
        {
            "part": "snippet",
            "parentId": "parent-1",
            "maxResults": 7,
            "pageToken": "next-token",
            "textFormat": "plainText",
        }
    ]


def test_comments_delete_normalizes_empty_google_success_response() -> None:
    manager, tracker, _guard_calls = _configure()
    empty_response = cast(dict[str, object], cast(object, ""))
    manager.service.comments_resource.delete_request.response = empty_response

    result = comments.youtube_comments_delete(account="primary", id="comment-3")

    assert result == {}
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert manager.service.comments_resource.delete_calls == [{"id": "comment-3"}]


@pytest.mark.asyncio
async def test_comments_tools_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(comments.youtube_comments_list).parameters) == [
        "account",
        "part",
        "id",
        "parent_id",
        "max_results",
        "page_token",
        "text_format",
        "ctx",
    ]
    assert list(inspect.signature(comments.youtube_comments_insert).parameters) == [
        "account",
        "part",
        "comment_body",
        "ctx",
    ]
    assert list(inspect.signature(comments.youtube_comments_update).parameters) == [
        "account",
        "part",
        "comment_body",
        "ctx",
    ]
    assert list(inspect.signature(comments.youtube_comments_setModerationStatus).parameters) == [
        "account",
        "id",
        "moderation_status",
        "ban_author",
        "ctx",
    ]
    assert list(inspect.signature(comments.youtube_comments_markAsSpam).parameters) == [
        "account",
        "id",
        "ctx",
    ]
    assert list(inspect.signature(comments.youtube_comments_delete).parameters) == [
        "account",
        "id",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    expected_names = {
        "youtube_comments_list",
        "youtube_comments_insert",
        "youtube_comments_update",
        "youtube_comments_setModerationStatus",
        "youtube_comments_markAsSpam",
        "youtube_comments_delete",
    }

    assert expected_names <= registered.keys()
    assert registered["youtube_comments_list"].parameters["required"] == ["account", "part"]
    assert "ctx" not in registered["youtube_comments_list"].parameters["properties"]

    for tool_name in expected_names - {"youtube_comments_list"}:
        tool = registered[tool_name]
        tool_meta = cast(dict[str, object], tool.meta)
        assert tool.tags == {"mutating"}
        assert tool_meta["scopes"] == ["https://www.googleapis.com/auth/youtube.force-ssl"]
        assert tool_meta["cost"] == 50
        assert "ctx" not in tool.parameters["properties"]

    moderation_meta = cast(
        dict[str, object],
        registered["youtube_comments_setModerationStatus"].meta,
    )
    spam_meta = cast(dict[str, object], registered["youtube_comments_markAsSpam"].meta)
    assert moderation_meta["method"] == (
        "youtube.comments.setModerationStatus"
    )
    assert spam_meta["method"] == (
        "youtube.comments.markAsSpam"
    )


@pytest.mark.asyncio
async def test_invalid_moderation_status_rejected_at_schema() -> None:
    _ = _configure()
    tools = await mcp.list_tools()
    tool = {item.name: item for item in tools}["youtube_comments_setModerationStatus"]

    assert tool.parameters["properties"]["moderation_status"]["enum"] == [
        "heldForReview",
        "published",
        "rejected",
    ]
    with pytest.raises(ValidationError):
        _ = await tool.run(
            {
                "account": "primary",
                "id": ["comment-1"],
                "moderation_status": "hidden",
            }
        )
