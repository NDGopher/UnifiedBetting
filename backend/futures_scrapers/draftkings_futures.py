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
import pathlib
import re

logger = logging.getLogger(__name__)

def _find_chromium() -> str | None:
    import shutil, os
    REPLIT_PATH = "/nix/store/qa9cnw4v5xkxyip6mb9kxqfq1z4x2dx1-chromium-138.0.7204.100/bin/chromium"
    if os.path.exists(REPLIT_PATH):
        return REPLIT_PATH
    for candidate in (shutil.which("chromium"), shutil.which("chromium-browser"), shutil.which("google-chrome")):
        if candidate:
            return candidate
    return None

CHROMIUM_PATH = _find_chromium()

_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"

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


# ── Direct HTTP API (primary path — no Playwright needed) ─────────────────────

_DK_WIN_KWS_LOWER = tuple(kw.lower() for kw in DK_WIN_TOTAL_TYPE_KWS)

# Known DraftKings event-group IDs (from URL pattern /leagues/football/{sport})
_DK_EG_IDS: dict[str, int] = {
    "NFL":   88808,
    "NCAAF": 84240,
}

_DK_API_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept":          "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_dk_v4_odds(data: dict, sport: str) -> list[dict]:
    """Parse DK Odds API v4 (eventgroups) response into win-total records."""
    records: list[dict] = []
    eg = data.get("eventGroup", data)
    events_by_id = {str(e["eventId"]): e for e in eg.get("events", [])}
    offers_map = eg.get("offersByEventId", {})

    if not offers_map:
        # Flat list of offers at root (alternate response shape)
        raw_offers = eg.get("offers", []) or data.get("offers", [])
        for offer in raw_offers:
            for outcome in offer.get("outcomes", []):
                direction = outcome.get("label", "").lower()
                if direction not in ("over", "under"):
                    continue
                participant = outcome.get("participant", "") or offer.get("label", "")
                participant = participant.split(" Over ")[0].split(" Under ")[0].strip()
                participant = _expand_team_name(participant)
                line = outcome.get("line")
                amer = _parse_dk_american(outcome.get("oddsAmerican", ""))
                if line is None or amer is None or not participant:
                    continue
                records.append({
                    "team": participant, "sport": sport, "line": float(line),
                    "direction": direction, "american_odds": amer,
                    "market_type": offer.get("label", ""), "book": "DraftKings",
                })
        return records

    for event_id, event_data in offers_map.items():
        event = events_by_id.get(str(event_id), {})
        for offer in event_data.get("offers", []):
            label = offer.get("label", "")
            # Accept any offer whose label contains a win-total keyword
            if not any(kw in label.lower() for kw in _DK_WIN_KWS_LOWER):
                continue
            for outcome in offer.get("outcomes", []):
                direction = outcome.get("label", "").lower()
                if direction not in ("over", "under"):
                    continue
                line = outcome.get("line")
                amer = _parse_dk_american(outcome.get("oddsAmerican", ""))
                if line is None or amer is None:
                    continue
                # participant > event name > label extraction
                participant = (
                    outcome.get("participant", "")
                    or event.get("teamName1", "")
                    or event.get("name", "")
                )
                m = _MARKET_NAME_RE.match(label)
                if not participant and m:
                    participant = m.group("team").strip()
                participant = _expand_team_name(participant.strip())
                if not participant:
                    continue
                records.append({
                    "team": participant, "sport": sport, "line": float(line),
                    "direction": direction, "american_odds": amer,
                    "market_type": label, "book": "DraftKings",
                })

    logger.info("[DK] Direct API v4 %s: parsed %d records", sport, len(records))
    return records


