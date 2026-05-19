"""Tests for youtube_mcp.types."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from youtube_mcp.types import (
    AccountConfig,
    MutatingGuardConfig,
    QuotaState,
    RetryPolicy,
    TokenBundle,
    UploadProgress,
    YouTubeScope,
)


def test_import_smoke() -> None:
    """The public types surface imports cleanly."""

    assert AccountConfig is not None
    assert TokenBundle is not None
    assert RetryPolicy is not None
    assert QuotaState is not None
    assert UploadProgress is not None
    assert MutatingGuardConfig is not None
    assert YouTubeScope is not None


def test_account_config_round_trips_with_scopes() -> None:
    """AccountConfig should serialize and deserialize cleanly."""

    account = AccountConfig(
        key="jsigvardt",
        client_id="client-id",
        client_secret="client-secret",
        channel_id="channel-id",
        channel_handle="@jsigvardt",
        oauth_scopes=[YouTubeScope.READONLY],
        created_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )

    round_tripped = AccountConfig.model_validate_json(account.model_dump_json())

    assert round_tripped.model_dump() == account.model_dump()


def test_account_config_allows_empty_oauth_scopes_round_trip() -> None:
    """Empty oauth_scopes should remain valid and survive JSON round-tripping."""

    account = AccountConfig(
        key="jsigvardt",
        client_id="client-id",
        client_secret="client-secret",
        oauth_scopes=[],
    )

    round_tripped = AccountConfig.model_validate_json(account.model_dump_json())

    assert round_tripped.oauth_scopes == []
    assert round_tripped.model_dump() == account.model_dump()


def test_account_config_rejects_empty_key() -> None:
    """AccountConfig should require a non-empty key."""

    with pytest.raises(ValidationError):
        AccountConfig(
            key="",
            client_id="client-id",
            client_secret="client-secret",
            oauth_scopes=[],
        )


def test_upload_progress_rejects_percent_over_100() -> None:
    """UploadProgress should reject invalid progress percentages."""

    with pytest.raises(ValidationError):
        UploadProgress(bytes_uploaded=0, bytes_total=100, percent=200)


def test_retry_policy_defaults_match_spec() -> None:
    """RetryPolicy defaults should match the plan."""

    policy = RetryPolicy()

    assert policy.max_attempts == 5
    assert policy.initial_wait == 1.0
    assert policy.max_wait == 60.0
    assert policy.multiplier == 2.0
    assert policy.jitter is True


def test_readonly_scope_value_matches_google_docs() -> None:
    """Scope constants should use the documented Google OAuth strings."""

    assert YouTubeScope.READONLY.value == "https://www.googleapis.com/auth/youtube.readonly"
