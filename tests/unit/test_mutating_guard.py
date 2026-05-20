"""Tests for the live mutating-account safety guard."""
# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from typing import cast

import pytest

from youtube_mcp.auth.accounts import AccountManager, AccountNotFoundError
from youtube_mcp.tools._framework import (
    AccountManagerProtocol,
    FrameworkContext,
    QuotaTrackerProtocol,
    configure_framework,
    youtube_tool,
)
from youtube_mcp.types import AccountConfig, MutatingGuardConfig, RetryPolicy, YouTubeScope
from youtube_mcp.utils.mutating_guard import (
    MutatingGuard,
    MutatingOpForbiddenError,
    mutating_guard,
)


class FakeAccountManager:
    def __init__(self, accounts: dict[str, AccountConfig]) -> None:
        self._accounts: dict[str, AccountConfig] = accounts
        self.get_calls: list[str] = []
        self.credentials_calls: list[str] = []
        self.youtube_calls: list[str] = []
        self.analytics_calls: list[str] = []
        self.reporting_calls: list[str] = []

    def get(self, key: str) -> AccountConfig:
        self.get_calls.append(key)
        try:
            return self._accounts[key]
        except KeyError as exc:
            raise AccountNotFoundError(f"Account {key!r} is not configured") from exc

    def get_credentials(self, key: str) -> object:
        self.credentials_calls.append(key)
        return object()

    def get_youtube_service(self, key: str) -> object:
        self.youtube_calls.append(key)
        return object()

    def get_analytics_service(self, key: str) -> object:
        self.analytics_calls.append(key)
        return object()

    def get_reporting_service(self, key: str) -> object:
        self.reporting_calls.append(key)
        return object()


class FakeQuotaTracker:
    enforce: bool = False

    def __init__(self) -> None:
        self.preflight_calls: list[tuple[str, int]] = []
        self.record_calls: list[tuple[str, int]] = []

    def would_exceed(self, account_key: str, units: int) -> bool:
        self.preflight_calls.append((account_key, units))
        return False

    def record(self, account_key: str, units: int) -> None:
        self.record_calls.append((account_key, units))


def _account(key: str, channel_handle: str | None) -> AccountConfig:
    return AccountConfig(
        key=key,
        client_id="client-id",
        client_secret="client-secret",
        channel_handle=channel_handle,
        oauth_scopes=[YouTubeScope.FORCE_SSL],
    )


def _guard_manager(account: AccountConfig) -> AccountManager:
    return cast(AccountManager, cast(object, FakeAccountManager({account.key: account})))


def _framework_context(
    manager: FakeAccountManager,
    tracker: FakeQuotaTracker,
) -> FrameworkContext:
    return FrameworkContext(
        account_manager=cast(AccountManagerProtocol, manager),
        quota_tracker=cast(QuotaTrackerProtocol, tracker),
        retry_policy=RetryPolicy(initial_wait=0.001, max_wait=0.01, multiplier=1.0, jitter=False),
    )


def test_jsigvardt_allowed() -> None:
    guard = MutatingGuard(allowed_channel_handle="@jsigvardt")
    account = _account("primary", "@jsigvardt")

    guard.assert_allowed("primary", _guard_manager(account))


def test_other_handle_raises() -> None:
    guard = MutatingGuard(allowed_channel_handle="@jsigvardt")
    account = _account("primary", "@other-channel")

    with pytest.raises(MutatingOpForbiddenError) as exc_info:
        guard.assert_allowed("primary", _guard_manager(account))

    assert exc_info.value.account_key == "primary"
    assert exc_info.value.expected == "@jsigvardt"
    assert exc_info.value.got == "@other-channel"
    assert "expected channel_handle '@jsigvardt', got '@other-channel'" in str(exc_info.value)


def test_missing_handle_raises() -> None:
    guard = MutatingGuard(allowed_channel_handle="@jsigvardt")
    account = _account("primary", None)

    with pytest.raises(MutatingOpForbiddenError) as exc_info:
        guard.assert_allowed("primary", _guard_manager(account))

    assert exc_info.value.got is None
    assert "missing channel_handle" in str(exc_info.value)


def test_account_not_found_propagates() -> None:
    manager = cast(AccountManager, cast(object, FakeAccountManager({})))

    with pytest.raises(AccountNotFoundError):
        MutatingGuard().assert_allowed("missing", manager)


def test_env_override_allowed_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE", "@secondary-live")
    guard = MutatingGuard()
    account = _account("secondary", "@secondary-live")

    assert guard.allowed_channel_handle == "@secondary-live"
    guard.assert_allowed("secondary", _guard_manager(account))


def test_config_constructor_and_context_manager() -> None:
    config = MutatingGuardConfig(allowed_channel_handle="@fixture-live", enforce=False)
    guard = MutatingGuard(config)

    with guard as active_guard:
        assert active_guard is guard

    assert guard.config == config
    assert guard.allowed_channel_handle == "@fixture-live"
    assert guard.enforce is False


def test_fixture_callable_exported() -> None:
    assert callable(mutating_guard)


def test_fixture_wiring(mutating_guard: MutatingGuard) -> None:
    assert isinstance(mutating_guard, MutatingGuard)
    assert mutating_guard.allowed_channel_handle == "@jsigvardt"


def test_framework_enforces_guard_for_mutating_tool_when_env_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_MCP_ENFORCE_GUARD", "1")
    manager = FakeAccountManager({"primary": _account("primary", "@other-channel")})
    tracker = FakeQuotaTracker()
    configure_framework(_framework_context(manager, tracker))
    calls = 0

    @youtube_tool(
        name="youtube_mutating_guard_framework_denied",
        api="youtube",
        method="youtube.comments.insert",
        scopes=[YouTubeScope.FORCE_SSL],
        mutating=True,
    )
    def framework_tool(account: str) -> dict[str, bool]:
        nonlocal calls
        _ = account
        calls += 1
        return {"ok": True}

    with pytest.raises(MutatingOpForbiddenError):
        _ = framework_tool(account="primary")

    assert calls == 0
    assert manager.get_calls == ["primary"]
    assert manager.youtube_calls == []
    assert tracker.record_calls == []


def test_framework_skips_strict_guard_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YOUTUBE_MCP_ENFORCE_GUARD", raising=False)
    manager = FakeAccountManager({"primary": _account("primary", "@other-channel")})
    tracker = FakeQuotaTracker()
    configure_framework(_framework_context(manager, tracker))

    @youtube_tool(
        name="youtube_mutating_guard_framework_unset_env",
        api="youtube",
        method="youtube.comments.insert",
        scopes=[YouTubeScope.FORCE_SSL],
        mutating=True,
    )
    def framework_tool(account: str) -> dict[str, bool]:
        _ = account
        return {"ok": True}

    assert framework_tool(account="primary") == {"ok": True}
    assert manager.get_calls == []
    assert manager.youtube_calls == ["primary"]
    assert tracker.record_calls == [("primary", 50)]
