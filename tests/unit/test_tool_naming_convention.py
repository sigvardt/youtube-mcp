"""Cross-module assertions for MCP tool naming."""

# pyright: reportMissingTypeStubs=false, reportExplicitAny=false, reportAny=false

from __future__ import annotations

import re
from typing import Any, cast

import pytest

from youtube_mcp.server import make_app, mcp

TOOL_NAME_RE = re.compile(r"^youtube_[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z][A-Za-z0-9]*)+$")


@pytest.mark.asyncio
async def test_registered_tool_names_match_google_resource_verb_shape() -> None:
    _ = make_app()
    tools = await mcp.list_tools()

    failures: list[str] = []
    for tool in tools:
        app_tool = cast(Any, await mcp.get_tool(tool.name))
        if not str(app_tool.fn.__module__).startswith("youtube_mcp.tools."):
            continue

        meta = cast(dict[str, object], tool.meta or {})
        method = meta.get("method")
        if not isinstance(method, str):
            failures.append(f"{tool.name}: missing method metadata")
            continue

        name_parts = tool.name.split("_")
        if not TOOL_NAME_RE.fullmatch(tool.name):
            failures.append(f"{tool.name}: invalid name shape")
        if len(name_parts) < 3:
            failures.append(f"{tool.name}: missing resource or verb segment for {method}")
        if meta.get("api") not in {"youtube", "analytics", "reporting"}:
            failures.append(f"{tool.name}: invalid api metadata")

    assert failures == []
