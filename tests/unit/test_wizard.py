# pyright: reportAny=false, reportMissingImports=false, reportMissingTypeStubs=false, reportUnannotatedClassAttribute=false, reportUnusedCallResult=false
"""Tests for the interactive first-run setup wizard."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import youtube_mcp.auth.accounts as accounts_module
import youtube_mcp.cli as cli_module
from youtube_mcp.auth.accounts import AccountConfigStore, AccountManager
from youtube_mcp.auth.oauth_flow import AUTH_URI, TOKEN_URI
from youtube_mcp.auth.wizard import run_wizard
from youtube_mcp.types import AccountConfig, TokenBundle, YouTubeScope

FUTURE_EXPIRY = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)


class InMemoryTokenStore:
    """In-memory token store for wizard tests."""

    def __init__(self) -> None:
        self._bundles: dict[str, TokenBundle] = {}
        self._lock = threading.Lock()

    def get(self, account_key: str) -> TokenBundle | None:
        with self._lock:
            bundle = self._bundles.get(account_key)
            return None if bundle is None else bundle.model_copy(deep=True)

    def put(self, account_key: str, bundle: TokenBundle) -> None:
        with self._lock:
            self._bundles[account_key] = bundle.model_copy(deep=True)

    def delete(self, account_key: str) -> None:
        with self._lock:
            _ = self._bundles.pop(account_key, None)

    def list_keys(self) -> list[str]:
        with self._lock:
            return sorted(self._bundles)


def scripted_input(responses: list[str]) -> Callable[[str], str]:
    response_iter = iter(responses)

    def read_prompt(prompt: str) -> str:
        assert prompt == ""
        return next(response_iter)

    return read_prompt


def write_client_creds(path: Path) -> None:
    payload = {
        "installed": {
            "client_id": "client-id",
            "client_secret": "client-secret",
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": ["http://localhost"],
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_bundle() -> TokenBundle:
    return TokenBundle(
        access_token="access-token",
        refresh_token="refresh-token",
        expiry=FUTURE_EXPIRY,
        scopes=[YouTubeScope.FORCE_SSL.value, YouTubeScope.ANALYTICS_READONLY.value],
    )


def make_youtube_service() -> MagicMock:
    service = MagicMock()
    service.channels.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "UC999", "snippet": {"customUrl": "brandhandle"}}]
    }
    return service


def test_run_wizard_end_to_end_with_mocked_oauth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client_creds_path = tmp_path / "client.json"
    write_client_creds(client_creds_path)
    token_store = InMemoryTokenStore()
    oauth_calls: list[tuple[AccountConfig, list[str]]] = []

    def oauth_runner(account: AccountConfig, scopes: list[str]) -> TokenBundle:
        oauth_calls.append((account, scopes))
        return make_bundle()

    monkeypatch.setattr(accounts_module, "build", MagicMock(return_value=make_youtube_service()))
    manager = AccountManager(
        AccountConfigStore(tmp_path / "accounts.json"),
        token_store,
        oauth_runner=oauth_runner,
    )

    result = run_wizard(
        manager=manager,
        input_func=scripted_input(["main", str(client_creds_path), "", "n"]),
    )

    captured = capsys.readouterr()
    account = manager.get("main")
    assert result is True
    assert captured.out == ""
    assert "No YouTube accounts are configured" in captured.err
    assert "Path to GCP OAuth client credentials JSON?" in captured.err
    assert "Tip: in the Google account picker" in captured.err
    assert "Discovered channel: @brandhandle / UC999" in captured.err
    assert account.channel_handle == "@brandhandle"
    assert account.channel_id == "UC999"
    assert account.oauth_scopes == [YouTubeScope.FORCE_SSL, YouTubeScope.ANALYTICS_READONLY]
    assert token_store.get("main") == make_bundle()
    assert oauth_calls[0][1] == [
        YouTubeScope.FORCE_SSL.value,
        YouTubeScope.ANALYTICS_READONLY.value,
    ]


def test_auth_add_non_interactive_with_creds_and_no_scopes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    creds_path = tmp_path / "client.json"
    write_client_creds(creds_path)

    class FakeManager:
        def __init__(self) -> None:
            self.last_call: tuple[str, Path, list[YouTubeScope]] | None = None

        def list(self) -> list[AccountConfig]:
            return []

        def add(
            self,
            key: str,
            client_creds_path: Path,
            scopes: list[YouTubeScope],
        ) -> AccountConfig:
            self.last_call = (key, client_creds_path, list(scopes))
            return AccountConfig(
                key=key,
                client_id="client-id",
                client_secret="client-secret",
                oauth_scopes=scopes,
                channel_handle="@test",
                channel_id="UC_test",
            )

    def no_prompts(prompt: str) -> str:
        raise AssertionError(f"unexpected interactive prompt: {prompt!r}")

    manager = FakeManager()
    result = run_wizard(
        manager=manager,
        input_func=no_prompts,
        initial_key="testkey",
        initial_client_creds_path=creds_path,
        initial_scope_selection="",
        offer_add_another=False,
    )

    captured = capsys.readouterr()
    assert result is True
    assert manager.last_call == (
        "testkey",
        creds_path,
        [YouTubeScope.FORCE_SSL, YouTubeScope.ANALYTICS_READONLY],
    )
    assert "Google Cloud OAuth client credentials are required." not in captured.err
    assert "Path to GCP OAuth client credentials JSON?" not in captured.err


def test_run_wizard_handles_no_add_another_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_store = AccountConfigStore(tmp_path / "accounts.json")
    config_store.save(
        [
            AccountConfig(
                key="main",
                client_id="client-id",
                client_secret="client-secret",
                channel_handle="@brandhandle",
                oauth_scopes=[YouTubeScope.FORCE_SSL],
            )
        ]
    )
    manager = AccountManager(config_store, InMemoryTokenStore())

    result = run_wizard(manager=manager, input_func=scripted_input(["n"]))

    captured = capsys.readouterr()
    assert result is True
    assert captured.out == ""
    assert "Configured YouTube accounts:" in captured.err
    assert "Add another account? [y/N]" in captured.err
    assert "Setup unchanged." in captured.err
    assert manager.list()[0].key == "main"


def test_run_wizard_invalid_client_creds_path_can_retry_then_abort(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manager = AccountManager(AccountConfigStore(tmp_path / "accounts.json"), InMemoryTokenStore())
    missing_path = tmp_path / "missing.json"

    result = run_wizard(
        manager=manager,
        input_func=scripted_input(["main", str(missing_path), ""]),
    )

    captured = capsys.readouterr()
    assert result is False
    assert captured.out == ""
    assert "Client credentials file is not readable" in captured.err
    assert "Try another path, or press Enter to abort." in captured.err
    assert "Setup aborted before OAuth." in captured.err
    assert manager.list() == []


def test_cli_no_args_triggers_wizard(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object | None] = []

    def fake_runtime() -> object:
        return MagicMock()

    def fake_run_wizard(**kwargs: object) -> bool:
        calls.append(kwargs.get("manager"))
        return True

    monkeypatch.setattr(cli_module, "_runtime", fake_runtime)
    monkeypatch.setattr(cli_module, "run_wizard", fake_run_wizard)

    result = CliRunner().invoke(cli_module.app, [])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert len(calls) == 1
