"""
Ace Sports Scraper (action23.ag)
Handles login, league fetching, and odds scraping for Ace sportsbook
"""

import requests
import json
import logging
import time
import sys
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin
import re
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from utils.pod_utils import normalize_team_name_for_matching, analyze_markets_for_ev, clean_pod_team_name_for_search, determine_betbck_search_term
from odds_processing import fetch_live_pinnacle_event_odds
from utils import process_event_odds_for_display
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import threading
from collections import defaultdict

from buckeye_scraper import get_buckeye_scraper
from buckeye_scraper import BuckeyeScraper
import queue

# Set up base directory for all file operations
BASE_DIR = Path(__file__).resolve().parent

# Set up comprehensive file logging
def setup_ace_logging():
    """Set up comprehensive logging to file for debugging"""
    try:
        # Create logs directory relative to backend/
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"ace_debug_{timestamp}.log"
        
        # Configure logging - to both file and console
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)  # Also log to console
            ],
            force=True  # Force reconfiguration
        )
        

        
        # Set specific loggers to DEBUG level
        logging.getLogger("ace").setLevel(logging.DEBUG)
        logging.getLogger("buckeye").setLevel(logging.DEBUG)
        logging.getLogger("urllib3").setLevel(logging.DEBUG)
        logging.getLogger("requests").setLevel(logging.DEBUG)
        
        # Test logging
        test_logger = logging.getLogger("ace")
        test_logger.info(f"[ACE LOGGING] Comprehensive debug log will be written to: {log_file.absolute()}")
        test_logger.info("[ACE LOGGING] Logging setup completed successfully")
        
        return log_file
        
    except Exception as e:
        print(f"[ACE LOGGING ERROR] Failed to setup logging: {e}")
        import traceback
        print(f"[ACE LOGGING ERROR] Traceback: {traceback.format_exc()}")
        return None

# Set up logging when module is imported
ACE_DEBUG_LOG_FILE = setup_ace_logging()

logger = logging.getLogger("ace")

def safe_print(s):
    try:
        if isinstance(s, bytes):
            s = s.decode('utf-8', errors='replace')
        print(str(s).encode('ascii', 'replace').decode('ascii', 'replace'))
    except Exception as e:
        print(f"[PRINT ERROR] {e}")

def clean_fraction_entities(s: str) -> str:
    if not isinstance(s, str):
        return s
    return (
        s.replace('&frac12;', '.5')
         .replace('&frac14;', '.25')
         .replace('&frac34;', '.75')
         .replace('PK', '0')  # Convert PK (pick'em) to 0
         .replace('EV', '+100')  # Convert EV (even money) to +100
    )

