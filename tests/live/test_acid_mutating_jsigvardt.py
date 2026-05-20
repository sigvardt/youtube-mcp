"""Live mutating acid tests restricted to the ``@jsigvardt`` brand account.

These tests are skipped unless both ``RUN_LIVE_TESTS=1`` and
``RUN_MUTATING_TESTS=1`` are set. When enabled, collection and setup assert that
the configured ``jsigvardt`` account resolves to ``@jsigvardt`` before any test
body can execute. ``RUN_DESTRUCTIVE_LIVE=1`` is additionally required for the
irreversible abuse-report smoke test.

``tests/fixtures/test_video_30s.mp4`` is a placeholder fixture in this repo. Replace
it with a real private-safe 30 second MP4 before running this suite against YouTube.
"""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false

from __future__ import annotations

import copy
import os
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from tests.live.conftest import SKIPPABLE_PERMISSION_REASONS
from youtube_mcp.auth.accounts import AccountConfigStore, AccountManager, AccountNotFoundError
from youtube_mcp.auth.token_store import make_token_store
from youtube_mcp.tools import (
    analytics_groups,
    channel_sections,
    channels,
    comment_threads,
    comments,
    livestream,
    playlists,
    reporting_jobs,
    subscriptions,
    video_assets,
    video_meta,
    videos,
)
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import AccountConfig, RetryPolicy
from youtube_mcp.utils.mutating_guard import MutatingGuard, MutatingOpForbiddenError
from youtube_mcp.utils.quota import QuotaTracker

ACCOUNT_KEY = "jsigvardt"
ALLOWED_HANDLE = "@jsigvardt"
RUN_LIVE_TESTS = "RUN_LIVE_TESTS"
RUN_MUTATING_TESTS = "RUN_MUTATING_TESTS"
RUN_DESTRUCTIVE_LIVE = "RUN_DESTRUCTIVE_LIVE"
THUMBNAIL_TARGET_VIDEO_ENV = "YOUTUBE_MCP_ACID_THUMBNAIL_VIDEO_ID"

PROJECT_ROOT = Path(__file__).parents[2]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
EVIDENCE_UPLOAD_IDS = PROJECT_ROOT / ".sisyphus" / "evidence" / "task-47-uploaded-video-ids.txt"
TEST_VIDEO_PATH = FIXTURES_DIR / "test_video_30s.mp4"
TEST_THUMBNAIL_PATH = FIXTURES_DIR / "test_thumbnail.jpg"
TEST_THUMBNAIL_REVERT_PATH = FIXTURES_DIR / "test_thumbnail_revert.jpg"
TEST_BANNER_PATH = FIXTURES_DIR / "test_banner.jpg"
TEST_WATERMARK_PATH = FIXTURES_DIR / "test_watermark.png"

DEFAULT_PUBLIC_VIDEO_ID = "dQw4w9WgXcQ"
DEFAULT_SUBSCRIBE_CHANNEL_ID = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
SENTINEL = f"youtube-mcp-acid-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def _env_flag(name: str) -> bool:
    return os.environ.get(name) == "1"


def _live_mutating_enabled() -> bool:
    return _env_flag(RUN_LIVE_TESTS) and _env_flag(RUN_MUTATING_TESTS)


pytestmark = pytest.mark.skipif(
    not _live_mutating_enabled(),
    reason="set RUN_LIVE_TESTS=1 and RUN_MUTATING_TESTS=1 to run mutating live tests",
)


class _ConfigOnlyAccountManager:
    _config_store: AccountConfigStore

    def __init__(self, config_store: AccountConfigStore) -> None:
        self._config_store = config_store

    def get(self, key: str) -> AccountConfig:
        account = self._config_store.get(key)
        if account is None:
            raise AccountNotFoundError(f"Account {key!r} is not configured")
        return account


def _assert_jsigvardt_configured() -> None:
    config_manager = _ConfigOnlyAccountManager(AccountConfigStore())
    account = config_manager.get(ACCOUNT_KEY)
    if account.channel_handle != ALLOWED_HANDLE:
        raise MutatingOpForbiddenError(
            account_key=ACCOUNT_KEY,
            expected=ALLOWED_HANDLE,
            got=account.channel_handle,
        )
    MutatingGuard().assert_allowed(ACCOUNT_KEY, cast(AccountManager, cast(object, config_manager)))


