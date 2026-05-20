# Phase 5 REPL Probes

- Run started: `2026-05-20T10:16:42.379637+00:00`
- Account: `jsigvardt`
- Channel ID: `UCvTRR-gKfkSwnXTkxg3w2Nw`
- Starting quota: `35`
- Scope: read-only tools only; no mutating tool calls.

## youtube_channels_list (Data)

- Arguments: `account="jsigvardt", part="snippet,contentDetails,statistics", mine=True, max_results=1`
- Quota before: `35`
- Quota after: `36`
- Quota delta: `1`
- Response top-level key set: `['etag', 'items', 'kind', 'pageInfo']`
- Classification: `successful`

## youtube_videos_list (Data)

- Arguments: `account="jsigvardt", part="snippet,contentDetails,statistics,status", mine=True, max_results=5`
- Quota before: `36`
- Quota after: `39`
- Quota delta: `3`
- Response top-level key set: `['etag', 'items', 'kind', 'pageInfo']`
- Classification: `successful`

## youtube_playlists_list (Data)

- Arguments: `account="jsigvardt", part="snippet,contentDetails", mine=True, max_results=5`
- Quota before: `39`
- Quota after: `40`
- Quota delta: `1`
- Response top-level key set: `['etag', 'items', 'kind', 'pageInfo']`
- Classification: `successful`

## youtube_search_list (Data)

- Arguments: `account="jsigvardt", part="snippet", q="cats", max_results=5`
- Quota before: `40`
- Quota after: `40`
- Quota delta: `0`
- Response top-level key set: `['exception', 'message']`
- Classification: `unexpected-error`
- Error reason: `TypeError`
- Diagnostic message: `Got an unexpected keyword argument relatedToVideoId`

## youtube_subscriptions_list (Data)

- Arguments: `account="jsigvardt", part="snippet,contentDetails", mine=True, max_results=5`
- Quota before: `40`
- Quota after: `41`
- Quota delta: `1`
- Response top-level key set: `['etag', 'items', 'kind', 'nextPageToken', 'pageInfo']`
- Classification: `successful`

## youtube_commentThreads_list (Data)

- Arguments: `account="jsigvardt", part="snippet,replies", all_threads_related_to_channel_id="UCvTRR-gKfkSwnXTkxg3w2Nw", max_results=5`
- Quota before: `41`
- Quota after: `42`
- Quota delta: `1`
- Response top-level key set: `['etag', 'items', 'kind', 'pageInfo']`
- Classification: `successful`

## youtube_i18nLanguages_list (Data)

- Arguments: `account="jsigvardt", part="snippet"`
- Quota before: `42`
- Quota after: `43`
- Quota delta: `1`
- Response top-level key set: `['etag', 'items', 'kind']`
- Classification: `successful`

## youtube_videoCategories_list (Data)

- Arguments: `account="jsigvardt", part="snippet", region_code="US"`
- Quota before: `43`
- Quota after: `44`
- Quota delta: `1`
- Response top-level key set: `['etag', 'items', 'kind']`
- Classification: `successful`

## youtube_analytics_reports_query (Analytics)

- Arguments: `account="jsigvardt", ids="channel==MINE", metrics="views", start_date="2026-05-13", end_date="2026-05-19", max_results=1`
- Quota before: `44`
- Quota after: `44`
- Quota delta: `0`
- Response top-level key set: `['columnHeaders', 'kind', 'rows']`
- Classification: `successful`

## youtube_reporting_reportTypes_list (Reporting)

- Arguments: `account="jsigvardt", include_system_managed=True, page_size=10`
- Quota before: `44`
- Quota after: `45`
- Quota delta: `1`
- Response top-level key set: `['nextPageToken', 'reportTypes']`
- Classification: `successful`

## youtube_reporting_jobs_list (Reporting)

- Arguments: `account="jsigvardt", include_system_managed=True, page_size=10`
- Quota before: `45`
- Quota after: `46`
- Quota delta: `1`
- Response top-level key set: `[]`
- Classification: `successful`

## Summary

- Probes attempted: `11`
- Successful: `10`
- Known-skippable: `0`
- Unexpected: `1`
- Data API quota burn: `9`
- Total quota burn: `11`
