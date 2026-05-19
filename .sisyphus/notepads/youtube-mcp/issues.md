# issues.md (youtube-mcp)

## [2026-05-19] Open non-blocking items

- **uv deprecation**: `pyproject.toml` uses `[tool.uv]` `dev-dependencies` which uv warns is deprecated. Migrate to `[dependency-groups]` `dev = [...]` in a later cleanup pass. Does NOT block T2-T48.
- **Evidence files**: T1 subagent created none of the `.sisyphus/evidence/task-1-*.txt` files the plan asked for. All future subagents MUST write evidence files exactly as named in the plan's "Evidence to Capture" subsection.
- **Playwright noise**: `.playwright-mcp/` contains a large pile of unrelated console/page snapshots from previous sessions. Not relevant to T1; leave alone unless plan touches them.

## Conventions for subagents

- Always use `uv run <cmd>`; never call `python` / `pip` directly.
- Always write evidence files to `.sisyphus/evidence/task-N-<name>.txt`.
- Never commit secrets — `.gitignore` already excludes `.env`, tokens, and `.sisyphus/evidence/`.
- Never introduce ANY reference to `videos.delete` or `videos_delete` in src/ or tests/.

## [2026-05-19] Task: T9

- `uv run mypy --strict src/youtube_mcp/utils/` still fails on pre-existing, untouched files: `src/youtube_mcp/utils/cache.py` (`no-any-return`) and `src/youtube_mcp/utils/retry.py` (`import-untyped`, `redundant-cast`).
- I did not modify those files because they belong to other tasks in the plan, so the new pagination module itself is strict-clean, but the package-wide utils mypy target is not yet green.