if _live_mutating_enabled():
    _assert_jsigvardt_configured()


@pytest.fixture(scope="session", autouse=True)
def mutating_account() -> str:
    """Return the only account key allowed for this file after a hard handle gate."""

    if not _live_mutating_enabled():
        pytest.skip("mutating live tests are disabled")
    try:
        _assert_jsigvardt_configured()
    except MutatingOpForbiddenError as exc:
        pytest.exit(str(exc), returncode=4)
    return ACCOUNT_KEY


@pytest.fixture(scope="session", autouse=True)
def live_framework(mutating_account: str) -> None:
    account_manager = AccountManager(AccountConfigStore(), make_token_store())
    guard = MutatingGuard()

    def assert_mutating_account(account: str) -> None:
        guard.assert_allowed(account, account_manager)

    configure_framework(
        FrameworkContext(
            account_manager=account_manager,
            quota_tracker=QuotaTracker(),
            mutating_guard=assert_mutating_account,
            retry_policy=RetryPolicy(),
        )
    )
    _ = mutating_account


@pytest.fixture(scope="session")
def acid_marker() -> str:
    return SENTINEL


@pytest.fixture(scope="session")
def public_video_id() -> str:
    return os.environ.get("YOUTUBE_MCP_ACID_PUBLIC_VIDEO_ID", DEFAULT_PUBLIC_VIDEO_ID)


def _resource_id(response: Mapping[str, object]) -> str:
    value = response.get("id")
    assert isinstance(value, str) and value
    return value


def _items(response: Mapping[str, object]) -> list[Mapping[str, object]]:
    value = response.get("items")
    assert isinstance(value, list)
    raw_items = cast(list[object], value)
    items: list[Mapping[str, object]] = []
    for item in raw_items:
        if isinstance(item, Mapping):
            items.append(cast(Mapping[str, object], item))
    return items


def _first_item(response: Mapping[str, object], label: str) -> Mapping[str, object]:
    items = _items(response)
    if not items:
        pytest.skip(f"no {label} available for mutating acid test", allow_module_level=False)
    return items[0]


def _response(value: dict[str, object] | dict[str, dict[str, object]]) -> dict[str, object]:
    response = cast(dict[str, object], value)
    error = response.get("error")
    if isinstance(error, Mapping):
        error_mapping = cast(Mapping[str, object], error)
        reason = error_mapping.get("reason")
        if isinstance(reason, str) and reason in SKIPPABLE_PERMISSION_REASONS:
            pytest.skip(f"mutating acid test skipped: {reason}")
        pytest.fail(f"Google API returned MCP error: {error}")
    return response


def _mapping(value: object) -> Mapping[str, object]:
    assert isinstance(value, Mapping)
    return cast(Mapping[str, object], value)


def _string(value: object, label: str) -> str:
    assert isinstance(value, str) and value, label
    return value


