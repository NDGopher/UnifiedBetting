# UnifiedBetting3 - Real-Time Sports Betting Alert System

## Overview
A comprehensive real-time sports betting alert system that monitors POD (Pick of the Day) alerts, compares odds across multiple sportsbooks, and provides live EV (Expected Value) calculations.

## Architecture

### Backend (FastAPI - Python)
- **Location**: `backend/`
- **Entry point**: `backend/main.py`
- **Port**: 8000 (localhost)
- **Framework**: FastAPI + uvicorn
- **Key features**: WebSocket broadcasting, background event refresher, POD alerts, BetBCK scraping, Pinnacle odds fetching

### Frontend (React + TypeScript)
- **Location**: `frontend/`
- **Entry point**: `frontend/src/index.tsx`
- **Port**: 5000 (0.0.0.0)
- **Framework**: Create React App + Material UI
- **Key features**: Real-time alerts display, PropBuilder EV, EV Bets (Buckeye), EV Calculator

## Workflows
- **Start application**: `cd frontend && PORT=5000 BROWSER=none HOST=0.0.0.0 npm start` (webview, port 5000)
- **Backend API**: `cd backend && python -m uvicorn main:app --host localhost --port 8000 --log-level info` (console, port 8000)

## API Configuration
- Frontend uses `frontend/src/utils/apiConfig.ts` for dynamic backend URL resolution
- In Replit environment: uses `https://<replId>-8000.<domain>` format
- Locally: uses `http://localhost:8000`

## Key Components
- `frontend/src/components/PODAlerts.tsx` - Main alerts display
- `frontend/src/components/PropBuilder.tsx` - Prop builder interface
- `frontend/src/components/BuckeyeScraper.tsx` - EV Bets (Buckeye integration)
- `frontend/src/components/EVCalculator.tsx` - Manual EV calculator
- `frontend/src/utils/apiConfig.ts` - Dynamic backend URL config

## Futures EV Pipeline

Scrapes NFL/NCAAF win totals from Buckeye (bet book), FanDuel, DraftKings, and BetMGM (reference books), devigged per-book, averaged for consensus fair odds, and calculates EV against Buckeye's lines.

### Running via the dashboard
Hit **Run Futures Pipeline** in the UI. Results appear in the Futures tab.

### Running locally (recommended for full coverage)
Running locally gives you your real state's DraftKings and FanDuel — the Replit server is in Oregon, which blocks NCAAF on DK and NFL futures on FD. Your home IP will likely unlock both.

**One-time setup** (after `git pull origin main`):
```bat
pip install -r backend/requirements.txt
playwright install chromium
cd frontend && npm install
```

**Start backend + frontend** (two terminals):
```bat
cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000
cd frontend && PORT=5000 npm start
```

Then open `http://localhost:5000` and click **Run Futures Pipeline**.

The Chromium path is now auto-detected — it uses the Replit nix path when on Replit, and falls back to whatever `playwright install chromium` placed locally. No manual config needed.

### API endpoint
```
POST /api/run-futures-pipeline
GET  /api/futures-pipeline-status
GET  /api/futures-results
```

### Key files
- `backend/futures_scrapers/` — FD, DK, MGM, Buckeye scrapers
- `backend/futures_ev.py` — devig + consensus EV calc
- `backend/futures_config.py` — market definitions
- `backend/data/futures_results.json` — last run output

## Notes
- Selenium/Chrome-based PTO scraper requires Chrome browser (not available in Replit sandbox, will log errors but won't crash)
- pywin32 is Windows-only and not required in Linux/Replit
- The backend gracefully handles missing Chrome by retrying the PTO scraper
- WebSocket endpoint: `/ws` on the backend port
