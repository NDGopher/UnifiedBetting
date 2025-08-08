import re
import time
from typing import Dict, Any, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager


SPORTS_PATHS = [
    "#!/sport/1",  # MLB
    "#!/sport/3",  # NFL (football)
    "#!/sport/2",  # NBA
]

SPORT_LABEL = {
    "#!/sport/1": "MLB",
    "#!/sport/2": "NBA",
    "#!/sport/3": "NFL",
}


def _build_driver(user_data_dir: Optional[str], profile_dir: Optional[str], headless: bool = True) -> webdriver.Chrome:
    chrome_options = Options()
    if user_data_dir:
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    if profile_dir:
        chrome_options.add_argument(f"--profile-directory={profile_dir}")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--remote-allow-origins=*")
    chrome_options.add_argument("--disable-gpu")
    if headless:
        chrome_options.add_argument("--headless=new")
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def _extract_american_pair(text_block: str) -> Optional[List[str]]:
    # Heuristic: first two American odds tokens like +110, -120. Filter obviously bad values.
    raw = re.findall(r"[+\-\u2212\u2013]\d{2,3}", text_block)
    odds: List[str] = []
    for tok in raw:
        try:
            tok_norm = tok.replace("\u2212", "-").replace("\u2013", "-")
            val = int(tok_norm)
            if -500 <= val <= 500:
                odds.append(tok_norm)
        except Exception:
            continue
        if len(odds) == 2:
            break
    return odds if len(odds) == 2 else None


_DISALLOWED_TOKENS = {
    "baseball", "basketball", "football", "collapse", "expand", "all", "showing:",
    "filters", "events", "odds", "market", "today", "favorites", "parlay", "live",
}


def _is_probable_team_name(name: str) -> bool:
    n = (name or "").strip().lower()
    if not n or len(n) < 3:
        return False
    if any(tok in n for tok in _DISALLOWED_TOKENS):
        return False
    # Avoid labels with punctuation/colon heavy
    if ":" in n or "/" in n or n.startswith("+") or n.startswith("-"):
        return False
    # Require at least one alpha
    return any(c.isalpha() for c in n)


def scrape_plive_odds(
    base_url: str = "https://plive.becoms.co/live/",
    sports_paths: Optional[List[str]] = None,
    user_data_dir: Optional[str] = None,
    profile_dir: Optional[str] = None,
    headless: bool = True,
    timeout: int = 25,
) -> List[Dict[str, Any]]:
    paths = sports_paths or SPORTS_PATHS
    driver = _build_driver(user_data_dir, profile_dir, headless=headless)
    wait = WebDriverWait(driver, timeout)
    events: List[Dict[str, Any]] = []
    try:
        for path in paths:
            driver.get(base_url + path)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
            except Exception:
                continue
            # Nudge virtualization
            try:
                driver.execute_script('window.scrollTo(0, 0)')
                driver.execute_script('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(0.6)
                driver.execute_script('window.scrollTo(0, 0)')
            except Exception:
                pass
            # Generic rows: capture containers with team names and odds
            rows = driver.find_elements(By.CSS_SELECTOR, '[class*="event"], [class*="match"], li, .row, [class*="game"]')
            print(f"[PLive] {path} candidate rows: {len(rows)}")
            for r in rows:
                try:
                    txt = (r.get_attribute('innerText') or r.text or "").strip()
                except StaleElementReferenceException:
                    continue
                except Exception:
                    # stale element; skip
                    continue
                if not txt or len(txt) < 5:
                    continue
                lines = [t.strip() for t in txt.split("\n") if t.strip()]
                if len(lines) < 2:
                    continue
                home, away = lines[0], lines[1]
                if not (_is_probable_team_name(home) and _is_probable_team_name(away)):
                    continue
                pair = _extract_american_pair(txt)
                if not pair:
                    # Try scanning child spans for odds tokens
                    try:
                        spans = r.find_elements(By.CSS_SELECTOR, "span, div")
                        texts = []
                        for s in spans:
                            try:
                                t = s.get_attribute('innerText') or s.text
                                if t:
                                    texts.append(t)
                            except StaleElementReferenceException:
                                continue
                        span_text = " ".join(texts)
                        pair = _extract_american_pair(span_text)
                    except Exception:
                        pass
                if not pair:
                    # If we still don't have a pair, skip row — we only want priced events
                    continue
                # Determine market heuristically: look for spread/total markers
                market = "moneyline"
                txt_lower = txt.lower()
                if re.search(r"\b[-+]\d+\.5\b|\b[-+]\d+\b", txt_lower) and re.search(r"spread|handicap", txt_lower, re.I):
                    market = "spread"
                elif re.search(r"\b\d+\.5\b|\b\d+\b", txt_lower) and re.search(r"total|over|under|o/u", txt_lower, re.I):
                    market = "total"
                books = {}
                books["betbck"] = {"home": pair[0], "away": pair[1]}
                events.append({
                    "sport": SPORT_LABEL.get(path, "unknown"),
                    "market": market,
                    "home": home,
                    "away": away,
                    "books": books,
                })
            print(f"[PLive] {path} parsed events so far: {len(events)}")
        # De-duplicate consecutive identical events by key
        seen = set()
        unique: List[Dict[str, Any]] = []
        for e in events:
            key = (e.get("home"," ").lower(), e.get("away"," ").lower(), e.get("market"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(e)
        return unique
    finally:
        try:
            driver.quit()
        except Exception:
            pass

