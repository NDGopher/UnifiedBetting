"""Scrape FanDuel season win totals via Playwright.

Uses a fresh Playwright browser context with Mac user-agent to bypass
PerimeterX on the first page load. Intercepts the content-managed-page
API response (1.9 MB) that contains all market odds.
"""
import asyncio
import json
import logging
import re

logger = logging.getLogger(__name__)

CHROMIUM_PATH = (
    "/nix/store/qa9cnw4v5xkxyip6mb9kxqfq1z4x2dx1-chromium-138.0.7204.100/bin/chromium"
)

# FD market-type strings that represent regular-season win totals
_WIN_TOTAL_KEYWORDS = ("REGULAR_SEASON_WINS",)
_SKIP_KEYWORDS = ("H2H", "X+_WINS")

# FD sports → (label, URL)
FD_WIN_TOTAL_PAGES = [
    ("NCAAF", "https://sportsbook.fanduel.com/navigation/ncaaf?tab=win-totals"),
    ("NFL",   "https://sportsbook.fanduel.com/navigation/nfl?tab=win-totals"),
]

RUNNER_RE = re.compile(
    r"^(?P<team>.+?)\s+(?P<dir>Over|Under)\s+(?P<line>[\d.]+)\s+Wins?$",
    re.IGNORECASE,
)


def _fresh_context_kwargs() -> dict:
    return dict(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
        locale="en-US",
        timezone_id="America/Chicago",
    )


def parse_fd_content_page(data: dict, sport: str) -> list[dict]:
    """Parse a FD content-managed-page JSON blob into standardised win-total records.

    Each record: {team, sport, line, direction ('over'|'under'), american_odds, book}
    """
    markets = data.get("attachments", {}).get("markets", {})
    results: list[dict] = []

    for mid, m in markets.items():
        mt: str = m.get("marketType", "")
        # Keep only regular-season win-total markets
        if not any(kw in mt for kw in _WIN_TOTAL_KEYWORDS):
            continue
        if any(kw in mt for kw in _SKIP_KEYWORDS):
            continue

        for runner in m.get("runners", []):
            rn: str = runner.get("runnerName", "")
            amer = (
                runner.get("winRunnerOdds", {})
                .get("americanDisplayOdds", {})
                .get("americanOdds")
            )
            if amer is None:
                continue
            match = RUNNER_RE.match(rn)
            if not match:
                continue
            results.append(
                {
                    "team": match.group("team").strip(),
                    "sport": sport,
                    "line": float(match.group("line")),
                    "direction": match.group("dir").lower(),
                    "american_odds": int(amer),
                    "market_type": mt,
                    "book": "FanDuel",
                }
            )

    return results


def _parse_fd_dom(html_text: str, sport: str) -> list[dict]:
    """Parse FD page DOM text into win-total records when API intercept is unavailable.

    FD renders each bet as:
        Alabama Over 8.5 Wins     ← one line
        -124                      ← very next non-blank line is the odds

    Same format as DK — reuse the same regex approach.
    """
    import re as _re

    BET_RE  = _re.compile(
        r'^(?P<team>.+?)\s+(?P<dir>Over|Under)\s+(?P<line>[\d.]+)\s+Win[s]?$',
        _re.IGNORECASE,
    )
    ODDS_RE = _re.compile(r'^([+-]\d{2,4})$')

    lines   = [ln.strip() for ln in html_text.splitlines()]
    records: list[dict] = []
    seen:    set        = set()

    for i, ln in enumerate(lines):
        m = BET_RE.match(ln)
        if not m:
            continue
        odds_str: str | None = None
        for j in range(i + 1, min(i + 6, len(lines))):
            cand = lines[j]
            if not cand:
                continue
            if ODDS_RE.match(cand):
                odds_str = cand
            break
        if odds_str is None:
            continue
        try:
            amer = int(odds_str)
        except ValueError:
            continue
        team      = m.group("team").strip()
        direction = m.group("dir").lower()
        line_val  = float(m.group("line"))
        if not (1.0 <= line_val <= 20.0) or len(team) < 2 or len(team) > 55:
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
            "market_type":   "REGULAR_SEASON_WINS_DOM",
            "book":          "FanDuel",
        })
    return records


