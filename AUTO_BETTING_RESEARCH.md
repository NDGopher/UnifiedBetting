# Auto-Betting Research — UnifiedBetting3

## Goal
When a POD alert fires and the calculated EV is within our configured range, automatically place the bet on BetBCK without any manual interaction. Every placed bet should fire a Telegram notification so you can log it in PinnacleOddsDropper manually.

---

## Why Playwright (Browser Automation)?

BetBCK has no public API. All bets must be placed through the website UI. Playwright is the right tool because:

- **Headless-capable** — can run in a background process on your machine or a server, no visible window needed unless debugging
- **Already partly built** — `auto_bettor/auto_bettor.py` exists and already has the BetBCK login selectors, search logic, and `inetWagerNumber` targeting
- **Reliable** — Playwright's auto-wait handles slow page loads and AJAX updates better than raw Selenium
- **Persistent auth** — saves a browser profile/cookies so you don't log in on every run

---

## Proposed Architecture

```
POD Extension  →  FastAPI /api/alert  →  EV check
                                              │
                                    EV ≥ minEv AND ≤ maxEv
                                    AND auto-bet enabled
                                              │
                                    auto_bettor.py (Playwright)
                                              │
                                   ┌──────────┴──────────┐
                               Success                  Failure
                                  │                       │
                         bet_logger.log_bet_placed   bet_logger.log_bet_failed
                         Telegram notification       Telegram error notification
                         frontend bet feed update
```

### Key Principle: Run Playwright in the Same Process

The current `auto_bettor.py` is a standalone CLI script. The better approach for production is to integrate it as an **async function called from the FastAPI backend**, sharing the same process:

- Avoids subprocess overhead and race conditions
- Backend already has all the event/EV data in memory
- Can update the frontend via WebSocket immediately after bet placement
- Single dedup lock covers both alert processing AND bet placement

---

## BetBCK Bet Placement Flow

Based on the existing `auto_bettor.py` selectors:

```python
# 1. Login (once, persist session)
page.fill('#username', USERNAME)
page.fill('#password', PASSWORD)
page.click('button[type=submit]')

# 2. Search for the game
page.fill('#searchBox', search_term)        # e.g. "dragons" (shortest unique term)
page.click('#searchButton')

# 3. Find the right row and click the odds cell
# Selector targets inetWagerNumber — the bet slip trigger
page.click(f'td[inetWagerNumber="{wager_number}"]')

# 4. Enter stake in the bet slip
page.fill('#wagerAmt', str(stake))

# 5. Confirm
page.click('#placeBetBtn')

# 6. Verify confirmation message appears (no "insufficient funds" / error)
confirmation = page.locator('#betConfirmation').text_content()
```

**Critical:** Step 6 — always verify the confirmation. BetBCK can silently reject bets (insufficient balance, line moved, game locked). Log the full confirmation text in the bet record.

---

## Duplicate / Safety Controls

These must ALL pass before a bet fires:

| Check | Implementation |
|-------|---------------|
| EV ≥ minEv | Shared `abMinEv` state (synced with POD filter) |
| EV ≤ maxEv | Shared `abMaxEv` state |
| Auto-bet enabled | `abEnabled` toggle in Auto Bet Placement panel |
| Not already bet | `_bet_placed_this_session` set — keyed by `(event_id, market, selection, line)` |
| Max per event | Running total of stakes per `event_id` |
| Line hasn't moved | Re-check EV immediately before Playwright clicks (not just at alert time) |
| BetBCK game is live | Verify game is still showing, not "No Action" |

---

## Telegram Notifications

### Setup
1. Create a bot: message `@BotFather` → `/newbot`
2. Get your `chat_id`: send any message to the bot, then `GET https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Store as env secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

### Proposed Message Format

**Bet Placed:**
```
🎯 AUTO BET PLACED
━━━━━━━━━━━━━━━━━━━━
Away @ Home
Market: Total Over 7.0
BetBCK: -115  |  NVP: -130
EV: +5.7%  |  Stake: $50
Confirm: "Wager #48291 accepted"
Time: 2026-05-03 08:14 UTC
━━━━━━━━━━━━━━━━━━━━
📝 Enter in POD tracker manually
```

**Bet Failed:**
```
⚠️ AUTO BET FAILED
━━━━━━━━━━━━━━━━━━━━
Away @ Home — Total Over 7.0
Reason: Line moved before placement
EV at alert: +5.7%  |  Stake attempted: $50
Time: 2026-05-03 08:14 UTC
```

### Simple send function (no library needed):
```python
import httpx

async def send_telegram(message: str):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    await httpx.AsyncClient().post(url, json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    })
```

---

## Bet Log — `bets_placed.jsonl`

`bet_logger.py` already writes every bet to `backend/logs/bets/bets_placed.jsonl` (one JSON object per line). Each record contains:

```json
{
  "timestamp": "2026-05-03T08:14:22Z",
  "event_id": "1629700298",
  "home_team": "Fubon Guardians",
  "away_team": "Wei Chuan Dragons",
  "market": "Total",
  "selection": "Over",
  "line": "7.0",
  "odds_at_placement": "-115",
  "pinnacle_nvp_at_placement": "-130",
  "ev_pct_at_placement": 5.68,
  "kelly_fraction": "fixed",
  "stake": 50,
  "result": "placed"
}
```

A `GET /api/bets` endpoint can serve this file for a future "Bet History" panel in the frontend.

---

## Manual POD Tracking Workflow (Your Current Plan)

```
Auto-bet fires
    → Telegram notification on phone
    → Open PinnacleOddsDropper
    → Enter: teams, market, odds, stake manually
    → POD tracks result, P&L, CLV, etc.
```

This is the right call. POD does the tracking work well, and the Telegram notification gives you all the data you need to enter it quickly.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| BetBCK UI changes (selectors break) | Playwright runs in headed mode first when testing; add screenshot-on-failure |
| Line moves between alert and bet placement | Re-calculate EV from current NVP immediately before clicking; abort if EV dropped below threshold |
| Double-bet if backend restarts mid-alert | `bets_placed.jsonl` checked on startup to rebuild the in-session dedup set |
| BetBCK session expires | Playwright re-login on 401/redirect; store cookies in `playwright_state.json` |
| Network timeout during bet | Playwright timeout → log_bet_failed → Telegram error alert |
| Insufficient balance | Parse confirmation text; if "insufficient" appears → alert and disable auto-bet |

---

## Next Implementation Steps (Priority Order)

1. **Add Telegram env secrets** (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) — 5 min
2. **Write `telegram_notify.py`** — simple async send wrapper — 15 min
3. **Refactor `auto_bettor.py`** into an async `place_bet(event, market, stake)` function callable from FastAPI — 1 hr
4. **Wire it into the alert handler** in `main.py` after EV calculation, gated on `abEnabled` and EV range — 30 min
5. **Add `GET /api/bets` endpoint** + simple Bet History panel in frontend — 1 hr
6. **Test in dry-run mode** (log everything but don't click confirm) — iterate on selectors
7. **First live bet** — set minEv=8%, fixed $25, watch Telegram — verify manually in POD
