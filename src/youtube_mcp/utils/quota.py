"""Persistent YouTube API quota tracking."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from youtube_mcp.types import QuotaState

logger = logging.getLogger("youtube_mcp.quota")

WARNING_THRESHOLD = 0.8

QUOTA_COSTS: dict[str, int] = {
    "youtube.activities.list": 1,
    "youtube.captions.list": 1,
    "youtube.captions.insert": 400,
    "youtube.captions.update": 450,
    "youtube.captions.download": 200,
    "youtube.channels.list": 1,
    "youtube.channels.update": 50,
    "youtube.channelBanners.insert": 50,
    "youtube.channelSections.list": 1,
    "youtube.channelSections.insert": 50,
    "youtube.channelSections.update": 50,
    "youtube.channelSections.delete": 50,
    "youtube.comments.list": 1,
    "youtube.comments.insert": 50,
    "youtube.comments.update": 50,
    "youtube.comments.markAsSpam": 50,
    "youtube.comments.setModerationStatus": 50,
    "youtube.comments.delete": 50,
    "youtube.commentThreads.list": 1,
    "youtube.commentThreads.insert": 50,
    "youtube.i18nLanguages.list": 1,
    "youtube.i18nRegions.list": 1,
    "youtube.members.list": 1,
    "youtube.membershipsLevels.list": 1,
    "youtube.playlists.list": 1,
    "youtube.playlists.insert": 50,
    "youtube.playlists.update": 50,
    "youtube.playlists.delete": 50,
    "youtube.playlistItems.list": 1,
    "youtube.playlistItems.insert": 50,
    "youtube.playlistItems.update": 50,
    "youtube.playlistItems.delete": 50,
    "youtube.search.list": 100,
    "youtube.subscriptions.list": 1,
    "youtube.subscriptions.insert": 50,
    "youtube.subscriptions.delete": 50,
    "youtube.videos.list": 1,
    "youtube.videos.insert": 1600,
    "youtube.videos.update": 50,
    "youtube.videos.rate": 50,
    "youtube.videos.getRating": 1,
    "youtube.videos.reportAbuse": 50,
    "youtube.thumbnails.set": 50,
    "youtube.watermarks.set": 50,
    "youtube.watermarks.unset": 50,
    "youtube.videoCategories.list": 1,
    "youtube.videoAbuseReportReasons.list": 1,
    "youtube.liveBroadcasts.list": 1,
    "youtube.liveBroadcasts.insert": 50,
    "youtube.liveBroadcasts.update": 50,
    "youtube.liveBroadcasts.delete": 50,
    "youtube.liveBroadcasts.bind": 50,
    "youtube.liveBroadcasts.transition": 50,
    "youtube.liveBroadcasts.cuepoint": 50,
    "youtube.liveStreams.list": 1,
    "youtube.liveStreams.insert": 50,
    "youtube.liveStreams.update": 50,
    "youtube.liveStreams.delete": 50,
    "youtube.liveChatMessages.list": 1,
    "youtube.liveChatMessages.insert": 50,
    "youtube.liveChatMessages.delete": 50,
    "youtube.liveChatModerators.list": 1,
    "youtube.liveChatModerators.insert": 50,
    "youtube.liveChatModerators.delete": 50,
    "youtube.liveChatBans.insert": 50,
    "youtube.liveChatBans.delete": 50,
    "youtube.superChatEvents.list": 1,
    "youtube.abuseReports.insert": 50,
    "youtube.tests.insert": 0,
    "youtubeAnalytics.reports.query": 1,
    "youtubeAnalytics.groups.list": 1,
    "youtubeAnalytics.groups.insert": 1,
    "youtubeAnalytics.groups.update": 1,
    "youtubeAnalytics.groups.delete": 1,
    "youtubeAnalytics.groupItems.list": 1,
    "youtubeAnalytics.groupItems.insert": 1,
    "youtubeAnalytics.groupItems.delete": 1,
    "youtubeReporting.jobs.list": 1,
    "youtubeReporting.jobs.create": 1,
    "youtubeReporting.jobs.delete": 1,
    "youtubeReporting.jobs.reports.list": 1,
    "youtubeReporting.jobs.reports.get": 1,
    "youtubeReporting.reportTypes.list": 1,
}


class QuotaExhaustedError(Exception):
    """Raised when a quota record would exceed the configured daily limit."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def quota_cost(method: str) -> int:
    """Return the quota cost for a Google API method name."""

    cost = QUOTA_COSTS.get(method)
    if cost is None:
        logger.debug("Unknown quota cost for method %s; defaulting to 0", method)
        return 0
    return cost


