# Phase 8 Manual Cleanup Walkthrough

Date: 2026-05-20
Scope: operator-only cleanup for artifacts created during Phase 4 mutating live tests
Reason: video deletion is intentionally absent from the server, so deletion must be done in YouTube Studio

## Inputs

- Uploaded video IDs file: `.sisyphus/evidence/task-47-uploaded-video-ids.txt`
- Phase 4 evidence: `.sisyphus/evidence/phase-4-mutating.md`
- Live test file: `tests/live/test_acid_mutating_jsigvardt.py`

## Phase 4 Artifact Inventory

### Videos

| Kind | ID | Studio URL | Manual cleanup |
| --- | --- | --- | --- |
| Uploaded private video kept for cleanup | `A-CNdRDfljw` | `https://studio.youtube.com/video/A-CNdRDfljw/edit` | Delete forever |

The uploaded video ID file exists and contains one entry:

```text
2026-05-20T10:27:43.536179+00:00	youtube-mcp-acid-20260520T102726Z	A-CNdRDfljw
```

### Other resource categories from Phase 4

| Category | Phase 4 result | Manual cleanup needed |
| --- | --- | --- |
| Playlists | Created in test body, deleted in `finally`, no persisted ID logged | No |
| Playlist items | Created in test body, deleted in `finally`, no persisted ID logged | No |
| Comments | Created in test body, deleted in `finally`, no persisted ID logged | No |
| Channel sections | Test attempted create, cleanup path deletes section and helper playlist, no persisted ID logged | No |
| Live broadcasts | Test cleanup deletes broadcast in `finally`, no persisted ID logged | No |
| Live streams | Test cleanup deletes stream in `finally`, no persisted ID logged | No |
| Analytics groups | Test cleanup deletes group item and group in `finally`, no persisted ID logged | No |
| Reporting jobs | Test cleanup deletes job in `finally`, no persisted ID logged | No |
| Channel keywords | Updated then reverted in `finally` | No |
| Thumbnail | Set then reverted in `finally`; phase 4 failed before a successful set | No |
| Watermark | Set then unset in `finally` | No |

Phase 4 evidence did not log any other persisted artifact IDs besides the uploaded private video.

## Manual Cleanup Checklist

- [ ] Sign in to Google as `joakim.sigvardt.eu@gtempaccount.com`.
- [ ] Open `https://studio.youtube.com`.
- [ ] Use the brand-account picker and switch to `Joakim Sigvardt` / `@jsigvardt`.
- [ ] Open the video edit page for the retained upload: `https://studio.youtube.com/video/A-CNdRDfljw/edit`.
- [ ] In YouTube Studio, locate the row for the test upload `youtube-mcp-acid-20260520T102726Z`.
- [ ] Click the row, then click the `...` menu.
- [ ] Choose `Delete forever`.
- [ ] Confirm the permanent deletion prompt.
- [ ] Verify the video no longer appears in Studio content.

## Summary

- Artifacts to clean up: 1
- Videos: 1
- Comments / playlist items / channel sections / live broadcasts / playlists with manual cleanup: 0
- Channel-level changes left unreverted by the tests: 0 confirmed

## Phase 9 Additional Upload

Date: 2026-05-20
Scope: Phase 9 operator override mutating sweep

| Kind | ID | Studio URL | Manual cleanup |
| --- | --- | --- | --- |
| Uploaded private video kept for cleanup | `U12LBSanfLU` | `https://studio.youtube.com/video/U12LBSanfLU/edit` | Delete forever |

Uploaded video evidence entry:

```text
2026-05-20T12:02:29.516937+00:00	youtube-mcp-acid-20260520T120227Z	U12LBSanfLU
```
