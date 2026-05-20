# YouTube Reporting API v1 reference

The Reporting API is YouTube's bulk CSV export channel. Subscribe to a report type once, wait roughly a day, then pull CSV files day after day. It is not a real-time query tool. Use it when you need wide historical coverage, raw row-level data, or both. For ad-hoc slices of recent metrics, reach for the Analytics API instead (see the "When to use Reporting vs Analytics" guide at the bottom of this file).

All Reporting tools require the `https://www.googleapis.com/auth/yt-analytics.readonly` scope. Every tool takes `account` as its first argument and supports an optional `on_behalf_of_content_owner` parameter for CMS/partner accounts.

## Lifecycle (text diagram)

```
1. youtube_reporting_reportTypes_list   (browse the catalog, cached 24h)
        |
        v
2. youtube_reporting_jobs_create        (subscribe to one report type)
        |
        v
3. WAIT ~24 hours                       (Google's SLA is "approximately daily")
        |
        v
4. youtube_reporting_reports_list       (poll until a report appears)
        |
        v
5. youtube_reporting_reports_download   (stream the CSV to disk)
        |
        v
6. (next day) repeat from step 4        (one job produces one CSV per day)
```

The job is permanent until you delete it. Once subscribed, YouTube keeps generating one report per day going forward, plus a backfill window of around 60 days. You only call `jobs_create` once per report type per account.

## Tool reference

### youtube_reporting_reportTypes_list (cached, 24h TTL)

Lists the report types available to the authenticated account. Results are cached for 24 hours since the catalog rarely changes.

```python
youtube_reporting_reportTypes_list(
    account: str,
    include_system_managed: bool | None = None,
    on_behalf_of_content_owner: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
) -> dict
```

Scopes: `yt-analytics.readonly`. Example: `youtube_reporting_reportTypes_list(account="main", include_system_managed=False)` returns the catalog of channel-owner report types (views, traffic source, demographics, etc.).

### youtube_reporting_jobs_list

Lists the active reporting jobs for the account.

```python
youtube_reporting_jobs_list(
    account: str,
    include_system_managed: bool | None = None,
    on_behalf_of_content_owner: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
) -> dict
```

Scopes: `yt-analytics.readonly`. Example: `youtube_reporting_jobs_list(account="main")` shows every job already subscribed, with its `id` and `reportTypeId`.

### youtube_reporting_jobs_get

Fetches one reporting job by id. Use this when you already have a `job_id` and need fresh metadata without listing every job.