async def scrape_fanduel_win_totals() -> list[dict]:
    """Navigate to each FD win-totals page, intercept the content-managed-page
    response, and return parsed records.

    Each sport gets its OWN fresh browser context so that a PerimeterX block
    on one page cannot carry over and flag the next page's session.
    Rotating user-agents reduce the chance of persistent fingerprinting.
    """
    import random
    from playwright.async_api import async_playwright

    # Windows + Chrome 127/126 pool — more representative of a real US desktop user.
    # PerimeterX is less suspicious of Chrome/127 Win10 than Mac/Safari or older builds.
    _UA_POOL = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    ]

    captured:       dict[str, dict]  = {}
    dom_fallback:   list[dict]       = []   # records from DOM when API is CAPTCHA'd

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM_PATH,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                # Critical: removes the Automation flag that PerimeterX detects
                "--disable-blink-features=AutomationControlled",
                "--window-size=1440,900",
            ],
        )

        for sport, url in FD_WIN_TOTAL_PAGES:
            # Fresh isolated context per sport — no shared cookies/fingerprint
            ctx_kwargs = _fresh_context_kwargs()
            ua = random.choice(_UA_POOL)
            ctx_kwargs["user_agent"] = ua
            # Match sec-ch-ua to the chosen Chrome version
            _chrome_ver = "127"
            if "Chrome/126" in ua:
                _chrome_ver = "126"
            elif "Chrome/125" in ua:
                _chrome_ver = "125"
            _is_mac = "Macintosh" in ua or "Mac OS" in ua
            _sec_ch_ua = (
                f'"Not)A;Brand";v="99", "Google Chrome";v="{_chrome_ver}", "Chromium";v="{_chrome_ver}"'
                if "Chrome" in ua else
                '"Not A;Brand";v="99"'
            )
            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            await page.set_extra_http_headers({
                "sec-ch-ua":          _sec_ch_ua,
                "sec-ch-ua-mobile":   "?0",
                "sec-ch-ua-platform": '"macOS"' if _is_mac else '"Windows"',
                "sec-fetch-dest":     "document",
                "sec-fetch-mode":     "navigate",
                "sec-fetch-site":     "none",
                "sec-fetch-user":     "?1",
                "upgrade-insecure-requests": "1",
            })

            all_urls: list[str] = []

            async def _on_response(r, _sport=sport):
                all_urls.append(r.url)
                if "content-managed-page" in r.url and r.status == 200:
                    body = await r.body()
                    try:
                        captured[_sport] = json.loads(body)
                        logger.info(
                            "[FD] Captured %s content page: %d bytes", _sport, len(body)
                        )
                    except json.JSONDecodeError:
                        logger.warning("[FD] Could not parse content page JSON for %s", _sport)

            page.on("response", _on_response)

            try:
                # Random pre-navigation pause — looks more human to PerimeterX
                await asyncio.sleep(random.uniform(1.5, 4.0))
                await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
                # Simulate human: small mouse movement after load, then wait
                await page.mouse.move(
                    random.randint(300, 900),
                    random.randint(200, 600),
                )
                await page.wait_for_timeout(random.randint(12_000, 18_000))
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("[FD] Navigation error for %s: %s", sport, exc)
            finally:
                if sport not in captured:
                    api_urls = [u for u in all_urls if "fanduel" in u.lower() or "api" in u.lower()]
                    logger.warning(
                        "[FD] %s: content-managed-page NOT found. API URLs seen (%d):\n%s",
                        sport, len(api_urls),
                        "\n".join(f"  {u}" for u in api_urls[:20]),
                    )
                    # ── DOM fallback: parse "Team Over X.X Wins\nODDS" directly ──────
                    try:
                        dom_text: str = await page.evaluate(
                            "() => { const m = document.querySelector('main') || document.body; return m ? m.innerText : ''; }"
                        )
                        if dom_text and ("Over" in dom_text or "Under" in dom_text):
                            dom_records = _parse_fd_dom(dom_text, sport)
                            if dom_records:
                                logger.info("[FD] %s: DOM fallback → %d records", sport, len(dom_records))
                                dom_fallback.extend(dom_records)
                            else:
                                sample = "\n".join(dom_text.splitlines()[:50])
                                logger.warning("[FD] %s: DOM fallback returned 0. Sample:\n%s", sport, sample)
                    except Exception as _de:
                        logger.warning("[FD] %s: DOM fallback error: %s", sport, _de)

                await page.close()
                await context.close()

        await browser.close()

    # Parse each captured API page, then merge any DOM fallback records
    results: list[dict] = []
    for sport, data in captured.items():
        parsed = parse_fd_content_page(data, sport)
        logger.info("[FD] Parsed %d entries for %s", len(parsed), sport)
        results.extend(parsed)

    # Deduplicate DOM fallback against API results (API wins if both present for same key)
    api_keys = {(r["team"].lower(), r["line"], r["direction"]) for r in results}
    dom_new  = [r for r in dom_fallback if (r["team"].lower(), r["line"], r["direction"]) not in api_keys]
    if dom_new:
        logger.info("[FD] Merging %d DOM fallback records (API had %d)", len(dom_new), len(results))
        results.extend(dom_new)

    # ── NFL search-page fallback ──────────────────────────────────────────────
    # If NFL still has no records (tab gets CAPTCHA'd), try the search page which
    # is served by a different FD endpoint and rarely triggers PerimeterX.
    nfl_covered = {r["team"].lower() for r in results if r.get("sport") == "NFL"}
    if not nfl_covered:
        logger.info("[FD] NFL: 0 records from tab — trying search-page fallback")
        search_records = await _scrape_fd_nfl_via_search()
        if search_records:
            logger.info("[FD] NFL search fallback → %d records", len(search_records))
            results.extend(search_records)
        else:
            logger.warning("[FD] NFL search fallback also returned 0 records")

    logger.info("[FD] Total entries: %d across %s", len(results), list(captured) + (["DOM"] if dom_new else []))
    return results


