"""Tests for the YouTube captions tools."""

# pyright: reportMissingTypeStubs=false, reportRedeclaration=false, reportUnannotatedClassAttribute=false
# pyright: reportImplicitOverride=false, reportMissingImports=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import BinaryIO, ClassVar, cast
from unittest.mock import Mock

import pytest
from fastmcp import Context

import youtube_mcp.tools.captions as captions
from youtube_mcp.server import mcp
from youtube_mcp.tools._framework import FrameworkContext, configure_framework
from youtube_mcp.types import RetryPolicy, YouTubeScope


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


class FakeCaptionsRequest:
    response: dict[str, object]
    execute_calls: int

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.execute_calls = 0

    def execute(self) -> dict[str, object]:
        self.execute_calls += 1
        return self.response


class FakeDownloadRequest:
    pass


class FakeCaptionsResource:
    list_request: FakeCaptionsRequest
    insert_request: FakeCaptionsRequest
    update_request: FakeCaptionsRequest
    delete_request: FakeCaptionsRequest
    download_request: FakeDownloadRequest
    list_calls: list[dict[str, object]]
    insert_calls: list[dict[str, object]]
    update_calls: list[dict[str, object]]
    delete_calls: list[dict[str, object]]
    download_media_calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.list_request = FakeCaptionsRequest({"items": [{"id": "caption-list-1"}]})
        self.insert_request = FakeCaptionsRequest({"id": "caption-insert-1"})
        self.update_request = FakeCaptionsRequest({"id": "caption-update-1"})
        self.delete_request = FakeCaptionsRequest({"id": "caption-delete-1"})
        self.download_request = FakeDownloadRequest()
        self.list_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []
        self.download_media_calls = []

    def list(self, **kwargs: object) -> FakeCaptionsRequest:
        self.list_calls.append(dict(kwargs))
        return self.list_request

    def insert(self, **kwargs: object) -> FakeCaptionsRequest:
        self.insert_calls.append(dict(kwargs))
        return self.insert_request

    def update(self, **kwargs: object) -> FakeCaptionsRequest:
        self.update_calls.append(dict(kwargs))
        return self.update_request

    def delete(self, **kwargs: object) -> FakeCaptionsRequest:
        self.delete_calls.append(dict(kwargs))
        return self.delete_request

    def download_media(self, **kwargs: object) -> FakeDownloadRequest:
        self.download_media_calls.append(dict(kwargs))
        return self.download_request


class FakeYouTubeService:
    captions_resource: FakeCaptionsResource
    captions_calls: int

    def __init__(self) -> None:
        self.captions_resource = FakeCaptionsResource()
        self.captions_calls = 0

    def captions(self) -> FakeCaptionsResource:
        self.captions_calls += 1
        return self.captions_resource


class FakeAccountManager:
    service: FakeYouTubeService
    _services: dict[tuple[str, str], object]
    credentials_calls: list[str]
    youtube_calls: list[str]
    analytics_calls: list[str]
    reporting_calls: list[str]

    def __init__(self, service: FakeYouTubeService) -> None:
        self.service = service
        self._services = {}
        self.credentials_calls = []
        self.youtube_calls = []
        self.analytics_calls = []
        self.reporting_calls = []

    def get_credentials(self, key: str) -> object:
        self.credentials_calls.append(key)
        return object()

    def get_youtube_service(self, key: str) -> FakeYouTubeService:
        self.youtube_calls.append(key)
        self._services[(key, "youtube")] = self.service
        return self.service

    def get_analytics_service(self, key: str) -> object:
        self.analytics_calls.append(key)
        return object()

    def get_reporting_service(self, key: str) -> object:
        self.reporting_calls.append(key)
        return object()


class FakeMediaFileUpload:
    calls: ClassVar[list[dict[str, object]]] = []

    def __init__(self, filename: str, resumable: bool = False) -> None:
        self.filename = filename
        self.resumable = resumable
        self.calls.append({"filename": filename, "resumable": resumable})


class FakeDownloadStatus:
    value: float

    def __init__(self, value: float) -> None:
        self.value = value

    def progress(self) -> float:
        return self.value


class FakeMediaIoBaseDownload:
    instances: ClassVar[list[FakeMediaIoBaseDownload]] = []

    def __init__(self, fd: BinaryIO, request: FakeDownloadRequest) -> None:
        self.fd = fd
        self.request = request
        self.next_chunk_calls = 0
        self.instances.append(self)

    def next_chunk(self) -> tuple[FakeDownloadStatus, bool]:
        self.next_chunk_calls += 1
        if self.next_chunk_calls == 1:
            _ = self.fd.write(b"caption ")
            return FakeDownloadStatus(0.5), False

        _ = self.fd.write(b"bytes")
        return FakeDownloadStatus(1.0), True


def _retry_policy(max_attempts: int = 3) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=max_attempts,
        initial_wait=0.001,
        max_wait=0.01,
        multiplier=1.0,
        jitter=False,
    )


