"""Shared registration framework for YouTube MCP tools.

Tool modules should expose one function per Google API method and decorate each function with
``@youtube_tool(...)``. The wrapped function keeps the original public signature so FastMCP can
derive the MCP input schema from normal Python annotations. Every tool must accept an explicit
``account: str`` parameter and may accept ``ctx: Context | None = None`` for progress or warnings.

The decorator applies the project-wide tool contract in one place:

1. Reject the forbidden video-deletion method at decoration time as a defense-in-depth exclusion.
2. Resolve the explicit account through the injected account manager and refresh/load credentials.
3. Pre-flight the configured quota cost and either raise or warn before the API call.
4. Invoke the mutating-operation guard hook for tools marked ``mutating=True``.
5. Select the appropriate Google API service for YouTube Data, Analytics, or Reporting.
6. Execute the inner tool body through ``retry_with_backoff`` using the configured retry policy.
7. Convert final ``HttpError`` failures into token-free structured MCP error dictionaries.
8. Record quota consumption only after a successful inner call.
9. Register the wrapped callable with the module-level FastMCP ``mcp`` instance at import time.

Runtime dependencies are intentionally injected through ``configure_framework``. This keeps tool
modules importable during tests and lets ``server.make_app()`` wire the real account manager,
quota tracker, mutating guard, and retry policy once those components are available.
"""
# pyright: reportAny=false, reportExplicitAny=false, reportImplicitStringConcatenation=false
# pyright: reportMissingTypeStubs=false

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
from collections.abc import Callable, Coroutine, Mapping, Sequence
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Literal, ParamSpec, Protocol, TypeVar, cast

from googleapiclient.errors import HttpError

from youtube_mcp.auth.accounts import AccountManager
from youtube_mcp.server import mcp
from youtube_mcp.types import RetryPolicy, YouTubeScope
from youtube_mcp.utils.mutating_guard import MutatingGuard as StrictMutatingGuard
from youtube_mcp.utils.quota import QUOTA_COSTS, QuotaExhaustedError
from youtube_mcp.utils.retry import retry_with_backoff

P = ParamSpec("P")
R = TypeVar("R")

ApiName = Literal["youtube", "analytics", "reporting"]
MutatingGuard = Callable[[str], None]

logger = logging.getLogger(__name__)

_HTTP_REASON_FALLBACK = "httpError"
_HTTP_MESSAGE_FALLBACK = "Google API request failed"
_ENFORCE_MUTATING_GUARD_ENV = "YOUTUBE_MCP_ENFORCE_GUARD"
_BLOCKED_VIDEO_DELETION_METHOD = ".".join(("youtube", "videos", "delete"))
_MEMBERSHIP_METHODS = frozenset(
    {
        "youtube.members.list",
        "youtube.membershipsLevels.list",
    }
)
_MEMBERSHIPS_NOT_ENABLED_REASON = "MembershipsNotEnabledError"
_MEMBERSHIPS_NOT_ENABLED_MESSAGE = (
    "Requires channel to have Memberships enabled (Partner Program + monetization). "
    "YouTube returned 403 for this partner-only endpoint."
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)(access_token|refresh_token|client_secret|authorization|bearer)\s*[:=]\s*[^\s,&}]+"),
    re.compile(r"ya29\.[A-Za-z0-9._\-]+"),
)
_BACKGROUND_WARNING_TASKS: set[asyncio.Task[None]] = set()


class AccountManagerProtocol(Protocol):
    """Structural account-manager surface required by the tool framework."""

    def get_credentials(self, key: str) -> object:
        """Return credentials for an account key without exposing token values."""
        ...

    def get_youtube_service(self, key: str) -> object:
        """Return a YouTube Data API service for the account key."""
        ...

    def get_analytics_service(self, key: str) -> object:
        """Return a YouTube Analytics API service for the account key."""
        ...

    def get_reporting_service(self, key: str) -> object:
        """Return a YouTube Reporting API service for the account key."""
        ...


