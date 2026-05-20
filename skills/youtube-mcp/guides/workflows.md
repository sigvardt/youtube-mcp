# YouTube MCP Workflows

Seven composition recipes that wire multiple tools end to end across the three APIs this server exposes (YouTube Data API v3, YouTube Analytics API v2, YouTube Reporting API v1). Each recipe lists the exact tool sequence, when an agent would use it, the OAuth scopes the connected account must hold, the rough quota cost, and the common failure modes.

Conventions used below:

- `ACCOUNT` is the account alias registered with `youtube_mcp accounts add`.
- `VIDEO_ID`, `CHANNEL_ID`, `PLAYLIST_ID`, `BROADCAST_ID`, `STREAM_ID`, `LIVE_CHAT_ID`, `COMMENT_ID`, `THREAD_ID` are placeholders the agent fills in from prior tool output.
- Quota estimates come from the public Data API documentation. `youtube_videos_insert` is the heavy one at ~1600 units per call. Most reads cost 1 unit. Most writes cost 50.
- The Reporting API and Analytics API use their own quotas, separate from Data API daily 10,000-unit budget.
- This server does NOT expose a video-deletion tool. None of these recipes remove a video.

## Recipe 1: Upload a video with thumbnail and captions

**Why**: The canonical "publish new video" workflow. Use this when an agent needs to push a finished video file to a channel, set a custom thumbnail, and attach a caption track in one coherent sequence. Once metadata changes (title, description, tags) need to land after upload, fold them into a follow-up `youtube_videos_update` call.

**Required scopes**:

- `https://www.googleapis.com/auth/youtube.upload` (the upload itself)
- `https://www.googleapis.com/auth/youtube.force-ssl` (thumbnail + caption writes)

**Account**: must own the target channel.

**Flow**:

```
youtube_videos_insert          (resumable upload, ~1600 quota)
        │
        ▼
youtube_thumbnails_set         (custom thumbnail, ~50 quota)
        │
        ▼
youtube_captions_insert        (caption track, ~400 quota)
        │
        ▼
youtube_videos_update          (final metadata polish, ~50 quota)
```

**Concrete calls**:

```jsonc
// 1. Resumable upload. Returns {"id": VIDEO_ID, ...}.
youtube_videos_insert({
  "account": ACCOUNT,
  "part": ["snippet", "status"],
  "file_path": "/abs/path/to/video.mp4",
  "body": {
    "snippet": {
      "title": "Quarterly product update",
      "description": "What shipped in Q1.",
      "categoryId": "28",
      "tags": ["product", "update"]
    },
    "status": {
      "privacyStatus": "private",
      "selfDeclaredMadeForKids": false
    }
  }
})

// 2. Attach a custom thumbnail (JPEG/PNG, < 2 MB).
youtube_thumbnails_set({
  "account": ACCOUNT,
  "videoId": VIDEO_ID,
  "file_path": "/abs/path/to/thumbnail.jpg"
})

// 3. Upload a caption track.
youtube_captions_insert({
  "account": ACCOUNT,
  "part": ["snippet"],
  "file_path": "/abs/path/to/captions.srt",
  "body": {
    "snippet": {
      "videoId": VIDEO_ID,
      "language": "en",
      "name": "English",
      "isDraft": false
    }
  }
})

// 4. Flip privacy to public and finalize tags/category if they need to change.
youtube_videos_update({
  "account": ACCOUNT,
  "part": ["status", "snippet"],
  "body": {
    "id": VIDEO_ID,
    "status": {"privacyStatus": "public"},
    "snippet": {
      "title": "Quarterly product update",
      "description": "What shipped in Q1.",
      "categoryId": "28",
      "tags": ["product", "update"]
    }
  }
})
```

**Approx. cost**: ~2,100 Data API quota units per video. Most of that is the upload itself.

**Error handling**:

- `youtube_videos_insert` streams in 8 MiB chunks. A transient network error during a chunk is retried by the resumable upload session automatically; a chunk that exhausts the retry budget raises and you should retry the whole call after a short backoff.
- A 403 with reason `uploadLimitExceeded` means the account hit the daily upload cap. Wait, do not retry immediately.
- `youtube_thumbnails_set` rejects images outside the supported size and aspect ratio. Re-encode and retry.
- `youtube_captions_insert` returns a 400 if the SRT/VTT is malformed. Validate locally first.
- Do not delete the uploaded video on failure of a later step. Re-run the failing step, or set `privacyStatus=private` via `youtube_videos_update` if you need to hide the upload while you debug.

