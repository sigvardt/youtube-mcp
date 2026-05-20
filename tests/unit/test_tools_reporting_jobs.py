"""Tests for the YouTube Reporting API jobs and reportTypes tools."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportRedeclaration=false
# pyright: reportUnannotatedClassAttribute=false, reportImplicitOverride=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast

import pytest

import youtube_mcp.tools.reporting_jobs as reporting_jobs
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy

REPORTING_TOOL_NAMES = {
    "youtube_reporting_jobs_list",
    "youtube_reporting_jobs_create",
    "youtube_reporting_jobs_get",
    "youtube_reporting_jobs_delete",
    "youtube_reporting_reportTypes_list",
}
MUTATING_TOOL_NAMES = {
    "youtube_reporting_jobs_create",
    "youtube_reporting_jobs_delete",
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


class FakeReportingRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeJobsResource:
    list_request: FakeReportingRequest
    create_request: FakeReportingRequest
    get_request: FakeReportingRequest
    delete_request: FakeReportingRequest
    list_calls: list[dict[str, object]]
    create_calls: list[dict[str, object]]
    get_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeReportingRequest({"jobs": [{"id": "job-list"}]})
        self.create_request = FakeReportingRequest({"id": "job-created"})
        self.get_request = FakeReportingRequest({"id": "job-1"})
        self.delete_request = FakeReportingRequest({})
        self.list_calls = []
        self.create_calls = []
        self.get_calls = []
        self.delete_calls = []

    def list(self, **kwargs: object) -> FakeReportingRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def create(self, **kwargs: object) -> FakeReportingRequest:
        self.create_calls.append(dict(kwargs))
        return self.create_request

    def get(self, **kwargs: object) -> FakeReportingRequest:
        self.get_calls.append(dict(kwargs))
        return self.get_request

    def delete(self, **kwargs: object) -> FakeReportingRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request


class FakeReportTypesResource:
    list_request: FakeReportingRequest
    list_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeReportingRequest({"reportTypes": [{"id": "channel_basic_a2"}]})
        self.list_calls = []

    def list(self, **kwargs: object) -> FakeReportingRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request


class FakeReportingService:
    jobs_resource: FakeJobsResource
    report_types_resource: FakeReportTypesResource
    jobs_calls: int
    report_types_calls: int

    def __init__(self) -> None:
        self.jobs_resource = FakeJobsResource()
        self.report_types_resource = FakeReportTypesResource()
        self.jobs_calls = 0
        self.report_types_calls = 0

    def jobs(self) -> FakeJobsResource:
        self.jobs_calls += 1
        return self.jobs_resource

    def reportTypes(self) -> FakeReportTypesResource:
        self.report_types_calls += 1
        return self.report_types_resource


class FakeAccountManager:
    service: FakeReportingService
    _services: dict[tuple[str, str], object]
    credentials_calls: list[str]
    youtube_calls: list[str]
    analytics_calls: list[str]
    reporting_calls: list[str]

    def __init__(self, service: FakeReportingService) -> None:
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

    def get_analytics_service(self, key: str) -> object:
        self.analytics_calls.append(key)
        return object()

    def get_reporting_service(self, key: str) -> FakeReportingService:
        self.reporting_calls.append(key)
        self._services[(key, "youtubereporting")] = self.service
        return self.service


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
    service: FakeReportingService | None = None,
    mutating_guard: Callable[[str], None] | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeReportingService()
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


def test_reporting_jobs_tools_call_mocked_discovery_client() -> None:
    guard_calls: list[str] = []
    manager, tracker = _configure(mutating_guard=guard_calls.append)
    job_body = {"reportTypeId": "channel_basic_a2", "name": "daily channel report"}

    listed = reporting_jobs.youtube_reporting_jobs_list(
        account="primary",
        include_system_managed=True,
        on_behalf_of_content_owner="owner-1",
        page_size=25,
        page_token="next-token",
    )
    created = reporting_jobs.youtube_reporting_jobs_create(
        account="primary",
        job_body=job_body,
        on_behalf_of_content_owner="owner-1",
    )
    fetched = reporting_jobs.youtube_reporting_jobs_get(
        account="primary",
        job_id="job-1",
        on_behalf_of_content_owner="owner-1",
    )
    deleted = reporting_jobs.youtube_reporting_jobs_delete(
        account="primary",
        job_id="job-1",
        on_behalf_of_content_owner="owner-1",
    )

    assert listed == {"jobs": [{"id": "job-list"}]}
    assert created == {"id": "job-created"}
    assert fetched == {"id": "job-1"}
    assert deleted == {}
    assert manager.credentials_calls == ["primary", "primary", "primary", "primary"]
    assert manager.reporting_calls == ["primary", "primary", "primary", "primary"]
    assert manager.youtube_calls == []
    assert manager.analytics_calls == []
    assert guard_calls == ["primary", "primary"]
    assert tracker.preflight_calls == [
        ("primary", 1),
        ("primary", 1),
        ("primary", 1),
        ("primary", 1),
    ]
    assert tracker.record_calls == tracker.preflight_calls
    assert manager.service.jobs_calls == 4
    assert manager.service.jobs_resource.list_calls == [
        {
            "includeSystemManaged": True,
            "onBehalfOfContentOwner": "owner-1",
            "pageSize": 25,
            "pageToken": "next-token",
        }
    ]
    assert manager.service.jobs_resource.create_calls == [
        {"body": job_body, "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.jobs_resource.get_calls == [
        {"jobId": "job-1", "onBehalfOfContentOwner": "owner-1"}
    ]
    assert manager.service.jobs_resource.delete_calls == [
        {"jobId": "job-1", "onBehalfOfContentOwner": "owner-1"}
    ]


def test_reporting_reportTypes_list_uses_cached_discovery_result() -> None:
    manager, tracker = _configure()
    account = "report-types-cache"

    first = reporting_jobs.youtube_reporting_reportTypes_list(
        account=account,
        include_system_managed=True,
        on_behalf_of_content_owner="owner-1",
        page_size=50,
        page_token=None,
    )
    second = reporting_jobs.youtube_reporting_reportTypes_list(
        account=account,
        include_system_managed=True,
        on_behalf_of_content_owner="owner-1",
        page_size=50,
        page_token=None,
    )
    miss = reporting_jobs.youtube_reporting_reportTypes_list(
        account=account,
        include_system_managed=False,
        on_behalf_of_content_owner="owner-1",
        page_size=50,
        page_token=None,
    )

    assert first == {"reportTypes": [{"id": "channel_basic_a2"}]}
    assert second == first
    assert miss == first
    assert manager.credentials_calls == [account, account, account]
    assert manager.reporting_calls == [account, account, account]
    assert tracker.preflight_calls == [(account, 1), (account, 1), (account, 1)]
    assert tracker.record_calls == tracker.preflight_calls
    assert manager.service.report_types_calls == 2
    assert manager.service.report_types_resource.list_request.execute_calls == 2
    assert manager.service.report_types_resource.list_calls == [
        {
            "includeSystemManaged": True,
            "onBehalfOfContentOwner": "owner-1",
            "pageSize": 50,
            "pageToken": None,
        },
        {
            "includeSystemManaged": False,
            "onBehalfOfContentOwner": "owner-1",
            "pageSize": 50,
            "pageToken": None,
        },
    ]


@pytest.mark.asyncio
async def test_reporting_tools_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(reporting_jobs.youtube_reporting_jobs_list).parameters) == [
        "account",
        "include_system_managed",
        "on_behalf_of_content_owner",
        "page_size",
        "page_token",
        "ctx",
    ]
    report_types_signature = inspect.signature(
        reporting_jobs.youtube_reporting_reportTypes_list
    )
    assert list(report_types_signature.parameters) == [
        "account",
        "include_system_managed",
        "on_behalf_of_content_owner",
        "page_size",
        "page_token",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert REPORTING_TOOL_NAMES <= registered.keys()
    for tool_name in MUTATING_TOOL_NAMES:
        assert registered[tool_name].tags == {"mutating"}
    assert registered["youtube_reporting_jobs_create"].parameters["required"] == [
        "account",
        "job_body",
    ]
    assert "ctx" not in registered["youtube_reporting_jobs_list"].parameters["properties"]
    assert "ctx" not in registered["youtube_reporting_reportTypes_list"].parameters["properties"]

    jobs_list_meta = cast(dict[str, object], registered["youtube_reporting_jobs_list"].meta)
    report_types_meta = cast(
        dict[str, object],
        registered["youtube_reporting_reportTypes_list"].meta,
    )
    assert jobs_list_meta == {
        "api": "reporting",
        "method": "youtubeReporting.jobs.list",
        "scopes": ["https://www.googleapis.com/auth/yt-analytics.readonly"],
        "cost": 1,
    }
    assert report_types_meta == {
        "api": "reporting",
        "method": "youtubeReporting.reportTypes.list",
        "scopes": ["https://www.googleapis.com/auth/yt-analytics.readonly"],
        "cost": 1,
    }
