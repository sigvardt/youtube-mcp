# pyright: reportMissingImports=false
"""Typer CLI entry points for youtube_mcp."""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnusedFunction=false

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, NoReturn, Protocol, cast

import typer

import youtube_mcp.tools as tools_package
from youtube_mcp.auth.accounts import AccountConfigStore, AccountManager, AccountNotFoundError
from youtube_mcp.auth.oauth_flow import refresh_credentials
from youtube_mcp.auth.token_store import TokenStore, make_token_store
from youtube_mcp.auth.wizard import run_wizard
from youtube_mcp.server import AccountResource, configure_account_provider, mcp
from youtube_mcp.server import serve as serve_server
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.tools.channels import youtube_channels_list
from youtube_mcp.types import AccountConfig, TokenBundle, YouTubeScope
from youtube_mcp.utils.quota import QuotaTracker

ApiFilter = Literal["youtube", "analytics", "reporting"]
TransportFilter = Literal["stdio", "http", "sse"]

class RegisteredTool(Protocol):
    """Small protocol for FastMCP tools returned by list_tools()."""

    name: str
    description: str | None
    meta: object


@dataclass(frozen=True)
class Runtime:
    """Concrete runtime dependencies used by CLI commands."""

    manager: AccountManager
    token_store: TokenStore
    quota_tracker: QuotaTracker


@dataclass(frozen=True)
class ToolDisplay:
    """Printable MCP tool details."""

    name: str
    api: str
    method: str
    summary: str


ROOT_HELP = """Operator CLI for youtube-mcp setup and maintenance.

Command tree: serve, auth add, auth list, auth remove, auth refresh, status, doctor,
tools list.
"""

app = typer.Typer(help=ROOT_HELP, no_args_is_help=False)
auth_app = typer.Typer(help="Manage configured YouTube OAuth accounts.", no_args_is_help=True)
tools_app = typer.Typer(help="Inspect registered MCP tools.", no_args_is_help=True)
app.add_typer(auth_app, name="auth")
app.add_typer(tools_app, name="tools")


def _runtime() -> Runtime:
    token_store = make_token_store()
    manager = AccountManager(AccountConfigStore(), token_store)
    return Runtime(manager=manager, token_store=token_store, quota_tracker=QuotaTracker())


def _abort(message: str) -> NoReturn:
    typer.echo(f"youtube-mcp: {message}", err=True)
    raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if not run_wizard(manager=_runtime().manager):
        raise typer.Exit(code=1)


def _scope_summary(scopes: Sequence[YouTubeScope | str]) -> str:
    names: list[str] = []
    for scope in scopes:
        value = scope.value if isinstance(scope, YouTubeScope) else scope
        try:
            names.append(YouTubeScope(value).name.lower())
        except ValueError:
            names.append(value)
    return ",".join(names) if names else "-"


def _scope_values(scopes: Sequence[YouTubeScope | str]) -> list[str]:
    return [scope.value if isinstance(scope, YouTubeScope) else scope for scope in scopes]


def _account_label(account: AccountConfig) -> str:
    handle = account.channel_handle or "-"
    channel_id = account.channel_id or "-"
    scopes = _scope_summary(account.oauth_scopes)
    return f"{account.key}\t{handle}\t{channel_id}\t{scopes}"


def _token_freshness(bundle: TokenBundle | None, now: datetime) -> str:
    if bundle is None:
        return "missing"

    expiry = bundle.expiry
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    expiry_utc = expiry.astimezone(UTC)
    status = "valid" if expiry_utc > now else "expired"
    return f"{status} until {expiry_utc.isoformat()}"


def _configure_tool_framework(runtime: Runtime) -> None:
    configure_framework(
        FrameworkContext(
            account_manager=runtime.manager,
            quota_tracker=runtime.quota_tracker,
        )
    )
    configure_account_provider(lambda: _account_resources(runtime.manager.list()))


