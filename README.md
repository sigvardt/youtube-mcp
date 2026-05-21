# youtube-mcp

An [MCP](https://modelcontextprotocol.io) server that exposes Google's three YouTube APIs (Data v3, Analytics v2, Reporting v1) as agent-callable tools. Built for AI assistants that need to inspect channels, fetch analytics, post comments, schedule live broadcasts, or upload videos without juggling raw OAuth refresh logic.

This server is a thin, opinionated wrapper around the official Google API client. It does not invent endpoints, hide quota costs, or try to be "smart" about the underlying API. What it does provide is brand-account-aware authentication, structured per-tool quota tracking, and an explicit safety policy that keeps destructive operations out of an agent's reach.

## Features

1. **Three API surfaces, one server.** YouTube Data API v3, YouTube Analytics API v2, and YouTube Reporting API v1 are exposed side by side. Tool names use the `youtube_*`, `analytics_*`, and `reporting_*` prefixes so an agent can route by surface.
2. **Multi-brand-account first-class.** Each operator-configured account is keyed locally (for example `main-channel`, `backup-channel`) and OAuth tokens are kept per key. Agents pass `account="main-channel"` on every call.
3. **OS keyring for tokens.** Refresh and access tokens live in the system keyring (macOS Keychain, Windows Credential Locker, freedesktop Secret Service). Tokens never sit in plaintext config files.
4. **Quota tracking per account.** Every tool declares its quota cost. The server tracks daily usage per account key and exposes it through the `youtube://quota/{account_key}` resource.
5. **Mutating-op guard.** Mutating tools (uploads, edits, comment posts, rating, abuse reports) are gated by an account-handle check. By default only `@jsigvardt` may run mutating operations against live YouTube. See `INSTALL.md` for the override.
6. **Operator CLI.** `youtube-mcp serve`, `youtube-mcp auth add`, `youtube-mcp auth list`, `youtube-mcp auth refresh`, `youtube-mcp status`, `youtube-mcp doctor`, and `youtube-mcp tools list` cover the day-to-day setup and health-check loop.
7. **Skill bundle for agents.** A drop-in Claude skill bundle lives at `skills/youtube-mcp/`. Point your agent at it to teach the model when to use the server, which tool to pick, and how much quota each call costs.

## Safety Policy: `videos.delete` is NOT a tool

The YouTube Data API endpoint `videos.delete` is **deliberately excluded** from this server. No tool wraps it. The `youtube_videos_*` module exposes `list`, `insert`, `update`, `rate`, `getRating`, and `reportAbuse` only.

The rationale is simple. Video deletion is irreversible at the API layer, and a bad agent prompt should never be one tool call away from wiping a channel's catalogue. If you need to take down a video, do it in the YouTube Studio UI. If you have a legitimate, audited workflow that requires programmatic deletion, fork this repo and add the tool yourself, with your own approval pipeline. We will not ship it upstream.

This rule is enforced both at the source level (no `videos_delete` symbol exists anywhere in `src/`) and by a CI grep that fails the build if the string ever appears.

## Install

Requires Python 3.11 or 3.12 and [`uv`](https://docs.astral.sh/uv/).

The PyPI distribution name is `youtube-api-mcp`. The shorter `youtube-mcp` package name is already occupied by an unrelated transcript package, so do not install it expecting this server.

Run the published server with `uvx`:

```bash
uvx youtube-api-mcp --help
uvx youtube-api-mcp serve --transport stdio
```

The wheel also installs a `youtube-mcp` console alias for persistent virtual environments. With `uvx`, prefer the distribution-matched `youtube-api-mcp` command above. If a client must call the historical executable name, use `uvx --from youtube-api-mcp youtube-mcp serve --transport stdio`.

For local development from a clone:

```bash
git clone https://github.com/sigvardt/youtube-mcp.git
cd youtube-mcp
uv sync
uv run youtube-mcp --help
```

OAuth setup, GCP project configuration, and the brand-account picker step are covered in [`INSTALL.md`](INSTALL.md). Read it before the first `youtube-api-mcp auth add`.

## Quickstart

1. Follow [`INSTALL.md`](INSTALL.md) to create a GCP OAuth client and add at least one account.
2. Verify the install:

   ```bash
   uvx youtube-api-mcp status
   uvx youtube-api-mcp tools list --api youtube
   ```

3. Wire the server into your MCP client.

### Claude Desktop

Edit `claude_desktop_config.json` (location varies per OS; see the Anthropic docs):

```json
{
  "mcpServers": {
    "youtube-mcp": {
      "command": "uvx",
      "args": ["youtube-api-mcp", "serve", "--transport", "stdio"]
    }
  }
}
```

If you cloned the repo instead of installing the published wheel, point `command` at `uv` and `args` at `["--directory", "/abs/path/to/youtube-mcp", "run", "youtube-mcp", "serve"]`.

### OpenCode

In your OpenCode config:

```json
{
  "mcp": {
    "youtube-mcp": {
      "type": "local",
      "command": ["uvx", "youtube-api-mcp", "serve", "--transport", "stdio"],
      "enabled": true
    }
  }
}
```

### Other MCP clients

The server speaks the standard MCP protocol over stdio (default), HTTP, or SSE. Pick the transport that matches your client:

```bash
uvx youtube-api-mcp serve --transport stdio
uvx youtube-api-mcp serve --transport http --host 127.0.0.1 --port 8765
uvx youtube-api-mcp serve --transport sse --host 127.0.0.1 --port 8765
```

## Tool inventory

There are 17 tool modules under `src/youtube_mcp/tools/`. Run `uvx youtube-api-mcp tools list` for the live list with quota costs and descriptions. The modules group as follows:

1. **Data API v3 (read/write):** `activities`, `captions`, `channel_sections`, `channels`, `comment_threads`, `comments`, `i18n`, `live_chat`, `livestream`, `members`, `misc`, `playlists`, `search`, `subscriptions`, `super_chat_events`, `video_assets`, `video_meta`, `videos`.
2. **Analytics API v2:** `analytics_groups`, `analytics_reports`.
3. **Reporting API v1:** `reporting_jobs`, `reporting_reports`.

Every tool returns a structured Pydantic model. None return raw HTTP bodies.

## Resources

The server also exposes three MCP resources:

1. `youtube://accounts`: list of configured account keys, handles, channel IDs, and granted scopes. Never includes tokens.
2. `youtube://quota/{account_key}`: current daily quota usage for a key.
3. `youtube://status`: version, transport, and configured account count.

## For agents and skill authors

The skill bundle at [`skills/youtube-mcp/`](skills/youtube-mcp/SKILL.md) is the canonical "when to use this server" reference for AI assistants. It explains:

1. Which API to pick for a given question (Data vs Analytics vs Reporting).
2. The brand-account model and how to pass `account="<key>"`.
3. Quota cost per tool and how to budget.
4. Workflow guides for upload, comment moderation, live broadcast, and analytics pulls.

If you are building a Claude skill or OpenCode agent on top of this server, ingest the skill bundle. Do not re-derive the catalogue from `tools list` output alone.

## Working on the code

See [`CLAUDE.md`](CLAUDE.md) for project conventions, the module map, the "where do I add a new tool" guide, and the mutating-guard rationale. New contributors and AI assistants editing this repo should read it first.

## License

MIT. See [`LICENSE`](LICENSE).