def _deepcopy_mapping(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        source = dict(cast(Mapping[str, object], value))
        copied = copy.deepcopy(source)
        return copied
    return {}


def _own_channel(mutating_account: str) -> Mapping[str, object]:
    response = _response(
        channels.youtube_channels_list(
            account=mutating_account,
            part="id,snippet,brandingSettings,contentDetails,status",
            mine=True,
        )
    )
    return _first_item(response, "owned channel")


@pytest.fixture(scope="session")
def own_channel_id(mutating_account: str) -> str:
    return _string(_own_channel(mutating_account).get("id"), "owned channel id")


def _own_uploads_playlist_id(mutating_account: str) -> str:
    channel = _own_channel(mutating_account)
    content_details = _mapping(channel.get("contentDetails"))
    related_playlists = _mapping(content_details.get("relatedPlaylists"))
    return _string(related_playlists.get("uploads"), "owned uploads playlist id")


def _first_owned_video_id(mutating_account: str) -> str:
    uploads_playlist_id = _own_uploads_playlist_id(mutating_account)
    response = _response(
        playlists.youtube_playlistItems_list(
            account=mutating_account,
            part="snippet,contentDetails",
            playlist_id=uploads_playlist_id,
            max_results=1,
        )
    )
    item = _first_item(response, "owned uploaded video")
    content_details = _mapping(item.get("contentDetails"))
    return _string(content_details.get("videoId"), "owned uploaded video id")


def _visible_comment_id(mutating_account: str, comment_id: str) -> str | None:
    for _attempt in range(3):
        response = _response(
            comments.youtube_comments_list(
                account=mutating_account,
                part="id",
                id=comment_id,
            )
        )
        items = _items(response)
        if items:
            return _resource_id(items[0])
        time.sleep(2)
    return None


def _fixture_path(path: Path, label: str) -> str:
    if not path.exists():
        pytest.fail(f"missing {label} fixture at {path}")
    return str(path)


def _record_uploaded_video_id(video_id: str, marker: str) -> None:
    EVIDENCE_UPLOAD_IDS.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat()
    with EVIDENCE_UPLOAD_IDS.open("a", encoding="utf-8") as handle:
        _ = handle.write(f"{timestamp}\t{marker}\t{video_id}\n")


@pytest.fixture(scope="session")
def uploaded_private_video_id(mutating_account: str, acid_marker: str) -> str:
    video_body: dict[str, object] = {
        "snippet": {
            "title": f"{acid_marker} uploaded private fixture",
            "description": f"{acid_marker} manual cleanup required",
            "tags": [acid_marker, "youtube-mcp-acid"],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
        },
    }
    response = _response(
        videos.youtube_videos_insert(
            account=mutating_account,
            part="snippet,status",
            video_body=video_body,
            file_path=_fixture_path(TEST_VIDEO_PATH, "private test video"),
            notify_subscribers=False,
        )
    )
    video_id = _resource_id(response)
    _record_uploaded_video_id(video_id, acid_marker)
    return video_id


@pytest.fixture(scope="session")
def thumbnail_target_video_id(mutating_account: str) -> str:
    configured_video_id = os.environ.get(THUMBNAIL_TARGET_VIDEO_ENV)
    if configured_video_id is not None:
        return configured_video_id
    return _first_owned_video_id(mutating_account)


@pytest.fixture(scope="session")
def analytics_video_id(mutating_account: str) -> str:
    configured_video_id = os.environ.get("YOUTUBE_MCP_ACID_ANALYTICS_VIDEO_ID")
    if configured_video_id is not None:
        return configured_video_id
    configured_own_video_id = os.environ.get("YOUTUBE_MCP_ACID_OWN_VIDEO_ID")
    if configured_own_video_id is not None:
        return configured_own_video_id
    return _first_owned_video_id(mutating_account)


@pytest.mark.live
@pytest.mark.mutating
def test_playlists_create_update_delete(mutating_account: str, acid_marker: str) -> None:
    playlist_id: str | None = None
    try:
        created = _response(
            playlists.youtube_playlists_insert(
                account=mutating_account,
                part="snippet,status",
                playlist_body={
                    "snippet": {
                        "title": f"{acid_marker} playlist",
                        "description": f"{acid_marker} playlist create",
                    },
                    "status": {"privacyStatus": "private"},
                },
            )
        )
        playlist_id = _resource_id(created)
        listed = _response(
            playlists.youtube_playlists_list(
                account=mutating_account,
                part="snippet,status",
                id=playlist_id,
                max_results=1,
            )
        )
        created_playlist = _first_item(listed, "created playlist")
        assert _resource_id(created_playlist) == playlist_id

        updated = _response(
            playlists.youtube_playlists_update(
                account=mutating_account,
                part="snippet,status",
                playlist_body={
                    "id": playlist_id,
                    "snippet": {
                        "title": f"{acid_marker} playlist updated",
                        "description": f"{acid_marker} playlist update",
                    },
                    "status": {"privacyStatus": "private"},
                },
            )
        )
        assert _resource_id(updated) == playlist_id
    finally:
        if playlist_id is not None:
            _ = _response(
                playlists.youtube_playlists_delete(account=mutating_account, id=playlist_id)
            )


@pytest.mark.live
@pytest.mark.mutating
def test_playlist_items_insert_delete(
    mutating_account: str,
    acid_marker: str,
    public_video_id: str,
) -> None:
    playlist_id: str | None = None
    item_id: str | None = None
    try:
        playlist_id = _resource_id(
            _response(
                playlists.youtube_playlists_insert(
                    account=mutating_account,
                    part="snippet,status",
                    playlist_body={
                        "snippet": {
                            "title": f"{acid_marker} playlist item host",
                            "description": acid_marker,
                        },
                        "status": {"privacyStatus": "private"},
                    },
                )
            )
        )
        inserted = _response(
            playlists.youtube_playlistItems_insert(
                account=mutating_account,
                part="snippet,contentDetails",
                item_body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": public_video_id},
                    },
                },
            )
        )
        item_id = _resource_id(inserted)
        listed = _response(
            playlists.youtube_playlistItems_list(
                account=mutating_account,
                part="snippet,contentDetails",
                playlist_id=playlist_id,
                video_id=public_video_id,
                max_results=1,
            )
        )
        playlist_item = _first_item(listed, "playlist item")
        assert _resource_id(playlist_item) == item_id
    finally:
        if item_id is not None:
            _ = _response(
                playlists.youtube_playlistItems_delete(account=mutating_account, id=item_id)
            )
        if playlist_id is not None:
            _ = _response(
                playlists.youtube_playlists_delete(account=mutating_account, id=playlist_id)
            )


