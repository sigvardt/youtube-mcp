# pyright: reportPrivateUsage=false

from __future__ import annotations

import pytest

from tests.live.conftest import SKIPPABLE_PERMISSION_REASONS
from tests.live.test_acid_mutating_jsigvardt import TEST_WATERMARK_PATH, _first_item, _response


def test_first_item_empty_collection_raises_pytest_skip() -> None:
    with pytest.raises(pytest.skip.Exception, match="no owned uploaded video available"):
        _ = _first_item({"items": []}, "owned uploaded video")


@pytest.mark.parametrize(
    "reason",
    [
        "channelNotActive",
        "liveStreamingNotEnabled",
        "subscriptionNotFound",
        "uploadRateLimitExceeded",
    ],
)
def test_mutating_response_skips_known_google_permission_reasons(reason: str) -> None:
    with pytest.raises(pytest.skip.Exception, match=reason):
        _ = _response({"error": {"reason": reason, "message": "legitimate Google behavior"}})


def test_skippable_permission_reasons_include_live_mutating_google_edges() -> None:
    assert {
        "channelNotActive",
        "liveStreamingNotEnabled",
        "subscriptionNotFound",
        "uploadRateLimitExceeded",
    } <= SKIPPABLE_PERMISSION_REASONS


def test_watermark_fixture_is_real_square_png() -> None:
    payload = TEST_WATERMARK_PATH.read_bytes()

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert int.from_bytes(payload[16:20], "big") == 150
    assert int.from_bytes(payload[20:24], "big") == 150