## Recipe 2: Schedule a live broadcast and bind it to a stream

**Why**: Use this when an agent is setting up a future live event end to end: it needs an ingest stream with a stream key, a broadcast scheduled for a specific time, the two bound together, and clean transitions through `testing` → `live` → `complete` when the show actually happens.

**Required scopes**:

- `https://www.googleapis.com/auth/youtube.force-ssl`

**Account**: must own the target channel and be enabled for live streaming.

**Flow**:

```
youtube_liveStreams_insert            (create ingest, ~50 quota)
        │
        ▼
youtube_liveBroadcasts_insert         (schedule broadcast, ~50 quota)
        │
        ▼
youtube_liveBroadcasts_bind           (attach stream, ~50 quota)
        │
        ▼  (showtime)
youtube_liveBroadcasts_transition     ("testing", ~50 quota)
        │
        ▼
youtube_liveBroadcasts_transition     ("live", ~50 quota)
        │
        ▼  (after the show)
youtube_liveBroadcasts_transition     ("complete", ~50 quota)
```

**Concrete calls**:

```jsonc
// 1. Create the ingest stream. Returns {"id": STREAM_ID, "cdn": {"ingestionInfo": {...}}}.
youtube_liveStreams_insert({
  "account": ACCOUNT,
  "part": ["snippet", "cdn", "status"],
  "body": {
    "snippet": {"title": "Product launch ingest"},
    "cdn": {
      "frameRate": "60fps",
      "ingestionType": "rtmp",
      "resolution": "1080p"
    }
  }
})

// 2. Schedule the broadcast in the future.
youtube_liveBroadcasts_insert({
  "account": ACCOUNT,
  "part": ["snippet", "status", "contentDetails"],
  "body": {
    "snippet": {
      "title": "Product launch live stream",
      "scheduledStartTime": "2026-06-01T17:00:00Z"
    },
    "status": {
      "privacyStatus": "unlisted",
      "selfDeclaredMadeForKids": false
    },
    "contentDetails": {"enableAutoStart": false, "enableAutoStop": false}
  }
})

// 3. Bind the broadcast to the ingest stream.
youtube_liveBroadcasts_bind({
  "account": ACCOUNT,
  "id": BROADCAST_ID,
  "part": ["id", "contentDetails"],
  "streamId": STREAM_ID
})

// 4. At showtime: testing → live → complete.
youtube_liveBroadcasts_transition({"account": ACCOUNT, "id": BROADCAST_ID, "broadcastStatus": "testing", "part": ["id", "status"]})
youtube_liveBroadcasts_transition({"account": ACCOUNT, "id": BROADCAST_ID, "broadcastStatus": "live",    "part": ["id", "status"]})
youtube_liveBroadcasts_transition({"account": ACCOUNT, "id": BROADCAST_ID, "broadcastStatus": "complete","part": ["id", "status"]})
```

**Approx. cost**: ~250 Data API quota units to set up, plus ~50 per transition.

**Error handling**:

- `youtube_liveBroadcasts_transition` returns `redundantTransition` if the broadcast is already in the requested state. Treat that as success and move on.
- `invalidTransition` means the stream is not actually receiving data, or the prior state was wrong. Pull `youtube_liveBroadcasts_list({id: BROADCAST_ID, part: ["status"]})` to inspect `lifeCycleStatus` before retrying.
- Always poll the stream's `status.streamStatus` (`youtube_liveStreams_list`) before calling `transition("live")`. Going live with no inbound video produces a black broadcast.

## Recipe 3: Moderate comments on a recent video

**Why**: Run this when an agent needs to triage comments held for review, classify them (spam, abusive, fine), and apply the right moderation action on each. Common trigger: a video just got a traffic spike, the channel owner wants comments cleaned up before the next post.

**Required scopes**:

- `https://www.googleapis.com/auth/youtube.force-ssl`

**Account**: must own the target video.

**Flow**:

