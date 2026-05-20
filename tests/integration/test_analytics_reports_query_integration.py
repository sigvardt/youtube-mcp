"""Recorded integration coverage for youtubeAnalytics.reports.query."""

# pyright: reportMissingTypeStubs=false

from __future__ import annotations

import pytest

from tests.integration.conftest import TEST_ACCOUNT, RecordedFramework
from youtube_mcp.tools.analytics_reports import youtube_analytics_reports_query

pytestmark = pytest.mark.vcr()


def test_analytics_reports_query_analytics_api(recorded_framework: RecordedFramework) -> None:
    result = youtube_analytics_reports_query(
        account=TEST_ACCOUNT,
        ids="channel==MINE",
        start_date="2026-05-01",
        end_date="2026-05-07",
        metrics="views,estimatedMinutesWatched",
        dimensions="day",
        sort="day",
        max_results=7,
    )

    assert result["kind"] == "youtubeAnalytics#resultTable"
    assert result["rows"] == [["2026-05-01", 101, 202], ["2026-05-02", 111, 222]]
    assert recorded_framework.account_manager.credentials_calls == [TEST_ACCOUNT]
    assert recorded_framework.account_manager.analytics_calls == [TEST_ACCOUNT]
    assert recorded_framework.account_manager.youtube_calls == []
    assert recorded_framework.quota_tracker.preflight_calls == [(TEST_ACCOUNT, 0)]
    assert recorded_framework.quota_tracker.record_calls == [(TEST_ACCOUNT, 0)]
