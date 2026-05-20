# Sub U multi-account read routing validation

**VERDICT: ROUTING-CLEAN-FULL-DATA**

All three configured accounts returned live Google data for their own channels. The safe read sweep passed 18/18 selected tests, and an additional read-only channel identity probe returned each account's expected channel ID and handle.

## Configured accounts (baseline)

```text
warning: The `tool.uv.dev-dependencies` field (used in `pyproject.toml`) is deprecated and will be removed in a future release; use `dependency-groups.dev` instead
key	handle	channel_id	scopes
jsigvardt	@jsigvardt	UCvTRR-gKfkSwnXTkxg3w2Nw	force_ssl,analytics_readonly,analytics_monetary,channel_memberships_creator
power-1	@powerdanmark	UCFAas6-aw9AhzodpD1mbyvQ	force_ssl,analytics_readonly
power-2	@powernorge	UCgVywZ90aWpkReo0kfw5o2Q	force_ssl,analytics_readonly
```

## Read-only selection safety

The unfiltered live file contains `test_tests_insert_auth_probe`, which calls `youtube_tests_insert` from `tests/live/test_acid_read_all_accounts.py:133`. That tool is decorated with `mutating=True` in `src/youtube_mcp/tools/misc.py:56`, so it was intentionally deselected. The executed command was:

```text
RUN_LIVE_TESTS=1 uv run pytest tests/live/test_acid_read_all_accounts.py -v --tb=short -k 'not test_tests_insert_auth_probe' 2>&1 | tee .sisyphus/evidence/sub-u-pytest-output.log
```

Pytest collection confirmed 18 safe selected tests and 3 deselected auth-probe tests.

## Quota state delta

| account | handle | before | after | delta | attribution verdict |
|---|---|---:|---:|---:|---|
| jsigvardt | @jsigvardt | 10069 | 10076 | +7 | own key only |
| power-1 | @powerdanmark | 0 | 7 | +7 | own key only |
| power-2 | @powernorge | 0 | 7 | +7 | own key only |

The local quota tracker advanced independently by 7 units for each key. No account's burn appeared on another account's counter. The `jsigvardt` account was already above the local daily quota baseline before this run, but the read calls still completed and the per-key delta was clean.

## Per-account test outcomes

### jsigvardt -> @jsigvardt

- Passed: `test_channels_list_mine`, `test_playlists_list_mine`, `test_subscriptions_list_mine`, `test_videos_list_mine`, `test_analytics_reports_query_views`, `test_reporting_report_types_list`.
- Failed: none.
- Skipped: none among selected tests.
- Deselected for safety: `test_tests_insert_auth_probe` because its tool is marked `mutating=True`.
- Handle integrity check: Y. Direct read-only `channels.list(mine=True)` returned `returned_id=UCvTRR-gKfkSwnXTkxg3w2Nw`, `custom_url=@jsigvardt`, `title=Joakim Sigvardt`.

### power-1 -> @powerdanmark

- Passed: `test_channels_list_mine`, `test_playlists_list_mine`, `test_subscriptions_list_mine`, `test_videos_list_mine`, `test_analytics_reports_query_views`, `test_reporting_report_types_list`.
- Failed: none.
- Skipped: none among selected tests.
- Deselected for safety: `test_tests_insert_auth_probe` because its tool is marked `mutating=True`.
- Handle integrity check: Y. Direct read-only `channels.list(mine=True)` returned `returned_id=UCFAas6-aw9AhzodpD1mbyvQ`, `custom_url=@powerdanmark`, `title=POWER`.

### power-2 -> @powernorge

- Passed: `test_channels_list_mine`, `test_playlists_list_mine`, `test_subscriptions_list_mine`, `test_videos_list_mine`, `test_analytics_reports_query_views`, `test_reporting_report_types_list`.
- Failed: none.
- Skipped: none among selected tests.
- Deselected for safety: `test_tests_insert_auth_probe` because its tool is marked `mutating=True`.
- Handle integrity check: Y. Direct read-only `channels.list(mine=True)` returned `returned_id=UCgVywZ90aWpkReo0kfw5o2Q`, `custom_url=@powernorge`, `title=POWER Norge`.

## Routing integrity findings

- Cross-contamination check: clean. No selected test failed, and the direct read-only identity probe returned the expected channel ID and handle for every account.
- Key-collision check: clean. Three distinct account keys resolved to three distinct token-backed Google channel identities.
- Quota-attribution check: clean. Local quota moved from 10069 to 10076 for `jsigvardt`, from 0 to 7 for `power-1`, and from 0 to 7 for `power-2`.
- Error classification: no `quotaExceeded`, `authError`, `forbidden`, or other Google API failures appeared in the selected pytest output.
- Payload-print caveat: the pytest suite itself does not print response payloads on success. To verify handle integrity, I ran a separate read-only channel identity probe through `AccountManager.get_youtube_service(...).channels().list(part="snippet", mine=True, maxResults=1).execute()`. This bypassed the framework quota tracker, so it did not affect the local per-key quota delta above.

## Bugs found

- No routing bug found.
- Non-routing safety bug: the file named as the read-all-accounts live suite includes `test_tests_insert_auth_probe` at `tests/live/test_acid_read_all_accounts.py:129`, and that test invokes `youtube_tests_insert` at `tests/live/test_acid_read_all_accounts.py:133`. The tool is decorated `mutating=True` at `src/youtube_mcp/tools/misc.py:56`. The test must remain excluded from read-only sweeps unless it is moved, renamed, or reclassified in a separate fix wave.

## Recommendation

Multi-account routing is production-ready for read-only use. The three configured accounts authenticated independently, routed to distinct Google channel identities matching `@jsigvardt`, `@powerdanmark`, and `@powernorge`, and burned local quota on their own account keys. Before calling the whole live read file unfiltered in automation, fix or isolate the `youtube_tests_insert` auth probe so the nominal read-only suite cannot run a tool marked `mutating=True`.
