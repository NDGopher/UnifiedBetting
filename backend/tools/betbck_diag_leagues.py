"""
BetBCK league diagnostic — YOU run this locally. Do not spam.

Modes:
  1) offline  — analyze a Get_SportsLeagues JSON you saved from Chrome (NO login)
  2) live     — one login + one Get_SportsLeagues (optional: one Lines probe)

Outputs under data/betbck_diag/:
  - sports_leagues_raw.json
  - sports_leagues_summary.txt
  - sport_filter_matches.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

OUT_DIR = BACKEND_DIR / "data" / "betbck_diag"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _analyze_leagues(leagues: list, sport_filters: list[str] | None = None) -> dict:
    from betbck_async_scraper import BetBCKAsyncScraper

    scraper = BetBCKAsyncScraper(sport_filters=sport_filters or [])
    by_type = Counter()
    by_period = Counter()
    game_rows = []
    futures_props = []
    for L in leagues:
        if not isinstance(L, dict):
            continue
        st = str(L.get("SportType") or "").strip()
        ss = str(L.get("SportSubType") or "").strip()
        pd = str(L.get("PeriodDescription") or "").strip()
        disp = str(L.get("SportSubTypeDisplay") or "").strip()
        by_type[st] += 1
        by_period[pd] += 1
        row = {
            "SportType": st,
            "SportSubType": ss,
            "SportSubTypeDisplay": disp,
            "PeriodDescription": pd,
            "PeriodNumber": L.get("PeriodNumber"),
            "Active": L.get("Active"),
            "SportSubType2": L.get("SportSubType2"),
        }
        if pd.lower() == "prop" or "FUTURE" in ss.upper() or "FUTURE" in disp.upper():
            futures_props.append(row)
        elif pd in ("Game", "1st Half", "1st 5 Innings", "1st Period", "1st Quarter"):
            game_rows.append(row)

    filters = sport_filters or list(scraper.sport_league_matchers.keys())
    matches = {}
    for key in filters:
        selected = scraper._select_leagues_for_filters(leagues, [key])
        matches[key] = [
            {
                "SportType": str(L.get("SportType") or "").strip(),
                "SportSubType": str(L.get("SportSubType") or "").strip(),
                "SportSubTypeDisplay": str(L.get("SportSubTypeDisplay") or "").strip(),
                "PeriodDescription": str(L.get("PeriodDescription") or "").strip(),
                "PeriodNumber": L.get("PeriodNumber"),
            }
            for L in selected
        ]

    return {
        "total_leagues": len(leagues),
        "by_sport_type": dict(by_type),
        "by_period": dict(by_period),
        "game_board_count": len(game_rows),
        "futures_prop_count": len(futures_props),
        "filter_matches": matches,
        "sample_soccer_game_boards": [
            r for r in game_rows if r["SportType"] == "SOCCER"
        ][:40],
        "sample_football_game_boards": [
            r for r in game_rows if r["SportType"] == "FOOTBALL"
        ][:40],
    }


def _write_summary(analysis: dict, path: Path) -> None:
    lines = []
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Total league rows: {analysis['total_leagues']}")
    lines.append(f"Game-board-ish rows: {analysis['game_board_count']}")
    lines.append(f"Futures/prop-ish rows: {analysis['futures_prop_count']}")
    lines.append("")
    lines.append("=== Counts by SportType ===")
    for k, v in sorted(analysis["by_sport_type"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("=== Counts by PeriodDescription ===")
    for k, v in sorted(analysis["by_period"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("=== Our sport_filter match counts (Game-period preferred in EV) ===")
    for key, rows in analysis["filter_matches"].items():
        game_only = [r for r in rows if r["PeriodDescription"] == "Game"]
        lines.append(f"  {key}: {len(rows)} rows ({len(game_only)} Game-only)")
        for r in rows[:8]:
            lines.append(
                f"    - {r['SportType']}/{r['SportSubType']} "
                f"[{r['PeriodDescription']}] {r['SportSubTypeDisplay']}"
            )
        if len(rows) > 8:
            lines.append(f"    ... +{len(rows) - 8} more")
    lines.append("")
    lines.append("=== Sample FOOTBALL game boards ===")
    for r in analysis["sample_football_game_boards"]:
        lines.append(
            f"  {r['SportType']}/{r['SportSubType']} [{r['PeriodDescription']}] "
            f"{r['SportSubTypeDisplay']}"
        )
    lines.append("")
    lines.append("=== Sample SOCCER game boards (first 40) ===")
    for r in analysis["sample_soccer_game_boards"]:
        lines.append(
            f"  {r['SportType']}/{r['SportSubType']} [{r['PeriodDescription']}] "
            f"{r['SportSubTypeDisplay']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_offline(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"ERROR: file not found: {src}")
        print("Save Get_SportsLeagues response JSON from Chrome DevTools, then re-run.")
        return 1
    raw = json.loads(src.read_text(encoding="utf-8"))
    leagues = raw.get("Leagues") if isinstance(raw, dict) else raw
    if not isinstance(leagues, list):
        print("ERROR: expected {Leagues:[...]} or a raw list")
        return 1

    analysis = _analyze_leagues(leagues)
    raw_out = OUT_DIR / "sports_leagues_raw.json"
    raw_out.write_text(json.dumps({"Leagues": leagues}, indent=2), encoding="utf-8")
    (OUT_DIR / "sport_filter_matches.json").write_text(
        json.dumps(analysis["filter_matches"], indent=2), encoding="utf-8"
    )
    summary = OUT_DIR / "sports_leagues_summary.txt"
    _write_summary(analysis, summary)
    print(f"Wrote {raw_out}")
    print(f"Wrote {summary}")
    print(f"Wrote {OUT_DIR / 'sport_filter_matches.json'}")
    print("Done (offline — no BetBCK login). Paste sports_leagues_summary.txt here if needed.")
    return 0


async def _live(args: argparse.Namespace) -> int:
    from betbck_async_scraper import BetBCKAsyncScraper
    import aiohttp

    scraper = BetBCKAsyncScraper(sport_filters=["ncaa_football"])
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(headers=scraper.headers, timeout=timeout) as session:
        print("[diag] Logging in once...")
        await scraper.login(session, fast_mode=True)
        try:
            await scraper.fetch_selection_page(session, fast_mode=True)
        except Exception as e:
            print(f"[diag] skin page optional fetch skipped: {e}")

        print("[diag] Calling Get_SportsLeagues once...")
        leagues = await scraper.fetch_sports_leagues(session, delay=True)
        print(f"[diag] Got {len(leagues)} league rows")

        raw_out = OUT_DIR / "sports_leagues_raw.json"
        raw_out.write_text(json.dumps({"Leagues": leagues}, indent=2), encoding="utf-8")

        analysis = _analyze_leagues(leagues)
        (OUT_DIR / "sport_filter_matches.json").write_text(
            json.dumps(analysis["filter_matches"], indent=2), encoding="utf-8"
        )
        summary = OUT_DIR / "sports_leagues_summary.txt"
        _write_summary(analysis, summary)
        print(f"[diag] Wrote {summary}")

        # Optional single Lines probe (NCAA Football / COLLEGE)
        if args.probe_ncaa:
            print("[diag] OPTIONAL probe: one Get_LeagueLines2 for FOOTBALL/COLLEGE ...")
            await asyncio.sleep(2.5)
            text = await scraper.fetch_lines_json(
                session,
                sport_type="FOOTBALL",
                sport_subtype="COLLEGE",
                period="Game",
                period_number=0,
                delay=False,
            )
            probe_path = OUT_DIR / "probe_ncaa_college_lines.json"
            probe_path.write_text(text, encoding="utf-8")
            try:
                payload = json.loads(text)
                n = len(payload.get("Lines") or [])
            except Exception:
                n = -1
            print(f"[diag] COLLEGE lines count={n} saved to {probe_path}")

        # Optional: does SportType-only bulk work? ONE call.
        if args.probe_bulk_soccer:
            print("[diag] OPTIONAL probe: one Get_LeagueLines2 SportType=SOCCER subtype='' ...")
            await asyncio.sleep(3.0)
            text = await scraper.fetch_lines_json(
                session,
                sport_type="SOCCER",
                sport_subtype="",
                period="Game",
                period_number=0,
                delay=False,
            )
            probe_path = OUT_DIR / "probe_bulk_soccer_lines.json"
            probe_path.write_text(text, encoding="utf-8")
            try:
                payload = json.loads(text)
                n = len(payload.get("Lines") or [])
            except Exception:
                n = -1
            print(f"[diag] bulk SOCCER lines count={n} saved to {probe_path}")

    print("Done. Share data/betbck_diag/sports_leagues_summary.txt (and probe files if used).")
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    return asyncio.run(_live(args))


def main() -> int:
    p = argparse.ArgumentParser(description="BetBCK leagues diagnostic (local only)")
    sub = p.add_subparsers(dest="cmd", required=True)

    off = sub.add_parser("offline", help="Analyze a saved Get_SportsLeagues JSON (no login)")
    off.add_argument(
        "--input",
        "-i",
        default=str(OUT_DIR / "from_chrome_Get_SportsLeagues.json"),
        help="Path to JSON saved from Chrome",
    )
    off.set_defaults(func=cmd_offline)

    live = sub.add_parser(
        "live",
        help="ONE login + ONE Get_SportsLeagues (optional single Lines probe)",
    )
    live.add_argument(
        "--probe-ncaa",
        action="store_true",
        help="Also do ONE Get_LeagueLines2 for FOOTBALL/COLLEGE",
    )
    live.add_argument(
        "--probe-bulk-soccer",
        action="store_true",
        help="Also do ONE Get_LeagueLines2 with SportType=SOCCER and empty subtype",
    )
    live.set_defaults(func=cmd_live)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
