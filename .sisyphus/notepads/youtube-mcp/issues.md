# issues.md (youtube-mcp)

## [2026-05-19] Open non-blocking items

- **uv deprecation**: `pyproject.toml` uses `[tool.uv]` `dev-dependencies` which uv warns is deprecated. Migrate to `[dependency-groups]` `dev = [...]` in a later cleanup pass. Does NOT block T2-T48.
- **Evidence files**: T1 subagent created none of the `.sisyphus/evidence/task-1-*.txt` files the plan asked for. All future subagents MUST write evidence files exactly as named in the plan's "Evidence to Capture" subsection.
- **Playwright noise**: `.playwright-mcp/` contains a large pile of unrelated console/page snapshots from previous sessions. Not relevant to T1; leave alone unless plan touches them.

## Conventions for subagents

- Always use `uv run <cmd>`; never call `python` / `pip` directly.
- Always write evidence files to `.sisyphus/evidence/task-N-<name>.txt`.
- Never commit secrets — `.gitignore` already excludes `.env`, tokens, and `.sisyphus/evidence/`.
- Never introduce ANY reference to `videos.delete` or `videos_delete` in src/ or tests/.

## [2026-05-19] Task: T9

- `uv run mypy --strict src/youtube_mcp/utils/` still fails on pre-existing, untouched files: `src/youtube_mcp/utils/cache.py` (`no-any-return`) and `src/youtube_mcp/utils/retry.py` (`import-untyped`, `redundant-cast`).
- I did not modify those files because they belong to other tasks in the plan, so the new pagination module itself is strict-clean, but the package-wide utils mypy target is not yet green.

## [2026-05-20] BLOCKER: live-test phases 2-8 require OAuth bootstrap (USER ACTION)

After all 48 implementation tasks and F1-F4 wave APPROVE, user pivoted to live testing against real Google APIs scoped to @jsigvardt only. Drafted a 9-phase live test plan (Phases 0-8). Phase 0 (state discovery) confirmed: zero configured accounts, empty macOS Keychain for service `youtube-mcp`, no `client_secret.json` on disk anywhere in the repo, no `YOUTUBE_MCP_*` env overrides.

