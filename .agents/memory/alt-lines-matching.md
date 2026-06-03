---
name: ALT lines matching in match_games.py
description: How ALT (alternate) lines are handled in the Pinnacle game de-duplication set
---

## Rule
Only **non-ALT** Pinnacle games should be added to `processed_pinnacle_keys`.
ALT lines for the same game must all be processed independently.

**Why:** When the main game adds to the set, subsequent ALT lines for the same
game hit the "already processed" guard and get skipped entirely, producing
zero ALT-line matches. The fix: check `if not is_alt: processed_pinnacle_keys.add(key)`.

## How to apply
If matched game count drops unexpectedly when ALT lines are present, check
whether the de-duplication set is being populated from ALT entries.
