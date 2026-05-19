"""Tests for youtube_mcp.utils.cache."""
# pyright: reportAny=false, reportMissingImports=false, reportMissingParameterType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUntypedFunctionDecorator=false

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import Mock

import pytest

import youtube_mcp.utils.cache as cache_module
from youtube_mcp.utils.cache import TTLCache, cached


def test_get_miss_returns_none() -> None:
    """Empty caches should return None for unknown keys."""

    cache = TTLCache()

    assert cache.get("missing") is None


def test_set_then_get_hit() -> None:
    """Setting a key should make it immediately retrievable."""

    cache = TTLCache()
    cache.set("stable", {"value": 1})

    assert cache.get("stable") == {"value": 1}


def test_expires_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Entries should disappear after their TTL elapses."""

    current_time = [datetime(2026, 5, 19, 12, 0, tzinfo=UTC)]
    monkeypatch.setattr(cache_module, "_now", lambda: current_time[0])

    cache = TTLCache(default_ttl=timedelta(minutes=5))
    cache.set("expiring", "value")

    assert cache.get("expiring") == "value"

    current_time[0] = current_time[0] + timedelta(minutes=6)

    assert cache.get("expiring") is None


def test_clear_key_invalidates_one() -> None:
    """Clearing one key should leave other keys intact."""

    cache = TTLCache()
    cache.set("keep", "value-keep")
    cache.set("drop", "value-drop")

    cache.clear_key("drop")

    assert cache.get("drop") is None
    assert cache.get("keep") == "value-keep"


def test_clear_empties_all() -> None:
    """Clearing the cache should remove every stored entry."""

    cache = TTLCache()
    cache.set("first", 1)
    cache.set("second", 2)

    cache.clear()

    assert cache.get("first") is None
    assert cache.get("second") is None


def test_cached_decorator_memoizes() -> None:
    """Decorated functions should only run once per cache key within TTL."""

    call_counter = {"count": 0}

    def side_effect(value: str) -> str:
        call_counter["count"] += 1
        return f"result-{call_counter['count']}-{value}"

    wrapped = Mock(side_effect=side_effect)

    @cached(lambda value: value)
    def fetch(value: str) -> str:
        return cast(str, wrapped(value))

    assert fetch("alpha") == "result-1-alpha"
    assert fetch("alpha") == "result-1-alpha"
    assert wrapped.call_count == 1
    assert call_counter["count"] == 1


def test_cached_decorator_refetches_after_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expired decorator entries should trigger a fresh function call."""

    current_time = [datetime(2026, 5, 19, 12, 0, tzinfo=UTC)]
    monkeypatch.setattr(cache_module, "_now", lambda: current_time[0])

    call_counter = {"count": 0}

    def side_effect(value: str) -> str:
        call_counter["count"] += 1
        return f"result-{call_counter['count']}-{value}"

    wrapped = Mock(side_effect=side_effect)

    @cached(lambda value: value, ttl=timedelta(minutes=5))
    def fetch(value: str) -> str:
        return cast(str, wrapped(value))

    assert fetch("alpha") == "result-1-alpha"

    current_time[0] = current_time[0] + timedelta(minutes=6)

    assert fetch("alpha") == "result-2-alpha"
    assert wrapped.call_count == 2
    assert call_counter["count"] == 2


def test_cached_decorator_account_key_in_key() -> None:
    """Callers should be able to include account identity in the cache key."""

    call_counter = {"count": 0}

    def side_effect(account_key: str, resource: str) -> str:
        call_counter["count"] += 1
        return f"result-{call_counter['count']}-{account_key}-{resource}"

    wrapped = Mock(side_effect=side_effect)

    @cached(lambda account_key, resource: f"{account_key}:{resource}")
    def fetch(account_key: str, resource: str) -> str:
        return cast(str, wrapped(account_key, resource))

    assert fetch("account-a", "videos") == "result-1-account-a-videos"
    assert fetch("account-b", "videos") == "result-2-account-b-videos"
    assert wrapped.call_count == 2
    assert call_counter["count"] == 2
