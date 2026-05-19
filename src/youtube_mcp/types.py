"""Type definitions for youtube_mcp."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class YouTubeScope(str, Enum):  # noqa: UP042
    """Supported YouTube OAuth scopes."""

    READONLY = "https://www.googleapis.com/auth/youtube.readonly"
    MANAGE = "https://www.googleapis.com/auth/youtube"
    UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
    PARTNER = "https://www.googleapis.com/auth/youtubepartner"
    FORCE_SSL = "https://www.googleapis.com/auth/youtube.force-ssl"
    ANALYTICS_READONLY = "https://www.googleapis.com/auth/yt-analytics.readonly"
    ANALYTICS_MONETARY = "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"
    REPORTING = "https://www.googleapis.com/auth/yt-analytics.readonly"


class AccountConfig(BaseModel):
    """OAuth account configuration for a single YouTube account."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    client_id: str
    client_secret: str
    channel_id: str | None = None
    channel_handle: str | None = None
    oauth_scopes: list[YouTubeScope]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TokenBundle(BaseModel):
    """Stored OAuth token payload."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    expiry: datetime
    scopes: list[str]


class RetryPolicy(BaseModel):
    """Retry backoff configuration."""

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = 5
    initial_wait: float = 1.0
    max_wait: float = 60.0
    multiplier: float = 2.0
    jitter: bool = True


class QuotaState(BaseModel):
    """Daily quota usage tracking for an account."""

    model_config = ConfigDict(extra="forbid")

    account_key: str
    units_used_today: int = 0
    last_reset: datetime = Field(default_factory=lambda: datetime.now(UTC))
    daily_limit: int = 10000


class UploadProgress(BaseModel):
    """Progress report for long-running uploads."""

    model_config = ConfigDict(extra="forbid")

    bytes_uploaded: int
    bytes_total: int
    percent: float

    @field_validator("percent")
    @classmethod
    def validate_percent(cls, value: float) -> float:
        """Ensure upload progress stays within a percentage range."""

        if value < 0 or value > 100:
            raise ValueError("percent must be between 0 and 100")
        return value


class MutatingGuardConfig(BaseModel):
    """Guardrail settings for mutating YouTube operations."""

    model_config = ConfigDict(extra="forbid")

    allowed_channel_handle: str = "@jsigvardt"
    enforce: bool = True
