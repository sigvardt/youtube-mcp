# Sub R2 deprecated kwargs audit

## Summary
- Tool wrappers touched: 91
- Discovery-scope params audited: 349
- Status counts: DEPRECATED 2, REMOVED 4, RENAMED 0, UNKNOWN 0
- Omitted from counts: 342 VALID params, googleapiclient transport kwargs `body` and `media_body`, and the intentional `analytics_reports_query.extra_params` passthrough.
- Confirmed clean: `youtube_search_list` no longer forwards `relatedToVideoId`.

## [2026-05-20] Sub R2 deprecated kwargs audit

### youtube.activities.list
| tool function name | parameter | status | source URL or doc ref | recommended action |
| --- | --- | --- | --- | --- |
| `youtube_activities_list` | `home` | `DEPRECATED` | code: `https://github.com/sigvardt/youtube-mcp/blob/693d55d4341600b61e356d39b7ff660f70fe5e87/src/youtube_mcp/tools/activities.py#L36-L66`; discovery: `https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest` | mark deprecated in docstring |

Discovery snapshot:
```json
home {"deprecated": true, "location": "query", "type": "boolean"}
```

### youtube.channelSections.list
| tool function name | parameter | status | source URL or doc ref | recommended action |
| --- | --- | --- | --- | --- |
| `youtube_channelSections_list` | `hl` | `DEPRECATED` | code: `https://github.com/sigvardt/youtube-mcp/blob/693d55d4341600b61e356d39b7ff660f70fe5e87/src/youtube_mcp/tools/channel_sections.py#L36-L60`; discovery: `https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest` | mark deprecated in docstring |

Discovery snapshot:
```json
hl {"deprecated": true, "description": "Return content in specified language", "location": "query", "type": "string"}
```

### youtubeAnalytics.reports.query
| tool function name | parameter | status | source URL or doc ref | recommended action |
| --- | --- | --- | --- | --- |
| `youtube_analytics_reports_query` | `segment` | `REMOVED` | code: `https://github.com/sigvardt/youtube-mcp/blob/693d55d4341600b61e356d39b7ff660f70fe5e87/src/youtube_mcp/tools/analytics_reports.py#L126-L159` and `https://github.com/sigvardt/youtube-mcp/blob/693d55d4341600b61e356d39b7ff660f70fe5e87/src/youtube_mcp/tools/analytics_reports.py#L169-L210`; discovery: `https://www.googleapis.com/discovery/v1/apis/youtubeAnalytics/v2/rest` | remove |

Discovery snapshot:
```json
PARAMS ['currency', 'dimensions', 'endDate', 'filters', 'ids', 'includeHistoricalChannelData', 'maxResults', 'metrics', 'sort', 'startDate', 'startIndex']
```

Note: `analytics_reports_query.extra_params` is an intentional passthrough and was excluded from severity counts because it is user supplied, not a fixed Discovery kwarg.

### youtube.playlistImages.update
| tool function name | parameter | status | source URL or doc ref | recommended action |
| --- | --- | --- | --- | --- |
| `youtube_playlistImages_update` | `onBehalfOfContentOwnerChannel` | `REMOVED` | code: `https://github.com/sigvardt/youtube-mcp/blob/693d55d4341600b61e356d39b7ff660f70fe5e87/src/youtube_mcp/tools/playlist_images.py#L163-L187`; discovery: `https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest` | remove |

Discovery snapshot:
```json
PARAMS ['onBehalfOfContentOwner', 'part']
```

### youtube.playlistImages.delete
| tool function name | parameter | status | source URL or doc ref | recommended action |
| --- | --- | --- | --- | --- |
| `youtube_playlistImages_delete` | `onBehalfOfContentOwnerChannel` | `REMOVED` | code: `https://github.com/sigvardt/youtube-mcp/blob/693d55d4341600b61e356d39b7ff660f70fe5e87/src/youtube_mcp/tools/playlist_images.py#L198-L218`; discovery: `https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest` | remove |

Discovery snapshot:
```json
PARAMS ['id', 'onBehalfOfContentOwner']
```

### youtube.videoTrainability.get
| tool function name | parameter | status | source URL or doc ref | recommended action |
| --- | --- | --- | --- | --- |
| `youtube_videoTrainability_get` | `part` | `REMOVED` | code: `https://github.com/sigvardt/youtube-mcp/blob/693d55d4341600b61e356d39b7ff660f70fe5e87/src/youtube_mcp/tools/videos.py#L392-L410`; discovery: `https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest` | remove |

Discovery snapshot:
```json
PARAMS ['id']
```

### Confirmed clean: youtube.search.list
The prior `relatedToVideoId` regression is still absent from the current wrapper and current discovery params.

Code ref: `https://github.com/sigvardt/youtube-mcp/blob/693d55d4341600b61e356d39b7ff660f70fe5e87/src/youtube_mcp/tools/search.py#L83-L158`
Discovery snapshot:
```json
PARAMS ['channelId', 'channelType', 'eventType', 'forContentOwner', 'forDeveloper', 'forMine', 'location', 'locationRadius', 'maxResults', 'onBehalfOfContentOwner', 'order', 'pageToken', 'part', 'publishedAfter', 'publishedBefore', 'q', 'regionCode', 'relevanceLanguage', 'safeSearch', 'topicId', 'type', 'videoCaption', 'videoCategoryId', 'videoDefinition', 'videoDimension', 'videoDuration', 'videoEmbeddable', 'videoLicense', 'videoPaidProductPlacement', 'videoSyndicated', 'videoType']
```