```
youtube_commentThreads_list           (heldForReview, 1 quota/page)
        │
        ▼  (for each thread)
agent classifies (LLM, rules, etc.)
        │
        ├──► youtube_comments_setModerationStatus("published",  ~50 quota)
        ├──► youtube_comments_setModerationStatus("rejected",   ~50 quota)
        └──► youtube_comments_markAsSpam                        (~50 quota)
```

**Concrete calls**:

```jsonc
// 1. Pull held comment threads for a video.
youtube_commentThreads_list({
  "account": ACCOUNT,
  "part": ["snippet", "replies"],
  "videoId": VIDEO_ID,
  "moderationStatus": "heldForReview",
  "maxResults": 50
})

// 2. For each thread item, decide what to do, then act on the top-level comment id.
//    Approve:
youtube_comments_setModerationStatus({
  "account": ACCOUNT,
  "id": [COMMENT_ID_1, COMMENT_ID_2],
  "moderationStatus": "published"
})

//    Reject as policy violation:
youtube_comments_setModerationStatus({
  "account": ACCOUNT,
  "id": [COMMENT_ID_3],
  "moderationStatus": "rejected",
  "banAuthor": true
})

//    Flag obvious spam:
youtube_comments_markAsSpam({"account": ACCOUNT, "id": [COMMENT_ID_4]})
```

**Approx. cost**: 1 quota per page of threads (50 threads per page), plus ~50 per moderation action. Batch the `id` array on `setModerationStatus` so 50 approvals cost 50 quota, not 50 × 50.

**Error handling**:

- `commentsDisabled` reason on `youtube_commentThreads_list` means the channel turned comments off. Surface that to the user rather than retrying.
- `banAuthor=true` only works with `moderationStatus="rejected"`. Setting it on `published` is silently ignored.
- Held comments older than ~60 days get auto-rejected by YouTube; the API call returns success but the comment was already gone. Re-fetch the thread to confirm.

## Recipe 4: Pull a daily analytics report for a video

**Why**: Use this when an agent needs to answer "how is this video performing?" with day-by-day numbers. The Analytics API returns structured rows the agent can format, chart, or feed into a digest.

**Required scopes**:

- `https://www.googleapis.com/auth/yt-analytics.readonly`
- Add `https://www.googleapis.com/auth/yt-analytics-monetary.readonly` if you need revenue metrics.

**Account**: must own the channel hosting the video.

**Flow**:

```
youtube_analytics_reports_describe   (optional, validate metric set, 0 Data quota)
        │
        ▼
youtube_analytics_reports_query      (the actual report, 1 Analytics quota)
```

**Concrete calls**:

```jsonc
// 1. (Optional) Confirm the metrics + dimensions combo is supported.
youtube_analytics_reports_describe({
  "account": ACCOUNT,
  "ids": "channel==MINE",
  "metrics": "views,estimatedMinutesWatched,averageViewDuration,likes,subscribersGained",
  "dimensions": "day",
  "filters": "video==" + VIDEO_ID
})

// 2. Run the query for the last 28 days, broken down by day.
youtube_analytics_reports_query({
  "account": ACCOUNT,
  "ids": "channel==MINE",
  "startDate": "2026-04-21",
  "endDate": "2026-05-18",
  "metrics": "views,estimatedMinutesWatched,averageViewDuration,likes,subscribersGained",
  "dimensions": "day",
  "filters": "video==" + VIDEO_ID,
  "sort": "day"
})
```

**Approx. cost**: 1 Analytics API query unit per call. The Analytics quota is generous (well above what one report consumes). No Data API quota is touched here.

**Error handling**:

- An empty `rows` array is a valid result. It means the video has zero activity in that window, not that the call failed.
- A 400 `invalidQuery` usually means the metric/dimension combination is not supported. Use `youtube_analytics_reports_describe` to check, or trim the dimension list.
- A 403 `forbidden` means the account does not own the channel referenced in `ids`. Confirm the account alias is the right channel manager.

## Recipe 5: Set up bulk daily CSV reporting via the Reporting API

**Why**: Use this when an agent needs raw, line-level data dumps (every video, every day, all viewers) rather than the aggregated rows from Analytics. The Reporting API drops zipped CSVs into a queue; the channel subscribes to a report type once, then downloads new files daily.

**Required scopes**:

- `https://www.googleapis.com/auth/yt-analytics.readonly`
- Add `https://www.googleapis.com/auth/yt-analytics-monetary.readonly` for revenue report types.

