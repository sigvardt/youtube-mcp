# Operator Unblock Checklist — youtube-mcp Live Testing

**Status**: Phases 2-8 of the live test plan are blocked on OAuth bootstrap, which requires the human operator's browser and their @jsigvardt-owning Google account. This file is the copy-paste-runnable walkthrough to unblock.

**Constraint (verbatim from user)**: "write/update/delete endpoints you're only allowed to test write operations against the account: https://www.youtube.com/@jsigvardt"

---

## What is blocked and why

Eight `tests/live/` and live-probe phases cannot run without:

1. A Google Cloud OAuth 2.0 **Desktop** client credentials JSON file on disk.
2. A completed browser consent flow that lands an access + refresh token in the macOS Keychain under service `youtube-mcp` key `jsigvardt`.

Neither is possible from inside an agent session. Both need the operator's hands and browser.

---

## Step 1 — Obtain a Google OAuth Desktop client JSON

Skip steps 1.1 through 1.6 if you already have such a file.

### 1.1 Open the GCP credentials console

<https://console.cloud.google.com/apis/credentials>

Pick an existing GCP project or create a new one. Reusing an existing personal project is fine.

### 1.2 Enable the three APIs on that project

APIs & Services -> Library -> enable each of:

- YouTube Data API v3
- YouTube Analytics API
- YouTube Reporting API

### 1.3 Configure the OAuth consent screen

APIs & Services -> OAuth consent screen.