async def _discover_dk_eg_id(sport: str, client) -> int | None:
    """Fetch DK's page HTML and extract the current event group ID.

    DK uses Next.js.  The server embeds initial state as
    <script id="__NEXT_DATA__" type="application/json">…</script>
    which is present in the raw HTML without executing any JavaScript.
    We extract the event group ID from this JSON blob.

    Falls back to the hardcoded _DK_EG_IDS value if extraction fails
    (stale, but still worth trying).
    """
    import re as _re, json as _json

    # Use the URL from DK_WIN_TOTAL_PAGES for this sport (they have different params).
    # NFL:   ?category=futures&subcategory=wins&nav_1=regular-season-wins
    # NCAAF: ?category=wins&subcategory=regular-season&nav_1=all-teams
    # Using the wrong params causes a 302 redirect to /sports/football which
    # then yields the wrong (or no) event group ID.
    page_url = next((u for s, u in DK_WIN_TOTAL_PAGES if s == sport), None)
    if not page_url:
        sport_path = "nfl" if sport == "NFL" else "ncaaf"
        page_url = (
            f"https://sportsbook.draftkings.com/leagues/football/{sport_path}"
            f"?category=futures&subcategory=wins&nav_1=regular-season-wins"
        )
    headers = {
        **_DK_API_HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://sportsbook.draftkings.com/",
    }

    try:
        r = await client.get(page_url, headers=headers, timeout=20)
        logger.info("[DK] Page HTML %s → HTTP %d (%d bytes)", sport, r.status_code, len(r.content))
        html = r.text

        # Save for inspection
        import pathlib as _pl
        _pl.Path(str(_DATA_DIR / f"dk_{sport.lower()}_page.html")).write_text(html[:200_000], encoding="utf-8", errors="replace")

        # 1 — Try to extract __NEXT_DATA__ JSON blob
        nd_match = _re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, _re.DOTALL)
        if nd_match:
            try:
                nd = _json.loads(nd_match.group(1))
                # Search recursively for eventGroupId / leagueId in the JSON tree
                blob = _json.dumps(nd)
                # Look for patterns: "eventGroupId":NNNNNN or "leagueId":NNNNNN
                eg_hits = _re.findall(r'"eventGroup[Ii]d"\s*:\s*(\d{4,7})', blob)
                if eg_hits:
                    eg_id = int(eg_hits[0])
                    logger.info("[DK] __NEXT_DATA__ event group ID for %s: %d", sport, eg_id)
                    return eg_id
            except Exception as _e:
                logger.debug("[DK] __NEXT_DATA__ parse failed: %s", _e)

        # 2 — Broader regex scan of raw HTML for any event group reference
        eg_hits = _re.findall(r'"eventGroup[Ii]d"\s*:\s*(\d{4,7})', html)
        if eg_hits:
            eg_id = int(eg_hits[0])
            logger.info("[DK] HTML regex event group ID for %s: %d", sport, eg_id)
            return eg_id

        # 3 — Also look for the nash URL pattern embedded in the HTML
        nash_hits = _re.findall(r'eventgroup/(\d{4,7})', html)
        if nash_hits:
            eg_id = int(nash_hits[0])
            logger.info("[DK] Nash URL event group ID for %s: %d", sport, eg_id)
            return eg_id

    except Exception as exc:
        logger.warning("[DK] Page HTML fetch failed for %s: %s", sport, exc)

    # 4 — Fall back to hardcoded (may be stale)
    fallback = _DK_EG_IDS.get(sport)
    logger.warning("[DK] Using fallback event group ID for %s: %s", sport, fallback)
    return fallback


