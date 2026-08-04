"""Scrape BetMGM season win totals via their public CDS REST API.

BetMGM (Entain platform) exposes a CDS (Content Delivery Service) API that
returns all futures markets for a competition without needing Playwright.

Discovery findings (from live page inspection):
  - Access ID lives in the page's own HTTP requests, captured in a debug run:
      YTJkYzUyNTMtMGIwOS00OTNiLWI0YjItMDM4MzA4MTY0YjA3
  - Endpoint: https://www.nv.betmgm.com/cds-api/bettingoffer/fixture-view
  - Required params: lang, country, usercountry, fixtureTypes=Standard,
    offerMapping=All, competitionIds=<id>
  - NCAAF competitionId = 211 (from URL …/college-football-211)
  - NFL   competitionId = 35  (from URL …/nfl-35)

Data shape per win-total game:
  game.name.value  = "Alabama: Regular season wins"
  game.results[]   = [{"name":{"value":"Over 8.5"}, "americanOdds": -120}, ...]

Playwright fallback is retained for geo-locked edge cases but is not expected
to be needed for the NV CDS endpoint.
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

# Data dir: relative to this file so it works locally and on Replit
DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"

# ── CDS config ─────────────────────────────────────────────────────────────────
# Static public access ID embedded in every betmgm.com page load.
_CDS_ACCESS_ID = "YTJkYzUyNTMtMGIwOS00OTNiLWI0YjItMDM4MzA4MTY0YjA3"

# nv.betmgm.com 403s from non-Nevada IPs.  Try states in order until one
# returns 200.  NJ and PA are the most broadly accessible endpoints.
_CDS_STATES = ["nj", "pa", "mi", "nv", "az", "co"]
_CDS_BASE   = "https://www.nv.betmgm.com/cds-api"  # overridden per-state below

# { sport_label: (competition_id, page_url_suffix_for_Referer) }
_SPORTS: dict[str, tuple[int, str]] = {
    "NCAAF": (211, "college-football-211"),
    "NFL":   (35,  "nfl-35"),
}

# Keywords identifying win-total markets (case-insensitive in game name)
_WIN_TOTAL_KWS = (
    "win total", "season wins", "regular season wins",
    "total wins", "season win",
)

_OVER_RE  = re.compile(r"over\s+([\d.]+)", re.IGNORECASE)
_UNDER_RE = re.compile(r"under\s+([\d.]+)", re.IGNORECASE)


def _is_win_total(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in _WIN_TOTAL_KWS)


def _parse_games(games: list, sport: str) -> list[dict]:
    """Extract win-total records from a CDS fixture's games list."""
    records: list[dict] = []

    for game in games:
        if not isinstance(game, dict):
            continue
        game_name = (game.get("name") or {}).get("value", "")
        if not _is_win_total(game_name):
            continue

        # "Alabama: Regular season wins" → "Alabama"
        team_raw = game_name.split(":")[0].strip() if ":" in game_name else game_name.strip()
        if not team_raw:
            continue

        over_odds = under_odds = None
        over_line = under_line = None

        for result in game.get("results", []):
            if not isinstance(result, dict):
                continue
            r_name  = (result.get("name") or {}).get("value", "")
            amer    = result.get("americanOdds")
            if amer is None:
                continue
            try:
                amer_int = int(amer)
            except (TypeError, ValueError):
                continue

            om = _OVER_RE.search(r_name)
            um = _UNDER_RE.search(r_name)
            if om:
                over_odds = amer_int
                try:
                    over_line = float(om.group(1))
                except ValueError:
                    pass
            elif um:
                under_odds = amer_int
                try:
                    under_line = float(um.group(1))
                except ValueError:
                    pass

        canon_line = over_line or under_line
        if canon_line is None:
            continue

        if over_odds is not None:
            records.append({
                "team":          team_raw,
                "sport":         sport,
                "line":          canon_line,
                "direction":     "over",
                "american_odds": over_odds,
                "book":          "BetMGM",
            })
        if under_odds is not None:
            records.append({
                "team":          team_raw,
                "sport":         sport,
                "line":          under_line or canon_line,
                "direction":     "under",
                "american_odds": under_odds,
                "book":          "BetMGM",
            })

    return records


def _parse_response(data, sport: str) -> list[dict]:
    """Handle the CDS fixture-view response envelope and extract games."""
    if isinstance(data, dict):
        fixture = data.get("fixture", data)
        games   = fixture.get("games", [])
        if games:
            return _parse_games(games, sport)
        # Fallback: list root
        if isinstance(data, list):
            return _parse_games(data, sport)
    elif isinstance(data, list):
        return _parse_games(data, sport)
    return []


# ── REST API scraper ───────────────────────────────────────────────────────────

