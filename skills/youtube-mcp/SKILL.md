---
name: youtube-mcp
description: |
  Complete reference for the youtube-mcp server, an MCP that exposes Google's YouTube APIs as
  agent-callable tools. Use this skill whenever the user mentions YouTube, YouTube API, YouTube MCP,
  channel analytics, video analytics, video upload, comment moderation, live broadcast, playlist
  management, subscriptions, captions, monetization, super chat, or membership levels. Also trigger
  on phrases like "upload to YouTube", "post YouTube comment", "schedule YouTube live",
  "fetch YouTube analytics", "manage YouTube playlist", "moderate YouTube comments", or any task
  involving the Data API v3, Analytics API v2, or Reporting API v1. Even casual mentions of
  YouTube or "the YT channel" should consult this skill before calling any youtube_* tool.
voice_triggers:
  - upload to YouTube
  - post YouTube comment
  - schedule YouTube live
  - fetch YouTube analytics
  - manage YouTube playlist
  - moderate YouTube comments
  - check YouTube quota
  - YouTube channel report
---

# youtube-mcp

The youtube-mcp server exposes Google's YouTube platform as a set of MCP tools that any compatible
agent can call. It wraps three official APIs behind a single, brand-account-aware surface so an
agent can list videos, post comments, fetch analytics reports, or manage live broadcasts without
juggling raw HTTP calls or OAuth refresh logic.

