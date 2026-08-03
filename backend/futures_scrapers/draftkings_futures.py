"""Scrape DraftKings season win totals via Playwright.

DraftKings lazy-loads team markets as the user scrolls.  We navigate to each
sport's win-totals page and scroll aggressively to trigger all API calls to
sportsbook-nash.draftkings.com, then intercept and collect all JSON responses.

DK only exposes "Regular Season Wins Alternates" (multiple lines per team).
We return ALL alternate lines so the caller can pick the one that best matches
the FanDuel / BetBCK primary line.
"""
import asyncio
import json
import logging
import re

logger = logging.getLogger(__name__)

CHROMIUM_PATH = (
    "/nix/store/qa9cnw4v5xkxyip6mb9kxqfq1z4x2dx1-chromium-138.0.7204.100/bin/chromium"
)

# DK URL for each sport's win-totals / futures page
DK_WIN_TOTAL_PAGES = [
    # nav_1=regular-season-wins loads the "Regular Season Wins Alternates" market on DK
    (
        "NFL",
        "https://sportsbook.draftkings.com/leagues/football/nfl"
        "?category=futures&subcategory=wins&nav_1=regular-season-wins",
    ),
    # NCAAF win totals — confirmed working URL from user
    (
        "NCAAF",
        "https://sportsbook.draftkings.com/leagues/football/ncaaf"
        "?category=wins&subcategory=regular-season&nav_1=all-teams",
    ),
]

# Market type strings that represent season win totals on DK (broad — NCAAF may differ)
DK_WIN_TOTAL_TYPE_KWS = (
    "Regular Season Wins",
    "Season Wins",
    "Win Total",
    "Season Win Total",
    "Regular Season Win",
    "Wins",
)

# Match both "ARI Cardinals Regular Season Wins 2026" AND "Alabama Win Total 2026"
_MARKET_NAME_RE = re.compile(
    r"^(?P<team>.+?)\s+(?:Regular Season )?Win(?:s|s Alternates| Total)\b",
    re.IGNORECASE,
)

# DK API hostnames to intercept (NCAAF may not use sportsbook-nash)
_DK_API_HOSTS = (
    "sportsbook-nash.draftkings.com",
    "api.draftkings.com",
    "sportsbook.draftkings.com",
)

# Abbreviated NFL team prefix → full name
_NFL_ABBREV: dict[str, str] = {
    "ARI Cardinals": "Arizona Cardinals",
    "ATL Falcons": "Atlanta Falcons",
    "BAL Ravens": "Baltimore Ravens",
    "BUF Bills": "Buffalo Bills",
    "CAR Panthers": "Carolina Panthers",
    "CHI Bears": "Chicago Bears",
    "CIN Bengals": "Cincinnati Bengals",
    "CLE Browns": "Cleveland Browns",
    "DAL Cowboys": "Dallas Cowboys",
    "DEN Broncos": "Denver Broncos",
    "DET Lions": "Detroit Lions",
    "GB Packers": "Green Bay Packers",
    "HOU Texans": "Houston Texans",
    "IND Colts": "Indianapolis Colts",
    "JAX Jaguars": "Jacksonville Jaguars",
    "KC Chiefs": "Kansas City Chiefs",
    "LAC Chargers": "Los Angeles Chargers",
    "LAR Rams": "Los Angeles Rams",
    "LV Raiders": "Las Vegas Raiders",
    "MIA Dolphins": "Miami Dolphins",
    "MIN Vikings": "Minnesota Vikings",
    "NE Patriots": "New England Patriots",
    "NO Saints": "New Orleans Saints",
    "NYG Giants": "New York Giants",
    "NYJ Jets": "New York Jets",
    "PHI Eagles": "Philadelphia Eagles",
    "PIT Steelers": "Pittsburgh Steelers",
    "SEA Seahawks": "Seattle Seahawks",
    "SF 49ers": "San Francisco 49ers",
    "TB Buccaneers": "Tampa Bay Buccaneers",
    "TEN Titans": "Tennessee Titans",
    "WSH Commanders": "Washington Commanders",
}


def _parse_dk_american(odds_str: str) -> int | None:
    """Parse DK odds strings like '−320', '+250', '-110' to integers."""
    if not odds_str:
        return None
    # Normalise Unicode minus signs
    cleaned = odds_str.replace("\u2212", "-").replace("\u2013", "-").strip()
    try:
        return int(cleaned)
    except ValueError:
        return None


def _expand_team_name(raw: str) -> str:
    """Expand DK abbreviated team names; leave NCAAF full names unchanged."""
    return _NFL_ABBREV.get(raw, raw)


