---
name: Pinnacle spread key mapping
description: How to correctly look up NVP for spread bets in calculate_ev_table.py using Pinnacle's hdp key structure.
---

## Rule
Pinnacle's `spreads` dict is keyed by `hdp` (the home team's handicap as a string):
- Positive hdp → home team **receives** pts (home is underdog at +hdp, away is favorite at -hdp)
- Negative hdp → home team **gives** pts (home is favorite at -|hdp|, away is underdog at +|hdp|)

For ANY BetBCK spread at `bet_line` for team T:
- T == Pinnacle HOME → key = `str(bet_line)` (direct), field = `nvp_home`
- T == Pinnacle AWAY → key = `str(-bet_line)` (negated), field = `nvp_away`

This rule is **independent of whether T is BetBCK's top or bottom team**. BetBCK and Pinnacle can have different home/away assignments (e.g., Winnipeg is BetBCK site-home/top but Pinnacle away for the same CFL game).

**Why:** The old code used direct key first for site_top_team_spreads and neg-key first for site_bottom_team_spreads, assuming top=home and bottom=away. When BetBCK swaps home/away relative to Pinnacle, this picks the wrong spread market (the alt line at opposite direction), producing wildly wrong NVP and false positive EV.

**How to apply:** In calculate_ev_table.py the spread section now uses a `_find_spread_market_and_nvp` helper that checks `bck_team_norm` against `normalized_pinnacle_home` and `normalized_pinnacle_away` to select the key and nvp field, then calls it uniformly for both site_top_team_spreads and site_bottom_team_spreads.

## Verification (Winnipeg CFL game, event 1631603492)
- Pinnacle home = Calgary, Pinnacle away = Winnipeg (BetBCK has Winnipeg as top/site-home)
- BetBCK Winnipeg (away in Pinnacle) at -1.5 → key = str(-(-1.5)) = "1.5"
- Swordfish key "1.5": home_raw=1.909 (-110 = Calgary +1.5), away_raw=1.961 (-104 = Winnipeg -1.5)
- nvp_away ≈ +103 → EV = -5.9% (correct negative EV, was previously showing false +8.9%)

## Reference
- pod_utils.py lines 907-970 has the proven reference implementation (iterates all spreads, uses hdp field directly).
- calculate_ev_table.py spread section (lines ~444+) uses key-based lookup.
