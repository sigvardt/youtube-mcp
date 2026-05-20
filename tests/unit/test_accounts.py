"""Tests for youtube_mcp.auth.accounts."""
# pyright: reportAny=false, reportMissingTypeStubs=false, reportUnannotatedClassAttribute=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnusedCallResult=false, reportUnusedParameter=false

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import youtube_mcp.auth.accounts as accounts_module
from youtube_mcp.auth.accounts import AccountConfigStore, AccountManager, AccountNotFoundError
from youtube_mcp.auth.oauth_flow import AUTH_URI, TOKEN_URI
from youtube_mcp.types import AccountConfig, TokenBundle, YouTubeScope

FUTURE_EXPIRY = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
PAST_EXPIRY = datetime(2020, 1, 1, 12, 0, tzinfo=UTC)


class InMemoryTokenStore:
    """Thread-safe in-memory token store for AccountManager tests."""

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


class FakeCredentials:
    """Minimal replacement for google.oauth2.credentials.Credentials."""

    refresh_count = 0
    refresh_lock = threading.Lock()

    def __init__(
        self,
        *,
        token: str,
        refresh_token: str,
        token_uri: str,
        client_id: str,
        client_secret: str,
        scopes: list[str],
    ) -> None:
        self.token = token
        self.refresh_token = refresh_token
        self.token_uri = token_uri
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.expiry = PAST_EXPIRY if token == "expired-access" else FUTURE_EXPIRY
        self.expired = token == "expired-access"

    def refresh(self, request: object) -> None:
        _ = request
        with self.refresh_lock:
            type(self).refresh_count += 1
        self.token = "fresh-access"
        self.expiry = FUTURE_EXPIRY
        self.expired = False


def make_account(key: str = "brand") -> AccountConfig:
    return AccountConfig(
        key=key,
        client_id="client-id",
        client_secret="client-secret",
        channel_id="UC123",
        channel_handle="@brand",
        oauth_scopes=[YouTubeScope.READONLY],
        created_at=FUTURE_EXPIRY,
    )


def make_bundle(access_token: str = "access-token") -> TokenBundle:
    return TokenBundle(
        access_token=access_token,
        refresh_token="refresh-token",
        expiry=PAST_EXPIRY if access_token == "expired-access" else FUTURE_EXPIRY,
        scopes=[YouTubeScope.READONLY.value],
    )


def write_client_creds(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                    "auth_uri": AUTH_URI,
                    "token_uri": TOKEN_URI,
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
        encoding="utf-8",
    )


def file_mode(path: Path) -> int:
    return os.stat(path).st_mode & 0o777


def make_youtube_service(response: dict[str, object]) -> MagicMock:
    service = MagicMock()
    service.channels.return_value.list.return_value.execute.return_value = response
    return service


def test_config_store_uses_xdg_path_and_secure_permissions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    store = AccountConfigStore()
    account = make_account()

    store.save([account])

    assert store.path == config_home / "youtube-mcp" / "accounts.json"
    assert file_mode(store.path.parent) == 0o700
    assert file_mode(store.path) == 0o600
    assert store.load() == [account]
    assert "access-token" not in store.path.read_text(encoding="utf-8")


