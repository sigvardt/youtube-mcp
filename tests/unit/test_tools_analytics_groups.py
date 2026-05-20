"""Tests for the YouTube Analytics groups and groupItems tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportImplicitOverride=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest

import youtube_mcp.tools.analytics_groups as analytics_groups
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy

GROUP_TOOL_NAMES = {
    "youtube_analytics_groups_list",
    "youtube_analytics_groups_insert",
    "youtube_analytics_groups_update",
    "youtube_analytics_groups_delete",
}
GROUP_ITEM_TOOL_NAMES = {
    "youtube_analytics_groupItems_list",
    "youtube_analytics_groupItems_insert",
    "youtube_analytics_groupItems_delete",
}
MUTATING_TOOL_NAMES = (GROUP_TOOL_NAMES | GROUP_ITEM_TOOL_NAMES) - {
    "youtube_analytics_groups_list",
    "youtube_analytics_groupItems_list",
}


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


class FakeAnalyticsRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeGroupsResource:
    list_request: FakeAnalyticsRequest
    insert_request: FakeAnalyticsRequest
    update_request: FakeAnalyticsRequest
    delete_request: FakeAnalyticsRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeAnalyticsRequest({"items": [{"id": "GROUP-list"}]})
        self.insert_request = FakeAnalyticsRequest({"id": "GROUP-insert"})
        self.update_request = FakeAnalyticsRequest({"id": "GROUP-update"})
        self.delete_request = FakeAnalyticsRequest({})
        self.list_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []

    def list(self, **kwargs: object) -> FakeAnalyticsRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeAnalyticsRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def update(self, **kwargs: object) -> FakeAnalyticsRequest:
        self.update_calls.append(dict(kwargs))
        return self.update_request

    def delete(self, **kwargs: object) -> FakeAnalyticsRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakeGroupItemsResource:
    list_request: FakeAnalyticsRequest
    insert_request: FakeAnalyticsRequest
    delete_request: FakeAnalyticsRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeAnalyticsRequest({"items": [{"id": "GROUPITEM-list"}]})
        self.insert_request = FakeAnalyticsRequest({"id": "GROUPITEM-insert"})
        self.delete_request = FakeAnalyticsRequest({})
        self.list_calls = []
        self.insert_calls = []
        self.delete_calls = []

    def list(self, **kwargs: object) -> FakeAnalyticsRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeAnalyticsRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def delete(self, **kwargs: object) -> FakeAnalyticsRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakeAnalyticsService:
    groups_resource: FakeGroupsResource
    group_items_resource: FakeGroupItemsResource
    groups_calls: int
    group_items_calls: int

    def __init__(self) -> None:
        self.groups_resource = FakeGroupsResource()
        self.group_items_resource = FakeGroupItemsResource()
        self.groups_calls = 0
        self.group_items_calls = 0

    def groups(self) -> FakeGroupsResource:
        self.groups_calls += 1
        return self.groups_resource

    def groupItems(self) -> FakeGroupItemsResource:
        self.group_items_calls += 1
        return self.group_items_resource


class FakeAccountManager:
    service: FakeAnalyticsService
    _services: dict[tuple[str, str], object]
    credentials_calls: list[str]
    youtube_calls: list[str]
    analytics_calls: list[str]
    reporting_calls: list[str]

    def __init__(self, service: FakeAnalyticsService) -> None:
        self.service = service
        self._services = {}
        self.credentials_calls = []
        self.youtube_calls = []
        self.analytics_calls = []
        self.reporting_calls = []

    def get_credentials(self, key: str) -> object:
        self.credentials_calls.append(key)
        return object()

    def get_youtube_service(self, key: str) -> object:
        self.youtube_calls.append(key)
        return object()

    def get_analytics_service(self, key: str) -> FakeAnalyticsService:
        self.analytics_calls.append(key)
        self._services[(key, "youtubeAnalytics")] = self.service
        return self.service

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
    service: FakeAnalyticsService | None = None,
    mutating_guard: Callable[[str], None] | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeAnalyticsService()
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


def test_analytics_groups_tools_call_mocked_discovery_client() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    group_body = {"snippet": {"title": "Test analytics group"}}

    listed = analytics_groups.youtube_analytics_groups_list(
        account="primary",
        id="GROUP123",
        mine=True,
        page_token="next-token",
        on_behalf_of_content_owner="owner-1",
    )
    inserted = analytics_groups.youtube_analytics_groups_insert(
        account="primary",
        group_body=group_body,
        on_behalf_of_content_owner="owner-1",
    )
    updated = analytics_groups.youtube_analytics_groups_update(
        account="primary",
        group_body=group_body,
        on_behalf_of_content_owner="owner-1",
    )
    deleted = analytics_groups.youtube_analytics_groups_delete(
        account="primary",
        id="GROUP123",
        on_behalf_of_content_owner="owner-1",
    )

    assert listed == {"items": [{"id": "GROUP-list"}]}
    assert inserted == {"id": "GROUP-insert"}
    assert updated == {"id": "GROUP-update"}
    assert deleted == {}
    assert manager.credentials_calls == ["primary", "primary", "primary", "primary"]
    assert manager.youtube_calls == []
    assert manager.analytics_calls == ["primary", "primary", "primary", "primary"]
    assert manager.reporting_calls == []
    assert guard_calls == ["primary", "primary", "primary"]
    assert tracker.preflight_calls == [
        ("primary", 1),
        ("primary", 1),
        ("primary", 1),
        ("primary", 1),
    ]
    assert tracker.record_calls == tracker.preflight_calls
    assert manager.service.groups_calls == 4
    assert manager.service.groups_resource.list_calls == [
        {
            "id": "GROUP123",
            "mine": True,
            "pageToken": "next-token",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.groups_resource.insert_calls == [
        {"body": group_body, "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.groups_resource.update_calls == [
        {"body": group_body, "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.groups_resource.delete_calls == [
        {"id": "GROUP123", "onBehalfOfContentOwner": "owner-1"}
    ]


def test_analytics_groupItems_tools_call_mocked_discovery_client() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    group_item_body = {
        "groupId": "GROUP123",
        "resource": {"id": "video-1", "kind": "youtube#video"},
    }

    listed = analytics_groups.youtube_analytics_groupItems_list(
        account="primary",
        group_id="GROUP123",
        on_behalf_of_content_owner="owner-1",
    )
    inserted = analytics_groups.youtube_analytics_groupItems_insert(
        account="primary",
        group_item_body=group_item_body,
        on_behalf_of_content_owner="owner-1",
    )
    deleted = analytics_groups.youtube_analytics_groupItems_delete(
        account="primary",
        id="GROUPITEM123",
        on_behalf_of_content_owner="owner-1",
    )

    assert listed == {"items": [{"id": "GROUPITEM-list"}]}
    assert inserted == {"id": "GROUPITEM-insert"}
    assert deleted == {}
    assert manager.credentials_calls == ["primary", "primary", "primary"]
    assert manager.youtube_calls == []
    assert manager.analytics_calls == ["primary", "primary", "primary"]
    assert manager.reporting_calls == []
    assert guard_calls == ["primary", "primary"]
    assert tracker.preflight_calls == [("primary", 1), ("primary", 1), ("primary", 1)]
    assert tracker.record_calls == tracker.preflight_calls
    assert manager.service.group_items_calls == 3
    assert manager.service.group_items_resource.list_calls == [
        {"groupId": "GROUP123", "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.group_items_resource.insert_calls == [
        {"body": group_item_body, "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.group_items_resource.delete_calls == [
        {"id": "GROUPITEM123", "onBehalfOfContentOwner": "owner-1"}
    ]


@pytest.mark.asyncio
async def test_all_analytics_group_tool_names_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(analytics_groups.youtube_analytics_groups_list).parameters) == [
        "account",
        "id",
        "mine",
        "page_token",
        "on_behalf_of_content_owner",
        "ctx",
    ]
    group_items_list_parameters = inspect.signature(
        analytics_groups.youtube_analytics_groupItems_list
    ).parameters
    assert list(group_items_list_parameters) == [
        "account",
        "group_id",
        "on_behalf_of_content_owner",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    expected_names = GROUP_TOOL_NAMES | GROUP_ITEM_TOOL_NAMES

    assert expected_names <= registered.keys()
    for tool_name in MUTATING_TOOL_NAMES:
        assert registered[tool_name].tags == {"mutating"}
    assert registered["youtube_analytics_groups_insert"].parameters["required"] == [
        "account",
        "group_body",
    ]
    assert registered["youtube_analytics_groupItems_insert"].parameters["required"] == [
        "account",
        "group_item_body",
    ]
    assert registered["youtube_analytics_groups_list"].meta == {
        "api": "analytics",
        "method": "youtubeAnalytics.groups.list",
        "scopes": ["https://www.googleapis.com/auth/yt-analytics.readonly"],
        "cost": 1,
    }
    assert registered["youtube_analytics_groupItems_list"].meta == {
        "api": "analytics",
        "method": "youtubeAnalytics.groupItems.list",
        "scopes": ["https://www.googleapis.com/auth/yt-analytics.readonly"],
        "cost": 1,
    }
    assert "ctx" not in registered["youtube_analytics_groups_list"].parameters["properties"]
    assert "ctx" not in registered["youtube_analytics_groupItems_list"].parameters["properties"]
