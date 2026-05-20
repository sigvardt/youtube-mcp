"""Tests for the Typer CLI entry point."""
# pyright: reportMissingTypeStubs=false, reportAny=false

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

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


def make_runtime(manager: MagicMock) -> cli.Runtime:
    return cli.Runtime(
        manager=cast(AccountManager, manager),
        token_store=cast(TokenStore, MagicMock()),
        quota_tracker=cast(QuotaTracker, MagicMock()),
    )


def _disable_tool_framework(runtime: cli.Runtime) -> None:
    _ = runtime


def _doctor_probe_pass(**kwargs: object) -> dict[str, object]:
    _ = kwargs
    return {"id": "probe-1"}


def _doctor_probe_fail(**kwargs: object) -> dict[str, object]:
    _ = kwargs
    return {"error": {"reason": "insufficientPermissions"}}


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
                name="youtube_tests_insert",
                api="youtube",
                method="youtube.tests.insert",
                summary="Run auth probe.",
            )
        ]

    monkeypatch.setattr(cli, "_collect_tools", fake_collect_tools)

    result = runner.invoke(cli.app, ["tools", "list", "--api", "youtube"])

    assert result.exit_code == 0
    assert calls == ["youtube"]
    assert "youtube_tests_insert" in result.output
    assert "youtube.tests.insert" in result.output
    assert "Run auth probe." in result.output


def test_auth_remove_requires_confirmation_and_yes_bypasses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MagicMock()
    manager.get.return_value = make_account()
    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))

    cancel_result = runner.invoke(cli.app, ["auth", "remove", "primary"], input="n\n")

    assert cancel_result.exit_code == 1
    manager.remove.assert_not_called()

    yes_result = runner.invoke(cli.app, ["auth", "remove", "primary", "--yes"])

    assert yes_result.exit_code == 0
    manager.remove.assert_called_once_with("primary")
    assert "Removed account 'primary'." in yes_result.output


def test_doctor_reports_pass_and_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = MagicMock()
    manager.list.return_value = [make_account()]
    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))
    monkeypatch.setattr(cli, "_configure_tool_framework", _disable_tool_framework)
    monkeypatch.setattr(cli, "youtube_tests_insert", _doctor_probe_pass)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "primary\tPASS" in result.output


def test_doctor_reports_error_reason_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MagicMock()
    manager.list.return_value = [make_account()]
    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))
    monkeypatch.setattr(cli, "_configure_tool_framework", _disable_tool_framework)
    monkeypatch.setattr(cli, "youtube_tests_insert", _doctor_probe_fail)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 1
    assert "primary\tFAIL: insufficientPermissions" in result.output


def test_doctor_direct_call_raises_exit_on_fail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manager = MagicMock()
    manager.list.return_value = [make_account()]
    monkeypatch.setattr(cli, "_runtime", lambda: make_runtime(manager))
    monkeypatch.setattr(cli, "_configure_tool_framework", _disable_tool_framework)
    monkeypatch.setattr(cli, "youtube_tests_insert", _doctor_probe_fail)

    with pytest.raises(typer.Exit) as exc_info:
        cli.doctor()

    captured = capsys.readouterr()
    assert exc_info.value.exit_code == 1
    assert "primary\tFAIL: insufficientPermissions" in captured.out
