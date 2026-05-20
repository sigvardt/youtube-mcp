# F3 Re-run Real Manual QA Structural Report

Date: 2026-05-19

Environment: CI/dev shell without live YouTube OAuth tokens or a pre-seeded `jsigvardt` keyring entry. This re-run executed structural QA only and explicitly gated live OAuth surfaces.

## Executed Scenarios

| Scenario | Command or check | Actual output summary |
| --- | --- | --- |
| CLI root help and manual CLI surface | `uv run youtube-mcp --help` plus tmux manual run | Exited 0; showed command tree with `serve`, `auth add`, `auth list`, `auth remove`, `auth refresh`, `status`, `doctor`, and `tools list`. Repeated in tmux; invalid command `uv run youtube-mcp nope` returned `No such command`, and tmux `uv run youtube-mcp auth list` printed `No accounts configured.` |
| Tool listing | `uv run youtube-mcp tools list` | Exited 0; enumerated registered tools without crashing. |
| Empty account list | `uv run youtube-mcp auth list` | Exited 0; printed `No accounts configured.` |
| Empty status | `uv run youtube-mcp status` | Exited 0; printed `Configured accounts: 0`. |
| VCR integration suite | `uv run pytest tests/integration -v` | Collected 4 tests; 4 passed, 1 warning. |
| Live test collection | `uv run pytest tests/live -v --collect-only` | Collected 24 live tests. |
| Live test skip behavior | `uv run pytest tests/live -q` | 24 skipped, 1 warning without live env or accounts. |
| FastMCP registry bootstrap | `uv run python -c ... make_app().list_tools()` | `TOOL_COUNT 98`; server bootstrap returns the expected current registry surface. |
| Prior registry gaps | registry introspection | `playlistImages` tools present: `youtube_playlistImages_list`, `youtube_playlistImages_insert`, `youtube_playlistImages_update`, `youtube_playlistImages_delete`. `videoTrainability` tool present: `youtube_videoTrainability_get`. |
| Mutating guard direct mock | `uv run python -c ... MutatingGuard().assert_allowed(...)` | Printed `VERIFIED_MUTATING_GUARD_REJECTED Mutating YouTube operation forbidden for account 'other': expected channel_handle '@jsigvardt', got '@not-jsigvardt'`. |
| Mutating guard unit suite | `uv run pytest tests/unit/test_mutating_guard.py -v` | Collected 10 tests; 10 passed, 1 warning. |
| Forbidden delete safety | registry introspection and `grep -rn "videos.delete\|videos_delete" src/ tests/` | Registry reported `FORBIDDEN_PRESENT False`; source/test grep printed `NO_FORBIDDEN_SOURCE_MATCHES`. |
| Package build | `uv build --out-dir /var/folders/fs/s4w_v3qd3px0gg4qlt25wrbc0000gn/T/opencode/youtube-mcp-f3-rerun-build` | Successfully built sdist and wheel in the temporary output directory. |

## Gated Scenarios

- Live read-only OAuth acid calls are gated because no OAuth accounts or live credentials are configured in this CI/dev shell. Collection succeeded and all no-account parametrizations skipped cleanly.
- Live mutating `@jsigvardt` acid calls and pre-seeded keyring validation are gated because `RUN_LIVE_TESTS`, `RUN_MUTATING_TESTS`, and a pre-seeded `jsigvardt` account/keyring entry are absent. The structural guard path was verified by mock script and unit tests instead.

## Registry Inventory

Tool count: 98

- `youtube_abuseReports_insert`
- `youtube_activities_list`
- `youtube_analytics_groupItems_delete`
- `youtube_analytics_groupItems_insert`
- `youtube_analytics_groupItems_list`
- `youtube_analytics_groups_delete`
- `youtube_analytics_groups_insert`
- `youtube_analytics_groups_list`
- `youtube_analytics_groups_update`
- `youtube_analytics_reports_describe`
- `youtube_analytics_reports_query`
- `youtube_captions_delete`
- `youtube_captions_download`
- `youtube_captions_insert`
- `youtube_captions_list`
- `youtube_captions_update`
- `youtube_channelSections_delete`
- `youtube_channelSections_insert`
- `youtube_channelSections_list`
- `youtube_channelSections_update`
- `youtube_channel_banners_insert`
- `youtube_channels_list`
- `youtube_channels_update`
- `youtube_commentThreads_insert`
- `youtube_commentThreads_list`
- `youtube_comments_delete`
- `youtube_comments_insert`
- `youtube_comments_list`
- `youtube_comments_markAsSpam`
- `youtube_comments_setModerationStatus`
- `youtube_comments_update`
- `youtube_i18nLanguages_list`
- `youtube_i18nRegions_list`
- `youtube_liveBroadcasts_bind`
- `youtube_liveBroadcasts_cuepoint`
- `youtube_liveBroadcasts_delete`
- `youtube_liveBroadcasts_insert`
- `youtube_liveBroadcasts_list`
- `youtube_liveBroadcasts_transition`
- `youtube_liveBroadcasts_update`
- `youtube_liveChatBans_delete`
- `youtube_liveChatBans_insert`
- `youtube_liveChatMessages_delete`
- `youtube_liveChatMessages_insert`
- `youtube_liveChatMessages_list`
- `youtube_liveChatMessages_transition`
- `youtube_liveChatModerators_delete`
- `youtube_liveChatModerators_insert`
- `youtube_liveChatModerators_list`
- `youtube_liveStreams_delete`
- `youtube_liveStreams_insert`
- `youtube_liveStreams_list`
- `youtube_liveStreams_update`
- `youtube_members_list`
- `youtube_membershipsLevels_list`
- `youtube_playlistImages_delete`
- `youtube_playlistImages_insert`
- `youtube_playlistImages_list`
- `youtube_playlistImages_update`
- `youtube_playlistItems_delete`
- `youtube_playlistItems_insert`
- `youtube_playlistItems_list`
- `youtube_playlistItems_update`
- `youtube_playlists_delete`
- `youtube_playlists_insert`
- `youtube_playlists_list`
- `youtube_playlists_update`
- `youtube_reporting_jobs_create`
- `youtube_reporting_jobs_delete`
- `youtube_reporting_jobs_get`
- `youtube_reporting_jobs_list`
- `youtube_reporting_reportTypes_list`
- `youtube_reporting_reports_download`
- `youtube_reporting_reports_get`
- `youtube_reporting_reports_list`
- `youtube_reporting_wait_for_next_report`
- `youtube_search_list`
- `youtube_subscriptions_delete`
- `youtube_subscriptions_insert`
- `youtube_subscriptions_list`
- `youtube_superChatEvents_list`
- `youtube_tests_insert`
- `youtube_third_party_links_delete`
- `youtube_third_party_links_insert`
- `youtube_third_party_links_list`
- `youtube_third_party_links_update`
- `youtube_thumbnails_set`
- `youtube_videoAbuseReportReasons_list`
- `youtube_videoCategories_list`
- `youtube_videoTrainability_get`
- `youtube_videos_getRating`
- `youtube_videos_insert`
- `youtube_videos_list`
- `youtube_videos_rate`
- `youtube_videos_reportAbuse`
- `youtube_videos_update`
- `youtube_watermarks_set`
- `youtube_watermarks_unset`

## Final Verdict

Scenarios [12 executed / 2 gated] | Integration [4/4 pass] | @jsigvardt guard [VERIFIED] | Pre-seeded keyring [GATED-NO-LIVE-CREDS] | Registry gaps from prior F3 [CLOSED] | VERDICT: APPROVE
