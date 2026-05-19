"""Tests for youtube_mcp.auth.token_store."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import keyring
import keyring.errors
import pytest

from youtube_mcp.auth.token_store import (
    KEYRING_REGISTRY_KEY,
    FileTokenStore,
    KeyringTokenStore,
    make_token_store,
    migrate,
)
from youtube_mcp.types import TokenBundle


def make_bundle(label: str = "main") -> TokenBundle:
    return TokenBundle(
        access_token=f"access-{label}",
        refresh_token=f"refresh-{label}",
        expiry=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
        scopes=["https://www.googleapis.com/auth/youtube.readonly", label],
    )


def install_fake_keyring(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], str]:
    passwords: dict[tuple[str, str], str] = {}

    def get_password(service: str, username: str) -> str | None:
        return passwords.get((service, username))

    def set_password(service: str, username: str, password: str) -> None:
        passwords[(service, username)] = password

    def delete_password(service: str, username: str) -> None:
        _ = passwords.pop((service, username), None)

    monkeypatch.setattr(keyring, "get_password", get_password)
    monkeypatch.setattr(keyring, "set_password", set_password)
    monkeypatch.setattr(keyring, "delete_password", delete_password)
    return passwords


def file_mode(path: Path) -> int:
    return os.stat(path).st_mode & 0o777


def test_keyring_store_round_trips_compact_json_and_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passwords = install_fake_keyring(monkeypatch)
    store = KeyringTokenStore(service="unit-service")
    bundle = make_bundle()

    store.put("account-a", bundle)

    assert passwords[("unit-service", "account-a")] == bundle.model_dump_json()
    assert json.loads(passwords[("unit-service", KEYRING_REGISTRY_KEY)]) == ["account-a"]
    assert store.get("account-a") == bundle
    assert store.list_keys() == ["account-a"]


def test_keyring_delete_removes_token_and_registry_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passwords = install_fake_keyring(monkeypatch)
    store = KeyringTokenStore(service="unit-service")

    store.put("account-a", make_bundle("a"))
    store.put("account-b", make_bundle("b"))
    store.delete("account-a")

    assert ("unit-service", "account-a") not in passwords
    assert store.get("account-a") is None
    assert store.list_keys() == ["account-b"]
    assert json.loads(passwords[("unit-service", KEYRING_REGISTRY_KEY)]) == ["account-b"]


def test_file_store_writes_secure_default_path_and_compact_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    store = FileTokenStore()
    bundle = make_bundle()

    store.put("account-a", bundle)

    token_dir = tmp_path / "youtube-mcp" / "tokens"
    token_path = token_dir / "account-a.json"
    assert token_path.read_text(encoding="utf-8") == bundle.model_dump_json()
    assert file_mode(token_dir) == 0o700
    assert file_mode(token_path) == 0o600
    assert store.get("account-a") == bundle


def test_file_store_lists_and_deletes_json_tokens(tmp_path: Path) -> None:
    store = FileTokenStore(token_dir=tmp_path / "tokens")

    store.put("account-b", make_bundle("b"))
    store.put("account-a", make_bundle("a"))
    _ = (tmp_path / "tokens" / "ignored.txt").write_text("not a token", encoding="utf-8")

    assert store.list_keys() == ["account-a", "account-b"]

    store.delete("account-a")

    assert store.get("account-a") is None
    assert store.list_keys() == ["account-b"]


def test_make_token_store_auto_falls_back_to_file_and_warns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("YOUTUBE_MCP_TOKEN_STORE", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    def unavailable_keyring(_service: str, _username: str) -> str | None:
        raise keyring.errors.NoKeyringError()

    monkeypatch.setattr(keyring, "get_password", unavailable_keyring)

    store = make_token_store("auto")

    captured = capsys.readouterr()
    assert isinstance(store, FileTokenStore)
    assert "falling back to file token store" in captured.err


def test_env_override_forces_file_store_without_touching_keyring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_MCP_TOKEN_STORE", "file")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    def fail_if_called(_service: str, _username: str) -> str | None:
        raise AssertionError("keyring should not be read when file backend is forced")

    monkeypatch.setattr(keyring, "get_password", fail_if_called)

    store = make_token_store("keyring")

    assert isinstance(store, FileTokenStore)


def test_migrate_copies_file_tokens_to_keyring_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = install_fake_keyring(monkeypatch)
    src = FileTokenStore(token_dir=tmp_path / "source-tokens")
    dst = KeyringTokenStore(service="unit-service")
    first = make_bundle("first")
    second = make_bundle("second")
    src.put("account-a", first)
    src.put("account-b", second)

    copied = migrate(src, dst)

    assert copied == 2
    assert dst.list_keys() == ["account-a", "account-b"]
    assert dst.get("account-a") == first
    assert dst.get("account-b") == second


def test_make_token_store_keyring_backend_returns_keyring_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("YOUTUBE_MCP_TOKEN_STORE", raising=False)

    store = make_token_store("keyring")

    assert isinstance(store, KeyringTokenStore)
