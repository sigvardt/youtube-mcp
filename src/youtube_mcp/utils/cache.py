"""In-memory TTL cache helpers for stable, non-mutating data."""
# pyright: reportAny=false, reportExplicitAny=false, reportCallInDefaultInitializer=false, reportUnusedCallResult=false

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

P = ParamSpec("P")
T = TypeVar("T")


def _now() -> datetime:
    return datetime.now(UTC)


class TTLCache:
    """Simple in-memory string-keyed cache with time-based expiry."""

    _default_ttl: timedelta
    _entries: dict[str, tuple[Any, datetime]]

    def __init__(self, default_ttl: timedelta = timedelta(hours=24)) -> None:
        self._default_ttl = default_ttl
        self._entries = {}

    def _entry(self, key: str) -> tuple[Any, datetime] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None

        value, expiry_dt = entry
        if expiry_dt <= _now():
            _ = self._entries.pop(key, None)
            return None

        return value, expiry_dt

    def get(self, key: str) -> Any | None:
        entry = self._entry(key)
        if entry is None:
            return None
        return entry[0]

    def set(self, key: str, value: Any, ttl: timedelta | None = None) -> None:
        expiry_ttl = self._default_ttl if ttl is None else ttl
        self._entries[key] = (value, _now() + expiry_ttl)

    def clear(self) -> None:
        self._entries.clear()

    def clear_key(self, key: str) -> None:
        _ = self._entries.pop(key, None)


def cached(
    key_fn: Callable[P, str],
    ttl: timedelta | None = None,
    cache: TTLCache | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Cache stable function results in memory.

    Use this only for lister-style data that is safe to reuse. Do not apply it to
    mutating responses or auth-dependent results unless the cache key includes all
    relevant account context.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        local_cache: TTLCache = cache if cache is not None else TTLCache()

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            key = key_fn(*args, **kwargs)
            cached_value = local_cache.get(key)
            if cached_value is not None:
                return cast(T, cached_value)

            value = func(*args, **kwargs)
            local_cache.set(key, value, ttl)
            return value

        return wrapper

    return decorator


default_cache: TTLCache = TTLCache()
