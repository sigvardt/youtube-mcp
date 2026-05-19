# learnings.md (youtube-mcp)

## [2026-05-19] T1 — Project Scaffolding

- **Build backend**: `hatchling>=1.24` (chosen by T1 subagent; works fine, `uv sync` happy)
- **Python**: pinned `>=3.11,<3.13` in pyproject (host has python 3.14 but uv resolves per-project)
- **Package layout**: `src/youtube_mcp/{__init__.py,server.py,cli.py,config.py,types.py,auth/,tools/,utils/}` — confirmed working layout, all subpackages have `__init__.py`
- **Lint/type**: `ruff.toml` (line-length 100, py311 target, `E,F,W,I,B,UP,RUF` rules) + `mypy.ini` (`strict = true`, ignore_missing_imports for `googleapiclient.*` and `google.*`)
- **CLI entry point**: `youtube-mcp = "youtube_mcp.cli:main"` — stub `main()` in place
- **Dev deps location**: Currently under `[tool.uv]` `dev-dependencies` — uv warns this is deprecated; should migrate to `[dependency-groups]` `dev = [...]` in a later cleanup pass (NON-BLOCKING for T2+)
- **Verification commands that work**:
  - `uv sync` → "Resolved 113 packages"
  - `uv run python -c "import fastmcp, googleapiclient, keyring, tenacity, pydantic, youtube_mcp"` → ok
  - `uv run ruff check src/` → all checks passed
  - `uv run mypy --strict src/youtube_mcp/` → success, no issues in 8 source files
- **Host env**: `uv` installed via `brew install uv` (was missing). Use `uv run <cmd>` for ALL Python commands — DO NOT call `python` / `pip` directly. System `python3` is 3.14.4 which is not what the project uses.
- **`.sisyphus/evidence/`**: directory exists but no task-1 evidence file was written by subagent — non-blocking, but future tasks should actually populate `task-N-*.txt` files when the plan asks for them.

## [2026-05-19] Task: T3

- **Pydantic v2 pattern**: `model_config = ConfigDict(extra="forbid")` on each model, `Field(default_factory=lambda: datetime.now(UTC))` for timezone-aware defaults, and `field_validator("percent")` for `UploadProgress.percent` range enforcement.
- **Scope values**: `YouTubeScope` uses the documented Google strings exactly: `youtube.readonly`, `youtube`, `youtube.upload`, `youtubepartner`, `youtube.force-ssl`, `yt-analytics.readonly`, `yt-analytics-monetary.readonly`; `REPORTING` intentionally aliases `yt-analytics.readonly` because Google docs map reporting to the analytics readonly scope.
- **Validation gotcha**: `AccountConfig.key` needs `Field(min_length=1)` so the plan's empty-key ValidationError scenario is real; empty `oauth_scopes` remains valid and round-trips.
- **Ruff/mypy gotchas**: `ruff` wanted `datetime.UTC` and `str | None` instead of `timezone.utc` / `Optional[str]`; switching to the newer forms kept the model spec intact and made `ruff check` clean.

## [2026-05-19] Task: T2

- CI workflow now has four jobs: `lint`, `types`, `unit`, and `integration`.
- Each job uses `actions/setup-python@v5` with Python 3.11, `astral-sh/setup-uv@v3`, `.venv` caching keyed on `uv.lock`, and `uv sync --frozen`.
- `integration` waits on `unit`; no live-test env var or secrets were added.

## [2026-05-19] Task: T4

- `TokenStore` is a protocol in `src/youtube_mcp/auth/token_store.py`; both concrete backends serialize tokens only with `TokenBundle.model_dump_json()` and restore with `TokenBundle.model_validate_json()`.
- `KeyringTokenStore.list_keys()` uses a sidecar keyring entry named `__youtube_mcp_registry__` because the `keyring` API has no portable enumeration primitive.
- `FileTokenStore` defaults to `${XDG_CONFIG_HOME:-~/.config}/youtube-mcp/tokens`, creates the token dir at `0o700`, and chmods token JSON files to `0o600` after each write.
- `make_token_store("auto")` probes keyring by reading the registry; `keyring.errors.NoKeyringError` falls back to file storage and emits a stderr warning.
- Unit tests mock `keyring.get_password` / `set_password` / `delete_password` with `pytest.MonkeyPatch`; no test touches the real system keyring.
