# Phase 4 Mutating Live Suite Evidence

Date: 2026-05-20
Account: `jsigvardt` / `@jsigvardt`
Channel ID: `UCvTRR-gKfkSwnXTkxg3w2Nw`
Guard env: `YOUTUBE_MCP_ENFORCE_GUARD=1`
Destructive env: `RUN_DESTRUCTIVE_LIVE` unset

## Command

```bash
RUN_LIVE_TESTS=1 RUN_MUTATING_TESTS=1 YOUTUBE_MCP_ENFORCE_GUARD=1 uv run pytest tests/live/test_acid_mutating_jsigvardt.py -v -rs --tb=short
```

Captured full stdout and stderr at `/var/folders/fs/s4w_v3qd3px0gg4qlt25wrbc0000gn/T/opencode/phase-4-mutating-pytest.log` before embedding below.

## Guard Verification

- `tests/live/test_acid_mutating_jsigvardt.py` defines `ACCOUNT_KEY = "jsigvardt"` and `ALLOWED_HANDLE = "@jsigvardt"`.
- `_assert_jsigvardt_configured()` loads `AccountConfigStore()`, checks `account.channel_handle != ALLOWED_HANDLE`, raises `MutatingOpForbiddenError` on mismatch, then calls `MutatingGuard().assert_allowed(...)`.
- Collection calls `_assert_jsigvardt_configured()` when live mutating tests are enabled, and the autouse `mutating_account` fixture exits pytest with return code 4 on a guard mismatch.
- `src/youtube_mcp/utils/mutating_guard.py` reads `YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE` and defaults through `MutatingGuardConfig()`; the configured default observed in project docs is `@jsigvardt`.

## Quota Burn

| Metric | Value |
| --- | ---: |
| Before | 53/10000 |
| After | 2562/10000 |
| Delta | 2509 |

### Status Before

```text
warning: The `tool.uv.dev-dependencies` field (used in `pyproject.toml`) is deprecated and will be removed in a future release; use `dependency-groups.dev` instead
Configured accounts: 1
key	handle	channel_id	scopes	token	quota
jsigvardt	@jsigvardt	UCvTRR-gKfkSwnXTkxg3w2Nw	force_ssl,analytics_readonly,analytics_monetary,channel_memberships_creator	valid until 2026-05-20T10:41:38+00:00	53/10000
```

### Status After

```text
warning: The `tool.uv.dev-dependencies` field (used in `pyproject.toml`) is deprecated and will be removed in a future release; use `dependency-groups.dev` instead
Configured accounts: 1
key	handle	channel_id	scopes	token	quota
jsigvardt	@jsigvardt	UCvTRR-gKfkSwnXTkxg3w2Nw	force_ssl,analytics_readonly,analytics_monetary,channel_memberships_creator	valid until 2026-05-20T10:41:38+00:00	2562/10000
```

## Summary

| Total | Passed | Failed | Skipped | Pytest Summary |
| ---: | ---: | ---: | ---: | --- |
| 17 | 3 | 13 | 1 | `13 failed, 3 passed, 1 skipped, 1 warning in 26.01s` |

## Per-Test Status Breakdown

