"""Tests for the FastMCP server bootstrap."""
# pyright: reportMissingTypeStubs=false

from __future__ import annotations

import json
import selectors
import signal as std_signal
import subprocess
from pathlib import Path
from typing import cast

import pytest

from youtube_mcp import __version__, server


def test_imports_clean() -> None:
    from youtube_mcp.server import make_app, mcp, serve

    assert mcp is server.mcp
    assert callable(make_app)
    assert callable(serve)


def test_make_app_returns_mcp_instance() -> None:
    assert server.make_app() is server.mcp


def test_make_app_silent_on_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    _ = server.make_app()

    captured = capsys.readouterr()

    assert captured.out == ""


def test_accounts_resource_returns_empty_list_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def empty_account_provider() -> list[server.AccountResource]:
        return []

    monkeypatch.setattr(server, "_account_provider", empty_account_provider)

    # FastMCP's resource registry is internal/async in 3.3.1; the decorator preserves the
    # handler, so call it directly to verify the resource payload contract.
    assert server.accounts_resource() == []


def test_configure_account_provider_updates_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    def empty_account_provider() -> list[server.AccountResource]:
        return []

    monkeypatch.setattr(server, "_account_provider", empty_account_provider)

    server.configure_account_provider(
        lambda: [
            {
                "key": "primary",
                "channel_handle": "@example",
                "channel_id": "UC123",
                "scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
            }
        ]
    )

    assert server.accounts_resource()[0]["key"] == "primary"
    assert server.status_resource()["configured_accounts"] == 1


def test_quota_resource_returns_json_serializable_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    quota = server.quota_resource("primary")

    assert quota["account_key"] == "primary"
    assert quota["units_used_today"] == 0
    assert isinstance(quota["last_reset"], str)


def test_status_resource_includes_version_and_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server,
        "_account_provider",
        lambda: [
            {
                "key": "primary",
                "channel_handle": "@example",
                "channel_id": None,
                "scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
            }
        ],
    )
    monkeypatch.setattr(server, "_current_transport", "stdio")

    status = server.status_resource()

    assert status == {
        "configured_accounts": 1,
        "transport": "stdio",
        "version": __version__,
    }


def test_serve_sets_transport_and_passes_http_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    run_calls: list[dict[str, object]] = []
    signal_calls: list[object] = []

    def fake_signal(signum: object, handler: object) -> None:
        signal_calls.extend([signum, handler])

    def fake_run(**kwargs: object) -> None:
        run_calls.append(kwargs)

    monkeypatch.setattr("youtube_mcp.server.signal.signal", fake_signal)
    monkeypatch.setattr(server.mcp, "run", fake_run)

    server.serve("http", host="127.0.0.1", port=8766)

    assert signal_calls[0] == std_signal.SIGTERM
    assert server.status_resource()["transport"] == "http"
    assert run_calls == [
        {"transport": "http", "host": "127.0.0.1", "port": 8766, "show_banner": False}
    ]


def test_stdio_handshake_smoke() -> None:
    request = (
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0.0"},
                },
            }
        )
        + "\n"
    )
    process = subprocess.Popen(
        ["uv", "run", "python", "-c", "from youtube_mcp.server import serve; serve('stdio')"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        assert process.stdin is not None
        assert process.stdout is not None

        _ = process.stdin.write(request)
        process.stdin.flush()

        selector = selectors.DefaultSelector()
        try:
            _ = selector.register(process.stdout, selectors.EVENT_READ)
            events = selector.select(timeout=10)
        finally:
            selector.close()

        if not events:
            process.kill()
            _, stderr = process.communicate(timeout=5)
            pytest.fail(f"Timed out waiting for stdio initialize response. stderr={stderr}")

        line = process.stdout.readline()
        parsed_response = cast(object, json.loads(line))
        assert isinstance(parsed_response, dict)
        response = cast(dict[str, object], parsed_response)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                _ = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _ = process.wait(timeout=5)
