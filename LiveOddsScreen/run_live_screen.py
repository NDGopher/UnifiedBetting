import argparse
import json
import time
from typing import Any, Dict, List
import time as _time

from pto_live_dom_scraper import scrape_pto_live, PTOSelectors
from schema import EventOdds
from team_matching import match_events
from dashboard import build_best_table, serve_dashboard
from profile_resolver import resolve_chrome_profile
from plive_client import fetch_plive_snapshot
from pto_ws_client import PTOWebSocketClient
from plive_ws_client import PLiveWebSocketClient
from pto_token import extract_pto_bearer_from_har
from plive_gsid import extract_gsid_from_har
from pto_ws_mapping import canonicalize_site
from plive_dom_scraper import scrape_plive_odds


def load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Config is optional; we will fallback to backend/config.json via resolver
        return {}
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(description="Standalone live odds screen aggregator")
    parser.add_argument("--config", default="LiveOddsScreen/config.json", help="Optional local config (profile override)")
    parser.add_argument("--selectors", default="LiveOddsScreen/selectors.json")
    parser.add_argument("--refresh", type=int, default=15, help="Refresh interval seconds")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    cfg = load_json(args.config)
    sels = load_json(args.selectors)

    bck_cfg = sels.get("betbck", {})
    pto_cfgs = sels["pto_multi"] if "pto_multi" in sels else [sels["pto"]]

    # Prefer explicit local config, otherwise resolve from backend PTO config
    user_data_dir = cfg.get("chrome_user_data_dir")
    profile_dir = cfg.get("chrome_profile_dir")
    if not user_data_dir:
        cud, cpd = resolve_chrome_profile()
        user_data_dir = user_data_dir or cud
        profile_dir = profile_dir or cpd

    # Start dashboard server
    serve_dashboard([], port=args.port)

    # Optional WebSocket clients (will backfill output.json as updates arrive)
    ws_rows: List[Dict[str, Any]] = []

    def pto_on_event(payload: Dict[str, Any]):
        # Map betCache updates into rows if present
        try:
            data = payload.get("data") or {}
            bet_cache = data.get("betCache")
            if not bet_cache:
                return
            # bet_cache is an array of BetMarketType with listings and conditions
            for market in (bet_cache if isinstance(bet_cache, list) else [bet_cache]):
                listings = market.get("listings") or []
                conditions = market.get("conditions") or []
                # Identify home/away/team via condition fields when possible
                # For odds screen, PTO groups by game/league; we fallback to generic labels
                books = {}
                for lst in listings:
                    site_id = canonicalize_site(str(lst.get("siteId", "")))
                    american = lst.get("americanOdds")
                    if not site_id:
                        continue
                    # Assign same price to both sides when side unknown (we’ll refine once we pull side mapping)
                    books[site_id] = {"home": str(american) if american is not None else None,
                                      "away": None}
                if books:
                    ws_rows.append({
                        "sport": "unknown",
                        "market": "moneyline",
                        "home": "PTO Live",
                        "away": "Market",
                        "books": books,
                    })
        except Exception:
            return

    # PTO WS: subscribe to betCache stream across leagues via filters stored in PTO UI
    token = extract_pto_bearer_from_har() or ""
    pto_ws = PTOWebSocketClient(on_event=pto_on_event, token_provider=lambda: token)
    pto_ws_query = (
        "subscription ($request: InputBetCacheSubscriptionRequestType) {\n"
        "  betCache(request: $request) {\n"
        "    hashCode\n"
        "    listings { siteId americanOdds }\n"
        "    conditions { marketType overUnder betValue teamId isGameBet }\n"
        "  }\n"
        "}"
    )
    try:
        # Wildcard request; PTO determines leagues from user settings server-side. If empty, server returns defaults.
        pto_ws.start(query=pto_ws_query, variables={"request": {}})
    except Exception:
        pass

    plive_ws_messages: List[str] = []
    def plive_on_message(msg: str):
        plive_ws_messages.append(msg)
    gsid = extract_gsid_from_har() or None
    auth = {"gsid": gsid} if gsid else None
    plive_ws = PLiveWebSocketClient(on_message=plive_on_message, auth=auth)
    try:
        plive_ws.start()
    except Exception:
        pass

    last_rows: List[EventOdds] = []
    last_rows_ts: float = 0.0

    while True:
        all_pto_events: List[Dict[str, Any]] = []
        # Scrape all PTO facets configured (ML/Spread/Total, multiple leagues)
        for pto_cfg in pto_cfgs:
            try:
                print(f"[PTO] Scraping {pto_cfg.get('url')} ...")
                pto_events = scrape_pto_live(
                    pto_url=pto_cfg["url"],
                    selectors=PTOSelectors(
                        event_row_selector=pto_cfg["event_row_selector"],
                        home_team_selector=pto_cfg.get("home_team_selector", ""),
                        away_team_selector=pto_cfg.get("away_team_selector", ""),
                        market_container_selector=pto_cfg.get("market_container_selector"),
                        price_selector=pto_cfg.get("price_selector"),
                        team_title_selector=pto_cfg.get("team_title_selector"),
                        book_cell_selector=pto_cfg.get("book_cell_selector"),
                        book_icon_selector=pto_cfg.get("book_icon_selector"),
                        book_odds_value_selector=pto_cfg.get("book_odds_value_selector"),
                    ),
                    user_data_dir=user_data_dir,
                    profile_dir=profile_dir,
                    allowed_books=None,
                    live_only=True,
                )
                print(f"[PTO] Found {len(pto_events)} events")
                market_name = pto_cfg.get("market") or "moneyline"
                for e in pto_events:
                    e["sport"] = pto_cfg.get("sport", "unknown")
                    # Keep detected market if scraper provided it; else fallback
                    if not e.get("market"):
                        e["market"] = market_name
                all_pto_events.extend(pto_events)
            except Exception as ex:
                print(f"[PTO] Error: {ex}")

        # Skip BetBCK iframe/login path for speed and stability; rely on PLive
        bck_events: List[Dict[str, Any]] = []

        # Prefer PLive direct odds (no login). Always try it first for speed.
        try:
            print("[PLive] Fast scrape ...")
            plive_events = scrape_plive_odds(headless=True)
            print(f"[PLive] Found {len(plive_events)} events")
        except Exception as ex:
            print(f"[PLive] Error: {ex}")
            plive_events = []

        # If both BetBCK and PLive empty, log once
        if not bck_events and not plive_events:
            try:
                print("[PLive] No events found from PLive; keeping PTO rows only this cycle")
            except Exception as ex:
                print(f"[PLive] Error: {ex}")
        for e in bck_events:
            e["sport"] = bck_cfg.get("sport", e.get("sport", "unknown"))
            e["market"] = e.get("market", bck_cfg.get("market", "moneyline"))

        # Optional: capture PLive snapshot for debugging/matching improvements
        # Disable extra PLive snapshot to avoid opening more browsers each cycle
        _plive = {}

        # Merge PLive (BetBCK) + BetBCK iframe results
        merged_bck = (bck_events or []) + (plive_events or [])
        matches = match_events(merged_bck, all_pto_events)
        
        # Combine into EventOdds with per-book prices
        combined: List[EventOdds] = []
        if matches:
            for m in matches:
                b = m["left"]
                p = m["right"]
                eo = EventOdds(
                    sport=b.get("sport", p.get("sport", "unknown")),
                    market=b.get("market", p.get("market", "moneyline")),
                    home=b.get("home", ""),
                    away=b.get("away", ""),
                    books={},
                )
                # Carry BetBCK prices from PLive/BetBCK event if present
                b_books = b.get("books", {})
                betbck_prices = b_books.get("betbck")
                if not betbck_prices:
                    # Try to infer from markets list
                    betbck_home = None
                    betbck_away = None
                    for market_data in b.get("markets", []):
                        label = (market_data.get("label") or "").lower()
                        if eo.market in label or not label:
                            betbck_home = market_data.get("home") or market_data.get("price")
                            betbck_away = market_data.get("away")
                            break
                    betbck_prices = {"home": betbck_home, "away": betbck_away}
                eo.books["betbck"] = {
                    "home": betbck_prices.get("home"),
                    "away": betbck_prices.get("away"),
                }
                # Merge PTO books detected in row
                p_books = p.get("books", {})
                for book_name, sides in p_books.items():
                    key = book_name.lower().strip().replace(" ", "_")
                    eo.books[key] = {"home": sides.get("home"), "away": sides.get("away")}
                combined.append(eo)
        else:
            # No PTO matches; emit PLive/BetBCK-only rows so dashboard still shows BetBCK games
            for b in merged_bck:
                eo = EventOdds(
                    sport=b.get("sport", "unknown"),
                    market=b.get("market", "moneyline"),
                    home=b.get("home", ""),
                    away=b.get("away", ""),
                    books=b.get("books", {}),
                )
                combined.append(eo)

        # Merge any WS placeholder rows for visibility
        if ws_rows:
            combined.extend([
                EventOdds(sport=r.get('sport','unknown'), market=r.get('market','moneyline'), home=r.get('home',''), away=r.get('away',''), books=r.get('books',{}))
                for r in ws_rows
            ])
            ws_rows.clear()

        # Live-only filter: keep rows with any BetBCK price (home or away)
        live_rows = [e for e in combined if (e.books.get("betbck", {}).get("home") or e.books.get("betbck", {}).get("away"))]

        # If this cycle yields zero rows, keep last non-empty snapshot for 60s to avoid dashboard flicker
        if not live_rows and last_rows:
            if (_time.time() - last_rows_ts) < 60:
                live_rows = last_rows
        else:
            if live_rows:
                last_rows = live_rows
                last_rows_ts = _time.time()
        # Write a small debug snapshot for troubleshooting
        try:
            from pathlib import Path
            Path("LiveOddsScreen/debug_last.json").write_text(
                json.dumps({
                    "counts": {
                        "pto": len(all_pto_events),
                        "plive": len(plive_events),
                        "betbck_iframe": len(bck_events),
                        "matches": len(matches),
                        "live_rows": len(live_rows),
                    },
                    "sample_plive": (plive_events[:3] if plive_events else []),
                }, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        print(f"[Combine] PTO={len(all_pto_events)} PLive={len(plive_events)} BetBCK_iframe={len(bck_events)} matches={len(matches)} live_rows={len(live_rows)}")
        rows = build_best_table(live_rows)
        # Write JSON that dashboard.html loads
        from pathlib import Path
        Path("LiveOddsScreen/output.json").write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")
        print(f"[Write] output.json with {len(rows)} rows")

        time.sleep(args.refresh)


if __name__ == "__main__":
    main()

