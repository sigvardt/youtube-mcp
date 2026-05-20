"""Safety guard for live tests that execute mutating YouTube operations.

The pytest fixture is intentionally exported from this source module so live test modules can
import ``mutating_guard`` directly without depending on a repository-local ``tests/conftest.py``.
Framework env gating decides whether to call the guard; once called, ``assert_allowed`` always
validates the account handle and never treats ``MutatingGuardConfig.enforce`` as a bypass.
"""
# pyright: reportImplicitOverride=false, reportMissingTypeStubs=false

from __future__ import annotations

import os
from collections.abc import Callable
from types import TracebackType
from typing import cast

from youtube_mcp.auth.accounts import AccountManager
from youtube_mcp.types import MutatingGuardConfig

_pytest_fixture: Callable[..., object] | None
try:
    from pytest import fixture as _imported_pytest_fixture
except ModuleNotFoundError:  # pragma: no cover - production installs need not include pytest
    _pytest_fixture = None
else:
    _pytest_fixture = _imported_pytest_fixture

_ALLOWED_HANDLE_ENV = "YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE"


class MutatingOpForbiddenError(Exception):
    """Raised when a mutating operation targets any account except the allowed handle."""

    def __init__(self, account_key: str, expected: str, got: str | None) -> None:
        self.account_key: str = account_key
        self.expected: str = expected
        self.got: str | None = got
        super().__init__(account_key, expected, got)

    def __str__(self) -> str:
        got = "missing channel_handle" if self.got is None else repr(self.got)
        return (
            f"Mutating YouTube operation forbidden for account {self.account_key!r}: "
            f"expected channel_handle {self.expected!r}, got {got}"
        )


class MutatingGuard:
    """Allow mutating YouTube operations only for the configured channel handle."""

    def __init__(self, allowed_channel_handle: str | MutatingGuardConfig | None = None) -> None:
        self.config: MutatingGuardConfig = self._config_from_input(allowed_channel_handle)
        self.allowed_channel_handle: str = self.config.allowed_channel_handle
        self.enforce: bool = self.config.enforce

    def __enter__(self) -> MutatingGuard:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = (exc_type, exc, traceback)

    def assert_allowed(self, account_key: str, account_manager: AccountManager) -> None:
        config = account_manager.get(account_key)
        channel_handle = config.channel_handle
        if channel_handle != self.allowed_channel_handle:
            raise MutatingOpForbiddenError(
                account_key=account_key,
                expected=self.allowed_channel_handle,
                got=channel_handle,
            )

    @staticmethod
    def _config_from_input(
        allowed_channel_handle: str | MutatingGuardConfig | None,
    ) -> MutatingGuardConfig:
        if isinstance(allowed_channel_handle, MutatingGuardConfig):
            return allowed_channel_handle

        handle = allowed_channel_handle or os.environ.get(
            _ALLOWED_HANDLE_ENV,
            MutatingGuardConfig().allowed_channel_handle,
        )
        return MutatingGuardConfig(allowed_channel_handle=handle)


def _mutating_guard_fixture() -> MutatingGuard:
    return MutatingGuard()


mutating_guard: Callable[[], MutatingGuard]
if _pytest_fixture is None:
    mutating_guard = _mutating_guard_fixture
else:
    fixture_decorator = cast(
        Callable[[Callable[[], MutatingGuard]], Callable[[], MutatingGuard]],
        _pytest_fixture(name="mutating_guard"),
    )
    mutating_guard = fixture_decorator(_mutating_guard_fixture)


__all__ = ["MutatingGuard", "MutatingOpForbiddenError", "mutating_guard"]
