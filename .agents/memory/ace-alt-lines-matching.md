---
name: Ace ALT lines matching — multiple entries per game
description: Why Ace pipeline was matching 52/81 instead of 74/81 games, and the fix in match_games.py
---

## The Rule
Never add `(event_id, 'ALT')` to `processed_pinnacle_keys` in `match_pinnacle_to_betbck`.

## Why
Ace's league 419 (MLB - ALTERNATE RUNLINES & TOTALS) sends **multiple entries per game** (alternate runlines, alternate totals, etc.) each with a different `betbck_game_id`.  After entry #1 matches and adds `(event_id, 'ALT')` to `processed_pinnacle_keys`, entry #2 checks `(event_id, 'ALT') in processed_pinnacle_keys` → True → skips the only viable Pinnacle event → `no_candidates`.

## How to Apply
In `match_games.py`, the `processed_pinnacle_keys.add(...)` call after a successful match must be gated:
```python
if betbck_game.get('market_suffix') != 'ALT':
    processed_pinnacle_keys.add((best_match["event_id"], betbck_game.get('market_suffix')))
```
Main and 1H games still get tracked (preventing duplicate Pinnacle event claims), but ALT games are unrestricted, letting all alternate-line entries share the same Pinnacle event.

## Result
Fixed 52 → 74 matched games (2026-06-03). Remaining 7 unmatched are genuinely absent from Pinnacle (SEA vs NY, CD GODOY CRUZ, CR BRASIL AL).
