"""Tool implementations for youtube_mcp."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterable
from typing import cast


def import_tool_modules() -> None:
    """Import all concrete tool modules to trigger FastMCP registration."""

    package_paths = cast(Iterable[str], globals().get("__path__", ()))
    for module_info in pkgutil.iter_modules(package_paths):
        if module_info.ispkg or module_info.name.startswith("_"):
            continue
        _ = importlib.import_module(f"{__name__}.{module_info.name}")
