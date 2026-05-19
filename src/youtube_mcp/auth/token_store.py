"""Token storage backends for OAuth token bundles."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Literal, Protocol, cast

import keyring
import keyring.errors
from pydantic import TypeAdapter

from youtube_mcp.types import TokenBundle

DEFAULT_KEYRING_SERVICE = "youtube-mcp"
KEYRING_REGISTRY_KEY = "__youtube_mcp_registry__"
TokenStoreBackend = Literal["keyring", "file", "auto"]
REGISTRY_KEYS_ADAPTER: TypeAdapter[list[str]] = TypeAdapter(list[str])


class TokenStore(Protocol):
    """Persistence interface for OAuth token bundles."""

    def get(self, account_key: str) -> TokenBundle | None:
        """Return the token bundle for account_key, or None when absent."""
        ...

    def put(self, account_key: str, bundle: TokenBundle) -> None:
        """Persist bundle for account_key."""
        ...

    def delete(self, account_key: str) -> None:
        """Remove any stored token bundle for account_key."""
        ...

    def list_keys(self) -> list[str]:
        """Return account keys with stored token bundles."""
        ...


class KeyringTokenStore:
    """Store tokens in the OS keyring.

    Keyring has no portable enumeration API, so list_keys() is backed by a sidecar
    keyring entry under KEYRING_REGISTRY_KEY containing a compact JSON list of account keys.
    """

    def __init__(self, service: str = DEFAULT_KEYRING_SERVICE) -> None:
        self.service: str = service

    def get(self, account_key: str) -> TokenBundle | None:
        payload = keyring.get_password(self.service, account_key)
        if payload is None:
            return None
        return TokenBundle.model_validate_json(payload)

    def put(self, account_key: str, bundle: TokenBundle) -> None:
        keyring.set_password(self.service, account_key, bundle.model_dump_json())
        keys = self.list_keys()
        if account_key not in keys:
            keys.append(account_key)
            self._write_registry(keys)

    def delete(self, account_key: str) -> None:
        try:
            keyring.delete_password(self.service, account_key)
        except keyring.errors.PasswordDeleteError:
            pass
        self._write_registry([key for key in self.list_keys() if key != account_key])

    def list_keys(self) -> list[str]:
        return self._read_registry()

    def _read_registry(self) -> list[str]:
        payload = keyring.get_password(self.service, KEYRING_REGISTRY_KEY)
        if payload is None:
            return []

        return sorted(REGISTRY_KEYS_ADAPTER.validate_json(payload))

    def _write_registry(self, keys: list[str]) -> None:
        registry_payload = json.dumps(sorted(set(keys)), separators=(",", ":"))
        keyring.set_password(self.service, KEYRING_REGISTRY_KEY, registry_payload)


class FileTokenStore:
    """Store tokens as secure JSON files under the XDG config directory."""

    def __init__(self, token_dir: Path | None = None) -> None:
        self.token_dir: Path = token_dir if token_dir is not None else self._default_token_dir()

    def get(self, account_key: str) -> TokenBundle | None:
        path = self._path(account_key)
        if not path.exists():
            return None
        return TokenBundle.model_validate_json(path.read_text(encoding="utf-8"))

    def put(self, account_key: str, bundle: TokenBundle) -> None:
        self._ensure_token_dir()
        path = self._path(account_key)
        _ = path.write_text(bundle.model_dump_json(), encoding="utf-8")
        os.chmod(path, 0o600)

    def delete(self, account_key: str) -> None:
        self._path(account_key).unlink(missing_ok=True)

    def list_keys(self) -> list[str]:
        if not self.token_dir.exists():
            return []
        return sorted(path.stem for path in self.token_dir.glob("*.json") if path.is_file())

    def _path(self, account_key: str) -> Path:
        return self.token_dir / f"{account_key}.json"

    @staticmethod
    def _default_token_dir() -> Path:
        config_home = os.environ.get("XDG_CONFIG_HOME")
        base_dir = Path(config_home) if config_home is not None else Path.home() / ".config"
        return base_dir / "youtube-mcp" / "tokens"

    def _ensure_token_dir(self) -> None:
        self.token_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.token_dir, 0o700)


def make_token_store(backend: TokenStoreBackend = "auto") -> TokenStore:
    """Create a token store, optionally honoring YOUTUBE_MCP_TOKEN_STORE."""

    env_backend = os.environ.get("YOUTUBE_MCP_TOKEN_STORE")
    if env_backend is not None:
        if env_backend not in {"keyring", "file"}:
            raise ValueError("YOUTUBE_MCP_TOKEN_STORE must be 'keyring' or 'file'")
        backend = cast(TokenStoreBackend, env_backend)

    if backend == "keyring":
        return KeyringTokenStore()
    if backend == "file":
        return FileTokenStore()
    if backend == "auto":
        store = KeyringTokenStore()
        try:
            _ = store.list_keys()
        except keyring.errors.NoKeyringError:
            _ = sys.stderr.write(
                "youtube-mcp: keyring unavailable; falling back to file token store\n"
            )
            return FileTokenStore()
        return store


def migrate(src: TokenStore, dst: TokenStore) -> int:
    """Copy all token bundles from src to dst and return the number copied."""

    copied = 0
    for account_key in src.list_keys():
        bundle = src.get(account_key)
        if bundle is None:
            continue
        dst.put(account_key, bundle)
        copied += 1
    return copied
