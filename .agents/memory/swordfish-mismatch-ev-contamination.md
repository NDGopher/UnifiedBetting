---
name: Swordfish team mismatch EV contamination
description: Cross-game EV contamination when background refresher receives wrong game from Swordfish but still stores its NVPs
---

## The Rule
When the background refresher fetches Swordfish and detects a team mismatch, it must **revert** `working_event_data["pinnacle_data_processed"]` back to the old data — not just skip `analyze_markets_for_ev`.

## Why
`processed_odds` (wrong game's Pinnacle NVPs) is written into `working_event_data["pinnacle_data_processed"]` at line 321, *before* the mismatch guard runs. If the guard only skips `analyze_markets_for_ev` but leaves the write in place, `build_event_object` recalculates EV by mixing the wrong game's NVPs with this game's BetBCK odds — producing completely fake high EVs (e.g. +20.98%).

## How to Apply
In `pod_event_manager.py` background refresher, inside the `if max(_best_fwd, _best_rev) < 0.4:` branch, always include:
```python
working_event_data["pinnacle_data_processed"] = event_data.get("pinnacle_data_processed", {})
```
This restores the original (stub or last-good) Pinnacle data so the wrong game's NVPs never reach broadcast or storage.

## Context
Triggered by: extension capturing wrong Pinnacle event ID (e.g., Shamrock Rovers alert gets Larne vs SP Tre Fiori Swordfish data). The `*** SUSPECT ***` log line in the Alert Log is the visible symptom.