@pytest.mark.live
@pytest.mark.mutating
def test_channel_sections_insert_update_delete(mutating_account: str, acid_marker: str) -> None:
    playlist_id: str | None = None
    section_id: str | None = None
    try:
        playlist_id = _resource_id(
            _response(
                playlists.youtube_playlists_insert(
                    account=mutating_account,
                    part="snippet,status",
                    playlist_body={
                        "snippet": {
                            "title": f"{acid_marker} section playlist",
                            "description": acid_marker,
                        },
                        "status": {"privacyStatus": "private"},
                    },
                )
            )
        )
        inserted = _response(
            channel_sections.youtube_channelSections_insert(
                account=mutating_account,
                part="snippet,contentDetails",
                section_body={
                    "snippet": {"type": "singlePlaylist", "style": "horizontalRow"},
                    "contentDetails": {"playlists": [playlist_id]},
                },
            )
        )
        section_id = _resource_id(inserted)
        updated = _response(
            channel_sections.youtube_channelSections_update(
                account=mutating_account,
                part="snippet,contentDetails",
                section_body={
                    "id": section_id,
                    "snippet": {"type": "singlePlaylist", "style": "verticalList"},
                    "contentDetails": {"playlists": [playlist_id]},
                },
            )
        )
        assert _resource_id(updated) == section_id
    finally:
        if section_id is not None:
            _ = _response(
                channel_sections.youtube_channelSections_delete(
                    account=mutating_account,
                    id=section_id,
                )
            )
        if playlist_id is not None:
            _ = _response(
                playlists.youtube_playlists_delete(account=mutating_account, id=playlist_id)
            )


@pytest.mark.live
@pytest.mark.mutating
def test_subscriptions_subscribe_unsubscribe(mutating_account: str) -> None:
    target_channel_id = os.environ.get(
        "YOUTUBE_MCP_ACID_SUBSCRIBE_CHANNEL_ID",
        DEFAULT_SUBSCRIBE_CHANNEL_ID,
    )
    subscription_id: str | None = None
    try:
        inserted = _response(
            subscriptions.youtube_subscriptions_insert(
                account=mutating_account,
                part="snippet",
                subscription_body={
                    "snippet": {
                        "resourceId": {"kind": "youtube#channel", "channelId": target_channel_id},
                    },
                },
            )
        )
        subscription_id = _resource_id(inserted)
        assert subscription_id
    finally:
        if subscription_id is not None:
            _ = _response(
                subscriptions.youtube_subscriptions_delete(
                    account=mutating_account,
                    id=subscription_id,
                )
            )


