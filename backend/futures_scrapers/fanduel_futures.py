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


async def scrape_fanduel_win_totals() -> list[dict]:
    """Navigate to each FD win-totals page, intercept the content-managed-page
    response, and return parsed records.

    Each sport gets its own fresh browser context to avoid PerimeterX blocking.
    """
    from playwright.async_api import async_playwright

    captured: dict[str, dict] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        for sport, url in FD_WIN_TOTAL_PAGES:
            context = await browser.new_context(**_fresh_context_kwargs())
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            all_urls: list[str] = []

            async def _log_response(r):
                url_r = r.url
                all_urls.append(url_r)
                if "content-managed-page" in url_r and r.status == 200:
                    body = await r.body()
                    try:
                        captured[sport] = json.loads(body)
                        logger.info("[FD] Captured %s content page: %d bytes", sport, len(body))
                    except json.JSONDecodeError:
                        logger.warning("[FD] Could not parse content page JSON for %s", sport)

            page.on("response", _log_response)

            try:
                await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
                # Wait for all XHRs to fire — 15s gives FD plenty of time
                await page.wait_for_timeout(15_000)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("[FD] Navigation error for %s: %s", sport, exc)
            finally:
                # Log all response URLs so we can identify the correct API endpoint
                api_urls = [u for u in all_urls if "fanduel" in u.lower() or "api" in u.lower()]
                if sport not in captured:
                    logger.warning(
                        "[FD] %s: content-managed-page NOT found. API URLs seen (%d):\n%s",
                        sport,
                        len(api_urls),
                        "\n".join(f"  {u}" for u in api_urls[:30]),
                    )
                await page.close()
                await context.close()

        await browser.close()

    # Parse each captured page
    results: list[dict] = []
    for sport, data in captured.items():
        parsed = parse_fd_content_page(data, sport)
        logger.info("[FD] Parsed %d entries for %s", len(parsed), sport)
        results.extend(parsed)

    logger.info("[FD] Total entries: %d across %s", len(results), list(captured))
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rows = asyncio.run(scrape_fanduel_win_totals())
    print(f"FD win totals: {len(rows)} rows")
    for r in rows[:5]:
        print(r)
