"""YouTube Data API live chat tools."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnusedParameter=false

from __future__ import annotations

from typing import Any, Literal, cast

from fastmcp import Context

from youtube_mcp.tools._framework import _require_context, youtube_tool
from youtube_mcp.types import YouTubeScope


def _youtube_service(account: str) -> Any:
    framework_ctx = _require_context()
    account_manager = cast(Any, framework_ctx.account_manager)
    cache_key = (account, "youtube")
    cached_services = cast(
        dict[tuple[str, str], Any] | None,
        getattr(account_manager, "_services", None),
    )
    if cached_services is not None and cache_key in cached_services:
        return cached_services[cache_key]

    return account_manager.get_youtube_service(account)


@youtube_tool(
    name="youtube_liveChatMessages_list",
    api="youtube",
    method="youtube.liveChatMessages.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_liveChatMessages_list(
    account: str,
    live_chat_id: str,
    part: str,
    hl: str | None = None,
    max_results: int | None = None,
    page_token: str | None = None,
    profile_image_size: int | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List live chat messages."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveChatMessages()
        .list(
            liveChatId=live_chat_id,
            part=part,
            hl=hl,
            maxResults=max_results,
            pageToken=page_token,
            profileImageSize=profile_image_size,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveChatMessages_insert",
    api="youtube",
    method="youtube.liveChatMessages.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveChatMessages_insert(
    account: str,
    part: str,
    message_body: dict[str, Any],
    ctx: Context | None = None,
) -> dict[str, object]:
    """Post a live chat message."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveChatMessages()
        .insert(
            part=part,
            body=message_body,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveChatMessages_delete",
    api="youtube",
    method="youtube.liveChatMessages.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveChatMessages_delete(
    account: str,
    id: str,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a live chat message."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveChatMessages()
        .delete(
            id=id,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveChatMessages_transition",
    api="youtube",
    method="youtube.liveChatMessages.transition",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveChatMessages_transition(
    account: str,
    id: str,
    status: Literal["statusUnspecified", "closed"],
    ctx: Context | None = None,
) -> dict[str, object]:
    """Transition a live chat message event to a new status."""

    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveChatMessages()
        .transition(
            id=id,
            status=status,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveChatModerators_list",
    api="youtube",
    method="youtube.liveChatModerators.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_liveChatModerators_list(
    account: str,
    live_chat_id: str,
    part: str,
    max_results: int | None = None,
    page_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List live chat moderators."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveChatModerators()
        .list(
            liveChatId=live_chat_id,
            part=part,
            maxResults=max_results,
            pageToken=page_token,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveChatModerators_insert",
    api="youtube",
    method="youtube.liveChatModerators.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveChatModerators_insert(
    account: str,
    part: str,
    moderator_body: dict[str, Any],
    ctx: Context | None = None,
) -> dict[str, object]:
    """Add a live chat moderator."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveChatModerators()
        .insert(
            part=part,
            body=moderator_body,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveChatModerators_delete",
    api="youtube",
    method="youtube.liveChatModerators.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveChatModerators_delete(
    account: str,
    id: str,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Remove a live chat moderator."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveChatModerators()
        .delete(
            id=id,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveChatBans_insert",
    api="youtube",
    method="youtube.liveChatBans.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveChatBans_insert(
    account: str,
    part: str,
    ban_body: dict[str, Any],
    ctx: Context | None = None,
) -> dict[str, object]:
    """Ban a live chat user."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveChatBans()
        .insert(
            part=part,
            body=ban_body,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_liveChatBans_delete",
    api="youtube",
    method="youtube.liveChatBans.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_liveChatBans_delete(
    account: str,
    id: str,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Remove a live chat ban."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.liveChatBans()
        .delete(
            id=id,
        )
        .execute(),
    )
