"""Tests for the YouTube miscellaneous tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast

import pytest

import youtube_mcp.tools.misc as misc
from youtube_mcp.server import mcp
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


class FakeMiscRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeAbuseReportsResource:
    insert_request: FakeMiscRequest
    insert_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.insert_request = FakeMiscRequest({"id": "abuse-report-1"})
        self.insert_calls = []

    def insert(self, **kwargs: object) -> FakeMiscRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request


class FakeTestsResource:
    insert_request: FakeMiscRequest
    insert_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.insert_request = FakeMiscRequest({"id": "auth-probe-1"})
        self.insert_calls = []

    def insert(self, **kwargs: object) -> FakeMiscRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request


class FakeYouTubeService:
    abuse_reports_resource: FakeAbuseReportsResource
    tests_resource: FakeTestsResource
    abuse_reports_calls: int
    tests_calls: int

    def __init__(self) -> None:
        self.abuse_reports_resource = FakeAbuseReportsResource()
        self.tests_resource = FakeTestsResource()
        self.abuse_reports_calls = 0
        self.tests_calls = 0

    def abuseReports(self) -> FakeAbuseReportsResource:
        self.abuse_reports_calls += 1
        return self.abuse_reports_resource

    def tests(self) -> FakeTestsResource:
        self.tests_calls += 1
        return self.tests_resource


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


def test_misc_tools_call_mocked_discovery_client() -> None:
    manager, tracker, guard_calls = _configure()
    abuse_report_body = {"subject": {"videoId": "video-1"}, "reasonId": "V"}
    test_body = {"snippet": {"description": "auth probe"}}

    abuse_result = misc.youtube_abuseReports_insert(
        account="primary",
        part="snippet",
        abuse_report_body=abuse_report_body,
    )
    test_result = misc.youtube_tests_insert(
        account="primary",
        part="snippet",
        test_body=test_body,
        external_channel_id="UC123",
    )

    assert abuse_result == {"id": "abuse-report-1"}
    assert test_result == {"id": "auth-probe-1"}
    assert manager.credentials_calls == ["primary", "primary"]
    assert manager.youtube_calls == ["primary", "primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 50), ("primary", 0)]
    assert tracker.record_calls == tracker.preflight_calls
    assert guard_calls == ["primary", "primary"]
    assert manager.service.abuse_reports_calls == 1
    assert manager.service.tests_calls == 1
    assert manager.service.abuse_reports_resource.insert_calls == [
        {"part": "snippet", "body": abuse_report_body}
    ]
    assert manager.service.tests_resource.insert_calls == [
        {"part": "snippet", "body": test_body, "externalChannelId": "UC123"}
    ]


@pytest.mark.asyncio
async def test_all_misc_tool_names_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(misc.youtube_abuseReports_insert).parameters) == [
        "account",
        "part",
        "abuse_report_body",
        "ctx",
    ]
    assert list(inspect.signature(misc.youtube_tests_insert).parameters) == [
        "account",
        "part",
        "test_body",
        "external_channel_id",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert {"youtube_abuseReports_insert", "youtube_tests_insert"} <= registered.keys()
    assert registered["youtube_abuseReports_insert"].tags == {"mutating"}
    assert registered["youtube_tests_insert"].tags == {"mutating"}
    assert registered["youtube_abuseReports_insert"].parameters["required"] == [
        "account",
        "part",
        "abuse_report_body",
    ]
    assert registered["youtube_tests_insert"].parameters["required"] == [
        "account",
        "part",
        "test_body",
    ]
    assert "ctx" not in registered["youtube_abuseReports_insert"].parameters["properties"]
    assert "ctx" not in registered["youtube_tests_insert"].parameters["properties"]

    abuse_meta = cast(dict[str, object], registered["youtube_abuseReports_insert"].meta)
    test_meta = cast(dict[str, object], registered["youtube_tests_insert"].meta)
    assert abuse_meta == {
        "api": "youtube",
        "method": "youtube.abuseReports.insert",
        "scopes": ["https://www.googleapis.com/auth/youtube.force-ssl"],
        "cost": 50,
    }
    assert test_meta == {
        "api": "youtube",
        "method": "youtube.tests.insert",
        "scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
        "cost": 0,
    }