def test_add_discover_list(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client_creds_path = tmp_path / "client.json"
    write_client_creds(client_creds_path)
    config_store = AccountConfigStore(tmp_path / "accounts.json")
    token_store = InMemoryTokenStore()
    bundle = make_bundle()
    captured: dict[str, object] = {}
    youtube_service = make_youtube_service(
        {"items": [{"id": "UC999", "snippet": {"customUrl": "brandhandle"}}]}
    )

    def oauth_runner(account: AccountConfig, scopes: list[str]) -> TokenBundle:
        captured["account"] = account
        captured["scopes"] = scopes
        return bundle

    build_mock = MagicMock(return_value=youtube_service)
    monkeypatch.setattr(accounts_module, "build", build_mock)

    manager = AccountManager(config_store, token_store, oauth_runner=oauth_runner)
    account = manager.add("brand", client_creds_path, [YouTubeScope.READONLY])

    assert captured["account"] == AccountConfig(
        key="brand",
        client_id="client-id",
        client_secret="client-secret",
        oauth_scopes=[YouTubeScope.READONLY],
        created_at=account.created_at,
    )
    assert captured["scopes"] == [YouTubeScope.READONLY.value]
    assert token_store.get("brand") == bundle
    assert account.channel_id == "UC999"
    assert account.channel_handle == "@brandhandle"
    assert manager.list() == [account]
    assert manager.get("brand") == account
    build_mock.assert_called_once()
    youtube_service.channels.return_value.list.assert_called_once_with(part="snippet,id", mine=True)
    assert "access-token" not in config_store.path.read_text(encoding="utf-8")


def test_add_handles_empty_channel_discovery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client_creds_path = tmp_path / "client.json"
    write_client_creds(client_creds_path)
    config_store = AccountConfigStore(tmp_path / "accounts.json")
    token_store = InMemoryTokenStore()
    empty_channel_service = make_youtube_service({"items": []})
    monkeypatch.setattr(accounts_module, "build", MagicMock(return_value=empty_channel_service))

    manager = AccountManager(
        config_store,
        token_store,
        oauth_runner=lambda account, scopes: make_bundle(),
    )

    account = manager.add("brand", client_creds_path, [YouTubeScope.READONLY])

    assert account.channel_id is None
    assert account.channel_handle is None
    assert "no YouTube channel discovered" in capsys.readouterr().err


def test_unknown_account_raises(tmp_path: Path) -> None:
    manager = AccountManager(AccountConfigStore(tmp_path / "accounts.json"), InMemoryTokenStore())

    with pytest.raises(AccountNotFoundError):
        _ = manager.get("missing")


def test_get_credentials_refreshes_and_persists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    FakeCredentials.refresh_count = 0
    monkeypatch.setattr(accounts_module, "Credentials", FakeCredentials)
    config_store = AccountConfigStore(tmp_path / "accounts.json")
    config_store.save([make_account()])
    token_store = InMemoryTokenStore()
    token_store.put("brand", make_bundle("expired-access"))
    manager = AccountManager(config_store, token_store)

    credentials = manager.get_credentials("brand")
    stored_bundle = token_store.get("brand")

    assert credentials.token == "fresh-access"
    assert stored_bundle is not None
    assert stored_bundle.access_token == "fresh-access"
    assert stored_bundle.expiry == FUTURE_EXPIRY
    assert FakeCredentials.refresh_count == 1


def test_concurrent_refresh_dedup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    FakeCredentials.refresh_count = 0
    monkeypatch.setattr(accounts_module, "Credentials", FakeCredentials)
    config_store = AccountConfigStore(tmp_path / "accounts.json")
    config_store.save([make_account()])
    token_store = InMemoryTokenStore()
    token_store.put("brand", make_bundle("expired-access"))
    manager = AccountManager(config_store, token_store)

    def fetch_token(_: int) -> str:
        token = manager.get_credentials("brand").token
        assert isinstance(token, str)
        return token

    with ThreadPoolExecutor(max_workers=8) as executor:
        tokens = list(executor.map(fetch_token, range(8)))

    assert tokens == ["fresh-access"] * 8
    assert FakeCredentials.refresh_count == 1


def test_service_builders_cache_per_account_and_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(accounts_module, "Credentials", FakeCredentials)
    config_store = AccountConfigStore(tmp_path / "accounts.json")
    config_store.save([make_account()])
    token_store = InMemoryTokenStore()
    token_store.put("brand", make_bundle())
    built_services: list[tuple[str, str, object]] = []

    def fake_build(api_name: str, version: str, credentials: object) -> object:
        service = object()
        built_services.append((api_name, version, service))
        return service

    monkeypatch.setattr(accounts_module, "build", fake_build)
    manager = AccountManager(config_store, token_store)

    youtube_a = manager.get_youtube_service("brand")
    youtube_b = manager.get_youtube_service("brand")
    analytics = manager.get_analytics_service("brand")
    reporting = manager.get_reporting_service("brand")

    assert youtube_a is youtube_b
    assert youtube_a is not analytics
    assert youtube_a is not reporting
    assert [(api_name, version) for api_name, version, _ in built_services] == [
        ("youtube", "v3"),
        ("youtubeAnalytics", "v2"),
        ("youtubereporting", "v1"),
    ]


def test_remove_deletes_token_config_and_cached_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(accounts_module, "Credentials", FakeCredentials)
    config_store = AccountConfigStore(tmp_path / "accounts.json")
    config_store.save([make_account()])
    token_store = InMemoryTokenStore()
    token_store.put("brand", make_bundle())

    def fake_build_for_remove(*args: object, **kwargs: object) -> object:
        _ = args, kwargs
        return object()

    monkeypatch.setattr(accounts_module, "build", fake_build_for_remove)
    manager = AccountManager(config_store, token_store)
    _ = manager.get_youtube_service("brand")

    manager.remove("brand")

    assert token_store.get("brand") is None
    assert config_store.load() == []
    with pytest.raises(AccountNotFoundError):
        _ = manager.get_youtube_service("brand")