def _account_resources(accounts: Sequence[AccountConfig]) -> list[AccountResource]:
    return [
        {
            "key": account.key,
            "channel_handle": account.channel_handle,
            "channel_id": account.channel_id,
            "scopes": _scope_values(account.oauth_scopes),
        }
        for account in accounts
    ]


def _log_startup_context(runtime: Runtime) -> None:
    api_key_status = "configured" if runtime.manager.public_api_key_configured else "not configured"
    message = (
        f"youtube-mcp: account_config={runtime.manager.config_path}; "
        + f"configured_accounts={len(runtime.manager.list())}; "
        + f"public_api_key={api_key_status}"
    )
    typer.echo(
        message,
        err=True,
    )


def _import_tool_modules() -> None:
    tools_package.import_tool_modules()


async def _collect_tools(api: ApiFilter | None) -> list[ToolDisplay]:
    _import_tool_modules()
    registered_tools = cast(Sequence[RegisteredTool], await mcp.list_tools())
    displays: list[ToolDisplay] = []

    for tool in registered_tools:
        meta = cast(Mapping[str, object], tool.meta) if isinstance(tool.meta, dict) else {}
        raw_api = meta.get("api")
        if not isinstance(raw_api, str):
            raw_api = "unknown"
        if api is not None and raw_api != api:
            continue

        raw_method = meta.get("method")
        method = raw_method if isinstance(raw_method, str) else "-"
        summary = tool.description or method
        displays.append(
            ToolDisplay(
                name=tool.name,
                api=raw_api,
                method=method,
                summary=summary,
            )
        )

    return sorted(displays, key=lambda item: item.name)


def _doctor_status(response: Mapping[str, object], channel_id: str | None) -> tuple[str, bool]:
    error = response.get("error")
    if isinstance(error, Mapping):
        reason = error.get("reason")
        reason_text = reason if isinstance(reason, str) else "unknown"
        return f"FAIL: {reason_text}", True

    items = response.get("items")
    if not isinstance(items, list) or not items:
        return "FAIL: no channels returned", True

    first_item = items[0]
    if not isinstance(first_item, Mapping):
        return "FAIL: invalid channel payload", True

    if not channel_id:
        return "FAIL: missing account channel_id", True

    actual_channel_id = first_item.get("id")
    if not isinstance(actual_channel_id, str):
        return "FAIL: missing channel id", True

    if actual_channel_id != channel_id:
        return f"FAIL: channel_id mismatch (expected {channel_id}, got {actual_channel_id})", True

    return "OK", False


@app.command()
def serve(
    transport: Annotated[TransportFilter, typer.Option(help="MCP transport to run.")] = "stdio",
    host: Annotated[str, typer.Option(help="Host for HTTP or SSE transports.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port for HTTP or SSE transports.")] = 8765,
) -> None:
    """Run the MCP server."""

    runtime = _runtime()
    if (
        not runtime.manager.list()
        and not runtime.manager.public_api_key_configured
        and not run_wizard(manager=runtime.manager)
    ):
        raise typer.Exit(code=1)
    _configure_tool_framework(runtime)
    _log_startup_context(runtime)
    serve_server(transport=transport, host=host, port=port)


@auth_app.command("add")
def auth_add(
    key: Annotated[str, typer.Argument(help="Local account key.")],
    client_creds: Annotated[
        Path | None,
        typer.Option(
            "--client-creds",
            help="Path to the Google OAuth client-secret JSON file.",
        ),
    ] = None,
    scopes: Annotated[
        list[str] | None,
        typer.Option(
            "--scopes",
            help="OAuth scope URL/name. Repeat or comma-separate values.",
        ),
    ] = None,
) -> None:
    """Run OAuth for an account and store its token."""

    runtime = _runtime()
    scope_selection = ",".join(scopes) if scopes is not None else ""
    if not run_wizard(
        manager=runtime.manager,
        initial_key=key,
        initial_client_creds_path=client_creds,
        initial_scope_selection=scope_selection,
        offer_add_another=False,
    ):
        raise typer.Exit(code=1)