def _configure(
    *,
    service: FakeYouTubeService | None = None,
    mutating_guard: Callable[[str], None] | None = None,
) -> tuple[FakeAccountManager, FakeQuotaTracker]:
    fake_service = service or FakeYouTubeService()
    manager = FakeAccountManager(fake_service)
    tracker = FakeQuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=mutating_guard or (lambda _account: None),
            retry_policy=_retry_policy(),
        )
    )
    return manager, tracker


def test_list_calls_captions_list_with_mocked_discovery_client() -> None:
    manager, tracker = _configure()

    result = captions.youtube_captions_list(
        account="primary",
        part="snippet",
        video_id="video-123",
        id="caption-456",
        on_behalf_of_content_owner="owner-1",
        on_behalf_of="channel-1",
    )

    assert result == {"items": [{"id": "caption-list-1"}]}
    assert manager.credentials_calls == ["primary"]
    assert manager.youtube_calls == ["primary"]
    assert manager.analytics_calls == []
    assert manager.reporting_calls == []
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert manager.service.captions_calls == 1
    assert manager.service.captions_resource.list_calls == [
        {
            "part": "snippet",
            "videoId": "video-123",
            "id": "caption-456",
            "onBehalfOfContentOwner": "owner-1",
            "onBehalfOf": "channel-1",
        }
    ]
    assert manager.service.captions_resource.list_request.execute_calls == 1