- User Type: External (or Internal if @jsigvardt's owning Google account is in a Workspace org you control).
- App name: `youtube-mcp-jsigvardt` (any name works).
- User support email: `joakim@signikant.com`.
- Developer contact email: `joakim@signikant.com`.
- Scopes screen: skip. Scopes are requested at consent time by the library.
- Test users (only matters while the app is in Testing status): **add the Google account that owns @jsigvardt**. If you skip this, the consent screen will deny with `Error 403: access_denied`. This is the single most common foot-gun.

### 1.4 Create the OAuth client credential

APIs & Services -> Credentials -> Create credentials -> OAuth client ID.

- Application type: **Desktop app** (critical — the loopback flow in `src/youtube_mcp/auth/oauth_flow.py` only works with Desktop clients).
- Name: `youtube-mcp local desktop`.
- Click Create. A dialog appears with the client_id and client_secret. Click Download JSON.

### 1.5 Store the JSON at a stable path

```bash
mkdir -p /Users/user/Repositories/youtube-mcp/.secrets
mv ~/Downloads/client_secret_*.json /Users/user/Repositories/youtube-mcp/.secrets/client_secret.jsigvardt.json
chmod 600 /Users/user/Repositories/youtube-mcp/.secrets/client_secret.jsigvardt.json
```

### 1.6 Confirm `.secrets/` is gitignored

```bash
cd /Users/user/Repositories/youtube-mcp
grep -E '^\.?secrets' .gitignore || echo '.secrets/' >> .gitignore
```

---

## Step 2 — Run the auth bootstrap (browser will open)

```bash
cd /Users/user/Repositories/youtube-mcp
uv run youtube-mcp auth add jsigvardt --client-creds=.secrets/client_secret.jsigvardt.json
```

What happens:

1. A local loopback server starts on a random high port on `localhost`.
2. Your default browser opens a Google consent screen.
3. **In the Google account picker, pick the account that owns @jsigvardt.** If unsure, open <https://www.youtube.com/account> in the same browser first to confirm the active YouTube identity is @jsigvardt.
4. You'll see a "Google hasn't verified this app" warning because the OAuth client is in Testing. Click **Advanced** -> **Go to youtube-mcp-jsigvardt (unsafe)**. Expected and safe — your own client, your own account.
5. Scope grant screen lists read, manage, upload, force-ssl, partner, channel memberships, analytics readonly, analytics monetary, reporting. **Tick every scope.** Skipping any becomes a 403 in the live mutating phase.
6. The tab closes itself with "Authentication complete".
7. Refresh token lands in macOS Keychain under service `youtube-mcp` account `jsigvardt`. Index lands in `~/.config/youtube-mcp/accounts.json`.

### 2.1 Verify the bootstrap

```bash
cd /Users/user/Repositories/youtube-mcp
uv run youtube-mcp auth list
uv run youtube-mcp status
```

Both should now show `jsigvardt` with a valid token. If they do, paste either output in chat or just say "done" and the agent will fire Phases 2-8.

---

## Step 3 — What the agent will run autonomously after Step 2 lands

In this order. Stop at any step that fails; record the failure.

### Phase 2 — auth smoke probe

```bash
uv run youtube-mcp doctor
```

Calls `youtube.tests.insert` (a no-op test resource, not a real video). Costs 1 quota unit. Proves OAuth refresh, scope grant, network path.

### Phase 3 — live read-only test suite

```bash
RUN_LIVE_TESTS=1 uv run pytest tests/live -k readonly -v
```

Read-only across all three APIs. ~50-200 quota units total. Proves response shape parity with real Google.

### Phase 5 — REPL probes

Targeted live calls of ~10 read tools across the three APIs (channels.list mine=True, videos.list, search.list, analytics_reports_query for last 7d, reporting_jobs.list, reporting_reportTypes.list, etc.). ~50 quota units.

### Phase 7 — MCP stdio handshake

Boot `youtube-mcp serve --transport stdio` as a subprocess, send a JSON-RPC `tools/list` request over stdin, expect all 98 tools in the response. No API calls.

### Phase 6 — quota-cost audit

Re-run the Phase 5 probes with `QuotaTracker` reads bracketing each call. Diff declared `cost=N` against observed delta.

### Phase 4 — live mutating suite (DESTRUCTIVE on @jsigvardt only)

```bash
RUN_LIVE_TESTS=1 RUN_MUTATING_TESTS=1 YOUTUBE_MCP_ENFORCE_GUARD=1 uv run pytest tests/live -k mutating -v
```

Real mutations on @jsigvardt only — the framework hard-fails the suite at fixture time if the account's `channel_handle` is anything other than `@jsigvardt`. Uploads test videos, posts comments, rates, edits playlists, creates+deletes analytics groups. ~5000-10000 quota units (uploads expensive).

**No video deletion** — `youtube.videos.delete` is intentionally absent from this MCP. You must delete uploaded test videos manually in YouTube Studio after the run. See Phase 8.

`abuseReports.insert` is additionally gated by `RUN_DESTRUCTIVE_LIVE=1`. Leave that env var unset unless you explicitly want to file an abuse report against a real video.

### Phase 8 — cleanup evidence

```bash
cat .sisyphus/evidence/task-47-uploaded-video-ids.txt
```

Lists every video ID uploaded by the mutating suite. Manually delete each at <https://studio.youtube.com> -> Content.

---

## Optional escape hatches

- **Skip Phase 4 entirely** (no live mutations on @jsigvardt). Tell the agent "skip mutating" before unblocking. Reasonable if you want to validate read paths only or save quota.
- **Skip just abuseReports.insert** (default behavior — `RUN_DESTRUCTIVE_LIVE` left unset).
- **Use a previously-saved OAuth client JSON** from a different path. Just point `--client-creds=` at it.

---

## How to resume the agent after unblocking

1. Confirm `uv run youtube-mcp auth list` shows jsigvardt with a token.
2. Re-enter the conversation and say "done" (or paste the verification output, or just "go").
3. Agent will re-read this checklist's state, mark Phase 1 done, and proceed.

---

## Why this file exists

Per `/Users/user/.config/opencode/AGENTS.md` "stuck continuation loop" protocol, the auto-continue framework was firing "Continue working" prompts on a true external blocker (USER ACTION on OAuth). Agent has deregistered the boulder by writing this checklist and marking the 8 remaining todos as `cancelled` with handoff notes. Restart by following Step 2 above.
