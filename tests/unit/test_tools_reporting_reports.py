"""Tests for the YouTube Reporting API report tools."""

# pyright: reportMissingTypeStubs=false, reportRedeclaration=false, reportUnannotatedClassAttribute=false
# pyright: reportImplicitOverride=false, reportMissingImports=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportAny=false, reportPrivateUsage=false, reportUnknownLambdaType=false
# pyright: reportPrivateLocalImportUsage=false, reportUnusedCallResult=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import BinaryIO, ClassVar, cast
from unittest.mock import Mock

import pytest
from fastmcp import Context

import youtube_mcp.tools.reporting_reports as reporting_reports
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy, YouTubeScope

REPORTING_REPORTS_TOOL_NAMES = {
    "youtube_reporting_reports_list",
    "youtube_reporting_reports_get",
    "youtube_reporting_reports_download",
    "youtube_reporting_wait_for_next_report",
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


class FakeReportsResource:
    list_request: FakeReportingRequest
    get_request: FakeReportingRequest
    list_calls: list[dict[str, object]]
    get_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeReportingRequest({"reports": [{"id": "report-list-1"}]})
        self.get_request = FakeReportingRequest(
            {"id": "report-123", "downloadUrl": "https://reports.example/download.csv"}
        )
        self.list_calls = []
        self.get_calls = []

    def list(self, **kwargs: object) -> FakeReportingRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def get(self, **kwargs: object) -> FakeReportingRequest:
        self.get_calls.append(dict(kwargs))
        return self.get_request


class FakeJobsResource:
    reports_resource: FakeReportsResource
    reports_calls: int

    def __init__(self) -> None:
        self.reports_resource = FakeReportsResource()
        self.reports_calls = 0

    def reports(self) -> FakeReportsResource:
        self.reports_calls += 1
        return self.reports_resource


class FakeReportingService:
    jobs_resource: FakeJobsResource
    jobs_calls: int
    _http: object

    def __init__(self) -> None:
        self.jobs_resource = FakeJobsResource()
        self.jobs_calls = 0
        self._http = object()

    def jobs(self) -> FakeJobsResource:
        self.jobs_calls += 1
        return self.jobs_resource


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


class FakeHttpRequest:
    kwargs: dict[str, object]

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = dict(kwargs)


class FakeDownloadStatus:
    resumable_progress: int
    total_size: int

    def __init__(self, resumable_progress: int, total_size: int) -> None:
        self.resumable_progress = resumable_progress
        self.total_size = total_size


class FakeMediaIoBaseDownload:
    instances: ClassVar[list[FakeMediaIoBaseDownload]] = []

    def __init__(self, fd: BinaryIO, request: FakeHttpRequest, chunksize: int) -> None:
        self.fd = fd
        self.request = request
        self.chunksize = chunksize
        self.next_chunk_calls = 0
        self.instances.append(self)

    def next_chunk(self) -> tuple[FakeDownloadStatus, bool]:
        self.next_chunk_calls += 1
        if self.next_chunk_calls == 1:
            _ = self.fd.write(b"col1,col2\n")
            return FakeDownloadStatus(10, 18), False

        _ = self.fd.write(b"a,b\n")
        return FakeDownloadStatus(18, 18), True


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


def test_list_and_get_call_reporting_reports_with_mocked_discovery_client() -> None:
    manager, tracker = _configure()

    listed = reporting_reports.youtube_reporting_reports_list(
        account="primary",
        job_id="job-123",
        created_after="2026-05-01T00:00:00Z",
        start_time_at_or_after="2026-05-02T00:00:00Z",
        start_time_before="2026-05-03T00:00:00Z",
        on_behalf_of_content_owner="owner-1",
        page_size=50,
        page_token="page-2",
    )
    fetched = reporting_reports.youtube_reporting_reports_get(
        account="primary",
        job_id="job-123",
        report_id="report-123",
        on_behalf_of_content_owner="owner-1",
    )

    assert listed == {"reports": [{"id": "report-list-1"}]}
    assert fetched == {"id": "report-123", "downloadUrl": "https://reports.example/download.csv"}
    assert manager.credentials_calls == ["primary", "primary"]
    assert manager.reporting_calls == ["primary", "primary"]
    assert manager.youtube_calls == []
    assert manager.analytics_calls == []
    assert tracker.preflight_calls == [("primary", 1), ("primary", 1)]
    assert tracker.record_calls == tracker.preflight_calls
    assert manager.service.jobs_calls == 2
    assert manager.service.jobs_resource.reports_calls == 2
    assert manager.service.jobs_resource.reports_resource.list_calls == [
        {
            "jobId": "job-123",
            "createdAfter": "2026-05-01T00:00:00Z",
            "startTimeAtOrAfter": "2026-05-02T00:00:00Z",
            "startTimeBefore": "2026-05-03T00:00:00Z",
            "onBehalfOfContentOwner": "owner-1",
            "pageSize": 50,
            "pageToken": "page-2",
        }
    ]
    assert manager.service.jobs_resource.reports_resource.get_calls == [
        {
            "jobId": "job-123",
            "reportId": "report-123",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.jobs_resource.reports_resource.list_request.execute_calls == 1
    assert manager.service.jobs_resource.reports_resource.get_request.execute_calls == 1


def test_wait_for_next_report_polls_until_report_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, tracker = _configure()
    reports_resource = manager.service.jobs_resource.reports_resource
    reports_resource.list_request.response = {"reports": []}
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        reports_resource.list_request.response = {"reports": [{"id": "report-new"}]}

    monkeypatch.setattr(reporting_reports.time, "sleep", fake_sleep)

    report = reporting_reports.youtube_reporting_wait_for_next_report(
        account="primary",
        job_id="job-123",
        since="2026-05-01T00:00:00Z",
        timeout_seconds=10,
        poll_interval_seconds=2,
        on_behalf_of_content_owner="owner-1",
    )

    assert report == {"id": "report-new"}
    assert sleep_calls == [2]
    assert tracker.preflight_calls == [("primary", 0)]
    assert manager.service.jobs_resource.reports_resource.list_calls == [
        {
            "jobId": "job-123",
            "createdAfter": "2026-05-01T00:00:00Z",
            "onBehalfOfContentOwner": "owner-1",
            "pageSize": 1,
        },
        {
            "jobId": "job-123",
            "createdAfter": "2026-05-01T00:00:00Z",
            "onBehalfOfContentOwner": "owner-1",
            "pageSize": 1,
        },
    ]


def test_download_streams_csv_to_output_path_with_mocked_http(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    FakeMediaIoBaseDownload.instances = []
    http_request_factory = Mock(side_effect=lambda **kwargs: FakeHttpRequest(**kwargs))
    monkeypatch.setattr(reporting_reports, "HttpRequest", http_request_factory)
    monkeypatch.setattr(reporting_reports, "MediaIoBaseDownload", FakeMediaIoBaseDownload)
    manager, tracker = _configure()
    output_path = tmp_path / "report.csv"
    report_progress = Mock()
    ctx = cast(Context, cast(object, SimpleNamespace(report_progress=report_progress)))

    result = reporting_reports.youtube_reporting_reports_download(
        account="primary",
        download_url="https://reports.example/download.csv",
        output_path=str(output_path),
        ctx=ctx,
    )

    assert result == str(output_path)
    assert output_path.read_bytes() == b"col1,col2\na,b\n"
    assert tracker.preflight_calls == [("primary", 0)]
    assert tracker.record_calls == [("primary", 0)]
    assert manager.credentials_calls == ["primary"]
    assert manager.reporting_calls == ["primary"]
    assert http_request_factory.call_count == 1
    request_kwargs = http_request_factory.call_args.kwargs
    assert request_kwargs["http"] is manager.service._http
    assert request_kwargs["uri"] == "https://reports.example/download.csv"
    assert request_kwargs["method"] == "GET"
    assert request_kwargs["methodId"] == "youtubeReporting.reports.download"
    assert callable(request_kwargs["postproc"])
    assert FakeMediaIoBaseDownload.instances[0].chunksize == 1024 * 1024
    assert FakeMediaIoBaseDownload.instances[0].next_chunk_calls == 2
    assert report_progress.call_args_list[0].kwargs == {"progress": 10.0, "total": 18.0}
    assert report_progress.call_args_list[1].kwargs == {"progress": 18.0, "total": 18.0}


def test_download_refuses_to_overwrite_existing_output_path(tmp_path: Path) -> None:
    _manager, tracker = _configure()
    output_path = tmp_path / "report.csv"
    output_path.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        reporting_reports.youtube_reporting_reports_download(
            account="primary",
            download_url="https://reports.example/download.csv",
            output_path=str(output_path),
        )

    assert output_path.read_text(encoding="utf-8") == "existing"
    assert tracker.preflight_calls == [("primary", 0)]
    assert tracker.record_calls == []


@pytest.mark.asyncio
async def test_registered() -> None:
    _ = _configure()

    assert list(inspect.signature(reporting_reports.youtube_reporting_reports_list).parameters) == [
        "account",
        "job_id",
        "created_after",
        "start_time_at_or_after",
        "start_time_before",
        "on_behalf_of_content_owner",
        "page_size",
        "page_token",
        "ctx",
    ]
    download_parameters = inspect.signature(
        reporting_reports.youtube_reporting_reports_download
    ).parameters
    assert list(download_parameters) == [
        "account",
        "download_url",
        "output_path",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert REPORTING_REPORTS_TOOL_NAMES <= registered.keys()
    assert registered["youtube_reporting_reports_list"].tags == set()
    assert registered["youtube_reporting_reports_get"].tags == set()
    assert registered["youtube_reporting_reports_download"].tags == set()
    assert registered["youtube_reporting_reports_list"].parameters["required"] == [
        "account",
        "job_id",
    ]
    assert registered["youtube_reporting_reports_get"].parameters["required"] == [
        "account",
        "job_id",
        "report_id",
    ]
    assert registered["youtube_reporting_reports_download"].parameters["required"] == [
        "account",
        "download_url",
        "output_path",
    ]
    assert "ctx" not in registered["youtube_reporting_reports_download"].parameters["properties"]
    list_meta = registered["youtube_reporting_reports_list"].meta
    get_meta = registered["youtube_reporting_reports_get"].meta
    download_meta = registered["youtube_reporting_reports_download"].meta
    assert list_meta is not None
    assert get_meta is not None
    assert download_meta is not None
    assert list_meta["api"] == "reporting"
    assert list_meta["method"] == "youtubeReporting.reports.list"
    assert get_meta["method"] == "youtubeReporting.reports.get"
    assert download_meta["method"] == "youtubeReporting.reports.download"
    assert list_meta["scopes"] == [YouTubeScope.ANALYTICS_READONLY.value]
    assert download_meta["cost"] == 0
