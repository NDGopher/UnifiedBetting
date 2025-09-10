import time
import re
import random
import asyncio
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import logging
from websocket_manager import manager

logger = logging.getLogger(__name__)

class PTOScraper:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.driver = None
        self.live_props = {}  # prop_id -> {"prop": prop, "created_at": dt, "updated_at": dt}
        self.last_refresh = time.time()
        self.refresh_interval = random.uniform(2 * 60 * 60, 2.5 * 60 * 60)  # 2 to 2.5 hours
        self.is_running = False
        self.pto_url = config.get("pto_url", "https://picktheodds.app/en/expectedvalue")
        # Use config values for Chrome profile
        self.chrome_user_data_dir = config.get("chrome_user_data_dir", "C:/Users/steph/OneDrive/Desktop/ProdProjects/PropBuilderEV/pto_chrome_profile")
        self.chrome_profile_dir = config.get("chrome_profile_dir", "Profile 1")  # Default to Profile 1
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 30)
        self.scraping_interval = config.get("scraping_interval_seconds", 2)  # 2-3 seconds like original
        self.min_ev_threshold = config.get("min_ev_threshold", 3.0)  # Show only 3%+ EV by default
        self.telegram_enabled = config.get("telegram_enabled", True)
        self.dry_run = False  # Enable Telegram alerts now that parsing is fixed
        
        # Initialize Telegram alerts if enabled
        if self.telegram_enabled:
            try:
                from telegram_alerts import TelegramAlerts
                self.telegram = TelegramAlerts()
                logger.info("Telegram alerts initialized")
            except ImportError:
                logger.warning("[WARNING] Telegram alerts module not found, disabling")
                self.telegram_enabled = False
                self.telegram = None
        else:
            self.telegram = None
        
    def get_driver_fallback(self):
        """Fallback driver creation without profile directory"""
        try:
            logger.info("[DEBUG] Trying fallback driver creation without profile...")
            
            options = Options()
            
            # Anti-detection flags
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--start-maximized')
            options.add_argument('--disable-gpu')
            
            logger.info("[DEBUG] Launching Chrome driver (fallback mode)...")
            driver = webdriver.Chrome(options=options)
            
            # Remove the "Chrome is being controlled by automated software" message
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            logger.info("Chrome driver created successfully (fallback mode)")
            return driver
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to create Chrome driver (fallback): {e}")
            raise

    def get_driver(self):
        """Initialize Chrome driver with PTO profile and anti-detection flags (old project logic)"""
        try:
            # Kill any existing Chrome processes that might be using the profile
            self.kill_chrome_processes()
            
            logger.info(f"[DEBUG] Creating Chrome driver with profile: {self.chrome_user_data_dir}/{self.chrome_profile_dir}")
            
            options = Options()
            
            # Use the profile configuration from config.json
            logger.info(f"[DEBUG] Using Chrome profile - user-data-dir: {self.chrome_user_data_dir}")
            logger.info(f"[DEBUG] Using Chrome profile - profile-directory: {self.chrome_profile_dir}")
            
            # Add profile arguments
            options.add_argument(f'--user-data-dir={self.chrome_user_data_dir}')
            options.add_argument(f'--profile-directory={self.chrome_profile_dir}')
            
            # Anti-detection flags
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--start-maximized')
            options.add_argument('--disable-gpu')
            
            # DO NOT use headless mode - we want to see the purple window
            # options.add_argument('--headless')  # COMMENTED OUT
            
            logger.info("[DEBUG] Launching Chrome driver...")
            driver = webdriver.Chrome(options=options)
            
            # Remove the "Chrome is being controlled by automated software" message
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            logger.info("Chrome driver created successfully")
            return driver
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to create Chrome driver: {e}")
            logger.error(f"[DEBUG] Profile path: {self.chrome_user_data_dir}")
            logger.error(f"[DEBUG] Profile name: {self.chrome_profile_dir}")
            
            # Try fallback method without profile
            logger.info("[RETRY] Trying fallback driver creation...")
            return self.get_driver_fallback()

    def kill_chrome_processes(self):
        """Kill any existing Chrome processes that might be using the profile"""
        try:
            import psutil
            killed_count = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_name = proc.info['name']
                    if proc_name and 'chrome' in proc_name.lower():
                        logger.info(f"Killing Chrome process: {proc.info['pid']}")
                        proc.kill()
                        killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if killed_count > 0:
                logger.info(f"Killed {killed_count} Chrome processes")
                time.sleep(2)  # Wait for processes to fully terminate
            else:
                logger.info("ℹ️ No Chrome processes found to kill")
                
        except Exception as e:
            logger.warning(f"Warning: Could not kill Chrome processes: {e}")

    def wait_for_cloudflare(self, driver, timeout=60):
        """Wait for Cloudflare challenge to complete"""
        logger.info("🔒 Waiting for Cloudflare challenge...")
        
        try:
            # Wait for Cloudflare challenge to appear and disappear
            wait = WebDriverWait(driver, timeout)
            
            # Check for Cloudflare challenge page
            if "cloudflare" in driver.page_source.lower():
                logger.info("[WAIT] Cloudflare challenge detected, waiting...")
                
                # Wait for the page to load completely
                wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
                
                # Wait a bit more for any JavaScript challenges
                time.sleep(5)
                
                # Check if we're still on Cloudflare
                if "cloudflare" in driver.page_source.lower():
                    logger.warning("[WARNING] Still on Cloudflare page, waiting longer...")
                    time.sleep(10)
            
            # Check if we're redirected to the target site
            if "picktheodds" in driver.current_url.lower():
                logger.info("Successfully passed Cloudflare challenge")
                return True
            else:
                logger.warning(f"[WARNING] Unexpected URL after Cloudflare: {driver.current_url}")
                return False
                
        except TimeoutException:
            logger.error("[ERROR] Timeout waiting for Cloudflare challenge")
            return False
        except Exception as e:
            logger.error(f"[ERROR] Error during Cloudflare wait: {e}")
            return False

    def check_login_status(self, driver):
        """Check if we're logged in to PTO by looking for multiple indicators"""
        try:
            # Method 1: Look for the 'S' button in the top right as definitive login indicator
            try:
                # Updated XPath to look for 'S' in span element, not p element
                s_button = driver.find_element(By.XPATH, "//button[contains(@class, 'MuiButton-root') and .//span[text()='S']]")
                if s_button:
                    logger.info("'S' button found in top right, assuming logged in")
                    return True
            except Exception:
                pass
            
            # Method 2: Look for prop data elements that indicate we're logged in
            try:
                # Look for prop cards or data elements
                prop_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'MuiCard-root') or contains(@class, 'prop-card')]")
                if len(prop_elements) > 0:
                    logger.info("Prop data elements found, assuming logged in")
                    return True
            except Exception:
                pass
            
            # Method 3: Check for login/logout indicators in page source
            try:
                page_source = driver.page_source.lower()
                login_indicators = ["sign in", "log in", "login", "signin", "please log in"]
                logout_indicators = ["logout", "sign out", "profile", "account", "settings"]
                
                has_login = any(indicator in page_source for indicator in login_indicators)
                has_logout = any(indicator in page_source for indicator in logout_indicators)
                
                if has_logout and not has_login:
                    logger.info("Appears to be logged in (logout/profile found)")
                    return True
                elif has_login and not has_logout:
                    logger.warning("[WARNING] Appears to be logged out")
                    return False
                else:
                    logger.info("[UNKNOWN] Login status unclear, assuming logged out")
                    return False
            except Exception as e:
                logger.warning(f"[WARNING] Error checking page source for login indicators: {e}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error checking login status: {e}")
            return False

    def handle_login_required(self, driver):
        """Handle login requirement - waits indefinitely for manual login"""
        logger.warning("[LOGIN] Login required. Please log in manually.")
        logger.info("[INSTRUCTIONS] Instructions:")
        logger.info("1. Log in to your PTO account")
        logger.info("2. Navigate to the Prop Builder tab")
        logger.info("3. Verify you can see prop data")
        logger.info("4. The scraper will continue automatically")
        logger.info("[NOTE] No timeout - scraper will wait indefinitely for login")
        
        # Wait indefinitely for user to log in (no timeout)
        check_interval = 30  # Check every 30 seconds
        
        while self.is_running:  # Only stop if scraper is stopped externally
            try:
                # Check if we're still on the PTO site
                current_url = driver.current_url
                if "picktheodds.app" not in current_url:
                    logger.warning(f"[LOGIN] Browser navigated away from PTO: {current_url}")
                    logger.info("[LOGIN] Please navigate back to https://picktheodds.app")
                
                if self.check_login_status(driver):
                    logger.info("Login detected, continuing...")
                    return True
                
                # Check every 30 seconds
                time.sleep(check_interval)
                logger.info(f"[LOGIN] Still waiting for login... (checking every {check_interval}s)")
                
            except Exception as e:
                logger.warning(f"[LOGIN] Error checking login status: {e}")
                time.sleep(check_interval)
        
        logger.info("[LOGIN] Scraper stopped while waiting for login")
        return False

    def parse_prop_card_text(self, card_text: str) -> Optional[Dict[str, Any]]:
        """Parse prop card text and extract structured data"""
        lines = [line.strip() for line in card_text.split('\n') if line.strip()]
        logger.debug(f"[PTO DEBUG] Raw card lines: {lines}")
        logger.info(f"[PTO DEBUG] Raw card lines for debugging: {lines}")
        if not lines or len(lines) < 6:
            return None
        sport = lines[0]
        if 'mlb' in sport.lower():
            # MLB: Find lines that look like team names, skipping odds, dollar values, and pitcher names
            team_lines = []
            for l in lines[1:]:
                # Stop if we hit a time or prop line
                if (':' in l and ('am' in l.lower() or 'pm' in l.lower())) or re.match(r'\d{1,2}:\d{2}', l):
                    break
                # Skip lines with $ (dollar values), odds, percents, or numbers
                if ('$' in l or '%' in l or re.match(r'^[+-]?\d+(\.\d+)?$', l) or re.match(r'^[+-]?\d{1,4}$', l)):
                    continue
                # Skip lines that look like pitcher names (single initial + dot + last name OR last name + comma + first initial)
                if re.match(r'^[A-Z]\. [A-Za-z\-]+$', l) or re.match(r'^[A-Za-z\-]+, [A-Z]$', l):
                    logger.info(f"[PTO DEBUG] Skipping pitcher name (pattern 1): {l}")
                    continue
                # Skip lines that look like pitcher names with more complex patterns
                if re.match(r'^[A-Za-z\-]+, [A-Z]\.$', l) or re.match(r'^[A-Za-z\-]+, [A-Z][a-z]+$', l):
                    logger.info(f"[PTO DEBUG] Skipping pitcher name (pattern 2): {l}")
                    continue
                # Skip lines that look like bet types (Over/Under)
                if l.lower().startswith('over') or l.lower().startswith('under'):
                    continue
                # Skip lines that are all uppercase (often not team names)
                if l.isupper():
                    continue
                logger.info(f"[PTO DEBUG] Adding as team name: {l}")
                team_lines.append(l)
                if len(team_lines) == 2:
                    break
            teams = team_lines if len(team_lines) == 2 else [None, None]
            logger.debug(f"[PTO DEBUG] MLB teams extracted: {teams}")
            logger.info(f"[PTO DEBUG] MLB team extraction - team_lines: {team_lines}, final teams: {teams}")
        else:
            team_lines = []
            for l in lines[1:]:
                if (':' in l and ('am' in l.lower() or 'pm' in l.lower())) or re.match(r'\d{1,2}:\d{2}', l):
                    break
                if l.isupper() or any(char.isdigit() for char in l):
                    continue
                team_lines.append(l)
            teams = team_lines[:2] if len(team_lines) >= 2 else [None, None]
            logger.debug(f"[PTO DEBUG] Other sport teams extracted: {teams}")
        
        game_time = next((l for l in lines if (('am' in l.lower() or 'pm' in l.lower()) and ':' in l) or re.match(r'\d{1,2}:\d{2}', l)), None)
        prop_desc = next((l for l in lines if '-' in l and not l.startswith('Width')), None)
        bet_type = next((l for l in lines if l.startswith('Over') or l.startswith('Under')), None)
        odds = next((l for l in lines if (l.startswith('+') or l.startswith('-')) and len(l) <= 5), None)
        width = next((l for l in lines if l.isdigit()), None)
        
        # Find Multiplicative row for FV
        fv = None
        for i, l in enumerate(lines):
            if l.lower().startswith('multiplicative') and i+2 < len(lines):
                fv_candidate = lines[i+1]
                if fv_candidate.startswith('+') or fv_candidate.startswith('-'):
                    fv = fv_candidate
                break
                
        # Find all percent values and use the lowest (worst) as EV
        ev_candidates = []
        for l in lines:
            match = re.match(r'^-?\d+(\.\d+)?%$', l.strip())
            if match:
                try:
                    ev_candidates.append(float(l.strip().replace('%','')))
                except Exception:
                    pass
                    
        ev = None
        if ev_candidates:
            ev = f"{min(ev_candidates):.1f}%"
            
        return {
            'sport': sport,
            'teams': teams,
            'propDesc': prop_desc,
            'betType': bet_type,
            'odds': odds,
            'width': width,
            'gameTime': game_time,
            'fairValue': fv,
            'ev': ev,
            'timestamp': datetime.now().isoformat()
        }

    def get_sport_emoji(self, sport: str) -> str:
        """Get emoji for sport type - using ASCII-safe characters"""
        sport = sport.lower()
        if 'nba' in sport:
            return '[BASKETBALL]'
        if 'wnba' in sport:
            return '[BASKETBALL]'
        if 'mlb' in sport:
            return '[BASEBALL]'
        if 'nfl' in sport:
            return '[FOOTBALL]'
        if 'nhl' in sport:
            return '[HOCKEY]'
        if 'soccer' in sport or 'futbol' in sport or 'football' in sport:
            return '[SOCCER]'
        return '[SPORT]'

    def format_telegram_alert(self, prop, created_at=None, updated_at=None, prev_ev=None):
        """Format prop for Telegram alert (from original project)"""
        # Format teams and game time
        teams = ''
        if prop.get('teams') and len(prop['teams']) == 2:
            team1 = prop['teams'][0]
            team2 = prop['teams'][1]
            teams = f"{team1} vs. {team2}"
        game_time = prop.get('gameTime', '')
        fair_value = prop.get('fairValue', None)
        odds = prop.get('odds', '')
        ev = prop.get('ev', '')
        sport = prop.get('sport','')
        emoji = self.get_sport_emoji(sport)
        
        # Format prop line (description + bet type)
        prop_line = f"{prop.get('propDesc','')} | {prop.get('betType','')}"
        prop_line = prop_line.replace(' - ', ' - ').title()
        fv_str = f"FV: <code>{fair_value}</code>" if fair_value else ""
        
        # EV change arrow - using ASCII characters
        ev_arrow = ''
        try:
            ev_float = float(str(ev).replace('%','').replace('+',''))
            prev_ev_float = float(str(prev_ev).replace('%','').replace('+','')) if prev_ev is not None else None
            if prev_ev_float is not None:
                if ev_float > prev_ev_float:
                    ev_arrow = ' ^'  # ASCII up arrow
                elif ev_float < prev_ev_float:
                    ev_arrow = ' v'  # ASCII down arrow
        except Exception:
            pass
        
        game_time_str = (game_time or '').upper()
        ev_str = str(ev)
        if not ev_str.strip().endswith('%'):
            ev_str += '%'
        
        alert = (
            f"<b>{sport.upper()}</b>\n"
            f"{teams}\n"
            f"{game_time_str}\n\n"
            f"<b>{prop_line}</b>\n"
            f"Odds: <code>{odds}</code>" + (f" | {fv_str}" if fv_str else "") + "\n"
            f"Width: <b>{prop.get('width', '')}</b>\n"
            f"<b>EV: {ev_str}{ev_arrow}</b>\n"
        )
        
        return alert

    def send_telegram_alert(self, prop, is_new=True, prev_ev=None, message_id=None):
        """Send or update Telegram alert for prop"""
        if not self.telegram_enabled or not self.telegram or self.dry_run:
            action = "send" if is_new or not message_id else "edit"
            logger.info(f"[DRY RUN] Would {action} Telegram alert for: {prop.get('propDesc','')} (EV: {prop.get('ev','')})")
            return 123456 if is_new or not message_id else message_id  # Fake message_id for testing
        try:
            alert_text = self.format_telegram_alert(prop, prev_ev=prev_ev)
            if is_new or not message_id:
                # Send new alert
                message_id = self.telegram.send_alert(alert_text)
                logger.info(f"[TELEGRAM] Sent Telegram alert for new prop: {prop.get('propDesc','')}")
                return message_id
            else:
                # Edit existing alert
                success = self.telegram.edit_message(message_id, alert_text)
                if success:
                    logger.info(f"[TELEGRAM] Edited Telegram alert for updated prop: {prop.get('propDesc','')}")
                    return message_id
                else:
                    logger.warning(f"[TELEGRAM] Failed to edit Telegram alert, sending new one instead.")
                    message_id = self.telegram.send_alert(alert_text)
                    return message_id
        except Exception as e:
            logger.error(f"[TELEGRAM] Failed to send/edit Telegram alert: {e}")
            return None

    def switch_to_prop_builder(self, driver, timeout=20):
        """Switch to the Prop Builder tab"""
        wait = WebDriverWait(driver, timeout)
        try:
            logger.info("[PROP-BUILDER] Attempting to switch to Prop Builder tab")
            # Click the dropdown button (the one with the current tab name)
            dropdown_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[contains(text(), 'Default')] or .//span[contains(text(), 'Prop Builder')] or .//span[contains(text(), 'EV LIVE')] or .//span[contains(text(), 'LIVE PROPS')]]")
            ))
            logger.info("[PROP-BUILDER] Found dropdown button, clicking...")
            dropdown_btn.click()
            # Click the 'Prop Builder' option in the dropdown
            prop_builder_option = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//li[.//span[contains(text(), 'Prop Builder')]]")
            ))
            logger.info("[PROP-BUILDER] Found Prop Builder option, clicking...")
            prop_builder_option.click()
            # Wait for the Prop Builder tab to load (adjust selector as needed)
            wait.until(EC.visibility_of_element_located(
                (By.XPATH, "//span[contains(text(), 'Prop Builder')]")
            ))
            logger.info("[PROP-BUILDER] Successfully switched to Prop Builder tab")
            return True
        except Exception as e:
            logger.warning(f"[PROP-BUILDER] Could not switch to Prop Builder tab, but will continue scraping anyway: {e}")
            return False

    def start_scraping(self):
        """Start the PTO scraping process in a background thread"""
        if self.is_running:
            logger.warning("PTO scraper is already running")
            return
            
        self.is_running = True
        threading.Thread(target=self._scraping_loop, daemon=True).start()
        logger.info("PTO scraper started in background thread")

    def stop_scraping(self):
        """Stop the PTO scraping process"""
        self.is_running = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
        
        # Kill any remaining Chrome processes
        self.kill_chrome_processes()
        
        logger.info("PTO scraper stopped")

    def build_stable_prop_id(self, prop):
        # Use lower, strip, and fallback to 'unknown' for missing fields
        sport = (prop.get('sport') or 'unknown').strip().lower()
        prop_desc = (prop.get('propDesc') or 'unknown').strip().lower()
        bet_type = (prop.get('betType') or 'unknown').strip().lower()
        team1 = (prop.get('teams', ['unknown', 'unknown'])[0] or 'unknown').strip().lower()
        team2 = (prop.get('teams', ['unknown', 'unknown'])[1] or 'unknown').strip().lower()
        return f"{sport}|{prop_desc}|{bet_type}|{team1}|{team2}"

    async def broadcast_prop_update(self):
        try:
            props_list = [
                {
                    'prop': v['prop'],
                    'created_at': v.get('created_at').isoformat() if isinstance(v.get('created_at'), datetime) else v.get('created_at'),
                    'updated_at': v.get('updated_at').isoformat() if isinstance(v.get('updated_at'), datetime) else v.get('updated_at')
                }
                for v in self.live_props.values()
            ]
            message = {
                'type': 'pto_prop_update',
                'props': props_list,
                'total_count': len(props_list),
                'last_update': datetime.now().isoformat()
            }
            logger.info(f"[WebSocket] Broadcasting PTO update: {len(props_list)} props")
            await manager.broadcast(message)
            logger.info(f"[WebSocket] Successfully broadcasted PTO update")
        except Exception as e:
            logger.error(f"[WebSocket] Error in broadcast_prop_update: {e}")
            import traceback
            logger.error(f"[WebSocket] Traceback: {traceback.format_exc()}")

    def _scraping_loop(self):
        """Main scraping loop with enhanced error handling and fast updates"""
        retry_count = 0
        last_refresh_time = time.time()
        initial_login_complete = False
        # Track consecutive misses for each prop
        miss_threshold = 1  # Used to be 3; changed to 1 for faster removal of missing props
        while self.is_running and retry_count < self.max_retries:
            try:
                logger.info(f"[SCRAPING] Starting scraping session (attempt {retry_count + 1})")
                self.driver = self.get_driver()
                logger.info(f"[DEBUG] Using Chrome profile at: {self.chrome_user_data_dir}/{self.chrome_profile_dir}")
                logger.info(f"[DEBUG] Attempting to load URL: {self.pto_url}")
                # Load PTO URL
                logger.info("[DEBUG] Loading PTO URL...")
                self.driver.get(self.pto_url)
                logger.info(f"[DEBUG] Current URL: {self.driver.current_url}")
                # Wait for Cloudflare challenge
                if not self.wait_for_cloudflare(self.driver):
                    raise Exception("Failed to pass Cloudflare challenge")
                # Check login status
                if not self.check_login_status(self.driver):
                    if not self.handle_login_required(self.driver):
                        raise Exception("Login required but not completed")
                # Only switch to Prop Builder if not already selected (startup)
                if not self.is_on_prop_builder(self.driver):
                    self.switch_to_prop_builder(self.driver)  # Try once, but always continue
                logger.info("[SCRAPING] PTO setup complete, starting prop monitoring...")
                retry_count = 0  # Reset retry count on success
                initial_login_complete = True
                while self.is_running:
                    try:
                        # Only refresh every 2-2.5 hours
                        if time.time() - last_refresh_time > self.refresh_interval:
                            logger.info("[INFO] Refreshing page and switching to 'Prop Builder' tab...")
                            self.driver.refresh()
                            if not self.wait_for_cloudflare(self.driver):
                                raise Exception("Cloudflare challenge on refresh")
                            # Only switch to Prop Builder after refresh
                            if not self.is_on_prop_builder(self.driver):
                                self.switch_to_prop_builder(self.driver)  # Try once, but always continue
                            last_refresh_time = time.time()
                            self.refresh_interval = random.uniform(2 * 60 * 60, 2.5 * 60 * 60)
                        # If redirected to account/user-control-panel, PAUSE and LOG a critical error (never try to recover)
                        current_url = self.driver.current_url
                        if initial_login_complete and ("user-control-panel" in current_url or "account" in current_url):
                            logger.critical(f"[CRITICAL] Redirected to account page after initial login: {current_url}. Pausing scraper. Manual intervention required.")
                            while self.is_running:
                                time.sleep(30)
                            return
                        # Scrape props
                        elements = self.driver.find_elements(By.CSS_SELECTOR, 'div.css-ndwsoy')
                        # Find all prop cards
                        prop_cards = self.driver.find_elements(By.CSS_SELECTOR, "div[data-testid='prop-card']")
                        if len(prop_cards) > 0:
                            logger.info(f"Selenium found prop cards: {len(prop_cards)}")
                        current_props = {}
                        now = datetime.now()
                        for i, card_element in enumerate(elements):
                            card_text = card_element.text
                            logger.debug(f"[DEBUG] Card text:\n{card_text}")
                            prop = self.parse_prop_card_text(card_text)
                            if not prop:
                                logger.debug("[DEBUG] Could not parse prop card text.")
                                continue
                            # --- Extract sportsbook logos for width ---
                            books = []
                            try:
                                logo_imgs = card_element.find_elements(By.CSS_SELECTOR, '.css-hp68mp img')
                                for img in logo_imgs:
                                    book = img.get_attribute('aria-label') or img.get_attribute('alt')
                                    if book:
                                        books.append(book.strip())
                            except Exception as e:
                                logger.warning(f"[PTO SCRAPER] Failed to extract books for width: {e}")
                            prop['books'] = books
                            # Check EV threshold
                            try:
                                ev_value = float(prop.get("ev", "0").replace("%", ""))
                                if ev_value < self.min_ev_threshold:
                                    continue  # Skip props below threshold
                            except (ValueError, AttributeError):
                                continue
                            prop_id = self.build_stable_prop_id(prop)
                            logger.debug(f"[LOG] Built prop_id: {prop_id}")
                            current_props[prop_id] = prop
                            prev_ev = None
                            prev_width = None
                            prev_team1 = None
                            prev_team2 = None
                            if prop_id in self.live_props:
                                old_prop = self.live_props[prop_id]["prop"]
                                old_message_id = self.live_props[prop_id].get("message_id")
                                prev_ev = old_prop.get("ev")
                                prev_width = old_prop.get("width")
                                prev_team1 = (old_prop.get('teams', ['unknown', 'unknown'])[0] or 'unknown').strip().lower()
                                prev_team2 = (old_prop.get('teams', ['unknown', 'unknown'])[1] or 'unknown').strip().lower()
                                # Only edit if EV, width, or team names change
                                ev_changed = prop.get("ev") != prev_ev
                                width_changed = prop.get("width") != prev_width
                                team1_changed = (prop.get('teams', ['unknown', 'unknown'])[0] or 'unknown').strip().lower() != prev_team1
                                team2_changed = (prop.get('teams', ['unknown', 'unknown'])[1] or 'unknown').strip().lower() != prev_team2
                                if ev_changed or width_changed or team1_changed or team2_changed:
                                    logger.info(f"Prop updated: {prop.get('propDesc','')} (EV: {prop.get('ev','')}) [edit]")
                                    message_id = self.send_telegram_alert(prop, is_new=False, prev_ev=prev_ev, message_id=old_message_id)
                                    self.live_props[prop_id]["prop"] = prop
                                    self.live_props[prop_id]["updated_at"] = now
                                    self.live_props[prop_id]["message_id"] = message_id
                                self.live_props[prop_id]["miss_count"] = 0  # Reset miss count if seen
                            else:
                                logger.info(f"New prop found: {prop.get('propDesc','')} (EV: {prop.get('ev','')}) [new]")
                                message_id = self.send_telegram_alert(prop, is_new=True)
                                self.live_props[prop_id] = {"prop": prop, "created_at": now, "updated_at": now, "message_id": message_id, "miss_count": 0}
                        # Remove props that are no longer active (after N misses)
                        for pid in list(self.live_props.keys()):
                            if pid not in current_props:
                                self.live_props[pid]["miss_count"] = self.live_props[pid].get("miss_count", 0) + 1
                                logger.debug(f"[LOG] Prop {pid} missed {self.live_props[pid]['miss_count']} times")
                                if self.live_props[pid]["miss_count"] >= miss_threshold:
                                    logger.info(f"Prop removed: {self.live_props[pid]['prop'].get('propDesc','')} [delete]")
                                    message_id = self.live_props[pid].get("message_id")
                                    if message_id:
                                        if self.dry_run:
                                            logger.info(f"[DRY RUN] Would delete Telegram alert for: {self.live_props[pid]['prop'].get('propDesc','')}")
                                        else:
                                            try:
                                                self.telegram.delete_message(message_id)
                                                logger.info(f"🗑️ Deleted Telegram alert for: {self.live_props[pid]['prop'].get('propDesc','')}")
                                            except Exception as e:
                                                logger.error(f"[ERROR] Failed to delete Telegram alert for {pid}: {e}")
                                    del self.live_props[pid]
                        # Broadcast prop updates to all WebSocket clients
                        try:
                            # Use the main event loop for WebSocket broadcasting
                            from main import main_event_loop
                            if main_event_loop and main_event_loop.is_running():
                                logger.info(f"[WebSocket] Broadcasting prop update with {len(self.live_props)} props")
                                asyncio.run_coroutine_threadsafe(self.broadcast_prop_update(), main_event_loop)
                            else:
                                logger.warning("[WebSocket] Main event loop not available for broadcasting")
                        except Exception as e:
                            logger.error(f"[WebSocket] Error broadcasting prop update: {e}")
                            import traceback
                            logger.error(f"[WebSocket] Traceback: {traceback.format_exc()}")
                        time.sleep(self.scraping_interval)
                    except Exception as e:
                        logger.error(f"[ERROR] Error in scraping loop: {e}")
                        break  # Break inner loop to restart session
            except Exception as e:
                retry_count += 1
                logger.error(f"[ERROR] Critical error in scraping session (attempt {retry_count}): {e}")
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
                if retry_count < self.max_retries:
                    logger.info(f"[WAIT] Waiting {self.retry_delay} seconds before retry...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"[ERROR] Max retries ({self.max_retries}) reached. Stopping scraper.")
                    break
        # Cleanup
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def is_on_prop_builder(self, driver):
        """Return True if currently on the Prop Builder tab"""
        try:
            selected_tab = driver.find_element(By.XPATH, "//button[.//span[contains(text(), 'Prop Builder')] and contains(@class, 'Mui-selected')]")
            return selected_tab is not None
        except Exception:
            return False

    def get_live_props(self) -> Dict[str, Any]:
        """Get current live props data"""
        # Wrap each prop dict for frontend compatibility, ensure datetimes are ISO strings
        wrapped_props = [
            {
                'prop': v['prop'],
                'created_at': v.get('created_at').isoformat() if isinstance(v.get('created_at'), datetime) else v.get('created_at'),
                'updated_at': v.get('updated_at').isoformat() if isinstance(v.get('updated_at'), datetime) else v.get('updated_at')
            }
            for v in self.live_props.values()
        ]
        return {
            "status": "success",
            "data": {
                "props": wrapped_props,
                "total_count": len(self.live_props),
                "last_update": datetime.now().isoformat()
            }
        }

    def get_props_by_ev_threshold(self, min_ev: float = 0.0) -> Dict[str, Any]:
        """Get props filtered by minimum EV threshold, returning a flat list of prop dicts for frontend."""
        filtered_props = []
        for prop_data in self.live_props.values():
            prop = prop_data.get("prop")
            try:
                ev_value = float(str(prop.get("ev", "0")).replace("%", ""))
                if ev_value >= min_ev:
                    filtered_props.append({
                        'prop': prop,
                        'created_at': prop_data.get('created_at').isoformat() if isinstance(prop_data.get('created_at'), datetime) else prop_data.get('created_at'),
                        'updated_at': prop_data.get('updated_at').isoformat() if isinstance(prop_data.get('updated_at'), datetime) else prop_data.get('updated_at')
                    })
            except (ValueError, AttributeError, TypeError):
                continue
        return {
            "status": "success",
            "data": {
                "props": filtered_props,
                "total_count": len(filtered_props),
                "min_ev": min_ev,
                "last_update": datetime.now().isoformat()
            }
        }

    def test_profile(self) -> bool:
        """Test if the Chrome profile is working correctly"""
        logger.info("🧪 Testing PTO Chrome profile...")
        
        try:
            # Create a temporary driver for testing
            test_driver = self.get_driver()
            
            # Navigate to PTO
            logger.info("🔗 Navigating to PTO for profile test...")
            test_driver.get(self.pto_url)
            
            # Wait for page to load
            time.sleep(5)
            
            # Check if we're logged in
            if self.check_login_status(test_driver):
                logger.info("Profile test successful - logged in to PTO")
                test_driver.quit()
                return True
            else:
                logger.warning("[WARNING] Profile test failed - not logged in to PTO")
                test_driver.quit()
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Profile test failed with error: {e}")
            try:
                if 'test_driver' in locals():
                    test_driver.quit()
            except:
                pass
            return False 