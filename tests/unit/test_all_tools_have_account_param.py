"""Cross-module assertion that every tool is account-scoped."""

# pyright: reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportExplicitAny=false
# pyright: reportAny=false, reportUnknownMemberType=false

from __future__ import annotations

import inspect
from typing import Any, cast

import pytest

from youtube_mcp.server import make_app, mcp


@pytest.mark.asyncio
async def test_every_registered_tool_takes_account_first() -> None:
    _ = make_app()
    tools = await mcp.list_tools()

    failures: list[str] = []
    for tool in tools:
        app_tool = cast(Any, await mcp.get_tool(tool.name))
        if not str(app_tool.fn.__module__).startswith("youtube_mcp.tools."):
            continue

        parameters = list(inspect.signature(app_tool.fn).parameters.values())
        if not parameters:
            failures.append(f"{tool.name}: no parameters")
            continue

        first = parameters[0]
        tool_parameters = cast(dict[str, object], tool.parameters)
        properties = cast(dict[str, object], tool_parameters.get("properties", {}))
        account_schema = properties.get("account")
        if first.name != "account":
            failures.append(f"{tool.name}: first parameter is {first.name!r}")
        if first.annotation not in {str, "str"}:
            failures.append(f"{tool.name}: account annotation is {first.annotation!r}")
        if account_schema != {"type": "string"}:
            failures.append(f"{tool.name}: account schema is {account_schema!r}")

    assert failures == []
