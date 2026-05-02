"""
auto_bettor.py — Foundation auto-betting script for UnifiedBetting3.

Connects to the backend SSE stream, listens for +EV POD alerts, and
(when enabled) places bets on BetBCK using requests + optional Playwright.

Usage:
  # Dry-run against local dev backend (safe — nothing placed):
  python auto_bettor.py --backend http://localhost:8000 --min-ev 3.0

  # Dry-run against Replit (port-5000 proxy):
  python auto_bettor.py --backend https://<replit-domain>:5000 --min-ev 3.0

  # Live betting (after selector confirmation — see CONFIRMED_SELECTORS below):
  python auto_bettor.py --backend http://localhost:8000 --min-ev 3.0 --no-dry-run

Requirements:
  pip install requests sseclient-py playwright
  playwright install chromium
"""

import argparse
import csv
import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, Any, Optional

import requests
try:
    import sseclient
    HAS_SSE = True
except ImportError:
    HAS_SSE = False
    print("[AutoBettor] sseclient-py not installed. Run: pip install sseclient-py")

try:
    from playwright.sync_api import sync_playwright, Page, BrowserContext
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("[AutoBettor] playwright not installed. Run: pip install playwright && playwright install chromium")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("auto_bettor.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("auto_bettor")


# ────────────────────────────────────────────────────────────────────────────
# BetBCK selectors — confirmed from scraper source code analysis
# Items marked TODO need one live observation to finalise.
# ────────────────────────────────────────────────────────────────────────────
CONFIRMED_SELECTORS = {
    # --- Login page ---
    "login_customer_id":    "input[name='customerID']",       # confirmed
    "login_password":       "input[name='password']",          # confirmed
    "login_submit":         "input[type='submit']",            # confirmed

    # --- Post-login search page (PlayerGameSelection.php) ---
    "search_form":          "form#GameSelectionForm",           # confirmed
    "inet_wager_number":    "input[name='inetWagerNumber']",   # confirmed (hidden)
    "inet_sport_select":    "input[name='inetSportSelection']",# confirmed (hidden)
    "search_field":         "input[name='keyword_search']",    # confirmed
    "search_submit":        "input[type='submit'][value='Search']",  # confirmed

    # --- Search results structure ---
    # Primary game wrapper tables (one per game)
    "game_wrapper_soccer":  "table.table_container_betting Soccer",
    "game_wrapper_basket":  "table.table_container_betting Basketball",
    "game_wrapper_baseball":"table.table_container_betting Baseball",
    "game_wrapper_hockey":  "table.table_container_betting Hockey",
    "game_wrapper_football":"table.table_container_betting American Football",
    "game_wrapper_tennis":  "table.table_container_betting Tennis",
    # Fallback wrappers
    "game_wrapper_fallback1":"table.teams_betting_options_2",
    "game_wrapper_fallback2":"table.teams_betting_options",
    # Team name elements
    "team_name_td":         "td[class^='tbl_betAmount_team1_main_name']",
    "home_team_div":        "div.team1_name_up",
    "away_team_div":        "div.team2_name_down",
    "team_name_span":       "span[data-language]",             # confirmed
    # Odds cells
    "odds_table":           "table.new_tb_cont",               # confirmed
    "odds_td":              "td[class*='tbl_betAmount_td']",   # confirmed

    # --- Bet slip / wager entry ---
    # TODO: confirm by observing the DOM after clicking an odds cell.
    # Current best guesses from BetBCK's traditional HTML form layout:
    "wager_amount_input":   "input[name='amount']",            # TODO — confirm
    "wager_submit_button":  "input[type='submit'][value='Place Bet']",  # TODO — confirm
    # Alternative submit patterns sometimes seen:
    # "input[type='button'][value='Place Wager']"
    # "button:has-text('Place Bet')"
}

# Session-level wager flow — extracted from scraper (betbck_scraper.py lines 879-888)
# After search POST, the response HTML contains updated inetWagerNumber.
# That value must be echoed back in the wager POST payload.
# POST payload for bet placement (guessed from pattern, TODO confirm):
# {
#   "action":               "PlaceBet",    # or "Wager" — TODO confirm
#   "inetWagerNumber":      <value from response>,
#   "inetSportSelection":   <value from response>,
#   "amount":               <stake>,
# }
#
# For Playwright automation the flow is:
# 1. login → navigate to PlayerGameSelection.php
# 2. search for team keyword
# 3. locate the matching game wrapper table
# 4. click the odds cell for the target market/selection
# 5. observe what DOM element becomes active (bet slip form?)
# 6. fill amount field + click submit
# ────────────────────────────────────────────────────────────────────────────


BET_LOG_FILE = "placed_bets.csv"
BET_LOG_FIELDS = [
    "placed_at", "event_id", "teams", "market", "selection", "line",
    "betbck_odds", "pinnacle_nvp", "ev_pct", "stake", "dry_run", "status"
]


def init_bet_log():
    if not os.path.exists(BET_LOG_FILE):
        with open(BET_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=BET_LOG_FIELDS)
            writer.writeheader()


def log_bet(record: Dict):
    with open(BET_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BET_LOG_FIELDS)
        writer.writerow({k: record.get(k, "") for k in BET_LOG_FIELDS})


def human_delay(min_ms: int = 300, max_ms: int = 1200):
    time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


def human_type(page: "Page", selector: str, text: str):
    el = page.locator(selector)
    el.click()
    human_delay(80, 250)
    for char in text:
        el.press(char)
        time.sleep(random.uniform(0.04, 0.13))


def login_to_betbck(page: "Page", customer_id: str, password: str) -> bool:
    """Log in to BetBCK. Returns True on success."""
    from playwright.sync_api import TimeoutError as PWTimeout
    try:
        log.info("[BetBCK] Navigating to login page...")
        page.goto("https://betbck.com/Qubic/Login.php", wait_until="domcontentloaded")
        human_delay(600, 1200)

        human_type(page, CONFIRMED_SELECTORS["login_customer_id"], customer_id)
        human_delay(200, 500)
        human_type(page, CONFIRMED_SELECTORS["login_password"], password)
        human_delay(300, 700)

        page.locator(CONFIRMED_SELECTORS["login_submit"]).click()

        # Wait for redirect to post-login page
        page.wait_for_url(
            lambda url: "StraightLoginSportSelection" in url
                        or "PlayerGameSelection" in url
                        or "MainMenu" in url,
            timeout=10_000,
        )
        log.info("[BetBCK] Login successful.")
        return True
    except PWTimeout:
        log.error("[BetBCK] Login timed out — check credentials or URL.")
        return False
    except Exception as exc:
        log.error(f"[BetBCK] Login failed: {exc}")
        return False


def search_and_place_bet(
    page: "Page",
    teams: str,
    market: str,
    selection: str,
    line: str,
    betbck_odds: str,
    stake: float,
    dry_run: bool,
) -> str:
    """
    Search for a game on BetBCK and place a bet.
    Returns status string: 'placed' | 'dry_run' | 'selector_todo' | 'error'

    Selector flow confirmed from betbck_scraper.py:
      search form  → keyword_search POST → results HTML with game wrapper tables
      → team1_name_up / team2_name_down to find the right game
      → tbl_betAmount_td odds cells to click target market
      → wager entry form (amount field + submit) — TODO confirm exact selectors

    To finalise:
      1. Log in manually to betbck.com
      2. Search for any game
      3. Right-click the odds cell for the market you want → Inspect
      4. Note the input/button selector and the bet-slip amount field name
      5. Update CONFIRMED_SELECTORS["wager_amount_input"] and ["wager_submit_button"]
    """
    if dry_run:
        log.info(
            f"[DRY RUN] Would bet ${stake:.2f} on {teams} | "
            f"{market} {selection} {line} @ {betbck_odds}"
        )
        return "dry_run"

    if not HAS_PLAYWRIGHT:
        log.error("[BetBCK] Playwright not available.")
        return "error"

    try:
        log.info(f"[BetBCK] Navigating to search page...")
        page.goto("https://betbck.com/Qubic/PlayerGameSelection.php", wait_until="domcontentloaded")
        human_delay(700, 1400)

        # Extract search keyword from home team (last meaningful word)
        home_team = teams.split(" vs ")[0].strip()
        words = [w for w in home_team.split() if len(w) > 3 and w.lower() not in
                 ("city", "united", "club", "football", "fc", "sc", "ac", "the")]
        search_term = words[-1] if words else home_team.split()[-1]

        log.info(f"[BetBCK] Searching for '{search_term}'...")
        human_type(page, CONFIRMED_SELECTORS["search_field"], search_term)
        human_delay(300, 600)
        page.locator(CONFIRMED_SELECTORS["search_submit"]).click()
        human_delay(1200, 2500)

        # --- Locate target game wrapper ---
        # Try all sport-specific wrapper classes
        wrapper_selectors = [
            "table.table_container_betting Soccer",
            "table.table_container_betting Basketball",
            "table.table_container_betting Baseball",
            "table.table_container_betting Hockey",
            "table.table_container_betting American Football",
            "table.table_container_betting Tennis",
            "table.teams_betting_options_2",
            "table.teams_betting_options",
        ]
        away_team = teams.split(" vs ")[-1].strip() if " vs " in teams else ""
        target_wrapper = None

        for ws in wrapper_selectors:
            wrappers = page.locator(ws).all()
            for w in wrappers:
                home_div = w.locator("div.team1_name_up").first
                away_div = w.locator("div.team2_name_down").first
                try:
                    h_text = home_div.inner_text(timeout=500).lower().strip()
                    a_text = away_div.inner_text(timeout=500).lower().strip()
                    ht_last = home_team.split()[-1].lower()
                    at_last = away_team.split()[-1].lower()
                    if ht_last in h_text or at_last in a_text:
                        target_wrapper = w
                        log.info(f"[BetBCK] Found game wrapper: '{h_text}' vs '{a_text}'")
                        break
                except Exception:
                    continue
            if target_wrapper:
                break

        if not target_wrapper:
            log.warning(f"[BetBCK] Could not locate game wrapper for '{teams}' in results.")
            return "error"

        # --- Click the odds cell for the target market ---
        odds_cells = target_wrapper.locator(CONFIRMED_SELECTORS["odds_td"]).all()
        clicked_odds = False
        for cell in odds_cells:
            try:
                cell_text = cell.inner_text(timeout=300).strip()
                if betbck_odds and betbck_odds in cell_text:
                    cell.click()
                    human_delay(800, 1500)
                    clicked_odds = True
                    log.info(f"[BetBCK] Clicked odds cell: {betbck_odds}")
                    break
            except Exception:
                continue

        if not clicked_odds:
            log.warning(f"[BetBCK] Could not find odds cell for {betbck_odds}. Selectors need manual confirmation.")
            return "selector_todo"

        # --- Enter stake and submit ---
        # TODO: confirm "wager_amount_input" and "wager_submit_button" selectors after
        # observing the DOM that appears when an odds cell is clicked.
        try:
            page.locator(CONFIRMED_SELECTORS["wager_amount_input"]).fill(str(stake))
            human_delay(400, 900)
            page.locator(CONFIRMED_SELECTORS["wager_submit_button"]).click()
            human_delay(1500, 3000)
            log.info(f"[BetBCK] Bet submitted: ${stake:.2f} on {teams} | {market} {selection} {line} @ {betbck_odds}")
            return "placed"
        except Exception as exc:
            log.warning(
                f"[BetBCK] Bet-slip entry failed ({exc}). "
                "Update CONFIRMED_SELECTORS['wager_amount_input'] and ['wager_submit_button'] "
                "after inspecting the DOM when an odds cell is clicked."
            )
            return "selector_todo"

    except Exception as exc:
        log.error(f"[BetBCK] Unexpected error: {exc}")
        return "error"


def process_ev_alert(
    event: Dict[str, Any],
    event_id: str,
    min_ev: float,
    stake: float,
    dry_run: bool,
    page: Optional["Page"],
    already_bet: set,
    credentials: Dict,
    logged_in: bool,
) -> bool:
    """Evaluate markets and bet on qualifying ones. Returns updated logged_in flag."""
    markets = event.get("markets", [])
    teams = event.get("title", "Unknown")

    for m in markets:
        ev_str = str(m.get("ev", "0")).replace("%", "")
        try:
            ev = float(ev_str)
        except ValueError:
            continue

        if ev < min_ev:
            continue

        sel  = m.get("selection", "?")
        line = m.get("line", "") or ""
        betbck_odds = m.get("betbck_odds", "")
        pin_nvp     = m.get("pinnacle_nvp", "")
        mkt         = m.get("market", "?")

        bet_key = f"{event_id}_{mkt}_{sel}_{line}"
        if bet_key in already_bet:
            log.info(f"[Skip] Already acted on: {bet_key}")
            continue

        log.info(
            f"[+EV {ev:+.2f}%] {teams} | {mkt} {sel} {line} "
            f"@ BetBCK {betbck_odds} | PIN_NVP {pin_nvp}"
        )

        status = "skipped"
        if page and not dry_run:
            if not logged_in and credentials.get("customer_id"):
                logged_in = login_to_betbck(page, credentials["customer_id"], credentials["password"])
            if logged_in:
                status = search_and_place_bet(
                    page=page,
                    teams=teams,
                    market=mkt,
                    selection=sel,
                    line=line,
                    betbck_odds=betbck_odds,
                    stake=stake,
                    dry_run=False,
                )
        elif dry_run:
            status = search_and_place_bet(
                page=None, teams=teams, market=mkt, selection=sel,
                line=line, betbck_odds=betbck_odds, stake=stake, dry_run=True,
            )

        log_bet({
            "placed_at": datetime.utcnow().isoformat() + "Z",
            "event_id": event_id,
            "teams": teams,
            "market": mkt,
            "selection": sel,
            "line": line,
            "betbck_odds": betbck_odds,
            "pinnacle_nvp": pin_nvp,
            "ev_pct": f"{ev:+.2f}%",
            "stake": stake,
            "dry_run": dry_run,
            "status": status,
        })

        if status in ("placed", "dry_run"):
            already_bet.add(bet_key)

    return logged_in


def run(backend: str, min_ev: float, stake: float, dry_run: bool, credentials: Dict):
    log.info(
        f"AutoBettor starting | backend={backend} | "
        f"min_ev={min_ev:.1f}% | stake=${stake:.2f} | dry_run={dry_run}"
    )
    if not dry_run:
        log.info("[!] Live mode — bets WILL be placed when selectors are confirmed.")
    init_bet_log()

    if not HAS_SSE:
        log.error("sseclient-py required: pip install sseclient-py")
        return

    stream_url = f"{backend.rstrip('/')}/api/events/stream"
    already_bet: set = set()
    logged_in = False

    playwright_ctx = None
    page: Optional["Page"] = None

    if not dry_run and HAS_PLAYWRIGHT:
        playwright_ctx = sync_playwright().start()
        browser = playwright_ctx.chromium.launch(headless=False)
        context: BrowserContext = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        log.info("[Browser] Chromium launched (visible — do not close).")

    while True:
        try:
            log.info(f"[SSE] Connecting to {stream_url}")
            response = requests.get(
                stream_url,
                headers={"Accept": "text/event-stream", "Cache-Control": "no-cache"},
                stream=True,
                timeout=65,
            )
            client = sseclient.SSEClient(response)

            for msg in client.events():
                if not msg.data or msg.data.strip() in ("", "ping"):
                    continue
                try:
                    payload = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue

                msg_type = payload.get("type")

                if msg_type == "pod_alert":
                    event_id = payload.get("eventId", "")
                    event    = payload.get("event", {})
                    logged_in = process_ev_alert(
                        event=event, event_id=event_id,
                        min_ev=min_ev, stake=stake,
                        dry_run=dry_run, page=page,
                        already_bet=already_bet,
                        credentials=credentials,
                        logged_in=logged_in,
                    )

                elif msg_type == "pod_alert_removed":
                    event_id = payload.get("eventId", "")
                    log.info(f"[Expired] Alert removed: {event_id}")
                    already_bet = {k for k in already_bet if not k.startswith(event_id)}

        except KeyboardInterrupt:
            log.info("Stopped by user.")
            break
        except Exception as exc:
            log.error(f"[SSE] Connection error: {exc} — reconnecting in 5s")
            time.sleep(5)

    if playwright_ctx:
        playwright_ctx.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UnifiedBetting3 Auto-Bettor")
    parser.add_argument("--backend", default="http://localhost:8000",
                        help="Backend base URL")
    parser.add_argument("--min-ev", type=float, default=3.0,
                        help="Minimum EV %% to act on (default: 3.0)")
    parser.add_argument("--stake", type=float, default=50.0,
                        help="Flat stake per bet in $ (default: 50)")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                        help="Enable live betting (default is dry-run)")
    parser.add_argument("--customer-id", default=os.environ.get("BETBCK_ID", ""),
                        help="BetBCK customer ID (or set BETBCK_ID env var)")
    parser.add_argument("--password", default=os.environ.get("BETBCK_PASS", ""),
                        help="BetBCK password (or set BETBCK_PASS env var)")
    parser.set_defaults(dry_run=True)
    args = parser.parse_args()

    creds = {"customer_id": args.customer_id, "password": args.password}
    if not args.dry_run and not creds["customer_id"]:
        parser.error("--customer-id (or BETBCK_ID env var) required for live mode.")

    run(
        backend=args.backend,
        min_ev=args.min_ev,
        stake=args.stake,
        dry_run=args.dry_run,
        credentials=creds,
    )
