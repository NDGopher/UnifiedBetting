"""
auto_bettor.py — Foundation auto-betting script for UnifiedBetting3.

Connects to the backend SSE stream, listens for +EV POD alerts, and
(when enabled) places bets on BetBCK with human-like behaviour.

Usage:
  # Point at local dev backend:
  python auto_bettor.py --backend http://localhost:8000 --min-ev 3.0

  # Point at Replit backend (through port-5000 proxy):
  python auto_bettor.py --backend https://<replit-domain>:5000 --min-ev 3.0

  # Dry-run mode (no bets placed, just logs):
  python auto_bettor.py --backend http://localhost:8000 --min-ev 2.0 --dry-run

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
    from playwright.sync_api import sync_playwright, Page
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


BET_LOG_FILE = "placed_bets.csv"
BET_LOG_FIELDS = [
    "placed_at", "event_id", "teams", "market", "selection", "line",
    "betbck_odds", "pinnacle_nvp", "ev_pct", "stake", "dry_run"
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
    """Pause for a random human-like delay."""
    time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


def human_type(page: "Page", selector: str, text: str):
    """Type text character by character with random delays."""
    el = page.locator(selector)
    el.click()
    human_delay(100, 300)
    for char in text:
        el.press(char)
        time.sleep(random.uniform(0.04, 0.15))


def place_bet_on_betbck(
    page: "Page",
    teams: str,
    market: str,
    selection: str,
    line: str,
    odds: str,
    stake: float,
    dry_run: bool,
) -> bool:
    """
    Navigate BetBCK and place a bet with human-like behaviour.
    Returns True if successful (or dry_run=True).

    NOTE: This is a foundation skeleton. Fill in the exact selectors
    once you have confirmed the BetBCK UI structure.
    """
    if dry_run:
        log.info(f"[DRY RUN] Would bet ${stake} on {teams} | {market} {selection} {line} @ {odds}")
        return True

    if not HAS_PLAYWRIGHT:
        log.error("Playwright not available — cannot place bet.")
        return False

    try:
        log.info(f"[Bet] Placing ${stake} on {teams} | {market} {selection} {line} @ {odds}")
        page.goto("https://betbck.com/Qubic/StraightSportSelection.php")
        human_delay(800, 1500)

        # --- Search for the event ---
        search_term = teams.split(" vs ")[0].split()[-1].lower()  # last word of home team
        human_type(page, "input[name='keyword']", search_term)
        human_delay(400, 900)
        page.keyboard.press("Enter")
        human_delay(1000, 2000)

        # --- TODO: locate the correct row, click the odds cell ---
        # This section needs to be completed once BetBCK bet-slip selectors are confirmed.
        # page.locator(f"td:has-text('{odds}')").first.click()
        # human_delay(500, 1000)

        # --- TODO: enter stake and submit ---
        # page.fill("input[name='amount']", str(stake))
        # human_delay(300, 700)
        # page.locator("button:has-text('Place Bet')").click()
        # human_delay(1000, 2000)

        log.warning("[Bet] Bet-slip selectors not yet implemented — manual confirmation required.")
        return False

    except Exception as exc:
        log.error(f"[Bet] Error placing bet: {exc}")
        return False


def process_ev_alert(
    event: Dict[str, Any],
    event_id: str,
    min_ev: float,
    stake: float,
    dry_run: bool,
    page: Optional["Page"],
    already_bet: set,
):
    """Evaluate markets in an alert and bet on qualifying ones."""
    markets = event.get("markets", [])
    teams = event.get("title", "Unknown")

    for m in markets:
        ev_str = m.get("ev", "0%").replace("%", "")
        try:
            ev = float(ev_str)
        except ValueError:
            continue

        if ev < min_ev:
            continue

        bet_key = f"{event_id}_{m['market']}_{m['selection']}_{m.get('line', '')}"
        if bet_key in already_bet:
            log.info(f"[Skip] Already acted on {bet_key}")
            continue

        log.info(
            f"[+EV] {teams} | {m['market']} {m['selection']} {m.get('line','')} "
            f"@ BetBCK {m['betbck_odds']} | NVP {m['pinnacle_nvp']} | EV {ev:.2f}%"
        )

        success = place_bet_on_betbck(
            page=page,
            teams=teams,
            market=m["market"],
            selection=m["selection"],
            line=m.get("line", ""),
            odds=m["betbck_odds"],
            stake=stake,
            dry_run=dry_run,
        )

        log_bet({
            "placed_at": datetime.utcnow().isoformat() + "Z",
            "event_id": event_id,
            "teams": teams,
            "market": m["market"],
            "selection": m["selection"],
            "line": m.get("line", ""),
            "betbck_odds": m["betbck_odds"],
            "pinnacle_nvp": m["pinnacle_nvp"],
            "ev_pct": f"{ev:.2f}%",
            "stake": stake,
            "dry_run": dry_run,
        })

        if success:
            already_bet.add(bet_key)


def run(backend: str, min_ev: float, stake: float, dry_run: bool):
    log.info(f"AutoBettor starting | backend={backend} | min_ev={min_ev}% | stake=${stake} | dry_run={dry_run}")
    init_bet_log()

    if not HAS_SSE:
        log.error("sseclient-py required. Install with: pip install sseclient-py")
        return

    stream_url = f"{backend.rstrip('/')}/api/events/stream"
    already_bet: set = set()

    playwright_ctx = None
    page = None
    if not dry_run and HAS_PLAYWRIGHT:
        playwright_ctx = sync_playwright().start()
        browser = playwright_ctx.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        log.info("[Browser] Chromium launched")

    while True:
        try:
            log.info(f"[SSE] Connecting to {stream_url}")
            headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}
            response = requests.get(stream_url, headers=headers, stream=True, timeout=60)
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
                    event = payload.get("event", {})
                    process_ev_alert(
                        event=event,
                        event_id=event_id,
                        min_ev=min_ev,
                        stake=stake,
                        dry_run=dry_run,
                        page=page,
                        already_bet=already_bet,
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
    parser.add_argument(
        "--backend",
        default="http://localhost:8000",
        help="Backend base URL (e.g. http://localhost:8000 or https://your-replit.dev:5000)",
    )
    parser.add_argument("--min-ev", type=float, default=3.0, help="Minimum EV %% to act on (default: 3.0)")
    parser.add_argument("--stake", type=float, default=50.0, help="Flat stake per bet in dollars (default: 50)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Log bets without placing them (default: True)")
    args = parser.parse_args()

    run(
        backend=args.backend,
        min_ev=args.min_ev,
        stake=args.stake,
        dry_run=args.dry_run,
    )
