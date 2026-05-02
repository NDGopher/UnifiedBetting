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

## Notes
- Selenium/Chrome-based PTO scraper requires Chrome browser (not available in Replit sandbox, will log errors but won't crash)
- pywin32 is Windows-only and not required in Linux/Replit
- The backend gracefully handles missing Chrome by retrying the PTO scraper
- WebSocket endpoint: `/ws` on the backend port
