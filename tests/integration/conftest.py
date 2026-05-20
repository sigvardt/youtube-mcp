"""Shared fixtures for recorded Google API integration tests."""

# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false, reportUnknownVariableType=false

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import googleapiclient
import pytest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build_from_document

from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy

TEST_ACCOUNT = "test_account"

_DISCOVERY_ROOT = Path(googleapiclient.__file__).parent / "discovery_cache" / "documents"


class IntegrationQuotaTracker:
    enforce: bool
    preflight_calls: list[tuple[str, int]]
    record_calls: list[tuple[str, int]]

    def __init__(self) -> None:
        self.enforce = False
        self.preflight_calls = []
        self.record_calls = []

    def would_exceed(self, account_key: str, units: int) -> bool:
        self.preflight_calls.append((account_key, units))
        return False

    def record(self, account_key: str, units: int) -> None:
        self.record_calls.append((account_key, units))


class RecordedAccountManager:
    _services: dict[tuple[str, str], Any]
    credentials_calls: list[str]
    youtube_calls: list[str]
    analytics_calls: list[str]
    reporting_calls: list[str]
    _credentials: Credentials

    def __init__(self) -> None:
        self._services = {}
        self.credentials_calls = []
        self.youtube_calls = []
        self.analytics_calls = []
        self.reporting_calls = []
        self._credentials = Credentials(token="synthetic-access-token")  # type: ignore[no-untyped-call]

    def get_credentials(self, key: str) -> Credentials:
        self._assert_test_account(key)
        self.credentials_calls.append(key)
        return self._credentials

    def get_youtube_service(self, key: str) -> Any:
        self._assert_test_account(key)
        self.youtube_calls.append(key)
        return self._service(key, "youtube", "youtube.v3.json")

    def get_analytics_service(self, key: str) -> Any:
        self._assert_test_account(key)
        self.analytics_calls.append(key)
        return self._service(key, "youtubeAnalytics", "youtubeAnalytics.v2.json")

    def get_reporting_service(self, key: str) -> Any:
        self._assert_test_account(key)
        self.reporting_calls.append(key)
        return self._service(key, "youtubereporting", "youtubereporting.v1.json")

    def _service(self, key: str, api_key: str, document_name: str) -> Any:
        cache_key = (key, api_key)
        if cache_key not in self._services:
            discovery_document = (_DISCOVERY_ROOT / document_name).read_text()
            self._services[cache_key] = build_from_document(
                discovery_document,
                credentials=self._credentials,
            )
        return self._services[cache_key]

    def _assert_test_account(self, key: str) -> None:
        if key != TEST_ACCOUNT:
            raise AssertionError(f"integration tests must use {TEST_ACCOUNT!r}, got {key!r}")


@dataclass(frozen=True)
class RecordedFramework:
    account_manager: RecordedAccountManager
    quota_tracker: IntegrationQuotaTracker
    mutating_guard_calls: list[str]


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=3,
        initial_wait=0.001,
        max_wait=0.01,
        multiplier=1.0,
        jitter=False,
    )


@pytest.fixture(scope="module")
def vcr_cassette_dir() -> str:
    return str(Path(__file__).with_name("cassettes"))


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, object]:
    record_mode = os.environ.get("VCR_RECORD_MODE")
    if record_mode is None:
        record_mode = "once" if os.environ.get("RUN_LIVE_TESTS") else "none"

    return {
        "record_mode": record_mode,
        "filter_headers": ["authorization", "Authorization"],
        "filter_query_parameters": ["key", "access_token"],
        "decode_compressed_response": True,
    }


@pytest.fixture()
def recorded_framework() -> RecordedFramework:
    account_manager = RecordedAccountManager()
    quota_tracker = IntegrationQuotaTracker()
    mutating_guard_calls: list[str] = []
    mutating_guard: Callable[[str], None] = mutating_guard_calls.append
    configure_framework(
        FrameworkContext(
            account_manager=account_manager,
            quota_tracker=quota_tracker,
            mutating_guard=mutating_guard,
            retry_policy=_retry_policy(),
        )
    )
    return RecordedFramework(
        account_manager=account_manager,
        quota_tracker=quota_tracker,
        mutating_guard_calls=mutating_guard_calls,
    )
