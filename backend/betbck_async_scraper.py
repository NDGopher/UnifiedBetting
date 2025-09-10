import asyncio
import aiohttp
import hashlib
import json
import random
import re
import os
from datetime import datetime
from bs4 import BeautifulSoup
import dateutil.parser
import logging
from utils.pod_utils import normalize_team_name_for_matching, is_prop_market_by_name

logger = logging.getLogger(__name__)

class BetBCKAsyncScraper:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.headers = self.config['betbck']['headers']
        self.login_url = self.config['betbck']['login_action_url']
        self.login_page_url = self.config['betbck']['login_page_url']
        self.selection_url = self.config['betbck']['main_page_url_after_login']
        self.games_url = self.config['betbck']['search_action_url']
        self.skip_indicators = [
            'bookings', 'cards', 'fouls', 'corners', 'outright', 'futures',
            'to lift the trophy', 'lift the trophy', 'mvp', 'coach of the year',
            'player of the year', 'series correct score', 'when will series finish',
            'most points in series', 'most assists in series', 'most rebounds in series',
            'most threes made in series', 'margin of victory', 'exact outcome'
        ]
        self.checkbox_patterns = [
            re.compile(r"SOCCER_.*?_Game_"),
            re.compile(r"BASKETBALL_NBA_Game_"),
            re.compile(r"BASKETBALL_NCAAB_Game_"),
            re.compile(r"BASKETBALL_WNBA_Game_"),
            re.compile(r"FOOTBALL_NFL_Game_"),
            re.compile(r"FOOTBALL_NCAAF_Game_"),
            re.compile(r"FOOTBALL_COLLEGE_Game_"),
            re.compile(r"FOOTBALL_CANADIAN_Game_"),
            re.compile(r"HOCKEY_NHL_Game_"),
            re.compile(r"BASEBALL_MLB_Game_"),
            re.compile(r"BASEBALL_WBC_Game_"),
            re.compile(r"BASEBALL_MEXICAN@20;BASE_Game_"),
            re.compile(r"BASEBALL_(JAPAN|KOREA|TAIWAN)_.*?_Game_"),
            re.compile(r"BASEBALL_OTHER@20;LEAGUE_Game_"),
            re.compile(r"MARTIAL@20;ARTS_.*?_Game_"),
            re.compile(r"BOXING_.*?_Game_"),
            re.compile(r"GOLF_.*?_Game_"),
            re.compile(r"TENNIS_.*?_Game_"),
            re.compile(r"AUTO@20;RACING_.*?_Game_"),
            re.compile(r"CRICKET_.*?_Game_"),
            re.compile(r"RUGBY_.*?_Game_"),
            re.compile(r"LIVE_MLB@20;LIVE_Game_"),
            re.compile(r"LIVE_FOOTBALL_NFL@20;LIVE_Game_"),
            re.compile(r"LIVE_FOOTBALL_COLLEGE@20;LIVE_Game_"),
            re.compile(r"LIVE_BASKETBALL_NBA@20;LIVE_Game_"),
            re.compile(r"LIVE_BASKETBALL_WNBA@20;LIVE_Game_"),
            re.compile(r"LIVE_HOCKEY_NHL@20;LIVE_Game_"),
            re.compile(r"LIVE_SOCCER_.*?@20;LIVE_Game_"),
            re.compile(r"LIVE_TENNIS_.*?@20;LIVE_Game_"),
            re.compile(r"LIVE_GOLF_.*?@20;LIVE_Game_"),
            re.compile(r"LIVE_MARTIAL@20;ARTS_.*?@20;LIVE_Game_"),
            re.compile(r"LIVE_BOXING_.*?@20;LIVE_Game_"),
            re.compile(r"LIVE_AUTO@20;RACING_.*?@20;LIVE_Game_"),
            re.compile(r"LIVE_CRICKET_.*?@20;LIVE_Game_"),
            re.compile(r"LIVE_RUGBY_.*?@20;LIVE_Game_")
        ]
        self.output_file = "data/betbck_games.json"

    async def login(self, session):
        await asyncio.sleep(random.uniform(1.2, 2.5))
        async with session.get(self.login_page_url, headers=self.headers) as _:
            pass
        payload = self.config['betbck']['credentials']
        async with session.post(self.login_url, data=payload, headers=self.headers) as resp:
            text = await resp.text()
            if 'logout' not in text.lower():
                raise Exception('Login failed!')
            print('[LOG] Login successful.')

    async def fetch_selection_page(self, session):
        await asyncio.sleep(random.uniform(0.8, 1.5))
        async with session.get(self.selection_url, headers=self.headers) as resp:
            html = await resp.text()
            return html

    async def fetch_games_page(self, session, post_payload):
        await asyncio.sleep(random.uniform(1.0, 2.0))
        async with session.post(self.games_url, data=post_payload, headers=self.headers) as resp:
            html = await resp.text()
            return html

    def parse_games(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        search_context = soup.find('form', {'name': 'GameSelectionForm', 'id': 'GameSelectionForm'}) or soup
        found_games_data = []
        game_wrappers = search_context.find_all('table', class_=lambda x: x and x.startswith('table_container_betting'))
        for gw in game_wrappers:
            team_name_td = gw.find('td', class_=lambda x: x and x.startswith('tbl_betAmount_team1_main_name'))
            if not team_name_td: continue
            div_t1 = team_name_td.find('div', class_='team1_name_up')
            div_t2 = team_name_td.find('div', class_='team2_name_down')
            if not (div_t1 and div_t2): continue
            home = div_t1.get_text(strip=True)
            away = div_t2.get_text(strip=True)
            if not home or not away: continue
            # Robust prop/corner/future filtering
            if is_prop_market_by_name(home, away):
                continue
            odds_table = gw.find('table', class_='new_tb_cont')
            odds = {
                "site_top_team_moneyline_american": None,
                "site_bottom_team_moneyline_american": None,
                "draw_moneyline_american": None,
                "site_top_team_spreads": [],
                "site_bottom_team_spreads": [],
                "game_total_line": None,
                "game_total_over_odds": None,
                "game_total_under_odds": None
            }
            if odds_table:
                rows = odds_table.find_all('tr', recursive=False)
                if len(rows) >= 2:
                    tds_top = rows[0].find_all('td', class_=lambda x: x and 'tbl_betAmount_td' in x)
                    tds_bot = rows[1].find_all('td', class_=lambda x: x and 'tbl_betAmount_td' in x)
                    # Moneylines
                    if len(tds_top) > 1:
                        odds["site_top_team_moneyline_american"] = self.extract_american_odds(tds_top[1])
                    if len(tds_bot) > 1:
                        odds["site_bottom_team_moneyline_american"] = self.extract_american_odds(tds_bot[1])
                    # Spreads (first column)
                    if len(tds_top) > 0:
                        odds["site_top_team_spreads"] = self.extract_spreads_from_td(tds_top[0])
                    if len(tds_bot) > 0:
                        odds["site_bottom_team_spreads"] = self.extract_spreads_from_td(tds_bot[0])
                    # Totals (third column)
                    if len(tds_top) > 2:
                        total_line, over_odds = self.extract_total_from_td(tds_top[2], over=True)
                        if total_line is not None:
                            odds["game_total_line"] = total_line
                            odds["game_total_over_odds"] = over_odds
                    if len(tds_bot) > 2:
                        total_line, under_odds = self.extract_total_from_td(tds_bot[2], over=False)
                        if total_line is not None:
                            odds["game_total_line"] = total_line
                            odds["game_total_under_odds"] = under_odds
            # Normalize team names for ID and saving
            norm_home = normalize_team_name_for_matching(home)
            norm_away = normalize_team_name_for_matching(away)
            # Extract date/time from .dateLinebetting
            date_div = gw.find_previous('div', class_='dateLinebetting')
            date_str = ''
            norm_date = ''
            if date_div and date_div.text:
                date_str = date_div.text.strip()
                m = re.search(r'(\w{3}) (\d{1,2})/(\d{1,2})\s+(\d{1,2}:\d{2}[AP]M)', date_str)
                if m:
                    month = int(m.group(2))
                    day = int(m.group(3))
                    time = m.group(4)
                    year = datetime.now().year
                    dt = dateutil.parser.parse(f"{year}-{month:02d}-{day:02d} {time}")
                    norm_date = dt.strftime('%Y-%m-%dT%H:%M')
            sport = gw.get('data-sport', '').strip().lower() if gw.has_attr('data-sport') else 'soccer'
            teams = sorted([norm_home, norm_away])
            game_id = hashlib.md5(f"{teams[0]}_{teams[1]}_{sport}_{norm_date}".encode()).hexdigest()[:8]
            found_games_data.append({
                "betbck_game_id": game_id,
                "betbck_site_home_team": home,
                "betbck_site_away_team": away,
                "betbck_site_odds": odds,
                "timestamp": datetime.now().isoformat(),
                "event_datetime": norm_date
            })
        return found_games_data

    def extract_american_odds(self, td):
        text = td.get_text(" ", strip=True)
        match = re.search(r'([+-]\d{3,})', text)
        return match.group(1) if match else None

    def extract_spreads_from_td(self, td):
        spreads = []
        select = td.find('select')
        if select:
            for option in select.find_all('option'):
                text = option.get_text(" ", strip=True)
                m = re.match(r'([+-]?[\w½¼¾,\.\+\-]+)\s*([+-]\d{3,})', text)
                if m:
                    line_raw, odds = m.group(1), m.group(2)
                    line = self.parse_split_line(line_raw)
                    spreads.append({"line": line, "odds": odds, "raw": line_raw})
        else:
            text = td.get_text(" ", strip=True)
            for m in re.finditer(r'([+-]?[\w½¼¾,\.\+\-]+)\s*([+-]\d{3,})', text):
                line_raw, odds = m.group(1), m.group(2)
                line = self.parse_split_line(line_raw)
                spreads.append({"line": line, "odds": odds, "raw": line_raw})
        return spreads

    def extract_total_from_td(self, td, over=True):
        text = td.get_text(" ", strip=True).lower()
        m = re.search(r'(o|u)?\s*([\d½¼¾,\.\+\-pk]+)\s*([+-]\d{3,})', text)
        if m:
            line_raw = m.group(2)
            odds = m.group(3)
            line = self.parse_split_line(line_raw)
            if (over and 'o' in text) or (not over and 'u' in text):
                return line, odds
        return None, None

    def parse_split_line(self, line_raw):
        def part_to_decimal(part):
            part = part.replace('pk', '0').replace('−', '-')
            part = part.replace('½', '.5').replace('¼', '.25').replace('¾', '.75')
            try:
                return float(part)
            except Exception:
                return part
        if ',' in line_raw:
            parts = [part_to_decimal(p.strip()) for p in line_raw.split(',')]
            if all(isinstance(p, float) for p in parts):
                return sum(parts) / len(parts)
            return line_raw
        else:
            return part_to_decimal(line_raw.strip())

    def deduplicate_games(self, games):
        seen = set()
        deduped = []
        for g in games:
            key = (g['betbck_site_home_team'], g['betbck_site_away_team'])
            if key not in seen:
                deduped.append(g)
                seen.add(key)
        return deduped

    async def run(self):
        async with aiohttp.ClientSession(headers=self.headers) as session:
            await self.login(session)
            selection_html = await self.fetch_selection_page(session)
            selection_soup = BeautifulSoup(selection_html, 'html.parser')
            inet_wager_input = selection_soup.find('input', {'name': 'inetWagerNumber'})
            inet_wager_value = inet_wager_input['value'] if inet_wager_input else "0.1234567890123456"
            all_checkboxes = selection_soup.find_all('input', {'type': 'checkbox'})
            checkbox_names = [cb.get('name') for cb in all_checkboxes if cb.get('name') and any(p.fullmatch(cb.get('name')) for p in self.checkbox_patterns)]
            print(f"[LOG] Found {len(checkbox_names)} sport/league checkboxes for async POST.")
            
            # Log all checkbox names for debugging
            all_checkbox_names = [cb.get('name') for cb in all_checkboxes if cb.get('name')]
            print(f"[LOG] All available checkboxes ({len(all_checkbox_names)}):")
            for i, name in enumerate(all_checkbox_names[:20]):  # Show first 20
                print(f"   {i+1}. {name}")
            if len(all_checkbox_names) > 20:
                print(f"   ... and {len(all_checkbox_names) - 20} more")
            tasks = []
            for name in checkbox_names:
                post_payload = {
                    'keyword_search': '',
                    'inetWagerNumber': inet_wager_value,
                    'inetSportSelection': 'sport',
                    'contestType1': '', 'contestType2': '', 'contestType3': '',
                    'x': '79', 'y': '5',
                    name: 'on'
                }
                tasks.append(self.fetch_games_page(session, post_payload))
            games_htmls = await asyncio.gather(*tasks)
            all_games = []
            for html in games_htmls:
                all_games.extend(self.parse_games(html))
            deduped_games = self.deduplicate_games(all_games)
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump(deduped_games, f, indent=2, ensure_ascii=False)
            print(f"[LOG] Saved {len(deduped_games)} deduplicated games to {self.output_file}")

    def normalize_team_name(self, name):
        return re.sub(r'[^a-zA-Z ]+', '', name).strip().lower()

def get_all_betbck_games():
    """Synchronous wrapper for async BetBCK scraping - use only in scripts, not in FastAPI endpoints"""
    import asyncio
    try:
        # Check if we're already in an event loop
        loop = asyncio.get_running_loop()
        logger.warning("get_all_betbck_games called from within an event loop. Use _get_all_betbck_games_async() instead.")
        # Create a new event loop for this thread
        import threading
        if threading.current_thread() is threading.main_thread():
            # We're in the main thread, create a new loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_get_all_betbck_games_async())
            finally:
                loop.close()
        else:
            # We're in a different thread, this should be safe
            return asyncio.run(_get_all_betbck_games_async())
    except RuntimeError:
        # No event loop running, safe to use asyncio.run
        return asyncio.run(_get_all_betbck_games_async())

async def _get_all_betbck_games_async():
    scraper = BetBCKAsyncScraper()
    await scraper.run()
    with open(scraper.output_file, "r", encoding="utf-8") as f:
        return json.load(f)

if __name__ == "__main__":
    games = get_all_betbck_games()
    print(f"Scraped {len(games)} games")
    print(json.dumps(games[:2], indent=2, ensure_ascii=False)) 