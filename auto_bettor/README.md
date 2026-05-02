# Auto-Bettor

Foundation script that connects to the backend SSE stream, monitors for +EV alerts, and places bets on BetBCK with human-like behaviour.

## Setup

```bash
pip install requests sseclient-py playwright
playwright install chromium
```

## Usage

**Dry-run against local backend (default — safe, no bets placed):**
```bash
python auto_bettor.py --backend http://localhost:8000 --min-ev 3.0
```

**Dry-run against Replit:**
```bash
python auto_bettor.py --backend https://<your-replit-domain>:5000 --min-ev 3.0
```

**Live betting (when ready):**
```bash
python auto_bettor.py --backend http://localhost:8000 --min-ev 3.0 --stake 50 --no-dry-run
```

## Output files

| File | Contents |
|---|---|
| `auto_bettor.log` | Full run log with every alert seen and action taken |
| `placed_bets.csv` | Row per bet: teams, market, odds, NVP, EV, stake, timestamp |

## Status

- [x] SSE stream connection + reconnect
- [x] +EV alert detection with configurable threshold
- [x] Dry-run mode with full logging
- [x] CSV bet log
- [ ] BetBCK bet-slip automation (selectors to be confirmed from live UI)