This file is the entry point. Read the sections below before invoking any tool. Detailed per-tool
parameters and quota costs live in the [References](#references) and [Workflow Guides](#workflow-guides)
linked at the bottom.

## What This Skill Provides

youtube-mcp covers three distinct Google API surfaces. Each surface answers different questions and
costs quota differently, so picking the right one matters.

1. **YouTube Data API v3** (`youtube_*` tools). The read/write surface for channel content. Lists
   and edits videos, playlists, comments, captions, channel sections, subscriptions, live broadcasts,
   live chat, super chat events, members, and abuse reports. This is where most day-to-day work
   happens. Quota costs vary per call from 1 unit (simple list) to 1600 units (video upload).
2. **YouTube Analytics API v2** (`analytics_*` tools). The interactive reporting surface. Runs ad-hoc
   queries against channel performance metrics (views, watch time, average view duration, revenue
   when monetized) sliced by dimensions like day, country, traffic source, or device type. Best when
   the agent needs an answer right now and the date range is bounded.
3. **YouTube Reporting API v1** (`reporting_*` tools). The bulk export surface. Schedules recurring
   report jobs that drop large CSV files into Google's bucket each day. Best when the agent is
   pulling months of granular data or feeding a downstream warehouse. Reports lag by one to three
   days but contain far more rows than Analytics queries return.

All three surfaces share one authentication model, one quota pool per Google project, and the same
`account` selection convention described below.

## Tool Naming Convention

Every tool follows the pattern `{api}_{resource}_{verb}`, lowercase, snake_case. The verb maps
directly to the underlying Google method.

```
youtube_videos_list          # Data API v3, videos.list
youtube_videos_insert        # Data API v3, videos.insert
youtube_videos_update        # Data API v3, videos.update
youtube_comments_insert      # Data API v3, comments.insert
youtube_liveBroadcasts_bind  # Data API v3, liveBroadcasts.bind
analytics_reports_query      # Analytics API v2, reports.query
reporting_jobs_create        # Reporting API v1, jobs.create
reporting_reports_list       # Reporting API v1, reports.list
```

### Tool families (25)

| Family | API | Module |
|--------|-----|--------|
| activities | Data v3 | tools/activities.py |
| captions | Data v3 | tools/captions.py |
| channelBanners | Data v3 | tools/channel_banners.py |
| channelSections | Data v3 | tools/channel_sections.py |
| channels | Data v3 | tools/channels.py |
| comments | Data v3 | tools/comments.py |
| commentThreads | Data v3 | tools/comment_threads.py |
| i18nLanguages, i18nRegions | Data v3 | tools/i18n.py |
| liveBroadcasts | Data v3 | tools/live_broadcasts.py |
| liveChatMessages, liveChatBans, liveChatModerators | Data v3 | tools/live_chat.py |
| liveStreams | Data v3 | tools/live_streams.py |
| members | Data v3 | tools/members.py |
| membershipsLevels | Data v3 | tools/memberships_levels.py |
| playlistItems | Data v3 | tools/playlist_items.py |
| playlists | Data v3 | tools/playlists.py |
| search | Data v3 | tools/search.py |
| subscriptions | Data v3 | tools/subscriptions.py |
| superChatEvents | Data v3 | tools/super_chat.py |
| thumbnails | Data v3 | tools/thumbnails.py |
| videoAbuseReportReasons, videoCategories | Data v3 | tools/video_meta.py |
| videos (list, insert, update, rate, getRating, reportAbuse) | Data v3 | tools/videos.py |
| watermarks | Data v3 | tools/watermarks.py |
| analytics.reports | Analytics v2 | tools/analytics.py |
| reporting.jobs, reporting.reportTypes, reporting.reports | Reporting v1 | tools/reporting.py |

## Critical Constraints

> **NO `videos.delete` tool exists.**
>
> The youtube-mcp server does NOT expose `youtube.videos.delete`. The delete-video endpoint is
> unavailable by design and is programmatically absent from the framework: there is no
> `youtube_videos_delete` tool, no gated variant, no hidden override.
>
> **To remove a video from public view, set its `privacyStatus` to `private` (or `unlisted`)
> via `youtube_videos_update`.** This keeps the video record, watch history, and any embedded
> references intact while making the video invisible to non-owners.
>
> If a user asks the agent to "delete a video on YouTube", the correct response is to call
> `youtube_videos_update` with `privacyStatus=private` and tell the user the video has been hidden
> rather than destroyed. Hard deletion can only be performed by the channel owner in Studio.

Other things to know:

- **All mutating tools are gated.** Inserts, updates, deletes (other than the missing one), bans,
  rates, and uploads route through a MutatingGuard. The guard checks the env var
  `YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE` against the requested `account`. If the account isn't on
  the allow-list, the call returns a typed error before any HTTP request goes out.
- **No token contents in logs.** Refresh tokens, access tokens, and storage paths must not be echoed
  back to the agent under any circumstance. If a tool returns an auth error, it surfaces a typed
  message and a remediation hint (typically "run `youtube-mcp auth add <handle>`") and nothing else.
- **No bypass paths.** There is no "raw HTTP" tool, no `youtube_execute_arbitrary`, no shell escape.
  Every API touch goes through a typed tool with explicit parameters.

## Account Selection

youtube-mcp is multi-brand-account first-class. A single MCP server instance can hold credentials
for many YouTube channels, and every tool call must say which one to use.

**Every tool takes an `account: str` parameter** (always the first or second positional argument
after `ctx`). The value is the brand-account *handle key*, not the channel ID, channel title, or
Google email. Handles are short, agent-friendly strings like `"main"`, `"second"`, `"podcast"`, or
`"client-acme"`.

```python
# List the most recent 10 videos on the "main" channel
youtube_videos_list(account="main", part=["snippet", "statistics"], mine=True, max_results=10)

# Post a reply on the "podcast" channel
youtube_comments_insert(account="podcast", parent_id="UgxXYZ...", text_original="Thanks!")

# Pull last 28 days of views for the "client-acme" channel
analytics_reports_query(
    account="client-acme",
    start_date="2026-04-21",
    end_date="2026-05-18",
    metrics=["views", "estimatedMinutesWatched"],
    dimensions=["day"],
)
```

### Discovering available accounts

The server exposes a read-only MCP resource that lists configured handles:

```
youtube://accounts        # all registered brand-account handles
```

The agent should read this resource before guessing handle names. The resource returns handles only,
never tokens or credentials.

### Adding a new account

If the user wants to register a new channel, point them at the CLI:

```
youtube-mcp auth add <handle>
```

This opens an OAuth flow in the browser. Once the user grants access, the refresh token is stored
in the OS keyring under the chosen handle. From that point on, any tool call with
`account="<handle>"` works. The MCP server itself never collects credentials interactively, so the
agent cannot trigger the auth flow on the user's behalf, it can only suggest the command.

## Quota Awareness

The Data API v3 charges quota units per call. The default per-project ceiling is 10,000 units per
day. Burning the budget early breaks every subsequent call until midnight Pacific.

Approximate costs by call category:

| Call type | Typical cost |
|-----------|--------------|
| Simple list (videos, playlists, comments) | 1 unit |
| Search list | 100 units |
| Insert (comment, playlist item, subscription) | 50 units |
| Update (video metadata, playlist) | 50 units |
| Video upload (insert) | 1600 units |
| Caption insert | 400 units |
| Thumbnail set | 50 units |

The Analytics API and Reporting API use separate quotas and are much harder to exhaust under
normal use.

### Checking remaining quota

The server exposes a per-account quota resource:

```
youtube://quota/{account}    # remaining units and last-reset timestamp
```

Before launching a chain of expensive calls (search loops, batch uploads, bulk metadata edits), read
this resource and abort early if the remaining budget can't cover the plan.

## Long-Running Operations

Some tools take seconds or minutes to complete, not milliseconds. They accept the MCP `Context`
implicitly and report progress through it so the agent (and the user) can see what's happening.

- **`youtube_videos_insert`** drives a resumable upload in 8 MiB chunks. After each chunk it calls
  `ctx.report_progress(progress=bytes_sent, total=total_bytes)`. For a 500 MB video on a typical
  connection, expect 30 to 90 seconds and roughly 60 progress events.
- **`reporting_jobs_create`** schedules a recurring export. The job itself returns instantly, but
  the first report file arrives 24 to 48 hours later. Poll `reporting_reports_list` after that delay.
- **`youtube_liveBroadcasts_transition`** changes broadcast lifecycle state (testing → live → complete).
  Transitions can take 15 to 60 seconds while YouTube reconfigures the stream; the tool blocks until
  the new state is confirmed.

If the agent runs in a context that surfaces progress to the user (claude-cli, Claude Desktop with
progress UI, Cursor), let those events flow through. If running headless, the progress events are
still emitted but can be safely ignored.

## References

Detailed per-resource documentation lives in the `reference/` directory next to this file. Read the
right reference before calling tools in that area, especially for resources with quirky parameters
(search, captions, liveBroadcasts).

- [reference/data-api.md](reference/data-api.md) — every YouTube Data API v3 tool, resource by
  resource: activities, captions, channels, channelBanners, channelSections, comments,
  commentThreads, i18n, members, memberships, playlists, playlistItems, search, subscriptions,
  videos, video assets, video meta, liveBroadcasts, liveStreams, liveChat, superChatEvents, abuse,
  tests. Each tool entry shows signature, quota cost, OAuth scopes, behavior, and pitfalls.
- [reference/analytics-api.md](reference/analytics-api.md) — Analytics API v2 query surface.
  Supported metrics, dimensions, filters, sort keys, and the rules for combining them. Includes
  the metric-dimension compatibility matrix and worked query examples.
- [reference/reporting-api.md](reference/reporting-api.md) — Reporting API v1 job and report
  lifecycle. How to discover report types, create a job, poll for completed reports, and download
  the CSV files. Includes the canonical report-type catalog.

## Workflow Guides

End-to-end recipes for common multi-tool tasks. Open these when the user's request crosses several
tool families.

- [guides/upload-and-publish.md](guides/upload-and-publish.md) — upload a local video file, set
  metadata (title, description, tags, category, default language), attach a thumbnail, add captions
  in one or more languages, and either publish immediately or schedule for later.
- [guides/comment-moderation.md](guides/comment-moderation.md) — fetch recent comment threads,
  classify them, hide spam, reply to questions, ban repeat offenders from live chat, and report
  abuse to YouTube's review queue.

Both guides assume the reader has already read this SKILL.md and one of the reference files above.

## Quick Sanity Checklist

Before invoking a youtube-mcp tool, confirm:

1. The user's intent maps to a real tool family in the table above (not `videos.delete`, see
   [Critical Constraints](#critical-constraints)).
2. The `account` handle is known. If unsure, read `youtube://accounts` first.
3. Remaining quota is enough. For expensive call chains, read `youtube://quota/{account}` first.
4. If the tool mutates state, the target account is on the `YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE`
   allow-list. If not, surface the gating error to the user instead of retrying.
5. For long-running operations, the calling environment is one that surfaces progress, or the agent
   is prepared to wait through the operation silently.
