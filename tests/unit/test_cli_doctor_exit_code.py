"""Doctor command exit-code regression tests."""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest
from click.testing import Result
from typer.testing import CliRunner

from youtube_mcp import cli
from youtube_mcp.auth.accounts import AccountManager
from youtube_mcp.auth.token_store import TokenStore
from youtube_mcp.types import AccountConfig, YouTubeScope
from youtube_mcp.utils.quota import QuotaTracker

runner = CliRunner()


def make_account(key: str) -> AccountConfig:
    return AccountConfig(
        key=key,
        client_id=f"{key}-client-id",
        client_secret=f"{key}-client-secret",
        channel_id=f"UC{key.upper()}",
        channel_handle=f"@{key}",
        oauth_scopes=[YouTubeScope.READONLY],
    )


class FakeDoctorManager:
    accounts: list[AccountConfig]

    def __init__(self, accounts: list[AccountConfig]) -> None:
        self.accounts = accounts

    def list(self) -> list[AccountConfig]:
        return self.accounts


def make_runtime(accounts: list[AccountConfig]) -> cli.Runtime:
    manager = FakeDoctorManager(accounts)
    return cli.Runtime(
        manager=cast(AccountManager, cast(object, manager)),
        token_store=cast(TokenStore, object()),
        quota_tracker=cast(QuotaTracker, object()),
    )


def disable_tool_framework(runtime: cli.Runtime) -> None:
    _ = runtime


def doctor_probe_for(failing_accounts: set[str]) -> Callable[..., dict[str, object]]:
    def fake_doctor_probe(**kwargs: object) -> dict[str, object]:
        account = kwargs["account"]
        assert isinstance(account, str)
        if account in failing_accounts:
            return {"items": [{"id": "UCWRONG"}]}
        return {"items": [{"id": f"UC{account.upper()}"}]}

    return fake_doctor_probe


def invoke_doctor_with_statuses(
    monkeypatch: pytest.MonkeyPatch,
    accounts: list[str],
    failing_accounts: set[str],
) -> Result:
    monkeypatch.setattr(
        cli,
        "_runtime",
        lambda: make_runtime([make_account(key) for key in accounts]),
    )
    monkeypatch.setattr(cli, "_configure_tool_framework", disable_tool_framework)
    monkeypatch.setattr(cli, "youtube_channels_list", doctor_probe_for(failing_accounts))
    return runner.invoke(cli.app, ["doctor"])


def test_doctor_all_pass_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    result = invoke_doctor_with_statuses(monkeypatch, ["alpha", "beta"], set())

    assert result.exit_code == 0
    assert result.output == "alpha\tOK\nbeta\tOK\n"


def test_doctor_one_fail_among_many_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    result = invoke_doctor_with_statuses(monkeypatch, ["alpha", "beta", "gamma"], {"beta"})

    assert result.exit_code == 1
    expected_output = (
        "alpha\tOK\n"
        "beta\tFAIL: channel_id mismatch (expected UCBETA, got UCWRONG)\n"
        "gamma\tOK\n"
    )
    assert result.output == expected_output


def test_doctor_all_fail_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    result = invoke_doctor_with_statuses(monkeypatch, ["alpha", "beta"], {"alpha", "beta"})

    assert result.exit_code == 1
    expected_output = (
        "alpha\tFAIL: channel_id mismatch (expected UCALPHA, got UCWRONG)\n"
        "beta\tFAIL: channel_id mismatch (expected UCBETA, got UCWRONG)\n"
    )
    assert result.output == expected_output