class QuotaTrackerProtocol(Protocol):
    """Structural quota-tracker surface required by the tool framework."""

    enforce: bool

    def would_exceed(self, account_key: str, units: int) -> bool:
        """Return True when adding units would put the account over its daily limit."""
        ...

    def record(self, account_key: str, units: int) -> None:
        """Record successfully consumed quota units for an account."""
        ...


class ToolRegistrationError(Exception):
    """Raised when a tool definition violates the framework registration contract."""


def _mutating_guard(_account: str) -> None:
    """Default mutating-account guard hook; T13 replaces this through framework config."""


@dataclass(frozen=True)
class FrameworkContext:
    """Runtime dependencies injected by server startup or tests."""

    account_manager: AccountManagerProtocol
    quota_tracker: QuotaTrackerProtocol
    mutating_guard: MutatingGuard = _mutating_guard
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)


_ctx: FrameworkContext | None = None


def configure_framework(ctx: FrameworkContext) -> None:
    """Configure runtime dependencies used by all decorated tools."""

    global _ctx
    _ctx = ctx


def _require_context() -> FrameworkContext:
    if _ctx is None:
        raise ToolRegistrationError("youtube_mcp tool framework is not configured")
    return _ctx


def _resolve_cost(method: str, cost: int | None) -> int:
    if cost is not None:
        return cost
    try:
        return QUOTA_COSTS[method]
    except KeyError as exc:
        raise ToolRegistrationError(f"Unknown quota cost for Google API method {method!r}") from exc


def _select_youtube_service(
    account_manager: AccountManagerProtocol,
    api: ApiName,
    account: str,
) -> object:
    if api == "youtube":
        return account_manager.get_youtube_service(account)
    if api == "analytics":
        return account_manager.get_analytics_service(account)
    return account_manager.get_reporting_service(account)


def _sanitize_message(message: str) -> str:
    sanitized = message
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub("[redacted]", sanitized)
    return sanitized


