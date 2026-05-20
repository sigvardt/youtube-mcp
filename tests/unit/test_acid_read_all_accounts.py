"""Tests for live acid scope matching helpers."""

# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from tests.live.test_acid_read_all_accounts import (
    ANALYTICS_READ_SCOPES,
    DATA_READ_SCOPES,
    _require_any_scope,
)
from youtube_mcp.types import AccountConfig, YouTubeScope


@dataclass
class ScopeAccount:
    """Minimal account-shaped object for scope matching tests."""

    key: str
    oauth_scopes: list[YouTubeScope | str]


@pytest.mark.parametrize(
    ("oauth_scopes", "allowed_scopes"),
    [
        ([YouTubeScope.FORCE_SSL], DATA_READ_SCOPES),
        (["force_ssl"], DATA_READ_SCOPES),
        ([YouTubeScope.ANALYTICS_READONLY], ANALYTICS_READ_SCOPES),
        (["analytics_readonly"], ANALYTICS_READ_SCOPES),
    ],
)
def test_require_any_scope_accepts_enum_members_and_short_names(
    oauth_scopes: list[YouTubeScope | str],
    allowed_scopes: frozenset[YouTubeScope],
) -> None:
    account = cast(
        AccountConfig,
        cast(object, ScopeAccount(key="jsigvardt", oauth_scopes=oauth_scopes)),
    )

    _require_any_scope(account, "youtube_tests_insert", allowed_scopes)
