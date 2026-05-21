"""Multi-account YouTube auth management."""
# pyright: reportAny=false, reportCallInDefaultInitializer=false, reportExplicitAny=false
# pyright: reportMissingTypeStubs=false, reportUnannotatedClassAttribute=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnusedCallResult=false
# pyright: reportUnnecessaryCast=false

from __future__ import annotations

import builtins
import os
import sys
import threading
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Protocol, cast

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from pydantic import TypeAdapter
from typing_extensions import override

from youtube_mcp.auth.oauth_flow import TOKEN_URI, load_client_creds_from_file, run_oauth_flow
from youtube_mcp.auth.token_store import TokenStore
from youtube_mcp.types import AccountConfig, TokenBundle, YouTubeScope

ACCOUNT_CONFIGS_ADAPTER: TypeAdapter[list[AccountConfig]] = TypeAdapter(list[AccountConfig])
PUBLIC_API_KEY_ACCOUNT: Final = "default"
YOUTUBE_MCP_API_KEY_ENV: Final = "YOUTUBE_MCP_API_KEY"
YOUTUBE_API_KEY_ENV: Final = "YOUTUBE_API_KEY"
_PUBLIC_API_KEY_CREDENTIALS = cast(Credentials, object())


def youtube_api_key_from_env() -> str | None:
    for env_name in (YOUTUBE_MCP_API_KEY_ENV, YOUTUBE_API_KEY_ENV):
        raw_value = os.environ.get(env_name)
        if raw_value is None:
            continue
        value = raw_value.strip()
        if value:
            return value
    return None


class OAuthRunner(Protocol):
    """Callable boundary for the installed-app OAuth flow."""

    def __call__(self, account: AccountConfig, scopes: list[str]) -> TokenBundle:
        """Run OAuth for account and return a token bundle."""
        ...


class RefreshableGoogleCredentials(Protocol):
    """Credential attributes AccountManager needs from google-auth."""

    token: str | None
    refresh_token: str | None
    expiry: datetime | None
    scopes: Sequence[str] | None
    expired: bool

    def refresh(self, request: object) -> None:
        """Refresh credentials through google-auth."""
        ...


class CredentialsFactory(Protocol):
    """Typed constructor boundary for google.oauth2.credentials.Credentials."""

    def __call__(
        self,
        *,
        token: str,
        refresh_token: str,
        token_uri: str,
        client_id: str,
        client_secret: str,
        scopes: list[str],
    ) -> RefreshableGoogleCredentials:
        """Build refreshable credentials."""
        ...


class AccountNotFoundError(KeyError):
    """Raised when an account key is not configured."""

    @override
    def __str__(self) -> str:
        if len(self.args) == 1 and isinstance(self.args[0], str):
            return self.args[0]
        return super().__str__()


