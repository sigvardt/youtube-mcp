"""Tests for the YouTube live chat tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportImplicitOverride=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast

import pytest

import youtube_mcp.tools.live_chat as live_chat
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy, YouTubeScope

LIVE_CHAT_TOOL_NAMES = {
    "youtube_liveChatMessages_list",
    "youtube_liveChatMessages_insert",
    "youtube_liveChatMessages_delete",
    "youtube_liveChatMessages_transition",
    "youtube_liveChatModerators_list",
    "youtube_liveChatModerators_insert",
    "youtube_liveChatModerators_delete",
    "youtube_liveChatBans_insert",
    "youtube_liveChatBans_delete",
}
READONLY_TOOL_NAMES = {
    "youtube_liveChatMessages_list",
    "youtube_liveChatModerators_list",
}
MUTATING_TOOL_NAMES = LIVE_CHAT_TOOL_NAMES - READONLY_TOOL_NAMES


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


class FakeYouTubeRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeLiveChatMessagesResource:
    list_request: FakeYouTubeRequest
    insert_request: FakeYouTubeRequest
    delete_request: FakeYouTubeRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]
    transition_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeYouTubeRequest({"items": [{"id": "message-list-1"}]})
        self.insert_request = FakeYouTubeRequest({"id": "message-insert-1"})
        self.delete_request = FakeYouTubeRequest({})
        self.transition_request = FakeYouTubeRequest({"id": "message-transition-1"})
        self.list_calls = []
        self.insert_calls = []
        self.delete_calls = []
        self.transition_calls = []

    def list(self, **kwargs: object) -> FakeYouTubeRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeYouTubeRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def delete(self, **kwargs: object) -> FakeYouTubeRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request

    def transition(self, **kwargs: object) -> FakeYouTubeRequest:
        self.transition_calls.append(dict(kwargs))
        return self.transition_request


class FakeLiveChatModeratorsResource:
    list_request: FakeYouTubeRequest
    insert_request: FakeYouTubeRequest
    delete_request: FakeYouTubeRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeYouTubeRequest({"items": [{"id": "moderator-list-1"}]})
        self.insert_request = FakeYouTubeRequest({"id": "moderator-insert-1"})
        self.delete_request = FakeYouTubeRequest({})
        self.list_calls = []
        self.insert_calls = []
        self.delete_calls = []

    def list(self, **kwargs: object) -> FakeYouTubeRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeYouTubeRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def delete(self, **kwargs: object) -> FakeYouTubeRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakeLiveChatBansResource:
    insert_request: FakeYouTubeRequest
    delete_request: FakeYouTubeRequest
    insert_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.insert_request = FakeYouTubeRequest({"id": "ban-insert-1"})
        self.delete_request = FakeYouTubeRequest({})
        self.insert_calls = []
        self.delete_calls = []

    def insert(self, **kwargs: object) -> FakeYouTubeRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def delete(self, **kwargs: object) -> FakeYouTubeRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakeYouTubeService:
    live_chat_messages_resource: FakeLiveChatMessagesResource
    live_chat_moderators_resource: FakeLiveChatModeratorsResource
    live_chat_bans_resource: FakeLiveChatBansResource
    live_chat_messages_calls: int
    live_chat_moderators_calls: int
    live_chat_bans_calls: int

    def __init__(self) -> None:
        self.live_chat_messages_resource = FakeLiveChatMessagesResource()
        self.live_chat_moderators_resource = FakeLiveChatModeratorsResource()
        self.live_chat_bans_resource = FakeLiveChatBansResource()
        self.live_chat_messages_calls = 0
        self.live_chat_moderators_calls = 0
        self.live_chat_bans_calls = 0

    def liveChatMessages(self) -> FakeLiveChatMessagesResource:
        self.live_chat_messages_calls += 1
        return self.live_chat_messages_resource

    def liveChatModerators(self) -> FakeLiveChatModeratorsResource:
        self.live_chat_moderators_calls += 1
        return self.live_chat_moderators_resource

    def liveChatBans(self) -> FakeLiveChatBansResource:
        self.live_chat_bans_calls += 1
        return self.live_chat_bans_resource


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
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeYouTubeService()
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


def test_live_chat_tools_call_mocked_discovery_client() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    message_body = {
        "snippet": {
            "liveChatId": "chat-1",
            "textMessageDetails": {"messageText": "hi"},
        }
    }
    moderator_body = {
        "snippet": {
            "liveChatId": "chat-1",
            "moderatorDetails": {"channelId": "UCmod"},
        }
    }
    ban_body = {"snippet": {"liveChatId": "chat-1", "type": "temporary"}}

    messages_list = live_chat.youtube_liveChatMessages_list(
        account="primary",
        live_chat_id="chat-1",
        part="snippet,authorDetails",
        hl="en",
        max_results=500,
        page_token="message-page-2",
        profile_image_size=88,
    )
    message_insert = live_chat.youtube_liveChatMessages_insert(
        account="primary",
        part="snippet",
        message_body=message_body,
    )
    message_delete = live_chat.youtube_liveChatMessages_delete(account="primary", id="msg-1")
    message_transition = live_chat.youtube_liveChatMessages_transition(
        account="primary",
        id="msg-1",
        status="closed",
    )
    moderators_list = live_chat.youtube_liveChatModerators_list(
        account="primary",
        live_chat_id="chat-1",
        part="snippet",
        max_results=25,
        page_token="moderator-page-2",
    )
    moderator_insert = live_chat.youtube_liveChatModerators_insert(
        account="primary",
        part="snippet",
        moderator_body=moderator_body,
    )
    moderator_delete = live_chat.youtube_liveChatModerators_delete(account="primary", id="mod-1")
    ban_insert = live_chat.youtube_liveChatBans_insert(
        account="primary",
        part="snippet",
        ban_body=ban_body,
    )
    ban_delete = live_chat.youtube_liveChatBans_delete(account="primary", id="ban-1")

    assert messages_list == {"items": [{"id": "message-list-1"}]}
    assert message_insert == {"id": "message-insert-1"}
    assert message_delete == {}
    assert message_transition == {"id": "message-transition-1"}
    assert moderators_list == {"items": [{"id": "moderator-list-1"}]}
    assert moderator_insert == {"id": "moderator-insert-1"}
    assert moderator_delete == {}
    assert ban_insert == {"id": "ban-insert-1"}
    assert ban_delete == {}
    assert manager.credentials_calls == ["primary"] * 9
    assert manager.youtube_calls == ["primary"] * 9
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert guard_calls == ["primary"] * 7
    assert tracker.preflight_calls == [
        ("primary", 1),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
        ("primary", 1),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
        ("primary", 50),
    ]
    assert tracker.record_calls == tracker.preflight_calls
    assert manager.service.live_chat_messages_calls == 4
    assert manager.service.live_chat_moderators_calls == 3
    assert manager.service.live_chat_bans_calls == 2
    assert manager.service.live_chat_messages_resource.list_calls == [
        {
            "liveChatId": "chat-1",
            "part": "snippet,authorDetails",
            "hl": "en",
            "maxResults": 500,
            "pageToken": "message-page-2",
            "profileImageSize": 88,
        }
    ]
    assert manager.service.live_chat_messages_resource.insert_calls == [
        {"part": "snippet", "body": message_body}
    ]
    assert manager.service.live_chat_messages_resource.delete_calls == [{"id": "msg-1"}]
    assert manager.service.live_chat_messages_resource.transition_calls == [
        {"id": "msg-1", "status": "closed"}
    ]
    assert manager.service.live_chat_moderators_resource.list_calls == [
        {
            "liveChatId": "chat-1",
            "part": "snippet",
            "maxResults": 25,
            "pageToken": "moderator-page-2",
        }
    ]
    assert manager.service.live_chat_moderators_resource.insert_calls == [
        {"part": "snippet", "body": moderator_body}
    ]
    assert manager.service.live_chat_moderators_resource.delete_calls == [{"id": "mod-1"}]
    assert manager.service.live_chat_bans_resource.insert_calls == [
        {"part": "snippet", "body": ban_body}
    ]
    assert manager.service.live_chat_bans_resource.delete_calls == [{"id": "ban-1"}]


@pytest.mark.asyncio
async def test_registered() -> None:
    _ = _configure()

    assert list(inspect.signature(live_chat.youtube_liveChatMessages_list).parameters) == [
        "account",
        "live_chat_id",
        "part",
        "hl",
        "max_results",
        "page_token",
        "profile_image_size",
        "ctx",
    ]
    assert list(inspect.signature(live_chat.youtube_liveChatModerators_list).parameters) == [
        "account",
        "live_chat_id",
        "part",
        "max_results",
        "page_token",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert LIVE_CHAT_TOOL_NAMES <= registered.keys()
    for tool_name in LIVE_CHAT_TOOL_NAMES:
        assert "ctx" not in registered[tool_name].parameters["properties"]

    for tool_name in READONLY_TOOL_NAMES:
        tool = registered[tool_name]
        tool_meta = cast(dict[str, object], tool.meta)
        assert tool.tags == set()
        assert tool_meta["scopes"] == [YouTubeScope.READONLY.value]
        assert tool_meta["cost"] == 1

    for tool_name in MUTATING_TOOL_NAMES:
        tool = registered[tool_name]
        tool_meta = cast(dict[str, object], tool.meta)
        assert tool.tags == {"mutating"}
        assert tool_meta["scopes"] == [YouTubeScope.FORCE_SSL.value]
        assert tool_meta["cost"] == 50

    assert registered["youtube_liveChatMessages_list"].parameters["required"] == [
        "account",
        "live_chat_id",
        "part",
    ]
    assert registered["youtube_liveChatMessages_insert"].parameters["required"] == [
        "account",
        "part",
        "message_body",
    ]
    assert registered["youtube_liveChatModerators_insert"].parameters["required"] == [
        "account",
        "part",
        "moderator_body",
    ]
    assert registered["youtube_liveChatBans_insert"].parameters["required"] == [
        "account",
        "part",
        "ban_body",
    ]
    expected_methods = {
        "youtube_liveChatMessages_list": "youtube.liveChatMessages.list",
        "youtube_liveChatMessages_insert": "youtube.liveChatMessages.insert",
        "youtube_liveChatMessages_delete": "youtube.liveChatMessages.delete",
        "youtube_liveChatModerators_list": "youtube.liveChatModerators.list",
        "youtube_liveChatModerators_insert": "youtube.liveChatModerators.insert",
        "youtube_liveChatModerators_delete": "youtube.liveChatModerators.delete",
        "youtube_liveChatBans_insert": "youtube.liveChatBans.insert",
        "youtube_liveChatBans_delete": "youtube.liveChatBans.delete",
    }
    for tool_name, method in expected_methods.items():
        tool_meta = cast(dict[str, object], registered[tool_name].meta)
        assert tool_meta["method"] == method
