# YouTube Analytics API: Tool Reference

The `youtube_analytics_*` tools wrap the YouTube Analytics API v2 (`youtubeAnalytics:v2`). They split into three groups:

1. **Reports**: `reports.query` (run an analytics query) and `reports.describe` (curated dimension/metric matrix for agent guidance).
2. **Groups**: CRUD for analytics groups (create, list, update, delete a saved bag of channels, videos, playlists, or assets).
3. **Group items**: list, add, or remove members of a group.

All tools take an `account` argument that resolves to a stored OAuth profile via the account manager. Set `on_behalf_of_content_owner` only when acting as a CMS partner.

---

## Scopes

The decorator on each tool declares the OAuth scopes it needs. The framework uses these to pick (or reject) the active account.

| Tool family | Scope constant | OAuth scope URL |
|---|---|---|
| `reports.query`, `reports.describe`, `groups.list`, `groupItems.list` | `ANALYTICS_READONLY` | `https://www.googleapis.com/auth/yt-analytics.readonly` |
| `groups.insert/update/delete`, `groupItems.insert/delete` | `MANAGE` | `https://www.googleapis.com/auth/youtube` |
| Monetary metrics inside `reports.query` (e.g. `estimatedRevenue`, `cpm`) | request-time | `https://www.googleapis.com/auth/yt-analytics-monetary.readonly` (`ANALYTICS_MONETARY`) |

The `reports.query` decorator only declares `ANALYTICS_READONLY`. When the `metrics` string includes a monetary metric, the underlying credential must also carry `ANALYTICS_MONETARY` or Google returns a `403`. Provision both scopes during OAuth consent if you plan to fetch revenue reports.

---

## `analytics_reports_query`

**Tool name**: `youtube_analytics_reports_query`
**API method**: `youtubeAnalytics.reports.query`
**Scopes**: `ANALYTICS_READONLY` (plus `ANALYTICS_MONETARY` at the credential level for revenue metrics)
**Mutating**: no

```text
youtube_analytics_reports_query(
    account: str,
    ids: str,                       # "channel==MINE", "channel==UC...", "contentOwner==..."
    metrics: str,                   # comma-separated metric names
    start_date: str,                # "YYYY-MM-DD"
    end_date: str,                  # "YYYY-MM-DD"
    dimensions: str | None = None,
    filters: str | None = None,     # e.g. "country==US;video==abc123"
    max_results: int | None = None,
    sort: str | None = None,        # e.g. "-views"
    start_index: int | None = None,
    currency: str | None = None,    # ISO 4217, e.g. "USD"
    include_historical_channel_data: bool | None = None,
    extra_params: dict[str, object] | None = None,
) -> dict
```

One-line example:

```python
youtube_analytics_reports_query(account="main", ids="channel==MINE", metrics="views,estimatedMinutesWatched", start_date="2026-05-12", end_date="2026-05-18", dimensions="day")
```

Behavior notes:

- The tool is a thin passthrough to `youtubeAnalytics.reports.query`. It does **not** rewrite or validate metric names.
- Before the call, it checks the requested `(ids, metrics, dimensions)` triple against the curated matrix in `src/youtube_mcp/data/analytics_dim_metric_matrix.py`. If the combination is not in the matrix, the tool emits an MCP warning (`reports.query combination is not in the bundled ... matrix; forwarding to Google.`) and still runs the query. Treat the warning as a hint, not a hard rejection: rare combinations can still be valid.
- `extra_params` lets you pass any future Analytics parameters the wrapper does not name explicitly. Keys are merged into the request after the named arguments.

---

## `analytics_reports_describe`

**Tool name**: `youtube_analytics_reports_describe`
**API method**: `youtubeAnalytics.reports.query` (declared for accounting; no HTTP request is made)
**Scopes**: `ANALYTICS_READONLY`
**Mutating**: no

```text
youtube_analytics_reports_describe(account: str) -> dict
```

One-line example:

```python
youtube_analytics_reports_describe(account="main")
```

What it returns:

The tool calls `describe_analytics_matrix()` and returns the curated dimension/metric matrix bundled with this MCP server. The shape is:

```json
{
  "sources": [
    "https://developers.google.com/youtube/analytics/channel_reports",
    "https://developers.google.com/youtube/analytics/content_owner_reports",
    "https://developers.google.com/youtube/analytics/dimensions",
    "https://developers.google.com/youtube/analytics/metrics"
  ],
  "reports": [
    {
      "report_type": "channel" | "contentOwner",
      "name": "Channel core activity and engagement",
      "ids_prefixes": ["channel=="],
      "dimensions": ["day", "month", "country", "..."],
      "metrics":    ["views", "estimatedMinutesWatched", "..."]
    },
    ...
  ]
}
```