class AccountConfigStore:
    """Persist YouTube account metadata in the XDG config directory."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else self.default_path()

    @staticmethod
    def default_path() -> Path:
        config_home = os.environ.get("XDG_CONFIG_HOME")
        base_dir = Path(config_home) if config_home is not None else Path.home() / ".config"
        return base_dir / "youtube-mcp" / "accounts.json"

    def load(self) -> list[AccountConfig]:
        if not self.path.exists():
            return []
        return ACCOUNT_CONFIGS_ADAPTER.validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, accounts: list[AccountConfig]) -> None:
        self._ensure_parent_dir()
        _ = self.path.write_bytes(ACCOUNT_CONFIGS_ADAPTER.dump_json(accounts))
        os.chmod(self.path, 0o600)

    def get(self, key: str) -> AccountConfig | None:
        return next((account for account in self.load() if account.key == key), None)

    def upsert(self, account: AccountConfig) -> None:
        accounts = {stored.key: stored for stored in self.load()}
        accounts[account.key] = account
        self.save(sorted(accounts.values(), key=lambda stored: stored.key))

    def delete(self, key: str) -> None:
        accounts = self.load()
        updated_accounts = [account for account in accounts if account.key != key]
        if updated_accounts != accounts or self.path.exists():
            self.save(updated_accounts)

    def _ensure_parent_dir(self) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)


class AccountManager:
    """Coordinate account metadata, OAuth tokens, and Google API services."""

    def __init__(
        self,
        config_store: AccountConfigStore,
        token_store: TokenStore,
        oauth_runner: OAuthRunner | None = None,
        api_key: str | None = None,
    ) -> None:
        self._config_store = config_store
        self._token_store = token_store
        self._oauth_runner = (
            cast(OAuthRunner, run_oauth_flow) if oauth_runner is None else oauth_runner
        )
        self._api_key = self._normalize_api_key(
            youtube_api_key_from_env() if api_key is None else api_key
        )
        self._refresh_locks: dict[str, threading.Lock] = {}
        self._refresh_locks_lock = threading.Lock()
        self._services: dict[tuple[str, str], Resource] = {}
        self._services_lock = threading.Lock()

    @property
    def config_path(self) -> Path:
        return self._config_store.path

    @property
    def public_api_key_configured(self) -> bool:
        return self._api_key is not None

    def add(
        self,
        key: str,
        client_creds_path: Path,
        scopes: list[YouTubeScope],
    ) -> AccountConfig:
        client_creds = load_client_creds_from_file(client_creds_path)
        installed_creds = cast("dict[str, Any]", client_creds["installed"])
        account = AccountConfig(
            key=key,
            client_id=str(installed_creds["client_id"]),
            client_secret=str(installed_creds["client_secret"]),
            oauth_scopes=scopes,
        )
        scope_values = [scope.value for scope in scopes]
        bundle = self._oauth_runner(account, scope_values)
        self._token_store.put(key, bundle)

        credentials = self._credentials_from_bundle(bundle, account)
        youtube_service = self._build_service("youtube", "v3", credentials)
        channel_id, channel_handle = self._discover_channel(key, youtube_service)
        persisted_account = account.model_copy(
            update={"channel_id": channel_id, "channel_handle": channel_handle}
        )
        self._config_store.upsert(persisted_account)
        self._cache_service(key, "youtube", youtube_service)
        return persisted_account

    def list(self) -> list[AccountConfig]:
        return self._config_store.load()

    def get(self, key: str) -> AccountConfig:
        account = self._config_store.get(key)
        if account is None:
            raise AccountNotFoundError(self._account_not_found_message(key))
        return account

    def remove(self, key: str) -> None:
        self._token_store.delete(key)
        self._config_store.delete(key)
        self._clear_cached_services(key)

    def get_credentials(self, key: str) -> Credentials:
        if self._is_public_api_key_account(key):
            return _PUBLIC_API_KEY_CREDENTIALS

        account = self.get(key)
        with self._refresh_lock_for(key):
            bundle = self._token_store.get(key)
            if bundle is None:
                raise AccountNotFoundError(f"Account {key!r} does not have a stored token")

            credentials = self._credentials_from_bundle(bundle, account)
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                updated_bundle = self._token_bundle_from_credentials(credentials, bundle.scopes)
                self._token_store.put(key, updated_bundle)
            return cast(Credentials, cast(object, credentials))

    def get_youtube_service(self, key: str) -> Resource:
        return self._get_service(key, "youtube", "v3")

    def get_analytics_service(self, key: str) -> Resource:
        return self._get_service(key, "youtubeAnalytics", "v2")

    def get_reporting_service(self, key: str) -> Resource:
        return self._get_service(key, "youtubereporting", "v1")

    def _get_service(self, key: str, api_name: str, version: str) -> Resource:
        if self._is_public_api_key_account(key):
            if api_name != "youtube":
                message = (
                    f"Account {key!r} uses an API key for public YouTube Data API calls only; "
                    + f"{api_name} requires a configured OAuth account"
                )
                raise AccountNotFoundError(message)
            return self._get_public_youtube_service(key)

        cache_key = (key, api_name)
        with self._services_lock:
            cached_service = self._services.get(cache_key)
            if cached_service is not None:
                return cached_service

            credentials = self.get_credentials(key)
            service = self._build_service(api_name, version, credentials)
            self._services[cache_key] = service
            return service

    def _build_service(
        self,
        api_name: str,
        version: str,
        credentials: object,
    ) -> Resource:
        return cast(Resource, build(api_name, version, credentials=credentials))

    def _cache_service(self, key: str, api_name: str, service: Resource) -> None:
        with self._services_lock:
            self._services[(key, api_name)] = service

    def _get_public_youtube_service(self, key: str) -> Resource:
        cache_key = (key, "youtube")
        with self._services_lock:
            cached_service = self._services.get(cache_key)
            if cached_service is not None:
                return cached_service

            api_key = self._api_key
            if api_key is None:
                raise AccountNotFoundError(self._account_not_found_message(key))

            service = cast(Resource, build("youtube", "v3", developerKey=api_key))
            self._services[cache_key] = service
            return service

    def _is_public_api_key_account(self, key: str) -> bool:
        return (
            key == PUBLIC_API_KEY_ACCOUNT
            and self._api_key is not None
            and self._config_store.get(key) is None
        )

    def _account_not_found_message(self, key: str) -> str:
        configured_keys = [account.key for account in self._config_store.load()]
        configured = ", ".join(repr(configured_key) for configured_key in configured_keys)
        if not configured:
            configured = "none"

        message = (
            f"Account {key!r} is not configured. "
            + f"Configured OAuth account keys: {configured}. "
            + "Use the exact key from youtube://accounts or `youtube-mcp auth list`. "
            + f"The reserved key {PUBLIC_API_KEY_ACCOUNT!r} is only for public YouTube "
            + f"Data API calls when {YOUTUBE_MCP_API_KEY_ENV} is set"
        )
        if key == PUBLIC_API_KEY_ACCOUNT:
            return message + "; it is not a default OAuth account."
        return message + "; it is not an OAuth fallback."

    def _clear_cached_services(self, key: str) -> None:
        with self._services_lock:
            self._services = {
                cache_key: service
                for cache_key, service in self._services.items()
                if cache_key[0] != key
            }

    def _refresh_lock_for(self, key: str) -> threading.Lock:
        with self._refresh_locks_lock:
            lock = self._refresh_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._refresh_locks[key] = lock
            return lock

    @staticmethod
    def _normalize_api_key(api_key: str | None) -> str | None:
        if api_key is None:
            return None
        normalized = api_key.strip()
        return normalized or None

    def _discover_channel(
        self,
        key: str,
        youtube_service: Resource,
    ) -> tuple[str | None, str | None]:
        response = cast(
            "dict[str, Any]",
            cast("Any", youtube_service).channels().list(part="snippet,id", mine=True).execute(),
        )
        items = response.get("items")
        if not isinstance(items, list) or not items:
            _ = sys.stderr.write(f"Warning: no YouTube channel discovered for account {key!r}\n")
            return None, None

        first_item = cast("list[object]", items)[0]
        if not isinstance(first_item, dict):
            _ = sys.stderr.write(
                f"Warning: malformed YouTube channel response for account {key!r}\n"
            )
            return None, None

        first_item_dict = cast("dict[str, object]", first_item)
        channel_id = first_item_dict.get("id")
        snippet = first_item_dict.get("snippet")
        raw_handle: object | None = None
        if isinstance(snippet, dict):
            snippet_dict = cast("dict[str, object]", snippet)
            raw_handle = snippet_dict.get("customUrl") or snippet_dict.get("handle")

        return self._string_or_none(channel_id), self._normalize_handle(raw_handle)

    @staticmethod
    def _credentials_from_bundle(
        bundle: TokenBundle,
        account: AccountConfig,
    ) -> RefreshableGoogleCredentials:
        credentials_factory = cast(CredentialsFactory, cast(object, Credentials))
        return credentials_factory(
            token=bundle.access_token,
            refresh_token=bundle.refresh_token,
            token_uri=TOKEN_URI,
            client_id=account.client_id,
            client_secret=account.client_secret,
            scopes=bundle.scopes,
        )

    @staticmethod
    def _token_bundle_from_credentials(
        credentials: RefreshableGoogleCredentials,
        fallback_scopes: builtins.list[str],
    ) -> TokenBundle:
        token = credentials.token
        refresh_token = credentials.refresh_token
        expiry = credentials.expiry
        if token is None or refresh_token is None or expiry is None:
            raise ValueError("OAuth credentials are missing token fields")

        credential_scopes = credentials.scopes

        return TokenBundle(
            access_token=token,
            refresh_token=refresh_token,
            expiry=expiry,
            scopes=[*(credential_scopes or fallback_scopes)],
        )

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _normalize_handle(value: object | None) -> str | None:
        if not isinstance(value, str) or value == "":
            return None
        return value if value.startswith("@") else f"@{value}"
