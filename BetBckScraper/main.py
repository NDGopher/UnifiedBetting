import time
import random
import sqlite3
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
USERNAME = "xyz005"
PASSWORD = "xyz005" # <--- UPDATE THIS
LOGIN_URL = "https://betbck.com/mQubic/"
DB_NAME = "odds_history_v2.db"

class BetBuckeyeBot:
    def __init__(self):
        self.driver = None
        self.conn = sqlite3.connect(DB_NAME)
        self.setup_db()
        self.setup_driver()

    def setup_db(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            game_id TEXT,
            team_home TEXT,
            team_away TEXT,
            spread_home TEXT,
            spread_away TEXT,
            total_over TEXT,
            total_under TEXT,
            ml_home TEXT,
            ml_away TEXT
        )''')
        self.conn.commit()

    def setup_driver(self):
        print("🤖 Initializing Speed-Optimized Browser...")
        
        mobile_emulation = { "deviceName": "Pixel 7" }
        
        chrome_options = Options()
        chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors")
        
        # --- SPEED HACKS: BLOCK IMAGES ---
        prefs = {
            "profile.managed_default_content_settings.images": 2, 
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Keep window open
        chrome_options.add_experimental_option("detach", True)

        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.driver.set_script_timeout(30)

    def force_click(self, element):
        """JavaScript click to bypass 'not interactable' errors"""
        self.driver.execute_script("arguments[0].click();", element)

    def login(self):
        print(f"🔑 Authenticating as {USERNAME}...")
        try:
            self.driver.get(LOGIN_URL)
            
            # Check if already logged in
            try:
                if "Selection" in self.driver.current_url:
                    print("✅ Session Valid.")
                    return True
            except: pass

            # Wait for fields
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "customerID")))

            # Enter Creds
            self.driver.find_element(By.ID, "customerID").clear()
            self.driver.find_element(By.ID, "customerID").send_keys(USERNAME)
            
            self.driver.find_element(By.ID, "password").clear()
            self.driver.find_element(By.ID, "password").send_keys(PASSWORD)

            # FORCE CLICK LOGIN
            try:
                # Try finding the span text first (common in mQubic)
                btn = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Sign In')]")
                self.force_click(btn)
            except:
                # Fallback to input submit
                btn = self.driver.find_element(By.XPATH, "//input[@type='submit']")
                self.force_click(btn)

            print("⏳ Login clicked. Waiting for dashboard...")
            
            # Wait for redirect
            WebDriverWait(self.driver, 15).until(EC.url_contains("Selection"))
            print("✅ Login Successful.")
            return True
            
        except Exception as e:
            print(f"❌ Login Failed: {e}")
            return False

    def fetch_precise_odds(self):
        """
        Injects JavaScript to request specific sports data directly from the server.
        This bypasses the UI and is much faster.
        """
        js_payload = """
            var callback = arguments[arguments.length - 1];
            
            // Try to find the token, or generate a random one if missing
            var tokenInput = document.getElementById('inetWagerNumber');
            var wagerNum = tokenInput ? tokenInput.value : Math.random().toString();
            
            // The payload requests NFL, NCAAF, NBA, NCAAB, NHL, and Soccer ALL AT ONCE
            var body = "keyword_search=&inetWagerNumber=" + wagerNum + 
                       "&inetSportSelection=sport&contestType1=&contestType2=&contestType3=&correlatedID=" +
                       "&inetWagerNumber=" + wagerNum + "&inetSportSelection=sport" +
                       "&FOOTBALL_NFL_Game_=on&FOOTBALL_COLLEGE_Game_=on" + 
                       "&BASKETBALL_NBA_Game_=on&BASKETBALL_NCAA_Game_=on" +
                       "&BASKETBALL_NCAA@20;EXTRA_Game_=on&HOCKEY_NHL_Game_=on" + 
                       "&SOCCER_UEFA@20;EU@20;LEA_Game_=on" + 
                       "&x=29&y=15";

            fetch('https://betbck.com/mQubic/PlayerGameSelection.php', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: body
            })
            .then(res => res.text())
            .then(text => callback(text))
            .catch(err => callback("JS_ERROR: " + err));
        """
        return self.driver.execute_async_script(js_payload)

    def parse_and_save_regex(self, html):
        if not html or len(html) < 2000: return 0
        
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Regex Parsers
        teams = re.findall(r'data-language="([^"]+)"', html)
        select_matches = re.findall(r'id=([SL][12])_(\d+)_buyToSelect[^>]*>.*?SELECTED>([^<]+)', html)
        ml_matches = re.findall(r'>([^<]+)</td>\s*<td[^>]*><INPUT[^>]*name="M([12])_(\d+)"', html)

        games = {}

        # Map Data
        for type_code, idx, value in select_matches:
            if idx not in games: games[idx] = {}
            games[idx][type_code] = value.strip()

        for value, type_num, idx in ml_matches:
            if idx not in games: games[idx] = {}
            games[idx][f"M{type_num}"] = value.strip()

        db_rows = []
        
        # Sort by index to match team list order
        sorted_indices = sorted(games.keys(), key=lambda x: int(x))
        
        for i, idx in enumerate(sorted_indices):
            team_idx = i * 2
            if team_idx + 1 >= len(teams): break
            
            team_away = teams[team_idx]
            team_home = teams[team_idx+1]
            
            data = games[idx]
            game_id = f"{team_away[:3]}{team_home[:3]}".upper()
            
            db_rows.append((
                timestamp, game_id, team_home, team_away,
                data.get('S2', 'N/A'),
                data.get('S1', 'N/A'),
                data.get('L1', 'N/A'),
                data.get('L2', 'N/A'),
                data.get('M2', 'N/A'),
                data.get('M1', 'N/A') 
            ))

        if db_rows:
            self.conn.executemany('''INSERT INTO odds (timestamp, game_id, team_home, team_away, 
                spread_home, spread_away, total_over, total_under, ml_home, ml_away) 
                VALUES (?,?,?,?,?,?,?,?,?,?)''', db_rows)
            self.conn.commit()
            
        return len(db_rows)

    def run(self):
        if not self.login(): return

        print("\n🚀 STARTING FAST MONITOR (IMAGES OFF)")
        print("-------------------------------------")
        
        while True:
            try:
                start = time.time()
                
                # 1. Fetch via JS Injection (No clicking!)
                raw_html = self.fetch_precise_odds()
                
                # 2. Check for Session Issues
                if "login" in raw_html.lower() and len(raw_html) < 5000:
                    print("⚠️ Session Lost. Re-logging...")
                    self.login()
                    continue

                # 3. Parse
                count = self.parse_and_save_regex(raw_html)
                duration = time.time() - start
                
                print(f"⚡ Sweep: {duration:.2f}s | Games Found: {count}")
                
                # 4. Wait
                # Adjust this sleep time as needed. 10-20s is safe to avoid bans.
                time.sleep(15)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    bot = BetBuckeyeBot()
    bot.run()