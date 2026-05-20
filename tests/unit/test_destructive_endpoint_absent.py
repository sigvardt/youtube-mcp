"""Cross-module guard against exposing the blocked video deletion endpoint."""

# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from pathlib import Path

import pytest

from youtube_mcp.server import make_app, mcp

_FORBIDDEN = "_".join(("youtube", "videos", "delete"))
_FORBIDDEN_DOTTED = ".".join(("videos", "delete"))

ROOT = Path(__file__).resolve().parents[2]
SEARCH_ROOTS = (ROOT / "src", ROOT / "tests")
TEXT_SUFFIXES = {".py", ".pyi", ".toml", ".yaml", ".yml", ".md", ".json"}


def _source_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        for path in root.rglob("*"):
            if "__pycache__" in path.parts or not path.is_file():
                continue
            if path.suffix in TEXT_SUFFIXES:
                files.append(path)
    return files


def test_no_blocked_video_deletion_patterns_in_source_tree() -> None:
    blocked_patterns = (
        _FORBIDDEN_DOTTED,
        "_".join(("videos", "delete")),
        "videos" + "()" + _FORBIDDEN_DOTTED,
    )

    offenders: list[str] = []
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        for pattern in blocked_patterns:
            if pattern in text:
                offenders.append(f"{path.relative_to(ROOT)} contains {pattern!r}")

    assert offenders == []


@pytest.mark.asyncio
async def test_blocked_video_deletion_tool_not_registered() -> None:
    _ = make_app()
    blocked_name = _FORBIDDEN
    blocked_method = _FORBIDDEN_DOTTED

    tools = await mcp.list_tools()

    assert blocked_name not in {tool.name for tool in tools}
    assert blocked_method not in {
        tool.meta.get("method") for tool in tools if tool.meta is not None
    }
