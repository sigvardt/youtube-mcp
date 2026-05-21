"""Tests for the Typer CLI entry point."""
# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from typing import NoReturn, cast

import pytest
import typer
from typer.testing import CliRunner

from youtube_mcp import cli
from youtube_mcp.auth.accounts import AccountManager
from youtube_mcp.auth.token_store import TokenStore
from youtube_mcp.types import AccountConfig, YouTubeScope
from youtube_mcp.utils.quota import QuotaTracker

runner = CliRunner()


def make_account() -> AccountConfig:
    return AccountConfig(
        key="primary",
        client_id="client-id",
        client_secret="client-secret",
        channel_id="UC123",
        channel_handle="@primary",
        oauth_scopes=[YouTubeScope.READONLY],
    )


class FakeCliManager:
    accounts: list[AccountConfig]
    remove_calls: list[str]

    def __init__(self, accounts: list[AccountConfig] | None = None) -> None:
        self.accounts = accounts or [make_account()]
        self.remove_calls = []

    def list(self) -> list[AccountConfig]:
        return self.accounts

    def get(self, _key: str) -> AccountConfig:
        return self.accounts[0]

    def remove(self, key: str) -> None:
        self.remove_calls.append(key)


def make_runtime(manager: object) -> cli.Runtime:
    return cli.Runtime(
        manager=cast(AccountManager, manager),
        token_store=cast(TokenStore, object()),
        quota_tracker=cast(QuotaTracker, object()),
    )


def _disable_tool_framework(runtime: cli.Runtime) -> None:
    _ = runtime


def _doctor_probe_ok(**kwargs: object) -> dict[str, object]:
    _ = kwargs
    return {"items": [{"id": "UC123"}]}


def _doctor_probe_empty(**kwargs: object) -> dict[str, object]:
    _ = kwargs
    return {"items": []}


def _doctor_probe_mismatch(**kwargs: object) -> dict[str, object]:
    _ = kwargs
    return {"items": [{"id": "UC999"}]}


def _doctor_probe_raises(**kwargs: object) -> NoReturn:
    _ = kwargs
    raise RuntimeError("boom")


def test_help_exits_zero_and_shows_command_tree() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    for command_name in (
        "serve",
        "auth",
        "add",
        "list",
        "remove",
        "refresh",
        "status",
        "doctor",
        "tools",
    ):
        assert command_name in result.output


def test_auth_help_lists_account_commands() -> None:
    result = runner.invoke(cli.app, ["auth", "--help"])

    assert result.exit_code == 0
    for command_name in ("add", "list", "remove", "refresh"):
        assert command_name in result.output


def test_tools_list_prints_registered_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[cli.ApiFilter | None] = []

    async def fake_collect_tools(api: cli.ApiFilter | None) -> list[cli.ToolDisplay]:
        calls.append(api)
        return [
            cli.ToolDisplay(
                name="youtube_abuseReports_insert",
                api="youtube",
                method="youtube.abuseReports.insert",
                summary="Submit an abuse report.",
            )
        ]

    monkeypatch.setattr(cli, "_collect_tools", fake_collect_tools)

    result = runner.invoke(cli.app, ["tools", "list", "--api", "youtube"])

    assert result.exit_code == 0
    assert calls == ["youtube"]
    assert "youtube_abuseReports_insert" in result.output
    assert "youtube.abuseReports.insert" in result.output
    assert "Submit an abuse report." in result.output


def test_auth_remove_requires_confirmation_and_yes_bypasses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeCliManager()
    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))

    cancel_result = runner.invoke(cli.app, ["auth", "remove", "primary"], input="n\n")

    assert cancel_result.exit_code == 1
    assert manager.remove_calls == []

    yes_result = runner.invoke(cli.app, ["auth", "remove", "primary", "--yes"])

    assert yes_result.exit_code == 0
    assert manager.remove_calls == ["primary"]
    assert "Removed account 'primary'." in yes_result.output


def test_doctor_reports_ok_and_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = FakeCliManager()
    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))
    monkeypatch.setattr(cli, "_configure_tool_framework", _disable_tool_framework)
    monkeypatch.setattr(cli, "youtube_channels_list", _doctor_probe_ok)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "primary\tOK" in result.output


def test_doctor_reports_empty_items_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeCliManager()
    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))
    monkeypatch.setattr(cli, "_configure_tool_framework", _disable_tool_framework)
    monkeypatch.setattr(cli, "youtube_channels_list", _doctor_probe_empty)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 1
    assert "primary\tFAIL: no channels returned" in result.output


def test_doctor_reports_channel_id_mismatch_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeCliManager()
    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))
    monkeypatch.setattr(cli, "_configure_tool_framework", _disable_tool_framework)
    monkeypatch.setattr(cli, "youtube_channels_list", _doctor_probe_mismatch)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 1
    assert "primary\tFAIL: channel_id mismatch (expected UC123, got UC999)" in result.output


def test_doctor_direct_call_raises_exit_on_fail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manager = FakeCliManager()
    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))
    monkeypatch.setattr(cli, "_configure_tool_framework", _disable_tool_framework)
    monkeypatch.setattr(cli, "youtube_channels_list", _doctor_probe_raises)

    with pytest.raises(typer.Exit) as exc_info:
        cli.doctor()

    captured = capsys.readouterr()
    assert exc_info.value.exit_code == 1
    assert "primary\tFAIL: boom" in captured.out