@auth_app.command("list")
def auth_list() -> None:
    """Print configured accounts."""

    accounts = _runtime().manager.list()
    if not accounts:
        typer.echo("No accounts configured.")
        return

    typer.echo("key\thandle\tchannel_id\tscopes")
    for account in accounts:
        typer.echo(_account_label(account))


@auth_app.command("remove")
def auth_remove(
    key: Annotated[str, typer.Argument(help="Local account key to remove.")],
    yes: Annotated[bool, typer.Option("--yes", help="Confirm removal without prompting.")] = False,
) -> None:
    """Remove an account config and stored token after confirmation."""

    runtime = _runtime()
    try:
        _ = runtime.manager.get(key)
    except AccountNotFoundError as exc:
        _abort(str(exc))

    if not yes and not typer.confirm(
        f"Remove account {key!r} and its stored token?",
        default=False,
        err=True,
    ):
        typer.echo("Cancelled.", err=True)
        raise typer.Exit(code=1)

    runtime.manager.remove(key)
    typer.echo(f"Removed account {key!r}.")


@auth_app.command("refresh")
def auth_refresh(
    key: Annotated[str, typer.Argument(help="Local account key to refresh.")],
) -> None:
    """Force-refresh a stored OAuth token."""

    runtime = _runtime()
    try:
        account = runtime.manager.get(key)
    except AccountNotFoundError as exc:
        _abort(str(exc))

    bundle = runtime.token_store.get(key)
    if bundle is None:
        _abort(f"Account {key!r} does not have a stored token")

    refreshed = refresh_credentials(bundle, account)
    runtime.token_store.put(key, refreshed)
    typer.echo(f"Refreshed {key!r}; token expires {refreshed.expiry.astimezone(UTC).isoformat()}.")


@app.command()
def status() -> None:
    """Print configured-account, token, and quota health."""

    runtime = _runtime()
    accounts = runtime.manager.list()
    typer.echo(f"Configured accounts: {len(accounts)}")
    if not accounts:
        return

    now = datetime.now(UTC)
    typer.echo("key\thandle\tchannel_id\tscopes\ttoken\tquota")
    for account in accounts:
        bundle = runtime.token_store.get(account.key)
        quota_state = runtime.quota_tracker.current(account.key)
        quota = f"{quota_state.units_used_today}/{quota_state.daily_limit}"
        typer.echo(f"{_account_label(account)}\t{_token_freshness(bundle, now)}\t{quota}")


@app.command()
def doctor() -> None:
    """Run an auth smoke probe for every configured account.

    Returns 0 when no accounts are configured.
    """

    runtime = _runtime()
    accounts = runtime.manager.list()
    if not accounts:
        typer.echo("No accounts configured.")
        return

    _configure_tool_framework(runtime)
    failures = 0
    for account in accounts:
        try:
            response = youtube_channels_list(
                account=account.key,
                part="snippet",
                mine=True,
                max_results=1,
            )
        except Exception as exc:  # pragma: no cover - exact Google exceptions vary by transport.
            failures += 1
            typer.echo(f"{account.key}\tFAIL: {exc}")
        else:
            status, is_failure = _doctor_status(response, account.channel_id)
            if is_failure:
                failures += 1
            typer.echo(f"{account.key}\t{status}")

    if failures:
        raise typer.Exit(code=1)


@tools_app.command("list")
def tools_list(
    api: Annotated[
        ApiFilter | None,
        typer.Option("--api", help="Filter by Google API family."),
    ] = None,
) -> None:
    """List registered MCP tools with summaries."""

    tools = asyncio.run(_collect_tools(api))
    if not tools:
        typer.echo("No tools registered.")
        return

    for tool in tools:
        typer.echo(f"{tool.name}\t{tool.api}\t{tool.method}\t{tool.summary}")


def main() -> None:
    """Run the youtube-mcp CLI."""

    app()


if __name__ == "__main__":
    main()
