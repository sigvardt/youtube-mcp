"""Tests for the YouTube i18n tools."""

# pyright: reportMissingTypeStubs=false, reportRedeclaration=false, reportUnannotatedClassAttribute=false

from __future__ import annotations

import inspect

import pytest

from youtube_mcp.server import mcp
from youtube_mcp.tools import i18n
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy


class FakeQuotaTracker:
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


class FakeI18nRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeI18nResource:
    request: FakeI18nRequest
    list_calls: list[dict[str, object]]

    def __init__(self, response: dict[str, object]) -> None:
        self.request = FakeI18nRequest(response)
        self.list_calls = []

    def list(self, **kwargs: object) -> FakeI18nRequest:
        self.list_calls.append(dict(kwargs))
        return self.request


class FakeYouTubeService:
    i18n_languages_resource: FakeI18nResource
    i18n_regions_resource: FakeI18nResource
    i18n_languages_calls: int
    i18n_regions_calls: int

    def __init__(self) -> None:
        self.i18n_languages_resource = FakeI18nResource({"items": [{"id": "lang-en"}]})
        self.i18n_regions_resource = FakeI18nResource({"items": [{"id": "region-us"}]})
        self.i18n_languages_calls = 0
        self.i18n_regions_calls = 0

    def i18nLanguages(self) -> FakeI18nResource:
        self.i18n_languages_calls += 1
        return self.i18n_languages_resource

    def i18nRegions(self) -> FakeI18nResource:
        self.i18n_regions_calls += 1
        return self.i18n_regions_resource


class FakeAccountManager:
    service: FakeYouTubeService
    _services: dict[tuple[str, str], object]
    credentials_calls: list[str]
    youtube_calls: list[str]

    def __init__(self, service: FakeYouTubeService) -> None:
        self.service = service
        self._services = {}
        self.credentials_calls = []
        self.youtube_calls = []

    def get_credentials(self, key: str) -> object:
        self.credentials_calls.append(key)
        return object()

    def get_youtube_service(self, key: str) -> object:
        cache_key = (key, "youtube")
        cached_service = self._services.get(cache_key)
        if cached_service is not None:
            return cached_service

        self.youtube_calls.append(key)
        self._services[cache_key] = self.service
        return self.service

    def get_analytics_service(self, key: str) -> object:
        _ = key
        return object()

    def get_reporting_service(self, key: str) -> object:
        _ = key
        return object()


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=3,
        initial_wait=0.001,
        max_wait=0.01,
        multiplier=1.0,
        jitter=False,
    )


def _configure(
    service: FakeYouTubeService | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeYouTubeService()
    manager = FakeAccountManager(fake_service)
    tracker = FakeQuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=lambda _account: None,
            retry_policy=_retry_policy(),
        )
    )
    return manager, tracker


def test_i18n_tools_cache_results_and_register_with_fastmcp() -> None:
    manager, _ = _configure()

    languages_first = i18n.youtube_i18nLanguages_list(account="primary", hl="en")
    languages_second = i18n.youtube_i18nLanguages_list(account="primary", hl="en")
    regions = i18n.youtube_i18nRegions_list(account="primary", hl="en")

    assert languages_first == {"items": [{"id": "lang-en"}]}
    assert languages_second == {"items": [{"id": "lang-en"}]}
    assert regions == {"items": [{"id": "region-us"}]}
    assert manager.credentials_calls == ["primary", "primary", "primary"]
    assert manager.youtube_calls == ["primary"]
    assert manager.service.i18n_languages_calls == 1
    assert manager.service.i18n_regions_calls == 1
    assert manager.service.i18n_languages_resource.list_calls == [{"part": "snippet", "hl": "en"}]
    assert manager.service.i18n_regions_resource.list_calls == [{"part": "snippet", "hl": "en"}]
    assert manager.service.i18n_languages_resource.request.execute_calls == 1
    assert manager.service.i18n_regions_resource.request.execute_calls == 1


@pytest.mark.asyncio
async def test_i18n_tools_are_registered_with_fastmcp() -> None:
    _ = _configure()

    assert list(inspect.signature(i18n.youtube_i18nLanguages_list).parameters) == [
        "account",
        "part",
        "hl",
        "ctx",
    ]
    assert list(inspect.signature(i18n.youtube_i18nRegions_list).parameters) == [
        "account",
        "part",
        "hl",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}

    assert "youtube_i18nLanguages_list" in registered
    assert "youtube_i18nRegions_list" in registered
