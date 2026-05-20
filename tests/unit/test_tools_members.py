"""Tests for the YouTube channel memberships tools."""

# pyright: reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false

from __future__ import annotations

import importlib
import inspect
import json
from typing import Protocol, cast

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response  # type: ignore[import-untyped]

from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy


class MembersModule(Protocol):
    def youtube_members_list(
        self,
        account: str,
        part: str,
        mode: str | None = None,
        max_results: int | None = None,
        page_token: str | None = None,
        has_access_to_level: str | None = None,
        filter_by_member_channel_id: str | None = None,
        ctx: object | None = None,
    ) -> dict[str, object]:
        ...

    def youtube_membershipsLevels_list(
        self,
        account: str,
        part: str,
        ctx: object | None = None,
    ) -> dict[str, object]:
        ...


members_module = importlib.import_module("youtube_mcp.tools.members")
members = cast(MembersModule, cast(object, members_module))


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


class FakeMembersRequest:
    response: dict[str, object]
    error: HttpError | None
    execute_calls: int

    def __init__(self, response: dict[str, object], error: HttpError | None = None) -> None:
        self.response = response
        self.error = error
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        if self.error is not None:
            raise self.error
        return self.response


class FakeMembersResource:
    request: FakeMembersRequest
    list_calls: list[dict[str, object]]

    def __init__(self, response: dict[str, object], error: HttpError | None = None) -> None:
        self.request = FakeMembersRequest(response, error)
        self.list_calls = []

    def list(self, **kwargs: object) -> FakeMembersRequest:
        self.list_calls.append(dict(kwargs))
        return self.request


class FakeYouTubeService:
    members_resource: FakeMembersResource
    memberships_levels_resource: FakeMembersResource
    members_calls: int
    memberships_levels_calls: int

    def __init__(self, members_error: HttpError | None = None) -> None:
        self.members_resource = FakeMembersResource(
            {"items": [{"id": "member-1"}]},
            members_error,
        )
        self.memberships_levels_resource = FakeMembersResource(
            {"items": [{"id": "level-1"}]},
        )
        self.members_calls = 0
        self.memberships_levels_calls = 0

    def members(self) -> FakeMembersResource:
        self.members_calls += 1
        return self.members_resource

    def membershipsLevels(self) -> FakeMembersResource:
        self.memberships_levels_calls += 1
        return self.memberships_levels_resource


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
        cache_key = (key, "youtube")
        cached_service = self._services.get(cache_key)
        if isinstance(cached_service, FakeYouTubeService):
            return cached_service

        self.youtube_calls.append(key)
        self._services[cache_key] = self.service
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
    service: FakeYouTubeService | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeYouTubeService()
    manager = FakeAccountManager(fake_service)
    tracker = FakeQuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=lambda _account: None,
            retry_policy=_retry_policy(),
        )
    )
    return manager, tracker


def _http_error(status: int, body_reason: str, message: str = "request failed") -> HttpError:
    response = Response({"status": str(status)})
    response.reason = "HTTP Error"
    body = json.dumps(
        {"error": {"errors": [{"reason": body_reason}], "message": message}}
    ).encode("utf-8")
    return HttpError(response, body)


def test_members_tools_call_mocked_discovery_client() -> None:
    manager, tracker = _configure()

    members_result = members.youtube_members_list(
        account="primary",
        part="snippet",
        mode="all_current",
        max_results=7,
        page_token="next-token",
        has_access_to_level="level-1",
        filter_by_member_channel_id="UC123",
    )
    levels_result = members.youtube_membershipsLevels_list(account="primary", part="snippet")

    assert members_result == {"items": [{"id": "member-1"}]}
    assert levels_result == {"items": [{"id": "level-1"}]}
    assert manager.credentials_calls == ["primary", "primary"]
    assert manager.youtube_calls == ["primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 1), ("primary", 1)]
    assert tracker.record_calls == [("primary", 1), ("primary", 1)]
    assert manager.service.members_calls == 1
    assert manager.service.memberships_levels_calls == 1
    assert manager.service.members_resource.list_calls == [
        {
            "part": "snippet",
            "mode": "all_current",
            "maxResults": 7,
            "pageToken": "next-token",
            "hasAccessToLevel": "level-1",
            "filterByMemberChannelId": "UC123",
        }
    ]
    assert manager.service.memberships_levels_resource.list_calls == [{"part": "snippet"}]
    assert manager.service.members_resource.request.execute_calls == 1
    assert manager.service.memberships_levels_resource.request.execute_calls == 1


def test_403_mapping() -> None:
    error = _http_error(403, "forbidden", "channel memberships are unavailable")
    service = FakeYouTubeService(members_error=error)
    _, tracker = _configure(service)

    result = members.youtube_members_list(account="primary", part="snippet")

    assert result == {
        "error": {
            "status": 403,
            "reason": "MembershipsNotEnabledError",
            "message": (
                "Requires channel to have Memberships enabled "
                "(Partner Program + monetization). YouTube returned 403 for this "
                "partner-only endpoint."
            ),
        }
    }
    assert service.members_resource.request.execute_calls == 1
    assert tracker.record_calls == []


@pytest.mark.asyncio
async def test_members_tools_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(members.youtube_members_list).parameters) == [
        "account",
        "part",
        "mode",
        "max_results",
        "page_token",
        "has_access_to_level",
        "filter_by_member_channel_id",
        "ctx",
    ]
    assert list(inspect.signature(members.youtube_membershipsLevels_list).parameters) == [
        "account",
        "part",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    members_tool = registered["youtube_members_list"]
    levels_tool = registered["youtube_membershipsLevels_list"]

    assert members_tool.parameters["required"] == ["account", "part"]
    assert levels_tool.parameters["required"] == ["account", "part"]
    assert "ctx" not in members_tool.parameters["properties"]
    assert "ctx" not in levels_tool.parameters["properties"]
