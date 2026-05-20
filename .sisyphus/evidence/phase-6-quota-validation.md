# Phase 6 Quota Cost Validation

Date: 2026-05-20

## Summary

- Total tools enumerated: 98
- Tools with explicit decorator cost: 98
- Tools defaulting through `cost=None`: 0
- Phase 5 probes parsed: 11 attempted, 10 successful
- Unique tools validated against successful live quota tracker deltas: 10
- Mismatches: 0
- Phase 5 evidence input: `.sisyphus/evidence/phase-5-repl-probes.md`.
- Additional live quota burn by Phase 6 fallback before Phase 5 appeared: 3 units (`youtube_videos_list`).
- Mutating tools were not called by Phase 6.
- Analytics and Reporting APIs use separate Google quota pools; this repo records their local declared costs through the same `QuotaTracker` abstraction when tools succeed.

## Validation Notes

- `@youtube_tool` resolves `cost` once at decoration time and records exactly that many local units after a successful inner call.
- `youtube_videos_list(mine=True)` chains `channels.list`, `playlistItems.list`, and `videos.list`; Phase 5 observed delta 3 and the Phase 6 fallback probe also observed delta 3, matching declared cost 3.
- `youtube_search_list` is documented by Google at 100 units. Phase 5 attempted it once, but it failed with `TypeError` before the framework recorded quota, so its delta 0 is not treated as a quota-cost validation or mismatch.
- `youtube_captions_list` (50 units) and `youtube_captions_download` (200 units) remain unvalidated in live evidence; Phase 6 did not call them to stay inside the additional burn cap and avoid needing a caption id.
- The required `sg` command-line tool was unavailable in this environment, so decorator enumeration was performed with Python AST parsing after attempted ast-grep searches.

## Per-tool Cost Table