async def _fetch_dk_direct(sport: str) -> list[dict]:
    """Call DK's sportsbook-nash API directly — no browser needed.

    Strategy:
      1. Fetch DK's Next.js page HTML to extract the current event group ID
         (embedded in __NEXT_DATA__ — available without executing JavaScript).
      2. Call the sportsbook-nash CDN API directly with that ID.
         The nash API returns the same JSON format parse_dk_nash_response handles.
      3. Also try DK's Odds API v4 endpoint with the discovered ID.

    Works from any IP because the nash/odds API does not run PerimeterX
    (PerimeterX only blocks browser sessions, not plain HTTP requests).
    """
    try:
        import httpx
    except ImportError:
        logger.warning("[DK] httpx not installed; skipping direct API")
        return []

    sport_path = "nfl" if sport == "NFL" else "ncaaf"
    api_headers = {
        **_DK_API_HEADERS,
        "Referer": f"https://sportsbook.draftkings.com/leagues/football/{sport_path}",
    }

    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        # Step 1 — discover the correct event group ID from the page HTML
        eg_id = await _discover_dk_eg_id(sport, client)
        if not eg_id:
            logger.warning("[DK] No event group ID found for %s — skipping direct API", sport)
            return []

        # Step 2 — try sportsbook-nash CDN API with correct US-OR-SB site path
        # Confirmed from live Playwright intercept: base is
        # https://sportsbook-nash.draftkings.com/sites/US-OR-SB/api/sportscontent/
        # Try event-group listing endpoints to get all markets at once.
        nash_eg_urls = [
            f"https://sportsbook-nash.draftkings.com/sites/US-OR-SB/api/sportscontent/category/v2/eventgroups/{eg_id}",
            f"https://sportsbook-nash.draftkings.com/sites/US-OR-SB/api/sportscontent/category/v1/eventgroups/{eg_id}",
            f"https://sportsbook-nash.draftkings.com/sites/US-OR-SB/api/sportscontent/category/v2/eventgroups/{eg_id}/categories",
            f"https://sportsbook-nash.draftkings.com/sites/US-OR-SB/api/sportscontent/eventgroup/{eg_id}",
        ]
        for nash_url in nash_eg_urls:
            try:
                rn = await client.get(nash_url, headers=api_headers)
                logger.info("[DK] Nash API %s eg=%d → HTTP %d (%d bytes) from %s",
                            sport, eg_id, rn.status_code, len(rn.content), nash_url)
                if rn.status_code == 200:
                    try:
                        data = rn.json()
                    except Exception:
                        continue
                    records = parse_dk_nash_response(data, sport)
                    if records:
                        logger.info("[DK] Nash API %s: %d records ✓  (URL: %s)", sport, len(records), nash_url)
                        return records
                    logger.info("[DK] Nash API %s: 200 but 0 win-total records from %s", sport, nash_url[:80])
            except Exception as exc:
                logger.warning("[DK] Nash API %s error for %s: %s", sport, nash_url[:60], exc)

        # Step 3 — try Odds API v4 categories endpoint with discovered ID
        try:
            WIN_KWS = ("win total", "season wins", "wins")
            cat_url = f"https://sportsbook.draftkings.com/api/odds/v4/eventgroups/{eg_id}/categories"
            rc = await client.get(cat_url, headers=api_headers)
            logger.info("[DK] Odds API v4 categories %s eg=%d → HTTP %d", sport, eg_id, rc.status_code)
            if rc.status_code == 200:
                cats = rc.json().get("eventGroup", {}).get("offerCategories", [])
                logger.info("[DK] %s categories: %s", sport, [c.get("name") for c in cats])
                win_cat = next(
                    (c for c in cats if any(kw in c.get("name", "").lower() for kw in WIN_KWS)),
                    None,
                )
                if win_cat:
                    cat_id = win_cat["offerCategoryId"]
                    odds_url = f"https://sportsbook.draftkings.com/api/odds/v4/eventgroups/{eg_id}/categories/{cat_id}"
                    ro = await client.get(odds_url, headers=api_headers)
                    logger.info("[DK] Odds API v4 odds %s → HTTP %d (%d bytes)",
                                sport, ro.status_code, len(ro.content))
                    if ro.status_code == 200:
                        records = _parse_dk_v4_odds(ro.json(), sport)
                        if records:
                            return records
        except Exception as exc:
            logger.warning("[DK] Odds API v4 %s error: %s", sport, exc)

        return []


def _parse_dom_win_totals(html_text: str, sport: str, book: str = "DraftKings") -> list[dict]:
    """Parse DK (or FD) page DOM text into win-total records.

    Both DK and FD render each bet as a dedicated line then odds on the very
    next non-blank line, e.g.:

        Alabama Over 8.5 Wins      ← the bet
        -124                       ← odds (next non-blank line)
        Alabama Under 8.5 Wins
        +102

    This format is more reliable than the old regex that expected
    "Over 8.5\\n-124" (without the "Wins" suffix).
    """
    import re as _re

    # One bet per line: "Team Over/Under X.X Wins?" — optional trailing "Wins"
    BET_RE = _re.compile(
        r'^(?P<team>.+?)\s+(?P<dir>Over|Under)\s+(?P<line>[\d.]+)\s+Win[s]?$',
        _re.IGNORECASE,
    )
    # American odds: +/-NNN (2–4 digits)
    ODDS_RE = _re.compile(r'^([+-]\d{2,4})$')

    lines = [ln.strip() for ln in html_text.splitlines()]
    records: list[dict] = []
    seen: set = set()

    for i, ln in enumerate(lines):
        m = BET_RE.match(ln)
        if not m:
            continue

        # Find the next non-empty line and confirm it's an odds value
        odds_str: str | None = None
        for j in range(i + 1, min(i + 6, len(lines))):
            candidate = lines[j].strip()
            if not candidate:
                continue
            if ODDS_RE.match(candidate):
                odds_str = candidate
            break  # stop at first non-blank line regardless

        if odds_str is None:
            continue

        try:
            amer = int(odds_str)
        except ValueError:
            continue

        team      = m.group("team").strip()
        direction = m.group("dir").lower()
        line_val  = float(m.group("line"))

        # Sanity: odds must be plausible win-total range, team name reasonable
        if not (1.0 <= line_val <= 20.0):
            continue
        if len(team) < 2 or len(team) > 55:
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
            "book":          book,
        })

    return records