class QuotaTracker:
    """Track per-account YouTube API quota usage in JSON files."""

    def __init__(self, storage_dir: Path | None = None, enforce: bool = False) -> None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        self.storage_dir: Path = (
            storage_dir if storage_dir is not None else config_home / "youtube-mcp" / "quota"
        )
        self.enforce: bool = enforce
        self._states: dict[str, QuotaState] = {}
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def record(self, account_key: str, units: int) -> None:
        """Record quota units for an account and persist the updated state."""

        if self.enforce and self.would_exceed(account_key, units):
            state = self.current(account_key)
            message = (
                f"Recording {units} quota units for {account_key} would exceed daily limit "
                f"{state.daily_limit}"
            )
            raise QuotaExhaustedError(message)

        state = self.current(account_key)
        updated = state.model_copy(update={"units_used_today": state.units_used_today + units})
        self._states[account_key] = updated
        self._persist(updated)
        logger.debug(
            "Recorded %s quota units for account %s; used %s/%s today",
            units,
            account_key,
            updated.units_used_today,
            updated.daily_limit,
        )
        self._warn_if_threshold_reached(updated)

    def current(self, account_key: str) -> QuotaState:
        """Return current quota state, resetting it when the UTC date has advanced."""

        state = self._load(account_key)
        reset_state = self._reset_if_new_day(state)
        if reset_state is not state:
            self._states[account_key] = reset_state
            self._persist(reset_state)
        return reset_state

    def reset_if_new_day(self, account_key: str) -> None:
        """Persist a UTC-day reset for an account when its stored state is stale."""

        state = self._load(account_key)
        reset_state = self._reset_if_new_day(state)
        if reset_state is not state:
            self._states[account_key] = reset_state
            self._persist(reset_state)

    def would_exceed(self, account_key: str, units: int) -> bool:
        """Return True when adding units would put the account over its daily limit."""

        state = self.current(account_key)
        return state.units_used_today + units > state.daily_limit

    def _state_path(self, account_key: str) -> Path:
        return self.storage_dir / f"{account_key}.json"

    def _load(self, account_key: str) -> QuotaState:
        state = self._states.get(account_key)
        if state is not None:
            return state

        path = self._state_path(account_key)
        if path.exists():
            state = QuotaState.model_validate_json(path.read_text(encoding="utf-8"))
        else:
            state = QuotaState(account_key=account_key, last_reset=_utcnow())
        self._states[account_key] = state
        return state

    def _persist(self, state: QuotaState) -> None:
        path = self._state_path(state.account_key)
        _ = path.write_text(f"{state.model_dump_json()}\n", encoding="utf-8")
        os.chmod(path, 0o600)

    def _reset_if_new_day(self, state: QuotaState) -> QuotaState:
        now = _utcnow()
        if state.last_reset.date() < now.date():
            return state.model_copy(update={"units_used_today": 0, "last_reset": now})
        return state

    def _warn_if_threshold_reached(self, state: QuotaState) -> None:
        if state.daily_limit and state.units_used_today / state.daily_limit >= WARNING_THRESHOLD:
            logger.warning(
                "YouTube quota usage for account %s is at %.1f%% (%s/%s units)",
                state.account_key,
                state.units_used_today / state.daily_limit * 100,
                state.units_used_today,
                state.daily_limit,
            )
