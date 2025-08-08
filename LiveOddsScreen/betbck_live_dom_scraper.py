import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

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
class SiteSelectors:
    iframe_selector: str
    event_row_selector: str
    home_team_selector: str
    away_team_selector: str
    market_container_selector: Optional[str] = None
    price_selector: Optional[str] = None


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


def scrape_betbck_live(
    live_url: str,
    selectors: SiteSelectors,
    user_data_dir: Optional[str] = None,
    profile_dir: Optional[str] = None,
    timeout: int = 30,
    headless: bool = True,
) -> List[Dict[str, Any]]:
    # Robust driver bring-up similar to PTO scraper
    driver = None
    last_error = None
    for attempt in [
        ("chrome_profile_headless", True, True),
        ("chrome_profile_visible", False, True),
        ("chrome_no_profile_visible", False, False),
        ("edge_visible", False, False),
        ("firefox_visible", False, False),
    ]:
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
        print(f"[BetBCK] Could not start any browser driver. Last error: {last_error}")
        return []
    wait = WebDriverWait(driver, timeout)
    try:
        driver.get(live_url)
        # Try to switch to PLive iframe; if missing, navigate to PLive directly
        rows = []
        try:
            iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selectors.iframe_selector)))
            driver.switch_to.frame(iframe)
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selectors.event_row_selector)))
            rows = driver.find_elements(By.CSS_SELECTOR, selectors.event_row_selector)
        except Exception:
            try:
                # Attempt any iframe with plive in src
                all_ifr = driver.find_elements(By.TAG_NAME, 'iframe')
                target = None
                for f in all_ifr:
                    src = f.get_attribute('src') or ''
                    if 'plive.becoms.co' in src:
                        target = f
                        break
                if target:
                    driver.switch_to.frame(target)
            except Exception:
                pass
            # If still no rows, go straight to PLive public URL
            if not rows:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
                driver.get('https://plive.becoms.co/live/')
                # Generic fallback row selectors
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'body')))
                rows = driver.find_elements(By.CSS_SELECTOR, '[class*=event], [class*=match], li, .row')
        events: List[Dict[str, Any]] = []
        for row in rows:
            try:
                home_text = row.find_element(By.CSS_SELECTOR, selectors.home_team_selector).text.strip()
                away_text = row.find_element(By.CSS_SELECTOR, selectors.away_team_selector).text.strip()
            except Exception:
                # Generic text fallback: use first two non-empty lines as teams
                try:
                    txt = row.text.strip()
                    parts = [p for p in (txt.split('\n')) if p.strip()]
                    if len(parts) >= 2:
                        home_text, away_text = parts[0], parts[1]
                    else:
                        continue
                except Exception:
                    continue

            markets: List[Dict[str, Any]] = []
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

            events.append({
                "home": home_text,
                "away": away_text,
                "markets": markets,
            })
        return events
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass

