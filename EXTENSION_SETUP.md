# Extension Setup Guide — Getting Live POD Alerts

Follow these steps to start receiving live alerts in the Unified Betting dashboard.

## Prerequisites

- Google Chrome (Chromium will not work for MV3 extensions)
- Backend running on port 8000 (`Backend API` workflow started)
- Frontend running on port 5000 (`Start application` workflow started)

---

## Step 1: Load the POD Chrome Extension

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select the folder: `POD_Chrome_Extension/` (from this project root)
5. You should see "Odds Dropper" appear in your extension list
6. Verify the extension icon appears in the Chrome toolbar

The extension is now configured to send alerts to **port 8000** (already set correctly in the code).

---

## Step 2: Sign Into Pinnacle Odds Dropper

1. Navigate to [https://www.pinnacleoddsdropper.com](https://www.pinnacleoddsdropper.com)
2. Sign in with your Google account
3. Navigate to the **Terminal** section
4. The extension will automatically intercept alerts as they appear

---

## Step 3: Verify Alerts Are Flowing

When an alert fires:

1. **Backend console** — you will see a block like this:
   ```
   ============================================================
   [ALERT IN][12345678] Warriors @ Lakers | NBA | market=moneyline | -110 -> -105
   [SEARCH TERM][12345678] Using 'Lakers' (from 'Lakers' / 'Warriors'): last word of home team
   [SEARCH][12345678] POST PlayerGameSelection.php?keyword='Lakers' -> HTTP 200 (45231 bytes)
   [MATCH][12345678] [PASS] BCK 'Lakers' vs 'Warriors' <-> POD 'Lakers' vs 'Warriors' [token_sort=100]
   [FOUND][12345678] Matched BetBCK: 'Lakers' vs 'Warriors'
   [ODDS][12345678] home_moneyline=-105 | away_moneyline=+115 | ...
   [EV][12345678] Moneyline Home: BCK 1.9524 / PIN_NVP 1.8900 - 1 = +3.30%
   [ALERT DONE][12345678] result=ev_found | EV markets=1 | positive_ev=1
   ============================================================
   ```

2. **Frontend Alert Log panel** — the top card in the dashboard shows the alert in real-time:
   - Green border + "EV Found" badge = positive EV opportunity
   - Yellow border + "No EV" = game found but no edge at current lines
   - Red border + "Not Found" = BetBCK game not matched (check logs for name mismatch)
   - Gray border + "Skipped" = prop/corner bet, not supported

3. **POD Alerts section** — if EV is found, the event appears in the main table below

---

## Step 4: (Optional) Load BetBCK Helper Extension

The `betbck_extension/` folder contains a helper that shows an overlay popup on betbck.com with real-time EV data. To load it:

1. Go to `chrome://extensions`
2. Click **Load unpacked**
3. Select the folder: `betbck_extension/`

This extension is optional — the backend scrapes BetBCK server-side automatically.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| No alerts in Alert Log after POD fires | Extension not loaded or POD not signed in | Reload extension, sign into POD |
| "Not Found" result for every alert | BetBCK session expired or login failed | Check backend console for `[BetbckScraper] Login FAILED` |
| "Rate Limited" message | Too many requests to BetBCK in a short window | Wait 5 minutes for automatic cooldown reset |
| Backend not responding | Port 8000 occupied by old process | Restart the `Backend API` workflow |
| Alert Log panel shows "waiting for alerts" | WebSocket not connected | Check browser console for WS errors; ensure backend is running |

---

## Architecture Quick Reference

```
pinnacleoddsdropper.com  →  POD_Chrome_Extension  →  POST /pod_alert (port 8000)
                                                           ↓
                                                    main.py event_alert_worker
                                                           ↓
                                                    main_logic.py (AlertLogger started)
                                                           ↓
                                                    betbck_request_manager → betbck.com
                                                           ↓
                                              parse_specific_game_from_search_html
                                                           ↓
                                              analyze_markets_for_ev (Pinnacle NVP vs BCK)
                                                           ↓
                                              WS broadcast: pod_alert + alert_log
                                                           ↓
                                              Frontend: AlertLog panel + POD Alerts table
```