def parse_dk_nash_response(data: dict, sport: str) -> list[dict]:
    """Parse one sportsbook-nash JSON response into standardised win-total records.

    Each record: {team, sport, line, direction ('over'|'under'), american_odds, book}
    """
    records: list[dict] = []
    markets = {m["id"]: m for m in data.get("markets", [])}
    selections = data.get("selections", [])

    # Log all unique market type names on first parse per sport so we can tune keywords
    unique_mt = {m.get("marketType", {}).get("name", "") for m in markets.values()}
    if unique_mt:
        logger.info("[DK] %s market types in response: %s", sport, sorted(unique_mt)[:20])

    for sel in selections:
        market_id = sel.get("marketId")
        market = markets.get(market_id)
        if not market:
            continue

        mt_name: str = market.get("marketType", {}).get("name", "")
        if not any(kw in mt_name for kw in DK_WIN_TOTAL_TYPE_KWS):
            continue

        m_name: str = market.get("name", "")
        name_match = _MARKET_NAME_RE.match(m_name)
        if not name_match:
            continue

        team_raw = name_match.group("team").strip()
        team = _expand_team_name(team_raw)

        label: str = sel.get("label", "")  # "Over" | "Under"
        if label not in ("Over", "Under"):
            continue

        points = sel.get("points")
        if points is None:
            continue

        odds_str: str = sel.get("displayOdds", {}).get("american", "")
        amer = _parse_dk_american(odds_str)
        if amer is None:
            continue

        records.append(
            {
                "team": team,
                "sport": sport,
                "line": float(points),
                "direction": label.lower(),
                "american_odds": amer,
                "market_type": mt_name,
                "book": "DraftKings",
            }
        )

    return records


def _parse_dom_win_totals(html_text: str, sport: str) -> list[dict]:
    """Parse DK page text content (from DOM) to extract win total over/under records.

    DK renders odds in text like:
        "Alabama\nOver 8.5\n-120\nUnder 8.5\n+100"

    We look for "Over X.5" / "Under X.5" patterns adjacent to team names and odds.
    """
    import re as _re

    # Find all Over/Under occurrences with a line and then an immediately following odds
    # Pattern: "Over 8.5" or "Under 8.5" then optionally whitespace then an american odds string
    ou_odds_re = _re.compile(
        r'(Over|Under)\s+([\d.]+)\s*\n\s*([+-]?\d{3,4})',
        _re.IGNORECASE,
    )

    records: list[dict] = []
    matches = list(ou_odds_re.finditer(html_text))
    if not matches:
        return records

    # For each match, try to find the team name by looking backwards in the text
    # Team names appear on their own line before the Over/Under block
    lines = html_text.split('\n')
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def _find_team_name(match_start: int) -> str:
        """Walk backwards from match_start to find the last non-empty line that looks like a team."""
        # Find which line the match is on
        idx = 0
        for i, s in enumerate(line_starts):
            if s > match_start:
                idx = i - 1
                break
        else:
            idx = len(lines) - 1

        # Walk back up to 10 lines looking for a non-empty, non-odds line
        for i in range(idx - 1, max(0, idx - 10), -1):
            ln = lines[i].strip()
            if not ln:
                continue
            # Skip lines that look like odds (+120, -110) or numbers
            if _re.match(r'^[+-]?\d{1,4}$', ln):
                continue
            # Skip lines that look like "Over X.5" / "Under X.5"
            if _re.match(r'^(Over|Under)\s+[\d.]+$', ln, _re.IGNORECASE):
                continue
            # Skip very short lines (likely scores or labels)
            if len(ln) < 3:
                continue
            return ln
        return ""

    seen: set = set()
    for m in matches:
        direction = m.group(1).lower()
        try:
            line_val = float(m.group(2))
        except ValueError:
            continue
        try:
            amer = int(m.group(3))
        except ValueError:
            continue

        team = _find_team_name(m.start())
        if not team or len(team) > 50:
            continue

        key = (team.lower(), line_val, direction)
        if key in seen:
            continue
        seen.add(key)

        records.append({
            "team":          team,
            "sport":         sport,
            "line":          line_val,
            "direction":     direction,
            "american_odds": amer,
            "market_type":   "Regular Season Wins (DOM)",
            "book":          "DraftKings",
        })

    return records


