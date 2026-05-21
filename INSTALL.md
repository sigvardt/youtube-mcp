# INSTALL.md

End-to-end setup for youtube-mcp: GCP project, OAuth client, scopes, uvx install path, account onboarding, brand-account picker, and MCP client wiring.

Plan to spend 15-30 minutes the first time. The Google Cloud console steps are the slow part; the CLI steps take seconds.

## Prerequisites

1. A Google account that owns (or can manage) the YouTube channel you want to drive.
2. Python 3.11 or 3.12. The project pins this range in `pyproject.toml`. Newer Python releases are not supported.
3. [`uv`](https://docs.astral.sh/uv/) installed locally. `brew install uv` on macOS, or follow the upstream install instructions.
4. A working OS keyring. macOS Keychain, Windows Credential Locker, and freedesktop Secret Service (GNOME Keyring, KWallet) all work out of the box. Headless Linux servers need a keyring daemon running; see the Troubleshooting section.

The PyPI distribution is `youtube-api-mcp` because the shorter `youtube-mcp` package name is already used by an unrelated project. All end-user commands below use the published `uvx` path:

```bash
uvx youtube-api-mcp --help
```

The wheel also provides a `youtube-mcp` console alias for persistent virtual environments. With `uvx`, use `youtube-api-mcp` unless you explicitly need the alias form: `uvx --from youtube-api-mcp youtube-mcp ...`.

For local development from a clone, sync deps and replace `uvx youtube-api-mcp` with `uv run youtube-mcp` in the commands below:

```bash
git clone https://github.com/sigvardt/youtube-mcp.git
cd youtube-mcp
uv sync
```

You should see the `serve`, `auth`, `status`, `doctor`, and `tools` subcommands.

## Step 1: Create a Google Cloud project

1. Open the [Google Cloud Console](https://console.cloud.google.com).
2. From the project picker in the top bar, click **New Project**.
3. Name it something memorable (`youtube-mcp-<your-handle>` works). Region and org settings can stay at defaults for personal use.
4. Switch into the new project before continuing. The project name should show in the top bar.

## Step 2: Enable the three YouTube APIs

The server uses all three. You must enable each one explicitly; Google does not bundle them.

1. Navigate to **APIs & Services -> Library** in the left nav.
2. Search for and enable each of the following, one by one:
   1. **YouTube Data API v3**
   2. **YouTube Analytics API**
   3. **YouTube Reporting API**
3. Each one lands you on a status page after enabling. You can leave the default per-project quota in place; the server tracks usage locally.

## Step 3: Configure the OAuth consent screen

OAuth client creation will fail until you have a consent screen.

1. Go to **APIs & Services -> OAuth consent screen**.
2. Pick **External** unless your project is inside a Google Workspace org that limits to internal users.
3. Fill in the required fields:
   1. App name: `youtube-mcp` (or your fork's name).
   2. User support email: your address.
   3. Developer contact email: same.
4. On the **Scopes** step you can leave the list empty. Scopes are requested at runtime by the OAuth flow; you do not need to pre-declare them here for a desktop client used by yourself.
5. On the **Test users** step, add the Google account that owns the YouTube channel you will drive. While the app is in "Testing" status, only listed test users can consent. This is the recommended state for personal or single-operator deployments.
6. Save and exit. You do not need to publish or submit for verification.

## Step 4: Create the OAuth Client ID

1. Go to **APIs & Services -> Credentials**.
2. Click **Create Credentials -> OAuth client ID**.
3. Application type: **Desktop app**.
4. Name: `youtube-mcp-local` or similar.
5. Click **Create**. A modal pops up with the client ID and client secret.
6. Click **Download JSON**. Save the file somewhere you'll remember, for example `~/.config/youtube-mcp/client_secret.json`.

The downloaded file looks like `client_secret_<long-id>.apps.googleusercontent.com.json`. The exact filename does not matter; you'll pass its path to the CLI in the next step.

Do not commit this file. Add the path to your global `.gitignore` if you keep it inside a repo directory.

## Step 5: Add your first account

The `auth add` command runs the OAuth browser flow, captures the refresh token, stashes it in the system keyring under the account key you supply, and stores the (non-secret) account config on disk.

```bash
uvx youtube-api-mcp auth add main-channel \
  --client-creds ~/.config/youtube-mcp/client_secret.json
```

A browser window opens. Walk through it carefully:

1. **Google account picker.** Select the Google account that owns (or manages) your target channel. This is the *user* account, not the channel itself.
2. **Brand-account picker.** This is the step most people miss. If the user account manages one or more brand accounts (the normal case for serious creators), Google shows a second screen titled "Choose an account" with one option per brand account plus the personal one. **Pick the brand account whose channel you want to drive.** The brand account you select here is the principal bound to the local key (`main-channel`). All subsequent API calls made with `account="main-channel"` act as that brand account. If you pick the wrong brand here, you can't fix it by re-prompting; you have to `auth remove` and re-add.
3. **Consent screen.** Google lists the scopes the server is requesting and warns that the app is unverified. Click through "Advanced -> Go to youtube-mcp (unsafe)" if you see the unverified warning. This is expected for a desktop app in Testing status.
4. **Approve.** The browser closes; the CLI prints the account summary.

Verify:

```bash
uvx youtube-api-mcp auth list
uvx youtube-api-mcp status
```

`auth list` should show your key, the resolved channel handle (`@something`), the channel ID, and the granted scopes.

### Scope selection

By default `auth add` requests a sensible read/write scope bundle. To restrict or extend, pass `--scopes`:

```bash
uvx youtube-api-mcp auth add readonly-account \
  --client-creds ~/.config/youtube-mcp/client_secret.json \
  --scopes readonly,analytics_readonly
```

Available scope names map to `YouTubeScope` enum values in `src/youtube_mcp/types.py`:

1. `readonly`: `https://www.googleapis.com/auth/youtube.readonly`
2. `manage`: `https://www.googleapis.com/auth/youtube`
3. `upload`: `https://www.googleapis.com/auth/youtube.upload`
4. `partner`: `https://www.googleapis.com/auth/youtubepartner`
5. `force_ssl`: `https://www.googleapis.com/auth/youtube.force-ssl`
6. `channel_memberships_creator`: `https://www.googleapis.com/auth/youtube.channel-memberships.creator`
7. `analytics_readonly`: `https://www.googleapis.com/auth/yt-analytics.readonly`
8. `analytics_monetary`: `https://www.googleapis.com/auth/yt-analytics-monetary.readonly`

Pass full URLs if you prefer. You can also repeat `--scopes` instead of comma-separating.

## Step 6: Configure the mutating-allowed account

By default the server gates all *mutating* tools (uploads, edits, comment posts, rating, abuse reports) behind a handle check. Mutating calls only proceed when the calling account's resolved YouTube handle matches a configured allow-handle.

The default allow-handle is **`@jsigvardt`**. If you are running the server against your own channel, change this. The allow-handle is read from the `YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE` environment variable, and enforcement is on when `YOUTUBE_MCP_ENFORCE_GUARD=1`.

Recommended setup for the original maintainer's channel:

```bash
export YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE='@jsigvardt'
export YOUTUBE_MCP_ENFORCE_GUARD=1
uvx youtube-api-mcp serve
```

Recommended setup if you are running this server against your own channel:

```bash
export YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE='@your-handle-here'
export YOUTUBE_MCP_ENFORCE_GUARD=1
uvx youtube-api-mcp serve
```

Wire these into your shell profile (`~/.zshrc`, `~/.bashrc`) or, better, into the MCP client config's `env` block so they are scoped to the server.

Read-only tools are not gated. The guard only triggers when a tool marked `mutating=True` is invoked.

## Step 7: Wire the server into your MCP client

### Claude Desktop

Edit `claude_desktop_config.json`. The file lives at:

1. macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add:

```json
{
  "mcpServers": {
    "youtube-mcp": {
      "command": "uvx",
      "args": ["youtube-api-mcp", "serve", "--transport", "stdio"],
      "env": {
        "YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE": "@your-handle-here",
        "YOUTUBE_MCP_ENFORCE_GUARD": "1"
      }
    }
  }
}
```

For local development against a cloned repo:

```json
{
  "mcpServers": {
    "youtube-mcp": {
      "command": "uv",
      "args": [
        "--directory", "/abs/path/to/youtube-mcp",
        "run", "youtube-mcp", "serve", "--transport", "stdio"
      ],
      "env": {
        "YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE": "@your-handle-here",
        "YOUTUBE_MCP_ENFORCE_GUARD": "1"
      }
    }
  }
}
```

Restart Claude Desktop. The `youtube-mcp` server should appear in the MCP indicator.

### OpenCode

In your OpenCode config file:

```json
{
  "mcp": {
    "youtube-mcp": {
      "type": "local",
      "command": ["uvx", "youtube-api-mcp", "serve", "--transport", "stdio"],
      "enabled": true,
      "environment": {
        "YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE": "@your-handle-here",
        "YOUTUBE_MCP_ENFORCE_GUARD": "1"
      }
    }
  }
}
```

## Verification

After everything is wired:

```bash
uvx youtube-api-mcp status
uvx youtube-api-mcp doctor
uvx youtube-api-mcp tools list --api youtube
```

1. `status` shows configured accounts, token freshness, and quota usage.
2. `doctor` runs a `youtube.tests.insert` auth-probe call per account. Each account should print `PASS`.
3. `tools list` enumerates every registered MCP tool with its API and quota cost.

If all three are clean, you're done. Hand the server to your agent.

## Troubleshooting

### `keyring.errors.NoKeyringError` or "no recommended backend was available"

The OS keyring is not available. Common causes:

1. Headless Linux box with no Secret Service daemon. Install and start `gnome-keyring-daemon` or `keepassxc` with the Secret Service plugin, or fall back to file-based keyring via `keyrings.alt` (less secure).
2. SSH session without `DBUS_SESSION_BUS_ADDRESS` exported. Run `dbus-launch youtube-api-mcp ...` or unlock the keyring inside the session.
3. macOS Keychain locked. Unlock it from Keychain Access and retry.

### "Token has been expired or revoked" after browser flow

Google revokes refresh tokens that sit unused for six months, or when the user changes password, or if the OAuth app is moved between Testing and Production. Re-run `auth refresh` first; if that fails too, run `auth remove` then `auth add` to redo the OAuth flow.

```bash
uvx youtube-api-mcp auth refresh main-channel
# if still broken:
uvx youtube-api-mcp auth remove main-channel --yes
uvx youtube-api-mcp auth add main-channel --client-creds ~/.config/youtube-mcp/client_secret.json
```

### Brand vs personal account confusion

A symptom: `auth list` shows a channel handle and ID, but it's not the channel you wanted to drive. The brand-account picker was skipped or the wrong brand was selected.

Fix:

```bash
uvx youtube-api-mcp auth remove main-channel --yes
uvx youtube-api-mcp auth add main-channel --client-creds ~/.config/youtube-mcp/client_secret.json
```

When the browser shows the "Choose an account" screen during step 5, **pick the brand account, not the personal one**. If the picker doesn't appear at all, your Google user does not have any brand accounts attached, and the personal account is the only choice. That's fine; just confirm `auth list` shows the channel handle you expect.

### Scope mismatch errors at runtime

Symptom: a tool call returns `Insufficient Permission` or `Request had insufficient authentication scopes`.

Cause: the account was created with a narrower scope set than the tool needs. For example, an account added with `--scopes readonly` cannot call `youtube_videos_insert`, which requires the `upload` scope.

Fix: re-run `auth add` with the broader scope set. The CLI will re-run the OAuth flow and overwrite the stored token.

```bash
uvx youtube-api-mcp auth add main-channel \
  --client-creds ~/.config/youtube-mcp/client_secret.json \
  --scopes manage,upload,analytics_readonly,force_ssl
```

### "App is blocked" or "Access blocked: youtube-mcp has not completed verification"

This is normal for a Desktop OAuth client in Testing status. Click **Advanced** on the warning screen and then **Go to youtube-mcp (unsafe)**. Google flags any unverified app this way; your client is not actually unsafe.

If you want to remove the warning entirely, you'd have to submit the OAuth consent screen for Google verification. That's overkill for personal or single-operator use.

### Mutating-guard rejects a call you expected to succeed

Symptom: a mutating tool returns an error about the allow-handle, even though the account looks correct.

Check three things:

1. `echo $YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE` matches the channel handle of the account you're calling. Handles are case-sensitive and must include the leading `@`.
2. `echo $YOUTUBE_MCP_ENFORCE_GUARD` is `1`. If unset or `0`, the guard is in advisory mode; if you wanted the call to go through, you need to flip enforcement off.
3. The account's resolved handle, shown by `uvx youtube-api-mcp auth list`, matches the allow-handle. If it doesn't, you authenticated with the wrong brand account; see the brand vs personal fix above.

### `youtube-mcp doctor` reports `FAIL` for every account

Most likely cause: the YouTube Data API is not enabled on the GCP project that issued the OAuth client. Re-do step 2 and confirm all three APIs are enabled. The `tests.insert` probe used by `doctor` is the cheapest call that exercises auth end-to-end, and it fails fast when the API itself is disabled.

### Quota errors mid-day

Each Google Cloud project has a daily YouTube Data API quota of 10,000 units by default. Heavy use (uploads cost 1,600 units each) burns through this fast.

1. `uvx youtube-api-mcp status` shows current usage per account.
2. Request a quota increase from the GCP console -> APIs & Services -> Quotas. Approval times vary.
3. The Analytics and Reporting APIs have their own separate quotas and are usually not the bottleneck.

### Where do tokens actually live?

In the OS keyring, under service name `youtube-mcp` and account name equal to your local key (for example `main-channel`). Inspect with:

1. macOS: open Keychain Access, search for `youtube-mcp`.
2. Linux (GNOME): `secret-tool search service youtube-mcp`.
3. Windows: Credential Manager -> Generic Credentials -> `youtube-mcp/<key>`.

The non-secret account config (key, client ID, channel ID, granted scopes) sits in `~/.config/youtube-mcp/accounts.json` (or the platform-equivalent config dir). Never put tokens in that file by hand; the CLI is the only sanctioned writer.

## Next steps

1. Read [`README.md`](README.md) for the safety policy on `videos.delete` and the tool inventory.
2. Read [`CLAUDE.md`](CLAUDE.md) if you plan to modify the codebase or add a new tool.
3. Point your agent at [`skills/youtube-mcp/SKILL.md`](skills/youtube-mcp/SKILL.md) so it knows when and how to call the server.
