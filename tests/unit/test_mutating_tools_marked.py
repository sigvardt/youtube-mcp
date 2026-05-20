"""Cross-module assertions for mutating tool metadata."""

# pyright: reportMissingTypeStubs=false, reportExplicitAny=false, reportAny=false

from __future__ import annotations

from typing import Any, cast

import pytest

from youtube_mcp.server import make_app, mcp

MUTATING_METHOD_VERBS = {
    "bind",
    "create",
    "cuepoint",
    "delete",
    "deliver",
    "insert",
    "markAsSpam",
    "rate",
    "reportAbuse",
    "send",
    "set",
    "setModerationStatus",
    "transition",
    "unban",
    "unset",
    "update",
}


@pytest.mark.asyncio
async def test_mutating_method_verbs_and_tags_stay_in_sync() -> None:
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

        verb = method.rsplit(".", maxsplit=1)[-1]
        expected_mutating = verb in MUTATING_METHOD_VERBS
        actual_mutating = "mutating" in tool.tags
        if actual_mutating != expected_mutating:
            message = (
                f"{tool.name}: method verb {verb!r} expected mutating={expected_mutating} "
                f"but tags={sorted(tool.tags)}"
            )
            failures.append(message)

    assert failures == []