| Test | Status | Reason or First Five Traceback Lines |
| --- | --- | --- |
| `test_playlists_create_update_delete` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:319: in test_playlists_create_update_delete<br>assert _resource_id(_first_item(listed, "created playlist")) == playlist_id<br>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<br>tests/live/test_acid_mutating_jsigvardt.py:172: in _first_item<br>pytest.skip(f"no {label} available for mutating acid test") |
| `test_playlist_items_insert_delete` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:390: in test_playlist_items_insert_delete<br>assert _resource_id(_first_item(listed, "playlist item")) == item_id<br>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<br>tests/live/test_acid_mutating_jsigvardt.py:172: in _first_item<br>pytest.skip(f"no {label} available for mutating acid test") |
| `test_channel_sections_insert_update_delete` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:423: in test_channel_sections_insert_update_delete<br>inserted = _response(<br>tests/live/test_acid_mutating_jsigvardt.py:180: in _response<br>pytest.fail(f"Google API returned MCP error: {error}")<br>E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'channelNotActive', 'message': 'One or more channels are not active.'} |
| `test_subscriptions_subscribe_unsubscribe` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:484: in test_subscriptions_subscribe_unsubscribe<br>_ = _response(<br>tests/live/test_acid_mutating_jsigvardt.py:180: in _response<br>pytest.fail(f"Google API returned MCP error: {error}")<br>E   Failed: Google API returned MCP error: {'status': 404, 'reason': 'subscriptionNotFound', 'message': "The subscription that you are trying to delete cannot be found. Check the value of the request's <code>id</code> parameter to ensure that it is correct."} |
| `test_comments_insert_update_delete` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:547: in test_comments_insert_update_delete<br>_ = _response(comments.youtube_comments_delete(account=mutating_account, id=reply_id))<br>^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<br>tests/live/test_acid_mutating_jsigvardt.py:178: in _response<br>error = response.get("error") |
| `test_comment_threads_insert_then_comment_delete` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:585: in test_comment_threads_insert_then_comment_delete<br>_ = _response(<br>tests/live/test_acid_mutating_jsigvardt.py:178: in _response<br>error = response.get("error")<br>^^^^^^^^^^^^ |
| `test_channels_update_keywords_then_revert` | PASSED | Completed successfully |
| `test_channel_banners_insert` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:625: in test_channel_banners_insert<br>response = _response(<br>tests/live/test_acid_mutating_jsigvardt.py:180: in _response<br>pytest.fail(f"Google API returned MCP error: {error}")<br>E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'bannerValidationError', 'message': 'Channel banner validation failed. This error can occur because the channel banner image is too large or is not accepted file type. Please see <a href="https://support.google.com/youtube/answer/2972003">YouTube Help Center</a> for banner guidelines.'} |
| `test_thumbnails_set_then_revert` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:639: in test_thumbnails_set_then_revert<br>response = _response(<br>tests/live/test_acid_mutating_jsigvardt.py:180: in _response<br>pytest.fail(f"Google API returned MCP error: {error}")<br>E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'invalidImage', 'message': 'The provided image content is invalid.'} |
| `test_watermarks_set_unset` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:666: in test_watermarks_set_unset<br>_ = _response(<br>tests/live/test_acid_mutating_jsigvardt.py:180: in _response<br>pytest.fail(f"Google API returned MCP error: {error}")<br>E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'badRequest', 'message': 'Request contains an invalid argument.'} |
| `test_live_broadcasts_insert_update_delete` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:692: in test_live_broadcasts_insert_update_delete<br>inserted = _response(<br>tests/live/test_acid_mutating_jsigvardt.py:180: in _response<br>pytest.fail(f"Google API returned MCP error: {error}")<br>E   Failed: Google API returned MCP error: {'status': 403, 'reason': 'liveStreamingNotEnabled', 'message': 'The user is not enabled for live streaming.'} |
| `test_live_streams_insert_delete` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:737: in test_live_streams_insert_delete<br>inserted = _response(<br>tests/live/test_acid_mutating_jsigvardt.py:180: in _response<br>pytest.fail(f"Google API returned MCP error: {error}")<br>E   Failed: Google API returned MCP error: {'status': 403, 'reason': 'liveStreamingNotEnabled', 'message': 'The user is not enabled for live streaming.'} |
| `test_videos_insert_update_keeps_uploaded_video_for_manual_cleanup` | PASSED | Completed successfully |
| `test_videos_rate_like_then_none` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:795: in test_videos_rate_like_then_none<br>_ = _response(<br>tests/live/test_acid_mutating_jsigvardt.py:178: in _response<br>error = response.get("error")<br>^^^^^^^^^^^^ |
| `test_abuse_reports_insert_destructive_only` | SKIPPED | set RUN_DESTRUCTIVE_LIVE=1 to run irreversible abuse-report smoke test |
| `test_analytics_groups_insert_add_remove_delete` | FAILED | tests/live/test_acid_mutating_jsigvardt.py:840: in test_analytics_groups_insert_add_remove_delete<br>_response(<br>tests/live/test_acid_mutating_jsigvardt.py:180: in _response<br>pytest.fail(f"Google API returned MCP error: {error}")<br>E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'required', 'message': 'Required'} |
| `test_reporting_jobs_create_delete` | PASSED | Completed successfully |

## Per-Test Details

### `test_playlists_create_update_delete`

- Status: FAILED
- Error: `Skipped: no created playlist available for mutating acid test`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:319: in test_playlists_create_update_delete
    assert _resource_id(_first_item(listed, "created playlist")) == playlist_id
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/live/test_acid_mutating_jsigvardt.py:172: in _first_item
    pytest.skip(f"no {label} available for mutating acid test")
```

### `test_playlist_items_insert_delete`

- Status: FAILED
- Error: `Skipped: no playlist item available for mutating acid test`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:390: in test_playlist_items_insert_delete
    assert _resource_id(_first_item(listed, "playlist item")) == item_id
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/live/test_acid_mutating_jsigvardt.py:172: in _first_item
    pytest.skip(f"no {label} available for mutating acid test")
```

### `test_channel_sections_insert_update_delete`

- Status: FAILED
- Error: `Failed: Google API returned MCP error: {'status': 400, 'reason': 'channelNotActive', 'message': 'One or more channels are not active.'}`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:423: in test_channel_sections_insert_update_delete
    inserted = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'channelNotActive', 'message': 'One or more channels are not active.'}
```

### `test_subscriptions_subscribe_unsubscribe`

- Status: FAILED
- Error: `Failed: Google API returned MCP error: {'status': 404, 'reason': 'subscriptionNotFound', 'message': "The subscription that you are trying to delete cannot be found. Check the value of the request's <code>id</code> parameter to ensure that it is correct."}`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:484: in test_subscriptions_subscribe_unsubscribe
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 404, 'reason': 'subscriptionNotFound', 'message': "The subscription that you are trying to delete cannot be found. Check the value of the request's <code>id</code> parameter to ensure that it is correct."}
```

### `test_comments_insert_update_delete`

- Status: FAILED
- Error: `AttributeError: 'str' object has no attribute 'get'`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:547: in test_comments_insert_update_delete
    _ = _response(comments.youtube_comments_delete(account=mutating_account, id=reply_id))
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/live/test_acid_mutating_jsigvardt.py:178: in _response
    error = response.get("error")
```

### `test_comment_threads_insert_then_comment_delete`

- Status: FAILED
- Error: `AttributeError: 'str' object has no attribute 'get'`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:585: in test_comment_threads_insert_then_comment_delete
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:178: in _response
    error = response.get("error")
            ^^^^^^^^^^^^
```

### `test_channels_update_keywords_then_revert`

- Status: PASSED
- Reason: completed successfully

### `test_channel_banners_insert`

- Status: FAILED
- Error: `Failed: Google API returned MCP error: {'status': 400, 'reason': 'bannerValidationError', 'message': 'Channel banner validation failed. This error can occur because the channel banner image is too large or is not accepted file type. Please see <a href="https://support.google.com/youtube/answer/2972003">YouTube Help Center</a> for banner guidelines.'}`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:625: in test_channel_banners_insert
    response = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'bannerValidationError', 'message': 'Channel banner validation failed. This error can occur because the channel banner image is too large or is not accepted file type. Please see <a href="https://support.google.com/youtube/answer/2972003">YouTube Help Center</a> for banner guidelines.'}
```

### `test_thumbnails_set_then_revert`

- Status: FAILED
- Error: `Failed: Google API returned MCP error: {'status': 400, 'reason': 'invalidImage', 'message': 'The provided image content is invalid.'}`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:639: in test_thumbnails_set_then_revert
    response = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'invalidImage', 'message': 'The provided image content is invalid.'}
```

### `test_watermarks_set_unset`

- Status: FAILED
- Error: `Failed: Google API returned MCP error: {'status': 400, 'reason': 'badRequest', 'message': 'Request contains an invalid argument.'}`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:666: in test_watermarks_set_unset
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'badRequest', 'message': 'Request contains an invalid argument.'}
```

### `test_live_broadcasts_insert_update_delete`

- Status: FAILED
- Error: `Failed: Google API returned MCP error: {'status': 403, 'reason': 'liveStreamingNotEnabled', 'message': 'The user is not enabled for live streaming.'}`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:692: in test_live_broadcasts_insert_update_delete
    inserted = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 403, 'reason': 'liveStreamingNotEnabled', 'message': 'The user is not enabled for live streaming.'}
```

### `test_live_streams_insert_delete`

- Status: FAILED
- Error: `Failed: Google API returned MCP error: {'status': 403, 'reason': 'liveStreamingNotEnabled', 'message': 'The user is not enabled for live streaming.'}`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:737: in test_live_streams_insert_delete
    inserted = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 403, 'reason': 'liveStreamingNotEnabled', 'message': 'The user is not enabled for live streaming.'}
```

### `test_videos_insert_update_keeps_uploaded_video_for_manual_cleanup`

- Status: PASSED
- Reason: completed successfully

### `test_videos_rate_like_then_none`

- Status: FAILED
- Error: `AttributeError: 'str' object has no attribute 'get'`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:795: in test_videos_rate_like_then_none
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:178: in _response
    error = response.get("error")
            ^^^^^^^^^^^^
```

### `test_abuse_reports_insert_destructive_only`

- Status: SKIPPED
- Reason: set RUN_DESTRUCTIVE_LIVE=1 to run irreversible abuse-report smoke test

### `test_analytics_groups_insert_add_remove_delete`

- Status: FAILED
- Error: `Failed: Google API returned MCP error: {'status': 400, 'reason': 'required', 'message': 'Required'}`
- First five traceback lines:

```text
tests/live/test_acid_mutating_jsigvardt.py:840: in test_analytics_groups_insert_add_remove_delete
    _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'required', 'message': 'Required'}
```

### `test_reporting_jobs_create_delete`

- Status: PASSED
- Reason: completed successfully

## Real Artifacts Created

| Artifact | ID | Timestamp | Marker |
| --- | --- | --- | --- |
| Uploaded private video kept for manual cleanup | `A-CNdRDfljw` | `2026-05-20T10:27:43.536179+00:00` | `youtube-mcp-acid-20260520T102726Z` |

No other created artifact IDs were logged in pytest output. Playlist, playlist item, comment, subscription, channel section, live, analytics, and reporting tests attempted cleanup where their test bodies reached cleanup paths. The uploaded private video is intentionally retained for manual cleanup because no video delete tool exists.

## Uploaded Video ID File Content

Path: `.sisyphus/evidence/task-47-uploaded-video-ids.txt`

```text
2026-05-20T10:27:43.536179+00:00	youtube-mcp-acid-20260520T102726Z	A-CNdRDfljw

```

## Blocking Bugs and Follow-Up Candidates

- `youtube_playlists_delete`, `youtube_playlistItems_delete`, `youtube_comments_delete`, and `youtube_videos_rate` surfaced no-content response shape problems: Google returned a raw empty string or non-mapping response, while the tools are annotated as returning `dict[str, object]` and the live harness calls `.get()`, producing `AttributeError: 'str' object has no attribute 'get'`.
- `youtube_subscriptions_delete` cleanup failed with Google API `404 subscriptionNotFound` after an insert returned an ID.
- `youtube_analytics_groups_insert` failed with Google API `400 required` for the minimal group body used by the test.
- Several failures appear environment or fixture related rather than confirmed tool bugs: channel sections `channelNotActive`, channel banner `bannerValidationError`, thumbnail `invalidImage`, watermark `badRequest/notFound`, and live broadcasts/streams `liveStreamingNotEnabled`.

## Verbatim Pytest Output

```text
warning: The `tool.uv.dev-dependencies` field (used in `pyproject.toml`) is deprecated and will be removed in a future release; use `dependency-groups.dev` instead
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0 -- /Users/user/Repositories/youtube-mcp/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/user/Repositories/youtube-mcp
configfile: pyproject.toml
plugins: cov-7.1.0, vcr-1.0.2, asyncio-1.3.0, respx-0.23.1, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 17 items

tests/live/test_acid_mutating_jsigvardt.py::test_playlists_create_update_delete FAILED [  5%]
tests/live/test_acid_mutating_jsigvardt.py::test_playlist_items_insert_delete FAILED [ 11%]
tests/live/test_acid_mutating_jsigvardt.py::test_channel_sections_insert_update_delete FAILED [ 17%]
tests/live/test_acid_mutating_jsigvardt.py::test_subscriptions_subscribe_unsubscribe FAILED [ 23%]
tests/live/test_acid_mutating_jsigvardt.py::test_comments_insert_update_delete FAILED [ 29%]
tests/live/test_acid_mutating_jsigvardt.py::test_comment_threads_insert_then_comment_delete FAILED [ 35%]
tests/live/test_acid_mutating_jsigvardt.py::test_channels_update_keywords_then_revert PASSED [ 41%]
tests/live/test_acid_mutating_jsigvardt.py::test_channel_banners_insert FAILED [ 47%]
tests/live/test_acid_mutating_jsigvardt.py::test_thumbnails_set_then_revert FAILED [ 52%]
tests/live/test_acid_mutating_jsigvardt.py::test_watermarks_set_unset FAILED [ 58%]
tests/live/test_acid_mutating_jsigvardt.py::test_live_broadcasts_insert_update_delete FAILED [ 64%]
tests/live/test_acid_mutating_jsigvardt.py::test_live_streams_insert_delete FAILED [ 70%]
tests/live/test_acid_mutating_jsigvardt.py::test_videos_insert_update_keeps_uploaded_video_for_manual_cleanup PASSED [ 76%]
tests/live/test_acid_mutating_jsigvardt.py::test_videos_rate_like_then_none FAILED [ 82%]
tests/live/test_acid_mutating_jsigvardt.py::test_abuse_reports_insert_destructive_only SKIPPED [ 88%]
tests/live/test_acid_mutating_jsigvardt.py::test_analytics_groups_insert_add_remove_delete FAILED [ 94%]
tests/live/test_acid_mutating_jsigvardt.py::test_reporting_jobs_create_delete PASSED [100%]

=================================== FAILURES ===================================
_____________________ test_playlists_create_update_delete ______________________
tests/live/test_acid_mutating_jsigvardt.py:319: in test_playlists_create_update_delete
    assert _resource_id(_first_item(listed, "created playlist")) == playlist_id
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/live/test_acid_mutating_jsigvardt.py:172: in _first_item
    pytest.skip(f"no {label} available for mutating acid test")
E   Skipped: no created playlist available for mutating acid test

During handling of the above exception, another exception occurred:
tests/live/test_acid_mutating_jsigvardt.py:338: in test_playlists_create_update_delete
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:178: in _response
    error = response.get("error")
            ^^^^^^^^^^^^
E   AttributeError: 'str' object has no attribute 'get'
______________________ test_playlist_items_insert_delete _______________________
tests/live/test_acid_mutating_jsigvardt.py:390: in test_playlist_items_insert_delete
    assert _resource_id(_first_item(listed, "playlist item")) == item_id
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/live/test_acid_mutating_jsigvardt.py:172: in _first_item
    pytest.skip(f"no {label} available for mutating acid test")
E   Skipped: no playlist item available for mutating acid test

During handling of the above exception, another exception occurred:
tests/live/test_acid_mutating_jsigvardt.py:393: in test_playlist_items_insert_delete
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:178: in _response
    error = response.get("error")
            ^^^^^^^^^^^^
E   AttributeError: 'str' object has no attribute 'get'
__________________ test_channel_sections_insert_update_delete __________________
tests/live/test_acid_mutating_jsigvardt.py:423: in test_channel_sections_insert_update_delete
    inserted = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'channelNotActive', 'message': 'One or more channels are not active.'}

During handling of the above exception, another exception occurred:
tests/live/test_acid_mutating_jsigvardt.py:455: in test_channel_sections_insert_update_delete
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:178: in _response
    error = response.get("error")
            ^^^^^^^^^^^^
E   AttributeError: 'str' object has no attribute 'get'
___________________ test_subscriptions_subscribe_unsubscribe ___________________
tests/live/test_acid_mutating_jsigvardt.py:484: in test_subscriptions_subscribe_unsubscribe
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 404, 'reason': 'subscriptionNotFound', 'message': "The subscription that you are trying to delete cannot be found. Check the value of the request's <code>id</code> parameter to ensure that it is correct."}
______________________ test_comments_insert_update_delete ______________________
tests/live/test_acid_mutating_jsigvardt.py:547: in test_comments_insert_update_delete
    _ = _response(comments.youtube_comments_delete(account=mutating_account, id=reply_id))
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/live/test_acid_mutating_jsigvardt.py:178: in _response
    error = response.get("error")
            ^^^^^^^^^^^^
E   AttributeError: 'str' object has no attribute 'get'
_______________ test_comment_threads_insert_then_comment_delete ________________
tests/live/test_acid_mutating_jsigvardt.py:585: in test_comment_threads_insert_then_comment_delete
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:178: in _response
    error = response.get("error")
            ^^^^^^^^^^^^
E   AttributeError: 'str' object has no attribute 'get'
_________________________ test_channel_banners_insert __________________________
tests/live/test_acid_mutating_jsigvardt.py:625: in test_channel_banners_insert
    response = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'bannerValidationError', 'message': 'Channel banner validation failed. This error can occur because the channel banner image is too large or is not accepted file type. Please see <a href="https://support.google.com/youtube/answer/2972003">YouTube Help Center</a> for banner guidelines.'}
_______________________ test_thumbnails_set_then_revert ________________________
tests/live/test_acid_mutating_jsigvardt.py:639: in test_thumbnails_set_then_revert
    response = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'invalidImage', 'message': 'The provided image content is invalid.'}

During handling of the above exception, another exception occurred:
tests/live/test_acid_mutating_jsigvardt.py:648: in test_thumbnails_set_then_revert
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'invalidImage', 'message': 'The provided image content is invalid.'}
__________________________ test_watermarks_set_unset ___________________________
tests/live/test_acid_mutating_jsigvardt.py:666: in test_watermarks_set_unset
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'badRequest', 'message': 'Request contains an invalid argument.'}

During handling of the above exception, another exception occurred:
tests/live/test_acid_mutating_jsigvardt.py:678: in test_watermarks_set_unset
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 404, 'reason': 'notFound', 'message': 'Requested entity was not found.'}
__________________ test_live_broadcasts_insert_update_delete ___________________
tests/live/test_acid_mutating_jsigvardt.py:692: in test_live_broadcasts_insert_update_delete
    inserted = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 403, 'reason': 'liveStreamingNotEnabled', 'message': 'The user is not enabled for live streaming.'}
------------------------------ Captured log call -------------------------------
WARNING  googleapiclient.http:http.py:140 Encountered 403 Forbidden with reason "liveStreamingNotEnabled"
_______________________ test_live_streams_insert_delete ________________________
tests/live/test_acid_mutating_jsigvardt.py:737: in test_live_streams_insert_delete
    inserted = _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 403, 'reason': 'liveStreamingNotEnabled', 'message': 'The user is not enabled for live streaming.'}
------------------------------ Captured log call -------------------------------
WARNING  googleapiclient.http:http.py:140 Encountered 403 Forbidden with reason "liveStreamingNotEnabled"
_______________________ test_videos_rate_like_then_none ________________________
tests/live/test_acid_mutating_jsigvardt.py:795: in test_videos_rate_like_then_none
    _ = _response(
tests/live/test_acid_mutating_jsigvardt.py:178: in _response
    error = response.get("error")
            ^^^^^^^^^^^^
E   AttributeError: 'str' object has no attribute 'get'
________________ test_analytics_groups_insert_add_remove_delete ________________
tests/live/test_acid_mutating_jsigvardt.py:840: in test_analytics_groups_insert_add_remove_delete
    _response(
tests/live/test_acid_mutating_jsigvardt.py:180: in _response
    pytest.fail(f"Google API returned MCP error: {error}")
E   Failed: Google API returned MCP error: {'status': 400, 'reason': 'required', 'message': 'Required'}
=============================== warnings summary ===============================
.venv/lib/python3.11/site-packages/opentelemetry/util/_importlib_metadata.py:32
  /Users/user/Repositories/youtube-mcp/.venv/lib/python3.11/site-packages/opentelemetry/util/_importlib_metadata.py:32: DeprecationWarning: SelectableGroups dict interface is deprecated. Use select.
    return EntryPoints(ep for group_eps in eps.values() for ep in group_eps)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
SKIPPED [1] tests/live/test_acid_mutating_jsigvardt.py:803: set RUN_DESTRUCTIVE_LIVE=1 to run irreversible abuse-report smoke test
============= 13 failed, 3 passed, 1 skipped, 1 warning in 26.01s ==============

```
