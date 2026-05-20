# Account Management

This guide is for agents driving `youtube-mcp` against more than one YouTube channel from one operator host. It covers why multi-account matters, how to add and remove accounts, how to address them in tool calls, and the brand-account picker step that trips up most first-time setups.

## Why Multi-Account

YouTube ties every API call to one OAuth identity. That identity owns exactly one channel at a time. If you run two channels (say a personal vlog and a brand channel for a podcast), you need two separate token bundles, each with its own client credentials, scopes, and refresh token.

There are two channel shapes you'll encounter:

1. **Personal channel.** Tied directly to a Google account (`you@gmail.com`). One Google account, one channel.
2. **Brand account channel.** A channel owned by a "Brand Account" (Google's term for a channel container that's separate from any one person's identity). One Google account can manage many brand accounts, and each brand account hosts its own channel. See `https://support.google.com/youtube/answer/4628007` for Google's explainer.

The practical consequence: when an agent uploads, comments, or pulls analytics, it must say *which* channel. `youtube-mcp` does not infer this. Every tool call takes an `account="<handle>"` argument that resolves to one stored token bundle, which resolves to one channel.

If you're running:

- One personal channel, you'll have one account configured. You still pass `account="<handle>"` on every call.
- One personal channel plus a podcast brand channel, you'll have two accounts. Each one was authorized separately. Tool calls pick between them by handle.
- Five brand channels for five different products, you'll have five accounts. Same story.

There are no defaults. Passing the wrong `account` value uploads to the wrong channel. Be deliberate.

## Adding a New Account

Use `auth add` to register a new account. The handle you choose is local to your operator. Pick something memorable (`personal`, `podcast`, `gaming_channel`). It never leaves your machine and never appears on YouTube.

```bash
youtube-mcp auth add <handle> --client-creds <path-to-client-secret.json>
```

Arguments:

- `<handle>`: your local nickname for this account. Required.
- `--client-creds <path>`: path to the OAuth client secret JSON file you downloaded from Google Cloud Console (`APIs & Services` > `Credentials` > `OAuth 2.0 Client IDs`, type "Desktop application"). Required.
- `--scopes <scope1,scope2,...>`: comma-separated list of YouTube scopes to request. Defaults to a sensible read+manage set if omitted. See the scopes section below.

### What Happens When You Run It

1. The CLI reads the client creds file and validates it (must contain `installed.client_id`, `installed.client_secret`, redirect URIs, etc.).
2. It launches the installed-app OAuth flow. A browser window opens to `accounts.google.com`.
3. You sign in with the **Google account that owns or manages the target channel**.
4. **You hit the brand-account picker** (covered in detail below). This is where most setup mistakes happen.
5. You approve the requested scopes.
6. The browser hands a code back to the local listener. The CLI exchanges it for an access token + refresh token.
7. The CLI calls `channels.list(mine=true)` once to discover which channel the token authorized. It stores the channel ID and handle alongside your local handle.
8. The token bundle gets written to your OS keyring. The account metadata lands in your XDG config directory.

After step 8, the account is ready. Tool calls can reference it by your chosen `<handle>`.

### The Brand-Account Picker (Critical)

This is the step that decides which channel the token will speak for, and it's easy to miss.

After you sign in with your Google account, YouTube shows a picker titled something like **"Choose an account"** or **"Switch account"**. The options look like:

```
[ ] Your Name (you@gmail.com)        <- your personal channel
[ ] Acme Podcast                     <- brand channel #1
[ ] Gaming Channel                   <- brand channel #2
[ ] Cooking Stream                   <- brand channel #3
```

**The channel you click here is the channel this token will authorize.** Not the Google account. Not the most recently used channel. Exactly the one you click.

If you click your personal entry, the token authorizes the personal channel, regardless of how you named the local handle. If you name your local handle `podcast` but click your personal entry in the picker, every "podcast" tool call will hit your personal channel. There is no warning. The upload just goes to the wrong place.

What to do:

- **Read the picker labels carefully.** Brand channels show their channel name. Personal shows your Google account name.
- **Pick the channel you actually want.** If you want to upload to "Acme Podcast", click "Acme Podcast".
- **Verify after the flow finishes.** Run `youtube-mcp auth list` (next section). The output shows `channel_handle` and `channel_id` for each account. If the handle doesn't match what you expected, remove the account and re-add it, picking the right entry this time.

If the channel you want isn't in the picker:

- Your Google account doesn't have manager or owner access to that brand. Add yourself as a manager from `studio.youtube.com` while signed in as the brand owner, then retry.
- You signed in with the wrong Google account. Click "Use another account" in the picker and switch.

Do **not** bypass the picker by force-selecting a different Google account hoping it'll work out. It won't.

### Scopes

The `--scopes` flag controls what the token can do. Pick the minimum set that covers your workflows. Some common combinations:

- Read-only metadata and analytics: `youtube.readonly,yt-analytics.readonly`
- Upload + manage videos: `youtube.upload,youtube`
- Full management including comments and live: `youtube.force-ssl,youtube`
- Monetization analytics: add `yt-analytics-monetary.readonly`

Scopes apply per channel. If you authorize the `podcast` account with read-only and then need to upload, you'll hit a `403 insufficientPermissions` error. The fix is documented under "Account Lacks a Required Scope" below.

## Listing Accounts

Two ways, depending on whether you're at the shell or inside an MCP session.

**From the shell:**

```bash
youtube-mcp auth list
```

Output looks like:

```
handle           channel_handle        channel_id                          scopes
personal         @yourname             UCabcdef1234567890abcdef            youtube.readonly, youtube
podcast          @acmepodcast          UCxyzpqr0987654321xyzpqr            youtube.upload, youtube, youtube.force-ssl
gaming_channel   @gamingchannel        UCmnopqr5555555555mnopqr            youtube.upload, youtube
```

**From an MCP client:**

Read the `youtube://accounts` resource. The response is structured JSON with the same fields plus `created_at` timestamps. Use this when an agent needs to inspect available accounts before deciding which one to use.

Both views read from the same XDG config file. They never list a token, only metadata. Token material stays in the OS keyring.

## Removing an Account

```bash
youtube-mcp auth remove <handle>
```

This deletes the token bundle from the keyring **and** removes the account entry from the config file. It also clears any cached API service objects in the running process.

It does **not** revoke the OAuth grant on Google's side. The refresh token is gone locally, so the operator can no longer mint new access tokens, but if you want full revocation, sign in at `https://myaccount.google.com/permissions` and remove the app there.

Use `auth remove` when:

- You picked the wrong channel in the brand-account picker and need to start over.
- A channel was deleted or the brand account was dissolved.
- You're rotating client creds and want a clean re-auth.
- A team member who shouldn't have access anymore is shutting down their operator.

## Choosing the Right Account in a Tool Call

Every tool that hits the YouTube API takes an `account` argument. Pass the handle you chose during `auth add`.

```python
youtube_videos_list(account="podcast", part="snippet,statistics", mine=True)
youtube_videos_insert(account="gaming_channel", file_path="/uploads/clip.mp4", title="Speedrun #42")
youtube_playlists_list(account="personal", part="snippet", mine=True)
```

There is no default account. Omitting `account` is an error, not a fallback. This is deliberate: defaults cause uploads to land on the wrong channel.

Resolution flow inside the server:

1. Tool receives `account="podcast"`.
2. Server looks up the `podcast` entry in the account config store.
3. Server pulls the matching token bundle from the keyring.
4. If the access token has expired, server uses the refresh token to mint a new one and writes the new bundle back to the keyring. This happens transparently.
5. Server builds the appropriate `googleapiclient` service object (`youtube`, `youtubeAnalytics`, or `youtubereporting`) with those credentials, caches it, and runs the API call.

If `podcast` isn't configured, the server raises `AccountNotFoundError`. If its token bundle is missing or unrefreshable, you get a clear error pointing at the handle.

## Switching Accounts Mid-Workflow

There's nothing to switch. Every tool call is stateless with respect to accounts. Just pass a different `account` value on the next call.

A common pattern:

```python
# Pull recent analytics for the podcast
youtube_analytics_query(account="podcast", metrics="views,watchTime", start_date="2026-04-01", end_date="2026-04-30")

# Cross-post a teaser to the gaming channel
youtube_videos_insert(account="gaming_channel", file_path="/clips/teaser.mp4", title="Podcast preview")

# Update a personal-channel video's description
youtube_videos_update(account="personal", id="dQw4w9WgXcQ", description="Updated notes")
```

Each call resolves its own account, holds its own credentials, and runs against its own channel. There is no global "current account" state.

## Refreshing Tokens

Token refresh is automatic. The server checks `credentials.expired` before every API call. If the access token has expired and a refresh token exists, the server refreshes it via google-auth, writes the new bundle back to the keyring, and continues. You don't need to call anything.

What you might need to handle manually:

- **Refresh token revoked.** If the user revoked the grant at `https://myaccount.google.com/permissions`, refresh fails with `RefreshError`. Re-authorize with `youtube-mcp auth add <handle> --client-creds <path>` (same handle replaces the old entry's token).
- **Client secret rotated.** If you regenerated the OAuth client in Google Cloud Console, the stored `client_secret` no longer matches. Same fix: `auth add` with the new client creds JSON.
- **Refresh hasn't happened in a long time.** Google can expire refresh tokens after extended inactivity, especially for unverified test apps. Same fix.

In all three cases, the error message names the account so the agent can decide whether to re-auth automatically (rare, since OAuth needs a browser) or surface a "please re-authorize `<handle>`" message to the human operator.

## Account Lacks a Required Scope

Symptom: a tool call returns `403 insufficientPermissions` or a similar scope-related error.

Cause: the token was minted with a smaller scope set than the tool needs. For example, you authorized `podcast` with `youtube.readonly` but then tried `youtube_videos_insert`, which needs `youtube.upload`.

Fix: re-add the account with the broader scope set.

```bash
youtube-mcp auth add podcast --client-creds /path/to/client.json --scopes youtube.upload,youtube,youtube.force-ssl
```

Re-adding the same handle:

1. Replaces the old account entry.
2. Triggers a fresh OAuth flow with the new scope list.
3. You'll see the brand-account picker again. **Pick the same channel as before.** If you pick a different one, you've just rebound the handle to a different channel. Verify with `auth list` after.
4. The new token bundle replaces the old one in the keyring.

Scopes apply per channel, so re-authorizing `podcast` doesn't affect `personal` or `gaming_channel`. Each account has its own scope set.

## Worked Example: Uploading to a Brand Account

Goal: an agent needs to upload a new video to a brand channel called "Gaming Channel" that you manage from your Google account.

### One-Time Setup

1. Create or locate an OAuth client in Google Cloud Console. Project > APIs & Services > Credentials > Create Credentials > OAuth client ID > Application type "Desktop application". Download the JSON to `~/secrets/youtube-client.json`.

2. Enable the YouTube Data API v3 on that project.

3. Add the operator account:

   ```bash
   youtube-mcp auth add gaming_channel \
     --client-creds ~/secrets/youtube-client.json \
     --scopes youtube.upload,youtube,youtube.force-ssl
   ```

4. Browser opens. Sign in with the Google account that manages the brand.

5. **The brand-account picker appears.** Options shown:

   ```
   [ ] Your Name (you@gmail.com)
   [ ] Gaming Channel
   [ ] Some Other Brand
   ```

   Click "Gaming Channel". Not your name. Not the other brand. Gaming Channel.

6. Approve the requested scopes (`youtube.upload`, `youtube`, `youtube.force-ssl`).

7. Wait for the CLI to confirm. It will print the discovered channel handle and ID.

8. Verify:

   ```bash
   youtube-mcp auth list
   ```

   Confirm the `gaming_channel` row shows the correct `channel_handle` (something like `@gamingchannel`). If it shows your personal handle, you picked the wrong row in step 5. Run `youtube-mcp auth remove gaming_channel` and start again at step 3.

### Performing the Upload

```python
result = youtube_videos_insert(
    account="gaming_channel",
    file_path="/uploads/speedrun_42.mp4",
    title="Speedrun #42: New Personal Best",
    description="Cut 14 seconds off the previous run.",
    tags=["speedrun", "gaming"],
    category_id="20",
    privacy_status="public",
)
```

The server resolves `gaming_channel` to the stored credentials for Gaming Channel, refreshes the token if needed, and starts a resumable upload. Progress reports flow back through the MCP context. When complete, `result` contains the new video ID.

### Cross-Checking

Right after the upload, list recent videos for the same account to confirm it landed on the correct channel:

```python
youtube_videos_list(account="gaming_channel", part="snippet", mine=True, max_results=5)
```

The new video should appear at the top with the title you set. If you see it on `personal` instead, the `gaming_channel` handle is still bound to your personal channel. Remove and re-add, paying close attention to the picker.

## Quick Reference

| Operation | Command |
|---|---|
| Add account | `youtube-mcp auth add <handle> --client-creds <path>` |
| Add with explicit scopes | `youtube-mcp auth add <handle> --client-creds <path> --scopes <list>` |
| List accounts (CLI) | `youtube-mcp auth list` |
| List accounts (MCP) | Read resource `youtube://accounts` |
| Remove account | `youtube-mcp auth remove <handle>` |
| Use account in a tool | Pass `account="<handle>"` |
| Re-authorize after scope error | `youtube-mcp auth add <same-handle> --client-creds <path> --scopes <broader-list>` |
| Refresh tokens | Automatic on next API call |

## Things to Never Do

- Never share token bundles between accounts. Each account holds one channel's credentials. Copying them across handles will silently send calls to the wrong channel.
- Never click past the brand-account picker without reading it. The Google sign-in step authenticates *you*. The picker authorizes *the channel*. They're different decisions.
- Never assume `account` has a default. It doesn't. Always pass it explicitly.
- Never edit the keyring or XDG config files by hand. Use the `auth` subcommands.