async def _fetch_cds(
    sport: str,
    competition_id: int,
    page_url_override: str | None = None,
) -> list[dict]:
    """Direct REST call to BetMGM CDS API — no browser needed.

    Rotates through state endpoints (nj → pa → mi → nv …) because
    nv.betmgm.com returns 403 from non-Nevada IPs.

    page_url_override: if supplied, use this as the Referer/Origin base instead
    of the football-centric default (needed for soccer, tennis, etc.)
    """
    try:
        import httpx
    except ImportError:
        logger.warning("[MGM] httpx not available; install it: pip install httpx")
        return []

    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        for state in _CDS_STATES:
            base      = f"https://www.{state}.betmgm.com/cds-api"
            origin    = f"https://www.{state}.betmgm.com"
            page_url  = page_url_override or (
                f"{origin}/en/sports/football-11/betting/usa-9/{_SPORTS[sport][1]}"
            )
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
                ),
                "Accept":          "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer":         page_url,
                "Origin":          origin,
                "x-bwin-accessid": _CDS_ACCESS_ID,
            }
            url = (
                f"{base}/bettingoffer/fixture-view"
                f"?x-bwin-accessid={_CDS_ACCESS_ID}"
                f"&lang=en-us&country=US&usercountry=US"
                f"&competitionIds={competition_id}"
                f"&fixtureTypes=Standard&offerMapping=All"
            )
            try:
                resp = await client.get(url, headers=headers)
                logger.info("[MGM] CDS %s (%s) → HTTP %d (%d bytes)",
                            sport, state, resp.status_code, len(resp.content))
                if resp.status_code == 403:
                    logger.info("[MGM] CDS %s: %s 403 — trying next state", sport, state)
                    continue
                if resp.status_code != 200:
                    logger.warning("[MGM] CDS %s (%s): HTTP %d", sport, state, resp.status_code)
                    continue
                if not resp.content:
                    continue

                data    = resp.json()
                records = _parse_response(data, sport)

                if not records:
                    games     = data.get("fixture", data).get("games", []) if isinstance(data, dict) else []
                    all_names = [g.get("name", {}).get("value", "") for g in games[:40] if isinstance(g, dict)]
                    logger.warning("[MGM] CDS %s (%s): 0 win-total records. Game names: %s",
                                   sport, state, all_names)
                    DATA_DIR.mkdir(exist_ok=True)
                    with open(DATA_DIR / f"mgm_{sport.lower()}_cds_nomatch.json", "w") as f:
                        json.dump(all_names, f, indent=2)
                    # 200 but 0 records — stop trying other states (data issue, not geo)
                    return []
                else:
                    logger.info("[MGM] CDS %s (%s): %d win-total records", sport, state, len(records))
                    DATA_DIR.mkdir(exist_ok=True)
                    with open(DATA_DIR / f"mgm_{sport.lower()}_sample.json", "w") as f:
                        json.dump(records[:5], f, indent=2)
                    return records

            except Exception as exc:
                logger.warning("[MGM] CDS %s (%s) error: %s", sport, state, exc)
                continue

    logger.warning("[MGM] CDS %s: all state endpoints failed", sport)
    return []


# ── Playwright fallback (WebSocket interception) ───────────────────────────────

_PW_WIN_KWS = _WIN_TOTAL_KWS


async def _try_parse_ws_frame(raw: str | bytes, sport: str) -> list[dict]:
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        data = json.loads(raw)
    except Exception:
        return []
    return _parse_response(data, sport)