def test_insert_uses_media_upload_and_mutating_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class EventAccountManager(FakeAccountManager):
        def get_credentials(self, key: str) -> object:
            events.append(f"credentials:{key}")
            return super().get_credentials(key)

        def get_youtube_service(self, key: str) -> FakeYouTubeService:
            events.append(f"service:{key}")
            return super().get_youtube_service(key)

    def guard(account: str) -> None:
        events.append(f"guard:{account}")

    FakeMediaFileUpload.calls = []
    monkeypatch.setattr(captions, "MediaFileUpload", FakeMediaFileUpload)

    fake_service = FakeYouTubeService()
    manager = EventAccountManager(fake_service)
    tracker = FakeQuotaTracker()
    configure_framework(
        FrameworkContext(
            account_manager=manager,
            quota_tracker=tracker,
            mutating_guard=guard,
            retry_policy=_retry_policy(),
        )
    )
    body = {"snippet": {"videoId": "video-123", "language": "en", "name": "English"}}

    result = captions.youtube_captions_insert(
        account="primary",
        part="snippet",
        caption_body=body,
        caption_file_path="/tmp/caption.srt",
        sync=True,
        on_behalf_of="channel-1",
        on_behalf_of_content_owner="owner-1",
    )

    assert result == {"id": "caption-insert-1"}
    assert events == ["credentials:primary", "guard:primary", "service:primary"]
    assert tracker.preflight_calls == [("primary", 400)]
    assert tracker.record_calls == [("primary", 400)]
    assert FakeMediaFileUpload.calls == [{"filename": "/tmp/caption.srt", "resumable": False}]
    media_body = fake_service.captions_resource.insert_calls[0]["media_body"]
    assert isinstance(media_body, FakeMediaFileUpload)
    assert fake_service.captions_resource.insert_calls == [
        {
            "part": "snippet",
            "body": body,
            "media_body": media_body,
            "sync": True,
            "onBehalfOf": "channel-1",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert fake_service.captions_resource.insert_request.execute_calls == 1


def test_update_adds_caption_id_and_optionally_uses_media_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeMediaFileUpload.calls = []
    monkeypatch.setattr(captions, "MediaFileUpload", FakeMediaFileUpload)
    manager, tracker = _configure(mutating_guard=lambda _account: None)
    body = {"snippet": {"name": "Updated English"}}

    result = captions.youtube_captions_update(
        account="primary",
        part="snippet",
        caption_id="caption-456",
        caption_body=body,
        caption_file_path="/tmp/updated.srt",
        sync=False,
        on_behalf_of="channel-1",
        on_behalf_of_content_owner="owner-1",
    )

    assert result == {"id": "caption-update-1"}
    assert tracker.preflight_calls == [("primary", 450)]
    assert tracker.record_calls == [("primary", 450)]
    assert FakeMediaFileUpload.calls == [{"filename": "/tmp/updated.srt", "resumable": False}]
    media_body = manager.service.captions_resource.update_calls[0]["media_body"]
    assert isinstance(media_body, FakeMediaFileUpload)
    assert manager.service.captions_resource.update_calls == [
        {
            "part": "snippet",
            "body": {"snippet": {"name": "Updated English"}, "id": "caption-456"},
            "media_body": media_body,
            "sync": False,
            "onBehalfOf": "channel-1",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert body == {"snippet": {"name": "Updated English"}}


def test_update_allows_metadata_only_without_media_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeMediaFileUpload.calls = []
    monkeypatch.setattr(captions, "MediaFileUpload", FakeMediaFileUpload)
    manager, _tracker = _configure(mutating_guard=lambda _account: None)

    result = captions.youtube_captions_update(
        account="primary",
        part="snippet",
        caption_id="caption-456",
    )

    assert result == {"id": "caption-update-1"}
    assert FakeMediaFileUpload.calls == []
    assert manager.service.captions_resource.update_calls == [
        {
            "part": "snippet",
            "body": {"id": "caption-456"},
            "media_body": None,
            "sync": None,
            "onBehalfOf": None,
            "onBehalfOfContentOwner": None,
        }
    ]


def test_download_writes_binary_to_output_path_and_returns_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    FakeMediaIoBaseDownload.instances = []
    monkeypatch.setattr(captions, "MediaIoBaseDownload", FakeMediaIoBaseDownload)
    manager, tracker = _configure()
    output_path = tmp_path / "caption.srt"
    report_progress = Mock()
    ctx = cast(Context, cast(object, SimpleNamespace(report_progress=report_progress)))

    result = captions.youtube_captions_download(
        account="primary",
        caption_id="caption-456",
        tfmt="srt",
        tlang="en",
        on_behalf_of="channel-1",
        on_behalf_of_content_owner="owner-1",
        output_path=str(output_path),
        ctx=ctx,
    )

    assert result == str(output_path)
    assert output_path.read_bytes() == b"caption bytes"
    assert tracker.preflight_calls == [("primary", 200)]
    assert tracker.record_calls == [("primary", 200)]
    assert manager.service.captions_resource.download_media_calls == [
        {
            "id": "caption-456",
            "tfmt": "srt",
            "tlang": "en",
            "onBehalfOf": "channel-1",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert (
        FakeMediaIoBaseDownload.instances[0].request
        is manager.service.captions_resource.download_request
    )
    assert FakeMediaIoBaseDownload.instances[0].next_chunk_calls == 2
    assert report_progress.call_args_list[0].kwargs == {"progress": 0.5, "total": 1.0}
    assert report_progress.call_args_list[1].kwargs == {"progress": 1.0, "total": 1.0}


def test_delete_calls_captions_delete_and_mutating_guard() -> None:
    events: list[str] = []

    def guard(account: str) -> None:
        events.append(f"guard:{account}")

    manager, tracker = _configure(mutating_guard=guard)

    result = captions.youtube_captions_delete(
        account="primary",
        caption_id="caption-456",
        on_behalf_of="channel-1",
        on_behalf_of_content_owner="owner-1",
    )

    assert result == {"id": "caption-delete-1"}
    assert events == ["guard:primary"]
    assert tracker.preflight_calls == [("primary", 50)]
    assert tracker.record_calls == [("primary", 50)]
    assert manager.service.captions_resource.delete_calls == [
        {
            "id": "caption-456",
            "onBehalfOf": "channel-1",
            "onBehalfOfContentOwner": "owner-1",
        }
    ]
    assert manager.service.captions_resource.delete_request.execute_calls == 1


@pytest.mark.asyncio
async def test_registered() -> None:
    _ = _configure()

    assert list(inspect.signature(captions.youtube_captions_list).parameters) == [
        "account",
        "part",
        "video_id",
        "id",
        "on_behalf_of_content_owner",
        "on_behalf_of",
        "ctx",
    ]
    assert list(inspect.signature(captions.youtube_captions_download).parameters) == [
        "account",
        "caption_id",
        "tfmt",
        "tlang",
        "on_behalf_of",
        "on_behalf_of_content_owner",
        "output_path",
        "ctx",
    ]

    tools = await mcp.list_tools()
    registered = {tool.name: tool for tool in tools}
    expected_names = {
        "youtube_captions_list",
        "youtube_captions_insert",
        "youtube_captions_update",
        "youtube_captions_download",
        "youtube_captions_delete",
    }

    assert expected_names <= registered.keys()
    assert registered["youtube_captions_list"].tags == set()
    assert registered["youtube_captions_download"].tags == set()
    assert registered["youtube_captions_insert"].tags == {"mutating"}
    assert registered["youtube_captions_update"].tags == {"mutating"}
    assert registered["youtube_captions_delete"].tags == {"mutating"}
    assert registered["youtube_captions_list"].parameters["required"] == [
        "account",
        "part",
        "video_id",
    ]
    assert "ctx" not in registered["youtube_captions_download"].parameters["properties"]
    assert "output_path" in registered["youtube_captions_download"].parameters["required"]
    insert_meta = registered["youtube_captions_insert"].meta
    download_meta = registered["youtube_captions_download"].meta
    assert insert_meta is not None
    assert download_meta is not None
    assert insert_meta["scopes"] == [YouTubeScope.FORCE_SSL.value]
    assert download_meta["cost"] == 200
