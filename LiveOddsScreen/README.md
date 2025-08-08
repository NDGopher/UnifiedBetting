Live Odds Comparison (Prototype)

What this is
- A self-contained prototype to compare live odds between your BetBCK live site and PickTheOdds (PTO) live screen.
- No edits to existing project files. Everything lives inside `LiveOddsScreen`.

Key findings from livebetting.har (BetBCK live)
- The page `https://betbck.com/Qubic/livebettinggs.php` embeds an iframe to a live product:
  - `https://plive.becoms.co/live/?skin=dark&customerId=XYZ005&...`
- Live data is delivered via Socket.IO WebSocket:
  - `wss://pandora.ganchrow.com/socket.io/?EIO=4&transport=websocket`
  - The app config includes `customWebSocketUrl: wss://pandora.ganchrow.com` and uses topics/rooms managed by a shared worker.
- A token endpoint appears present: `https://plive.becoms.co/betFactoryV2/api/streamToken.php`
- There are auxiliary PHP endpoints (e.g., `CommonFunctionsAjax.php`) for UI preferences, not the main live odds feed.

Approach
- Preferred: DOM scrape (like our PropBuilder approach) to avoid reverse-engineering WebSocket payloads and auth.
- We switch into the embedded iframe and extract teams/markets/odds via configurable selectors.
- PTO live screen is also scraped via DOM (configurable selectors, reuse Chrome profile to stay logged in).

What's included
- `compare_live_odds.py`: CLI to run both scrapers, normalize team names, and print a quick comparison.
- `betbck_live_dom_scraper.py`: DOM scraper for BetBCK live (handles iframe).
- `pto_live_dom_scraper.py`: DOM scraper for PTO live.
- `team_matching.py`: Aggressive normalization and fuzzy matching for cross-source team alignment.
- `selectors.sample.json`: Per-site CSS selectors you can tune without code changes.
- `config.sample.json`: Configure URLs and Chrome profile paths.

Quick start
1) Copy configs and edit:
   - `config.sample.json` -> `config.json`
   - `selectors.sample.json` -> `selectors.json`
2) Ensure Chrome is closed, then run with your profile to reuse sessions/login:
   - Set `chrome_user_data_dir` and optional `chrome_profile_dir` in `config.json`.
3) Install requirements (uses Selenium):
   - `pip install -r requirements.txt` (see local file here)
4) Run the comparator:
   - `python compare_live_odds.py --config config.json --selectors selectors.json`

Notes
- This is a scaffold. Selectors will likely need small adjustments once we confirm the actual PTO/BetBCK DOMs. Start by running each scraper in isolation with `--debug` to print raw text from found nodes.
- If you want a WebSocket client instead, we can add one to subscribe to the `pandora.ganchrow.com` topics, but it will need session context (gsid/token) and knowledge of subscription channels.

Next steps (once you provide any login/session details if needed)
- Lock the CSS selectors for PTO live and the iframe content.
- Expand market extraction (moneyline/spread/total) into a consistent schema.
- Persist snapshots to JSON for diffing over time.

