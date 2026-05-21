"""Tests for the Typer CLI entry point."""
# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from pathlib import Path
from typing import NoReturn, cast

import pytest
import typer
from typer.testing import CliRunner

from youtube_mcp import cli, server
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
    config_path: Path
    public_api_key_configured: bool

    def __init__(
        self,
        accounts: list[AccountConfig] | None = None,
        public_api_key_configured: bool = False,
    ) -> None:
        self.accounts = [make_account()] if accounts is None else accounts
        self.remove_calls = []
        self.config_path = Path("/tmp/youtube-mcp/accounts.json")
        self.public_api_key_configured = public_api_key_configured

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


def test_serve_configures_framework_resources_before_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeCliManager()
    serve_calls: list[dict[str, object]] = []

    def empty_account_provider() -> list[server.AccountResource]:
        return []

    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))
    monkeypatch.setattr(server, "_account_provider", empty_account_provider)

    def fake_serve_server(**kwargs: object) -> None:
        serve_calls.append(kwargs)
        assert server.accounts_resource() == [
            {
                "key": "primary",
                "channel_handle": "@primary",
                "channel_id": "UC123",
                "scopes": [YouTubeScope.READONLY.value],
            }
        ]
        assert server.status_resource()["configured_accounts"] == 1

    monkeypatch.setattr(cli, "serve_server", fake_serve_server)

    result = runner.invoke(cli.app, ["serve"])

    assert result.exit_code == 0
    assert serve_calls == [{"transport": "stdio", "host": "127.0.0.1", "port": 8765}]
    assert "account_config=/tmp/youtube-mcp/accounts.json" in result.output
    assert "configured_accounts=1" in result.output


def test_serve_skips_auth_wizard_when_public_api_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeCliManager(accounts=[], public_api_key_configured=True)
    wizard_calls: list[object] = []
    serve_calls: list[dict[str, object]] = []

    def empty_account_provider() -> list[server.AccountResource]:
        return []

    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))
    monkeypatch.setattr(server, "_account_provider", empty_account_provider)

    def fake_run_wizard(**kwargs: object) -> bool:
        wizard_calls.append(kwargs)
        return False

    def fake_serve_server(**kwargs: object) -> None:
        serve_calls.append(kwargs)
        assert server.status_resource()["configured_accounts"] == 0

    monkeypatch.setattr(cli, "run_wizard", fake_run_wizard)
    monkeypatch.setattr(cli, "serve_server", fake_serve_server)

    result = runner.invoke(cli.app, ["serve"])

    assert result.exit_code == 0
    assert wizard_calls == []
    assert serve_calls == [{"transport": "stdio", "host": "127.0.0.1", "port": 8765}]
    assert "configured_accounts=0" in result.output
    assert "public_api_key=configured" in result.output


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
