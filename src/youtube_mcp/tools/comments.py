"""YouTube Data API comments tools."""

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
    name="youtube_comments_list",
    api="youtube",
    method="youtube.comments.list",
    scopes=[YouTubeScope.READONLY],
    cost=1,
)
def youtube_comments_list(
    account: str,
    part: str,
    id: str | None = None,
    parent_id: str | None = None,
    max_results: int = 20,
    page_token: str | None = None,
    text_format: str | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """List comments or replies."""
    service = _youtube_service(account)
    request_kwargs: dict[str, object] = {"part": part}
    if id is not None:
        request_kwargs["id"] = id
    else:
        request_kwargs["parentId"] = parent_id
        request_kwargs["maxResults"] = max_results
        request_kwargs["pageToken"] = page_token
    request_kwargs["textFormat"] = text_format
    return cast(dict[str, object], service.comments().list(**request_kwargs).execute())


@youtube_tool(
    name="youtube_comments_insert",
    api="youtube",
    method="youtube.comments.insert",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_comments_insert(
    account: str,
    part: str,
    comment_body: dict[str, Any],
    ctx: Context | None = None,
) -> dict[str, object]:
    """Create a reply comment."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.comments()
        .insert(
            part=part,
            body=comment_body,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_comments_update",
    api="youtube",
    method="youtube.comments.update",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_comments_update(
    account: str,
    part: str,
    comment_body: dict[str, Any],
    ctx: Context | None = None,
) -> dict[str, object]:
    """Update a comment."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.comments()
        .update(
            part=part,
            body=comment_body,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_comments_setModerationStatus",
    api="youtube",
    method="youtube.comments.setModerationStatus",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_comments_setModerationStatus(
    account: str,
    id: list[str],
    moderation_status: Literal["heldForReview", "published", "rejected"],
    ban_author: bool | None = None,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Set a comment's moderation status."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.comments()
        .setModerationStatus(
            id=id,
            moderationStatus=moderation_status,
            banAuthor=ban_author,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_comments_markAsSpam",
    api="youtube",
    method="youtube.comments.markAsSpam",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_comments_markAsSpam(
    account: str,
    id: list[str],
    ctx: Context | None = None,
) -> dict[str, object]:
    """Mark a comment as spam."""
    service = _youtube_service(account)
    return cast(
        dict[str, object],
        service.comments()
        .markAsSpam(
            id=id,
        )
        .execute(),
    )


@youtube_tool(
    name="youtube_comments_delete",
    api="youtube",
    method="youtube.comments.delete",
    scopes=[YouTubeScope.FORCE_SSL],
    cost=50,
    mutating=True,
)
def youtube_comments_delete(
    account: str,
    id: str,
    ctx: Context | None = None,
) -> dict[str, object]:
    """Delete a comment."""
    service = _youtube_service(account)
    response = service.comments().delete(id=id).execute()
    if isinstance(response, dict):
        return cast(dict[str, object], response)
    return {}