| Tool | API | Method | Declared cost | Mutating | Observed cost | Source | Status |
| --- | --- | --- | ---: | --- | ---: | --- | --- |
| `youtube_abuseReports_insert` | `youtube` | `youtube.abuseReports.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_activities_list` | `youtube` | `youtube.activities.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_analytics_groupItems_delete` | `analytics` | `youtubeAnalytics.groupItems.delete` | 1 | true | N/A | N/A | NOT VALIDATED |
| `youtube_analytics_groupItems_insert` | `analytics` | `youtubeAnalytics.groupItems.insert` | 1 | true | N/A | N/A | NOT VALIDATED |
| `youtube_analytics_groupItems_list` | `analytics` | `youtubeAnalytics.groupItems.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_analytics_groups_delete` | `analytics` | `youtubeAnalytics.groups.delete` | 1 | true | N/A | N/A | NOT VALIDATED |
| `youtube_analytics_groups_insert` | `analytics` | `youtubeAnalytics.groups.insert` | 1 | true | N/A | N/A | NOT VALIDATED |
| `youtube_analytics_groups_list` | `analytics` | `youtubeAnalytics.groups.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_analytics_groups_update` | `analytics` | `youtubeAnalytics.groups.update` | 1 | true | N/A | N/A | NOT VALIDATED |
| `youtube_analytics_reports_describe` | `analytics` | `youtubeAnalytics.reports.query` | 0 | false | N/A | N/A | NOT VALIDATED |
| `youtube_analytics_reports_query` | `analytics` | `youtubeAnalytics.reports.query` | 0 | false | 0 | Phase 5 | MATCH |
| `youtube_captions_delete` | `youtube` | `youtube.captions.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_captions_download` | `youtube` | `youtube.captions.download` | 200 | false | N/A | N/A | NOT VALIDATED |
| `youtube_captions_insert` | `youtube` | `youtube.captions.insert` | 400 | true | N/A | N/A | NOT VALIDATED |
| `youtube_captions_list` | `youtube` | `youtube.captions.list` | 50 | false | N/A | N/A | NOT VALIDATED |
| `youtube_captions_update` | `youtube` | `youtube.captions.update` | 450 | true | N/A | N/A | NOT VALIDATED |
| `youtube_channelSections_delete` | `youtube` | `youtube.channelSections.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_channelSections_insert` | `youtube` | `youtube.channelSections.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_channelSections_list` | `youtube` | `youtube.channelSections.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_channelSections_update` | `youtube` | `youtube.channelSections.update` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_channel_banners_insert` | `youtube` | `youtube.channelBanners.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_channels_list` | `youtube` | `youtube.channels.list` | 1 | false | 1 | Phase 5 | MATCH |
| `youtube_channels_update` | `youtube` | `youtube.channels.update` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_commentThreads_insert` | `youtube` | `youtube.commentThreads.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_commentThreads_list` | `youtube` | `youtube.commentThreads.list` | 1 | false | 1 | Phase 5 | MATCH |
| `youtube_comments_delete` | `youtube` | `youtube.comments.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_comments_insert` | `youtube` | `youtube.comments.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_comments_list` | `youtube` | `youtube.comments.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_comments_markAsSpam` | `youtube` | `youtube.comments.markAsSpam` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_comments_setModerationStatus` | `youtube` | `youtube.comments.setModerationStatus` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_comments_update` | `youtube` | `youtube.comments.update` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_i18nLanguages_list` | `youtube` | `youtube.i18nLanguages.list` | 1 | false | 1 | Phase 5 | MATCH |
| `youtube_i18nRegions_list` | `youtube` | `youtube.i18nRegions.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_liveBroadcasts_bind` | `youtube` | `youtube.liveBroadcasts.bind` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveBroadcasts_cuepoint` | `youtube` | `youtube.liveBroadcasts.cuepoint` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveBroadcasts_delete` | `youtube` | `youtube.liveBroadcasts.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveBroadcasts_insert` | `youtube` | `youtube.liveBroadcasts.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveBroadcasts_list` | `youtube` | `youtube.liveBroadcasts.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_liveBroadcasts_transition` | `youtube` | `youtube.liveBroadcasts.transition` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveBroadcasts_update` | `youtube` | `youtube.liveBroadcasts.update` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveChatBans_delete` | `youtube` | `youtube.liveChatBans.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveChatBans_insert` | `youtube` | `youtube.liveChatBans.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveChatMessages_delete` | `youtube` | `youtube.liveChatMessages.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveChatMessages_insert` | `youtube` | `youtube.liveChatMessages.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveChatMessages_list` | `youtube` | `youtube.liveChatMessages.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_liveChatMessages_transition` | `youtube` | `youtube.liveChatMessages.transition` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveChatModerators_delete` | `youtube` | `youtube.liveChatModerators.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveChatModerators_insert` | `youtube` | `youtube.liveChatModerators.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveChatModerators_list` | `youtube` | `youtube.liveChatModerators.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_liveStreams_delete` | `youtube` | `youtube.liveStreams.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveStreams_insert` | `youtube` | `youtube.liveStreams.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_liveStreams_list` | `youtube` | `youtube.liveStreams.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_liveStreams_update` | `youtube` | `youtube.liveStreams.update` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_members_list` | `youtube` | `youtube.members.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_membershipsLevels_list` | `youtube` | `youtube.membershipsLevels.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_playlistImages_delete` | `youtube` | `youtube.playlistImages.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_playlistImages_insert` | `youtube` | `youtube.playlistImages.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_playlistImages_list` | `youtube` | `youtube.playlistImages.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_playlistImages_update` | `youtube` | `youtube.playlistImages.update` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_playlistItems_delete` | `youtube` | `youtube.playlistItems.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_playlistItems_insert` | `youtube` | `youtube.playlistItems.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_playlistItems_list` | `youtube` | `youtube.playlistItems.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_playlistItems_update` | `youtube` | `youtube.playlistItems.update` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_playlists_delete` | `youtube` | `youtube.playlists.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_playlists_insert` | `youtube` | `youtube.playlists.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_playlists_list` | `youtube` | `youtube.playlists.list` | 1 | false | 1 | Phase 5 | MATCH |
| `youtube_playlists_update` | `youtube` | `youtube.playlists.update` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_reporting_jobs_create` | `reporting` | `youtubeReporting.jobs.create` | 1 | true | N/A | N/A | NOT VALIDATED |
| `youtube_reporting_jobs_delete` | `reporting` | `youtubeReporting.jobs.delete` | 1 | true | N/A | N/A | NOT VALIDATED |
| `youtube_reporting_jobs_get` | `reporting` | `youtubeReporting.jobs.get` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_reporting_jobs_list` | `reporting` | `youtubeReporting.jobs.list` | 1 | false | 1 | Phase 5 | MATCH |
| `youtube_reporting_reportTypes_list` | `reporting` | `youtubeReporting.reportTypes.list` | 1 | false | 1 | Phase 5 | MATCH |
| `youtube_reporting_reports_download` | `reporting` | `youtubeReporting.reports.download` | 0 | false | N/A | N/A | NOT VALIDATED |
| `youtube_reporting_reports_get` | `reporting` | `youtubeReporting.reports.get` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_reporting_reports_list` | `reporting` | `youtubeReporting.reports.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_reporting_wait_for_next_report` | `reporting` | `youtubeReporting.reports.waitForNext` | 0 | false | N/A | N/A | NOT VALIDATED |
| `youtube_search_list` | `youtube` | `youtube.search.list` | 100 | false | 0 | Phase 5 | NOT VALIDATED (unexpected-error) |
| `youtube_subscriptions_delete` | `youtube` | `youtube.subscriptions.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_subscriptions_insert` | `youtube` | `youtube.subscriptions.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_subscriptions_list` | `youtube` | `youtube.subscriptions.list` | 1 | false | 1 | Phase 5 | MATCH |
| `youtube_superChatEvents_list` | `youtube` | `youtube.superChatEvents.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_tests_insert` | `youtube` | `youtube.tests.insert` | 0 | true | N/A | N/A | NOT VALIDATED |
| `youtube_third_party_links_delete` | `youtube` | `youtube.thirdPartyLinks.delete` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_third_party_links_insert` | `youtube` | `youtube.thirdPartyLinks.insert` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_third_party_links_list` | `youtube` | `youtube.thirdPartyLinks.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_third_party_links_update` | `youtube` | `youtube.thirdPartyLinks.update` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_thumbnails_set` | `youtube` | `youtube.thumbnails.set` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_videoAbuseReportReasons_list` | `youtube` | `youtube.videoAbuseReportReasons.list` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_videoCategories_list` | `youtube` | `youtube.videoCategories.list` | 1 | false | 1 | Phase 5 | MATCH |
| `youtube_videoTrainability_get` | `youtube` | `youtube.videoTrainability.get` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_videos_getRating` | `youtube` | `youtube.videos.getRating` | 1 | false | N/A | N/A | NOT VALIDATED |
| `youtube_videos_insert` | `youtube` | `youtube.videos.insert` | 1600 | true | N/A | N/A | NOT VALIDATED |
| `youtube_videos_list` | `youtube` | `youtube.videos.list` | 3 | false | 3 | Phase 5 | MATCH |
| `youtube_videos_rate` | `youtube` | `youtube.videos.rate` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_videos_reportAbuse` | `youtube` | `youtube.videos.reportAbuse` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_videos_update` | `youtube` | `youtube.videos.update` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_watermarks_set` | `youtube` | `youtube.watermarks.set` | 50 | true | N/A | N/A | NOT VALIDATED |
| `youtube_watermarks_unset` | `youtube` | `youtube.watermarks.unset` | 50 | true | N/A | N/A | NOT VALIDATED |

## Default Cost Tools

No tools default to `cost=None`; every `@youtube_tool` decorator has an explicit `cost=` argument.

## Read-only Tools With Declared Cost Greater Than 1

| Tool | Declared cost | Probe decision |
| --- | ---: | --- |
| `youtube_captions_download` | 200 | Not covered; skipped because declared 200 units and requires a caption id. |
| `youtube_captions_list` | 50 | Not covered; skipped to preserve Phase 6 additional burn cap after fallback probe. |
| `youtube_search_list` | 100 | Covered by Phase 5 attempt only; failed before quota record, NOT VALIDATED. Do not probe again casually because Google documents 100 units. |
| `youtube_videos_list` | 3 | Covered by Phase 5 and duplicated by Phase 6 fallback; both deltas were 3, MATCH. |

## Mismatch Root-cause Hypotheses

- None among successful live-validated tools.

## Unexpected Probe Notes

- `youtube_search_list`: Phase 5 observed delta 0 because the call raised `TypeError: Got an unexpected keyword argument relatedToVideoId` before quota recording. This is an execution issue, not evidence that Google charged 0 units for `search.list`.
