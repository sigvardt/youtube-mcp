# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows semantic versioning.

## [Unreleased]

### Breaking changes

- Removed the deprecated `related_to_video_id` parameter from `youtube_search_list`. `search.list` no longer accepts `relatedToVideoId`, so callers should drop that argument.
- Removed the `segment_id` parameter from `youtube_analytics_reports_query`. `reports.query` no longer accepts `segment`, so callers should drop that argument.
- Removed the `part` parameter from `youtube_videoTrainability_get`. The current `videoTrainability.get` method no longer accepts `part`.
- Removed `on_behalf_of_content_owner_channel` from `youtube_playlistImages_list`, `youtube_playlistImages_insert`, `youtube_playlistImages_update`, and `youtube_playlistImages_delete`. The current `playlistImages` discovery schema no longer accepts `onBehalfOfContentOwnerChannel`.

### Changed

- Documented Google deprecation of `home` on `youtube_activities_list` and `hl` on `youtube_channelSections_list` in the tool docstrings.
- Removed `on_behalf_of_content_owner_channel` from `youtube_playlistImages_update` and `youtube_playlistImages_delete`. The current Discovery schema no longer accepts `onBehalfOfContentOwnerChannel` for those methods.

## [0.1.0] - 2026-05-19

### Added

- FastMCP server bootstrap with stdio, HTTP, and SSE transports, status/account/quota resources, lazy tool registration, retry handling, structured HTTP errors, and per-account quota accounting.
- Multi-brand-account OAuth setup with browser flow, token refresh, OS keyring storage, account config management, and a Typer CLI for `serve`, `auth`, `status`, `doctor`, and `tools list` workflows.
- YouTube Data API coverage across activities, captions, channels, channel sections, comments, comment threads, i18n, live chat, livestreams, members, playlists, playlist items, playlist images, search, subscriptions, Super Chat events, video metadata, video assets, abuse reports, and videos.
- YouTube Analytics API coverage for report queries, query descriptions, groups, and group items.
- YouTube Reporting API coverage for report types, jobs, reports, CSV downloads, single-job lookups, and waiting for the next generated report.
- Mutating-operation guard that tags state-changing tools and can enforce an allow-listed channel handle before uploads, edits, moderation actions, ratings, reports, and other writes.
- Unit, integration, and live-test scaffolding with mocked Google clients, VCR cassettes for read-only integration paths, cross-module registry guards, and coverage enforcement.
- Agent-facing documentation, installation guide, MCP client config examples, and the `skills/youtube-mcp` reference bundle for tool selection and quota-aware usage.

### Security

- Deliberately excluded the YouTube Data API video-deletion endpoint from source, registry, tests, and skill documentation, with defense-in-depth checks to prevent accidental exposure.
- Added cassette redaction expectations and token-free account/status resources so secrets do not appear in configs, docs, or test fixtures.
