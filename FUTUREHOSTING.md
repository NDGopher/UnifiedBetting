# UnifiedBetting3 — Future Hosting & Deployment Guide

## The Core Constraint

Everything in this system depends on the **POD Chrome Extension** (PinnacleOddsDropper). The extension watches Pinnacle in your browser and POSTs alerts to your backend when it detects line moves. **Without a real browser running the extension, no alerts fire.** This shapes every hosting option below.

---

## Option 1 — Pure Local (What You Have Now)

**How it works:** Run React + FastAPI on your local machine, open Chrome with the POD extension, done.

**Pros:**
- Zero cost
- Zero setup
- Works from any PC — pull the repo, start the two services, done
- Best for active monitoring where you're already at your computer

**Cons:**
- PC must be on and browser must be open
- No access from your phone / another device unless you expose the port

**Cost:** $0  
**Uptime:** Only while your PC is on  
**Best for:** Your current workflow — trading/monitoring sessions

---

## Option 2 — Hybrid: Backend on DigitalOcean, Browser Locally (Recommended Next Step)

**How it works:**
- FastAPI + React served from your DO droplet (nginx + systemd, auto-restarts on reboot)
- Change the POD extension's target from `localhost:8000` to `https://yourdomain.com`
- Run Chrome + extension on whatever PC you're at — the heavy work (BetBCK scraping, EV calc, alert history) runs 24/7 on the server

**Setup:**
1. $6/mo DO Droplet (1 vCPU, 1GB RAM — sufficient for this stack)
2. nginx reverse proxy with Let's Encrypt SSL (free)
3. systemd units for uvicorn and the React build (served as static files)
4. Point your domain (or use DO's free `.ondigitalocean.app`) to the droplet

**Pros:**
- Alert history, BetBCK scrape results, EV logs — all persistent, accessible from any device
- Backend never goes down due to laptop sleep/restart
- Frontend accessible from any browser (phone, other PCs)
- You only need Chrome + extension open when you want to receive live alerts

**Cons:**
- POD extension still runs locally (you still need a browser open with the extension)
- Small monthly cost

**Cost estimate:**
| Resource | Monthly Cost |
|----------|-------------|
| DO Droplet (Basic, 1 vCPU / 1 GB) | $6 |
| Domain (optional, e.g. Namecheap) | ~$1/mo amortized |
| SSL (Let's Encrypt) | Free |
| **Total** | **~$6–7/mo** |

**Uptime:** Backend 99.9%+ (DO SLA). Extension-dependent for live alerts.

---

## Option 3 — Fully Automated on DigitalOcean (No Local Browser Needed)

**How it works:** Run Chrome + the POD extension headlessly on the droplet using a virtual display (`Xvfb`). Access it remotely via noVNC (browser-based remote desktop) when you need to interact with it.

**Setup steps:**
1. $12/mo DO Droplet (2 vCPU, 2GB RAM — needed for Chrome)
2. Install `Xvfb`, `x11vnc`, `noVNC`, `google-chrome-stable`
3. Load the POD extension via `--load-extension` Chrome flag
4. Run everything under a single systemd unit that auto-restarts
5. Access the browser desktop via `https://yourdomain.com/novnc/` when needed

**Pros:**
- Fully unattended — alerts fire 24/7 with no local machine needed
- Can monitor games you're asleep for
- Access the browser from any device via noVNC

**Cons:**
- Chrome is memory-hungry; the $6 1GB droplet won't cut it
- Initial setup is complex (~1–2 hours)
- POD extension behavior may vary in headless environments (needs testing)
- noVNC adds a security consideration (password-protect it)

**Cost estimate:**
| Resource | Monthly Cost |
|----------|-------------|
| DO Droplet (Basic, 2 vCPU / 2 GB) | $12 |
| Domain + SSL | ~$1/mo |
| **Total** | **~$12–13/mo** |

**Uptime:** 99.9%+ for everything including alert capture.

---

## Option 4 — Replit Always-On Deployment

**How it works:** Deploy this project on Replit's paid hosting (Autoscale or Reserved VM).

**Pros:**
- Zero infrastructure management
- Built-in SSL, domain, restarts

**Cons:**
- Still requires the POD extension to run somewhere (local browser)
- More expensive than a DO droplet for equivalent compute
- Less control over the environment

**Cost estimate:**
| Tier | Monthly Cost |
|------|-------------|
| Replit Reserved VM (0.5 vCPU / 0.5 GB) | ~$7 |
| Replit Reserved VM (1 vCPU / 2 GB) | ~$20 |

**Best for:** If you want to avoid server administration entirely and cost isn't a concern.

---

## Recommended Path

```
Now         → Option 1 (pure local, free, what you have)
Next        → Option 2 (hybrid, $6/mo) — backend always on, use from any PC
Eventually  → Option 3 ($12/mo) — if you want fully unattended 24/7 alerts
```

---

## Option 2 Quick-Start Checklist (when you're ready)

```bash
# On the droplet (Ubuntu 22.04)
sudo apt update && sudo apt install -y python3-pip python3-venv nginx certbot python3-certbot-nginx nodejs npm

# Clone repo, install deps
git clone <your-repo> /opt/unifiedbetting
cd /opt/unifiedbetting/backend && pip install -r requirements.txt
cd /opt/unifiedbetting/frontend && npm install && npm run build

# Systemd unit: /etc/systemd/system/unifiedbetting-api.service
# Nginx config: proxy /api/ → localhost:8000, serve /frontend/build as static
# certbot --nginx -d yourdomain.com
```

Key config change — update the POD extension to POST to:
```
https://yourdomain.com/api/alert   (instead of http://localhost:8000/api/alert)
```

---

## Auto-Betting Architecture Research

> See `AUTO_BETTING_RESEARCH.md` for the full breakdown. Summary below.

### The Problem
BetBCK does not have an API. Bets must be placed via browser automation (Playwright).

### Recommended Architecture

```
POD Extension fires alert
    → FastAPI backend calculates EV
    → If EV ≥ threshold AND auto-bet enabled:
        → auto_bettor.py (Playwright) opens BetBCK in background
        → Places bet: searches game → selects market → enters stake → submits
        → Logs result to backend/logs/bets/bets_placed.jsonl
        → Sends Telegram notification with all bet details
```

### Telegram Notification Format (proposed)
```
🎯 AUTO BET PLACED
━━━━━━━━━━━━━━━━
Game:   Wei Chuan Dragons vs Fubon Guardians
Market: Total Over 7.0
BetBCK: -115  |  PIN NVP: -130
EV:     +5.7%
Stake:  $50 (Fixed)
Time:   2026-05-03 08:14:22 UTC
━━━━━━━━━━━━━━━━
➡ Enter in POD tracker manually
```

### Manual Tracking Workflow
1. Telegram notification fires when bet is placed
2. You manually enter in PinnacleOddsDropper for tracking
3. `bets_placed.jsonl` is your local audit trail (bet_logger.py already implemented)

### Key Safety Controls (already partially built)
- **Duplicate protection:** `_last_processed_times` dict prevents same event being bet twice within 120s
- **EV range filter:** Only bet if EV between `abMinEv` and `abMaxEv` (shared with POD Alerts view)
- **Max per event:** `abMaxPerEvent` caps total exposure per game
- **Kelly sizing:** Optional Kelly criterion sizing built into Auto Bet Placement panel

### Next Implementation Steps
1. Add Telegram bot token + chat ID to environment secrets
2. Wire `auto_bettor.py` to be called from the backend alert handler (not standalone)
3. Add Telegram notification call after successful bet placement
4. Add `/api/bets` endpoint to serve `bets_placed.jsonl` in the frontend
