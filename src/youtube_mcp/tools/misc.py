"""YouTube Data API miscellaneous tools."""

# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false

from __future__ import annotations

from typing import Protocol, cast

from fastmcp import Context

from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import YouTubeScope


class _Executable(Protocol):
    def execute(self) -> dict[str, object]:
        """Execute a googleapiclient request."""
        ...


class _AbuseReportsResource(Protocol):
    def insert(self, *, part: str, body: dict[str, object]) -> _Executable:
        """Build an abuseReports.insert request."""
        ...


class _YouTubeService(Protocol):
    def abuseReports(self) -> _AbuseReportsResource:
        """Return the abuseReports resource."""
        ...


class _AccountManager(Protocol):
    def get_youtube_service(self, key: str) -> _YouTubeService:
        """Return a YouTube Data API service."""
        ...


def _youtube_service(account: str) -> _YouTubeService:
    framework_ctx = _require_context()
    account_manager = cast(_AccountManager, cast(object, framework_ctx.account_manager))
    return account_manager.get_youtube_service(account)


@youtube_tool(
    name="youtube_abuseReports_insert",
    api="youtube",
    method="youtube.abuseReports.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_abuseReports_insert(
    account: str,
    part: str,
    abuse_report_body: dict[str, object],
    ctx: Context | None = None,
) -> dict[str, object]:
    """Submit an abuse report."""
    _ = ctx
    service = _youtube_service(account)
    return service.abuseReports().insert(part=part, body=abuse_report_body).execute()
