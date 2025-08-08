import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Iterable

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.firefox.service import Service as GeckoService
from webdriver_manager.firefox import GeckoDriverManager


@dataclass
class PTOSelectors:
    event_row_selector: str
    home_team_selector: str
    away_team_selector: str
    market_container_selector: Optional[str] = None
    price_selector: Optional[str] = None
    # Optional, when team names are inside two spans with class like MuiTypography-odds; if set, we will prefer title attribute
    team_title_selector: Optional[str] = None
    # Selector to capture all book cells in a row
    book_cell_selector: Optional[str] = None
    # Selector for the image/icon that carries the book name via alt
    book_icon_selector: Optional[str] = None
    # Selector for odds text spans within a book cell
    book_odds_value_selector: Optional[str] = None
    # Live indicator selector (if present in row -> consider live)
    live_indicator_selector: Optional[str] = '[data-testid="SensorsIcon"], .css-ctyr61'


def _build_driver(user_data_dir: Optional[str], profile_dir: Optional[str], headless: bool = True) -> webdriver.Chrome:
    chrome_options = Options()
    if user_data_dir:
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    if profile_dir:
        chrome_options.add_argument(f"--profile-directory={profile_dir}")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--remote-allow-origins=*")
    chrome_options.add_argument("--disable-gpu")
    if headless:
        chrome_options.add_argument("--headless=new")
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def scrape_pto_live(
    pto_url: str,
    selectors: PTOSelectors,
    user_data_dir: Optional[str] = None,
    profile_dir: Optional[str] = None,
    timeout: int = 30,
    headless: bool = True,
    allowed_books: Optional[Iterable[str]] = None,
    live_only: bool = True,
) -> List[Dict[str, Any]]:
    # Robust driver bring-up with multiple fallbacks. Honor headless preference.
    driver = None
    last_error = None
    attempts = []
    if headless:
        attempts = [
            ("chrome_profile_headless", True, True),
            ("chrome_no_profile_headless", True, False),
            ("edge_headless", True, False),
            ("firefox_headless", True, False),
        ]
    else:
        attempts = [
            ("chrome_profile_visible", False, True),
            ("chrome_no_profile_visible", False, False),
            ("edge_visible", False, False),
            ("firefox_visible", False, False),
        ]
    for attempt in attempts:
        name, headless_try, use_profile = attempt
        try:
            if name.startswith("chrome"):
                cud = user_data_dir if use_profile else None
                cpd = profile_dir if use_profile else None
                driver = _build_driver(cud, cpd, headless=headless_try)
                break
            if name.startswith("edge"):
                edge_opts = webdriver.EdgeOptions()
                if headless_try:
                    edge_opts.add_argument("--headless=new")
                edge_opts.add_argument("--disable-gpu")
                edge_opts.add_argument("--remote-allow-origins=*")
                driver = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()), options=edge_opts)
                break
            if name.startswith("firefox"):
                ff_opts = webdriver.FirefoxOptions()
                if headless_try:
                    ff_opts.add_argument("--headless")
                driver = webdriver.Firefox(service=GeckoService(GeckoDriverManager().install()), options=ff_opts)
                break
        except Exception as e:
            last_error = e
            driver = None
            continue
    if driver is None:
        print(f"[PTO] Could not start any browser driver. Last error: {last_error}")
        return []
    wait = WebDriverWait(driver, timeout)
    try:
        driver.get(pto_url)
        try:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selectors.event_row_selector)))
            rows = driver.find_elements(By.CSS_SELECTOR, selectors.event_row_selector)
        except Exception:
            # Fallback to a generic row heuristic
            rows = driver.find_elements(By.CSS_SELECTOR, '[virtualrowstart], .MuiBox-root')
        # Trigger virtualization to render book columns
        try:
            driver.execute_script('window.scrollTo(0, 0)')
            driver.execute_script('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(0.2)
            driver.execute_script('window.scrollTo(0, 0)')
        except Exception:
            pass
        events: List[Dict[str, Any]] = []
        for row in rows:
            # Ensure row is in view so its children render
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", row)
                time.sleep(0.05)
            except Exception:
                pass
            # Filter for live rows if required
            if live_only and selectors.live_indicator_selector:
                try:
                    _live = row.find_elements(By.CSS_SELECTOR, selectors.live_indicator_selector)
                    if not _live:
                        continue
                except Exception:
                    # If selector fails, keep row to avoid accidentally dropping all
                    pass
            try:
                # Prefer explicit selectors if provided, otherwise try to use two title-bearing spans
                if selectors.home_team_selector and selectors.away_team_selector:
                    home_text = row.find_element(By.CSS_SELECTOR, selectors.home_team_selector).text.strip()
                    away_text = row.find_element(By.CSS_SELECTOR, selectors.away_team_selector).text.strip()
                else:
                    titles = row.find_elements(By.CSS_SELECTOR, selectors.team_title_selector or 'span[title]')
                    # Fallback to visible text if title missing
                    if len(titles) >= 2:
                        h_title = titles[0].get_attribute('title') or titles[0].text
                        a_title = titles[1].get_attribute('title') or titles[1].text
                        home_text = (h_title or '').strip()
                        away_text = (a_title or '').strip()
                    else:
                        # Skip rows we cannot parse team names from
                        continue
            except Exception:
                continue

            markets: List[Dict[str, Any]] = []
            books: Dict[str, Dict[str, Optional[str]]] = {}
            if selectors.market_container_selector and selectors.price_selector:
                try:
                    containers = row.find_elements(By.CSS_SELECTOR, selectors.market_container_selector)
                    for c in containers:
                        try:
                            price_el = c.find_element(By.CSS_SELECTOR, selectors.price_selector)
                            price_text = price_el.text.strip()
                            markets.append({"label": c.text.strip(), "price": price_text})
                        except Exception:
                            continue
                except Exception:
                    pass

            # Extract per-book odds if configured
            if selectors.book_cell_selector and selectors.book_icon_selector and selectors.book_odds_value_selector:
                try:
                    book_cells = row.find_elements(By.CSS_SELECTOR, selectors.book_cell_selector)
                    for cell in book_cells:
                        try:
                            icon = cell.find_element(By.CSS_SELECTOR, selectors.book_icon_selector)
                            book_name = (icon.get_attribute('alt') or icon.get_attribute('aria-label') or '').strip()
                            if not book_name:
                                # try parent div aria-label
                                parent_label = cell.get_attribute('aria-label') or ''
                                book_name = parent_label.strip()
                            if not book_name:
                                continue
                            # Canonicalize and filter
                            canonical = canonicalize_book_name(book_name)
                            if allowed_books is not None and canonical not in set(map(canonicalize_book_name, allowed_books)):
                                continue
                            vals = cell.find_elements(By.CSS_SELECTOR, selectors.book_odds_value_selector)
                            odds_vals = [v.text.strip() for v in vals if v.text.strip()]
                            # Map first to home, second to away if present
                            home_val = odds_vals[0] if len(odds_vals) >= 1 else None
                            away_val = odds_vals[1] if len(odds_vals) >= 2 else None
                            books[canonical] = {"home": home_val, "away": away_val}
                        except Exception:
                            continue
                except Exception:
                    pass
            else:
                # Minimal fallback: try to collect any two odds in the row as a generic PTO aggregate
                try:
                    vals = row.find_elements(By.CSS_SELECTOR, 'span[class*="oddsRobotoMono"], span[class*="odds"]')
                    if len(vals) >= 2:
                        books['pto'] = {"home": vals[0].text.strip(), "away": vals[1].text.strip()}
                except Exception:
                    pass

            # Generic pass: if books still empty, walk all icons and pull nearby odds
            if not books:
                try:
                    icons = row.find_elements(By.CSS_SELECTOR, 'img[alt]')
                    for ic in icons:
                        try:
                            alt = (ic.get_attribute('alt') or '').strip()
                            if not alt:
                                continue
                            canonical = canonicalize_book_name(alt)
                            container = ic.find_element(By.XPATH, './ancestor::div[contains(@class,"MuiBox-root")][1]')
                            spans = container.find_elements(By.CSS_SELECTOR, 'span[class*="oddsRobotoMono"], span[class*="odds"]')
                            odds_vals = [s.text.strip() for s in spans if s.text.strip()]
                            if odds_vals:
                                home_val = odds_vals[0] if len(odds_vals) >= 1 else None
                                away_val = odds_vals[1] if len(odds_vals) >= 2 else None
                                if home_val or away_val:
                                    books[canonical] = {"home": home_val, "away": away_val}
                        except Exception:
                            continue
                except Exception:
                    pass

            # If still nothing, try a shallow scrape for the PTO aggregate price (fallback only)
            if not books:
                try:
                    shallow = row.find_elements(By.CSS_SELECTOR, '.MuiTypography-oddsRobotoMono')
                    vals = [v.text.strip() for v in shallow if v.text.strip()]
                    if len(vals) >= 2:
                        books['pto'] = {"home": vals[0], "away": vals[1]}
                except Exception:
                    pass

            # Determine market label heuristically from row text
            market_label = "moneyline"
            try:
                row_text = row.text.lower()
                if "spread" in row_text:
                    market_label = "spread"
                elif "total" in row_text or "o/u" in row_text:
                    market_label = "total"
            except Exception:
                pass

            events.append({
                "home": home_text,
                "away": away_text,
                "markets": markets,
                "market": market_label,
                "books": books,
            })
        return events
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass


def canonicalize_book_name(raw: str) -> str:
    name = (raw or '').lower().strip()
    mapping = {
        'fanduel': 'fanduel',
        'fan duel': 'fanduel',
        'betmgm': 'betmgm',
        'mgm': 'betmgm',
        'draftkings': 'draftkings',
        'dk': 'draftkings',
        'caesars': 'caesars',
        'espnbet': 'espnbet',
        'espn bet': 'espnbet',
        'pinnacle': 'pinnacle',
        'betonline': 'betonline',
        'bet online': 'betonline',
        'betrivers': 'betrivers',
        'bet rivers': 'betrivers',
    }
    # handle variants like 'Betway (US)' etc. keep original for non-targets
    for key, val in mapping.items():
        if key in name:
            return val
    return name.replace(' ', '_')

