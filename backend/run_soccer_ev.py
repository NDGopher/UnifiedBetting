import asyncio
import sys
import os
import logging
logging.disable(logging.CRITICAL)   # silence all logger output
sys.path.insert(0, os.path.dirname(__file__))

from buckeye_scraper import BuckeyeScraper
from betbck_async_scraper import _get_all_betbck_games_async
from match_games import match_pinnacle_to_betbck
from calculate_ev_table import calculate_ev_table_async

async def main():
    print("=" * 72)
    print("  SOCCER PIPELINE — Full game + 1H")
    print("=" * 72)

    # ── Step 1: Pinnacle ─────────────────────────────────────────────────
    print("\n[1/4] Fetching Pinnacle events...", flush=True)
    scraper = BuckeyeScraper({})
    pinnacle_events = scraper.get_todays_event_ids()
    print(f"      Pinnacle events : {len(pinnacle_events)}")

    # ── Step 2: BetBCK soccer (full + 1H) ────────────────────────────────
    print("\n[2/4] Scraping BetBCK soccer (full game + 1H)...", flush=True)
    raw = await _get_all_betbck_games_async(sport_filters=["soccer"])
    # _get_all_betbck_games_async returns a plain list; wrap it for match_pinnacle_to_betbck
    games = raw if isinstance(raw, list) else raw.get("games", [])
    betbck_data = {"games": games}
    fg_games = [g for g in games if not g.get("market_suffix")]
    h1_games = [g for g in games if g.get("market_suffix") == "1H"]
    print(f"      Total scraped   : {len(games)}")
    print(f"      Full-game lines : {len(fg_games)}")
    print(f"      1H lines        : {len(h1_games)}")

    # ── Step 3: Match ─────────────────────────────────────────────────────
    print("\n[3/4] Matching Pinnacle ↔ BetBCK...", flush=True)
    matched = match_pinnacle_to_betbck(pinnacle_events, betbck_data)
    fg_m = [m for m in matched if not m.get("market_suffix")]
    h1_m = [m for m in matched if m.get("market_suffix") == "1H"]
    print(f"      Matched total   : {len(matched)}")
    print(f"      Full-game       : {len(fg_m)}")
    print(f"      1H              : {len(h1_m)}")

    # ── Step 4: EV ───────────────────────────────────────────────────────
    print("\n[4/4] Calculating EV (parallel Swordfish calls)...", flush=True)
    ev_table = await calculate_ev_table_async(matched)
    def ev_float(r):
        v = r.get("ev") or "0"
        try: return float(str(v).rstrip("%"))
        except: return 0.0

    fg_ev = [r for r in ev_table if r.get("period","FG") == "FG"]
    h1_ev = [r for r in ev_table if r.get("period","FG") == "1H"]
    pos   = [r for r in ev_table if ev_float(r) > 0]
    print(f"      EV rows total   : {len(ev_table)}")
    print(f"      Full-game bets  : {len(fg_ev)}")
    print(f"      1H bets         : {len(h1_ev)}")
    print(f"      Positive EV     : {len(pos)}")

    # ── Matched games summary ─────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  MATCHED GAMES")
    print("=" * 72)
    for m in sorted(matched, key=lambda x: (x.get("market_suffix") or "", x.get("betbck_home_team",""))):
        tag   = "[1H]" if m.get("market_suffix") == "1H" else "[FG]"
        score = m.get("match_score", 0)
        bh    = m.get("betbck_home_team") or m.get("betbck_site_home_team","")
        ba    = m.get("betbck_away_team") or m.get("betbck_site_away_team","")
        ph    = m.get("pinnacle_home_team","")
        pa    = m.get("pinnacle_away_team","")
        print(f"  {tag} {score:5.1f}  BetBCK: {bh} vs {ba}")
        print(f"         {'':5}  Pinnacle: {ph} vs {pa}")

    # ── Full EV table ─────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  EV TABLE")
    print("=" * 72)
    hdr = f"  {'Game':<38} {'Bet':<28} {'BetBCK':>8} {'NVP':>8} {'EV%':>7}"
    print(hdr)
    print("  " + "-" * 93)
    for row in sorted(ev_table, key=lambda x: -ev_float(x)):
        game = (row.get("matchup") or "")
        if len(game) > 37:
            game = game[:34] + "..."
        bet  = (row.get("bet","") or "")[:27]
        bck  = row.get("betbck_odds","")
        nvp  = row.get("pinnacle_nvp","")
        ev   = ev_float(row)
        ev_s = f"{ev:+.2f}%" if (row.get("ev") not in (None, "")) else "  n/a"
        flag = "  <-- +EV" if ev > 0 else ""
        print(f"  {game:<38} {bet:<28} {str(bck):>8} {str(nvp):>8} {ev_s:>7}{flag}")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print(f"  DONE  matched={len(matched)}  ev_rows={len(ev_table)}  +EV={len(pos)}")
    if pos:
        print("\n  POSITIVE EV BETS:")
        for r in sorted(pos, key=lambda x: -ev_float(x)):
            print(f"    {ev_float(r):+.2f}%  {r.get('matchup','')}  —  {r.get('bet','')}")
    print("=" * 72)

asyncio.run(main())
