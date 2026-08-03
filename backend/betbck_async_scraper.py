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
    def __init__(self, config_path='config.json', sport_filters=None):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.headers = self.config['betbck']['headers']
        self.login_url = self.config['betbck']['login_action_url']
        self.login_page_url = self.config['betbck']['login_page_url']
        self.selection_url = self.config['betbck']['main_page_url_after_login']
        self.games_url = self.config['betbck']['search_action_url']
        self.sport_filters = sport_filters or []  # List of sport keys to filter (e.g., ['nfl', 'nba'])
        self.skip_indicators = [
            'bookings', 'cards', 'fouls', 'corners', 'outright', 'futures',
            'to lift the trophy', 'lift the trophy', 'mvp', 'coach of the year',
            'player of the year', 'series correct score', 'when will series finish',
            'most points in series', 'most assists in series', 'most rebounds in series',
            'most threes made in series', 'margin of victory', 'exact outcome'
        ]
        # Sport mapping: maps sport keys to checkbox name patterns
        # Each key lists BOTH the _Game_ and _1st@20;Half_ variants so BetBCK returns
        # full-game AND first-half lines in the same POST response.
        self.sport_checkbox_mapping = {
            'nfl': ['FOOTBALL_NFL_Game_'],
            'ncaa_football': ['FOOTBALL_COLLEGE_Game_'],
            'nba': ['BASKETBALL_NBA_Game_', 'BASKETBALL_NBA_1st@20;Half_'],
            'ncaa_basketball': ['BASKETBALL_NCAA_Game_', 'BASKETBALL_NCAA@20;EXTRA_Game_'],
            'nhl': ['HOCKEY_NHL_Game_'],
            'mlb': ['BASEBALL_MLB_Game_'],
            'wnba': ['BASKETBALL_WNBA_Game_', 'BASKETBALL_WNBA_1st@20;Half_'],
            # Season win totals — exact checkbox names confirmed from BetBCK request log
            'nfl_season_wins': ['FOOTBALL_NFL@20;SEAS@20;WIN_Game_'],
            'cfb_season_wins': ['FOOTBALL_NCAA@20;SEA@20;WIN_Game_'],
            'soccer': ['SOCCER_.*?_Game_', 'SOCCER_.*?_1st@20;Half_'],  # All soccer + 1H
            'soccer_major': [  # Major soccer leagues + their 1H lines
                'SOCCER_UEFA@20;CH@20;LEA_Game_',
                'SOCCER_UEFA@20;EU@20;LEA_Game_',
                'SOCCER_ENG@20;PREM_Game_', 'SOCCER_ENG@20;PREM_1st@20;Half_',
                'SOCCER_ENG@20;LEA1_Game_',
                'SOCCER_ENG@20;CHAMPI_Game_', 'SOCCER_ENG@20;CHAMPI_1st@20;Half_',
                'SOCCER_SPA@20;LA@20;LIGA_Game_', 'SOCCER_SPA@20;LA@20;LIGA_1st@20;Half_',
                'SOCCER_ITA@20;SER@20;A_Game_',
                'SOCCER_GER@20;BUNDE_Game_',
                'SOCCER_FRE@20;LIGUE1_Game_', 'SOCCER_FRE@20;LIGUE1_1st@20;Half_',
                'SOCCER_MEX@20;-@20;PR@20;DIV_Game_',
                'SOCCER_USA@20;MLS_Game_', 'SOCCER_USA@20;MLS_1st@20;Half_',
                'SOCCER_BRA@20;-@20;SER@20;A_Game_', 'SOCCER_BRA@20;-@20;SER@20;A_1st@20;Half_',
                'SOCCER_ARG@20;PRI@20;DIV_Game_', 'SOCCER_ARG@20;PRI@20;DIV_1st@20;Half_',
            ]
        }
        # Priority order for "all sports" mode - highest priority first
        self.sport_priority = [
            'nfl', 'nba', 'nhl', 'mlb',            # Major US sports first
            'ncaa_football', 'ncaa_basketball',      # College sports
            'nfl_season_wins', 'cfb_season_wins',    # Season win totals
            'soccer_major',                          # Major soccer leagues
            'soccer'                                 # All other soccer (lowest priority)
        ]
        self.checkbox_patterns = [
            re.compile(r"SOCCER_.*?_Game_"),
            re.compile(r"SOCCER_.*?_1st@20;Half_"),   # soccer first-half lines
            re.compile(r"BASKETBALL_NBA_Game_"),
            re.compile(r"BASKETBALL_NBA_1st@20;Half_"),  # NBA first-half lines
            re.compile(r"BASKETBALL_NCAAB_Game_"),
            re.compile(r"BASKETBALL_WNBA_Game_"),
            re.compile(r"BASKETBALL_WNBA_1st@20;Half_"),  # WNBA first-half lines
            re.compile(r"FOOTBALL_NFL_Game_"),
            re.compile(r"FOOTBALL_NCAAF_Game_"),
            re.compile(r"FOOTBALL_COLLEGE_Game_"),
            re.compile(r"FOOTBALL_CANADIAN_Game_"),
            re.compile(r"FOOTBALL_NFL@20;SEAS@20;WIN_Game_"),   # NFL season win totals
            re.compile(r"FOOTBALL_NCAA@20;SEA@20;WIN_Game_"),  # CFB season win totals
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

    async def login(self, session, fast_mode=False):
        if not fast_mode:
            await asyncio.sleep(random.uniform(0.4, 0.8))
        async with session.get(self.login_page_url, headers=self.headers) as _:
            pass
        payload = self.config['betbck']['credentials']
        async with session.post(self.login_url, data=payload, headers=self.headers) as resp:
            text = await resp.text()
            if 'logout' not in text.lower():
                raise Exception('Login failed!')
        print('[LOG] Login successful.')

    async def fetch_selection_page(self, session, fast_mode=False):
        if not fast_mode:
            await asyncio.sleep(random.uniform(0.3, 0.6))
        async with session.get(self.selection_url, headers=self.headers) as resp:
            html = await resp.text()
            return html

    async def fetch_games_page(self, session, post_payload, delay=True):
        # Reduced delay for small sport selections - only delay if delay=True
        if delay:
            await asyncio.sleep(random.uniform(1.5, 3.0))
        async with session.post(self.games_url, data=post_payload, headers=self.headers) as resp:
            # Check for rate limiting
            if resp.status == 429 or resp.status == 403:
                logger.warning(f"[BetBCK Async] Rate limited: HTTP {resp.status}, waiting 10 seconds...")
                await asyncio.sleep(10)
                raise Exception(f"BetBCK rate limited: HTTP {resp.status}")
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
            def _clean_team(div):
                # Use the span with data-language if available (same as betbck_scraper.py)
                name_span = div.find('span', {'data-language': True})
                raw = name_span.get_text(strip=True) if name_span else div.get_text(strip=True)
                # Strip rotation numbers (e.g. "551Philadelphia" -> "Philadelphia")
                raw = re.sub(r'^\d{3,7}\s*', '', raw).strip()
                # Strip must-start pitcher info (e.g. "M Fried - L must start")
                raw = re.sub(r'\s*-\s*[A-Za-z\s.]+\s*-\s*[RLrl]\s*(must\s*start|sta\.?)\s*$', '', raw, flags=re.IGNORECASE).strip()
                raw = re.sub(r'\s*[A-Z]\.\s*[A-Za-z\s.]+\s*-\s*[RLrl]\s*(must\s*start|sta\.?)\s*$', '', raw, flags=re.IGNORECASE).strip()
                # Strip H+R+E suffix
                raw = re.sub(r'\s*\((hits\+runs\+errors|h\+r\+e|hre)\)$', '', raw, flags=re.IGNORECASE).strip()
                return ' '.join(raw.split())
            home = _clean_team(div_t1)
            away = _clean_team(div_t2)
            if not home or not away: continue
            # Detect and strip period suffix so team names are clean for matching
            # BetBCK shows e.g. "New York Knicks 1H" / "Philadelphia 76ers 1H"
            _market_suffix = None
            for _pfx in (' 1H', ' 2H', ' 1Q', ' 2Q', ' 3Q', ' 4Q'):
                if home.endswith(_pfx) and away.endswith(_pfx):
                    _market_suffix = _pfx.strip()
                    home = home[:-len(_pfx)].strip()
                    away = away[:-len(_pfx)].strip()
                    break
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
                "game_total_under_odds": None,
                "home_team_total_over_line": None,
                "home_team_total_over_odds": None,
                "home_team_total_under_line": None,
                "home_team_total_under_odds": None,
                "away_team_total_over_line": None,
                "away_team_total_over_odds": None,
                "away_team_total_under_line": None,
                "away_team_total_under_odds": None,
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
                    # Team Totals (columns 3 and 4 for each row)
                    if len(tds_top) > 3:
                        tt_line, tt_odds = self.extract_total_from_td(tds_top[3], over=True)
                        if tt_line is not None:
                            odds["home_team_total_over_line"] = tt_line
                            odds["home_team_total_over_odds"] = tt_odds
                    if len(tds_top) > 4:
                        tt_line, tt_odds = self.extract_total_from_td(tds_top[4], over=False)
                        if tt_line is not None:
                            odds["home_team_total_under_line"] = tt_line
                            odds["home_team_total_under_odds"] = tt_odds
                    if len(tds_bot) > 3:
                        tt_line, tt_odds = self.extract_total_from_td(tds_bot[3], over=True)
                        if tt_line is not None:
                            odds["away_team_total_over_line"] = tt_line
                            odds["away_team_total_over_odds"] = tt_odds
                    if len(tds_bot) > 4:
                        tt_line, tt_odds = self.extract_total_from_td(tds_bot[4], over=False)
                        if tt_line is not None:
                            odds["away_team_total_under_line"] = tt_line
                            odds["away_team_total_under_odds"] = tt_odds
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
                    # Use current year, but check if the date has already passed
                    current_year = datetime.now().year
                    try:
                        dt = dateutil.parser.parse(f"{current_year}-{month:02d}-{day:02d} {time}")
                        # If the date is in the past, assume it's next year
                        if dt < datetime.now():
                            dt = dateutil.parser.parse(f"{current_year + 1}-{month:02d}-{day:02d} {time}")
                        norm_date = dt.strftime('%Y-%m-%dT%H:%M')
                    except Exception as e:
                        logger.warning(f"[BetBCK] Error parsing date '{date_str}': {e}")
                        norm_date = f"{current_year}-{month:02d}-{day:02d}T{time}"
            # Check for data-sport attribute
            if gw.has_attr('data-sport'):
                sport = gw.get('data-sport', '').strip().lower()
                logger.debug(f"[BetBCK] Found data-sport attribute: '{sport}' for {home} vs {away}")
            else:
                sport = 'soccer'
                logger.debug(f"[BetBCK] No data-sport attribute, defaulting to soccer for {home} vs {away}")
            
            # Also check for other sport indicators in the class names
            class_names = ' '.join(gw.get('class', []))
            if 'basketball' in class_names.lower():
                sport = 'basketball'
                logger.debug(f"[BetBCK] Detected basketball from class names for {home} vs {away}")
            elif 'football' in class_names.lower():
                sport = 'football'
                logger.debug(f"[BetBCK] Detected football from class names for {home} vs {away}")
            elif 'baseball' in class_names.lower():
                sport = 'baseball'
                logger.debug(f"[BetBCK] Detected baseball from class names for {home} vs {away}")
            elif 'hockey' in class_names.lower():
                sport = 'hockey'
                logger.debug(f"[BetBCK] Detected hockey from class names for {home} vs {away}")
            teams = sorted([norm_home, norm_away])
            game_id = hashlib.md5(f"{teams[0]}_{teams[1]}_{sport}_{norm_date}_{_market_suffix or ''}".encode()).hexdigest()[:8]
            found_games_data.append({
                "betbck_game_id": game_id,
                "betbck_site_home_team": home,
                "betbck_site_away_team": away,
                "betbck_site_odds": odds,
                "timestamp": datetime.now().isoformat(),
                "event_datetime": norm_date,
                "sport": sport,
                "market_suffix": _market_suffix,
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
            # Include market_suffix in key so "Arsenal FG" and "Arsenal 1H" are NOT treated as dupes
            key = (g['betbck_site_home_team'], g['betbck_site_away_team'], g.get('market_suffix'))
            if key not in seen:
                deduped.append(g)
                seen.add(key)
        return deduped

    async def run(self):
        # Determine if this is a fast mode run (small sport selection)
        is_fast_mode = len(self.sport_filters) > 0 and len(self.sport_filters) <= 2
        
        timeout = aiohttp.ClientTimeout(total=300)  # 5-min cap; large pages need time to download
        async with aiohttp.ClientSession(headers=self.headers, timeout=timeout) as session:
            await self.login(session, fast_mode=is_fast_mode)
            selection_html = await self.fetch_selection_page(session, fast_mode=is_fast_mode)
            selection_soup = BeautifulSoup(selection_html, 'html.parser')
            inet_wager_input = selection_soup.find('input', {'name': 'inetWagerNumber'})
            inet_wager_value = inet_wager_input['value'] if inet_wager_input else "0.1234567890123456"
            all_checkboxes = selection_soup.find_all('input', {'type': 'checkbox'})
            
            # Filter checkboxes based on sport_filters
            if self.sport_filters:
                # Build exact match patterns for selected sports
                selected_patterns = []
                for sport_key in self.sport_filters:
                    if sport_key in self.sport_checkbox_mapping:
                        patterns = self.sport_checkbox_mapping[sport_key]
                        for pattern in patterns:
                            # Store pattern as-is (checkbox names use @20; for spaces, so match literally)
                            selected_patterns.append(pattern)
                
                # Filter checkboxes to only those matching selected sports
                checkbox_names = []
                for cb in all_checkboxes:
                    cb_name = cb.get('name')
                    if cb_name:
                        # Check if checkbox name matches any selected pattern
                        for pattern in selected_patterns:
                            # Handle wildcard patterns (.*?)
                            if '.*?' in pattern:
                                # Convert pattern to regex: escape everything except .*?
                                pattern_parts = pattern.split('.*?')
                                pattern_regex = '.*?'.join([re.escape(p) for p in pattern_parts])
                                if re.search(pattern_regex, cb_name):  # Use search instead of match
                                    checkbox_names.append(cb_name)
                                    break
                            else:
                                # For exact patterns, check if pattern appears in checkbox name
                                # Checkbox names might have suffixes like _Game_123 or @20;Game_
                                # So we check if the pattern is contained in the name, not just starts with
                                if pattern in cb_name or cb_name.startswith(pattern):
                                    checkbox_names.append(cb_name)
                                    break
                print(f"[LOG] Filtered to {len(checkbox_names)} checkboxes for sports: {self.sport_filters}")
                if len(checkbox_names) == 0:
                    print(f"[LOG] WARNING: No checkboxes found! Available checkbox names (first 20):")
                    available_names = [cb.get('name') for cb in all_checkboxes if cb.get('name')][:20]
                    for name in available_names:
                        print(f"[LOG]   - {name}")
                    print(f"[LOG] Patterns we're looking for: {selected_patterns}")
            else:
                # Use all checkboxes (original behavior) - but prioritize by sport importance
                all_checkbox_dict = {}
                for cb in all_checkboxes:
                    cb_name = cb.get('name')
                    if cb_name and any(p.fullmatch(cb_name) for p in self.checkbox_patterns):
                        # Determine priority based on sport
                        priority = 999  # Default low priority
                        for i, sport_key in enumerate(self.sport_priority):
                            if sport_key in self.sport_checkbox_mapping:
                                patterns = self.sport_checkbox_mapping[sport_key]
                                for pattern in patterns:
                                    if '.*?' in pattern:
                                        pattern_parts = pattern.split('.*?')
                                        pattern_regex = '.*?'.join([re.escape(p) for p in pattern_parts])
                                        if re.match(pattern_regex, cb_name):
                                            priority = i
                                            break
                                    elif cb_name.startswith(pattern):
                                        priority = i
                                        break
                                if priority != 999:
                                    break
                        all_checkbox_dict[cb_name] = priority
                
                # Sort by priority (lower number = higher priority)
                checkbox_names = sorted(all_checkbox_dict.keys(), key=lambda x: all_checkbox_dict[x])
                print(f"[LOG] Found {len(checkbox_names)} sport/league checkboxes for async POST (all sports, prioritized).")
            
            # Log all checkbox names for debugging
            all_checkbox_names = [cb.get('name') for cb in all_checkboxes if cb.get('name')]
            print(f"[LOG] All available checkboxes ({len(all_checkbox_names)}):")
            for i, name in enumerate(all_checkbox_names[:20]):  # Show first 20
                print(f"   {i+1}. {name}")
            if len(all_checkbox_names) > 20:
                print(f"   ... and {len(all_checkbox_names) - 20} more")
            # Season win total checkboxes generate huge HTML responses (one row per team,
            # 130+ CFB + 32 NFL teams) that push a combined request past BetBCK's transfer
            # limit.  Split them out and send as a second sequential request with a natural
            # pause — same pattern as a user clicking a second tab.  Everything else goes in
            # the original single request, exactly as it always has.
            SEASON_WIN_PATTERNS = ("SEAS@20;WIN", "SEA@20;WIN")
            season_win_names = [n for n in checkbox_names if any(p in n for p in SEASON_WIN_PATTERNS)]
            main_names       = [n for n in checkbox_names if not any(p in n for p in SEASON_WIN_PATTERNS)]
            MAX_CONCURRENT_BETBCK_REQUESTS = 5  # Reduced from unlimited to 5 concurrent requests
            games_htmls = []

            if len(checkbox_names) == 0:
                logger.error(f"[LOG] ERROR: No checkboxes found for sport filters: {self.sport_filters}")
                logger.error(f"[LOG] This means no games will be scraped. Check the patterns above.")
                all_games = []
                deduped_games = self.deduplicate_games(all_games)
                os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
                with open(self.output_file, "w", encoding="utf-8") as f:
                    json.dump(deduped_games, f, indent=2, ensure_ascii=False)
                print(f"[LOG] Saved 0 games to {self.output_file} (no checkboxes found)")
                return  # Exit early - no point continuing

            async def _post_checkboxes(names, label):
                """Send a single POST for the given checkbox names and return the HTML."""
                post_payload = {
                    'keyword_search': '',
                    'inetWagerNumber': inet_wager_value,
                    'inetSportSelection': 'sport',
                    'contestType1': '', 'contestType2': '', 'contestType3': '',
                    'x': random.randint(75, 85), 'y': random.randint(10, 15),
                }
                for name in names:
                    post_payload[name] = 'on'
                logger.info(f"[LOG] {label}: sending POST with {len(names)} checkboxes")
                try:
                    html = await self.fetch_games_page(session, post_payload, delay=True)
                    logger.info(f"[LOG] {label}: received {len(html)} chars")
                    return html
                except Exception as e:
                    import traceback
                    logger.error(f"[BetBCK Async] {label} error: {e}\n{traceback.format_exc()}")
                    return None

            # Request 1 — all normal checkboxes (same single request that has always worked)
            if main_names:
                html = await _post_checkboxes(main_names, "Main request")
                if html:
                    games_htmls.append(html)

            # Request 2 — season win totals only, sent separately with a human-pace delay
            if season_win_names:
                pause = random.uniform(3.0, 6.0)
                logger.info(f"[LOG] Waiting {pause:.1f}s before season-win-total request...")
                await asyncio.sleep(pause)
                html = await _post_checkboxes(season_win_names, "Season-win-totals request")
                if html:
                    games_htmls.append(html)
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

async def _get_all_betbck_games_async(sport_filters=None):
    scraper = BetBCKAsyncScraper(sport_filters=sport_filters)
    await scraper.run()
    with open(scraper.output_file, "r", encoding="utf-8") as f:
        return json.load(f)

if __name__ == "__main__":
    games = get_all_betbck_games()
    print(f"Scraped {len(games)} games")
    print(json.dumps(games[:2], indent=2, ensure_ascii=False)) 