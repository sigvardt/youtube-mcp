"""Recorded integration coverage for youtube.channels.list."""

# pyright: reportMissingTypeStubs=false

from __future__ import annotations

import pytest

from tests.integration.conftest import TEST_ACCOUNT, RecordedFramework
from youtube_mcp.tools.channels import youtube_channels_list

pytestmark = pytest.mark.vcr()


def test_channels_list_data_api_read(recorded_framework: RecordedFramework) -> None:
    result = youtube_channels_list(
        account=TEST_ACCOUNT,
        part="snippet,contentDetails,statistics",
        mine=True,
        max_results=5,
    )

    assert result["kind"] == "youtube#channelListResponse"
    items = result["items"]
    assert isinstance(items, list)
    assert items[0]["id"] == "UC_TEST_CHANNEL_001"
    assert recorded_framework.account_manager.credentials_calls == [TEST_ACCOUNT]
    assert recorded_framework.account_manager.youtube_calls == [TEST_ACCOUNT]
    assert recorded_framework.quota_tracker.preflight_calls == [(TEST_ACCOUNT, 1)]
    assert recorded_framework.quota_tracker.record_calls == [(TEST_ACCOUNT, 1)]