```python
youtube_reporting_jobs_get(
    account: str,
    job_id: str,
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

Scopes: `yt-analytics.readonly`. Quota cost: 1. Example: `youtube_reporting_jobs_get(account="main", job_id="abc123")` returns one job's metadata.

### youtube_reporting_jobs_create (mutating)

Subscribes the account to a report type. Pass a job body whose `reportTypeId` matches a value from `reportTypes_list`.

```python
youtube_reporting_jobs_create(
    account: str,
    job_body: dict,
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

Scopes: `yt-analytics.readonly` (the API ignores this and writes anyway). Example: `youtube_reporting_jobs_create(account="main", job_body={"reportTypeId": "channel_basic_a2", "name": "daily-views"})` creates the subscription and returns the new `jobId`.

### youtube_reporting_jobs_delete (mutating)

Cancels a job. New reports stop being generated, but existing reports stay downloadable until their normal expiration.

```python
youtube_reporting_jobs_delete(
    account: str,
    job_id: str,
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

Scopes: `yt-analytics.readonly`. Example: `youtube_reporting_jobs_delete(account="main", job_id="abc123")` removes the subscription.

### youtube_reporting_reports_list

Lists the CSV reports a job has produced. Each report has a `downloadUrl`, a `startTime`, and an `endTime`. Use the time filters to scan a date window without paging the entire history.

```python
youtube_reporting_reports_list(
    account: str,
    job_id: str,
    created_after: str | None = None,
    start_time_at_or_after: str | None = None,
    start_time_before: str | None = None,
    on_behalf_of_content_owner: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
) -> dict
```

Scopes: `yt-analytics.readonly`. Example: `youtube_reporting_reports_list(account="main", job_id="abc123", created_after="2026-05-01T00:00:00Z")` returns reports generated this month.

### youtube_reporting_reports_get

Fetches the metadata for a single report by id. Useful when you've already cached a `reportId` and just want the fresh `downloadUrl`.

```python
youtube_reporting_reports_get(
    account: str,
    job_id: str,
    report_id: str,
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

Scopes: `yt-analytics.readonly`. Example: `youtube_reporting_reports_get(account="main", job_id="abc123", report_id="r42")` returns one report's metadata.

### youtube_reporting_reports_download (CSV download helper)

Streams the CSV body to disk in 1 MB chunks. `output_path` must not already exist (the tool refuses to overwrite). Returns the absolute path on disk as a string. Progress is reported through the MCP `Context` when one is supplied.

```python
youtube_reporting_reports_download(
    account: str,
    download_url: str,
    output_path: str,
) -> str
```

Scopes: `yt-analytics.readonly`. Quota cost: 0. Example: `youtube_reporting_reports_download(account="main", download_url=report["downloadUrl"], output_path="/tmp/views-2026-05-18.csv")` writes the CSV and returns `/tmp/views-2026-05-18.csv`.

### youtube_reporting_wait_for_next_report

Polls `reports.list` until a report newer than `since` appears for a job, then returns the first report metadata dictionary. Use short `poll_interval_seconds` values in tests and long values in production so you do not spin on the Reporting API's daily cadence.

```python
youtube_reporting_wait_for_next_report(
    account: str,
    job_id: str,
    since: str,
    timeout_seconds: int = 86400,
    poll_interval_seconds: int = 300,
    on_behalf_of_content_owner: str | None = None,
) -> dict
```

Scopes: `yt-analytics.readonly`. Quota cost: 0. Example: `youtube_reporting_wait_for_next_report(account="main", job_id="abc123", since="2026-05-18T00:00:00Z")` waits for the next generated CSV report.

Notes on `output_path`:

1. The path is opened in binary write mode and the response body streams in directly.
2. If the file already exists, the call raises `FileExistsError` instead of clobbering it. Pick a fresh path per report (the `reportId` or `startTime` makes a good filename component).
3. The return value is the same path you passed in, normalized through `pathlib.Path`. Use it as the canonical reference for downstream CSV parsing.

## Bulk CSV workflow

The standard daily-bulk-report pattern:

```python
types = youtube_reporting_reportTypes_list(account="main")
job = youtube_reporting_jobs_create(
    account="main",
    job_body={"reportTypeId": "channel_basic_a2", "name": "daily-views"},
)
job_id = job["id"]

# ... 24 hours later, or any time after the first report lands ...

reports = youtube_reporting_reports_list(account="main", job_id=job_id)
for report in reports.get("reports", []):
    csv_path = youtube_reporting_reports_download(
        account="main",
        download_url=report["downloadUrl"],
        output_path=f"/data/reports/{report['id']}.csv",
    )
    # csv_path is now ready for pandas, duckdb, etc.
```

Operational notes:

1. The first report typically appears 24 to 48 hours after `jobs_create`. Google describes the cadence as "approximately daily" and does not commit to a tighter SLA.
2. Once the job is running, each new report covers one UTC day. Filter `reports_list` with `created_after` to page only fresh files.
3. Download URLs are short-lived signed URLs. If a URL fails, call `reports_get` to mint a new one.
4. The CSV is gzip-encoded on the wire but written to disk as plain CSV by the download helper.

## Report type catalog (top channel-owner types)

The catalog is large. These are the most common types for channel owners:

1. **`channel_basic_a2`**: views, watch time, average view duration, subscribers gained/lost. The default "how is the channel doing" file. Dimensions: `video`, `day`. Metrics: `views`, `watch_time_minutes`, `average_view_duration_seconds`, `subscribers_gained`, `subscribers_lost`.
2. **`channel_traffic_source_a2`**: where viewers came from. Dimensions: `video`, `day`, `traffic_source_type`, `traffic_source_detail`. Metrics: `views`, `watch_time_minutes`. Use it to attribute views to search, suggested videos, browse, external, etc.
3. **`channel_demographics_a1`**: viewer age and gender breakdown. Dimensions: `video`, `day`, `age_group`, `gender`. Metric: `views_percentage`.
4. **`channel_playback_location_a2`**: embedded vs watch page vs mobile app. Dimensions: `video`, `day`, `playback_location_type`, `playback_location_detail`. Metrics: `views`, `watch_time_minutes`.
5. **`channel_device_os_a2`**: viewer device type and operating system. Dimensions: `video`, `day`, `device_type`, `operating_system`. Metrics: `views`, `watch_time_minutes`.
6. **`channel_subtitles_a2`**: caption usage. Dimensions: `video`, `day`, `subtitle_language`, `subtitle_enabled`. Metrics: `views`, `watch_time_minutes`.

For the full list, browse the YouTube Reporting docs at `https://developers.google.com/youtube/reporting/v1/reports/channel_reports` or call `reportTypes_list` against your own account. Content-owner-scoped types follow the same naming pattern with a `content_owner_` prefix.

## When to use Reporting vs Analytics

| Need | Use |
|------|-----|
| Ad-hoc slice for the last 7 days | Analytics API |
| Dashboard query that runs on demand | Analytics API |
| One number for one video right now | Analytics API |
| Full row-level data for every video, every day | Reporting API |
| 90 days of historical CSVs for a warehouse load | Reporting API |
| Recurring nightly export pipeline | Reporting API |
| Watch-time-per-video for 50,000 videos | Reporting API |

Rule of thumb: if the answer fits in a single chart and you want it now, query Analytics. If the answer is "give me everything, I'll process it later," subscribe a Reporting job and download CSVs.

Reporting trade-offs to keep in mind:

1. Latency. Plan for "next day" data, not "right now" data.
2. Setup cost. The job has to exist before any data starts flowing. Subscribe early.
3. Volume. One CSV per day per report type per account. Storage adds up fast.
4. Backfill. Once subscribed, YouTube backfills roughly 60 prior days. Older data is not retrievable through Reporting.

## External references

1. `https://developers.google.com/youtube/reporting/v1/reports`: Reporting API overview and lifecycle.
2. `https://developers.google.com/youtube/reporting/v1/reports/channel_reports`: full channel report type catalog with column definitions.
