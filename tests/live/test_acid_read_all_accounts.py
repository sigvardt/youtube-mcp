"""Read-only live acid tests for every configured YouTube account."""
# pyright: reportMissingTypeStubs=false

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Final, cast

import pytest

from tests.live.conftest import SKIPPABLE_PERMISSION_REASONS, LiveFramework
from youtube_mcp.tools.analytics_reports import youtube_analytics_reports_query
from youtube_mcp.tools.channels import youtube_channels_list
from youtube_mcp.tools.misc import youtube_tests_insert
from youtube_mcp.tools.playlists import youtube_playlists_list
from youtube_mcp.tools.reporting_jobs import youtube_reporting_reportTypes_list
from youtube_mcp.tools.subscriptions import youtube_subscriptions_list
from youtube_mcp.tools.videos import youtube_videos_list
from youtube_mcp.types import AccountConfig, YouTubeScope

LIVE_SKIP_REASON: Final = "set RUN_LIVE_TESTS=1 to run live YouTube API acid tests"
DATA_READ_SCOPES: Final = frozenset(
    {
        YouTubeScope.READONLY,
        YouTubeScope.MANAGE,
        YouTubeScope.FORCE_SSL,
        YouTubeScope.PARTNER,
    }
)
ANALYTICS_READ_SCOPES: Final = frozenset({YouTubeScope.ANALYTICS_READONLY})


def _normalize_scope(scope: YouTubeScope | str) -> YouTubeScope | str:
    if isinstance(scope, YouTubeScope):
        return scope

    try:
        return YouTubeScope(scope)
    except ValueError:
        normalized_name = scope.replace("-", "_").upper()
        if normalized_name in YouTubeScope.__members__:
            return YouTubeScope[normalized_name]
        return scope


def _require_any_scope(
    account: AccountConfig,
    tool_name: str,
    allowed_scopes: frozenset[YouTubeScope],
) -> None:
    account_scopes = {_normalize_scope(scope) for scope in account.oauth_scopes}
    allowed_scope_members = {_normalize_scope(scope) for scope in allowed_scopes}
    if account_scopes.isdisjoint(allowed_scope_members):
        scope_names = ", ".join(sorted(scope.value for scope in allowed_scopes))
        pytest.skip(f"{tool_name} skipped for {account.key}: missing OAuth scope ({scope_names})")


def _quota_before(live_framework: LiveFramework, account: AccountConfig) -> int:
    return live_framework.quota_tracker.current(account.key).units_used_today


def _successful_response(
    response: object,
    *,
    account: AccountConfig,
    tool_name: str,
) -> Mapping[str, object]:
    assert isinstance(response, dict), f"{tool_name} returned non-object response"
    response_mapping = cast(Mapping[str, object], response)
    error = response_mapping.get("error")
    if isinstance(error, dict):
        error_mapping = cast(Mapping[str, object], error)
        reason = error_mapping.get("reason")
        status = error_mapping.get("status")
        message = error_mapping.get("message")
        if isinstance(reason, str) and reason in SKIPPABLE_PERMISSION_REASONS:
            pytest.skip(f"{tool_name} skipped for {account.key}: {reason}")
        failure = f"{tool_name} failed for {account.key}: status={status!r} "
        failure += f"reason={reason!r} message={message!r}"
        pytest.fail(failure)
    return response_mapping


def _finish_call(
    live_framework: LiveFramework,
    account: AccountConfig,
    tool_name: str,
    before_units: int,
    response: object,
) -> Mapping[str, object]:
    payload = _successful_response(response, account=account, tool_name=tool_name)
    cost = live_framework.record_quota_delta(account.key, tool_name, before_units)
    assert cost < 200, f"{tool_name} used {cost} quota units for {account.key}"
    return payload


def _assert_has_keys(response: Mapping[str, object], *keys: str) -> None:
    missing = [key for key in keys if key not in response]
    assert not missing, f"response missing expected keys: {missing}"


def _list_field(response: Mapping[str, object], field: str) -> list[object]:
    value = response.get(field)
    assert isinstance(value, list), f"response field {field!r} is not a list"
    return cast(list[object], value)


def _assert_list_response(response: Mapping[str, object], field: str = "items") -> list[object]:
    items = _list_field(response, field)
    if items:
        assert isinstance(items[0], dict), f"first {field} entry is not an object"
    return items


