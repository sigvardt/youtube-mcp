"""Doctor command exit-code regression tests."""
# pyright: reportMissingTypeStubs=false, reportAny=false, reportUnknownMemberType=false

from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from unittest.mock import MagicMock

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


def make_runtime(accounts: list[AccountConfig]) -> cli.Runtime:
    manager = MagicMock()
    manager.list.return_value = accounts
    return cli.Runtime(
        manager=cast(AccountManager, manager),
        token_store=cast(TokenStore, MagicMock()),
        quota_tracker=cast(QuotaTracker, MagicMock()),
    )


def disable_tool_framework(runtime: cli.Runtime) -> None:
    _ = runtime


def doctor_probe(**kwargs: object) -> dict[str, object]:
    return {"account": kwargs["account"]}


def doctor_status_for(failing_accounts: set[str]) -> object:
    def fake_doctor_status(response: Mapping[str, object]) -> tuple[str, bool]:
        account = response["account"]
        assert isinstance(account, str)
        if account in failing_accounts:
            return f"FAIL: {account}", True
        return "PASS", False

    return fake_doctor_status


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
    monkeypatch.setattr(cli, "youtube_tests_insert", doctor_probe)
    monkeypatch.setattr(cli, "_doctor_status", doctor_status_for(failing_accounts))
    return runner.invoke(cli.app, ["doctor"])


def test_doctor_all_pass_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    result = invoke_doctor_with_statuses(monkeypatch, ["alpha", "beta"], set())

    assert result.exit_code == 0
    assert result.output == "alpha\tPASS\nbeta\tPASS\n"


def test_doctor_one_fail_among_many_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    result = invoke_doctor_with_statuses(monkeypatch, ["alpha", "beta", "gamma"], {"beta"})

    assert result.exit_code == 1
    assert result.output == "alpha\tPASS\nbeta\tFAIL: beta\ngamma\tPASS\n"


def test_doctor_all_fail_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    result = invoke_doctor_with_statuses(monkeypatch, ["alpha", "beta"], {"alpha", "beta"})

    assert result.exit_code == 1
    assert result.output == "alpha\tFAIL: alpha\nbeta\tFAIL: beta\n"