async def _scrape_fd_nfl_via_search() -> list[dict]:
    """Try to get FD NFL win totals via the /search page.

    The NFL Win Totals *tab* (`/navigation/nfl?tab=win-totals`) is blocked by
    PerimeterX on every run from this server.  The search page is a different
    product surface and is not subject to the same bot-detection rules.

    Strategy:
      1. Navigate to https://sportsbook.fanduel.com/search?tab=american-football
      2. Wait for page to load, then type "regular season wins" into the search box.
      3. Intercept any content-managed-page API response (same format as tab scrape).
      4. Fallback: DOM-scrape the rendered results using _parse_fd_dom().
    """
    import random as _random
    from playwright.async_api import async_playwright

    _UA_POOL = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    ]

    captured:  dict = {}
    dom_text:  str  = ""
    search_url = "https://sportsbook.fanduel.com/search?tab=american-football"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM_PATH,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1440,900",
            ],
        )
        ua = _random.choice(_UA_POOL)
        context = await browser.new_context(
            user_agent=ua,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/Chicago",
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        async def _on_resp(r):
            if "content-managed-page" in r.url and r.status == 200:
                try:
                    body = await r.body()
                    captured["data"] = json.loads(body)
                    logger.info("[FD] Search: captured content-managed-page (%d bytes)", len(body))
                except Exception:
                    pass

        page.on("response", _on_resp)

        try:
            await asyncio.sleep(_random.uniform(1.0, 3.0))
            await page.goto(search_url, timeout=45_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3_000)

            # Find the search input and type the query
            search_input = await page.query_selector(
                'input[type="search"], input[placeholder*="earch" i], '
                'input[aria-label*="earch" i], [role="searchbox"], input[name="search"]'
            )
            if search_input:
                await search_input.click()
                await asyncio.sleep(0.5)
                await search_input.type("regular season wins", delay=60)
                logger.info("[FD] Search: typed query")
                # Wait for results to load
                await page.wait_for_timeout(6_000)
            else:
                logger.warning("[FD] Search: could not find search input — waiting for initial page content")
                await page.wait_for_timeout(5_000)

            # Try DOM scrape regardless of whether API was captured
            dom_text: str = await page.evaluate(
                "() => { const m = document.querySelector('main') || document.body; return m ? m.innerText : ''; }"
            )

            # Save DOM for inspection on first run
            import pathlib as _pl
            _dbg = _pl.Path("/home/runner/workspace/backend/data/fd_nfl_search_dom.txt")
            _dbg.write_text(dom_text or "", encoding="utf-8")
            logger.info("[FD] Search DOM saved (%d chars) → %s", len(dom_text or ""), _dbg)

        except Exception as exc:
            logger.warning("[FD] NFL search error: %s", exc)
        finally:
            await page.close()
            await context.close()
        await browser.close()

    # Parse: prefer API intercept, fall back to DOM
    if "data" in captured:
        records = parse_fd_content_page(captured["data"], "NFL")
        if records:
            return records

    if dom_text and ("Over" in dom_text or "Under" in dom_text):
        return _parse_fd_dom(dom_text, "NFL")

    return []


async def scrape_fanduel_outright(
    url: str,
    market_id: str,
    sport: str,
    market_type_kw: str = "WINNER",
) -> list[dict]:
    """Scrape a FanDuel outright winner page and return records.

    Same Playwright interception approach as win totals but calls
    parse_fd_outright_page() instead of parse_fd_content_page().
    """
    import random as _random
    from playwright.async_api import async_playwright
    from futures_ev_outright import parse_fd_outright_page

    _UA_POOL = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    ]

    captured: dict | None = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        ua = _random.choice(_UA_POOL)
        context = await browser.new_context(
            user_agent=ua,
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
            "sec-ch-ua-platform": '"Windows"' if "Windows" in ua else '"macOS"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
        })

        all_urls: list[str] = []

        async def _on_response(r):
            nonlocal captured
            all_urls.append(r.url)
            if "content-managed-page" in r.url and r.status == 200:
                try:
                    body = await r.body()
                    captured = json.loads(body)
                    logger.info("[FD-OUT] Captured %s content page: %d bytes", market_id, len(body))
                except json.JSONDecodeError:
                    logger.warning("[FD-OUT] Could not parse JSON for %s", market_id)

        page.on("response", _on_response)

        try:
            await asyncio.sleep(_random.uniform(1.5, 3.5))
            await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
            await page.mouse.move(_random.randint(300, 900), _random.randint(200, 500))
            await page.wait_for_timeout(_random.randint(12_000, 18_000))
        except Exception as exc:
            logger.warning("[FD-OUT] Navigation error for %s: %s", market_id, exc)
        finally:
            if captured is None:
                api_urls = [u for u in all_urls if "fanduel" in u.lower()]
                logger.warning("[FD-OUT] %s: content-managed-page NOT found. API URLs (%d):\n%s",
                               market_id, len(api_urls), "\n".join(f"  {u}" for u in api_urls[:15]))
            await page.close()
            await context.close()
        await browser.close()

    if not captured:
        return []

    records = parse_fd_outright_page(captured, sport, market_id, market_type_kw)
    logger.info("[FD-OUT] %s: %d outright records", market_id, len(records))
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rows = asyncio.run(scrape_fanduel_win_totals())
    print(f"FD win totals: {len(rows)} rows")
    for r in rows[:5]:
        print(r)
