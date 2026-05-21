# YouTube Data API v3 — Tool Reference

Per-resource catalogue of every `youtube-mcp` tool that wraps the YouTube Data API v3. The Analytics and Reporting APIs live in sibling files (`analytics-api.md`, `reporting-api.md`). Top-level orchestration guidance is in `../SKILL.md`.

Tool names preserve the camelCase of YouTube resources where the API itself does (so `youtube_commentThreads_list`, `youtube_videoCategories_list`, `youtube_liveBroadcasts_transition`). Snake_case is used only where the YouTube method itself uses snake-cased multi-word resources (`channel_banners`, `third_party_links`).

Every tool's first positional argument is `account` (the credential profile key). `ctx` is the FastMCP `Context` and is supplied by the runtime, never by the caller.

```
> NOT EXPOSED: the YouTube Data API `videos.delete` method is intentionally absent
> from this MCP server. There is no tool that wraps it, by design. To take a video
> out of public circulation, call `youtube_videos_update` with a body that sets
> `status.privacyStatus` to `"private"` (or `"unlisted"`) instead. See SKILL.md
> for the rationale and `videos` section below for the safety callout.
```

## Conventions

- `scopes`: OAuth scopes required by the underlying API call. The values reference the `YouTubeScope` enum: `READONLY`, `MANAGE` (`https://www.googleapis.com/auth/youtube`), `UPLOAD`, `FORCE_SSL`, `PARTNER`, `CHANNEL_MEMBERSHIPS_CREATOR`.
- `cost`: YouTube Data API quota units per call. The project's daily quota is shared across all tools, so plan accordingly (see `quota.md`).
- `mutating`: `yes` means the tool is gated by the mutating-handle guard (`YOUTUBE_MCP_MUTATING_ALLOWED_HANDLE`). `no` means read-only and ungated.
- `example`: a one-line, abbreviated call. Real calls always pass `account` and may pass additional optional parameters.
- Most list endpoints accept `part`, `max_results`, and `page_token` for pagination. Follow `nextPageToken` from the previous response until it is absent.

## Activities

YouTube `activities` resource: chronological feed entries on a channel.

### `youtube_activities_list`

- Purpose: list activity events (uploads, likes, playlist additions, comments, etc.) for a channel, the caller, or the homepage feed.
- Signature: `(account, channel_id=None, mine=None, home=None, max_results=5, page_token=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_activities_list(account="primary", mine=True, max_results=25)`

## Captions

Caption tracks attached to a specific video.

### `youtube_captions_list`

- Purpose: list caption tracks for a video.
- Signature: `(account, part, video_id, id=None, on_behalf_of_content_owner=None, on_behalf_of=None)`
- Scopes: `READONLY`
- Cost: 50
- Mutating: no
- Example: `youtube_captions_list(account="primary", part="id,snippet", video_id="dQw4w9WgXcQ")`

### `youtube_captions_insert`

