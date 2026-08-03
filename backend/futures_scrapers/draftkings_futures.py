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
    (
        "NFL",
        "https://sportsbook.draftkings.com/leagues/football/nfl"
        "?category=futures&subcategory=wins&nav_1=regular-season-wins",
    ),
    (
        "NCAAF",
        "https://sportsbook.draftkings.com/leagues/football/ncaaf"
        "?category=futures&subcategory=wins",
    ),
]

# Market type strings that represent season win totals on DK
# Broad match — log all types first so we can tune if needed
DK_WIN_TOTAL_TYPE_KWS = ("Regular Season Wins", "Season Wins", "Win Total")

# Strip the year suffix from DK market names like "ARI Cardinals Regular Season Wins 2026/27"
_MARKET_NAME_RE = re.compile(
    r"^(?P<team>.+?)\s+Regular Season Wins\b", re.IGNORECASE
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
                if "sportsbook-nash.draftkings.com" not in r.url:
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
                            "[DK] Intercepted %s nash response: +%d records",
                            _sport,
                            len(parsed),
                        )
                except Exception as exc:  # pylint: disable=broad-except
                    logger.debug("[DK] Could not parse nash response: %s", exc)

            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page.on("response", _on_response)

            try:
                await page.goto(url, timeout=45_000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3_000)

                # Scroll aggressively to trigger lazy loading for all teams
                # 80 steps × 250 px = 20 000 px total; 150 ms between steps
                for _ in range(80):
                    await page.evaluate("window.scrollBy(0, 250)")
                    await page.wait_for_timeout(150)

                # Wait for final API calls to settle
                await page.wait_for_timeout(3_000)

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