**Account**: must own the channel.

**Flow**:

```
youtube_reporting_reportTypes_list   (discover available report types)
        │
        ▼
youtube_reporting_jobs_create        (subscribe to one report type)
        │
        ▼  (YouTube generates a daily report; usually 24-48h later)
youtube_reporting_reports_list       (list available reports for the job)
        │
        ▼
youtube_reporting_reports_get        (fetch download URL for one report)
        │
        ▼
youtube_reporting_reports_download   (stream CSV.gz to disk)
```

**Concrete calls**:

```jsonc
// 1. List all report types the channel is allowed to subscribe to.
youtube_reporting_reportTypes_list({"account": ACCOUNT})

// 2. Pick one (e.g. "channel_basic_a2") and create a job. Returns {"id": JOB_ID, ...}.
youtube_reporting_jobs_create({
  "account": ACCOUNT,
  "body": {
    "reportTypeId": "channel_basic_a2",
    "name": "Daily channel basics"
  }
})

// 3. On a daily cron, list reports the job has produced.
youtube_reporting_reports_list({
  "account": ACCOUNT,
  "jobId": JOB_ID,
  "createdAfter": "2026-05-18T00:00:00Z"
})

// 4. For each new report, get the download URL.
youtube_reporting_reports_get({
  "account": ACCOUNT,
  "jobId": JOB_ID,
  "reportId": REPORT_ID
})

// 5. Stream the gzipped CSV to disk.
youtube_reporting_reports_download({
  "account": ACCOUNT,
  "resource_name": REPORT_RESOURCE_NAME,   // from step 4
  "output_path": "/abs/path/reports/channel_basic_a2/2026-05-18.csv.gz"
})
```

**Approx. cost**: Reporting API has its own quota and is essentially free at single-channel scale. No Data API quota is consumed.

**Error handling**:

- First report after `jobs_create` does not appear for 24 to 48 hours. Do not interpret an empty `reports_list` result during that window as a failure.
- A report can be reissued after a backfill. Always use the `id` and `createTime` fields to deduplicate downloads rather than just the day stamp.
- `youtube_reporting_reports_download` writes a `.csv.gz` (gzip). Decompress before parsing.

## Recipe 6: Manage playlists (create, add items, reorder)

**Why**: Use this when an agent needs to assemble a curated playlist: create the container, drop items in, and shuffle them into the right order. Common trigger: a weekly digest playlist, an evergreen "best of" collection, or a series order fix after a wrong upload sequence.

**Required scopes**:

- `https://www.googleapis.com/auth/youtube.force-ssl`

**Account**: must own the channel that will host the playlist.

**Flow**:

```
youtube_playlists_insert             (create playlist, ~50 quota)
        │
        ▼  (for each video to include)
youtube_playlistItems_insert         (add item, ~50 quota)
        │
        ▼  (to reorder)
youtube_playlistItems_update         (set new "position", ~50 quota)
        │
        ▼  (optional verification)
youtube_playlistItems_list           (confirm final order, 1 quota)
```

**Concrete calls**:

```jsonc
// 1. Create the playlist.
youtube_playlists_insert({
  "account": ACCOUNT,
  "part": ["snippet", "status"],
  "body": {
    "snippet": {
      "title": "May 2026 picks",
      "description": "Editor selection for May."
    },
    "status": {"privacyStatus": "public"}
  }
})

// 2. Add items, one call per video. position is optional on insert.
youtube_playlistItems_insert({
  "account": ACCOUNT,
  "part": ["snippet"],
  "body": {
    "snippet": {
      "playlistId": PLAYLIST_ID,
      "resourceId": {"kind": "youtube#video", "videoId": VIDEO_ID_1}
    }
  }
})

// 3. To move an existing item, update its position.
//    The position field is 0-indexed.
youtube_playlistItems_update({
  "account": ACCOUNT,
  "part": ["snippet"],
  "body": {
    "id": PLAYLIST_ITEM_ID,
    "snippet": {
      "playlistId": PLAYLIST_ID,
      "resourceId": {"kind": "youtube#video", "videoId": VIDEO_ID_1},
      "position": 0
    }
  }
})

// 4. Verify final order.
youtube_playlistItems_list({
  "account": ACCOUNT,
  "part": ["snippet"],
  "playlistId": PLAYLIST_ID,
  "maxResults": 50
})
```