Use this as the on-ramp. Call `describe` first when you need to decide which dimensions and metrics are safe to combine, then call `query` with values drawn from the same report row. The matrix is sourced from the URLs in `sources` and is condensed; rare or deprecated combinations are intentionally omitted to keep the agent's choices high-signal.

---

## Curated dimension / metric matrix

The matrix lives at `src/youtube_mcp/data/analytics_dim_metric_matrix.py`. Each row groups dimensions and metrics that Google documents as compatible for a single `reports.query` call.

### Channel reports (`ids="channel==MINE"` or `ids="channel==UC..."`)

| Report family | Allowed dimensions (any subset) | Allowed metrics (any subset) |
|---|---|---|
| Core activity and engagement | `day`, `month`, `country`, `province`, `video`, `playlist`, `group`, `subscribedStatus`, `youtubeProduct`, `liveOrOnDemand`, `creatorContentType`, `sharingService`, `insightPlaybackLocationType`, `insightPlaybackLocationDetail`, `insightTrafficSourceType`, `insightTrafficSourceDetail`, `deviceType`, `operatingSystem` | `views`, `redViews`, `estimatedMinutesWatched`, `estimatedRedMinutesWatched`, `averageViewDuration`, `averageViewPercentage`, `comments`, `likes`, `dislikes`, `shares`, `subscribersGained`, `subscribersLost`, `videosAddedToPlaylists`, `videosRemovedFromPlaylists`, plus revenue: `estimatedRevenue`, `estimatedAdRevenue`, `grossRevenue`, `estimatedRedPartnerRevenue`, `monetizedPlaybacks`, `playbackBasedCpm`, `cpm`, `adImpressions` |
| Demographics | `ageGroup`, `gender`, `video`, `group` | `viewerPercentage` |
| Playlist performance | `playlist`, `group`, `day`, `month`, `country`, `province`, `video` | `views`, `estimatedMinutesWatched`, `averageViewDuration`, `playlistStarts`, `viewsPerPlaylistStart`, `averageTimeInPlaylist` |
| Audience retention | `elapsedVideoTimeRatio`, `video`, `group` | `audienceWatchRatio`, `relativeRetentionPerformance` |
| Annotations, cards, end screens | `video`, `group`, `day`, `month` | `annotationImpressions`, `annotationClickableImpressions`, `annotationClicks`, `annotationClickThroughRate`, `annotationClosableImpressions`, `annotationCloses`, `annotationCloseRate`, `cardImpressions`, `cardClicks`, `cardClickRate`, `cardTeaserImpressions`, `cardTeaserClicks`, `cardTeaserClickRate`, `endScreenElementImpressions`, `endScreenElementClicks`, `endScreenElementClickRate` |

### Content owner reports (`ids="contentOwner==<CMS_ID>"`)

| Report family | Allowed dimensions | Allowed metrics |
|---|---|---|
| Core activity and engagement | `day`, `month`, `channel`, `video`, `asset`, `assetType`, `claimedStatus`, `uploaderType`, `country`, `province`, `playlist`, `group`, `subscribedStatus`, `youtubeProduct`, `liveOrOnDemand`, `creatorContentType`, `insightPlaybackLocationType`, `insightPlaybackLocationDetail`, `insightTrafficSourceType`, `insightTrafficSourceDetail`, `deviceType`, `operatingSystem` | same core + revenue metrics as the channel core row |
| Demographics | `ageGroup`, `gender`, `channel`, `video`, `group` | `viewerPercentage` |
| Playlist performance | `playlist`, `group`, `channel`, `video`, `day`, `month`, `country`, `province` | `views`, `estimatedMinutesWatched`, `averageViewDuration`, `playlistStarts`, `viewsPerPlaylistStart`, `averageTimeInPlaylist` |
| Audience retention | `elapsedVideoTimeRatio`, `video`, `group`, `channel` | `audienceWatchRatio`, `relativeRetentionPerformance` |
| Annotations, cards, end screens | `video`, `group`, `channel`, `day`, `month` | same annotation/card/end-screen metrics as the channel row |

### Rules of thumb

- Combine dimensions and metrics from **one row only**. Mixing across rows (for example, retention metrics with traffic-source dimensions) is what triggers the "combination is not in the bundled matrix" warning.
- `group` as a dimension means "an Analytics group". To filter by a specific group ID, use `filters="group==GROUP_ID"`, not the `group` dimension.
- Revenue metrics (`estimatedRevenue`, `cpm`, `adImpressions`, `estimatedAdRevenue`, `grossRevenue`, `estimatedRedPartnerRevenue`, `monetizedPlaybacks`, `playbackBasedCpm`) require the `ANALYTICS_MONETARY` scope on the credential. Without it, Google returns a 403 even if the matrix accepts the combo.
- Date ranges must be `YYYY-MM-DD`. Most reports support up to 2 years of history; demographics and retention reports may have shorter windows.

