# CLAUDE.md

Agent-facing guide for working *on* youtube-mcp. Read this before touching the codebase.

If you arrived here looking for "how do I use youtube-mcp as a tool from my agent", you want [`skills/youtube-mcp/SKILL.md`](skills/youtube-mcp/SKILL.md) instead. This file is for editing the server itself.

## What this repo is

A single Python package, `youtube_mcp`, that:

1. Boots a FastMCP server (`src/youtube_mcp/server.py`).
2. Registers ~84+ tools across 17 tool modules under `src/youtube_mcp/tools/` covering YouTube Data v3, Analytics v2, and Reporting v1.
3. Manages multi-brand-account OAuth, refresh, and quota tracking.
4. Exposes a Typer CLI (`youtube-mcp serve | auth ... | status | doctor | tools list`) so an operator can set up accounts and probe health without writing Python.

## Project conventions (non-negotiable)

1. **`uv run` for everything.** Never call `python`, `pip`, `pytest`, `mypy`, `ruff`, or `pyright` directly. The system Python is not the project Python. Always `uv run <command>`.
2. **`mypy --strict` is the source of truth.** Every module passes `--strict`. New code must too. `# type: ignore` requires a same-line justification comment naming the third-party limitation.
3. **`ruff check` is clean.** Config lives in `ruff.toml`. Rules: `E,F,W,I,B,UP,RUF`, line length 100, target `py311`.
4. **`pyright` runs in CI as a second opinion.** Some Google client stubs are partial; the existing `# pyright: reportMissingTypeStubs=false` block at the top of `cli.py` is the pattern when you have to suppress.
5. **No `# type: ignore` shotgun.** If you find yourself adding more than one `ignore` to a new file, stop and re-shape the types.
6. **Pydantic v2 for all model shapes.** Every public model uses `ConfigDict(extra="forbid")`. See `types.py` for the canon.
7. **`from __future__ import annotations` at the top of every module.** Consistent and matches the existing style.
8. **No `print()` for production logging.** Use `FastMCP` `Context.log` inside tools, and the module logger in `server.py` for boot-time messages.
9. **No emojis, no em dashes, no en dashes in source or docs.** This is enforced by review, not lint.
10. **Append to `.sisyphus/notepads/youtube-mcp/learnings.md` when you discover something non-obvious.** Never overwrite.

## Safety policy: `videos.delete` is NOT exposed

The `videos.delete` endpoint of the YouTube Data API is **deliberately not wrapped** by this server. The `youtube_videos_*` tool module exposes `list`, `insert`, `update`, `rate`, `getRating`, and `reportAbuse` only.

Why: video deletion is irreversible at the API layer. A single bad prompt should not be one tool call away from wiping a channel's catalogue. The exclusion is enforced two ways:

1. No symbol named `videos_delete`, `videos.delete`, or `youtube_videos_delete` exists anywhere in `src/` or `tests/`. Tests verify absence by joining the parts `("youtube", "videos", "delete")` dynamically so the literal string never appears in any source file.
2. A CI grep step (`grep -rn "videos.delete\|videos_delete" src/ tests/`) MUST return zero matches. If it ever does, the build fails.

If you are tempted to "just add it temporarily", don't. Fork the repo, do it on your fork, and keep your fork. We will not merge that tool upstream under any circumstances.

## Mutating-op guard

All tools that *change* YouTube state (uploads, edits, comment posts, ratings, abuse reports) are tagged `mutating=True` in their decorator. The framework consults a guard (`utils/mutating_guard.py`) **before** issuing the API call.

Guard behavior:

1. Reads the allow-handle from env `YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE` (defaults to `@jsigvardt` if unset).
2. Enforcement is on when env `YOUTUBE_MCP_ENFORCE_GUARD=1`. The pytest suites set this so live-acid tests can never mutate a non-allowed channel.
3. In production, enforcement is opt-in; the operator turns it on through the MCP client config's env block (see `INSTALL.md`).
4. When enforcement is on and the calling account's resolved channel handle does not match the allow-handle, the framework raises **before** the network call.

Do not bypass the guard from inside tool code. The framework wires it in for you automatically based on the `mutating=True` decorator flag.

## Module map

```
src/youtube_mcp/
├── __init__.py            # exports __version__
├── server.py              # FastMCP bootstrap, resources, transport selection
├── cli.py                 # Typer CLI: serve, auth, status, doctor, tools list
├── config.py              # config paths
├── types.py               # Pydantic models, YouTubeScope enum, QuotaState, TokenBundle, etc.
├── auth/
│   ├── accounts.py        # AccountConfigStore, AccountManager, on-disk account config
│   ├── oauth_flow.py      # google-auth-oauthlib browser flow + refresh
│   ├── token_store.py     # OS keyring read/write
│   └── wizard.py          # interactive auth-add wizard (also drives `auth add`)
├── tools/
│   ├── _framework.py      # @youtube_tool decorator, FrameworkContext, mutating-guard wiring
│   ├── activities.py
│   ├── analytics_groups.py
│   ├── analytics_reports.py
│   ├── captions.py
│   ├── channel_sections.py
│   ├── channels.py
│   ├── comment_threads.py
│   ├── comments.py
│   ├── i18n.py
│   ├── live_chat.py
│   ├── livestream.py
│   ├── members.py
│   ├── misc.py            # abuseReports
│   ├── playlists.py
│   ├── reporting_jobs.py
│   ├── reporting_reports.py
│   ├── search.py
│   ├── subscriptions.py
│   ├── super_chat_events.py
│   ├── video_assets.py
│   ├── video_meta.py
│   └── videos.py          # list, insert, update, rate, getRating, reportAbuse ONLY
└── utils/
    ├── quota.py           # QuotaTracker
    └── mutating_guard.py  # allow-handle enforcement
```