async def _extract_dk_page_records(page, sport: str) -> list[dict]:
    """Try to extract win-total records from DK page after load.

    Strategy 1: read visible DOM text and parse Over/Under patterns.
    Strategy 2: walk page.evaluate for any embedded JSON structures.
    """
    records: list[dict] = []

    # ── Pre-extraction: expand any collapsed accordion sections ──────────────
    try:
        n_expanded = await page.evaluate("""() => {
            // DK uses aria-expanded on section headers — click any that are collapsed
            const toggles = Array.from(document.querySelectorAll('[aria-expanded="false"]'));
            toggles.forEach(el => { try { el.click(); } catch(e) {} });
            return toggles.length;
        }""")
        if n_expanded:
            logger.info("[DK] %s: expanded %d collapsed sections", sport, n_expanded)
            await page.wait_for_timeout(2_000)   # let render settle
    except Exception:
        pass

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
            else:
                # Save full DOM to file and log a sample for debugging
                import pathlib as _pl
                _dbg = _DATA_DIR / f"dk_{sport.lower()}_dom_debug.txt"
                _dbg.write_text(dom_text, encoding="utf-8")
                sample = "\n".join(dom_text.splitlines()[:80])
                logger.warning("[DK] %s: DOM parser returned 0 records. Full DOM saved → %s. Sample:\n%s",
                               sport, _dbg, sample)
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
    """Return DK win-total records.

    Primary path: DK's public Odds API v4 (direct HTTP — no browser, no bot
    detection).  Falls back to Playwright only if the direct API returns 0
    for a given sport.
    """
    from playwright.async_api import async_playwright

    all_records: list[dict] = []
    need_playwright: list[tuple[str, str]] = []  # (sport, url) pairs that failed direct

    # ── Primary: direct HTTP API ───────────────────────────────────────────────
    for sport, url in DK_WIN_TOTAL_PAGES:
        logger.info("[DK] %s: trying direct API first", sport)
        records = await _fetch_dk_direct(sport)
        if records:
            logger.info("[DK] %s: direct API → %d records ✓", sport, len(records))
            all_records.extend(records)
        else:
            logger.warning("[DK] %s: direct API returned 0 — queuing Playwright fallback", sport)
            need_playwright.append((sport, url))

    if not need_playwright:
        logger.info("[DK] Total records (direct API): %d", len(all_records))
        return all_records

    # ── Fallback: Playwright for sports that failed direct API ────────────────
    logger.info("[DK] Playwright fallback for: %s", [s for s, _ in need_playwright])

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            **({"executable_path": CHROMIUM_PATH} if CHROMIUM_PATH else {}),
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        for sport, url in need_playwright:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/127.0.0.0 Safari/537.36"
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
                        # ★ Log the FULL URL — critical for direct-API discovery
                        logger.info(
                            "[DK] ★ WORKING URL for %s (%d records): %s",
                            _sport, len(parsed), r.url,
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
                            dbg_dir = _DATA_DIR
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
                # domcontentloaded fires fast; then wait briefly for networkidle
                # to capture the initial batch of nash API calls before scrolling.
                # Timeout is short (12 s) because DK fires background requests
                # indefinitely and networkidle would stall forever otherwise.
                await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
                try:
                    await page.wait_for_load_state("networkidle", timeout=12_000)
                except Exception:
                    pass  # timeout is expected; initial batch already captured

                # Dismiss any location/state-selection modal that blocks content
                for selector in [
                    "button[aria-label='Close']",
                    "button:has-text('Dismiss')",
                    "button:has-text('No Thanks')",
                    "[data-testid='modal-close']",
                ]:
                    try:
                        btn = page.locator(selector).first
                        if await btn.is_visible(timeout=1_500):
                            await btn.click()
                            await page.wait_for_timeout(500)
                    except Exception:
                        pass

                # Wait up to 10 s for actual odds content to appear on the page.
                # DK uses several class patterns; any one of these confirms content loaded.
                content_loaded = False
                for sel in [
                    ".sportsbook-outcome-cell__label",
                    ".sportsbook-odds",
                    "[class*='sportsbook-table']",
                    "[class*='outcome-cell']",
                ]:
                    try:
                        await page.wait_for_selector(sel, timeout=10_000)
                        content_loaded = True
                        logger.info("[DK] %s: content confirmed via selector %s", sport, sel)
                        break
                    except Exception:
                        pass

                if not content_loaded:
                    logger.warning("[DK] %s: no odds selector appeared — page may not have loaded content", sport)

                await page.wait_for_timeout(2_000)

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


async def scrape_draftkings_outright(
    url: str,
    market_id: str,
    sport: str,
    market_kw: str = "Winner",
) -> list[dict]:
    """Scrape a DraftKings outright winner market.

    Navigates to url, intercepts Nash/sportsbook JSON, parses via
    parse_dk_outright_response.  Falls back to DOM text extraction.
    """
    import random as _random
    from playwright.async_api import async_playwright
    from futures_ev_outright import parse_dk_outright_response

    records: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            **({"executable_path": CHROMIUM_PATH} if CHROMIUM_PATH else {}),
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/Chicago",
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        await page.set_extra_http_headers({
            "sec-ch-ua": '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        })

        captured_jsons: list[dict] = []

        async def _on_response(r):
            if any(kw in r.url for kw in DK_INTERCEPT_URLS) and r.status == 200:
                try:
                    body = await r.body()
                    data = json.loads(body)
                    parsed = parse_dk_outright_response(data, sport, market_id, market_kw)
                    if parsed:
                        records.extend(parsed)
                        logger.info("[DK-OUT] Intercepted %d %s outright records from %s", len(parsed), market_id, r.url[:60])
                    captured_jsons.append(data)
                except Exception:
                    pass

        page.on("response", _on_response)

        try:
            await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
            for _ in range(80):
                await page.evaluate("window.scrollBy(0, 400)")
                await page.wait_for_timeout(120)
            await page.wait_for_timeout(5_000)

            # DOM fallback if no XHR
            if not records:
                dom_text = await page.evaluate("""() => {
                    const m = document.querySelector('main') || document.body;
                    return m ? m.innerText : '';
                }""")
                if dom_text and market_kw.lower() in dom_text.lower():
                    # Try to find team names + odds from text
                    import re as _re
                    # Pattern: "Arsenal\n+160" or "Arsenal +160"
                    pattern = _re.compile(r'([A-Z][a-zA-Z &\'-]{2,30})\s*\n?\s*([+-]\d{3,5})', _re.MULTILINE)
                    seen: set = set()
                    for m in pattern.finditer(dom_text):
                        team = m.group(1).strip()
                        try:
                            amer = int(m.group(2))
                        except ValueError:
                            continue
                        k = team.lower()
                        if k not in seen:
                            seen.add(k)
                            records.append({
                                "team": team, "sport": sport, "market_id": market_id,
                                "direction": "winner", "line": 0.0,
                                "american_odds": amer, "book": "DraftKings",
                            })
                    if records:
                        logger.info("[DK-OUT] DOM text extraction → %d %s outright records", len(records), market_id)

        except Exception as exc:
            logger.warning("[DK-OUT] Navigation error for %s: %s", market_id, exc)
        finally:
            await page.close()
            await context.close()
        await browser.close()

    # Deduplicate
    from futures_ev_outright import _canonical
    seen2: set = set()
    deduped: list[dict] = []
    for r in records:
        k = _canonical(r["team"])
        if k not in seen2:
            seen2.add(k)
            deduped.append(r)

    logger.info("[DK-OUT] %s: %d outright records total", market_id, len(deduped))
    return deduped


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rows = asyncio.run(scrape_draftkings_win_totals())
    print(f"DK win totals: {len(rows)} rows")
    for r in rows[:5]:
        print(r)
