# UnifiedBetting — POD EV Alert System

Real-time EV alert system for sports betting. A Chrome extension monitors Pinnacle Odds Dropper (POD), sends alerts to a FastAPI backend that pulls Pinnacle NVP from the Swordfish API and scrapes BetBCK odds, calculates expected value, and streams everything live to a React dashboard.

---

## How It Works

```
POD page (Chrome)
  → Chrome Extension (Odds Dropper)
    → Backend API (FastAPI, port 8000)
      ├── Swordfish API  → Pinnacle NVP
      └── BetBCK scraper → comparison odds
          → EV calculation
            → Dashboard (React, port 5000)  ← WebSocket live updates
```

---

## Quick Start — Local (Windows)

### First-time setup
```bat
setup_dependencies.bat
```
Creates the Python venv and installs all packages.

### Every run
```bat
start_local.bat
```
Starts the backend (port 8000) and frontend (port 5000) in separate console windows.
**No browser opens automatically.**

Then manually open in Chrome:
1. **http://localhost:5000** — the alert dashboard
2. **https://www.pinnacleoddsdropper.com** — with Odds Dropper extension active
3. **https://betbck.com** — so the extension can auto-search games

---

## Quick Start — Replit

Start both workflows from the Replit UI:

| Workflow | Command |
|---|---|
| Backend API | `cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info` |
| Start application | `cd frontend && PORT=5000 BROWSER=none HOST=0.0.0.0 WDS_SOCKET_PATH=/wds npm start` |

Then set the extension's Backend URL to your Replit dev URL (e.g. `https://abc123.spock.replit.dev:8000`) via the extension Options page.

---

## Chrome Extension Setup

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked** → select the `POD_Chrome_Extension/` folder
4. After loading, click **Extension options** link (or right-click icon → Options)

| Setting | Value |
|---|---|
| **Backend URL** | Remote URL e.g. `https://abc123.replit.dev:8000`. Leave blank for localhost. |
| **Port** | Only used when Backend URL is blank. Default: `8000`. |

Click **Save**, then refresh the POD tab.

**To switch between local and remote:** update Backend URL in Options and refresh POD.

---

## Project Structure

```
POD_Chrome_Extension/     Chrome extension — load this in Chrome
  manifest.json           v1.3 — host permissions + options page declared
  background.js           Forwards POD alerts to backend; reads Options URL
  content.js              Detects alerts on POD page
  options.html / .js      Backend URL config UI
  betbck_auto_search.js   Auto-searches BetBCK when alert fires

backend/                  FastAPI backend (Python 3.12)
  main.py                 Entry point, API routes, WebSocket server
  main_logic.py           Core alert processing pipeline
  pod_event_manager.py    Alert lifecycle + background refresher loop
  betbck_scraper.py       BetBCK odds scraper + team name aliases
  match_games.py          Fuzzy game/team name matching
  utils/pod_utils.py      Pinnacle NVP fetching + name normalisation
  team_utils.py           Shared team alias maps
  alert_logger.py         Per-event step-by-step alert logging
  requirements.txt        Python dependencies

frontend/                 React + TypeScript dashboard
  src/components/
    PODAlerts.tsx         Live alerts table with EV display
  src/hooks/
    useWebSocket.ts       WebSocket connection + reconnect logic

auto_bettor/              Future: automated bet placement (not active)
SharpScanner/             Future: sharp money / steam detection (not active)
docs/                     Research notes and API findings
```

---

## Adding Team Name Aliases

BetBCK and Pinnacle sometimes use different names (e.g. "Heart of Midlothian" vs "Hearts").
Add to **all four** of these files:

| File | Dict name |
|---|---|
| `backend/betbck_scraper.py` | `TEAM_ALIASES` |
| `backend/utils/pod_utils.py` | `TEAM_ALIASES` |
| `backend/team_utils.py` | `TEAM_ALIASES` |
| `backend/match_games.py` | `TEAM_NAME_MAP` |

Format: `'canonical_name': ['alias1', 'alias2']`

---

## Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/pod_alert` | Receive alert from Chrome extension |
| GET | `/get_active_events_data` | All currently active alerts |
| GET | `/api/betbck/status` | BetBCK scraper health |
| GET | `/high-ev-alerts` | Historical high-EV alerts (>3%) |
| GET | `/refresher-status` | Background refresher loop status |
| WS | `/ws` | WebSocket — live dashboard updates |

---

## Stopping Everything

```bat
kill_all.bat
```
Or just close the Backend and Frontend console windows.

---

## Future Components (not active yet)

- **`auto_bettor/`** — automated bet placement research
- **`SharpScanner/`** — sharp money / steam move detection
- **`docs/`** — API research notes (Buckeye, PTO, BetMarket, etc.)