## How to add a new tool

Follow this exact recipe. Do not improvise.

1. **Find the right module.** Group by Google API resource. `youtube.activities.*` lives in `activities.py`, `analytics.reports.*` in `analytics_reports.py`, and so on. Create a new module only when no existing one matches the resource.
2. **Look up the official spec.** Use the Google API discovery docs for the exact endpoint name, request parameters, response shape, required scopes, and quota cost. Do not guess.
3. **Define request/response Pydantic models** at module top, with `ConfigDict(extra="forbid")`. Re-use shared types from `types.py` where possible.
4. **Write the tool function** decorated with `@youtube_tool(...)`. The decorator signature:

   ```python
   @youtube_tool(
       name="youtube_<resource>_<verb>",
       api="youtube",  # or "analytics" or "reporting"
       method="<resource>.<verb>",
       scopes=[YouTubeScope.MANAGE, ...],
       cost=<integer-units>,
       mutating=False,  # True if this changes YouTube state
   )
   def youtube_<resource>_<verb>(account: str, ...) -> <ResponseModel>:
       """One-line summary used as the MCP tool description."""
       ...
   ```

5. **Use the framework client.** The decorator injects an authenticated `googleapiclient` resource via `FrameworkContext`. Never instantiate a Google client by hand inside a tool body.
6. **Return a Pydantic model**, never a raw dict and never the raw Google response. Map fields explicitly so the schema is stable across Google's API drift.
7. **Confirm `mutating=True` is correct.** If the tool changes channel state, `mutating=True`. The framework will route it through the guard automatically.
8. **Write unit tests** under `tests/unit/test_tools_<module>.py`. Mock the Google client; assert request shape, response parsing, and scope/quota metadata.
9. **Run the local gauntlet:**

   ```bash
   uv run ruff check src/youtube_mcp/tools/<module>.py tests/unit/test_tools_<module>.py
   uv run mypy --strict src/youtube_mcp/tools/<module>.py
   uv run pytest tests/unit/test_tools_<module>.py -v
   uv run youtube-mcp tools list --api <api>   # confirm the tool registers
   grep -rn "videos.delete\|videos_delete" src/ tests/   # MUST return zero matches
   ```

10. **If the tool is `mutating=True`, add a live-acid test** under `tests/live/` gated by `RUN_LIVE_TESTS=1` and the mutating-guard. Live tests must pre-flight the account handle and fail loudly if not the allow-handle.

## Testing layout

1. `tests/unit/`: pure unit tests with mocked Google clients. Fast, run on every commit.
2. `tests/integration/`: wire-level tests using `respx` or VCR cassettes. No live network.
3. `tests/live/`: opt-in via `RUN_LIVE_TESTS=1`. Hits the real Google APIs. Mutating tests are guarded by the allow-handle.

Run the suites:

```bash
uv run pytest tests/unit                              # fast
uv run pytest tests/unit tests/integration            # default CI
RUN_LIVE_TESTS=1 uv run pytest tests/live -k readonly # safe live reads
RUN_LIVE_TESTS=1 YOUTUBE_MCP_ENFORCE_GUARD=1 \
  uv run pytest tests/live -k mutating                # live mutating, allow-handle only
```

## CLI subcommand surface

Eight subcommands. Implementations live in `cli.py`.

1. `youtube-mcp serve [--transport stdio|http|sse] [--host HOST] [--port PORT]`: boot the MCP server.
2. `youtube-mcp auth add <key> [--client-creds PATH] [--scopes ...]`: run OAuth, store token.
3. `youtube-mcp auth list`: print configured accounts.
4. `youtube-mcp auth remove <key> [--yes]`: drop an account and its stored token.
5. `youtube-mcp auth refresh <key>`: force token refresh.
6. `youtube-mcp status`: accounts + token freshness + quota usage.
7. `youtube-mcp doctor`: runs `youtube.channels.list(mine=true)` per account as an auth smoke probe and prints `OK` when the returned channel id matches the account config.
8. `youtube-mcp tools list [--api youtube|analytics|reporting]`: enumerate registered MCP tools with summaries.

When you add a CLI command, update `ROOT_HELP` in `cli.py` and the list above.

## Things that look fixable but aren't

1. `[tool.uv] dev-dependencies` in `pyproject.toml` is deprecated. uv suggests migrating to `[dependency-groups]`. **Don't migrate yet.** Defer to a dedicated cleanup task; touching it here drags in lock-file churn unrelated to whatever you're working on.
2. The `_account_provider` lambda default in `server.py` is wired to `lambda: []` at module load and replaced by `serve()`. Don't refactor it into a class attribute; the lambda is intentional to keep import-time side effects to zero.
3. Some Google client methods have no type stubs. The `# pyright: reportMissingTypeStubs=false` block at the top of `cli.py` is the canonical workaround. Don't try to add stubs to this repo; that's upstream's problem.

## When stuck

1. Search `.sisyphus/notepads/youtube-mcp/learnings.md` first; the answer to most "why is this set up this way" questions is in there.
2. Read the plan at `.sisyphus/plans/youtube-mcp.md` for the original task that introduced the file you're editing. Each task ID (`T1`, `T13`, `T25`...) maps to a section with WHY and acceptance criteria.
3. The plan file is **read-only**. Never edit it. The Sisyphus orchestrator owns it.
4. Don't bypass the mutating-guard, don't add `videos.delete`, don't put tokens in config files. Everything else is negotiable.