async def _extract_dk_page_records(page, sport: str) -> list[dict]:
    """Try to extract win-total records from DK page after load.

    Strategy 1: read visible DOM text and parse Over/Under patterns.
    Strategy 2: walk page.evaluate for any embedded JSON structures.
    """
    records: list[dict] = []

    # ── Strategy 1: DOM text content ─────────────────────────────────────────
    try:
        dom_text: str = await page.evaluate(
            """() => {
                // Get text of the main content area — skip nav/header noise
                const main = document.querySelector('main') || document.body;
                return main.innerText || '';
            }"""
        )
        if dom_text:
            dom_records = _parse_dom_win_totals(dom_text, sport)
            if dom_records:
                logger.info("[DK] DOM text extraction → %d %s records", len(dom_records), sport)
                records.extend(dom_records)
    except Exception as exc:
        logger.debug("[DK] DOM text extraction failed: %s", exc)

    # ── Strategy 2: __NEXT_DATA__ server-side props ───────────────────────────
    if not records:
        try:
            next_data = await page.evaluate("() => window.__NEXT_DATA__ || null")
            if next_data:
                # DK embeds market data somewhere in the props tree; do a deep search
                import json as _json
                blob = _json.dumps(next_data)
                # Look for patterns with "Regular Season Wins" or "Win Total"
                if "Regular Season" in blob or "Win Total" in blob:
                    # Try nash-like parsing on the extracted blob
                    parsed_blob = _json.loads(blob)
                    nd_records = parse_dk_nash_response(parsed_blob, sport)
                    if nd_records:
                        logger.info("[DK] __NEXT_DATA__ extraction → %d %s records", len(nd_records), sport)
                        records.extend(nd_records)
        except Exception as exc:
            logger.debug("[DK] __NEXT_DATA__ extraction failed: %s", exc)

    return records


async def scrape_draftkings_win_totals() -> list[dict]:
    """Navigate to each DK win-totals page, scroll to trigger lazy loading,
    intercept all sportsbook-nash API responses, and return parsed records.
    """
    from playwright.async_api import async_playwright

    all_records: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        for sport, url in DK_WIN_TOTAL_PAGES:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/138.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 900},
                locale="en-US",
                timezone_id="America/Chicago",
            )

            sport_records: list[dict] = []

            async def _on_response(r, _sport=sport, _records=sport_records):
                # Intercept all DK JSON endpoints (nash + main API + sportsbook)
                if not any(h in r.url for h in _DK_API_HOSTS):
                    return
                if r.status != 200:
                    return
                ct = r.headers.get("content-type", "")
                if "json" not in ct:
                    return
                try:
                    body = await r.body()
                    data = json.loads(body)
                    parsed = parse_dk_nash_response(data, _sport)
                    if parsed:
                        _records.extend(parsed)
                        logger.info(
                            "[DK] Intercepted %s response (%s): +%d records",
                            _sport, r.url[:80], len(parsed),
                        )
                    else:
                        # Log all market type names we saw but didn't match
                        unique_mt = {
                            m.get("marketType", {}).get("name", "")
                            for m in data.get("markets", [])
                        }
                        if unique_mt and unique_mt != {""}:
                            logger.info(
                                "[DK] %s non-matching types from %s: %s",
                                _sport, r.url[:60], sorted(unique_mt)[:10],
                            )
                        # Save debug sample for any response with markets
                        if data.get("markets"):
                            import pathlib
                            dbg_dir = pathlib.Path("/home/runner/workspace/backend/data")
                            dbg_dir.mkdir(exist_ok=True)
                            dbg_path = dbg_dir / f"dk_{_sport.lower()}_raw_debug.json"
                            with open(dbg_path, "w") as _f:
                                json.dump(
                                    {"url": r.url,
                                     "markets": data.get("markets", [])[:5],
                                     "selections": data.get("selections", [])[:20]},
                                    _f, indent=2
                                )
                            logger.info("[DK] Saved debug sample → %s", dbg_path)
                except Exception as exc:  # pylint: disable=broad-except
                    logger.debug("[DK] Could not parse response from %s: %s", r.url[:60], exc)

            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page.on("response", _on_response)

            try:
                await page.goto(url, timeout=45_000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3_000)

                # Scroll aggressively to trigger lazy loading for all teams.
                # NFL has 32 teams × multiple alternate lines — need deep scroll.
                # 300 steps × 300 px = 90 000 px total; 200 ms between steps.
                for _ in range(300):
                    await page.evaluate("window.scrollBy(0, 300)")
                    await page.wait_for_timeout(200)

                # Scroll back to top then down again to catch any missed loads
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(1_000)
                for _ in range(100):
                    await page.evaluate("window.scrollBy(0, 500)")
                    await page.wait_for_timeout(150)

                # Wait for final API calls to settle
                await page.wait_for_timeout(5_000)

                # If XHR interception yielded nothing, fall back to DOM/SSR extraction
                if not sport_records:
                    logger.info("[DK] %s: no XHR records — trying DOM/SSR extraction", sport)
                    fallback = await _extract_dk_page_records(page, sport)
                    sport_records.extend(fallback)

                logger.info(
                    "[DK] %s: collected %d records after scroll", sport, len(sport_records)
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("[DK] Navigation error for %s: %s", sport, exc)
            finally:
                await page.close()
                await context.close()

            all_records.extend(sport_records)

        await browser.close()

    logger.info("[DK] Total records across all sports: %d", len(all_records))
    return all_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rows = asyncio.run(scrape_draftkings_win_totals())
    print(f"DK win totals: {len(rows)} rows")
    for r in rows[:5]:
        print(r)
