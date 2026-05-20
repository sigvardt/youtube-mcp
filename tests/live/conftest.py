"""Shared fixtures for live YouTube API tests."""
# pyright: reportMissingTypeStubs=false

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest

from youtube_mcp.auth.accounts import AccountConfigStore, AccountManager
from youtube_mcp.auth.token_store import FileTokenStore, make_token_store
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import AccountConfig, RetryPolicy
from youtube_mcp.utils.quota import QuotaTracker

NO_ACCOUNTS_SKIP_REASON = "no youtube-mcp accounts configured"
SKIPPABLE_PERMISSION_REASONS: frozenset[str] = frozenset(
    {
        "accessNotConfigured",
        "authError",
        "channelNotActive",
        "forbidden",
        "insufficientPermissions",
        "liveStreamingNotEnabled",
        "parentCommentNotFound",
        "subscriptionDuplicate",
        "subscriptionNotFound",
        "uploadRateLimitExceeded",
        "youtubeSignupRequired",
    }
)
LOGGER = logging.getLogger(__name__)


@dataclass
class LiveFramework:
    """Runtime dependencies and quota accounting for live acid tests."""

    account_manager: AccountManager
    quota_tracker: QuotaTracker
    quota_by_account: dict[str, int] = field(default_factory=dict)

    def record_quota_delta(self, account_key: str, tool_name: str, before_units: int) -> int:
        after_units = self.quota_tracker.current(account_key).units_used_today
        cost = max(after_units - before_units, 0)
        total = self.quota_by_account.get(account_key, 0) + cost
        self.quota_by_account[account_key] = total
        LOGGER.info("%s[%s] quota cost=%s total=%s", tool_name, account_key, cost, total)
        return cost


def _configured_accounts() -> list[AccountConfig]:
    manager = AccountManager(AccountConfigStore(), FileTokenStore())
    return manager.list()


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=3,
        initial_wait=1.0,
        max_wait=10.0,
        multiplier=2.0,
        jitter=True,
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "account" not in metafunc.fixturenames:
        return

    accounts = _configured_accounts()
    if not accounts:
        metafunc.parametrize(
            "account",
            [
                pytest.param(
                    None,
                    marks=pytest.mark.skip(reason=NO_ACCOUNTS_SKIP_REASON),
                    id="no-accounts",
                )
            ],
        )
        return

    metafunc.parametrize(
        "account",
        [pytest.param(account, id=account.key) for account in accounts],
    )


@pytest.fixture(scope="session")
def live_framework() -> Iterator[LiveFramework]:
    account_manager = AccountManager(AccountConfigStore(), make_token_store())
    quota_tracker = QuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=account_manager,
            quota_tracker=quota_tracker,
            mutating_guard=lambda _account: None,
            retry_policy=_retry_policy(),
        )
    )
    framework = LiveFramework(account_manager=account_manager, quota_tracker=quota_tracker)
    yield framework

    for account_key, total in sorted(framework.quota_by_account.items()):
        LOGGER.info("%s total live acid quota cost=%s", account_key, total)
        assert total < 200, f"live acid suite used {total} quota units for {account_key}"