**Phase 1 is a true external blocker**:
- Requires a GCP OAuth 2.0 **Desktop** client credentials JSON (operator must create or locate one).
- Requires browser consent flow with the @jsigvardt-owning Google account (operator's hands on browser).

Neither is achievable from inside the agent session. The auto-continue loop fired twice on this blocker; per `/Users/user/.config/opencode/AGENTS.md` "stuck continuation loop" protocol, deregistering by:

1. Writing `.sisyphus/evidence/operator-unblock-checklist.md` — copy-paste-runnable walkthrough covering GCP console steps, `uv run youtube-mcp auth add jsigvardt --client-creds=...`, verification commands, and the Phase 2-8 sequence the agent will fire after bootstrap lands.
2. Marking all 8 remaining live-test todos as `cancelled` with `HANDOFF:` prefix and a one-line summary of the unblocker.
3. Holding F1-F4 plan checkboxes at `- [x]` (already correctly ticked from prior round — reviewers APPROVED).

**To unblock**: follow `.sisyphus/evidence/operator-unblock-checklist.md` Steps 1-2. Then say "done" (or "go") in chat. Agent will re-read state, mark Phase 1 done, and execute Phases 2-8 autonomously.

**Sequence the agent will execute after unblock** (in order):
1. Phase 2: `uv run youtube-mcp doctor` — auth smoke probe (1 quota unit).
2. Phase 3: `RUN_LIVE_TESTS=1 uv run pytest tests/live -k readonly -v` — read-only suite across 3 APIs (~50-200 units).
3. Phase 5: Python REPL probes of ~10 read tools (~50 units).
4. Phase 7: stdio MCP server `tools/list` handshake (no API calls).
5. Phase 6: re-run Phase 5 with quota-tracker brackets to validate declared `cost=N` numbers.
6. Phase 4: `RUN_LIVE_TESTS=1 RUN_MUTATING_TESTS=1 YOUTUBE_MCP_ENFORCE_GUARD=1 uv run pytest tests/live -k mutating -v` — destructive on @jsigvardt only, guard-protected at fixture time (~5000-10000 units; uploads test videos that need manual cleanup from YouTube Studio).
7. Phase 8: read `.sisyphus/evidence/task-47-uploaded-video-ids.txt`, print cleanup list.

**Mutating-guard verification**: env `YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE` defaults to `@jsigvardt` if unset; `YOUTUBE_MCP_ENFORCE_GUARD=1` activates pre-call channel-handle check. `tests/live/test_acid_mutating_jsigvardt.py` has a module-level fixture that aborts the whole file if `account.channel_handle != "@jsigvardt"`. abuseReports.insert is additionally gated by `RUN_DESTRUCTIVE_LIVE=1` (operator must opt in separately).

Operator may also tell the agent "skip mutating" to run only Phases 2,3,5,6,7,8 — defensible if you want read-path validation only or to save quota.

## [2026-05-20] BLOCKER: live auth probe returns insufficientPermissions

- After normalizing the live scope comparison, `test_tests_insert_auth_probe[jsigvardt]` still skips because `youtube_tests_insert(...)` returns `{'error': {'status': 403, 'reason': 'insufficientPermissions', 'message': 'Request had insufficient authentication scopes.'}}`.
- The configured account and token both carry `youtube.force-ssl`, `yt-analytics.readonly`, `yt-analytics-monetary.readonly`, and `youtube.channel-memberships.creator`, but not `youtube.readonly`, so the probe cannot reach the asserted `id` payload without a fresh OAuth grant.
- Unblock path: re-auth the `jsigvardt` account with the scope required by `youtube.tests.insert`, then rerun `RUN_LIVE_TESTS=1 uv run pytest tests/live/test_acid_read_all_accounts.py::test_tests_insert_auth_probe -v`.

## [2026-05-20] Phase 6 quota-validation coverage gap

- `.sisyphus/evidence/phase-5-repl-probes.md` was not present when Phase 6 ran, so only one fallback live read-only probe was performed under the 50-unit additional burn cap. No mismatch was found for the validated tool. Remaining high-cost read-only tools need Phase 5 evidence or a separate quota window before they can be marked MATCH/MISMATCH from live deltas.

## [2026-05-20] Phase 5 unexpected probe result

- `youtube_search_list(account="jsigvardt", part="snippet", q="cats", max_results=5)` raised `TypeError: Got an unexpected keyword argument relatedToVideoId` before quota was recorded. This appears to come from the tool wrapper passing `relatedToVideoId=None` into the generated Google client for `search().list(...)`; Phase 5 did not modify `src/` per orchestrator constraint. Evidence section: `.sisyphus/evidence/phase-5-repl-probes.md`.

## [2026-05-20] Phase 6 superseded fallback note

- Earlier Phase 6 notes saw Phase 5 evidence as missing. Phase 5 evidence landed during verification and `.sisyphus/evidence/phase-6-quota-validation.md` was regenerated from it. Current remaining validation gaps are `youtube_search_list` (attempt failed before quota record), `youtube_captions_list`, and `youtube_captions_download`; no successful live-delta mismatches were found.

## [2026-05-20] Phase 4 mutating suite failures on @jsigvardt

- Tool/test case: `youtube_playlists_delete` in `test_playlists_create_update_delete`. Exact error: `AttributeError: 'str' object has no attribute 'get'` after cleanup called `playlists.youtube_playlists_delete(...)`. The delete endpoint appears to return a no-content raw string while the tool annotation and live harness expect `dict[str, object]`.
- Tool/test case: `youtube_playlistItems_delete` in `test_playlist_items_insert_delete`. Exact error: `AttributeError: 'str' object has no attribute 'get'` after cleanup called `playlists.youtube_playlistItems_delete(...)`. Same no-content response shape problem.
- Tool/test case: `youtube_comments_delete` in `test_comments_insert_update_delete` and `test_comment_threads_insert_then_comment_delete`. Exact error: `AttributeError: 'str' object has no attribute 'get'` after cleanup called `comments.youtube_comments_delete(...)`. Same no-content response shape problem.
- Tool/test case: `youtube_videos_rate` in `test_videos_rate_like_then_none`. Exact error: `AttributeError: 'str' object has no attribute 'get'` after calling `videos.youtube_videos_rate(...)`. Same no-content response shape problem.
- Tool/test case: `youtube_subscriptions_delete` in `test_subscriptions_subscribe_unsubscribe`. Exact error: `Google API returned MCP error: {'status': 404, 'reason': 'subscriptionNotFound', 'message': "The subscription that you are trying to delete cannot be found. Check the value of the request's <code>id</code> parameter to ensure that it is correct."}`.
- Tool/test case: `youtube_channelSections_insert` in `test_channel_sections_insert_update_delete`. Exact error: `Google API returned MCP error: {'status': 400, 'reason': 'channelNotActive', 'message': 'One or more channels are not active.'}`.
- Tool/test case: `youtube_channel_banners_insert` in `test_channel_banners_insert`. Exact error: `Google API returned MCP error: {'status': 400, 'reason': 'bannerValidationError', 'message': 'Channel banner validation failed. This error can occur because the channel banner image is too large or is not accepted file type. Please see <a href="https://support.google.com/youtube/answer/2972003">YouTube Help Center</a> for banner guidelines.'}`.
- Tool/test case: `youtube_thumbnails_set` in `test_thumbnails_set_then_revert`. Exact error: `Google API returned MCP error: {'status': 400, 'reason': 'invalidImage', 'message': 'The provided image content is invalid.'}`.
- Tool/test case: `youtube_watermarks_set` / `youtube_watermarks_unset` in `test_watermarks_set_unset`. Exact errors: `Google API returned MCP error: {'status': 400, 'reason': 'badRequest', 'message': 'Request contains an invalid argument.'}` and cleanup `{'status': 404, 'reason': 'notFound', 'message': 'Requested entity was not found.'}`.
- Tool/test case: `youtube_liveBroadcasts_insert` in `test_live_broadcasts_insert_update_delete`. Exact error: `Google API returned MCP error: {'status': 403, 'reason': 'liveStreamingNotEnabled', 'message': 'The user is not enabled for live streaming.'}`.
- Tool/test case: `youtube_liveStreams_insert` in `test_live_streams_insert_delete`. Exact error: `Google API returned MCP error: {'status': 403, 'reason': 'liveStreamingNotEnabled', 'message': 'The user is not enabled for live streaming.'}`.
- Tool/test case: `youtube_analytics_groups_insert` in `test_analytics_groups_insert_add_remove_delete`. Exact error: `Google API returned MCP error: {'status': 400, 'reason': 'required', 'message': 'Required'}`.

## [2026-05-20] Phase 4 mutating live triage: real Google behavior and test-infra follow-up

- `test_channel_sections_insert_update_delete`: expected a channel section create/update/delete cycle, observed Google MCP error `status=400 reason=channelNotActive message=One or more channels are not active.` This is real Google channel-state behavior for the low-activity `@jsigvardt` channel, not a tool-wiring bug. Recommended workaround: make the live test skip on `channelNotActive` after ensuring any temporary playlist cleanup runs.
- `test_subscriptions_subscribe_unsubscribe`: expected unsubscribe cleanup of the ID returned by `subscriptions.insert`, observed Google MCP error `status=404 reason=subscriptionNotFound` on delete. This appears to be real Google behavior around duplicate/racing/stale subscription state for the configured target channel, not a mutating guard or request-shape bug. Recommended workaround: make unsubscribe cleanup tolerate `subscriptionNotFound` or preflight and skip when the target subscription state is already inconsistent.
- `test_channel_banners_insert`: expected banner upload URL, observed Google MCP error `status=400 reason=bannerValidationError`. Google rejected `tests/fixtures/test_banner.jpg` as too large or an unacceptable file type/content for banner guidelines, so this is fixture/API validation behavior. Recommended workaround: replace the fixture with a valid YouTube banner asset or skip on `bannerValidationError`.
- `test_thumbnails_set_then_revert`: expected custom thumbnail set and revert, observed Google MCP error `status=400 reason=invalidImage` for both primary and revert fixture attempts. Google rejected the fixture image content, not the tool call shape. Recommended workaround: replace `tests/fixtures/test_thumbnail*.jpg` with valid thumbnail images or skip on `invalidImage`.
- `test_watermarks_set_unset`: expected watermark set/unset, observed Google MCP error `status=400 reason=badRequest` on set and `status=404 reason=notFound` on unset cleanup. This is Google validation/state behavior for the provided watermark body/fixture on `@jsigvardt`, not confirmed tool wiring. Recommended workaround: validate the watermark fixture/body against current API requirements and tolerate `notFound` during cleanup when set never succeeded.
- `test_live_broadcasts_insert_update_delete` and `test_live_streams_insert_delete`: expected live resource create/delete cycles, observed Google MCP error `status=403 reason=liveStreamingNotEnabled`. This is real account capability behavior because `@jsigvardt` is not enabled for live streaming. Recommended workaround: skip these tests on `liveStreamingNotEnabled` unless the operator enables live streaming for the channel.
- `test_analytics_groups_insert_add_remove_delete`: expected analytics group creation, observed Google MCP error `status=400 reason=required` because the live request body omitted required `contentDetails.itemType`. This was test request-shape infrastructure, fixed in `tests/live/test_acid_mutating_jsigvardt.py` by sending `contentDetails: {itemType: youtube#video}`.

## [2026-05-20] BLOCKED: full live sweep quota gate

- `uv run youtube-mcp status` reported `jsigvardt` at `7401/10000` quota units used before the requested full live sweep. Remaining quota is `2599`, below the task hard stop threshold of `3000` remaining units. No live read or mutating pytest commands were run. Resume after quota resets or after the operator explicitly raises the available quota budget.

## [2026-05-20] Phase 9 watermark fixture bug fixed, live rerun deferred

- `test_watermarks_set_unset` failed during the Phase 9 operator-override mutating sweep with `400 badRequest` on `youtube_watermarks_set` and `404 notFound` during cleanup. Categorization: fixture bug. `file tests/fixtures/test_watermark.png` showed the fixture was ASCII text, not a PNG image.
- Fix applied: regenerated `tests/fixtures/test_watermark.png` as a real 150x150 PNG from the valid thumbnail fixture and added `tests/unit/test_mutating_test_helpers.py::test_watermark_fixture_is_real_square_png` so placeholder bytes cannot silently return.
- Live revalidation of `test_watermarks_set_unset` is deferred because the sweep exhausted quota to `10069/10000`. Re-run that single test after quota reset before considering watermark live coverage closed.

## [2026-05-20] Phase 9 quota monitor overran the 500-unit floor

- The one-off shell monitor in the Phase 9 mutating sweep parsed the wrong field from `uv run youtube-mcp status` because the `token` column contains spaces (`expired until ...`). It therefore logged `remaining_before=10000` for every test and did not stop before the high-cost upload test.
- `test_videos_insert_update_keeps_uploaded_video_for_manual_cleanup` ran at `8419/10000` used quota and moved quota to `10069/10000`, breaching the intended 500-unit floor. Evidence: `.sisyphus/evidence/phase-9-mutating-cutoff.md`.
- This was test-operator harness failure, not a youtube-mcp wrapper bug. Future quota monitors should parse the final tab-separated field from `youtube-mcp status` or use a JSON status command if one exists.
## [2026-05-20] Sub S playlist_images grep scope mismatch

- The task's file-wide grep for `on_behalf_of_content_owner_channel|onBehalfOfContentOwnerChannel` in `src/youtube_mcp/tools/playlist_images.py` still matches the valid `list` and `insert` wrappers.
- The implemented scope-only fix keeps `on_behalf_of_content_owner_channel` removed from `youtube_playlistImages_update` and `youtube_playlistImages_delete` as requested.
- If the grep must be zero, the verification command needs to be narrowed to the update/delete bodies or the task needs to explicitly remove the parameter from `list` and `insert` too.