**Approx. cost**: ~50 quota for the playlist + ~50 per item add + ~50 per reorder. A 10-item playlist costs roughly 550 units if no reorders are needed.

**Error handling**:

- `videoNotFound` on `playlistItems_insert` means the target video is private, deleted, or region-blocked for the channel owner. Skip and continue rather than aborting the whole batch.
- `playlistContainsMaximumNumberOfVideos` (5,000) means the playlist is full. Either start a new one or skip.
- When reordering, send the FULL `snippet` (playlistId, resourceId, position). Sending only the new `position` returns 400.

## Recipe 7: Monitor live chat and ban a user

**Why**: Use this when an agent is acting as an auto-moderator on a live stream: poll the chat for new messages, scan for abuse (LLM, regex, allow-list), and ban the user behind any offending message without removing the broadcast itself.

**Required scopes**:

- `https://www.googleapis.com/auth/youtube.force-ssl`

**Account**: must be the broadcast owner or a configured chat moderator.

**Flow**:

```
youtube_liveBroadcasts_list           (resolve liveChatId, 1 quota)
        │
        ▼  (loop)
youtube_liveChatMessages_list         (poll messages, 5 quota/page)
        │
        ▼  (agent classifies each message)
        │
        ├──► youtube_liveChatMessages_delete   (remove single message, ~50)
        └──► youtube_liveChatBans_insert       (ban author, ~50)
```

**Concrete calls**:

```jsonc
// 1. Resolve the active broadcast's liveChatId.
youtube_liveBroadcasts_list({
  "account": ACCOUNT,
  "part": ["snippet", "status"],
  "id": [BROADCAST_ID]
})
// Returns ...snippet.liveChatId === LIVE_CHAT_ID

// 2. Poll the chat. Respect the server-provided pollingIntervalMillis.
youtube_liveChatMessages_list({
  "account": ACCOUNT,
  "liveChatId": LIVE_CHAT_ID,
  "part": ["snippet", "authorDetails"],
  "maxResults": 200,
  "pageToken": NEXT_PAGE_TOKEN_OR_NULL
})

// 3a. Delete an offending message.
youtube_liveChatMessages_delete({
  "account": ACCOUNT,
  "id": LIVE_CHAT_MESSAGE_ID
})

// 3b. Ban the author. "permanent" bans the user; "temporary" supports banDurationSeconds.
youtube_liveChatBans_insert({
  "account": ACCOUNT,
  "part": ["snippet"],
  "body": {
    "snippet": {
      "liveChatId": LIVE_CHAT_ID,
      "type": "permanent",
      "bannedUserDetails": {"channelId": OFFENDING_CHANNEL_ID}
    }
  }
})
```

**Approx. cost**: ~5 quota per chat page polled, ~50 per delete, ~50 per ban. A two-hour stream polled every 5 seconds is roughly 7,200 units of polling on its own, so budget for it: this is the most quota-hungry workflow on this list if you let it run unattended.

**Error handling**:

- The chat ends when the broadcast ends. After the show, `liveChatMessages_list` returns a 403 `liveChatEnded`. Stop polling.
- Always honor `pollingIntervalMillis` from the previous response. Polling faster gets you throttled and burns extra quota.
- A `banAuthor` action on the broadcast owner returns `forbidden`. Filter the owner's own channelId before issuing bans.
- Temporary bans use `type="temporary"` with `banDurationSeconds`. A ban with both `type="permanent"` and `banDurationSeconds` set is rejected.

## Cross-recipe notes

- **Account aliases**: Every tool takes `account`. That string maps to a stored OAuth token. If the account is missing the scope a recipe needs, the very first call will fail with 403; re-run `youtube-mcp accounts add` with the correct scope set rather than retrying.
- **Quota budgets**: Data API daily quota defaults to 10,000 units per project. Recipe 1 (one upload) burns ~20% of that on its own. Plan accordingly when chaining recipes in the same day.
- **No video removal path**: This server intentionally does not expose a video-deletion tool. If a workflow needs to "take a video down", set `status.privacyStatus="private"` through `youtube_videos_update` instead. The video stays in the account, the public URL stops working, and the action is reversible.