@pytest.mark.live
@pytest.mark.mutating
def test_comments_insert_update_delete(
    mutating_account: str,
    acid_marker: str,
    public_video_id: str,
) -> None:
    parent_comment_id: str | None = None
    reply_id: str | None = None
    try:
        thread = _response(
            comment_threads.youtube_commentThreads_insert(
                            account=mutating_account,
                            part="snippet",
                            thread_body={
                                "snippet": {
                                    "videoId": public_video_id,
                                    "topLevelComment": {
                                        "snippet": {
                                            "textOriginal": f"{acid_marker} parent comment",
                                        },
                                    },
                                },
                            },
                        )
        )
        thread_snippet = _mapping(thread.get("snippet"))
        top_level_comment = _mapping(thread_snippet.get("topLevelComment"))
        parent_comment_id = _resource_id(top_level_comment)
        visible_parent_comment_id = _visible_comment_id(mutating_account, parent_comment_id)
        if visible_parent_comment_id is None:
            pytest.skip("inserted parent comment was not visible before reply insert")
        reply = _response(
            comments.youtube_comments_insert(
                account=mutating_account,
                part="snippet",
                comment_body={
                    "snippet": {
                        "parentId": visible_parent_comment_id,
                        "textOriginal": f"{acid_marker} reply comment",
                    },
                },
            )
        )
        reply_id = _resource_id(reply)
        updated = _response(
            comments.youtube_comments_update(
                account=mutating_account,
                part="snippet",
                comment_body={
                    "id": reply_id,
                    "snippet": {"textOriginal": f"{acid_marker} reply comment updated"},
                },
            )
        )
        assert _resource_id(updated) == reply_id
    finally:
        if reply_id is not None:
            _ = _response(comments.youtube_comments_delete(account=mutating_account, id=reply_id))
        if parent_comment_id is not None:
            _ = _response(
                comments.youtube_comments_delete(account=mutating_account, id=parent_comment_id)
            )


@pytest.mark.live
@pytest.mark.mutating
def test_comment_threads_insert_then_comment_delete(
    mutating_account: str,
    acid_marker: str,
    public_video_id: str,
) -> None:
    top_level_comment_id: str | None = None
    try:
        inserted = _response(
            comment_threads.youtube_commentThreads_insert(
                            account=mutating_account,
                            part="snippet",
                            thread_body={
                                "snippet": {
                                    "videoId": public_video_id,
                                    "topLevelComment": {
                                        "snippet": {
                                            "textOriginal": f"{acid_marker} thread comment",
                                        },
                                    },
                                },
                            },
                        )
        )
        snippet = _mapping(inserted.get("snippet"))
        top_level_comment = _mapping(snippet.get("topLevelComment"))
        top_level_comment_id = _resource_id(top_level_comment)
        assert top_level_comment_id
    finally:
        if top_level_comment_id is not None:
            _ = _response(
                comments.youtube_comments_delete(account=mutating_account, id=top_level_comment_id)
            )


@pytest.mark.live
@pytest.mark.mutating
def test_channels_update_keywords_then_revert(mutating_account: str, acid_marker: str) -> None:
    channel = _own_channel(mutating_account)
    channel_id = _string(channel.get("id"), "owned channel id")
    original_branding = _deepcopy_mapping(channel.get("brandingSettings"))
    modified_branding = _deepcopy_mapping(original_branding)
    modified_channel = _deepcopy_mapping(modified_branding.get("channel"))
    original_keywords = modified_channel.get("keywords")
    keywords = original_keywords if isinstance(original_keywords, str) else ""
    modified_channel["keywords"] = f"{keywords} {acid_marker}".strip()
    modified_branding["channel"] = modified_channel

    try:
        updated = _response(
            channels.youtube_channels_update(
                account=mutating_account,
                part="brandingSettings",
                channel_body={"id": channel_id, "brandingSettings": modified_branding},
            )
        )
        assert _resource_id(updated) == channel_id
    finally:
        _ = _response(
            channels.youtube_channels_update(
                account=mutating_account,
                part="brandingSettings",
                channel_body={"id": channel_id, "brandingSettings": original_branding},
            )
        )


@pytest.mark.live
@pytest.mark.mutating
def test_channel_banners_insert(mutating_account: str, own_channel_id: str) -> None:
    response = _response(
        channels.youtube_channel_banners_insert(
            account=mutating_account,
            banner_file_path=_fixture_path(TEST_BANNER_PATH, "banner image"),
            channel_id=own_channel_id,
        )
    )
    assert isinstance(response.get("url"), str)


