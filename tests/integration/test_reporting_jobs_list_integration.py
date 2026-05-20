"""Recorded integration coverage for youtubeReporting.jobs.list."""

# pyright: reportMissingTypeStubs=false

from __future__ import annotations

import pytest

from tests.integration.conftest import TEST_ACCOUNT, RecordedFramework
from youtube_mcp.tools.reporting_jobs import youtube_reporting_jobs_list

pytestmark = pytest.mark.vcr()


def test_reporting_jobs_list_reporting_api(recorded_framework: RecordedFramework) -> None:
    result = youtube_reporting_jobs_list(
        account=TEST_ACCOUNT,
        include_system_managed=True,
        page_size=10,
    )

    assert result["jobs"] == [
        {
            "id": "JOB_TEST_CHANNEL_DAILY",
            "name": "Synthetic channel basic daily",
            "reportTypeId": "channel_basic_a2",
            "createTime": "2026-05-01T00:00:00Z",
            "expireTime": "2026-06-01T00:00:00Z",
        }
    ]
    assert recorded_framework.account_manager.credentials_calls == [TEST_ACCOUNT]
    assert recorded_framework.account_manager.reporting_calls == [TEST_ACCOUNT]
    assert recorded_framework.account_manager.youtube_calls == []
    assert recorded_framework.quota_tracker.preflight_calls == [(TEST_ACCOUNT, 1)]
    assert recorded_framework.quota_tracker.record_calls == [(TEST_ACCOUNT, 1)]