---

## `analytics_groups_list`

**Tool name**: `youtube_analytics_groups_list`
**API method**: `youtubeAnalytics.groups.list`
**Scopes**: `ANALYTICS_READONLY`
**Mutating**: no

```text
youtube_analytics_groups_list(
    account: str,
    id: str | None = None,                     # comma-separated group IDs
    mine: bool | None = None,                  # True to list the caller's groups
    page_token: str | None = None,
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

One-line example:

```python
youtube_analytics_groups_list(account="main", mine=True)
```

Either `id` or `mine` should be set, matching the Analytics API contract.

---

## `analytics_groups_insert`

**Tool name**: `youtube_analytics_groups_insert`
**API method**: `youtubeAnalytics.groups.insert`
**Scopes**: `MANAGE` (mutating)
**Mutating**: yes

```text
youtube_analytics_groups_insert(
    account: str,
    group_body: dict,                          # full Group resource
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

One-line example:

```python
youtube_analytics_groups_insert(account="main", group_body={"snippet": {"title": "Top tutorials"}, "contentDetails": {"itemType": "youtube#video"}})
```

`contentDetails.itemType` must match the items you plan to add. Allowed values: `youtube#channel`, `youtube#video`, `youtube#playlist`, `youtubePartner#asset`.

---

## `analytics_groups_update`

**Tool name**: `youtube_analytics_groups_update`
**API method**: `youtubeAnalytics.groups.update`
**Scopes**: `MANAGE` (mutating)
**Mutating**: yes

```text
youtube_analytics_groups_update(
    account: str,
    group_body: dict,                          # must include id and snippet
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

One-line example:

```python
youtube_analytics_groups_update(account="main", group_body={"id": "GROUP_ID", "snippet": {"title": "Renamed group"}})
```

You can only mutate `snippet.title` on an existing group. `contentDetails.itemType` is fixed at insert time.

---

## `analytics_groups_delete`

**Tool name**: `youtube_analytics_groups_delete`
**API method**: `youtubeAnalytics.groups.delete`
**Scopes**: `MANAGE` (mutating)
**Mutating**: yes

```text
youtube_analytics_groups_delete(
    account: str,
    id: str,                                   # group ID
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

One-line example:

```python
youtube_analytics_groups_delete(account="main", id="GROUP_ID")
```

Returns an empty body on success. The group's items are removed at the same time.

---

## `analytics_groupItems_list`

**Tool name**: `youtube_analytics_groupItems_list`
**API method**: `youtubeAnalytics.groupItems.list`
**Scopes**: `ANALYTICS_READONLY`
**Mutating**: no

```text
youtube_analytics_groupItems_list(
    account: str,
    group_id: str,
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

One-line example:

```python
youtube_analytics_groupItems_list(account="main", group_id="GROUP_ID")
```

---

## `analytics_groupItems_insert`

**Tool name**: `youtube_analytics_groupItems_insert`
**API method**: `youtubeAnalytics.groupItems.insert`
**Scopes**: `MANAGE` (mutating)
**Mutating**: yes

```text
youtube_analytics_groupItems_insert(
    account: str,
    group_item_body: dict,                     # full GroupItem resource
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

One-line example:

```python
youtube_analytics_groupItems_insert(account="main", group_item_body={"groupId": "GROUP_ID", "resource": {"kind": "youtube#video", "id": "dQw4w9WgXcQ"}})
```

The `resource.kind` must match the group's `contentDetails.itemType`. Adding a `youtube#playlist` to a video group fails.

---

## `analytics_groupItems_delete`

**Tool name**: `youtube_analytics_groupItems_delete`
**API method**: `youtubeAnalytics.groupItems.delete`
**Scopes**: `MANAGE` (mutating)
**Mutating**: yes

```text
youtube_analytics_groupItems_delete(
    account: str,
    id: str,                                   # group item ID, not the resource ID
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

One-line example:

```python
youtube_analytics_groupItems_delete(account="main", id="GROUP_ITEM_ID")
```

The `id` is the membership ID returned by `groupItems_list` or `groupItems_insert`, not the underlying video / channel / playlist ID.

---

## Sample queries

Each sample shows the full `youtube_analytics_reports_query` call with concrete parameters and a one-line note on what it returns.

### 1. Views by day for the last 7 days

```python
youtube_analytics_reports_query(
    account="main",
    ids="channel==MINE",
    metrics="views",
    start_date="2026-05-12",
    end_date="2026-05-18",
    dimensions="day",
    sort="day",
)
```

Returns one row per day with `views`. Row order follows the `sort` parameter.

### 2. Top 10 videos by watch time, last 28 days

```python
youtube_analytics_reports_query(
    account="main",
    ids="channel==MINE",
    metrics="estimatedMinutesWatched,views,averageViewDuration",
    start_date="2026-04-21",
    end_date="2026-05-18",
    dimensions="video",
    sort="-estimatedMinutesWatched",
    max_results=10,
)
```

Returns 10 rows of `(video, estimatedMinutesWatched, views, averageViewDuration)`, highest watch time first.

### 3. Subscriber gains by traffic source

```python
youtube_analytics_reports_query(
    account="main",
    ids="channel==MINE",
    metrics="subscribersGained,subscribersLost",
    start_date="2026-04-01",
    end_date="2026-04-30",
    dimensions="insightTrafficSourceType",
    sort="-subscribersGained",
)
```

Returns one row per traffic-source type (e.g. `YT_SEARCH`, `SUGGESTED_VIDEO`, `EXTERNAL`).

### 4. Revenue by month (requires `ANALYTICS_MONETARY` scope)

```python
youtube_analytics_reports_query(
    account="main",
    ids="channel==MINE",
    metrics="estimatedRevenue,estimatedAdRevenue,cpm,monetizedPlaybacks",
    start_date="2026-01-01",
    end_date="2026-04-30",
    dimensions="month",
    currency="USD",
    sort="month",
)
```

Returns one row per month with revenue, CPM, and monetized playbacks. If the credential is missing `ANALYTICS_MONETARY`, the call returns 403.

### 5. Country breakdown for a single video

```python
youtube_analytics_reports_query(
    account="main",
    ids="channel==MINE",
    metrics="views,estimatedMinutesWatched,averageViewDuration",
    start_date="2026-03-01",
    end_date="2026-04-30",
    dimensions="country",
    filters="video==dQw4w9WgXcQ",
    sort="-views",
    max_results=25,
)
```

Returns the top 25 countries for that video, sorted by views.

### 6. Audience retention curve for a video

```python
youtube_analytics_reports_query(
    account="main",
    ids="channel==MINE",
    metrics="audienceWatchRatio,relativeRetentionPerformance",
    start_date="2026-03-01",
    end_date="2026-04-30",
    dimensions="elapsedVideoTimeRatio",
    filters="video==dQw4w9WgXcQ",
    sort="elapsedVideoTimeRatio",
)
```

Returns the retention curve (0.0 to 1.0 along the video) as one row per ratio bucket.

### 7. Demographics for a video

```python
youtube_analytics_reports_query(
    account="main",
    ids="channel==MINE",
    metrics="viewerPercentage",
    start_date="2026-04-01",
    end_date="2026-04-30",
    dimensions="ageGroup,gender",
    filters="video==dQw4w9WgXcQ",
)
```

Returns rows of `(ageGroup, gender, viewerPercentage)` that sum to 100.

---

## Group workflow

Groups let you run a single `reports.query` over a curated set of videos, channels, playlists, or assets. The workflow has three steps.

### 1. Create the group

```python
group = youtube_analytics_groups_insert(
    account="main",
    group_body={
        "snippet": {"title": "Q2 tutorial videos"},
        "contentDetails": {"itemType": "youtube#video"},
    },
)
group_id = group["id"]
```

### 2. Add items

```python
for video_id in ("dQw4w9WgXcQ", "9bZkp7q19f0", "kJQP7kiw5Fk"):
    youtube_analytics_groupItems_insert(
        account="main",
        group_item_body={
            "groupId": group_id,
            "resource": {"kind": "youtube#video", "id": video_id},
        },
    )
```

Verify with:

```python
youtube_analytics_groupItems_list(account="main", group_id=group_id)
```

### 3. Query the group

Reference the group through the `filters` parameter on `reports.query`. The `group` dimension is not what you want here; use the filter:

```python
youtube_analytics_reports_query(
    account="main",
    ids="channel==MINE",
    metrics="views,estimatedMinutesWatched",
    start_date="2026-04-01",
    end_date="2026-04-30",
    dimensions="day",
    filters=f"group=={group_id}",
    sort="day",
)
```

To drop the group later:

```python
youtube_analytics_groups_delete(account="main", id=group_id)
```

Deleting a group also removes its items.

---

## Pointers and sources

- Curated matrix module: `src/youtube_mcp/data/analytics_dim_metric_matrix.py`
- Reports tools: `src/youtube_mcp/tools/analytics_reports.py`
- Group / group-item tools: `src/youtube_mcp/tools/analytics_groups.py`
- Google docs: see the `sources` array returned by `analytics_reports_describe`. It includes the channel reports, content-owner reports, dimensions, and metrics reference pages.

When in doubt about a combination, call `analytics_reports_describe` first, find the row that matches your `ids` and the metric you want, then pick dimensions from the same row.
