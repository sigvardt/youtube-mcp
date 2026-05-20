# Phase 9 Mutating Cutoff

Date: 2026-05-20
Account: `jsigvardt` / `@jsigvardt`

## Cutoff

- The mutating sweep should have stopped before `test_videos_insert_update_keeps_uploaded_video_for_manual_cleanup` because quota was `8419/10000` after `test_thumbnails_set_then_revert`, leaving 1581 units.
- The estimated upload/update cost was 1700 units, which was enough to cross the 500-unit safety floor.
- The one-off shell monitor parsed the wrong quota field from `youtube-mcp status` because the token column contains spaces, so it reported `remaining_before=10000` throughout the sweep.
- The high-cost video upload test ran and passed, moving quota to `10069/10000`.
- No further live reruns were attempted after this point. The fixed watermark fixture needs live revalidation after quota resets.

## Skipped Due To Quota Exhaustion

- No original mutating test remained unattempted when quota ran out.
- Deferred revalidation: `test_watermarks_set_unset` after replacing the invalid watermark fixture.