@pytest.mark.live
@pytest.mark.mutating
def test_thumbnails_set_then_revert(mutating_account: str, thumbnail_target_video_id: str) -> None:
    try:
        response = _response(
            video_assets.youtube_thumbnails_set(
                account=mutating_account,
                video_id=thumbnail_target_video_id,
                image_file_path=_fixture_path(TEST_THUMBNAIL_PATH, "thumbnail image"),
            )
        )
        assert isinstance(response, dict)
    finally:
        _ = _response(
            video_assets.youtube_thumbnails_set(
                account=mutating_account,
                video_id=thumbnail_target_video_id,
                image_file_path=_fixture_path(TEST_THUMBNAIL_REVERT_PATH, "thumbnail revert image"),
            )
        )


@pytest.mark.live
@pytest.mark.mutating
def test_watermarks_set_unset(
    mutating_account: str,
    own_channel_id: str,
    acid_marker: str,
) -> None:
    _ = acid_marker
    try:
        _ = _response(
            video_assets.youtube_watermarks_set(
                account=mutating_account,
                channel_id=own_channel_id,
                watermark_body={
                    "timing": {"type": "offsetFromStart", "offsetMs": 0, "durationMs": 5000},
                    "position": {"type": "corner", "cornerPosition": "bottomRight"},
                },
                image_file_path=_fixture_path(TEST_WATERMARK_PATH, "watermark image"),
            )
        )
    finally:
        _ = _response(
            video_assets.youtube_watermarks_unset(
                account=mutating_account,
                channel_id=own_channel_id,
            )
        )


