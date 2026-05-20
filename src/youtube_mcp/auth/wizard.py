"""Interactive first-run setup wizard for YouTube OAuth accounts."""

# pyright: reportMissingTypeStubs=false

from __future__ import annotations

import builtins
from collections.abc import Callable
from pathlib import Path
from typing import Final, Literal, NamedTuple, Protocol

import typer

from youtube_mcp.auth.accounts import AccountConfigStore, AccountManager
from youtube_mcp.auth.oauth_flow import load_client_creds_from_file
from youtube_mcp.auth.token_store import make_token_store
from youtube_mcp.types import AccountConfig, YouTubeScope

InputReader = Callable[[str], str]
SingleAccountStatus = Literal["added", "skipped", "aborted"]

DEFAULT_SCOPES: Final = (
    YouTubeScope.FORCE_SSL,
    YouTubeScope.ANALYTICS_READONLY,
)
ALL_WIZARD_SCOPES: Final = (
    YouTubeScope.FORCE_SSL,
    YouTubeScope.ANALYTICS_READONLY,
    YouTubeScope.ANALYTICS_MONETARY,
    YouTubeScope.CHANNEL_MEMBERSHIPS_CREATOR,
)


class WizardAccountManager(Protocol):
    """Account manager operations needed by the setup wizard."""

    def list(self) -> list[AccountConfig]:
        """Return configured accounts."""
        ...

    def add(
        self,
        key: str,
        client_creds_path: Path,
        scopes: builtins.list[YouTubeScope],
    ) -> AccountConfig:
        """Add or replace an account through the existing OAuth runner."""
        ...


class AccountKeySelection(NamedTuple):
    """Result of account-key prompting."""

    key: str | None
    aborted: bool


def run_wizard(
    *,
    manager: WizardAccountManager | None = None,
    input_func: InputReader = input,
    initial_key: str | None = None,
    initial_client_creds_path: Path | None = None,
    initial_scope_selection: str | None = None,
    offer_add_another: bool = True,
) -> bool:
    """Guide an operator through first-run or add-account OAuth setup."""

    account_manager = manager if manager is not None else _make_account_manager()

    try:
        existing_accounts = account_manager.list()
        if existing_accounts:
            _print_configured_accounts(existing_accounts)
            if initial_key is None and not _confirm("Add another account?", input_func):
                typer.echo("Setup unchanged.", err=True)
                return True
        else:
            typer.echo("No YouTube accounts are configured. Starting first-run setup.", err=True)

        added_any = False
        key_to_use = initial_key
        creds_path_to_use = initial_client_creds_path
        scope_selection_to_use = initial_scope_selection
        while True:
            status = _run_single_account_setup(
                account_manager,
                input_func,
                initial_key=key_to_use,
                initial_client_creds_path=creds_path_to_use,
                initial_scope_selection=scope_selection_to_use,
            )
            if status == "aborted":
                return added_any
            if status == "skipped" and not offer_add_another:
                return False
            if status == "added":
                added_any = True

            if not offer_add_another:
                return added_any

            key_to_use = None
            creds_path_to_use = None
            scope_selection_to_use = None
            if not _confirm("Add another account?", input_func):
                typer.echo("Setup complete.", err=True)
                return True
    except (EOFError, KeyboardInterrupt):
        typer.echo("\nSetup cancelled.", err=True)
        return False


def _make_account_manager() -> AccountManager:
    return AccountManager(AccountConfigStore(), make_token_store())


def _run_single_account_setup(
    manager: WizardAccountManager,
    input_func: InputReader,
    *,
    initial_key: str | None,
    initial_client_creds_path: Path | None,
    initial_scope_selection: str | None,
) -> SingleAccountStatus:
    account_key_selection = _select_account_key(manager, input_func, initial_key)
    if account_key_selection.aborted:
        return "aborted"
    if account_key_selection.key is None:
        return "skipped"

    client_creds_path = _select_client_creds_path(input_func, initial_client_creds_path)
    if client_creds_path is None:
        return "aborted"

    scopes = _select_scopes(input_func, initial_scope_selection)
    typer.echo(
        "Tip: in the Google account picker, select the brand account whose channel you",
        err=True,
    )
    typer.echo("want this key to manage.", err=True)
    typer.echo("Starting OAuth flow. Your browser may open for Google consent.", err=True)
    account = manager.add(account_key_selection.key, client_creds_path, scopes)
    _print_added_account(account)
    typer.echo(
        "The brand account selected during Google consent is now bound to this key.",
        err=True,
    )
    return "added"


def _select_account_key(
    manager: WizardAccountManager,
    input_func: InputReader,
    initial_key: str | None,
) -> AccountKeySelection:
    while True:
        account_key = initial_key.strip() if initial_key is not None else _prompt(
            "Account key (for example 'main' or 'gaming_channel')? ", input_func
        )
        initial_key = None
        if account_key == "":
            typer.echo("Setup cancelled before creating an account.", err=True)
            return AccountKeySelection(key=None, aborted=True)
        if any(character.isspace() for character in account_key):
            typer.echo("Account key cannot contain whitespace.", err=True)
            continue

        existing_account = _find_account(manager.list(), account_key)
        if existing_account is None:
            return AccountKeySelection(key=account_key, aborted=False)

        current_channel = (
            existing_account.channel_handle or existing_account.channel_id or "unknown channel"
        )
        if _confirm(
            f"Replace existing account {account_key!r} (currently {current_channel})?",
            input_func,
        ):
            return AccountKeySelection(key=account_key, aborted=False)
        typer.echo(f"Skipped existing account {account_key!r}; no token was changed.", err=True)
        return AccountKeySelection(key=None, aborted=False)


