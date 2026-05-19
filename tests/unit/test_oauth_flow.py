# pyright: reportMissingTypeStubs=false, reportAny=false
# pyright: reportUnusedCallResult=false, reportUnusedParameter=false
"""Tests for youtube_mcp.auth.oauth_flow."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from youtube_mcp.auth.oauth_flow import (
    AUTH_URI,
    TOKEN_URI,
    TokenInvalidError,
    load_client_creds_from_file,
    refresh_credentials,
    run_oauth_flow,
)
from youtube_mcp.types import AccountConfig, TokenBundle, YouTubeScope


def make_account() -> AccountConfig:
    return AccountConfig(
        key="jsigvardt",
        client_id="client-id",
        client_secret="client-secret",
        oauth_scopes=[YouTubeScope.READONLY],
        created_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )


def make_client_creds(client_type: str) -> dict[str, dict[str, object]]:
    return {
        client_type: {
            "client_id": "x",
            "client_secret": "y",
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": ["http://localhost"],
        }
    }


def make_bundle() -> TokenBundle:
    return TokenBundle(
        access_token="old-access",
        refresh_token="old-refresh",
        expiry=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
        scopes=["scope-a"],
    )


def test_load_client_creds_from_file_parses_installed_block(tmp_path: Path) -> None:
    path = tmp_path / "client_secret_installed.json"
    payload = make_client_creds("installed")
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_client_creds_from_file(path) == payload


def test_load_client_creds_from_file_handles_web_block(tmp_path: Path) -> None:
    path = tmp_path / "client_secret_web.json"
    payload = make_client_creds("web")
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_client_creds_from_file(path) == {"installed": payload["web"]}


def test_load_client_creds_from_file_raises_on_malformed(tmp_path: Path) -> None:
    path = tmp_path / "client_secret_bad.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed client creds"):
        _ = load_client_creds_from_file(path)


def test_load_client_creds_from_file_raises_on_missing_required_fields(tmp_path: Path) -> None:
    path = tmp_path / "client_secret_missing.json"
    path.write_text(json.dumps({"installed": {"client_id": "x"}}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required fields"):
        _ = load_client_creds_from_file(path)


def test_run_oauth_flow_returns_token_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    account = make_account()
    scopes = ["scope-a"]
    expiry = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    fake_creds = MagicMock(
        token="access-token",
        refresh_token="refresh-token",
        expiry=expiry,
        scopes=["scope-a", "scope-b"],
    )
    flow = MagicMock()
    flow.authorization_url.return_value = ("https://accounts.example/auth", "state")
    flow.run_local_server.return_value = fake_creds
    from_client_config = MagicMock(return_value=flow)
    monkeypatch.setattr(InstalledAppFlow, "from_client_config", from_client_config)

    bundle = run_oauth_flow(account, scopes, port=8765, open_browser=False)

    from_client_config.assert_called_once_with(
        {
            "installed": {
                "client_id": "client-id",
                "client_secret": "client-secret",
                "auth_uri": AUTH_URI,
                "token_uri": TOKEN_URI,
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=scopes,
    )
    flow.run_local_server.assert_called_once_with(
        port=8765,
        open_browser=False,
        prompt="consent",
        access_type="offline",
    )
    assert bundle == TokenBundle(
        access_token="access-token",
        refresh_token="refresh-token",
        expiry=expiry,
        scopes=["scope-a", "scope-b"],
    )


def test_run_oauth_flow_raises_when_no_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_creds = MagicMock(
        token="access-token",
        refresh_token=None,
        expiry=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
        scopes=["scope-a"],
    )
    flow = MagicMock()
    flow.authorization_url.return_value = ("https://accounts.example/auth", "state")
    flow.run_local_server.return_value = fake_creds
    monkeypatch.setattr(InstalledAppFlow, "from_client_config", MagicMock(return_value=flow))

    with pytest.raises(TokenInvalidError, match="did not return a refresh token"):
        _ = run_oauth_flow(make_account(), ["scope-a"])


def test_run_oauth_flow_writes_manual_url_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_creds = MagicMock(
        token="access-token",
        refresh_token="refresh-token",
        expiry=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
        scopes=None,
    )
    flow = MagicMock()
    flow.authorization_url.return_value = ("https://accounts.example/auth", "state")
    flow.run_local_server.return_value = fake_creds
    monkeypatch.setattr(InstalledAppFlow, "from_client_config", MagicMock(return_value=flow))

    _ = run_oauth_flow(make_account(), ["scope-a"])

    captured = capsys.readouterr()
    assert "If browser didn't open, visit: https://accounts.example/auth" in captured.err


def test_refresh_credentials_translates_invalid_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    original_error = RefreshError("invalid_grant: token revoked")

    def raise_invalid_grant(self: Credentials, request: object) -> None:
        raise original_error

    monkeypatch.setattr(Credentials, "refresh", raise_invalid_grant)

    with pytest.raises(TokenInvalidError) as exc_info:
        _ = refresh_credentials(make_bundle(), make_account())

    assert exc_info.value.__cause__ is original_error


def test_refresh_credentials_returns_new_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    refreshed_expiry = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)

    def refresh_in_place(self: Credentials, request: object) -> None:
        self.token = "new-access"
        object.__setattr__(self, "_refresh_token", "new-refresh")
        self.expiry = refreshed_expiry
        object.__setattr__(self, "_scopes", ["scope-a", "scope-b"])

    monkeypatch.setattr(Credentials, "refresh", refresh_in_place)

    assert refresh_credentials(make_bundle(), make_account()) == TokenBundle(
        access_token="new-access",
        refresh_token="new-refresh",
        expiry=refreshed_expiry,
        scopes=["scope-a", "scope-b"],
    )