@pytest.mark.live
@pytest.mark.mutating
def test_live_broadcasts_insert_update_delete(mutating_account: str, acid_marker: str) -> None:
    broadcast_id: str | None = None
    scheduled_start = (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    try:
        inserted = _response(
            livestream.youtube_liveBroadcasts_insert(
                account=mutating_account,
                part="snippet,status,contentDetails",
                broadcast_body={
                    "snippet": {
                        "title": f"{acid_marker} live broadcast",
                        "description": f"{acid_marker} scheduled far future",
                        "scheduledStartTime": scheduled_start,
                    },
                    "status": {"privacyStatus": "private"},
                    "contentDetails": {"enableAutoStart": False, "enableAutoStop": False},
                },
            )
        )
        broadcast_id = _resource_id(inserted)
        updated = _response(
            livestream.youtube_liveBroadcasts_update(
                account=mutating_account,
                part="snippet,status,contentDetails",
                broadcast_body={
                    "id": broadcast_id,
                    "snippet": {
                        "title": f"{acid_marker} live broadcast updated",
                        "description": f"{acid_marker} scheduled far future updated",
                        "scheduledStartTime": scheduled_start,
                    },
                    "status": {"privacyStatus": "private"},
                    "contentDetails": {"enableAutoStart": False, "enableAutoStop": False},
                },
            )
        )
        assert _resource_id(updated) == broadcast_id
    finally:
        if broadcast_id is not None:
            _ = _response(
                livestream.youtube_liveBroadcasts_delete(account=mutating_account, id=broadcast_id)
            )


@pytest.mark.live
@pytest.mark.mutating
def test_live_streams_insert_delete(mutating_account: str, acid_marker: str) -> None:
    stream_id: str | None = None
    try:
        inserted = _response(
            livestream.youtube_liveStreams_insert(
                account=mutating_account,
                part="snippet,cdn",
                stream_body={
                    "snippet": {
                        "title": f"{acid_marker} live stream",
                        "description": f"{acid_marker} live stream delete cleanup",
                    },
                    "cdn": {
                        "ingestionType": "rtmp",
                        "resolution": "720p",
                        "frameRate": "30fps",
                    },
                },
            )
        )
        stream_id = _resource_id(inserted)
        assert stream_id
    finally:
        if stream_id is not None:
            _ = _response(
                livestream.youtube_liveStreams_delete(account=mutating_account, id=stream_id)
            )


@pytest.mark.live
@pytest.mark.mutating
def test_videos_insert_update_keeps_uploaded_video_for_manual_cleanup(
    mutating_account: str,
    acid_marker: str,
    uploaded_private_video_id: str,
) -> None:
    updated = _response(
        videos.youtube_videos_update(
            account=mutating_account,
            part="snippet,status",
            video_body={
                "id": uploaded_private_video_id,
                "snippet": {
                    "title": f"{acid_marker} uploaded private fixture updated",
                    "description": f"{acid_marker} manual cleanup required after update",
                    "tags": [acid_marker, "youtube-mcp-acid"],
                    "categoryId": "22",
                },
                "status": {
                    "privacyStatus": "private",
                    "selfDeclaredMadeForKids": False,
                },
            },
        )
    )
    assert _resource_id(updated) == uploaded_private_video_id


@pytest.mark.live
@pytest.mark.mutating
def test_videos_rate_like_then_none(mutating_account: str, public_video_id: str) -> None:
    _ = _response(
        videos.youtube_videos_rate(account=mutating_account, id=public_video_id, rating="like")
    )
    _ = _response(
        videos.youtube_videos_rate(account=mutating_account, id=public_video_id, rating="none")
    )


@pytest.mark.live
@pytest.mark.mutating
@pytest.mark.skipif(
    not _env_flag(RUN_DESTRUCTIVE_LIVE),
    reason="set RUN_DESTRUCTIVE_LIVE=1 to run irreversible abuse-report smoke test",
)
def test_abuse_reports_insert_destructive_only(mutating_account: str, acid_marker: str) -> None:
    target_video_id = os.environ.get("YOUTUBE_MCP_ACID_ABUSE_VIDEO_ID", DEFAULT_PUBLIC_VIDEO_ID)
    reasons = _response(
        video_meta.youtube_videoAbuseReportReasons_list(account=mutating_account, part="snippet")
    )
    reason = _first_item(reasons, "abuse report reason")
    reason_id = _string(reason.get("id"), "abuse report reason id")
    _ = _response(
        videos.youtube_videos_reportAbuse(
            account=mutating_account,
            abuse_report_body={
                "videoId": target_video_id,
                "reasonId": reason_id,
                "comments": f"{acid_marker} destructive live smoke test",
                "language": "en",
            },
        )
    )


@pytest.mark.live
@pytest.mark.mutating
def test_analytics_groups_insert_add_remove_delete(
    mutating_account: str,
    acid_marker: str,
    analytics_video_id: str,
) -> None:
    group_id: str | None = None
    group_item_id: str | None = None
    try:
        group_id = _resource_id(
            _response(
                analytics_groups.youtube_analytics_groups_insert(
                    account=mutating_account,
                    group_body={
                        "snippet": {"title": f"{acid_marker} analytics group"},
                        "contentDetails": {"itemType": "youtube#video"},
                    },
                )
            )
        )
        group_item_id = _resource_id(
            _response(
                analytics_groups.youtube_analytics_groupItems_insert(
                    account=mutating_account,
                    group_item_body={
                        "groupId": group_id,
                        "resource": {"kind": "youtube#video", "id": analytics_video_id},
                    },
                )
            )
        )
        listed = _response(
            analytics_groups.youtube_analytics_groupItems_list(
                account=mutating_account,
                group_id=group_id,
            )
        )
        assert any(_resource_id(item) == group_item_id for item in _items(listed))
    finally:
        if group_item_id is not None:
            _ = _response(
                analytics_groups.youtube_analytics_groupItems_delete(
                    account=mutating_account,
                    id=group_item_id,
                )
            )
        if group_id is not None:
            _ = _response(
                analytics_groups.youtube_analytics_groups_delete(
                    account=mutating_account,
                    id=group_id,
                )
            )


@pytest.mark.live
@pytest.mark.mutating
def test_reporting_jobs_create_delete(mutating_account: str, acid_marker: str) -> None:
    job_id: str | None = None
    try:
        report_types = _response(
            reporting_jobs.youtube_reporting_reportTypes_list(
                account=mutating_account,
                include_system_managed=False,
                page_size=10,
            )
        )
        available_report_types = report_types.get("reportTypes")
        if not isinstance(available_report_types, list) or not available_report_types:
            pytest.skip("no reporting report types available for this account")
        report_type_values = cast(list[object], available_report_types)
        report_type = _mapping(report_type_values[0])
        report_type_id = _string(report_type.get("id"), "report type id")
        created = _response(
            reporting_jobs.youtube_reporting_jobs_create(
                account=mutating_account,
                job_body={"reportTypeId": report_type_id, "name": f"{acid_marker} reporting job"},
            )
        )
        job_id = _resource_id(created)
        assert job_id
    finally:
        if job_id is not None:
            _ = _response(
                reporting_jobs.youtube_reporting_jobs_delete(
                    account=mutating_account,
                    job_id=job_id,
                )
            )
