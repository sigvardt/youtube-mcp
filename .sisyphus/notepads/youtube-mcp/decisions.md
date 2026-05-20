# decisions.md (youtube-mcp)

## [2026-05-19] Foundational decisions inherited from plan

- **Language**: Python 3.11+ (pyproject `>=3.11,<3.13`)
- **Framework**: `fastmcp>=2.0` (jlowin/fastmcp)
- **Google SDK stack**: `google-api-python-client` + `google-auth-oauthlib` + `google-auth-httplib2`
- **Tool granularity**: 1:1 endpoint mapping — one MCP tool per Google API method
- **Account**: explicit `account: str` parameter on EVERY tool (no implicit global active account)
- **Long-running ops**: synchronous calls + MCP `Context.report_progress()` for uploads / report-job polls
- **Transport**: stdio primary, `--transport=http` optional
- **Token storage**: hybrid — `keyring` lib default, file fallback at `~/.config/youtube-mcp/tokens/`
- **CRITICAL EXCLUSION**: `youtube.videos.delete` MUST be programmatically absent — not just gated. Zero references in src/ and tests/. Final wave will grep this.
- **Mutating-op gate**: live mutating tests only allowed against channel handle `@jsigvardt` — enforced by `MutatingGuardConfig` (T13).
- **OAuth creds**: located at `/Users/user/Desktop/YouTube MCP.txt` (test fixture only; never commit).
- **Verification cadence**: every task must produce evidence in `.sisyphus/evidence/task-N-*.txt`.

## [2026-05-19] Wave-1 sub-sequencing (Atlas decision)

Plan claims "Wave 1 — 13 tasks, all start immediately" but the dependency matrix in the same plan says `T3 → T4..T12`. Matrix wins. Sub-waves:

- **1a** (parallel): T2 (CI), T3 (types) — both only need T1
- **1b** (parallel): T4 (token store), T5 (oauth flow), T6 (account mgr), T7 (retry), T8 (quota), T9 (pagination), T10 (ttl cache) — all need T3
- **1c** (parallel): T11 (server bootstrap), T12 (tool reg framework) — need T3-T10
- **1d**: T13 (mutating-account guard) — needs T6
