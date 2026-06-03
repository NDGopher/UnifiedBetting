---
name: match_games.py time filter
description: Time diff threshold and logging level for the Ace/Pinnacle game matching time filter
---

## Rule
Time diff threshold in `match_games.py` is **259200 seconds (72 hours)**, not 24h.

**Why:** 24h was too aggressive — it silently dropped Ace games whose datetimes
were parsed with a different timezone offset than Pinnacle's UTC times.
The frontend "24h toggle" handles display-level filtering; the matching layer
just needs to avoid obviously wrong cross-week false positives.

## Logging
`[TIME-SKIP]` log lines use `logger.info` (NOT `logger.debug`) so that dropped
games are visible without enabling debug-level logging.

## How to apply
Do not tighten this window again unless you can verify both sources are
timezone-normalized before comparison.