async def _extract_mgm_dom(page, sport: str) -> list[dict]:
    """Extract win-total records from BetMGM page via JS DOM traversal.

    Handles the rendered layout:
        "Arizona Cardinals: Regular season wins"   ← section header
        "O 2.5"  "-325"                            ← over line + odds
        "U 2.5"  "+260"                            ← under line + odds
        ...
    """
    try:
        raw: list[dict] = await page.evaluate("""() => {
            const results = [];
            const HEADER_RE = /^(.+?):\\s+Regular\\s+season\\s+wins?$/i;
            const OU_RE     = /^([OU])\\s+([\\d.]+)$/i;
            const ODDS_RE   = /^([+-]\\d{2,6})$/;

            // Collect all leaf-level text nodes in document order
            const leafTexts = [];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
            let node = walker.nextNode();
            while (node) {
                if (node.children.length === 0) {
                    const t = (node.textContent || '').trim();
                    if (t) leafTexts.push(t);
                }
                node = walker.nextNode();
            }

            let currentTeam = null;
            for (let i = 0; i < leafTexts.length; i++) {
                const t = leafTexts[i];

                // Check for section header
                const hm = HEADER_RE.exec(t);
                if (hm) { currentTeam = hm[1].trim(); continue; }

                if (!currentTeam) continue;

                // Check for O/U line label
                const om = OU_RE.exec(t);
                if (!om) continue;
                const dir  = om[1].toUpperCase() === 'O' ? 'over' : 'under';
                const line = parseFloat(om[2]);
                if (line < 1 || line > 25) continue;

                // Find the odds on the next non-empty, non-O/U line (within 5 steps)
                for (let j = i + 1; j < Math.min(i + 6, leafTexts.length); j++) {
                    const cand = leafTexts[j];
                    // Stop if we hit another O/U or a new team header
                    if (OU_RE.test(cand) || HEADER_RE.test(cand)) break;
                    const odm = ODDS_RE.exec(cand);
                    if (odm) {
                        results.push({ team: currentTeam, direction: dir,
                                       line, odds: parseInt(odm[1]) });
                        break;
                    }
                }
            }
            return results;
        }""")

        if not raw:
            return []

        # Deduplicate and convert to standard record format
        records: list[dict] = []
        seen: set = set()
        for r in raw:
            key = (r["team"].lower(), r["line"], r["direction"])
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "team":          r["team"],
                "sport":         sport,
                "line":          r["line"],
                "direction":     r["direction"],
                "american_odds": r["odds"],
                "book":          "BetMGM",
            })

        logger.info("[MGM] DOM extraction %s: %d records", sport, len(records))
        if not records:
            dom_text = await page.evaluate(
                "() => { const m = document.querySelector('main') || document.body; return m ? m.innerText : ''; }"
            )
            sample = "\n".join((dom_text or "").splitlines()[:80])
            logger.warning("[MGM] DOM extraction %s: 0 records. DOM sample:\n%s", sport, sample)
            DATA_DIR.mkdir(exist_ok=True)
            (DATA_DIR / f"mgm_{sport.lower()}_dom_debug.txt").write_text(dom_text or "", encoding="utf-8")

        return records

    except Exception as exc:
        logger.warning("[MGM] DOM extraction %s error: %s", sport, exc)
        return []


async def _scrape_via_playwright(sport: str, competition_id: int) -> list[dict]:
    """Playwright: navigate the BetMGM page, try API intercept then DOM extraction."""
    from playwright.async_api import async_playwright

    # Try NJ first for Playwright — nv.betmgm.com 403s from non-Nevada IPs
    _pw_state = "nj"
    page_url = (
        f"https://www.{_pw_state}.betmgm.com/en/sports/football-11/betting/usa-9/"
        f"{_SPORTS[sport][1]}"
    )
    records: list[dict] = []
    all_urls: list[str] = []

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
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )

        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Keep API interception as a bonus — MGM sometimes streams CDS data
        page.on("websocket", lambda ws: ws.on(
            "framereceived",
            lambda payload: asyncio.ensure_future(_handle_ws(payload, sport, records)),
        ))

        async def _on_http(r):
            all_urls.append(r.url)
            if ("cds-api" in r.url or "fixture-view" in r.url) and r.status == 200:
                try:
                    body = await r.body()
                    data = json.loads(body)
                    parsed = _parse_response(data, sport)
                    if parsed:
                        records.extend(parsed)
                        logger.info("[MGM] PW HTTP %s: +%d API records (%s)", sport, len(parsed), r.url[:80])
                except Exception:
                    pass

        page.on("response", _on_http)

        try:
            await page.goto(page_url, timeout=60_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3_000)

            # First pass: scroll to load lazy sections
            for _ in range(150):
                await page.evaluate("window.scrollBy(0, 400)")
                await page.wait_for_timeout(100)

            # Expand any collapsed "Regular season wins" accordion sections
            n_clicked: int = await page.evaluate("""() => {
                let count = 0;
                const WINS_RE = /Regular\\s+season\\s+wins?/i;
                for (const el of document.querySelectorAll('*')) {
                    if (el.children.length > 0) continue;
                    if (!WINS_RE.test(el.textContent || '')) continue;
                    // Walk up to find the clickable accordion trigger
                    let btn = el;
                    for (let i = 0; i < 6; i++) {
                        if (!btn.parentElement) break;
                        btn = btn.parentElement;
                        const exp = btn.getAttribute('aria-expanded');
                        if (exp === 'false') { try { btn.click(); count++; } catch(e) {} break; }
                        if (exp === 'true') break;  // already open
                        if (btn.tagName === 'BUTTON') { try { btn.click(); count++; } catch(e) {} break; }
                    }
                }
                return count;
            }""")
            if n_clicked:
                logger.info("[MGM] PW %s: expanded %d collapsed sections", sport, n_clicked)
                await page.wait_for_timeout(2_000)
                # Scroll once more to render newly-expanded content
                for _ in range(50):
                    await page.evaluate("window.scrollBy(0, 400)")
                    await page.wait_for_timeout(80)

            await page.wait_for_timeout(3_000)

            # DOM extraction — primary path for NFL (CDS API doesn't return win totals)
            if not records:
                logger.info("[MGM] PW %s: no API intercept — extracting from DOM", sport)
                dom_records = await _extract_mgm_dom(page, sport)
                records.extend(dom_records)

        except Exception as exc:
            logger.warning("[MGM] PW error for %s: %s", sport, exc)
        finally:
            if not records:
                bet_urls = [u for u in all_urls if "betmgm" in u.lower()]
                DATA_DIR.mkdir(exist_ok=True)
                with open(DATA_DIR / f"mgm_{sport.lower()}_pw_debug.json", "w") as f:
                    json.dump({"urls": bet_urls[:30]}, f, indent=2)
                logger.warning("[MGM] PW %s: still 0 records after DOM extraction", sport)
            await page.close()
            await context.close()
        await browser.close()

    return records


