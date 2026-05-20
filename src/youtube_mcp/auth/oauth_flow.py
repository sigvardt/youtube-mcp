# pyright: reportMissingTypeStubs=false, reportExplicitAny=false
# pyright: reportAny=false, reportUnknownMemberType=false
"""OAuth installed-app flow helpers."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Protocol, cast

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import (  # type: ignore[import-untyped]  # oauthlib lacks stubs
    InstalledAppFlow,
)

from youtube_mcp.types import AccountConfig, TokenBundle

AUTH_URI: Final = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI: Final = "https://oauth2.googleapis.com/token"
REQUIRED_CLIENT_CREDS_FIELDS: Final = frozenset(
    {"client_id", "client_secret", "auth_uri", "token_uri", "redirect_uris"}
)


class TokenInvalidError(Exception):
    """Raised when an OAuth token bundle cannot be used or refreshed."""


class OAuthCredentials(Protocol):
    """Credential attributes consumed by TokenBundle conversion."""

    token: str | None
    refresh_token: str | None
    expiry: datetime | None
    scopes: Sequence[str] | None


class RefreshableOAuthCredentials(OAuthCredentials, Protocol):
    """Credential object that can refresh itself through google-auth."""

    def refresh(self, request: object) -> None:
        """Refresh credentials using a google-auth transport request."""
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
    ) -> RefreshableOAuthCredentials:
        """Build refreshable OAuth credentials."""
        ...


GOOGLE_CREDENTIALS_FACTORY: Final = cast(CredentialsFactory, cast(object, Credentials))


def load_client_creds_from_file(path: Path) -> dict[str, Any]:
    """Load a GCP OAuth client-secret JSON file for InstalledAppFlow."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("malformed client creds: invalid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("malformed client creds: expected top-level object")

    payload_dict = cast("dict[str, Any]", payload)
    wrapper_name: str
    if "installed" in payload_dict:
        wrapper_name = "installed"
    elif "web" in payload_dict:
        wrapper_name = "web"
    else:
        raise ValueError("malformed client creds: missing installed or web block")

    client_creds = payload_dict[wrapper_name]
    if not isinstance(client_creds, dict):
        raise ValueError(f"malformed client creds: {wrapper_name} block must be an object")

    client_creds_dict = cast("dict[str, Any]", client_creds)
    missing_fields = sorted(REQUIRED_CLIENT_CREDS_FIELDS - client_creds_dict.keys())
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"malformed client creds: missing required fields: {missing}")

    return {"installed": dict(client_creds_dict)}


def run_oauth_flow(
    account: AccountConfig,
    scopes: list[str],
    port: int = 0,
    open_browser: bool = True,
) -> TokenBundle:
    """Run Google's installed-app loopback OAuth flow for an account."""

    client_config: dict[str, object] = {
        "installed": {
            "client_id": account.client_id,
            "client_secret": account.client_secret,
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=scopes)
    authorization_url = cast("tuple[str, object]", flow.authorization_url())[0]
    _ = sys.stderr.write(f"If browser didn't open, visit: {authorization_url}\n")
    raw_creds = flow.run_local_server(
        port=port,
        open_browser=open_browser,
        prompt="select_account consent",
        access_type="offline",
    )
    creds = cast(OAuthCredentials, cast(object, raw_creds))

    if creds.refresh_token is None:
        raise TokenInvalidError(
            "OAuth flow did not return a refresh token - re-run with prompt=consent"
        )

    return _token_bundle_from_credentials(creds, scopes)


def refresh_credentials(bundle: TokenBundle, account: AccountConfig) -> TokenBundle:
    """Refresh a stored OAuth token bundle."""

    google_creds = GOOGLE_CREDENTIALS_FACTORY(
        token=bundle.access_token,
        refresh_token=bundle.refresh_token,
        token_uri=TOKEN_URI,
        client_id=account.client_id,
        client_secret=account.client_secret,
        scopes=bundle.scopes,
    )
    creds = cast(OAuthCredentials, google_creds)

    try:
        google_creds.refresh(Request())
    except RefreshError as exc:
        if "invalid_grant" in str(exc):
            raise TokenInvalidError(
                f"OAuth refresh failed with invalid_grant for account {account.key!r}; re-run OAuth"
            ) from exc
        raise

    if creds.refresh_token is None:
        raise TokenInvalidError(
            f"OAuth refresh did not return a refresh token for account {account.key!r}"
        )

    return _token_bundle_from_credentials(creds, bundle.scopes)


def _token_bundle_from_credentials(
    creds: OAuthCredentials,
    fallback_scopes: list[str],
) -> TokenBundle:
    access_token = creds.token
    refresh_token = creds.refresh_token
    expiry = creds.expiry
    if access_token is None or refresh_token is None or expiry is None:
        raise TokenInvalidError("OAuth credentials are missing token fields")

    return TokenBundle(
        access_token=access_token,
        refresh_token=refresh_token,
        expiry=expiry,
        scopes=list(creds.scopes or fallback_scopes),
    )