def _analytics_dates() -> tuple[str, str]:
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=7)
    return start_date.isoformat(), end_date.isoformat()


def _call_videos_list_mine(account: AccountConfig) -> object:
    return youtube_videos_list(account=account.key, part="snippet,status", mine=True)


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason=LIVE_SKIP_REASON)
def test_tests_insert_auth_probe(live_framework: LiveFramework, account: AccountConfig) -> None:
    _require_any_scope(account, "youtube_tests_insert", DATA_READ_SCOPES)
    before_units = _quota_before(live_framework, account)

    response = youtube_tests_insert(
        account=account.key,
        part="snippet",
        test_body={"snippet": {"description": "youtube-mcp live auth probe"}},
    )

    payload = _finish_call(live_framework, account, "youtube_tests_insert", before_units, response)
    _assert_has_keys(payload, "id")


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason=LIVE_SKIP_REASON)
def test_channels_list_mine(live_framework: LiveFramework, account: AccountConfig) -> None:
    _require_any_scope(account, "youtube_channels_list", DATA_READ_SCOPES)
    before_units = _quota_before(live_framework, account)

    response = youtube_channels_list(account=account.key, mine=True)

    payload = _finish_call(live_framework, account, "youtube_channels_list", before_units, response)
    items = _assert_list_response(payload)
    assert items, "channels.list(mine=True) should return the authenticated account channel"
    first_item = cast(Mapping[str, object], items[0])
    assert isinstance(first_item.get("id"), str)
    assert isinstance(first_item.get("snippet"), dict)


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason=LIVE_SKIP_REASON)
def test_playlists_list_mine(live_framework: LiveFramework, account: AccountConfig) -> None:
    _require_any_scope(account, "youtube_playlists_list", DATA_READ_SCOPES)
    before_units = _quota_before(live_framework, account)

    response = youtube_playlists_list(account=account.key, mine=True)

    payload = _finish_call(
        live_framework,
        account,
        "youtube_playlists_list",
        before_units,
        response,
    )
    _ = _assert_list_response(payload)


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason=LIVE_SKIP_REASON)
def test_subscriptions_list_mine(live_framework: LiveFramework, account: AccountConfig) -> None:
    _require_any_scope(account, "youtube_subscriptions_list", DATA_READ_SCOPES)
    before_units = _quota_before(live_framework, account)

    response = youtube_subscriptions_list(account=account.key, part="snippet", mine=True)

    payload = _finish_call(
        live_framework,
        account,
        "youtube_subscriptions_list",
        before_units,
        response,
    )
    _ = _assert_list_response(payload)


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason=LIVE_SKIP_REASON)
def test_videos_list_mine(live_framework: LiveFramework, account: AccountConfig) -> None:
    _require_any_scope(account, "youtube_videos_list", DATA_READ_SCOPES)
    before_units = _quota_before(live_framework, account)

    response = _call_videos_list_mine(account)

    payload = _finish_call(live_framework, account, "youtube_videos_list", before_units, response)
    _ = _assert_list_response(payload)


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason=LIVE_SKIP_REASON)
def test_analytics_reports_query_views(
    live_framework: LiveFramework,
    account: AccountConfig,
) -> None:
    _require_any_scope(account, "youtube_analytics_reports_query", ANALYTICS_READ_SCOPES)
    start_date, end_date = _analytics_dates()
    before_units = _quota_before(live_framework, account)

    response = youtube_analytics_reports_query(
        account=account.key,
        ids="channel==MINE",
        metrics="views",
        start_date=start_date,
        end_date=end_date,
    )

    payload = _finish_call(
        live_framework,
        account,
        "youtube_analytics_reports_query",
        before_units,
        response,
    )
    _assert_has_keys(payload, "kind", "columnHeaders")
    assert payload["kind"] == "youtubeAnalytics#resultTable"
    assert isinstance(payload["columnHeaders"], list)


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason=LIVE_SKIP_REASON)
def test_reporting_report_types_list(live_framework: LiveFramework, account: AccountConfig) -> None:
    _require_any_scope(account, "youtube_reporting_reportTypes_list", ANALYTICS_READ_SCOPES)
    before_units = _quota_before(live_framework, account)

    response = youtube_reporting_reportTypes_list(account=account.key)

    payload = _finish_call(
        live_framework,
        account,
        "youtube_reporting_reportTypes_list",
        before_units,
        response,
    )
    _ = _assert_list_response(payload, "reportTypes")
