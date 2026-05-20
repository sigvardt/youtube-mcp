# Sub Q2 empty-body normalization audit

## Risk summary

- HIGH: 1
- MEDIUM: 0
- LOW: 15
- NONE: 1 reference row
- Priority 1: harden `src/youtube_mcp/tools/playlist_images.py::youtube_playlistImages_delete`
- Priority 2: add a regression test for empty `playlistImages.delete` responses (`None` and `""` should become `{}` before `EmptyResponse.model_validate`)
- Priority 3: keep the framework normalization covered by tests; the remaining delete / unset wrappers are currently safe because `_framework._normalize_tool_result` handles empty bodies after return

## Reference baseline

`src/youtube_mcp/tools/comments.py::youtube_comments_delete` is the fixed pattern.
It does a local `isinstance(response, dict)` check and returns `{}` for empty bodies.
`_framework.py` also protects all decorated tools with `_normalize_tool_result`, which turns `None` and `""` into `{}` after the tool returns.

Modules scanned with no matching `delete` / `unset` / `remove` / `clear` wrappers:
`activities.py`, `analytics_reports.py`, `comment_threads.py`, `i18n.py`, `misc.py`, `search.py`, `super_chat_events.py`, `video_meta.py`, `videos.py`.

| module path | tool function name | Google API verb | empty-body risk | actual code snippet | reference comparison to comments.py |
| --- | --- | --- | --- | --- | --- |
| src/youtube_mcp/tools/comments.py | youtube_comments_delete | delete | NONE | `response = service.comments().delete(id=id).execute()`<br>`if isinstance(response, dict):`<br>`    return cast(dict[str, object], response)`<br>`return {}` | Reference pattern. It normalizes empty delete bodies inside the tool, then _framework._normalize_tool_result provides the same {} fallback after the call. |
| src/youtube_mcp/tools/playlist_images.py | youtube_playlistImages_delete | delete | HIGH | `response = cast(`<br>`    dict[str, Any],`<br>`    service.playlistImages().delete(...).execute(),`<br>`)`<br>`return EmptyResponse.model_validate(response)` | Deviates from comments.py. Validation runs on the raw execute() output, so an empty string or None can fail before framework normalization can coerce it to {}. |
| src/youtube_mcp/tools/analytics_groups.py | youtube_analytics_groups_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.groups().delete(...).execute(),`<br>`)` | No local empty-body guard, but _framework._normalize_tool_result converts None or "" to {} after the tool returns. Current risk is low, not high. |
| src/youtube_mcp/tools/analytics_groups.py | youtube_analytics_groupItems_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.groupItems().delete(...).execute(),`<br>`)` | Same as the reference fix only through the framework layer. There is no in-tool guard, but empty strings or None are normalized to {} after return. |
| src/youtube_mcp/tools/captions.py | youtube_captions_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.captions().delete(...).execute(),`<br>`)` | Matches the current safe pattern only because _framework._normalize_tool_result fixes empty string or None after the call. No per-tool guard present. |
| src/youtube_mcp/tools/channel_sections.py | youtube_channelSections_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.channelSections().delete(...).execute(),`<br>`)` | Matches the framework-safe pass-through. The raw execute() result is still direct, but None or "" is normalized to {} after return. |
| src/youtube_mcp/tools/channels.py | youtube_third_party_links_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.thirdPartyLinks().delete(...).execute(),`<br>`)` | Same framework-safe pattern as the other direct execute() wrappers. No local empty-body check, but the decorated result is normalized to {} if empty. |
| src/youtube_mcp/tools/live_chat.py | youtube_liveChatMessages_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.liveChatMessages().delete(...).execute(),`<br>`)` | Direct execute() pass-through only. Safe today because framework normalization converts empty bodies to {} after the wrapper returns. |
| src/youtube_mcp/tools/live_chat.py | youtube_liveChatModerators_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.liveChatModerators().delete(...).execute(),`<br>`)` | Same as comments.py only at the framework layer. The wrapper itself does not guard empty bodies, but the result is still normalized after return. |
| src/youtube_mcp/tools/live_chat.py | youtube_liveChatBans_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.liveChatBans().delete(...).execute(),`<br>`)` | Safe via framework normalization only. No local `response` guard, but empty string or None is converted to {} before MCP response construction. |
| src/youtube_mcp/tools/livestream.py | youtube_liveBroadcasts_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.liveBroadcasts().delete(...).execute(),`<br>`)` | Framework-safe direct pass-through. If the Google client returns an empty success body, _normalize_tool_result supplies {}. |
| src/youtube_mcp/tools/livestream.py | youtube_liveStreams_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.liveStreams().delete(...).execute(),`<br>`)` | Same safe framework path as the other delete wrappers. No per-tool guard, but the decorated result is normalized after execution. |
| src/youtube_mcp/tools/playlists.py | youtube_playlists_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.playlists().delete(...).execute(),`<br>`)` | Direct execute() return only. Empty string or None is handled by _framework._normalize_tool_result, so this is not the comments.py crash path. |
| src/youtube_mcp/tools/playlists.py | youtube_playlistItems_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.playlistItems().delete(...).execute(),`<br>`)` | Same framework-only protection as the other direct pass-through delete wrappers. No local normalization, but no current empty-body crash vector. |
| src/youtube_mcp/tools/reporting_jobs.py | youtube_reporting_jobs_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.jobs().delete(...).execute(),`<br>`)` | Framework-safe only. The wrapper forwards the Google response directly, but empty success bodies are normalized to {} after the decorated call. |
| src/youtube_mcp/tools/subscriptions.py | youtube_subscriptions_delete | delete | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.subscriptions().delete(...).execute(),`<br>`)` | Same safe path as comments.py only through framework normalization. The function itself does not special-case empty bodies. |
| src/youtube_mcp/tools/video_assets.py | youtube_watermarks_unset | unset | LOW | `return cast(`<br>`    dict[str, object],`<br>`    service.watermarks().unset(...).execute(),`<br>`)` | Unset is the same shape as delete here. The wrapper is safe today because the framework turns None or "" into {} after the inner function returns. |