def _select_client_creds_path(
    input_func: InputReader,
    initial_client_creds_path: Path | None,
) -> Path | None:
    if initial_client_creds_path is None:
        _print_client_creds_instructions()
    path_to_try = initial_client_creds_path
    while True:
        client_creds_path = path_to_try if path_to_try is not None else _prompt_path(input_func)
        path_to_try = None
        if client_creds_path is None:
            typer.echo("Setup aborted before OAuth.", err=True)
            return None
        try:
            _ = load_client_creds_from_file(client_creds_path)
        except OSError as exc:
            typer.echo(f"Client credentials file is not readable: {exc}", err=True)
            typer.echo("Try another path, or press Enter to abort.", err=True)
            continue
        except ValueError as exc:
            typer.echo(f"Invalid client credentials JSON: {exc}", err=True)
            typer.echo("Try another path, or press Enter to abort.", err=True)
            continue
        return client_creds_path


def _select_scopes(
    input_func: InputReader,
    initial_scope_selection: str | None,
) -> list[YouTubeScope]:
    typer.echo("Scopes: press Enter for youtube.force-ssl + analytics readonly.", err=True)
    typer.echo(
        "Optional scope names: monetary, memberships. Use 'all' for every listed scope.",
        err=True,
    )
    scope_selection = initial_scope_selection
    while True:
        raw_selection = scope_selection if scope_selection is not None else _prompt(
            "Scopes (comma-separated, empty for default, 'all' for all supported)? ", input_func
        )
        scope_selection = None
        try:
            scopes = _parse_scopes(raw_selection)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            continue

        typer.echo("Selected scopes:", err=True)
        for scope in scopes:
            typer.echo(f"  - {scope.value}", err=True)
        return scopes


def _parse_scopes(raw_selection: str) -> list[YouTubeScope]:
    normalized_selection = raw_selection.strip().lower()
    if normalized_selection == "":
        return list(DEFAULT_SCOPES)
    if normalized_selection == "all":
        return list(ALL_WIZARD_SCOPES)

    selected_scopes: list[YouTubeScope] = []
    invalid_names: list[str] = []
    aliases = _scope_aliases()
    for raw_name in normalized_selection.split(","):
        scope_name = raw_name.strip()
        if scope_name == "":
            continue
        scope = aliases.get(scope_name)
        if scope is None:
            invalid_names.append(scope_name)
            continue
        if scope not in selected_scopes:
            selected_scopes.append(scope)

    if invalid_names:
        names = ", ".join(invalid_names)
        raise ValueError(f"Unknown scope selection: {names}")
    if not selected_scopes:
        raise ValueError("Choose at least one scope, or press Enter for the default set.")
    return selected_scopes


def _scope_aliases() -> dict[str, YouTubeScope]:
    aliases = {
        "force-ssl": YouTubeScope.FORCE_SSL,
        "force_ssl": YouTubeScope.FORCE_SSL,
        "youtube.force-ssl": YouTubeScope.FORCE_SSL,
        "analytics": YouTubeScope.ANALYTICS_READONLY,
        "analytics-readonly": YouTubeScope.ANALYTICS_READONLY,
        "analytics_readonly": YouTubeScope.ANALYTICS_READONLY,
        "yt-analytics.readonly": YouTubeScope.ANALYTICS_READONLY,
        "monetary": YouTubeScope.ANALYTICS_MONETARY,
        "analytics-monetary": YouTubeScope.ANALYTICS_MONETARY,
        "analytics_monetary": YouTubeScope.ANALYTICS_MONETARY,
        "memberships": YouTubeScope.CHANNEL_MEMBERSHIPS_CREATOR,
        "channel-memberships": YouTubeScope.CHANNEL_MEMBERSHIPS_CREATOR,
        "channel_memberships": YouTubeScope.CHANNEL_MEMBERSHIPS_CREATOR,
    }
    for scope in YouTubeScope:
        aliases[scope.value.lower()] = scope
        aliases[scope.name.lower()] = scope
        aliases[scope.name.lower().replace("_", "-")] = scope
    return aliases


def _prompt_path(input_func: InputReader) -> Path | None:
    raw_path = _prompt("Path to GCP OAuth client credentials JSON? ", input_func)
    if raw_path == "":
        return None
    return Path(raw_path).expanduser()


def _prompt(prompt: str, input_func: InputReader) -> str:
    typer.echo(prompt, nl=False, err=True)
    return input_func("").strip()


def _confirm(prompt: str, input_func: InputReader) -> bool:
    answer = _prompt(f"{prompt} [y/N] ", input_func).lower()
    return answer in {"y", "yes"}


def _print_configured_accounts(accounts: list[AccountConfig]) -> None:
    typer.echo("Configured YouTube accounts:", err=True)
    for account in accounts:
        channel = account.channel_handle or account.channel_id or "unknown channel"
        typer.echo(f"  - {account.key} -> {channel}", err=True)


def _print_client_creds_instructions() -> None:
    typer.echo("Google Cloud OAuth client credentials are required.", err=True)
    typer.echo("Download them from Google Cloud Console > APIs & Services > Credentials.", err=True)
    typer.echo("Choose an OAuth client for a Desktop app, then save the JSON locally.", err=True)


def _print_added_account(account: AccountConfig) -> None:
    channel_bits: list[str] = []
    if account.channel_handle is not None:
        channel_bits.append(account.channel_handle)
    if account.channel_id is not None:
        channel_bits.append(account.channel_id)
    if channel_bits:
        typer.echo(f"Discovered channel: {' / '.join(channel_bits)}", err=True)
    else:
        typer.echo("No channel handle was discovered; account token was still stored.", err=True)
    typer.echo(f"Account {account.key!r} is configured.", err=True)


def _find_account(accounts: list[AccountConfig], key: str) -> AccountConfig | None:
    return next((account for account in accounts if account.key == key), None)