async def _handle_ws(payload: str | bytes, sport: str, records: list) -> None:
    parsed = await _try_parse_ws_frame(payload, sport)
    if parsed:
        records.extend(parsed)


# ── Public entry point ─────────────────────────────────────────────────────────

async def scrape_betmgm_win_totals() -> list[dict]:
    """Return BetMGM win-total records for all configured sports.

    Uses the direct CDS REST API (fast, no browser).  Falls back to
    Playwright+WebSocket if CDS returns nothing (geo-lock or outage).
    """
    all_records: list[dict] = []

    for sport, (competition_id, _) in _SPORTS.items():
        logger.info("[MGM] Scraping %s (competitionId=%d)…", sport, competition_id)

        records = await _fetch_cds(sport, competition_id)

        if not records:
            logger.info("[MGM] CDS yielded 0 for %s — trying Playwright fallback", sport)
            records = await _scrape_via_playwright(sport, competition_id)

        logger.info("[MGM] %s total: %d records", sport, len(records))
        all_records.extend(records)

    logger.info("[MGM] Grand total: %d records", len(all_records))
    return all_records


async def _fetch_cds_raw(competition_id: int, page_url: str) -> dict | list | None:
    """Return raw CDS JSON for any competition (no win-total parsing)."""
    try:
        import httpx
    except ImportError:
        return None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        ),
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         page_url,
        "Origin":          "https://www.nv.betmgm.com",
        "x-bwin-accessid": _CDS_ACCESS_ID,
    }
    url = (
        f"{_CDS_BASE}/bettingoffer/fixture-view"
        f"?x-bwin-accessid={_CDS_ACCESS_ID}"
        f"&lang=en-us&country=US&usercountry=US"
        f"&competitionIds={competition_id}"
        f"&fixtureTypes=Standard&offerMapping=All"
    )
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            logger.info("[MGM-RAW] CDS %d → HTTP %d (%d bytes)", competition_id, resp.status_code, len(resp.content))
            if resp.status_code == 200 and resp.content:
                return resp.json()
    except Exception as exc:
        logger.warning("[MGM-RAW] CDS %d error: %s", competition_id, exc)
    return None


async def scrape_betmgm_outright(
    competition_id: int,
    sport: str,
    market_id: str,
    game_kw: str,
    sport_path: str,
) -> list[dict]:
    """Scrape a BetMGM outright winner market (EPL, La Liga, etc.) via CDS REST.

    Returns records in the standard format:
      {team, sport, market_id, direction='winner', line=0, american_odds, book='BetMGM'}
    """
    from futures_ev_outright import parse_mgm_outright_response

    page_url = f"https://www.nv.betmgm.com/en/sports/{sport_path}"
    logger.info("[MGM-OUT] Scraping %s (competitionId=%d, path=%s)…", market_id, competition_id, sport_path)

    raw = await _fetch_cds_raw(competition_id, page_url)
    if not raw:
        logger.warning("[MGM-OUT] %s: no data from CDS", market_id)
        return []

    # Log first few game names to help debug the game_kw if needed
    if isinstance(raw, dict):
        fixture = raw.get("fixture", raw)
        games = fixture.get("games", []) if isinstance(fixture, dict) else []
        first_names = [(g.get("name") or {}).get("value", "") for g in games[:10]]
        logger.info("[MGM-OUT] %s: first game names: %s", market_id, first_names)

    records = parse_mgm_outright_response(raw, sport, market_id, game_kw)
    logger.info("[MGM-OUT] %s: %d outright records", market_id, len(records))

    if not records:
        DATA_DIR.mkdir(exist_ok=True)
        with open(DATA_DIR / f"mgm_{market_id}_debug.json", "w") as f:
            json.dump(raw if isinstance(raw, dict) else {}, f, indent=2)
        logger.warning("[MGM-OUT] %s: 0 records — raw saved for inspection", market_id)

    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rows = asyncio.run(scrape_betmgm_win_totals())
    print(f"BetMGM win totals: {len(rows)} rows")
    for r in rows[:10]:
        print(r)