class AceScraper:
    """Scraper for action23.ag sportsbook"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Ace scraper"""
        self.config = config
        self.debug = config.get("debug", False)
        
        # Use the correct Action23 domain
        self.base_url = "https://backend.action23.ag"  # Correct domain
        
        # Initialize session
        self.session = requests.Session()
        self.logged_in = False
        
        # Set up basic headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',  # Only allow gzip and deflate
            'Connection': 'keep-alive',
            'DNT': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session.headers.update(headers)
        
        # Set up data directory and files
        BASE_DIR = Path(__file__).resolve().parent
        self.data_dir = BASE_DIR / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.data_dir / "ace_results.json"
        
        # Exclusion patterns for filtering out props, futures, etc.
        self.exclusion_patterns = [
            r'\b(?:ESPORTS?|ESPORT)\b',
            r'\b(?:LOL|LEAGUE OF LEGENDS|CS2|COUNTER STRIKE|DOTA|VALORANT)\b',
            r'\b(?:ROCKET LEAGUE|FIFA|FORTNITE|PUBG|OVERWATCH)\b',
            r'\b(?:STARCRAFT|WARCRAFT|ESPORTS)\b',
            r'\b(?:MAKE PLAYOFFS|YES MAKE PLAYOFFS|NO MAKE PLAYOFFS)\b',
            r'\b(?:TO WIN|TO ADVANCE|PLAYER PROP|TEAM PROP)\b',
            r'\b(?:SEASON FUTURE|AWARD|MVP|ROOKIE)\b',
            r'\b(?:1ST HALF|2ND HALF|HALF TIME|1H|2H|Q1|Q2|Q3|Q4)\b',
            r'\b(?:QUARTER|PERIOD|OT|OVERTIME|EXTRA TIME)\b',
            r'\b(?:SET|1ST SET|2ND SET|3RD SET|4TH SET|5TH SET)\b',
            r'\b(?:HITS\+RUNS\+ERRORS|H\+R\+E|HRE|PITCHER|BATTER)\b',
            r'\b(?:STRIKEOUT|HOME RUN|RBI|ERA|WHIP|SAVE|HOLD)\b',
            r'\b(?:FIGHT|MATCH|BOUT|KNOCKOUT|KO|TKO|DECISION)\b',
            r'\b(?:SUBMISSION|CHOKE|ARM BAR|LEG LOCK)\b',
            r'\b(?:HOLE|ROUND|BOGEY|PAR|BIRDIE|EAGLE|PUTT|DRIVE)\b',
            # Tennis-specific exclusions
            r'\b(?:1ST SET|2ND SET|3RD SET|4TH SET|5TH SET)\b',
            r'\b(?:SETS|GAMES|GAME)\b',
            r'\b(?:TENNIS.*1ST SET|TENNIS.*GAMES|TENNIS.*SETS)\b',
            r'\b(?:ATP.*1ST SET|WTA.*1ST SET|ATP.*GAMES|WTA.*GAMES)\b',
            r'\b(?:ALT\s+)\b',  # Alternative lines
            r'\b(?:FIRST HALF|1H\s+)\b',  # First half lines
            # Futures and series exclusions
            r'\b(?:SERIES PRICES|SERIES WINNER|SERIES BET)\b',
            r'\b(?:CHAMPIONSHIP|CHAMPION|TITLE)\b',
            r'\b(?:SEASON|REGULAR SEASON|PLAYOFFS)\b',
            r'\b(?:WORLD SERIES|STANLEY CUP|SUPER BOWL)\b',
            r'\b(?:TO WIN|TO ADVANCE|TO MAKE)\b',
            r'\b(?:FUTURES|FUTURE BET|FUTURE MARKET)\b',
            # F1-specific exclusions
            r'\b(?:BOTH CARS IN PODIUM|DOUBLE PODIUM|PODIUM FINISH)\b',
            r'\b(?:F1.*PODIUM|F1.*FINISH|F1.*RESULT)\b',
            r'\b(?:FORMULA 1.*PODIUM|FORMULA 1.*FINISH|FORMULA 1.*RESULT)\b',
            r'\b(?:GP.*PODIUM|GP.*FINISH|GP.*RESULT)\b',
            r'\b(?:GRAND PRIX.*PODIUM|GRAND PRIX.*FINISH|GRAND PRIX.*RESULT)\b'
        ]
        
        safe_print(f"[ACE DEBUG] Initialized Ace scraper with base URL: {self.base_url}")
        safe_print(f"[ACE DEBUG] Data directory: {self.data_dir}")
        safe_print(f"[ACE DEBUG] Results file: {self.results_file}")
    
    def _validate_session(self) -> bool:
        """Validate if the current session is still active"""
        try:
            safe_print("[ACE DEBUG] Validating session...")
            
            # Try to access a protected page to check if we're still logged in
            test_url = f"{self.base_url}/wager/Welcome.aspx?login=1"
            safe_print(f"[ACE DEBUG] Testing session with URL: {test_url}")
            
            response = self.session.get(test_url, timeout=10, allow_redirects=False)
            safe_print(f"[ACE DEBUG] Session test response status: {response.status_code}")
            safe_print(f"[ACE DEBUG] Session test response URL: {response.url}")
            
            # If we get redirected to login, session is invalid
            if response.status_code == 302 and 'login' in response.headers.get('Location', '').lower():
                safe_print("[ACE DEBUG] Session validation failed - redirected to login")
                return False
            
            # If we get a 200 response, check if it's actually a protected page
            if response.status_code == 200:
                content = response.text.lower()
                # If we get a login page, session is invalid
                if ('<html' in content and 
                    ('login.aspx' in content or 
                     'action=\"./login' in content or 
                     'name=\"account\"' in content or
                     'name=\"password\"' in content)):
                    safe_print("[ACE DEBUG] Session validation failed - got login page")
                    return False
                
                safe_print("[ACE DEBUG] Session validation successful - got 200 response")
                return True
            else:
                safe_print(f"[ACE DEBUG] Session validation failed - got status {response.status_code}")
                return False
            
        except Exception as e:
            safe_print(f"[ACE DEBUG] Session validation failed: {e}")
            return False
    
    def login(self, username: str = "STEPHENFAR", password: str = "football") -> bool:
        """Login to action23.ag using the correct workflow (Buckeye-style robust)"""
        try:
            safe_print("[ACE DEBUG] Starting login process...")
            login_url = f"{self.base_url}/Login.aspx"
            safe_print(f"[ACE DEBUG] Fetching login page: {login_url}")
            response = self.session.get(login_url, allow_redirects=True)
            response.raise_for_status()
            safe_print(f"[ACE DEBUG] Login page response status: {response.status_code}")
            safe_print(f"[ACE DEBUG] Login page URL: {response.url}")
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form')
            if not form:
                safe_print("[ACE DEBUG] No form found on login page!")
                safe_print(f"[ACE DEBUG] Login page content preview: {response.text[:200]}")
                return False
            all_inputs = soup.find_all('input')
            safe_print(f"[ACE DEBUG] Found {len(all_inputs)} input fields on login page:")
            for inp in all_inputs:
                name = inp.get('name', 'NO_NAME')
                value = inp.get('value', 'NO_VALUE')
                input_type = inp.get('type', 'NO_TYPE')
                safe_print(f"[ACE DEBUG] Input: name='{name}', type='{input_type}', value='{value[:50]}...' if len(value) > 50 else value")
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})
            viewstate_generator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
            event_validation = soup.find('input', {'name': '__EVENTVALIDATION'})
            login_data = {
                'Account': username,
                'Password': password,
                'BtnSubmit': 'Login'
            }
            if viewstate:
                login_data['__VIEWSTATE'] = viewstate.get('value', '')
                safe_print(f"[ACE DEBUG] Added __VIEWSTATE: {viewstate.get('value', '')[:50]}...")
            if viewstate_generator:
                login_data['__VIEWSTATEGENERATOR'] = viewstate_generator.get('value', '')
                safe_print(f"[ACE DEBUG] Added __VIEWSTATEGENERATOR: {viewstate_generator.get('value', '')[:50]}...")
            if event_validation:
                login_data['__EVENTVALIDATION'] = event_validation.get('value', '')
                safe_print(f"[ACE DEBUG] Added __EVENTVALIDATION: {event_validation.get('value', '')[:50]}...")
            safe_print(f"[ACE DEBUG] Login data prepared: {list(login_data.keys())}")
            # Buckeye-style: allow_redirects=True
            safe_print("[ACE DEBUG] Submitting login form with allow_redirects=True...")
            login_response = self.session.post(login_url, data=login_data, allow_redirects=True)
            safe_print(f"[ACE DEBUG] Login response status: {login_response.status_code}")
            safe_print(f"[ACE DEBUG] Login response URL: {login_response.url}")
            safe_print(f"[ACE DEBUG] Login response headers: {dict(login_response.headers)}")
            # Check for login success: look for protected URLs and 'Logout' in response
            if ("Welcome.aspx" in login_response.url or "CreateSports.aspx" in login_response.url) and \
               ("Logout" in login_response.text or "logout" in login_response.text) and \
               ("Invalid User" not in login_response.text):
                safe_print("[ACE DEBUG] Login successful - reached protected page and found 'Logout' in response")
                self.logged_in = True
                return True
            else:
                safe_print(f"[ACE DEBUG] Login failed. Status: {login_response.status_code}. URL: {login_response.url}")
                safe_print(f"[ACE DEBUG] Login response content preview: {login_response.text[:200]}")
                return False
        except Exception as e:
            safe_print(f"[ACE DEBUG] Login failed: {e}")
            import traceback
            safe_print(f"[ACE DEBUG] Login traceback: {traceback.format_exc()}")
            return False
    
    EXCLUDED_TERMS = [
        "PRESIDENTIAL", "DEMOCRAT", "REPUBLICAN", "OSCARS", "NOBEL", "PERSON OF THE YEAR",
        "WINNER", "BREEDERS", "F1", "NASCAR", "CYCLING", "OUTRIGHT", "TEAM TOTALS",
        "1H", "SEASON TOTAL", "MATCHUPS",
        # User additions:
        "DARTS", "CRICKET", "SPECIALS", "SPECIAL", "REGULAR SEASON WINS", "MAKE THE PLAYOFFS",
        "AWARD", "E-SPORTS", "FORMULA 1", "CALDER", "VEZINA", "HART", "GOLF", "WINS",
        "QUARTERS", "POTENTIAL", "FUTURES", "RESULT", "PLAYER OF THE YEAR", "IMPROVED",
        "DEFENSIVE", "MVP", "NORRIS", "RICHARD", "ADAMS",
        # Additional exclusions to match Pinnacle scope:
        "PROPS", "NHL TO MAKE PLAYOFFS", "WNCAA", "WOMEN'S", "LADIES'", "LADIES",
        "EARLY GAME LINES", "STAGE OF ELIMINATION", "MOST RECEIVING YARDS", 
        "MOST RUSHING YARDS", "MOST PASSING YARDS", "CHAMPIONSHIP GONE"
    ]
    def _is_excluded_league_or_desc(self, text: str) -> bool:
        return any(term in text.upper() for term in self.EXCLUDED_TERMS)

    def get_active_league_ids(self) -> str:
        """Get active league IDs as a comma-separated string"""
        league_ids = self._fetch_active_leagues()
        league_ids_str = ','.join(league_ids)
        safe_print(f"[ACE DEBUG] get_active_league_ids returning: {league_ids_str}")
        return league_ids_str

    def _fetch_active_leagues(self) -> List[str]:
        """Fetch active leagues from Ace - use known working league IDs"""
        try:
            safe_print("[ACE DEBUG] Using known working league IDs...")
            
            # Expanded league IDs to include more sports (MLB, NBA, NFL, NHL, etc.)
            # Original working IDs plus additional major sports leagues
            working_league_ids = [
                # Original working IDs
                "2521", "515", "537", "1116", "3483", "1278", "439", "549", "451", "414",
                "558", "4437", "557", "440", "585", "1183", "333", "1180", "546", "2948",
                "1193", "1567", "520", "1241", "184", "2716", "482", "1195", "1189", "438",
                "745", "1186", "306", "116", "1181", "521", "4781", "2777", "1190", "441",
                "1196", "1162", "1569",
                
                # Additional MLB leagues
                "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",  # MLB and minor leagues
                "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
                
                # Additional NBA leagues  
                "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",  # NBA and G-League
                "31", "32", "33", "34", "35", "36", "37", "38", "39", "40",
                
                # Additional NFL leagues
                "41", "42", "43", "44", "45", "46", "47", "48", "49", "50",  # NFL and college
                "51", "52", "53", "54", "55", "56", "57", "58", "59", "60",
                
                # Additional NHL leagues
                "61", "62", "63", "64", "65", "66", "67", "68", "69", "70",  # NHL and AHL
                "71", "72", "73", "74", "75", "76", "77", "78", "79", "80",
                
                # Additional soccer leagues
                "81", "82", "83", "84", "85", "86", "87", "88", "89", "90",
                "91", "92", "93", "94", "95", "96", "97", "98", "99", "100",
                
                # Additional fighting/MMA leagues
                "101", "102", "103", "104", "105", "106", "107", "108", "109", "110",
                
                # Additional college sports
                "111", "112", "113", "114", "115", "117", "118", "119", "120",
                
                # Additional international leagues
                "121", "122", "123", "124", "125", "126", "127", "128", "129", "130",
                "131", "132", "133", "134", "135", "136", "137", "138", "139", "140"
            ]
            
            safe_print(f"[ACE DEBUG] Using {len(working_league_ids)} known working league IDs")
            return working_league_ids
                
        except Exception as e:
            safe_print(f"[ACE DEBUG] Error with league IDs: {e}")
            # Fallback to a broad range
            safe_print("[ACE DEBUG] Using fallback league range 1-1000")
            return [str(i) for i in range(1, 1001)]
    
    def get_combined_league_ids(self) -> str:
        """Get combined league IDs - now uses dynamic active leagues"""
        return self.get_active_league_ids()
    
    def fetch_odds_data(self, league_ids: str = None) -> str:
        """Fetch odds data from NewSchedule.aspx with retry logic"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if not self.logged_in:
                    safe_print("[ACE DEBUG] Not logged in")
                    return ""

                if not league_ids:
                    league_ids = self.get_combined_league_ids()

                # Validate session before fetching
                if not self._validate_session():
                    safe_print("[ACE DEBUG] Session expired, attempting to re-login")
                    if not self.login():
                        safe_print("[ACE DEBUG] Failed to re-login")
                        return ""

                # Step 1: Navigate to CreateSports.aspx first (as per workflow)
                safe_print("[ACE DEBUG] Step 1: Navigating to CreateSports.aspx...")
                create_sports_url = f"{self.base_url}/wager/CreateSports.aspx?WT=0"
                create_response = self.session.get(create_sports_url, allow_redirects=False)
                safe_print(f"[ACE DEBUG] CreateSports response status: {create_response.status_code}")
                safe_print(f"[ACE DEBUG] CreateSports response URL: {create_response.url}")
                
                # Check if we got redirected to login
                create_content = create_response.text.lower()
                if ('<html' in create_content and 
                    ('login.aspx' in create_content or 
                     'action=\"./login' in create_content or 
                     'name=\"account\"' in create_content or
                     'name=\"password\"' in create_content)):
                    safe_print("[ACE DEBUG] Got HTML login page from CreateSports.aspx")
                    if attempt < max_retries - 1:
                        safe_print("[ACE DEBUG] Re-logging in and retrying...")
                        if self.login():
                            time.sleep(retry_delay)
                            continue
                        else:
                            return ""
                    else:
                        return ""
                
                # Step 1.5: Also try Welcome.aspx to establish session
                safe_print("[ACE DEBUG] Step 1.5: Navigating to Welcome.aspx...")
                welcome_url = f"{self.base_url}/wager/Welcome.aspx?login=1"
                welcome_response = self.session.get(welcome_url, allow_redirects=False)
                safe_print(f"[ACE DEBUG] Welcome response status: {welcome_response.status_code}")
                safe_print(f"[ACE DEBUG] Welcome response URL: {welcome_response.url}")

                # Step 2: Fetch odds data from correct URL (NewScheduleHelper.aspx)
                odds_url = f"{self.base_url}/wager/NewScheduleHelper.aspx"
                params = {
                    'WT': '0',
                    'lg': league_ids
                }
                safe_print(f"[ACE DEBUG] Step 2: Fetching odds from: {odds_url} with params: {params} (attempt {attempt + 1}/{max_retries})")
                safe_print(f"[ACE DEBUG] Final league IDs: {league_ids}")
                
                # Add better headers to look more like a real browser
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',  # Remove brotli to avoid compression issues
                    'Connection': 'keep-alive',
                    'DNT': '1',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                    'Referer': f'{self.base_url}/wager/CreateSports.aspx?WT=0'
                }
                
                # Update session headers
                self.session.headers.update(headers)
                
                safe_print(f"[ACE DEBUG] Request headers: {dict(self.session.headers)}")
                try:
                    safe_print(f"[ACE DEBUG] Session cookies: {dict(self.session.cookies)}")
                except Exception as e:
                    safe_print(f"[ACE DEBUG] Could not log cookies: {e}")

                response = self.session.get(odds_url, params=params, timeout=30)
                safe_print(f"[ACE DEBUG] Odds response status: {response.status_code}")
                safe_print(f"[ACE DEBUG] Odds response URL: {response.url}")
                safe_print(f"[ACE DEBUG] Odds response headers: {dict(response.headers)}")
                
                # Check for compression and handle properly
                content_encoding = response.headers.get('content-encoding', '').lower()
                safe_print(f"[ACE DEBUG] Content encoding: {content_encoding}")
                
                # Get the response content properly
                if content_encoding == 'gzip':
                    safe_print("[ACE DEBUG] Response is gzipped, decompressing...")
                    try:
                        import gzip
                        import io
                        decompressed_bytes = gzip.decompress(response.content)
                        content = decompressed_bytes.decode('utf-8', errors='ignore')
                        safe_print(f"[ACE DEBUG] Successfully decompressed {len(response.content)} bytes to {len(content)} characters")
                    except Exception as e:
                        safe_print(f"[ACE DEBUG] Failed to decompress gzip: {e}")
                        try:
                            response.raw.decode_content = True
                            content = response.text
                            safe_print(f"[ACE DEBUG] Used requests built-in decompression: {len(content)} characters")
                        except Exception as e2:
                            safe_print(f"[ACE DEBUG] Alternative decompression also failed: {e2}")
                            content = response.text
                elif content_encoding == 'deflate':
                    safe_print("[ACE DEBUG] Response is deflated, decompressing...")
                    try:
                        import zlib
                        decompressed_bytes = zlib.decompress(response.content)
                        content = decompressed_bytes.decode('utf-8', errors='ignore')
                        safe_print(f"[ACE DEBUG] Successfully decompressed deflate: {len(content)} characters")
                    except Exception as e:
                        safe_print(f"[ACE DEBUG] Failed to decompress deflate: {e}")
                        content = response.text
                elif content_encoding == 'zstd':
                    safe_print("[ACE DEBUG] Response is zstd compressed, decompressing...")
                    try:
                        import zstandard
                        dctx = zstandard.ZstdDecompressor()
                        decompressed_bytes = dctx.decompress(response.content)
                        content = decompressed_bytes.decode('utf-8', errors='ignore')
                        safe_print(f"[ACE DEBUG] Successfully decompressed zstd: {len(content)} characters")
                    except Exception as e:
                        safe_print(f"[ACE DEBUG] Failed to decompress zstd: {e}")
                        content = response.text
                elif content_encoding == 'br':
                    safe_print("[ACE DEBUG] Response is brotli compressed, decompressing...")
                    try:
                        import brotli
                        decompressed_bytes = brotli.decompress(response.content)
                        content = decompressed_bytes.decode('utf-8', errors='ignore')
                        safe_print(f"[ACE DEBUG] Successfully decompressed brotli: {len(content)} characters")
                    except Exception as e:
                        safe_print(f"[ACE DEBUG] Failed to decompress brotli: {e}")
                        content = response.text
                else:
                    content = response.text
                    safe_print(f"[ACE DEBUG] No compression detected or unhandled, using response.text: {len(content)} characters")
                
                safe_print(f"[ACE DEBUG] Odds response length: {len(content)}")

                # Check for errors
                if response.status_code != 200:
                    safe_print(f"[ACE DEBUG] Odds HTTP error: {response.status_code}")
                    safe_print(f"[ACE DEBUG] Odds response text: {content[:200]}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        return ""

                # Check if response is HTML login page instead of JSON
                if '<html' in content.lower() or 'login' in content.lower():
                    safe_print("[ACE DEBUG] Received HTML login page, session expired or not authenticated!")
                    safe_print(f"[ACE DEBUG] HTML content preview: {content[:200]}")
                    if attempt < max_retries - 1:
                        safe_print(f"[ACE DEBUG] Re-logging in and retrying...")
                        if self.login():
                            time.sleep(retry_delay)
                            continue
                        else:
                            return ""
                    else:
                        return ""

                # Check if response is too short (might be error page)
                if len(content) < 100:
                    safe_print(f"[ACE DEBUG] Response too short ({len(content)} chars), might be error page")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return ""

                safe_print(f"[ACE DEBUG] Successfully fetched odds data ({len(content)} chars)")
                
                # Debug: Print the first 200 characters of the response (safe for Unicode)
                try:
                    safe_preview = content[:200].encode('ascii', 'ignore').decode('ascii')
                    safe_print(f"[ACE DEBUG] Response preview: {safe_preview}")
                    
                    # Check if it looks like JSON
                    if content.strip().startswith('{') or content.strip().startswith('['):
                        safe_print("[ACE DEBUG] Response appears to be JSON")
                    elif '<html' in content.lower():
                        safe_print("[ACE DEBUG] Response appears to be HTML")
                        # Save HTML response for debugging
                        try:
                            with open(self.data_dir / "last_html_response.txt", "w", encoding="utf-8") as f:
                                f.write(content)
                            safe_print(f"[ACE DEBUG] Saved HTML response to {self.data_dir / 'last_html_response.txt'}")
                        except Exception as save_error:
                            safe_print(f"[ACE DEBUG] Could not save HTML response: {save_error}")
                    elif 'error' in content.lower():
                        safe_print("[ACE DEBUG] Response appears to be an error page")
                    else:
                        safe_print("[ACE DEBUG] Response format unclear")
                        
                except Exception as preview_error:
                    safe_print(f"[ACE DEBUG] Could not create response preview: {preview_error}")
                    safe_print("[ACE DEBUG] Response preview: <Unicode content>")
                
                return content

            except requests.exceptions.ConnectionError as e:
                safe_print(f"[ACE DEBUG] Connection error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    safe_print(f"[ACE DEBUG] Waiting {retry_delay}s before retry...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    safe_print(f"[ACE DEBUG] All connection attempts failed")
                    return ""
                    
            except Exception as e:
                safe_print(f"[ACE DEBUG] Error fetching odds data on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    return ""
        
        return ""
    
    def parse_odds_html(self, html_content: str) -> List[Dict]:
        """Parse odds HTML and return a list of games with cleaned, split odds fields."""
        try:
            # Check if content looks like HTML login page
            if '<html' in html_content.lower() or 'login' in html_content.lower():
                logging.error("[ACE DEBUG] Received HTML login page instead of odds data")
                logging.error(f"[ACE DEBUG] Response preview: {html_content[:200]}")
                return []
            
            # Try to parse as JSON first
            if html_content.strip().startswith('{'):
                games = self._parse_json_response(html_content)
                logging.info(f"[ACE DEBUG] Parsed {len(games)} games from JSON.")
                if games:
                    logging.info(f"[ACE DEBUG] Sample game: {json.dumps(games[0], indent=2) if len(games) > 0 else 'None'}")
                return games
            
            # Fall back to HTML parsing for non-JSON responses
            soup = BeautifulSoup(html_content, 'html.parser')
            games = []
            
            # Find all competition containers (handle multiple classes)
            competitions = soup.find_all('div', class_=re.compile(r'Competition.*container-fluid'))
            
            for competition in competitions:
                # Find all game rows within this competition
                game_rows = competition.find_all('div', class_='row GameRow')
                
                if len(game_rows) < 2:
                    continue  # Need at least 2 teams
                
                # Extract game data
                game_data = self._extract_game_from_rows(game_rows)
                if game_data:
                    games.append(game_data)
            
            logging.info(f"[ACE DEBUG] Parsed {len(games)} games from HTML.")
            if games:
                logging.info(f"[ACE DEBUG] Sample game: {json.dumps(games[0], indent=2) if len(games) > 0 else 'None'}")
            return games
            
        except Exception as e:
            logging.error(f"Error parsing odds content: {e}")
            logging.error(f"[ACE DEBUG] Raw odds content (first 500 chars): {html_content[:500]}")
            return []
    
    def _parse_json_response(self, json_content: str) -> List[Dict]:
        """Parse JSON response from NewScheduleHelper.aspx with robust error handling"""
        try:
            # First, validate the response content
            if not json_content or not json_content.strip():
                safe_print("[ACE DEBUG] Empty response received")
                return []
            
            # Check if response is actually JSON
            if not json_content.strip().startswith('{') and not json_content.strip().startswith('['):
                safe_print("[ACE DEBUG] Response is not JSON - likely HTML or error page")
                safe_print(f"[ACE DEBUG] Response starts with: {json_content[:100]}")
                
                # Check if it's an HTML error page
                if '<html' in json_content.lower():
                    safe_print("[ACE DEBUG] Response is HTML - likely login page or error")
                    if 'login' in json_content.lower():
                        safe_print("[ACE DEBUG] HTML contains 'login' - session may have expired")
                    elif 'error' in json_content.lower():
                        safe_print("[ACE DEBUG] HTML contains 'error' - server error page")
                
                # Save the response for debugging
                try:
                    with open(self.data_dir / "last_bad_response.txt", "w", encoding="utf-8") as f:
                        f.write(json_content)
                    safe_print(f"[ACE DEBUG] Saved non-JSON response to {self.data_dir / 'last_bad_response.txt'}")
                except Exception as save_error:
                    safe_print(f"[ACE DEBUG] Could not save response: {save_error}")
                return []
            
            # Clean the JSON content to remove invalid control characters
            import re
            # Remove control characters except newlines and tabs
            cleaned_content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', json_content)
            
            # Try to find the end of the JSON structure
            # Look for the closing brackets to handle truncated JSON
            brace_count = 0
            end_pos = 0
            for i, char in enumerate(cleaned_content):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            
            if end_pos > 0:
                cleaned_content = cleaned_content[:end_pos]
                safe_print(f"[ACE DEBUG] Truncated JSON to {end_pos} characters")
            
            # Try to parse JSON
            data = json.loads(cleaned_content)
            games = []
            
            # Navigate JSON structure safely
            result = data.get('result', {})
            list_leagues = result.get('listLeagues', [])
            
            if not isinstance(list_leagues, list):
                safe_print(f"[ACE DEBUG] listLeagues is not a list: {type(list_leagues)}")
                return []
            
            for league_group in list_leagues:
                if not isinstance(league_group, list):
                    continue
                    
                for league in league_group:
                    if not isinstance(league, dict):
                        continue
                        
                    league_desc = league.get('Description', '')
                    league_games = league.get('Games', [])
                    
                    if not isinstance(league_games, list):
                        continue
                    
                    for game in league_games:
                        if not isinstance(game, dict):
                            continue
                        
                        # Only process main games (not child games/props)
                        # Check if this is a main game by looking for haschild=True or no GameChilds
                        game_lines = game.get('GameLines', [])
                        if not game_lines:
                            continue
                        
                        # Check if this is a main game (haschild=True) or has no child games
                        main_line = game_lines[0]
                        has_child = main_line.get('haschild', False)
                        game_childs = game.get('GameChilds', [])
                        
                        # Only process if this is a main game (haschild=True) or has no child games
                        if has_child or not game_childs:
                            game_data = self._extract_game_from_json(game, league_desc)
                            if game_data:
                                games.append(game_data)
                                safe_print(f"[ACE DEBUG] Added main game: {game_data.get('away_team', '')} vs {game_data.get('home_team', '')}")
                        else:
                            safe_print(f"[ACE DEBUG] Skipped child game: {game.get('htm', '')} vs {game.get('vtm', '')}")
            
            safe_print(f"[ACE DEBUG] _parse_json_response: {len(games)} main games parsed successfully")
            return games
            
        except json.JSONDecodeError as e:
            safe_print(f"[ACE DEBUG] JSON decode error: {e}")
            # Save the problematic response for debugging
            try:
                with open(self.data_dir / "last_json_error.txt", "w", encoding="utf-8") as f:
                    f.write(json_content)
                safe_print(f"[ACE DEBUG] Saved problematic response to {self.data_dir / 'last_json_error.txt'}")
            except Exception as save_error:
                safe_print(f"[ACE DEBUG] Could not save response: {save_error}")
            return []
        except Exception as e:
            safe_print(f"[ACE DEBUG] Unexpected error parsing JSON: {e}")
            return []
    
    def _extract_game_from_json(self, game_json: Dict, league_desc: str) -> Optional[Dict]:
        """Extract game data from JSON game object"""
        try:
            # Extract basic game info
            home_team = game_json.get('htm', '')
            away_team = game_json.get('vtm', '')
            game_id = game_json.get('idgm', '')
            game_date = game_json.get('gmdt', '')
            game_time = game_json.get('gmtm', '')
            
            if not home_team or not away_team:
                return None
            
            # Additional filtering for problematic team names
            combined_text = f"{home_team} {away_team} {league_desc}".upper()
            
            # Check for tennis props and other problematic patterns
            problematic_patterns = [
                r'\b(?:1ST SET|2ND SET|3RD SET|4TH SET|5TH SET)\b',
                r'\b(?:SETS|GAMES|GAME)\b',
                r'\b(?:ALT\s+)\b',
                r'\b(?:1H\s+)\b',
                r'\b(?:FIRST HALF)\b',
                r'\b(?:SERIES PRICES|SERIES WINNER|SERIES BET)\b',
                r'\b(?:CHAMPIONSHIP|CHAMPION|TITLE)\b',
                r'\b(?:SEASON|REGULAR SEASON|PLAYOFFS)\b',
                r'\b(?:WORLD SERIES|STANLEY CUP|SUPER BOWL)\b',
                r'\b(?:TO WIN|TO ADVANCE|TO MAKE)\b',
                r'\b(?:FUTURES|FUTURE BET|FUTURE MARKET)\b'
            ]
            
            for pattern in problematic_patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    safe_print(f"[ACE DEBUG] Skipped game due to pattern '{pattern}': {home_team} vs {away_team}")
                    return None
            
            # Additional check for problematic team names (reduced filtering)
            problematic_team_keywords = [
                '1ST SET', '2ND SET', '3RD SET', '4TH SET', '5TH SET',  # Tennis props
                'SERIES PRICES', 'SERIES WINNER', 'SERIES BET'  # Series futures
            ]
            if any(keyword in home_team.upper() or keyword in away_team.upper() for keyword in problematic_team_keywords):
                safe_print(f"[ACE DEBUG] Skipped game due to problematic team names: {home_team} vs {away_team}")
                return None
            
            # Get the main game lines
            game_lines = game_json.get('GameLines', [])
            if not game_lines:
                return None
            
            main_line = game_lines[0]  # First line is usually the main line
            
            # Extract and clean odds
            home_odds_raw = {
                'moneyline': main_line.get('hoddsh', ''),
                'spread': main_line.get('hsprdh', ''),
                'total': main_line.get('ovh', '')
            }
            
            away_odds_raw = {
                'moneyline': main_line.get('voddsh', ''),
                'spread': main_line.get('vsprdh', ''),
                'total': main_line.get('unh', '')
            }
            
            # Clean and parse odds using the same logic as _extract_odds_from_row
            home_odds = self._clean_and_parse_odds(home_odds_raw)
            away_odds = self._clean_and_parse_odds(away_odds_raw)
            
            # DEBUG: Log odds for this game
            logging.debug(f"[ACE DEBUG] Odds for {home_team} vs {away_team}: home_odds={home_odds}, away_odds={away_odds}")
            
            # Determine sport from league description
            sport = self._determine_sport_from_league(league_desc)
            
            # Format date/time
            date_time = self._format_json_datetime(game_date, game_time)
            if not date_time:
                date_time = f"{game_date} {game_time}" if game_date and game_time else "Unknown"
            return {
                'game_id': str(game_id),
                'date_time': date_time,
                'away_team': away_team,
                'home_team': home_team,
                'away_odds': away_odds,
                'home_odds': home_odds,
                'sport': sport,
                'league': league_desc
            }
            
        except Exception as e:
            logging.error(f"Error extracting game from JSON: {e}")
            return None
    
    def _determine_sport_from_league(self, league_desc: str) -> str:
        """Determine sport from league description"""
        league_lower = league_desc.lower()
        
        if 'mlb' in league_lower or 'baseball' in league_lower:
            return 'baseball'
        elif 'nfl' in league_lower or 'ncaaf' in league_lower or 'college football' in league_lower or 'football' in league_lower:
            return 'football'
        elif 'nba' in league_lower or 'wnba' in league_lower or 'ncaab' in league_lower or 'college basketball' in league_lower or 'basketball' in league_lower:
            return 'basketball'
        elif 'nhl' in league_lower or 'hockey' in league_lower:
            return 'hockey'
        elif 'soccer' in league_lower or 'football' in league_lower:
            return 'soccer'
        elif 'ufc' in league_lower or 'mma' in league_lower:
            return 'fighting'
        else:
            return 'unknown'
    
    def _format_json_datetime(self, date_str: str, time_str: str) -> str:
        """Format date and time from JSON response"""
        try:
            if date_str and time_str:
                # date_str format: "20250712"
                # time_str format: "22:05:00"
                if len(date_str) == 8:
                    formatted_date = f"{date_str[4:6]}/{date_str[6:8]}"
                    formatted_time = time_str[:5]  # Remove seconds
                    return f"{formatted_date} {formatted_time}"
            return None
        except Exception:
            return None
    
    def _extract_game_from_rows(self, game_rows: List) -> Optional[Dict]:
        """Extract game data from game rows"""
        try:
            if len(game_rows) < 2:
                return None
            
            # First row is away team, second row is home team
            away_row = game_rows[0]
            home_row = game_rows[1]
            
            # Extract team names
            away_team = self._extract_team_name(away_row)
            home_team = self._extract_team_name(home_row)
            
            if not away_team or not home_team:
                return None
            
            # Extract game ID from first team
            away_game_id = self._extract_game_id(away_row)
            home_game_id = self._extract_game_id(home_row)
            
            # Extract date/time
            date_time = self._extract_date_time(away_row, home_row)
            
            # Extract odds for both teams
            away_odds = self._extract_odds_from_row(away_row)
            home_odds = self._extract_odds_from_row(home_row)
            
            game_data = {
                'game_id': away_game_id,
                'date_time': date_time,
                'away_team': away_team,
                'home_team': home_team,
                'away_odds': away_odds,
                'home_odds': home_odds,
                'sport': self._determine_sport(away_team, home_team, away_odds, home_odds)
            }
            
            return game_data
            
        except Exception as e:
            logging.error(f"Error extracting game from rows: {e}")
            return None
    
    def _extract_team_name(self, row) -> Optional[str]:
        """Extract team name from a game row"""
        try:
            team_span = row.find('span', class_='Team')
            if team_span:
                # Get text and remove pitcher info if present
                team_text = team_span.get_text(strip=True)
                # Remove pitcher info in brackets
                team_text = re.sub(r'\[.*?\]', '', team_text).strip()
                return team_text
            return None
        except Exception as e:
            logging.error(f"Error extracting team name: {e}")
            return None
    
    def _extract_game_id(self, row) -> Optional[str]:
        """Extract game ID from a game row"""
        try:
            # Look for the game ID in the second column
            cols = row.find_all('div', class_=re.compile(r'col-xs-\d+'))
            if len(cols) >= 2:
                # Game ID is typically in the second column
                game_id_col = cols[1]
                # Look for visible-xs-inline-block span or direct text
                game_id_span = game_id_col.find('span', class_='visible-xs-inline-block')
                if game_id_span:
                    return game_id_span.get_text(strip=True)
                else:
                    # Direct text in the column
                    text = game_id_col.get_text(strip=True)
                    if text and text.isdigit():
                        return text
            return None
        except Exception as e:
            logging.error(f"Error extracting game ID: {e}")
            return None
    
    def _extract_date_time(self, away_row, home_row) -> Optional[str]:
        """Extract date and time from game rows"""
        try:
            # Date is typically in the first column of away row
            away_cols = away_row.find_all('div', class_=re.compile(r'col-xs-\d+'))
            home_cols = home_row.find_all('div', class_=re.compile(r'col-xs-\d+'))
            
            date = None
            time = None
            
            if away_cols:
                date_text = away_cols[0].get_text(strip=True)
                if date_text and date_text != '&nbsp;':
                    date = date_text
            
            if home_cols:
                time_text = home_cols[0].get_text(strip=True)
                if time_text and 'PM' in time_text or 'AM' in time_text:
                    time = time_text
            
            if date and time:
                return f"{date} {time}"
            elif date:
                return date
            elif time:
                return time
            
            return None
        except Exception as e:
            logging.error(f"Error extracting date/time: {e}")
            return None
    
    def _clean_and_parse_odds(self, odds_dict: Dict) -> Dict:
        """Clean and parse odds dictionary, splitting lines and odds, cleaning &frac entities."""
        cleaned_odds = {}
        
        for key, val in odds_dict.items():
            if not val:
                    continue
                
            val_clean = clean_fraction_entities(val)
            
            # Parse spread/total into line and odds
            if key in ['spread', 'total']:
                # e.g. '+1.5-105', 'u2.5-110', 'o2.25+100'
                import re
                m = re.match(r'([+\-]?[0-9.]+)([+-][0-9]+)', val_clean)
                if m:
                    cleaned_odds[f'{key}_line'] = m.group(1)
                    cleaned_odds[f'{key}_odds'] = m.group(2)
                    logger.info(f"[ACE ODDS PARSE] {key}: '{val}' -> line='{m.group(1)}', odds='{m.group(2)}'")
                else:
                    # Try to parse over/under, e.g. 'o2.5-110', 'u2.25+100'
                    m2 = re.match(r'([ou])([0-9.]+)([+-][0-9]+)', val_clean)
                    if m2:
                        cleaned_odds[f'{key}_ou'] = m2.group(1)
                        cleaned_odds[f'{key}_line'] = m2.group(2)
                        cleaned_odds[f'{key}_odds'] = m2.group(3)
                        logger.info(f"[ACE ODDS PARSE] {key}: '{val}' -> ou='{m2.group(1)}', line='{m2.group(2)}', odds='{m2.group(3)}'")
                    else:
                        cleaned_odds[key] = val_clean
                        logger.warning(f"[ACE ODDS PARSE] Could not parse {key}: '{val}' -> '{val_clean}'")
            else:
                cleaned_odds[key] = val_clean
                
        return cleaned_odds

    def _extract_odds_from_row(self, row) -> Dict:
        """Extract and parse odds from a row, splitting lines and odds, cleaning &frac entities."""
        odds = {}
        # Example fields: 'spread', 'total', 'moneyline'
        for key in ['spread', 'total', 'moneyline']:
            val = row.get(key, '')
            if not val:
                continue
            val_clean = clean_fraction_entities(val)
            # Parse spread/total into line and odds
            if key in ['spread', 'total']:
                # e.g. '+1.5-105', 'u2.5-110', 'o2.25+100'
                import re
                m = re.match(r'([+\-]?[0-9.]+)([+-][0-9]+)', val_clean)
                if m:
                    odds[f'{key}_line'] = m.group(1)
                    odds[f'{key}_odds'] = m.group(2)
                    logger.info(f"[ACE ODDS PARSE] {key}: '{val}' -> line='{m.group(1)}', odds='{m.group(2)}'")
                else:
                    # Try to parse over/under, e.g. 'o2.5-110', 'u2.25+100'
                    m2 = re.match(r'([ou])([0-9.]+)([+-][0-9]+)', val_clean)
                    if m2:
                        odds[f'{key}_ou'] = m2.group(1)
                        odds[f'{key}_line'] = m2.group(2)
                        odds[f'{key}_odds'] = m2.group(3)
                        logger.info(f"[ACE ODDS PARSE] {key}: '{val}' -> ou='{m2.group(1)}', line='{m2.group(2)}', odds='{m2.group(3)}'")
                    else:
                        odds[key] = val_clean
                        logger.warning(f"[ACE ODDS PARSE] Could not parse {key}: '{val}' -> '{val_clean}'")
            else:
                odds[key] = val_clean
        return odds
    
    def _is_total_odds(self, odds_text: str) -> bool:
        """Check if odds text represents total (over/under)"""
        return bool(re.search(r'^[ou]\d+', odds_text, re.IGNORECASE))
    
    def _is_spread_odds(self, odds_text: str) -> bool:
        """Check if odds text represents spread"""
        # Spread odds typically have fractional parts or multiple signs
        return bool(re.search(r'[+-]\d+\.?\d*½?[+-]\d+', odds_text) or  # -1½+118 or +7-115
                   re.search(r'^[+-]\d+\.?\d*½$', odds_text))  # -1½ or +7.5
    
    def _is_moneyline_odds(self, odds_text: str) -> bool:
        """Check if odds text represents moneyline"""
        # Moneyline odds are pure numbers with + or - (no fractions, no letters)
        return bool(re.search(r'^[+-]\d+$', odds_text))
    
    def _determine_sport(self, away_team: str, home_team: str, away_odds: Dict, home_odds: Dict) -> str:
        """Determine sport based on team names and odds structure"""
        try:
            # Check for specific sport indicators
            if 'BLUE JAYS' in away_team or 'ATHLETICS' in away_team:
                return 'baseball'
            elif 'TIMBERWOLVES' in away_team or 'NUGGETS' in away_team:
                return 'basketball'
            elif 'COWBOYS' in away_team or 'EAGLES' in away_team:
                return 'football'
            elif 'PARIS SAINT-GERMAIN' in away_team or 'CHELSEA FC' in away_team:
                return 'soccer'
            elif 'LEWIS' in away_team or 'TEIXEIRA' in away_team:
                return 'fighting'
            
            # Default classification
            return 'unknown'
            
        except Exception as e:
            logging.error(f"Error determining sport: {e}")
            return 'unknown'
    
    def scrape_games(self, league_ids: str = None) -> List[Dict]:
        """Scrape games from Ace with session validation"""
        try:
            # Check if we're still logged in by making a test request
            safe_print("[ACE DEBUG] Checking session validity...")
            
            # Use the proper session validation method
            if not self._validate_session():
                safe_print("[ACE DEBUG] Session expired, re-logging in...")
                if not self.login():
                    safe_print("[ACE DEBUG] Failed to re-login")
                    return []
                safe_print("[ACE DEBUG] Successfully re-logged in")
            else:
                safe_print("[ACE DEBUG] Session is still valid")
            
            # Now proceed with scraping
            safe_print("[ACE DEBUG] Starting game scraping...")
            
            # Get league IDs if not provided
            if not league_ids:
                safe_print("[ACE DEBUG] No league IDs provided, getting combined league IDs...")
                league_ids = self.get_combined_league_ids()
            safe_print(f"[ACE DEBUG] scrape_games using league IDs: {league_ids}")
            
            if not league_ids:
                safe_print("[ACE DEBUG] No valid leagues to scrape, aborting.")
                return []
            
            safe_print(f"[ACE DEBUG] Using league IDs: {league_ids}")
            
            # Fetch odds data
            safe_print("[ACE DEBUG] Fetching odds data...")
            odds_data = self.fetch_odds_data(league_ids)
            
            if not odds_data:
                safe_print("[ACE DEBUG] No odds data received")
                return []
            
            safe_print(f"[ACE DEBUG] Received odds data length: {len(odds_data) if odds_data else 0}")
            
            # Parse the odds data
            safe_print("[ACE DEBUG] Parsing JSON response...")
            games = self._parse_json_response(odds_data)
            
            if not games:
                safe_print("[ACE DEBUG] No games parsed from odds data")
                return []
            
            safe_print(f"[ACE DEBUG] Parsed {len(games)} games from odds data")
            
            # Filter games
            safe_print("[ACE DEBUG] Filtering games...")
            filtered_games = []
            for i, game in enumerate(games):
                if i < 5:  # Log first 5 games for debugging
                    safe_print(f"[ACE DEBUG] Checking game {i+1}: {game.get('away_team', '')} vs {game.get('home_team', '')}")
                
                if self._should_include_game(game):
                    filtered_games.append(game)
                    if len(filtered_games) <= 5:  # Log first 5 included games
                        safe_print(f"[ACE DEBUG] Included game {len(filtered_games)}: {game.get('away_team', '')} vs {game.get('home_team', '')}")
            
            safe_print(f"[ACE DEBUG] Filtered {len(games)} games down to {len(filtered_games)} valid games")
            
            return filtered_games
            
        except Exception as e:
            safe_print(f"[ACE DEBUG] Error in scrape_games: {e}")
            import traceback
            safe_print(f"[ACE DEBUG] Traceback: {traceback.format_exc()}")
            return []
    
    def _should_include_game(self, game: Dict) -> bool:
        """Check if a game should be included (not a prop, future, etc.)"""
        try:
            # Get team names and description
            away_team = game.get('away_team', '').upper()
            home_team = game.get('home_team', '').upper()
            league = game.get('league', '').upper()
            description = game.get('description', '').upper()
            
            # Combine all text for checking
            all_text = f"{away_team} {home_team} {league} {description}".upper()
            
            # Only use exclusion_patterns (regex) for props/futures/esports
            for pattern in self.exclusion_patterns:
                if re.search(pattern, all_text, re.IGNORECASE):
                    safe_print(f"[ACE GAME FILTER] Excluded game due to pattern '{pattern}': {away_team} vs {home_team}")
                    return False
            
            # Exclude futures, championships, and season-long bets
            futures_keywords = [
                'CHAMPIONSHIP WINNER', 'WORLD SERIES WINNER', 'STANLEY CUP WINNER', 
                'REGULAR SEASON WINS', 'DIVISION WINNER', 'CONFERENCE WINNER',
                'COIN TOSS', 'SUPER BOWL', 'RSW', 'SEASON WINS', 'SERIES PRICES',
                'SERIES WINNER', 'SERIES BET', 'SERIES HANDICAP', 'SERIES TOTAL'
            ]
            for keyword in futures_keywords:
                if keyword in all_text:
                    safe_print(f"[ACE GAME FILTER] Excluded futures/championship: {away_team} vs {home_team} (contains '{keyword}')")
                    return False
            
            # Additional check for series prices in league name
            if 'SERIES PRICES' in league:
                safe_print(f"[ACE GAME FILTER] Excluded series prices: {away_team} vs {home_team} (league: {league})")
                return False
            
            # Temporarily disable some aggressive filters to get more games
            # Only exclude the most obvious props/futures
            
            # Check for valid team names (must have at least 2 characters)
            if len(away_team.strip()) < 2 or len(home_team.strip()) < 2:
                safe_print(f"[ACE GAME FILTER] Excluded game due to short team names: {away_team} vs {home_team}")
                return False
            
            # Check for date filtering (only include games within next 7 days)
            game_date = game.get('date_time')
            if game_date:
                try:
                    from datetime import datetime, timedelta
                    if ' ' in game_date and len(game_date.split(' ')) == 2:
                        date_part, time_part = game_date.split(' ')
                        if '/' in date_part and len(date_part.split('/')) == 2:
                            month, day = date_part.split('/')
                            current_year = datetime.now().year
                            date_part = f"{current_year}/{month}/{day}"
                        try:
                            game_dt = datetime.strptime(f"{date_part} {time_part}", "%Y/%m/%d %H:%M")
                        except ValueError:
                            game_dt = datetime.strptime(f"{date_part} {time_part}", "%m/%d %H:%M")
                            game_dt = game_dt.replace(year=datetime.now().year)
                    else:
                        game_dt = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
                    now = datetime.now()
                    if game_dt > now + timedelta(days=7):
                        safe_print(f"[ACE GAME FILTER] Excluded game due to future date: {away_team} vs {home_team} ({game_date})")
                        return False
                except Exception as e:
                    safe_print(f"[ACE GAME FILTER] Could not parse date {game_date}: {e}")
            safe_print(f"[ACE GAME FILTER] Included game: {away_team} vs {home_team}")
            return True
        except Exception as e:
            safe_print(f"[ACE GAME FILTER] Error checking game: {e}")
            return False
    
    def run_ace_calculations(self) -> Dict[str, Any]:
        """Run Ace calculations - scrape Ace games and match to Pinnacle events"""
        try:
            safe_print("[ACE] Starting Ace calculations - scraping Ace games and matching to Pinnacle...")

            # Always start a new session and login fresh (to match test behavior)
            import requests
            self.session = requests.Session()
            self.logged_in = False
            safe_print("[ACE] Forced new session and login for production run")
            if not self.login():
                safe_print("[ACE] Login failed at start of run_ace_calculations")
                return {"error": "Login failed", "status": "error"}

            # Step 1: Scrape Ace games
            safe_print("[ACE] Step 1: Scraping Ace games...")
            ace_games = self.scrape_games()

            if not ace_games:
                safe_print("[ACE] No Ace games scraped")
                return {"error": "No Ace games found", "status": "error"}

            safe_print(f"[ACE] Scraped {len(ace_games)} Ace games")
            
            # Show sample of scraped games
            if ace_games:
                safe_print("[ACE] Sample of scraped games:")
                for i, game in enumerate(ace_games[:3]):
                    safe_print(f"[ACE]   {i+1}. {game.get('away_team', '')} vs {game.get('home_team', '')} ({game.get('league', '')})")
            
            # Step 2: Get Pinnacle event IDs for matching
            safe_print("[ACE] Step 2: Fetching Pinnacle event IDs...")
            event_ids = self._fetch_pinnacle_event_ids()
            
            if not event_ids:
                safe_print("[ACE] No Pinnacle event IDs available")
                return {"error": "No Pinnacle event IDs available", "status": "error"}
            
            safe_print(f"[ACE] Fetched {len(event_ids)} Pinnacle event IDs")
            
            # Filter out corners and props markets
            event_ids = self._filter_out_corners_and_props(event_ids)
            safe_print(f"[ACE] After filtering corners/props: {len(event_ids)} event IDs remaining")
            
            # Step 3: Create hash maps for optimized matching
            safe_print("[ACE] Step 3: Creating hash maps for optimized matching...")
            event_hash_maps = self._create_event_hash_map(event_ids)
            
            # Step 4: Match Ace games to Pinnacle events and calculate EV
            safe_print("[ACE] Step 4: Matching Ace games to Pinnacle events...")
            matched_markets = []
            total_matched = 0
            total_with_ev = 0
            
            safe_print(f"[ACE] Attempting to match {len(ace_games)} Ace games to Pinnacle events...")
            
            for i, game in enumerate(ace_games):
                if i < 5:  # Log first 5 matching attempts
                    safe_print(f"[ACE] Matching game {i+1}: {game.get('away_team', '')} vs {game.get('home_team', '')}")
                
                try:
                    matched_event_id = self._match_game_to_event_optimized(game, event_hash_maps)
                    if matched_event_id:
                        total_matched += 1
                        if i < 5:  # Log first 5 successful matches
                            safe_print(f"[ACE] [SUCCESS] Matched game {i+1} to event ID: {matched_event_id}")
                        
                                                # Get Pinnacle odds for this event
                        pinnacle_data = self._get_pinnacle_odds(matched_event_id)
                        if pinnacle_data:
                            # Calculate EV for each market
                            ev_results = self._calculate_ev_for_game(game, pinnacle_data)
                            if ev_results:
                                for result in ev_results:
                                    # Get team names from the matched event data (not pinnacle_data)
                                    # Find the matched event to get proper team names
                                    matched_event = None
                                    for category in ['exact_teams', 'clean_teams', 'partial_teams']:
                                        if category in event_hash_maps:
                                            for event_list in event_hash_maps[category].values():
                                                for event in event_list:
                                                    if event.get('event_id') == matched_event_id:
                                                        matched_event = event
                                                        break
                                                if matched_event:
                                                    break
                                            if matched_event:
                                                break
                                    
                                    # Use Pinnacle team names from the matched event if available
                                    if matched_event:
                                        pinnacle_away = matched_event.get('away_team', '')
                                        pinnacle_home = matched_event.get('home_team', '')
                                        if pinnacle_away and pinnacle_home:
                                            matchup = f"{pinnacle_away} vs {pinnacle_home}"
                                        else:
                                            # Fallback to ACE team names
                                            ace_away = game.get('away_team', '')
                                            ace_home = game.get('home_team', '')
                                            if ace_away and ace_home:
                                                matchup = f"{ace_away} vs {ace_home}"
                                            else:
                                                # Skip this market if we can't get team names
                                                continue
                                    else:
                                        # Fallback to ACE team names
                                        ace_away = game.get('away_team', '')
                                        ace_home = game.get('home_team', '')
                                        if ace_away and ace_home:
                                            matchup = f"{ace_away} vs {ace_home}"
                                        else:
                                            # Skip this market if we can't get team names
                                            continue
                                    
                                    # Use the formatted bet description from analyze_markets_for_ev
                                    bet_description = result.get("bet", "")
                                    
                                    # Format exactly like Buckeye for frontend compatibility
                                    market = {
                                        "matchup": matchup,
                                        "league": game.get("league", ""),
                                        "bet": bet_description,
                                        "betbck_odds": result.get("betbck_odds", ""),
                                        "pinnacle_nvp": result.get("pinnacle_nvp", ""),
                                        "pinnacle_limit": result.get("pinnacle_limit"),
                                        "ev": result.get("ev", "0%"),
                                        "ev_val": float(str(result.get('ev', '0')).replace('%', '')) / 100 if result.get('ev') else 0,
                                        "start_time": game.get("date_time", ""),
                                        "event_id": matched_event_id
                                    }
                                    matched_markets.append(market)
                                    if float(str(result.get('ev', '0')).replace('%', '')) > 0:
                                        total_with_ev += 1
                                        if total_with_ev <= 3:  # Log first 3 positive EV markets
                                            safe_print(f"[ACE] [SUCCESS] Found positive EV market: {market.get('bet', '')} EV: {market.get('ev', '')}")
                        else:
                            # Skip this game if no Pinnacle data available
                            continue
                    elif i < 5:  # Log first 5 failed matches
                        safe_print(f"[ACE] [FAILED] No match found for game {i+1}")
                except Exception as match_error:
                    safe_print(f"[ACE] Error matching game {i+1}: {match_error}")
                    continue
            
            # Calculate statistics
            match_rate = (total_matched / len(ace_games) * 100) if ace_games else 0
            ev_rate = (total_with_ev / total_matched * 100) if total_matched > 0 else 0
            
            safe_print(f"[ACE] Matching complete: {total_matched}/{len(ace_games)} games matched ({match_rate:.1f}%)")
            safe_print(f"[ACE] EV calculation complete: {total_with_ev} markets with positive EV ({ev_rate:.1f}%)")
            
            # Show ALL markets (no filtering by EV percentage) - user wants to see everything
            filtered_markets = matched_markets.copy()
            
            safe_print(f"[ACE] Showing ALL {len(filtered_markets)} markets (no EV filtering)")
            
            # Sort markets by EV (highest first) and limit to top 150
            filtered_markets.sort(key=lambda x: float(x.get('ev', '0').replace('%', '')), reverse=True)
            top_50_markets = filtered_markets[:150]  # Top 150 markets for backend processing
            
            # Count ALL EV markets (including negative EV)
            total_with_ev_filtered = len(filtered_markets)
            positive_ev_count = len([m for m in filtered_markets if float(m.get('ev', '0').replace('%', '')) > 0])
            ev_rate_filtered = (total_with_ev_filtered / total_matched * 100) if total_matched > 0 else 0
            
            safe_print(f"[ACE] Total markets: {len(filtered_markets)}, Positive EV: {positive_ev_count}, All EV: {total_with_ev_filtered} ({ev_rate_filtered:.1f}%)")
            
            # Save results in Buckeye format
            ace_results = {
                "events": top_50_markets,  # Top markets in Buckeye format
                "last_run": datetime.now().isoformat(),
                "total_processed": len(ace_games),
                "total_matched": total_matched,
                "total_with_ev": total_with_ev_filtered,
                "match_rate": match_rate,
                "ev_rate": ev_rate_filtered
            }
            
            with open(self.results_file, 'w') as f:
                json.dump(ace_results, f, indent=2)
            
            safe_print(f"[ACE] Saved {len(top_50_markets)} markets to {self.results_file}")
            
            return {
                "status": "success",
                "message": f"Processed {len(ace_games)} Ace games, matched {total_matched}, found {total_with_ev_filtered} with realistic EV",
                "events": top_50_markets,  # Top 50 markets in Buckeye format
                "total_processed": len(ace_games),
                "total_matched": total_matched,
                "total_with_ev": total_with_ev_filtered,
                "match_rate": match_rate,
                "ev_rate": ev_rate_filtered,
                "last_update": ace_results["last_run"]
            }
            
        except Exception as e:
            safe_print(f"[ACE] Error in calculations: {e}")
            import traceback
            safe_print(f"[ACE] Traceback: {traceback.format_exc()}")
            return {"error": str(e), "status": "error"}
    
    def _fetch_pinnacle_event_ids(self) -> List[Dict]:
        """Load event IDs from saved file (like Buckeye) instead of hitting Arcadia"""
        try:
            safe_print("[ACE DEBUG] Loading event IDs from saved file...")
            
            # Use the existing Buckeye logic to load saved event IDs
            from buckeye_scraper import BuckeyeScraper
            
            # Create a minimal config for Buckeye
            config = {"debug": True}
            buckeye = BuckeyeScraper(config)
            
            # Try to load saved event IDs first
            saved_event_ids = buckeye.load_event_ids()
            
            if saved_event_ids:
                safe_print(f"[ACE DEBUG] Loaded {len(saved_event_ids)} saved event IDs")
                
                # Use the actual team names from the saved file
                event_dicts = []
                for event_data in saved_event_ids:
                    if isinstance(event_data, dict):
                        event_dicts.append({
                            "event_id": event_data.get("event_id"),
                            "home_team": event_data.get("home_team", ""),
                            "away_team": event_data.get("away_team", "")
                        })
                    else:
                        # Fallback for simple event_id format
                        event_dicts.append({
                            "event_id": event_data,
                            "home_team": f"Team_{event_data}_Home",
                            "away_team": f"Team_{event_data}_Away"
                        })
                
                safe_print(f"[ACE DEBUG] Converted {len(event_dicts)} event IDs to dict format")
                return event_dicts
            else:
                safe_print("[ACE DEBUG] No saved event IDs found, fetching from Arcadia...")
                # Fallback to fetching from Arcadia if no saved file
                event_dicts = buckeye.get_todays_event_ids()
                safe_print(f"[ACE DEBUG] Fetched {len(event_dicts)} event IDs from Arcadia API")
                return event_dicts
                
        except Exception as e:
            safe_print(f"[ACE DEBUG] Error loading event IDs: {e}")
            import traceback
            safe_print(f"[ACE DEBUG] Traceback: {traceback.format_exc()}")
            return []
    
    def _filter_out_corners_and_props(self, event_dicts: List[Dict]) -> List[Dict]:
        """Filter out corners, props, and other non-game markets"""
        try:
            safe_print("[ACE DEBUG] Filtering out corners and props markets...")
            
            # Keywords that indicate corners, props, or other non-game markets
            corners_props_keywords = [
                'corners', 'corner', 'cards', 'card', 'shots', 'shot', 'fouls', 'foul',
                'offsides', 'offside', 'throw-ins', 'throw-in', 'free kicks', 'free kick',
                'penalties', 'penalty', 'yellow cards', 'red cards', 'bookings', 'booking',
                'assists', 'assist', 'goals', 'goal', 'saves', 'save', 'passes', 'pass',
                'tackles', 'tackle', 'interceptions', 'interception', 'clearances', 'clearance',
                'crosses', 'cross', 'headers', 'header', 'dribbles', 'dribble', 'blocks', 'block',
                'first half', 'second half', '1h', '2h', 'quarter', 'period', 'set', 'game',
                'player', 'team', 'season', 'tournament', 'championship', 'cup', 'league'
            ]
            
            filtered_events = []
            removed_count = 0
            
            for event in event_dicts:
                event_id = event.get('event_id', '')
                home_team = event.get('home_team', '').lower()
                away_team = event.get('away_team', '').lower()
                
                # Skip filtering if these are placeholder team names (from saved event IDs)
                if home_team.startswith('team_') and away_team.startswith('team_'):
                    filtered_events.append(event)
                    continue
                
                # Check if team names contain corners/props keywords
                is_corners_or_props = False
                for keyword in corners_props_keywords:
                    if keyword in home_team or keyword in away_team:
                        is_corners_or_props = True
                        safe_print(f"[ACE DEBUG] Filtered out event {event_id}: {away_team} vs {home_team} (contains '{keyword}')")
                        break
                
                if not is_corners_or_props:
                    filtered_events.append(event)
                else:
                    removed_count += 1
            
            safe_print(f"[ACE DEBUG] Filtered out {removed_count} corners/props events, kept {len(filtered_events)} game events")
            return filtered_events
            
        except Exception as e:
            safe_print(f"[ACE DEBUG] Error filtering corners/props: {e}")
            return event_dicts
    
    def _filter_games(self, games: List[Dict]) -> List[Dict]:
        """Filter out games that are props, futures, etc."""
        try:
            filtered_games = []
            
            for game in games:
                # Check if game should be included
                if self._should_include_game(game):
                    filtered_games.append(game)
            
            safe_print(f"[ACE] Filtered {len(games)} games down to {len(filtered_games)} valid games")
            return filtered_games
            
        except Exception as e:
            safe_print(f"[ACE] Error filtering games: {e}")
            return []
    
    def _create_event_hash_map(self, event_ids: List[Dict]) -> Dict[str, List[Dict]]:
        """Create hash maps for fast exact matching with robust error handling"""
        try:
            hash_maps = {
                'exact_teams': {},      # Original team names
                'clean_teams': {},      # Cleaned team names  
                'partial_teams': {}     # For partial matching
            }
            
            if not event_ids or not isinstance(event_ids, list):
                safe_print("[ACE DEBUG] No valid event IDs provided for hash map creation")
                return hash_maps
            
            safe_print(f"[ACE DEBUG] Creating hash maps for {len(event_ids)} events")
            
            for event in event_ids:
                if not isinstance(event, dict):
                    continue
                    
                event_id = event.get('event_id')
                away_team = event.get('away_team', '').strip()
                home_team = event.get('home_team', '').strip()
                
                if not event_id or not away_team or not home_team:
                    continue
                
                # Create exact match key
                exact_key = f"{away_team}|{home_team}"
                if exact_key not in hash_maps['exact_teams']:
                    hash_maps['exact_teams'][exact_key] = []
                hash_maps['exact_teams'][exact_key].append(event)
                
                # Create clean match key
                clean_away = clean_pod_team_name_for_search(away_team)
                clean_home = clean_pod_team_name_for_search(home_team)
                clean_key = f"{clean_away}|{clean_home}"
                
                if clean_key not in hash_maps['clean_teams']:
                    hash_maps['clean_teams'][clean_key] = []
                hash_maps['clean_teams'][clean_key].append(event)
                
                # Add to partial matching (by first word of each team) - FIXED: Add bounds checking
                away_words = clean_away.split()
                home_words = clean_home.split()
                
                # FIX: Check if both teams have at least one word before accessing [0]
                if away_words and home_words and len(away_words) > 0 and len(home_words) > 0:
                    partial_key = f"{away_words[0]}|{home_words[0]}"
                    if partial_key not in hash_maps['partial_teams']:
                        hash_maps['partial_teams'][partial_key] = []
                    hash_maps['partial_teams'][partial_key].append(event)
            
            safe_print(f"[ACE DEBUG] Hash maps created: {len(hash_maps['exact_teams'])} exact, {len(hash_maps['clean_teams'])} clean, {len(hash_maps['partial_teams'])} partial")
            return hash_maps
            
        except Exception as e:
            safe_print(f"[ACE DEBUG] Error creating hash maps: {e}")
            import traceback
            safe_print(f"[ACE DEBUG] Traceback: {traceback.format_exc()}")
            return {
                'exact_teams': {},
                'clean_teams': {}, 
                'partial_teams': {}
            }
    
    def _match_game_to_event_optimized(self, game: Dict, event_hash_maps: Dict) -> Optional[str]:
        """Use Buckeye's relaxed team matching logic instead of strict 70% threshold"""
        try:
            # Validate inputs
            if not isinstance(game, dict) or not isinstance(event_hash_maps, dict):
                safe_print("[ACE MATCH DEBUG] Invalid input types for matching")
                return None
            
            ace_away = game.get('away_team', '').strip()
            ace_home = game.get('home_team', '').strip()
            
            if not ace_away or not ace_home:
                safe_print(f"[ACE MATCH DEBUG] Missing team names: away='{ace_away}', home='{ace_home}'")
                return None
            
            # Clean team names for matching (like Buckeye)
            def ace_clean_team_name(name: str) -> str:
                if not name:
                    return ""
                # Just lowercase and basic cleanup
                cleaned = name.lower().strip()
                # Remove common suffixes but keep more of the original name
                suffixes_to_remove = ['fc', 'sc', 'bk', 'sk', 'ac', 'as', 'fk', 'cd', 'ca', 'afc', 'cfr', 'kc', 'scr']
                for suffix in suffixes_to_remove:
                    if cleaned.endswith(f' {suffix}'):
                        cleaned = cleaned[:-len(f' {suffix}')].strip()
                return cleaned
            
            clean_ace_away = ace_clean_team_name(ace_away)
            clean_ace_home = ace_clean_team_name(ace_home)
            
            safe_print(f"[ACE MATCH] ACE cleaned: away='{clean_ace_away}', home='{clean_ace_home}'")
            
            # Buckeye-style relaxed team matching
            def ace_team_match(team1: str, team2: str) -> bool:
                """More relaxed team matching for ACE scraper (like Buckeye)"""
                if not team1 or not team2:
                    return False
                # Exact match
                if team1 == team2:
                    return True
                # One team contains the other (partial match)
                if team1 in team2 or team2 in team1:
                    return True
                # Check for common variations
                variations = [
                    ('new york', 'ny'),
                    ('los angeles', 'la'),
                    ('st louis', 'st. louis'),
                    ('tottenham hotspur', 'tottenham'),
                    ('paris saint germain', 'psg'),
                    ('inter milan', 'inter'),
                    ('manchester united', 'man utd'),
                    ('manchester city', 'man city'),
                    ('real madrid', 'madrid'),
                    ('barcelona', 'barca')
                ]
                for var1, var2 in variations:
                    if (team1 == var1 and team2 == var2) or (team1 == var2 and team2 == var1):
                        return True
                return False
            
            # Try to find matches in all events
            all_events = []
            for events_list in event_hash_maps.get('exact_teams', {}).values():
                all_events.extend(events_list)
            for events_list in event_hash_maps.get('clean_teams', {}).values():
                all_events.extend(events_list)
            for events_list in event_hash_maps.get('partial_teams', {}).values():
                all_events.extend(events_list)
            
            # Find best match using Buckeye logic
            best_match = None
            best_score = 0
            
            for event in all_events:
                if not isinstance(event, dict):
                    continue
                    
                pinnacle_away = event.get('away_team', '').strip()
                pinnacle_home = event.get('home_team', '').strip()
                
                if not pinnacle_away or not pinnacle_home:
                    continue
                
                # Clean Pinnacle team names
                clean_pinnacle_away = ace_clean_team_name(pinnacle_away)
                clean_pinnacle_home = ace_clean_team_name(pinnacle_home)
                
                # Check if teams match (relaxed like Buckeye)
                away_match = ace_team_match(clean_ace_away, clean_pinnacle_away)
                home_match = ace_team_match(clean_ace_home, clean_pinnacle_home)
                
                if away_match and home_match:
                    # Perfect match
                    safe_print(f"[ACE MATCH] Perfect match found: {ace_away} vs {ace_home} -> {pinnacle_away} vs {pinnacle_home}")
                    return event.get('event_id')
                elif away_match and ace_team_match(clean_ace_away, clean_pinnacle_home) and ace_team_match(clean_ace_home, clean_pinnacle_away):
                    # Teams are reversed
                    safe_print(f"[ACE MATCH] Reversed match found: {ace_away} vs {ace_home} -> {pinnacle_home} vs {pinnacle_away}")
                    return event.get('event_id')
                else:
                    # Calculate similarity score for partial matches
                    away_similarity = self._calculate_team_similarity(clean_ace_away, clean_pinnacle_away)
                    home_similarity = self._calculate_team_similarity(clean_ace_home, clean_pinnacle_home)
                    match_score = min(away_similarity, home_similarity)
                    
                    if match_score > best_score and match_score >= 50:  # Lowered threshold like Buckeye
                        best_score = match_score
                        best_match = event
            
            if best_match and isinstance(best_match, dict):
                safe_print(f"[ACE MATCH] Partial match found: {ace_away} vs {ace_home} -> {best_match.get('away_team', '')} vs {best_match.get('home_team', '')} (score: {best_score:.1f}%)")
                return best_match.get('event_id')
            
            safe_print(f"[ACE MATCH] No match found for {ace_away} vs {ace_home}")
            return None
            
        except Exception as e:
            safe_print(f"[ACE MATCH] Error in matching: {e}")
            import traceback
            safe_print(f"[ACE MATCH] Traceback: {traceback.format_exc()}")
            return None

    def _calculate_team_similarity(self, team1: str, team2: str) -> float:
        """Calculate similarity between two team names using fuzzy matching"""
        try:
            if not team1 or not team2:
                return 0.0
            
            # Use fuzzywuzzy if available, otherwise use simple string matching
            try:
                from fuzzywuzzy import fuzz
                # Try different fuzzy matching methods
                ratio = fuzz.ratio(team1.lower(), team2.lower())
                partial_ratio = fuzz.partial_ratio(team1.lower(), team2.lower())
                token_sort_ratio = fuzz.token_sort_ratio(team1.lower(), team2.lower())
                token_set_ratio = fuzz.token_set_ratio(team1.lower(), team2.lower())
                
                # Use the best score
                best_score = max(ratio, partial_ratio, token_sort_ratio, token_set_ratio)
                return best_score
                
            except ImportError:
                # Fallback to simple string matching
                team1_lower = team1.lower()
                team2_lower = team2.lower()
                
                if team1_lower == team2_lower:
                    return 100.0
                elif team1_lower in team2_lower or team2_lower in team1_lower:
                    return 80.0
                else:
                    # Simple character-based similarity
                    common_chars = sum(1 for c in team1_lower if c in team2_lower)
                    total_chars = max(len(team1_lower), len(team2_lower))
                    return (common_chars / total_chars) * 100 if total_chars > 0 else 0.0
                    
        except Exception as e:
            logger.error(f"[ACE MATCH] Error calculating similarity: {e}")
            return 0.0
    
    def _get_pinnacle_odds(self, event_id: str) -> Optional[Dict]:
        """Get Pinnacle odds for an event ID using the same logic as Buckeye"""
        try:
            safe_print(f"[ACE EV] Attempting to fetch Pinnacle odds for event ID: {event_id}")
            
            # Add timeout protection using threading (Windows compatible)
            import threading
            import queue
            
            result_queue = queue.Queue()
            
            def fetch_with_timeout():
                try:
                    pinnacle_result = fetch_live_pinnacle_event_odds(event_id)
                    result_queue.put(("success", pinnacle_result))
                except Exception as e:
                    result_queue.put(("error", e))
            
            # Start the fetch in a separate thread
            fetch_thread = threading.Thread(target=fetch_with_timeout)
            fetch_thread.daemon = True
            fetch_thread.start()
            
            # Wait for result with timeout
            try:
                result_type, result_data = result_queue.get(timeout=10)  # 10 second timeout
                
                if result_type == "error":
                    raise result_data
                
                pinnacle_result = result_data
                
            except queue.Empty:
                safe_print(f"[ACE EV] Timeout fetching Pinnacle odds for event {event_id}")
                return None
            
            safe_print(f"[ACE EV] Pinnacle result: {pinnacle_result}")
            
            if pinnacle_result and pinnacle_result.get('success') == True:
                processed_data = process_event_odds_for_display(pinnacle_result.get('data'))
                safe_print(f"[ACE EV] Processed Pinnacle data: {processed_data}")
                return processed_data
            else:
                safe_print(f"[ACE EV] Pinnacle fetch failed or returned no data for event {event_id}")
            return None
            
        except Exception as e:
            safe_print(f"[ACE EV] Error fetching Pinnacle odds for event {event_id}: {e}")
            return None
    
    def _match_ace_to_pinnacle(self, ace_game: Dict, pinnacle_data: Dict) -> Optional[Dict]:
        """Match Ace game to Pinnacle data using robust team name matching"""
        try:
            # Clean team names for matching
            ace_home = clean_pod_team_name_for_search(ace_game.get('home_team', ''))
            ace_away = clean_pod_team_name_for_search(ace_game.get('away_team', ''))
            
            logger.info(f"[ACE MATCH] Attempting to match: '{ace_home}' vs '{ace_away}'")
            
            # Validate pinnacle_data structure
            if not pinnacle_data:
                logger.warning("[ACE MATCH] Pinnacle data is None or empty")
                return None
                
            # Extract team names from Pinnacle data (top-level event, not periods)
            # Defensive: try both the old and new way, log both
            event_data = None
            if isinstance(pinnacle_data, dict):
                # Try multiple possible data structures
                if 'data' in pinnacle_data and isinstance(pinnacle_data['data'], dict):
                    if 'data' in pinnacle_data['data']:
                        event_data = pinnacle_data['data']['data']
                        logger.debug("[ACE MATCH] Found data.data.data structure")
                    else:
                        event_data = pinnacle_data['data']
                        logger.debug("[ACE MATCH] Found data.data structure")
                else:
                    event_data = pinnacle_data
                    logger.debug("[ACE MATCH] Using pinnacle_data directly")
            else:
                logger.warning(f"[ACE MATCH] Pinnacle data is not a dict: {type(pinnacle_data)}")
                return None
                
            if not event_data:
                logger.warning("[ACE MATCH] Could not extract event data from Pinnacle response")
                logger.debug(f"[ACE MATCH] Pinnacle data structure: {type(pinnacle_data)}")
                if isinstance(pinnacle_data, dict):
                    logger.debug(f"[ACE MATCH] Pinnacle keys: {list(pinnacle_data.keys())}")
                return None
                
            # Extract team names with better error handling
            raw_home = event_data.get('home', '')
            raw_away = event_data.get('away', '')
            
            if not raw_home or not raw_away:
                logger.warning(f"[ACE MATCH] Missing team names in Pinnacle data: home='{raw_home}', away='{raw_away}'")
                logger.debug(f"[ACE MATCH] Available keys in event_data: {list(event_data.keys())}")
                return None
            
            # Clean Pinnacle team names
            pinnacle_home = clean_pod_team_name_for_search(raw_home)
            pinnacle_away = clean_pod_team_name_for_search(raw_away)
            
            logger.info(f"[ACE MATCH] Pinnacle teams: '{pinnacle_home}' vs '{pinnacle_away}'")
            
            # Try exact match first
            if (ace_home == pinnacle_home and ace_away == pinnacle_away) or \
               (ace_home == pinnacle_away and ace_away == pinnacle_home):
                logger.info(f"[ACE MATCH] Exact match found!")
                return event_data
            
            # Try fuzzy matching
            home_similarity = self._calculate_team_similarity(ace_home, pinnacle_home)
            away_similarity = self._calculate_team_similarity(ace_away, pinnacle_away)
            
            # Also try reversed matching
            home_away_similarity = self._calculate_team_similarity(ace_home, pinnacle_away)
            away_home_similarity = self._calculate_team_similarity(ace_away, pinnacle_home)
            
            logger.info(f"[ACE MATCH] Similarity scores - Normal: H={home_similarity:.1f}, A={away_similarity:.1f} | Reversed: H={home_away_similarity:.1f}, A={away_home_similarity:.1f}")
            
            # Check if we have a good match (either normal or reversed)
            normal_match_score = min(home_similarity, away_similarity)
            reversed_match_score = min(home_away_similarity, away_home_similarity)
            
            if normal_match_score >= 80 or reversed_match_score >= 80:
                if normal_match_score >= reversed_match_score:
                    logger.info(f"[ACE MATCH] Fuzzy match found (normal order): {normal_match_score:.1f}")
                    return event_data
                else:
                    logger.info(f"[ACE MATCH] Fuzzy match found (reversed order): {reversed_match_score:.1f}")
                    # Return reversed data
                    reversed_data = event_data.copy()
                    reversed_data['home'] = raw_away
                    reversed_data['away'] = raw_home
                    return reversed_data
            
            logger.warning(f"[ACE MATCH] No match found for {ace_home} vs {ace_away}")
            return None
            
        except Exception as e:
            logger.error(f"[ACE MATCH] Error in matching: {e}")
            import traceback
            logger.error(f"[ACE MATCH] Traceback: {traceback.format_exc()}")
            return None

    def _extract_pinnacle_odds(self, pinnacle_data: Dict) -> Dict:
        """Extract all NVP American odds and lines from all Pinnacle periods, robust like Buckeye."""
        try:
            # Use the same approach as Buckeye - let odds_processing handle it
            from odds_processing import fetch_live_pinnacle_event_odds
            
            # If we have an event_id, fetch fresh data
            event_id = pinnacle_data.get('event_id')
            if event_id:
                logger.info(f"[ACE PINNACLE ODDS] Fetching fresh odds for event {event_id}")
                fresh_data = fetch_live_pinnacle_event_odds(event_id)
                if fresh_data and fresh_data.get("status") == "success":
                    pinnacle_data = fresh_data.get("data", {})
            
            # Defensive: handle both processed and raw structures
            event = None
            if 'data' in pinnacle_data and isinstance(pinnacle_data['data'], dict):
                if 'data' in pinnacle_data['data']:
                    event = pinnacle_data['data']['data']
                else:
                    event = pinnacle_data['data']
            else:
                event = pinnacle_data

            periods = event.get('periods', {}) if event else {}
            
            # Debug logging
            logger.info(f"[ACE PINNACLE ODDS DEBUG] Raw pinnacle_data structure: {json.dumps(pinnacle_data, indent=2)}")
            logger.info(f"[ACE PINNACLE ODDS DEBUG] Extracted event: {json.dumps(event, indent=2)}")
            logger.info(f"[ACE PINNACLE ODDS DEBUG] periods: {json.dumps(periods, indent=2)}")
            
            odds = {
                'home_moneyline_nvp': [],
                'away_moneyline_nvp': [],
                'home_spreads': [],
                'away_spreads': [],
                'totals': []
            }
            
            # If periods is None or empty, return empty odds
            if not periods:
                logger.warning("[ACE PINNACLE ODDS] No periods found in Pinnacle data")
                return odds
            
            # Ensure periods is a dict before iterating
            if not isinstance(periods, dict):
                logger.warning(f"[ACE PINNACLE ODDS] periods is not a dict: {type(periods)}")
                return odds
            
            for period_key, period in periods.items():
                # Moneyline
                moneyline = period.get('money_line', {})
                if moneyline:
                    if moneyline.get('nvp_american_home') or moneyline.get('american_home'):
                        odds['home_moneyline_nvp'].append({
                            'period': period_key,
                            'odds': moneyline.get('nvp_american_home') or moneyline.get('american_home')
                        })
                    if moneyline.get('nvp_american_away') or moneyline.get('american_away'):
                        odds['away_moneyline_nvp'].append({
                            'period': period_key,
                            'odds': moneyline.get('nvp_american_away') or moneyline.get('american_away')
                        })
                # Spreads
                for line, spread in period.get('spreads', {}).items():
                    odds['home_spreads'].append({
                        'period': period_key,
                        'line': line,
                        'odds': spread.get('nvp_american_home') or spread.get('american_home')
                    })
                    odds['away_spreads'].append({
                        'period': period_key,
                        'line': line,
                        'odds': spread.get('nvp_american_away') or spread.get('american_away')
                    })
                # Totals
                for line, total in period.get('totals', {}).items():
                    odds['totals'].append({
                        'period': period_key,
                        'line': line,
                        'over_odds': total.get('nvp_american_over') or total.get('american_over'),
                        'under_odds': total.get('nvp_american_under') or total.get('american_under')
                    })
            return odds
        except Exception as e:
            logger.error(f"[ACE PINNACLE ODDS] Error extracting odds: {e}")
            return {}

    def _calculate_ev_for_game(self, game: Dict, pinnacle_data: Dict) -> List[Dict]:
        """Calculate EV for a game using the same robust logic as Buckeye"""
        try:
            logger.info(f"[ACE EV] Calculating EV for {game.get('away_team', '')} vs {game.get('home_team', '')}")
            # Match Ace game to Pinnacle data
            matched_pinnacle = self._match_ace_to_pinnacle(game, pinnacle_data)
            if not matched_pinnacle:
                logger.warning(f"[ACE EV] No Pinnacle match found for game")
                return []
            # Convert Ace odds to BetBCK format for EV calculation
            ace_bet_data = self._convert_ace_to_betbck_format(game)
            logger.info(f"[ACE EV] Ace BetBCK format: {json.dumps(ace_bet_data, indent=2)}")
            logger.info(f"[ACE EV] Pinnacle data: {json.dumps(matched_pinnacle, indent=2)}")
            
            # Use the same EV calculation logic as Buckeye - use analyze_markets_for_ev
            from utils.pod_utils import analyze_markets_for_ev
            # Ensure we have valid data before calling analyze_markets_for_ev
            if not matched_pinnacle or not ace_bet_data:
                logger.warning(f"[ACE EV] Missing data for EV calculation - matched_pinnacle: {bool(matched_pinnacle)}, ace_bet_data: {bool(ace_bet_data)}")
                return []
            
            # Validate Pinnacle data structure - ensure it has periods
            if not isinstance(matched_pinnacle, dict):
                logger.warning(f"[ACE EV] Invalid Pinnacle data structure - not a dict: {type(matched_pinnacle)}")
                return []
            
            # Check if periods exist and are valid
            periods = matched_pinnacle.get('periods', {})
            if not periods or not isinstance(periods, dict):
                logger.warning(f"[ACE EV] No valid periods found in Pinnacle data: {type(periods)}")
                return []
            
            # Ensure we have at least one period with data
            has_valid_period = False
            for period_key, period_data in periods.items():
                if isinstance(period_data, dict) and (period_data.get('money_line') or period_data.get('spreads') or period_data.get('totals')):
                    has_valid_period = True
                    break
            
            if not has_valid_period:
                logger.warning(f"[ACE EV] No valid period data found in Pinnacle periods")
                return []
            
            # Ensure ace_bet_data has at least some odds
            if not any([
                ace_bet_data.get('home_moneyline_american'),
                ace_bet_data.get('away_moneyline_american'),
                ace_bet_data.get('home_spreads'),
                ace_bet_data.get('away_spreads'),
                ace_bet_data.get('game_total_line')
            ]):
                logger.warning(f"[ACE EV] No valid odds found in Ace bet data")
                return []
            
            # Wrap matched_pinnacle in the expected structure for analyze_markets_for_ev
            pinnacle_data_wrapped = {'data': matched_pinnacle}
            ev_results = analyze_markets_for_ev(ace_bet_data, pinnacle_data_wrapped)
            
            if ev_results:
                logger.info(f"[ACE EV] Found {len(ev_results)} EV opportunities")
                for result in ev_results:
                    ev_value = result.get('ev', '0')
                    # Handle both string and numeric EV values
                    if isinstance(ev_value, str):
                        logger.debug(f"[ACE EV] Market: {result.get('market', 'Unknown')}, EV: {ev_value}")
                    else:
                        logger.debug(f"[ACE EV] Market: {result.get('market', 'Unknown')}, EV: {ev_value:.3f}")
            else:
                logger.info(f"[ACE EV] No EV opportunities found")
            
            return ev_results
            
        except Exception as e:
            logger.error(f"[ACE EV] Error calculating EV for game: {e}")
            return []

    def _convert_ace_to_betbck_format(self, ace_game: Dict) -> Dict:
        """Convert Ace odds format to BetBCK format for EV calculation"""
        try:
            ace_odds = ace_game.get('away_odds', {})
            home_odds = ace_game.get('home_odds', {})
            
            logger.info(f"[ACE CONVERT] Raw Ace odds - Away: {ace_odds}, Home: {home_odds}")
            
            betbck_format = {
                'home_moneyline_american': home_odds.get('moneyline'),
                'away_moneyline_american': ace_odds.get('moneyline'),
                'home_spreads': [],
                'away_spreads': [],
                'game_total_line': None,
                'game_total_over_odds': None,
                'game_total_under_odds': None
            }
            
            # Add moneyline to the format for EV calculation
            if ace_odds.get('moneyline'):
                betbck_format['moneyline_away'] = ace_odds.get('moneyline')
            if home_odds.get('moneyline'):
                betbck_format['moneyline_home'] = home_odds.get('moneyline')
            
            # Convert spreads - use the parsed spread_line and spread_odds
            if ace_odds.get('spread_line') and ace_odds.get('spread_odds'):
                betbck_format['away_spreads'].append({
                    'line': ace_odds.get('spread_line'),
                    'odds': ace_odds.get('spread_odds')
                })
                betbck_format['spread_away'] = ace_odds.get('spread_odds')
                logger.info(f"[ACE CONVERT] Added away spread: {ace_odds.get('spread_line')} @ {ace_odds.get('spread_odds')}")
            
            if home_odds.get('spread_line') and home_odds.get('spread_odds'):
                betbck_format['home_spreads'].append({
                    'line': home_odds.get('spread_line'),
                    'odds': home_odds.get('spread_odds')
                })
                betbck_format['spread_home'] = home_odds.get('spread_odds')
                logger.info(f"[ACE CONVERT] Added home spread: {home_odds.get('spread_line')} @ {home_odds.get('spread_odds')}")
            
            # Convert totals - use the parsed total_line and total_odds
            if ace_odds.get('total_line') and ace_odds.get('total_odds'):
                betbck_format['game_total_line'] = ace_odds.get('total_line')
                # Determine over/under based on total_ou field
                if ace_odds.get('total_ou') == 'o':
                    betbck_format['game_total_over_odds'] = ace_odds.get('total_odds')
                    betbck_format['game_total_under_odds'] = home_odds.get('total_odds')
                    betbck_format['total_over'] = ace_odds.get('total_odds')
                    betbck_format['total_under'] = home_odds.get('total_odds')
                else:  # 'u' for under
                    betbck_format['game_total_over_odds'] = home_odds.get('total_odds')
                    betbck_format['game_total_under_odds'] = ace_odds.get('total_odds')
                    betbck_format['total_over'] = home_odds.get('total_odds')
                    betbck_format['total_under'] = ace_odds.get('total_odds')
                logger.info(f"[ACE CONVERT] Added total: {ace_odds.get('total_line')} - Over: {betbck_format['game_total_over_odds']}, Under: {betbck_format['game_total_under_odds']}")
            
            logger.info(f"[ACE CONVERT] Final BetBCK format: {betbck_format}")
            return betbck_format
            
        except Exception as e:
            logger.error(f"[ACE CONVERT] Error converting Ace format: {e}")
            return {}

    def _parse_spread_line(self, spread_str: str) -> Optional[Dict]:
        """Parse spread line like '+1½-225' or '+&frac12;+115' into line and odds"""
        try:
            if not spread_str:
                return None
            
            # Clean the spread string
            cleaned = self._clean_odds_string(spread_str)
            logger.info(f"[ACE PARSE] Parsing spread: '{spread_str}' -> '{cleaned}'")
            
            # Handle special cases like 'PK' (pick'em)
            if cleaned.upper() == 'PK':
                return {'line': '0', 'odds': None}
            
            # Handle PK with odds like 'PK+105' or 'PK-115'
            pk_match = re.match(r'^PK([+-]\d+)$', cleaned)
            if pk_match:
                return {'line': '0', 'odds': pk_match.group(1)}
            
            # Extract line and odds - handle malformed spreads like '+&frac12;+115'
            # Pattern: +/-number(½)?+/-odds or +/-½+/-odds
            match = re.match(r'^([+-]?)(\d*(?:½)?)([+-]\d+)$', cleaned)
            if match:
                sign = match.group(1)
                line_part = match.group(2)
                odds = match.group(3)
                
                # Convert fraction to decimal
                line_decimal = self._normalize_fraction_to_decimal(line_part)
                
                # Handle empty line part (just fraction)
                if not line_decimal or line_decimal == '0':
                    if '½' in line_part:
                        line_decimal = '0.5'
                    else:
                        line_decimal = '0'
                
                # Apply sign
                if sign == '-':
                    line_decimal = f"-{line_decimal}"
                elif sign == '+':
                    line_decimal = f"+{line_decimal}"
                
                logger.info(f"[ACE PARSE] Spread parsed: line='{line_decimal}', odds='{odds}'")
                return {'line': line_decimal, 'odds': odds}
            
            logger.warning(f"[ACE PARSE] Could not parse spread: '{cleaned}'")
            return None
            
        except Exception as e:
            logger.error(f"[ACE PARSE] Error parsing spread '{spread_str}': {e}")
            return None

    def _parse_total_line(self, total_str: str) -> Optional[Dict]:
        """Parse total line like 'u7+105' or 'u2&frac12;-143' into line and odds"""
        try:
            if not total_str:
                return None
            
            # Clean the total string
            cleaned = self._clean_odds_string(total_str)
            logger.info(f"[ACE PARSE] Parsing total: '{total_str}' -> '{cleaned}'")
            
            # Extract over/under, line, and odds
            # Pattern: [ou]\d*(?:½)?[+-]\d+
            match = re.match(r'^([ou])(\d*(?:½)?)([+-]\d+)$', cleaned)
            if match:
                direction = match.group(1)
                line_part = match.group(2)
                odds = match.group(3)
                
                # Convert fraction to decimal
                line_decimal = self._normalize_fraction_to_decimal(line_part)
                
                # Handle empty line part (just fraction)
                if not line_decimal or line_decimal == '0':
                    if '½' in line_part:
                        line_decimal = '0.5'
                    else:
                        line_decimal = '0'
                
                logger.info(f"[ACE PARSE] Total parsed: direction='{direction}', line='{line_decimal}', odds='{odds}'")
                
                if direction == 'o':
                    return {'line': line_decimal, 'over_odds': odds, 'under_odds': None}
                else:
                    return {'line': line_decimal, 'over_odds': None, 'under_odds': odds}
            
            logger.warning(f"[ACE PARSE] Could not parse total: '{cleaned}'")
            return None
            
        except Exception as e:
            logger.error(f"[ACE PARSE] Error parsing total '{total_str}': {e}")
            return None
    
    def _calculate_ev(self, ace_odds: str, pinnacle_odds: str) -> Optional[float]:
        """Calculate EV between Ace and Pinnacle odds"""
        try:
            from utils.pod_utils import american_to_decimal, calculate_ev
            
            ace_decimal = american_to_decimal(ace_odds)
            pinnacle_decimal = american_to_decimal(pinnacle_odds)
            
            if ace_decimal and pinnacle_decimal:
                ev = calculate_ev(ace_decimal, pinnacle_decimal)
                return ev * 100 if ev else None
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating EV: {e}")
            return None
    
    def get_ace_results(self) -> Dict[str, Any]:
        """Get stored Ace results in Buckeye format"""
        try:
            if not self.results_file.exists():
                return {
                    "status": "error",
                    "message": "No Ace results found. Run calculations first.",
                    "markets": [],
                    "last_update": None
                }
            
            with open(self.results_file, 'r') as f:
                data = json.load(f)
            
            # Return in the format the frontend expects (like Buckeye)
            return {
                "status": "success",
                "message": "Ace results retrieved successfully",
                "markets": data.get("events", []),  # Map events to markets for frontend
                "last_update": data.get("last_run", None)
            }
            
        except Exception as e:
            logger.error(f"Ace Scraper: Error reading results: {e}")
            return {
                "status": "error",
                "message": f"Failed to read Ace results: {str(e)}",
                "markets": [],
                "last_update": None
            } 

    def _clean_odds_string(self, odds_str: str) -> str:
        """Clean odds string: remove whitespace, replace HTML entities, etc."""
        if not odds_str:
            return ''
        odds_str = odds_str.replace(' ', '')
        odds_str = clean_fraction_entities(odds_str)
        odds_str = odds_str.replace('EV', '+100')  # Normalize 'EV' to +100
        return odds_str

    def _normalize_fraction_to_decimal(self, fraction_str: str) -> str:
        """Convert fraction strings to decimal values"""
        if not fraction_str:
            return fraction_str
        
        # Handle common fractions
        fraction_map = {
            '½': '0.5',
            '¼': '0.25', 
            '¾': '0.75',
            '⅓': '0.333',
            '⅔': '0.667',
            '⅕': '0.2',
            '⅖': '0.4',
            '⅗': '0.6',
            '⅘': '0.8',
            '⅙': '0.167',
            '⅚': '0.833',
            '⅛': '0.125',
            '⅜': '0.375',
            '⅝': '0.625',
            '⅞': '0.875'
        }
        
        # Replace fractions with decimals
        for fraction, decimal in fraction_map.items():
            fraction_str = fraction_str.replace(fraction, decimal)
        
        return fraction_str

    def _parse_odds_from_html(self, html_content: str) -> List[Dict]:
        """Parse odds from HTML content with improved odds cleaning"""
        games = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all game rows
        game_rows = soup.find_all('tr', class_='gameRow')
        
        for row in game_rows:
            try:
                # Extract game data
                game_id = row.get('data-game-id', '')
                date_time = row.get('data-date-time', '')
                away_team = row.get('data-away-team', '')
                home_team = row.get('data-home-team', '')
                sport = row.get('data-sport', 'unknown')
                league = row.get('data-league', '')
                
                # Extract odds with cleaning
                away_odds = {}
                home_odds = {}
                
                # Moneyline odds
                away_ml = row.get('data-away-ml', '')
                home_ml = row.get('data-home-ml', '')
                if away_ml:
                    away_odds['moneyline'] = self._clean_odds_string(away_ml)
                if home_ml:
                    home_odds['moneyline'] = self._clean_odds_string(home_ml)
                
                # Spread odds
                away_spread = row.get('data-away-spread', '')
                home_spread = row.get('data-home-spread', '')
                if away_spread:
                    away_odds['spread'] = self._clean_odds_string(away_spread)
                if home_spread:
                    home_odds['spread'] = self._clean_odds_string(home_spread)
                
                # Total odds
                away_total = row.get('data-away-total', '')
                home_total = row.get('data-home-total', '')
                if away_total:
                    away_odds['total'] = self._clean_odds_string(away_total)
                if home_total:
                    home_odds['total'] = self._clean_odds_string(home_total)
                
                game = {
                    'game_id': game_id,
                    'date_time': date_time,
                    'away_team': away_team,
                    'home_team': home_team,
                    'away_odds': away_odds,
                    'home_odds': home_odds,
                    'sport': sport,
                    'league': league
                }
                
                games.append(game)
                
            except Exception as e:
                logger.warning(f"Error parsing game row: {e}")
                continue
        
        return games 

    def match_games_to_events_parallel(self, games: list, event_ids: list, max_workers: int = None) -> list:
        """Parallelize the matching of Ace games to event IDs for speed."""
        if max_workers is None:
            max_workers = self._get_optimal_worker_count()
        
        # Create hash maps once (shared across all workers)
        event_hash_maps = self._create_event_hash_map(event_ids)
        
        matched = [None] * len(games)
        
        def match_one(i):
            return (i, self._match_game_to_event_optimized(games[i], event_hash_maps))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(match_one, i) for i in range(len(games))]
            for future in as_completed(futures):
                i, result = future.result()
                matched[i] = result
        
        return matched

    def process_games_in_batches(self, games: list, event_ids: list, batch_size: int = 50, callback=None):
        """Process games in batches and call callback with results for real-time updates"""
        if not games:
            return []
        
        # Create hash maps once
        event_hash_maps = self._create_event_hash_map(event_ids)
        optimal_workers = self._get_optimal_worker_count()
        
        all_results = []
        total_batches = (len(games) + batch_size - 1) // batch_size
        
        logger.info(f"[ACE BATCH] Processing {len(games)} games in {total_batches} batches of {batch_size}")
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(games))
            batch_games = games[start_idx:end_idx]
            
            logger.info(f"[ACE BATCH] Processing batch {batch_num + 1}/{total_batches} (games {start_idx + 1}-{end_idx})")
            
            # Process this batch in parallel
            batch_results = []
            matched = [None] * len(batch_games)
            
            def match_batch_game(i):
                return (i, self._match_game_to_event_optimized(batch_games[i], event_hash_maps))
            
            with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
                futures = [executor.submit(match_batch_game, i) for i in range(len(batch_games))]
                for future in as_completed(futures):
                    i, result = future.result()
                    matched[i] = result
            
            # Process matched games for this batch
            for i, game in enumerate(batch_games):
                if matched[i]:
                    # Calculate EV for matched games
                    ev_results = self._calculate_ev_for_game(game, {})  # Will need pinnacle data
                    if ev_results:
                        batch_results.extend(ev_results)
            
            all_results.extend(batch_results)
            
            # Call callback with batch results for real-time updates
            if callback and batch_results:
                callback(batch_results, batch_num + 1, total_batches)
        
        return all_results

    def _get_optimal_worker_count(self) -> int:
        """Determine optimal worker count based on system resources"""
        try:
            # Get CPU count and current usage
            cpu_count = psutil.cpu_count(logical=True)
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Base calculation: use 50% of available cores, but respect current load
            base_workers = max(1, min(4, cpu_count // 2))
            
            # Reduce workers if CPU is already under high load (>70%)
            if cpu_percent > 70:
                optimal_workers = max(1, base_workers - 1)
            elif cpu_percent > 50:
                optimal_workers = max(2, base_workers - 1)
            else:
                optimal_workers = base_workers
            
            logger.info(f"[ACE OPTIMIZATION] CPU: {cpu_percent:.1f}%, Cores: {cpu_count}, Workers: {optimal_workers}")
            return optimal_workers
            
        except Exception as e:
            logger.warning(f"[ACE OPTIMIZATION] Could not determine optimal workers: {e}, using 4")
            return 4 

    def _get_pinnacle_data_for_game(self, matched_event: Dict) -> Optional[Dict]:
        """Get Pinnacle data for a specific matched event"""
        try:
            event_id = matched_event.get('event_id')
            if not event_id:
                return None
            
            return self._get_pinnacle_odds(str(event_id))
        except Exception as e:
            logger.error(f"[ACE PINNACLE] Error getting Pinnacle data: {e}")
            return None 