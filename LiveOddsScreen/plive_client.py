import re
import time
import json
from typing import Dict, Any, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


SPORTS_PATHS = [
    '#!/sport/1',  # baseball
    '#!/sport/2',  # basketball
    '#!/sport/3',  # football
]


def _build_driver(user_data_dir: Optional[str], profile_dir: Optional[str], headless: bool = True) -> webdriver.Chrome:
    chrome_options = Options()
    if user_data_dir:
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    if profile_dir:
        chrome_options.add_argument(f"--profile-directory={profile_dir}")
    chrome_options.add_argument("--disable-infobars")
    if headless:
        chrome_options.add_argument("--headless=new")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def fetch_plive_snapshot(base_url: str = 'https://plive.becoms.co/live/',
                         sports_paths: Optional[List[str]] = None,
                         user_data_dir: Optional[str] = None,
                         profile_dir: Optional[str] = None,
                         headless: bool = True,
                         timeout: int = 25) -> Dict[str, Any]:
    """Navigate PLive live site and return a minimal snapshot per sport.

    This DOM approach avoids reverse-engineering the internal WebSocket payload for now.
    We keep it best-effort and resilient to minor markup changes.
    """
    paths = sports_paths or SPORTS_PATHS
    driver = _build_driver(user_data_dir, profile_dir, headless=headless)
    wait = WebDriverWait(driver, timeout)
    results: Dict[str, Any] = {}
    try:
        for path in paths:
            driver.get(base_url + path)
            # Wait basic container
            try:
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'body')))
            except Exception:
                continue
            # Heuristic: capture visible event rows texts to aid matching
            rows = driver.find_elements(By.CSS_SELECTOR, '[class*="event"], [class*="row"], [class*="match"]')
            snapshot: List[Dict[str, Any]] = []
            for r in rows[:150]:
                txt = r.text.strip()
                if len(txt) < 5:
                    continue
                # Try to split team lines
                lines = [t for t in txt.split('\n') if t.strip()]
                if len(lines) >= 2:
                    snapshot.append({"raw": lines[:6]})
            results[path] = snapshot
        return results
    finally:
        driver.quit()