def _first_error_reason(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    payload_mapping = cast(Mapping[str, object], payload)
    error = payload_mapping.get("error")
    if not isinstance(error, dict):
        return None

    error_mapping = cast(Mapping[str, object], error)
    errors = error_mapping.get("errors")
    if not isinstance(errors, list) or not errors:
        return None

    first_error = cast(object, errors[0])
    if not isinstance(first_error, dict):
        return None

    first_error_mapping = cast(Mapping[str, object], first_error)
    reason = first_error_mapping.get("reason")
    return reason if isinstance(reason, str) and reason else None


def _error_message(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    payload_mapping = cast(Mapping[str, object], payload)
    error = payload_mapping.get("error")
    if not isinstance(error, dict):
        return None

    error_mapping = cast(Mapping[str, object], error)
    message = error_mapping.get("message")
    return message if isinstance(message, str) and message else None


def _http_status(error: HttpError) -> int | None:
    response = cast(object, error.resp)
    status = getattr(response, "status", None)
    if isinstance(status, int):
        return status
    if isinstance(status, str) and status.isdigit():
        return int(status)
    return None


def _http_error_to_mcp_error(
    error: HttpError,
    method: str | None = None,
) -> dict[str, dict[str, object]]:
    payload: object | None = None
    try:
        payload = json.loads(error.content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None

    status = _http_status(error) or 0
    response = cast(object, error.resp)
    reason = _first_error_reason(payload) or getattr(response, "reason", None)
    if not isinstance(reason, str) or not reason:
        reason = _HTTP_REASON_FALLBACK

    message = _error_message(payload) or _HTTP_MESSAGE_FALLBACK
    if status == 403 and method in _MEMBERSHIP_METHODS:
        reason = _MEMBERSHIPS_NOT_ENABLED_REASON
        message = _MEMBERSHIPS_NOT_ENABLED_MESSAGE

    return {
        "error": {
            "status": status,
            "reason": _sanitize_message(reason),
            "message": _sanitize_message(message),
        }
    }


def _warn_about_quota(ctx: object | None, message: str) -> None:
    if ctx is None:
        logger.warning(message)
        return

    warning_method = getattr(ctx, "warning", None)
    if not callable(warning_method):
        logger.warning(message)
        return

    warning_result = warning_method(message)
    if inspect.isawaitable(warning_result):
        coroutine = cast(Coroutine[Any, Any, None], warning_result)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coroutine)
        else:
            task = loop.create_task(coroutine)
            _BACKGROUND_WARNING_TASKS.add(task)
            task.add_done_callback(_BACKGROUND_WARNING_TASKS.discard)


def _extract_account(arguments: dict[str, object]) -> str:
    account = arguments.get("account")
    if not isinstance(account, str) or not account:
        raise ToolRegistrationError("Decorated YouTube MCP tools require account: str")
    return account


def _extract_ctx(arguments: dict[str, object]) -> object | None:
    ctx = arguments.get("ctx")
    return ctx


def _normalize_tool_result(result: R) -> R:
    if result is None:
        return cast(R, {})
    if isinstance(result, str) and result == "":
        return cast(R, {})
    return result


def _strict_mutating_guard_enabled() -> bool:
    return os.environ.get(_ENFORCE_MUTATING_GUARD_ENV) == "1"


def youtube_tool(
    *,
    name: str,
    api: ApiName,
    method: str,
    scopes: Sequence[YouTubeScope],
    cost: int | None = None,
    mutating: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R | dict[str, dict[str, object]]]]:
    """Register a Google API-backed function as a FastMCP YouTube tool."""

    if method == _BLOCKED_VIDEO_DELETION_METHOD:
        raise ToolRegistrationError("YouTube video deletion is not exposed by youtube_mcp")

    resolved_cost = _resolve_cost(method, cost)
    tags = {"mutating"} if mutating else None
    meta = {
        "api": api,
        "method": method,
        "scopes": [scope.value for scope in scopes],
        "cost": resolved_cost,
    }

    def decorator(func: Callable[P, R]) -> Callable[P, R | dict[str, dict[str, object]]]:
        signature = inspect.signature(func)
        if "account" not in signature.parameters:
            raise ToolRegistrationError("Decorated YouTube MCP tools require account: str")

        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R | dict[str, dict[str, object]]:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            bound_arguments = cast(dict[str, object], bound.arguments)
            account = _extract_account(bound_arguments)
            ctx = _extract_ctx(bound_arguments)
            framework_ctx = _require_context()

            _ = framework_ctx.account_manager.get_credentials(account)
            if framework_ctx.quota_tracker.would_exceed(account, resolved_cost):
                if framework_ctx.quota_tracker.enforce:
                    raise QuotaExhaustedError(
                        f"Quota cost {resolved_cost} for account {account} would exceed daily limit"
                    )
                _warn_about_quota(
                    ctx,
                    f"WARNING: quota cost {resolved_cost} for account {account} would exceed daily "
                    "limit; continuing because quota enforcement is disabled",
                )

            if mutating:
                if _strict_mutating_guard_enabled():
                    StrictMutatingGuard().assert_allowed(
                        account,
                        cast(AccountManager, framework_ctx.account_manager),
                    )
                framework_ctx.mutating_guard(account)

            _ = _select_youtube_service(framework_ctx.account_manager, api, account)

            @retry_with_backoff(framework_ctx.retry_policy)
            def call_inner() -> R:
                return func(*args, **kwargs)

            try:
                result = call_inner()
            except HttpError as exc:
                return _http_error_to_mcp_error(exc, method)

            framework_ctx.quota_tracker.record(account, resolved_cost)
            return _normalize_tool_result(result)

        cast(Any, wrapped).__signature__ = signature
        _ = mcp.tool(name=name, tags=tags, meta=meta)(wrapped)
        return wrapped

    return decorator


__all__ = [
    "AccountManagerProtocol",
    "FrameworkContext",
    "QuotaExhaustedError",
    "ToolRegistrationError",
    "configure_framework",
    "youtube_tool",
]
