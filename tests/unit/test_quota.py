"""Tests for youtube_mcp.utils.quota."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

import youtube_mcp.utils.quota as quota_module
from youtube_mcp.utils.quota import (
    QUOTA_COSTS,
    QuotaExhaustedError,
    QuotaTracker,
    quota_cost,
)


def test_record_persists_across_tracker_reinstantiation(tmp_path: Path) -> None:
    tracker = QuotaTracker(storage_dir=tmp_path)

    tracker.record("primary", 123)

    reloaded = QuotaTracker(storage_dir=tmp_path)
    state = reloaded.current("primary")
    saved_path = tmp_path / "primary.json"

    assert state.units_used_today == 123
    assert state.account_key == "primary"
    assert saved_path.exists()
    assert saved_path.stat().st_mode & 0o777 == 0o600


def test_reset_if_new_day_clears_counter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_day = datetime(2026, 5, 19, 23, 30, tzinfo=UTC)
    next_day = datetime(2026, 5, 20, 0, 1, tzinfo=UTC)
    monkeypatch.setattr(quota_module, "_utcnow", lambda: first_day)
    tracker = QuotaTracker(storage_dir=tmp_path)
    tracker.record("primary", 400)

    monkeypatch.setattr(quota_module, "_utcnow", lambda: next_day)
    tracker.reset_if_new_day("primary")

    state = tracker.current("primary")
    assert state.units_used_today == 0
    assert state.last_reset == next_day


def test_current_auto_resets_stale_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_day = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    next_day = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(quota_module, "_utcnow", lambda: first_day)
    tracker = QuotaTracker(storage_dir=tmp_path)
    tracker.record("primary", 900)

    monkeypatch.setattr(quota_module, "_utcnow", lambda: next_day)
    reloaded = QuotaTracker(storage_dir=tmp_path)

    state = reloaded.current("primary")
    assert state.units_used_today == 0
    assert state.last_reset == next_day


def test_would_exceed_uses_daily_limit(tmp_path: Path) -> None:
    tracker = QuotaTracker(storage_dir=tmp_path)
    tracker.record("primary", 9_999)

    assert tracker.would_exceed("primary", 1) is False
    assert tracker.would_exceed("primary", 2) is True


def test_record_logs_warning_at_80_percent_threshold(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    tracker = QuotaTracker(storage_dir=tmp_path)

    with caplog.at_level(logging.WARNING, logger="youtube_mcp.quota"):
        tracker.record("primary", 8_000)

    assert any("80.0%" in record.message for record in caplog.records)


def test_enforce_true_raises_when_record_would_exceed(tmp_path: Path) -> None:
    tracker = QuotaTracker(storage_dir=tmp_path, enforce=True)
    tracker.record("primary", 9_999)

    with pytest.raises(QuotaExhaustedError):
        tracker.record("primary", 2)

    assert tracker.current("primary").units_used_today == 9_999


def test_default_enforcement_never_raises(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    tracker = QuotaTracker(storage_dir=tmp_path)

    with caplog.at_level(logging.WARNING, logger="youtube_mcp.quota"):
        tracker.record("primary", 10_001)

    assert tracker.current("primary").units_used_today == 10_001
    assert any("100.0%" in record.message for record in caplog.records)


def test_quota_cost_known_methods() -> None:
    assert quota_cost("youtube.videos.list") == 1
    assert quota_cost("youtube.videos.insert") == 1600


def test_quota_cost_unknown_method_returns_zero(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="youtube_mcp.quota"):
        assert quota_cost("youtube.unknown.action") == 0

    assert any("Unknown quota cost" in record.message for record in caplog.records)


def test_quota_cost_table_covers_expected_surface() -> None:
    assert len(QUOTA_COSTS) >= 80
    assert QUOTA_COSTS["youtube.search.list"] == 100
    assert QUOTA_COSTS["youtubeAnalytics.reports.query"] == 1
    assert QUOTA_COSTS["youtubeReporting.reportTypes.list"] == 1
