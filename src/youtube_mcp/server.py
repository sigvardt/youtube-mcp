"""FastMCP server bootstrap for youtube_mcp."""

from __future__ import annotations

import logging
import signal
import sys
from collections.abc import Callable
from typing import Literal, TypedDict

from fastmcp import FastMCP

from . import __version__
from .utils.quota import QuotaTracker

Transport = Literal["stdio", "http", "sse"]


class AccountResource(TypedDict):
    """Token-free account metadata exposed through the accounts resource."""

    key: str
    channel_handle: str | None
    channel_id: str | None
    scopes: list[str]


AccountProvider = Callable[[], list[AccountResource]]

logger = logging.getLogger("youtube_mcp.server")

mcp: FastMCP = FastMCP(name="youtube-mcp", version=__version__)

# TODO(T6): wire to AccountManager once available.
_account_provider: AccountProvider = lambda: []  # noqa: E731
_current_transport: str | None = None


def _configure_logging() -> None:
    """Configure this module's logger to write to stderr only."""

    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)


@mcp.resource("youtube://accounts")
def accounts_resource() -> list[AccountResource]:
    """Return configured YouTube accounts without token values."""

    return _account_provider()


@mcp.resource("youtube://quota/{account_key}")
def quota_resource(account_key: str) -> dict[str, object]:
    """Return the current quota state for an account."""

    return QuotaTracker().current(account_key).model_dump(mode="json")


@mcp.resource("youtube://status")
def status_resource() -> dict[str, object]:
    """Return lightweight server status."""

    return {
        "configured_accounts": len(_account_provider()),
        "transport": _current_transport or "unstarted",
        "version": __version__,
    }


def make_app() -> FastMCP:
    """Return the configured FastMCP app after lazy registration imports."""

    # Future tool module imports: youtube_mcp.tools.activities, youtube_mcp.tools.captions,
    # youtube_mcp.tools.channels, youtube_mcp.tools.comments, youtube_mcp.tools.playlists,
    # youtube_mcp.tools.search, youtube_mcp.tools.videos, youtube_mcp.tools.analytics.
    return mcp


def serve(
    transport: Transport = "stdio",
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Run the FastMCP server over the requested transport."""

    global _current_transport

    _ = signal.signal(signal.SIGTERM, lambda _signum, _frame: sys.exit(0))
    _configure_logging()
    app = make_app()
    _current_transport = transport

    if transport == "stdio":
        app.run(transport="stdio", show_banner=False)
        return

    app.run(transport=transport, host=host, port=port, show_banner=False)
