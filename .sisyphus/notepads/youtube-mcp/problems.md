# problems.md (youtube-mcp)

(none yet — append blockers with timestamp and resolution path)

## [2026-05-19] Task: T10

- `uv run mypy --strict src/youtube_mcp/utils/` still fails on pre-existing `src/youtube_mcp/utils/retry.py:12` because `httplib2` lacks installed stubs (`import-untyped`). I did not modify that file because it is outside T10 scope.