- Purpose: upload a new caption track for a video.
- Signature: `(account, part, caption_body, caption_file_path, sync=None, on_behalf_of=None, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 400
- Mutating: yes
- Example: `youtube_captions_insert(account="primary", part="snippet", caption_body={"snippet": {...}}, caption_file_path="captions/en.srt")`

### `youtube_captions_update`

- Purpose: update metadata and/or replace the file for an existing caption track.
- Signature: `(account, part, caption_id, caption_body=None, caption_file_path=None, sync=None, on_behalf_of=None, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 450
- Mutating: yes
- Example: `youtube_captions_update(account="primary", part="snippet", caption_id="abc123", caption_file_path="captions/en-fixed.srt")`

### `youtube_captions_download`

- Purpose: download a caption track to a local file (supports `srt`, `vtt`, `sbv`, etc. via `tfmt`; translation via `tlang`).
- Signature: `(account, caption_id, tfmt=None, tlang=None, on_behalf_of=None, on_behalf_of_content_owner=None, *, output_path)`
- Scopes: `READONLY`
- Cost: 200
- Mutating: no
- Example: `youtube_captions_download(account="primary", caption_id="abc123", tfmt="vtt", output_path="out/en.vtt")`

### `youtube_captions_delete`

> SAFETY: deletes the caption track irreversibly. Mutating guard applies.

- Purpose: delete a caption track from a video.
- Signature: `(account, caption_id, on_behalf_of=None, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_captions_delete(account="primary", caption_id="abc123")`

## Channels

The channel resource itself.

### `youtube_channels_list`

- Purpose: fetch one or more channels by ID, handle, username, ownership filter, or `mine=True`.
- Signature: `(account, part="snippet,contentDetails,statistics", category_id=None, for_handle=None, for_username=None, id=None, managed_by_me=None, mine=None, hl=None, max_results=5, on_behalf_of_content_owner=None, page_token=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_channels_list(account="primary", for_handle="@youtubecreators")`

### `youtube_channels_update`

- Purpose: update channel metadata (branding, status, localizations, invideo promotion).
- Signature: `(account, part, channel_body, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_channels_update(account="primary", part="brandingSettings", channel_body={"id": "UC...", "brandingSettings": {...}})`

## Channel banners

Upload-and-bind workflow for the channel banner image.

### `youtube_channel_banners_insert`

- Purpose: upload a banner image and receive a banner URL that can then be bound to the channel via `youtube_channels_update` with `part="brandingSettings"`.
- Signature: `(account, banner_file_path, channel_id=None, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `UPLOAD`
- Cost: 50
- Mutating: yes
- Example: `youtube_channel_banners_insert(account="primary", banner_file_path="branding/banner-2560x1440.png")`

## Channel sections

Sections that appear on a channel's homepage.

### `youtube_channelSections_list`

- Purpose: list channel sections for a channel, by ID, or for the caller (`mine=True`).
- Signature: `(account, part, channel_id=None, id=None, mine=None, hl=None, on_behalf_of_content_owner=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_channelSections_list(account="primary", part="snippet,contentDetails", mine=True)`

### `youtube_channelSections_insert`

- Purpose: create a new channel section.
- Signature: `(account, part, section_body, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_channelSections_insert(account="primary", part="snippet,contentDetails", section_body={"snippet": {"type": "recentUploads", "style": "horizontalRow"}})`

### `youtube_channelSections_update`

- Purpose: update an existing channel section's body.
- Signature: `(account, part, section_body, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_channelSections_update(account="primary", part="snippet", section_body={"id": "CS...", "snippet": {"title": "Top picks"}})`

### `youtube_channelSections_delete`

> SAFETY: irreversible removal of a channel section. Mutating guard applies.

- Purpose: delete a channel section by ID.
- Signature: `(account, id, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_channelSections_delete(account="primary", id="CS...")`

## Third-party links

Linking tokens that associate a YouTube channel with an external identity (lives in `channels.py`).

### `youtube_third_party_links_list`

- Purpose: list third-party links attached to a channel.
- Signature: `(account, part="snippet,status,linkingToken", linking_token=None, type=None, external_channel_id=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_third_party_links_list(account="primary", external_channel_id="UC...")`

### `youtube_third_party_links_insert`

- Purpose: create a third-party link binding.
- Signature: `(account, part, link_body, external_channel_id=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_third_party_links_insert(account="primary", part="snippet,status", link_body={...})`

### `youtube_third_party_links_update`

- Purpose: update an existing third-party link.
- Signature: `(account, part, link_body, external_channel_id=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_third_party_links_update(account="primary", part="snippet,status", link_body={...})`

### `youtube_third_party_links_delete`

> SAFETY: removes the binding between the channel and the external identity. Mutating guard applies.

- Purpose: delete a third-party link by `linking_token` and `type`.
- Signature: `(account, linking_token, type, external_channel_id=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_third_party_links_delete(account="primary", linking_token="lt_...", type="channelToStoreLink")`

## Comments

Individual comment leaves (top-level or reply). For top-level threading, see CommentThreads.

### `youtube_comments_list`

- Purpose: list comments by ID, or fetch replies under a parent thread.
- Signature: `(account, part, id=None, parent_id=None, max_results=20, page_token=None, text_format=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_comments_list(account="primary", part="snippet", parent_id="Ugxxx...")`

### `youtube_comments_insert`

- Purpose: post a reply to an existing top-level comment thread.
- Signature: `(account, part, comment_body)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_comments_insert(account="primary", part="snippet", comment_body={"snippet": {"parentId": "Ugxxx...", "textOriginal": "Thanks!"}})`

### `youtube_comments_update`

- Purpose: edit an existing comment's text (only the comment author can update).
- Signature: `(account, part, comment_body)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_comments_update(account="primary", part="snippet", comment_body={"id": "Ugxxx...", "snippet": {"textOriginal": "Edited text"}})`

### `youtube_comments_setModerationStatus`

> SAFETY: bulk-changes the public visibility of comments and can optionally ban the comment author globally on the channel. Mutating guard applies. Double-check the `id` list before calling. Setting `ban_author=True` is sticky and should be used sparingly.

- Purpose: moderate one or more comments to `heldForReview`, `published`, or `rejected`, optionally banning the author.
- Signature: `(account, id: list[str], moderation_status: Literal["heldForReview", "published", "rejected"], ban_author=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_comments_setModerationStatus(account="primary", id=["Ugxxx..."], moderation_status="rejected", ban_author=False)`

### `youtube_comments_markAsSpam`

- Purpose: flag one or more comments as spam.
- Signature: `(account, id: list[str])`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_comments_markAsSpam(account="primary", id=["Ugxxx...", "Ugyyy..."])`

### `youtube_comments_delete`

> SAFETY: irreversibly removes a comment. Mutating guard applies.

- Purpose: delete a comment by ID.
- Signature: `(account, id)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_comments_delete(account="primary", id="Ugxxx...")`

## Comment threads

Top-level comment threads (the public-facing "comment + replies" unit).

### `youtube_commentThreads_list`

- Purpose: list top-level threads by channel, video, or `allThreadsRelatedToChannelId`, with optional search and moderation filters.
- Signature: `(account, part="snippet,replies", channel_id=None, video_id=None, all_threads_related_to_channel_id=None, search_terms=None, moderation_status=None, order=None, text_format=None, max_results=20, page_token=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_commentThreads_list(account="primary", video_id="dQw4w9WgXcQ", order="time")`

### `youtube_commentThreads_insert`

- Purpose: post a new top-level thread (a top-level comment on a channel or video).
- Signature: `(account, body, part="snippet")`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_commentThreads_insert(account="primary", body={"snippet": {"channelId": "UC...", "videoId": "dQw...", "topLevelComment": {"snippet": {"textOriginal": "First!"}}}})`

## i18n

Read-only catalogues exposed for localization.

### `youtube_i18nLanguages_list`

- Purpose: list the languages the YouTube site supports.
- Signature: `(account, part="snippet", hl=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_i18nLanguages_list(account="primary", hl="en_US")`

### `youtube_i18nRegions_list`

- Purpose: list the country regions YouTube supports.
- Signature: `(account, part="snippet", hl=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_i18nRegions_list(account="primary", hl="en_US")`

## Members and membership levels

Channel membership data. Requires the channel-memberships creator scope.

### `youtube_members_list`

- Purpose: list active channel members, optionally filtered by membership level or member channel ID.
- Signature: `(account, part, mode=None, max_results=None, page_token=None, has_access_to_level=None, filter_by_member_channel_id=None)`
- Scopes: `CHANNEL_MEMBERSHIPS_CREATOR`
- Cost: 1
- Mutating: no
- Example: `youtube_members_list(account="primary", part="snippet", mode="all_current")`

### `youtube_membershipsLevels_list`

- Purpose: list the membership levels offered by the creator channel.
- Signature: `(account, part)`
- Scopes: `CHANNEL_MEMBERSHIPS_CREATOR`
- Cost: 1
- Mutating: no
- Example: `youtube_membershipsLevels_list(account="primary", part="snippet")`

## Playlists

Playlist resource itself.

### `youtube_playlists_list`

- Purpose: list playlists by channel, ID, or `mine=True`.
- Signature: `(account, part="snippet,contentDetails", channel_id=None, id=None, mine=None, hl=None, max_results=5, page_token=None, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_playlists_list(account="primary", mine=True)`

### `youtube_playlists_insert`

- Purpose: create a new playlist.
- Signature: `(account, part, playlist_body, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `MANAGE`
- Cost: 50
- Mutating: yes
- Example: `youtube_playlists_insert(account="primary", part="snippet,status", playlist_body={"snippet": {"title": "Best of 2026"}, "status": {"privacyStatus": "unlisted"}})`

### `youtube_playlists_update`

- Purpose: update playlist metadata.
- Signature: `(account, part, playlist_body, on_behalf_of_content_owner=None)`
- Scopes: `MANAGE`
- Cost: 50
- Mutating: yes
- Example: `youtube_playlists_update(account="primary", part="snippet", playlist_body={"id": "PL...", "snippet": {"title": "Renamed"}})`

### `youtube_playlists_delete`

> SAFETY: irreversibly removes the playlist (its items survive on the source videos but the curation is lost). Mutating guard applies.

- Purpose: delete a playlist by ID.
- Signature: `(account, id, on_behalf_of_content_owner=None)`
- Scopes: `MANAGE`
- Cost: 50
- Mutating: yes
- Example: `youtube_playlists_delete(account="primary", id="PL...")`

## Playlist items

Membership of videos inside a playlist.

### `youtube_playlistItems_list`

- Purpose: list items in a playlist or look up specific items by ID or videoId.
- Signature: `(account, part="snippet,contentDetails", id=None, playlist_id=None, max_results=5, page_token=None, video_id=None, on_behalf_of_content_owner=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_playlistItems_list(account="primary", playlist_id="PL...", max_results=50)`

### `youtube_playlistItems_insert`

- Purpose: append a video to a playlist (or insert at a specific position via `snippet.position`).
- Signature: `(account, part, item_body, on_behalf_of_content_owner=None)`
- Scopes: `MANAGE`
- Cost: 50
- Mutating: yes
- Example: `youtube_playlistItems_insert(account="primary", part="snippet", item_body={"snippet": {"playlistId": "PL...", "resourceId": {"kind": "youtube#video", "videoId": "dQw..."}}})`

### `youtube_playlistItems_update`

- Purpose: change the position or note of an existing playlist item.
- Signature: `(account, part, item_body, on_behalf_of_content_owner=None)`
- Scopes: `MANAGE`
- Cost: 50
- Mutating: yes
- Example: `youtube_playlistItems_update(account="primary", part="snippet", item_body={"id": "PLI...", "snippet": {"playlistId": "PL...", "resourceId": {...}, "position": 0}})`

### `youtube_playlistItems_delete`

> SAFETY: irreversibly removes a video from the playlist (the video itself is unaffected). Mutating guard applies.

- Purpose: remove a playlist item by ID.
- Signature: `(account, id, on_behalf_of_content_owner=None)`
- Scopes: `MANAGE`
- Cost: 50
- Mutating: yes
- Example: `youtube_playlistItems_delete(account="primary", id="PLI...")`

## Playlist images

Custom cover images attached to playlists. Deleting a playlist image removes only the custom cover; the playlist and its videos are untouched.

### `youtube_playlistImages_list`

- Purpose: list custom cover images for a playlist.
- Signature: `(account, part, parent=None, page_token=None, max_results=None, on_behalf_of_content_owner=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_playlistImages_list(account="primary", part="snippet", parent="playlists/PL...")`

### `youtube_playlistImages_insert`

- Purpose: upload a custom playlist cover image from a local image file.
 - Signature: `(account, part, image_body, image_file_path, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_playlistImages_insert(account="primary", part="snippet", image_body={"snippet": {"playlistId": "PL..."}}, image_file_path="covers/playlist.jpg")`

### `youtube_playlistImages_update`

- Purpose: replace or update a custom playlist cover image from a local image file.
- Signature: `(account, part, image_body, image_file_path, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_playlistImages_update(account="primary", part="snippet", image_body={"id": "PLI...", "snippet": {"playlistId": "PL..."}}, image_file_path="covers/new.jpg")`

### `youtube_playlistImages_delete`

> SAFETY: removes only the custom playlist cover image. The playlist and videos remain untouched. Mutating guard applies.

- Purpose: delete a custom playlist cover image by ID.
- Signature: `(account, id, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_playlistImages_delete(account="primary", id="PLI...")`

## Search

> QUOTA WARNING: `search.list` costs **100 units per call** regardless of `max_results`. A single naive scan can burn through a 10,000-unit daily quota in 100 calls. Always:
>
> - request only the `part` you need (commonly `snippet`),
> - cap `max_results` near the desired page size (max 50),
> - follow `nextPageToken` deliberately rather than greedily,
> - prefer `youtube_videos_list`, `youtube_channels_list`, or `youtube_playlistItems_list` when you already have IDs (cost 1 each).

### `youtube_search_list`

- Purpose: hybrid search across videos, channels, and playlists with extensive filtering (geo, freshness, video traits, topics, content-owner scoping).
- Signature: `(account, part, channel_id=None, channel_type=None, event_type=None, for_content_owner=None, for_developer=None, for_mine=None, location=None, location_radius=None, max_results=5, on_behalf_of_content_owner=None, order=None, page_token=None, published_after=None, published_before=None, q=None, region_code=None, relevance_language=None, safe_search=None, topic_id=None, type=None, video_caption=None, video_category_id=None, video_definition=None, video_dimension=None, video_duration=None, video_embeddable=None, video_license=None, video_paid_product_placement=None, video_syndicated=None, video_type=None)`
- Scopes: `READONLY`
- Cost: 100
- Mutating: no
- Example: `youtube_search_list(account="primary", part="snippet", q="opencode demo", type="video", order="date", max_results=25)`
- Paging: stop iterating as soon as you have enough results. YouTube caps `search.list` at approximately 500 results total per query regardless of `nextPageToken`.

## Subscriptions

Channel-to-channel subscriptions.

### `youtube_subscriptions_list`

- Purpose: list subscriptions by channel, mine, my subscribers, my recent subscribers, or by `for_channel_id` to detect overlap.
- Signature: `(account, part, channel_id=None, id=None, mine=None, my_recent_subscribers=None, my_subscribers=None, for_channel_id=None, max_results=5, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None, order=None, page_token=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_subscriptions_list(account="primary", part="snippet", mine=True, max_results=50)`

### `youtube_subscriptions_insert`

- Purpose: subscribe the authenticated channel to another channel.
- Signature: `(account, part, subscription_body)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_subscriptions_insert(account="primary", part="snippet", subscription_body={"snippet": {"resourceId": {"kind": "youtube#channel", "channelId": "UC..."}}})`

### `youtube_subscriptions_delete`

> SAFETY: cancels the subscription immediately. Mutating guard applies.

- Purpose: unsubscribe by subscription ID.
- Signature: `(account, id)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_subscriptions_delete(account="primary", id="sub_...")`

## Videos

> **DELETE BANNER**: there is no tool that wraps the YouTube Data API `videos.delete` endpoint. The omission is by design and is enforced in source, tests, and this reference doc. To take a public video out of circulation, call `youtube_videos_update` with a body that sets `status.privacyStatus` to `"unlisted"` or `"private"`. See `../SKILL.md` for the full rationale.

### `youtube_videos_list`

- Purpose: fetch videos by ID, retrieve charts (e.g. `mostPopular`), look up the caller's rating context, or list the authenticated account's uploaded videos with `mine=True`.
- Signature: `(account, part, chart=None, id=None, mine=False, my_rating=None, hl=None, max_height=None, max_width=None, max_results=None, on_behalf_of_content_owner=None, page_token=None, region_code=None, video_category_id=None)`
- Scopes: `READONLY`
- Cost: 3 max (`mine=True` traverses `channels.list` -> `playlistItems.list` -> `videos.list`; raw `id`/`chart` calls still use one API request)
- Mutating: no
- Example: `youtube_videos_list(account="primary", part="snippet,statistics", mine=True, max_results=25)`

### `youtube_videos_insert`

- Purpose: upload a new video using a resumable upload (8 MiB chunks, progress reported via `ctx.report_progress`).
- Signature: `(account, part, video_body, file_path, notify_subscribers=None, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 1600
- Mutating: yes
- Example: `youtube_videos_insert(account="primary", part="snippet,status", video_body={"snippet": {"title": "Demo", "categoryId": "22"}, "status": {"privacyStatus": "unlisted"}}, file_path="uploads/demo.mp4")`

### `youtube_videos_update`

- Purpose: update video metadata, status, localizations, recording details, or topic details. **This is the canonical way to make a video private or unlisted in lieu of a delete.**
- Signature: `(account, part, video_body, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example (privatize): `youtube_videos_update(account="primary", part="status", video_body={"id": "dQw...", "status": {"privacyStatus": "private"}})`

### `youtube_videos_rate`

- Purpose: like, dislike, or clear the caller's rating on a video.
- Signature: `(account, id, rating: VideoRating)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_videos_rate(account="primary", id="dQw...", rating="like")`

### `youtube_videos_getRating`

- Purpose: read back the caller's current rating for one or more videos.
- Signature: `(account, id, on_behalf_of_content_owner=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_videos_getRating(account="primary", id="dQw...")`

### `youtube_videos_reportAbuse`

- Purpose: file an abuse report against a video using a reason from `youtube_videoAbuseReportReasons_list`.
- Signature: `(account, abuse_report_body, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_videos_reportAbuse(account="primary", abuse_report_body={"videoId": "dQw...", "reasonId": "Y", "language": "en"})`

### `youtube_videoTrainability_get`

- Purpose: read the third-party AI training permission state for a video.
- Signature: `(account, id)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_videoTrainability_get(account="primary", id="dQw...")`

## Video assets

Thumbnails and channel watermarks (binary uploads keyed by video or channel).

### `youtube_thumbnails_set`

- Purpose: replace the custom thumbnail on a video.
- Signature: `(account, video_id, image_file_path, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_thumbnails_set(account="primary", video_id="dQw...", image_file_path="thumbs/demo.jpg")`

### `youtube_watermarks_set`

- Purpose: set the channel watermark (the badge YouTube overlays on the player).
- Signature: `(account, channel_id, watermark_body, image_file_path, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_watermarks_set(account="primary", channel_id="UC...", watermark_body={"timing": {"type": "offsetFromEnd", "offsetMs": 5000, "durationMs": 10000}}, image_file_path="branding/watermark.png")`

### `youtube_watermarks_unset`

> SAFETY: removes the active channel watermark. Mutating guard applies.

- Purpose: clear the current channel watermark.
- Signature: `(account, channel_id, on_behalf_of_content_owner=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_watermarks_unset(account="primary", channel_id="UC...")`

## Video meta

Static catalogues used when composing `videos.insert`/`videos.update`/`videos.reportAbuse` bodies.

### `youtube_videoCategories_list`

- Purpose: list video categories, optionally for a region.
- Signature: `(account, part="snippet", hl=None, id=None, region_code=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_videoCategories_list(account="primary", region_code="US")`

### `youtube_videoAbuseReportReasons_list`

- Purpose: list valid abuse-report reasons for use with `youtube_videos_reportAbuse`.
- Signature: `(account, part="snippet", hl=None)`
- Scopes: `FORCE_SSL`
- Cost: 1
- Mutating: no
- Example: `youtube_videoAbuseReportReasons_list(account="primary")`

## Livestream — Broadcasts

`liveBroadcasts` is the scheduled "event" half of a live stream. Pair with `liveStreams` (the ingest half) via `bind`.

### `youtube_liveBroadcasts_list`

- Purpose: list broadcasts by ID, status, type, or `mine=True`.
- Signature: `(account, part="id,snippet,contentDetails,status", broadcast_status=None, broadcast_type=None, id=None, mine=None, max_results=5, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None, page_token=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_liveBroadcasts_list(account="primary", broadcast_status="upcoming", mine=True)`

### `youtube_liveBroadcasts_insert`

- Purpose: schedule a new broadcast event.
- Signature: `(account, part, broadcast_body, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveBroadcasts_insert(account="primary", part="snippet,contentDetails,status", broadcast_body={"snippet": {"title": "Demo", "scheduledStartTime": "2026-06-01T17:00:00Z"}, "status": {"privacyStatus": "unlisted"}})`

### `youtube_liveBroadcasts_update`

- Purpose: edit broadcast metadata or content details before/during the event.
- Signature: `(account, part, broadcast_body, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveBroadcasts_update(account="primary", part="snippet", broadcast_body={"id": "bc_...", "snippet": {"title": "Demo (updated)"}})`

### `youtube_liveBroadcasts_delete`

> SAFETY: irreversibly removes a scheduled or completed broadcast. Mutating guard applies. Prefer transitioning to `complete` instead of deleting if you want to preserve the archive.

- Purpose: delete a broadcast by ID.
- Signature: `(account, id, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveBroadcasts_delete(account="primary", id="bc_...")`

### `youtube_liveBroadcasts_bind`

- Purpose: bind a broadcast to a `liveStream` (or unbind by omitting `stream_id`).
- Signature: `(account, id, part, stream_id=None, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveBroadcasts_bind(account="primary", id="bc_...", part="id,contentDetails", stream_id="ls_...")`

### `youtube_liveBroadcasts_transition`

> SAFETY: transitions are state changes with viewer-facing effects (`testing`, `live`, `complete`). Mutating guard applies. `complete` is one-way.

- Purpose: drive the broadcast through its lifecycle states.
- Signature: `(account, id, broadcast_status: LiveBroadcastTransitionStatus, part, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveBroadcasts_transition(account="primary", id="bc_...", broadcast_status="live", part="id,status")`

### `youtube_liveBroadcasts_cuepoint`

- Purpose: insert an in-stream cue point (ad break) during a live broadcast.
- Signature: `(account, id, cuepoint_body, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveBroadcasts_cuepoint(account="primary", id="bc_...", cuepoint_body={"cueType": "cueTypeAd", "durationSecs": 30})`

## Livestream — Streams

`liveStreams` is the ingest configuration side of a live event.

### `youtube_liveStreams_list`

- Purpose: list live streams by ID or `mine=True`.
- Signature: `(account, part="id,snippet,cdn,status", id=None, mine=None, max_results=5, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None, page_token=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_liveStreams_list(account="primary", mine=True)`

### `youtube_liveStreams_insert`

- Purpose: create a new live stream (ingest endpoint configuration).
- Signature: `(account, part, stream_body, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveStreams_insert(account="primary", part="snippet,cdn,contentDetails", stream_body={"snippet": {"title": "Main feed"}, "cdn": {"resolution": "1080p", "frameRate": "30fps", "ingestionType": "rtmp"}})`

### `youtube_liveStreams_update`

- Purpose: update an existing live stream's metadata or CDN settings.
- Signature: `(account, part, stream_body, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveStreams_update(account="primary", part="snippet", stream_body={"id": "ls_...", "snippet": {"title": "Main feed (HD)"}})`

### `youtube_liveStreams_delete`

> SAFETY: irreversibly removes a stream ingest configuration. Mutating guard applies.

- Purpose: delete a stream by ID.
- Signature: `(account, id, on_behalf_of_content_owner=None, on_behalf_of_content_owner_channel=None)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveStreams_delete(account="primary", id="ls_...")`

## Live chat

Real-time chat surface attached to a live broadcast.

### `youtube_liveChatMessages_list`

- Purpose: poll the live chat for a broadcast's `liveChatId`. Use the response's `pollingIntervalMillis` to pace subsequent calls.
- Signature: `(account, live_chat_id, part, hl=None, max_results=None, page_token=None, profile_image_size=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_liveChatMessages_list(account="primary", live_chat_id="lc_...", part="snippet,authorDetails")`

### `youtube_liveChatMessages_insert`

- Purpose: post a chat message to a live chat.
- Signature: `(account, part, message_body)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveChatMessages_insert(account="primary", part="snippet", message_body={"snippet": {"liveChatId": "lc_...", "type": "textMessageEvent", "textMessageDetails": {"messageText": "Hi all"}}})`

### `youtube_liveChatMessages_delete`

> SAFETY: removes the chat message from the public stream. Mutating guard applies.

- Purpose: delete a chat message by ID.
- Signature: `(account, id)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveChatMessages_delete(account="primary", id="lcm_...")`

### `youtube_liveChatMessages_transition`

- Purpose: transition a live chat message event to a new status.
- Signature: `(account, id, status)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveChatMessages_transition(account="primary", id="lcm_...", status="closed")`

### `youtube_liveChatModerators_list`

- Purpose: list moderators on a live chat.
- Signature: `(account, live_chat_id, part, max_results=None, page_token=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_liveChatModerators_list(account="primary", live_chat_id="lc_...", part="snippet")`

### `youtube_liveChatModerators_insert`

- Purpose: grant moderator status to a user on a live chat.
- Signature: `(account, part, moderator_body)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveChatModerators_insert(account="primary", part="snippet", moderator_body={"snippet": {"liveChatId": "lc_...", "moderatorDetails": {"channelId": "UC..."}}})`

### `youtube_liveChatModerators_delete`

> SAFETY: revokes moderator privileges. Mutating guard applies.

- Purpose: remove a moderator by ID.
- Signature: `(account, id)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveChatModerators_delete(account="primary", id="lcm_...")`

### `youtube_liveChatBans_insert`

> SAFETY: bans block a user from participating in the chat (`permanent` or `temporary` with `banDurationSeconds`). This is a high-impact moderation action with viewer-facing effects. Mutating guard applies. Verify the `channelId` in `bannedUserDetails` before calling.

- Purpose: ban a user from a live chat.
- Signature: `(account, part, ban_body)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveChatBans_insert(account="primary", part="snippet", ban_body={"snippet": {"liveChatId": "lc_...", "type": "temporary", "banDurationSeconds": 300, "bannedUserDetails": {"channelId": "UC..."}}})`

### `youtube_liveChatBans_delete`

> SAFETY: lifts a chat ban. Mutating guard applies.

- Purpose: remove a chat ban by ID.
- Signature: `(account, id)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_liveChatBans_delete(account="primary", id="lcb_...")`

## Super Chat events

Read-only stream of monetary chat events tied to live broadcasts.

### `youtube_superChatEvents_list`

- Purpose: list Super Chat and Super Sticker events for the authenticated channel.
- Signature: `(account, part, hl=None, max_results=5, page_token=None)`
- Scopes: `READONLY`
- Cost: 1
- Mutating: no
- Example: `youtube_superChatEvents_list(account="primary", part="snippet", max_results=50)`

## Abuse reports

Channel-level abuse reports (distinct from `videos.reportAbuse`).

### `youtube_abuseReports_insert`

- Purpose: submit an abuse report against a YouTube entity.
- Signature: `(account, part, abuse_report_body)`
- Scopes: `FORCE_SSL`
- Cost: 50
- Mutating: yes
- Example: `youtube_abuseReports_insert(account="primary", part="snippet", abuse_report_body={"snippet": {"abuseTypes": [{"id": "S"}], "subject": {"id": "UC...", "type": "channel"}, "description": "..."}})`

## Composition examples

A handful of common flows expressed as call sequences. Quotas are aggregate; budget accordingly.

### Upload + tag + thumbnail

Goal: ship a new unlisted video, attach a custom thumbnail, and tag it with the right category.

1. `youtube_videoCategories_list(account, region_code="US")` — pick the right `categoryId` (cost 1).
2. `youtube_videos_insert(account, part="snippet,status", video_body={"snippet": {"title": "...", "categoryId": "22"}, "status": {"privacyStatus": "unlisted"}}, file_path="upload.mp4")` — resumable upload (cost 1600).
3. `youtube_thumbnails_set(account, video_id=<from step 2>, image_file_path="thumb.jpg")` — custom thumbnail (cost 50).

Total quota: ~1651 units. Make sure the mutating guard is configured before steps 2 and 3.

### Privatize a video (instead of delete)

1. `youtube_videos_update(account, part="status", video_body={"id": "<videoId>", "status": {"privacyStatus": "private"}})` — single mutating call (cost 50). This is the documented substitute for the deliberately absent delete endpoint (see the Videos section callout).

### Schedule a live broadcast and bind ingest

1. `youtube_liveStreams_insert(account, part="snippet,cdn,contentDetails", stream_body={...})` — create stream (cost 50).
2. `youtube_liveBroadcasts_insert(account, part="snippet,contentDetails,status", broadcast_body={...})` — create event (cost 50).
3. `youtube_liveBroadcasts_bind(account, id=<broadcastId>, part="id,contentDetails", stream_id=<streamId>)` — pair them (cost 50).
4. `youtube_liveBroadcasts_transition(account, id=<broadcastId>, broadcast_status="testing", part="id,status")` then `"live"` when ready, then `"complete"` to end (cost 50 each).
5. After completion, poll `youtube_liveChatMessages_list` only if you need archived chat (cost 1 per page).

### Moderate a comment thread

1. `youtube_commentThreads_list(account, video_id="<id>", order="time", moderation_status="heldForReview")` — surface held threads (cost 1).
2. `youtube_comments_setModerationStatus(account, id=[...], moderation_status="rejected", ban_author=False)` — bulk reject (cost 50).
3. Optional: `youtube_comments_markAsSpam(account, id=[...])` if you also want them flagged (cost 50).

### Build a curated playlist

1. `youtube_playlists_insert(account, part="snippet,status", playlist_body={"snippet": {"title": "Best of"}, "status": {"privacyStatus": "unlisted"}})` — create playlist (cost 50).
2. For each video to add: `youtube_playlistItems_insert(account, part="snippet", item_body={"snippet": {"playlistId": "<pid>", "resourceId": {"kind": "youtube#video", "videoId": "<vid>"}}})` (cost 50 each).
3. `youtube_playlists_list(account, mine=True, part="snippet,contentDetails")` to confirm (cost 1).

## Quota cheat sheet

- Read (`*_list`, `*_getRating`): 1 unit each.
- `captions.list`: 50 units.
- `captions.download`: 200 units.
- `captions.insert`: 400 units. `captions.update`: 450 units.
- All other mutating Data API calls in this server: 50 units each.
- `search.list`: **100 units per call** (see the search section above).
- `videos.insert`: **1600 units per upload**.

## Cross-references

- `../SKILL.md` — top-level skill, includes the absent-delete rationale and mutating guard onboarding.
- `analytics-api.md` — YouTube Analytics API tools (separate API).
- `reporting-api.md` — YouTube Reporting API tools (separate API).
- `quota.md` — quota planning across all three APIs.
- Official Google docs: `https://developers.google.com/youtube/v3/docs/` (per-resource pages mirror the section names above).
