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
            # Outright futures — league winner props
            'epl_winner':  ['SOCCER_ENGLAND@20;PREMIER@20;LEAGUE@20;FUTURES_Prop_TO@20;WIN@20;OUTRIGHT'],
            'la_liga_winner': ['SOCCER_SPAIN@20;LA@20;LIGA@20;FUTURES_Prop_TO@20;WIN@20;OUTRIGHT'],
            'seria_a_winner': ['SOCCER_ITALY@20;SER@20;A_FUTURES_Prop_TO@20;WIN@20;OUTRIGHT'],
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
        # Futures-only sports: not included in the default "all sports" scrape.
        # Request them explicitly via sport_filters in the futures pipeline.
        self.futures_only_sports = {'nfl_season_wins', 'cfb_season_wins', 'epl_winner', 'la_liga_winner', 'seria_a_winner'}
        self.sport_priority = [
            'nfl', 'nba', 'nhl', 'mlb',            # Major US sports first
            'ncaa_football', 'ncaa_basketball',      # College sports
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
        self.leagues_url = self.config['betbck'].get(
            'leagues_api_url',
            'https://betbck.com/cloud/api/League/Get_SportsLeagues',
        )
        # Map UI sport keys → which Get_SportsLeagues rows to pull (exact API codes).
        # Matchers receive a league dict from Get_SportsLeagues.
        self.sport_league_matchers = {
            "nfl": lambda L: (
                L.get("SportType") == "FOOTBALL"
                and L.get("SportSubType") in ("NFL", "NFL PRESEAS")
                and L.get("PeriodDescription") in ("Game", "1st Half")
            ),
            "ncaa_football": lambda L: (
                L.get("SportType") == "FOOTBALL"
                and L.get("SportSubType") == "COLLEGE"
                and L.get("PeriodDescription") in ("Game", "1st Half")
            ),
            "nba": lambda L: (
                L.get("SportType") == "BASKETBALL"
                and L.get("SportSubType") == "NBA"
                and L.get("PeriodDescription") in ("Game", "1st Half", "1st Quarter")
            ),
            "ncaa_basketball": lambda L: (
                L.get("SportType") == "BASKETBALL"
                and L.get("SportSubType") in ("NCAA", "NCAAB", "NCAA EXTRA")
                and L.get("PeriodDescription") in ("Game", "1st Half", "1st Quarter")
            ),
            "nhl": lambda L: (
                L.get("SportType") == "HOCKEY"
                and L.get("SportSubType") == "NHL"
                and L.get("PeriodDescription") in ("Game", "1st Period")
            ),
            "mlb": lambda L: (
                L.get("SportType") == "BASEBALL"
                and L.get("SportSubType") == "MLB"
                and L.get("PeriodDescription") in ("Game", "1st 5 Innings")
            ),
            "wnba": lambda L: (
                L.get("SportType") == "BASKETBALL"
                and L.get("SportSubType") == "WNBA"
                and L.get("PeriodDescription") in ("Game", "1st Half", "1st Quarter")
            ),
            "soccer_major": lambda L: (
                L.get("SportType") == "SOCCER"
                and L.get("SportSubType") in (
                    "ENG PREM", "UEFA CH LEA", "UEFA EU LEA", "GER BUNDE",
                    "SPA LA LIGA", "ITA SER A", "FRE LIGUE1", "USA MLS",
                    "MEX - PR DIV", "BRA - SER A", "ARG PRI DIV", "ENG LEA1", "ENG CHAMPI",
                )
                and L.get("PeriodDescription") in ("Game", "1st Half")
            ),
            # All soccer Game/1H boards — NOT futures, NOT props, NOT live
            "soccer": lambda L: (
                L.get("SportType") == "SOCCER"
                and str(L.get("PeriodDescription") or "") in ("Game", "1st Half")
                and "PROP" not in str(L.get("SportSubType") or "").upper()
                and "FUTURE" not in str(L.get("SportSubType") or "").upper()
                and "FUTURE" not in str(L.get("SportSubTypeDisplay") or "").upper()
                and str(L.get("PeriodDescription") or "").lower() != "prop"
            ),
            "nfl_season_wins": lambda L: (
                L.get("SportType") == "FOOTBALL"
                and L.get("SportSubType") in ("NFL SEAS WIN", "NFL ALT SW")
                and L.get("PeriodDescription") == "Game"
            ),
            "cfb_season_wins": lambda L: (
                L.get("SportType") == "FOOTBALL"
                and L.get("SportSubType") == "NCAA SEA WIN"
                and L.get("PeriodDescription") == "Game"
            ),
            "epl_winner": lambda L: (
                L.get("SportType") == "SOCCER"
                and (
                    "premier" in str(L.get("SportSubType") or "").lower()
                    or "premier" in str(L.get("SportSubTypeDisplay") or "").lower()
                )
                and str(L.get("PeriodDescription") or "").lower() == "prop"
                and "win" in str(L.get("SportSubType2") or "").lower()
            ),
            "la_liga_winner": lambda L: (
                L.get("SportType") == "SOCCER"
                and (
                    "la liga" in str(L.get("SportSubType") or "").lower()
                    or "la liga" in str(L.get("SportSubTypeDisplay") or "").lower()
                )
                and str(L.get("PeriodDescription") or "").lower() == "prop"
            ),
            "seria_a_winner": lambda L: (
                L.get("SportType") == "SOCCER"
                and (
                    "serie" in str(L.get("SportSubType") or "").lower()
                    or "serie" in str(L.get("SportSubTypeDisplay") or "").lower()
                )
                and str(L.get("PeriodDescription") or "").lower() == "prop"
            ),
        }
        # EV anti-bot pacing (seconds). Soccer can be many leagues — stay slow.
        self.EV_DELAY_MIN = 2.2
        self.EV_DELAY_MAX = 4.0
        # Prefer Game-only rows for EV to cut request count ~in half (1H still in POD path).
        self.EV_GAME_PERIOD_ONLY = True
        # If a sport would fire more than this many Lines calls, only pull Game period
        # and never exceed this many calls in one EV run (safety valve).
        self.EV_MAX_LEAGUE_CALLS = 20

    async def login(self, session, fast_mode=False):
        if not fast_mode:
            await asyncio.sleep(random.uniform(0.4, 0.8))
        page_headers = dict(self.headers)
        page_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        page_headers["Referer"] = self.login_page_url
        async with session.get(self.login_page_url, headers=page_headers) as _:
            pass
        creds = self.config['betbck']['credentials']
        customer_id = str(creds.get('customerID') or '').strip().upper()
        password = str(creds.get('password') or creds.get('Password') or '').strip().upper()
        domain = "betbck.com"
        payload = {
            "customerID": customer_id,
            "state": True,
            "password": password,
            "multiaccount": "1",
            "response_type": "code",
            "client_id": customer_id,
            "domain": domain,
            "redirect_uri": domain,
            "operation": "authenticateCustomer",
            "RRO": 1,
        }
        headers = dict(self.headers)
        headers["Referer"] = self.login_page_url
        headers["Content-Type"] = "application/json"
        headers["Authorization"] = "Bearer undefined"
        async with session.post(self.login_url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                raise Exception(f'Login failed! HTTP {resp.status}')
            data = await resp.json(content_type=None)
            token = data.get("code") or data.get("token")
            if not token:
                raise Exception('Login failed! No token in authenticateCustomer response')
            account = data.get("accountInfo") or {}
            self._cloud_auth = {
                "token": token,
                "customer_id": str(account.get("customerID") or customer_id).strip().upper(),
                "office": str(account.get("Office") or "").strip(),
            }
        print('[LOG] Login successful (cloud API).')

    async def fetch_sports_leagues(self, session, delay=True):
        """POST Get_SportsLeagues — same call the sbsports selection page uses."""
        if delay:
            await asyncio.sleep(random.uniform(0.4, 0.9))
        auth = getattr(self, "_cloud_auth", None) or {}
        if not auth.get("token"):
            raise Exception("BetBCK cloud auth missing — login first")
        form = {
            "customerID": auth.get("customer_id") or "",
            "wagerType": "Straight",
            "office": auth.get("office") or "",
            "placeLateFlag": "false",
            "operation": "Get_SportsLeagues",
            "RRO": "1",
        }
        headers = dict(self.headers)
        headers["Authorization"] = f"Bearer {auth['token']}"
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["Referer"] = self.selection_url
        async with session.post(self.leagues_url, data=form, headers=headers) as resp:
            if resp.status in (401, 403, 429):
                raise Exception(f"BetBCK leagues auth/rate limited: HTTP {resp.status}")
            data = await resp.json(content_type=None)
            leagues = data.get("Leagues") if isinstance(data, dict) else None
            return leagues if isinstance(leagues, list) else []

    async def fetch_lines_json(
        self,
        session,
        *,
        keyword="",
        sport_type="",
        sport_subtype="",
        period="Game",
        period_number=0,
        delay=True,
    ):
        """POST Get_LeagueLines2 (same endpoint as sbsports search-line / league click)."""
        if delay:
            dmin = getattr(self, "EV_DELAY_MIN", 2.2)
            dmax = getattr(self, "EV_DELAY_MAX", 4.0)
            await asyncio.sleep(random.uniform(dmin, dmax))
        auth = getattr(self, "_cloud_auth", None) or {}
        if not auth.get("token"):
            raise Exception("BetBCK cloud auth missing — login first")
        form = {
            "customerID": auth.get("customer_id") or "",
            "operation": "Get_LeagueLines2",
            "sportType": sport_type,
            "sportSubType": sport_subtype,
            "period": period or "Game",
            "hourFilter": "0",
            "propDescription": "",
            "wagerType": "Straight",
            "keyword": keyword,
            "office": auth.get("office") or "",
            "correlationID": "",
            "periodNumber": str(period_number if period_number is not None else 0),
            "periods": "0",
            "rotOrder": "0",
            "placeLateFlag": "false",
            "RRO": "1",
        }
        headers = dict(self.headers)
        headers["Authorization"] = f"Bearer {auth['token']}"
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["Referer"] = self.selection_url
        async with session.post(self.games_url, data=form, headers=headers) as resp:
            if resp.status in (401, 403, 429):
                logger.warning(f"[BetBCK Async] Auth/rate HTTP {resp.status}")
                raise Exception(f"BetBCK rate/auth limited: HTTP {resp.status}")
            text = await resp.text()
            return text

    def _select_leagues_for_filters(self, leagues, filters):
        """Pick Get_SportsLeagues rows matching our sport_filters keys."""
        selected = []
        seen = set()
        for key in filters:
            # Futures-only markets are opt-in (not pulled during default "all sports")
            if key in self.futures_only_sports and not self.sport_filters:
                continue
            matcher = self.sport_league_matchers.get(key)
            if not matcher:
                print(f"[LOG] No league matcher for sport filter '{key}' — skipping")
                continue
            matched = 0
            for league in leagues:
                if not isinstance(league, dict):
                    continue
                if int(league.get("Active") or 0) != 1:
                    continue
                try:
                    ok = bool(matcher(league))
                except Exception:
                    ok = False
                if not ok:
                    continue
                st = str(league.get("SportType") or "").strip()
                ss = str(league.get("SportSubType") or "").strip()
                pd = str(league.get("PeriodDescription") or "Game").strip()
                pn = league.get("PeriodNumber", 0)
                dedupe_key = (st, ss, pd, pn)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                selected.append(league)
                matched += 1
            print(f"[LOG] Filter '{key}' matched {matched} league row(s)")
        return selected

    def parse_games_from_lines_json(self, json_text):
        """Convert Get_LeagueLines2 JSON into the async scraper's game dicts."""
        try:
            payload = json.loads(json_text) if isinstance(json_text, str) else json_text
        except Exception:
            return []
        lines = payload.get("Lines") or []
        found = []
        for line in lines:
            if not isinstance(line, dict):
                continue
            if str(line.get("Status") or "").strip().upper() not in ("O", ""):
                continue
            home = str(line.get("Team1ID") or "").strip()
            away = str(line.get("Team2ID") or "").strip()
            if not home or not away:
                continue
            period = str(line.get("PeriodDescription") or "").strip()
            market_suffix = None
            pl = period.lower()
            if "1st half" in pl:
                market_suffix = "1H"
            elif "2nd half" in pl:
                market_suffix = "2H"
            elif "1st 5" in pl or "first 5" in pl:
                market_suffix = "1H"
            elif "1st quarter" in pl or "1q" in pl:
                market_suffix = "1Q"
            # Skip props
            blob = f"{home} {away} {line.get('SportSubType')} {line.get('SportSubTypeDisplay')}".lower()
            if "prop" in blob or is_prop_market_by_name(home, away):
                if not getattr(self, "_allow_outright_props", False):
                    continue

            def _amer(v):
                if v is None:
                    return None
                try:
                    n = int(v)
                except (TypeError, ValueError):
                    return None
                return f"+{n}" if n > 0 else str(n)

            sp = line.get("Spread")
            top_spreads, bottom_spreads = [], []
            if sp is not None:
                adj1, adj2 = _amer(line.get("SpreadAdj1")), _amer(line.get("SpreadAdj2"))
                if adj1:
                    top_spreads.append({"line": str(sp), "odds": adj1})
                if adj2:
                    try:
                        bottom_spreads.append({"line": str(-float(sp)), "odds": adj2})
                    except (TypeError, ValueError):
                        bottom_spreads.append({"line": str(sp), "odds": adj2})

            tot = line.get("TotalPoints")
            odds = {
                "site_top_team_moneyline_american": _amer(line.get("MoneyLine1")),
                "site_bottom_team_moneyline_american": _amer(line.get("MoneyLine2")),
                "draw_moneyline_american": _amer(line.get("MoneyLineDraw")),
                "site_top_team_spreads": top_spreads,
                "site_bottom_team_spreads": bottom_spreads,
                "game_total_line": str(tot) if tot is not None else None,
                "game_total_over_odds": _amer(line.get("TtlPtsAdj1")),
                "game_total_under_odds": _amer(line.get("TtlPtsAdj2")),
                "home_team_total_over_line": str(line["Team1TotalPoints"]) if line.get("Team1TotalPoints") is not None else None,
                "home_team_total_over_odds": _amer(line.get("Team1TtlPtsAdj1")),
                "home_team_total_under_line": str(line["Team1TotalPoints"]) if line.get("Team1TotalPoints") is not None else None,
                "home_team_total_under_odds": _amer(line.get("Team1TtlPtsAdj2")),
                "away_team_total_over_line": str(line["Team2TotalPoints"]) if line.get("Team2TotalPoints") is not None else None,
                "away_team_total_over_odds": _amer(line.get("Team2TtlPtsAdj1")),
                "away_team_total_under_line": str(line["Team2TotalPoints"]) if line.get("Team2TotalPoints") is not None else None,
                "away_team_total_under_odds": _amer(line.get("Team2TtlPtsAdj2")),
            }
            found.append({
                "betbck_site_home_team": home,
                "betbck_site_away_team": away,
                "betbck_game_id": str(line.get("GameNum") or f"{home}_{away}"),
                "market_suffix": market_suffix,
                "betbck_site_odds": odds,
                "lines": [],
                "game_datetime": line.get("GameDateTime"),
                "sport_type": str(line.get("SportType") or "").strip(),
                "sport_subtype": str(line.get("SportSubTypeDisplay") or line.get("SportSubType") or "").strip(),
            })
        return found

    async def fetch_selection_page(self, session, fast_mode=False):
        if not fast_mode:
            await asyncio.sleep(random.uniform(0.3, 0.6))
        async with session.get(self.selection_url, headers=self.headers) as resp:
            html = await resp.text()
            return html

    async def fetch_games_page(self, session, post_payload, delay=True):
        # Legacy HTML checkbox POST — kept for compatibility but cloud path preferred.
        if delay:
            await asyncio.sleep(random.uniform(1.5, 3.0))
        async with session.post(self.games_url, data=post_payload, headers=self.headers) as resp:
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
            # Robust prop/corner/future filtering.
            # _allow_outright_props: set to True on the instance by the futures
            # outright pipeline so that EPL/league-winner rows are not dropped.
            _is_outright_away = bool(re.search(
                r"(outright|to\s+win|win\s+outright|league\s+winner|champion)",
                away, re.IGNORECASE,
            ))
            if is_prop_market_by_name(home, away) and not (
                getattr(self, "_allow_outright_props", False) and _is_outright_away
            ):
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
        """Cloud API board scrape: Get_SportsLeagues → careful Get_LeagueLines2 per league.

        Anti-bot rules for EV:
        - One login, one leagues list, then sequential Lines calls only
        - Prefer Game-period only (cuts volume)
        - Hard cap on number of Lines calls per run
        - 2.2–4.0s jitter between Lines calls
        """
        is_fast_mode = len(self.sport_filters) > 0 and len(self.sport_filters) <= 2
        filters = self.sport_filters or list(self.sport_priority)

        # One connection to BetBCK — never parallelize Lines calls.
        connector = aiohttp.TCPConnector(
            limit=1,
            limit_per_host=1,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )
        timeout = aiohttp.ClientTimeout(total=600, sock_connect=20, sock_read=40)
        async with aiohttp.ClientSession(
            headers=self.headers, timeout=timeout, connector=connector
        ) as session:
            await self.login(session, fast_mode=is_fast_mode)
            try:
                await self.fetch_selection_page(session, fast_mode=True)
            except Exception as e:
                logger.warning(f"[BetBCK Async] skin page fetch skipped: {e}")

            try:
                leagues = await self.fetch_sports_leagues(session, delay=True)
            except Exception as e:
                logger.error(f"[BetBCK Async] Get_SportsLeagues failed: {e}")
                leagues = []
            print(f"[LOG] Get_SportsLeagues returned {len(leagues)} league row(s)")

            selected = self._select_leagues_for_filters(leagues, filters)

            # Prefer Game-only for EV volume control (POD keyword search still gets 1H).
            if self.EV_GAME_PERIOD_ONLY:
                game_only = [
                    L for L in selected
                    if str(L.get("PeriodDescription") or "").strip() == "Game"
                ]
                if game_only:
                    print(
                        f"[LOG] EV Game-period filter: {len(selected)} -> {len(game_only)} "
                        f"league call(s) (1H skipped to reduce request volume)"
                    )
                    selected = game_only

            if len(selected) > self.EV_MAX_LEAGUE_CALLS:
                print(
                    f"[LOG] SAFETY CAP: {len(selected)} leagues exceeds "
                    f"EV_MAX_LEAGUE_CALLS={self.EV_MAX_LEAGUE_CALLS}. "
                    f"Truncating to first {self.EV_MAX_LEAGUE_CALLS} "
                    f"(re-run with a narrower sport filter if needed)."
                )
                selected = selected[: self.EV_MAX_LEAGUE_CALLS]

            if not selected:
                print(f"[LOG] WARNING: no leagues matched filters={filters}; nothing to scrape")
                deduped_games = []
                out_dir = os.path.dirname(self.output_file)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                with open(self.output_file, "w", encoding="utf-8") as f:
                    json.dump(deduped_games, f, indent=2, ensure_ascii=False)
                print(f"[LOG] Saved 0 deduplicated games to {self.output_file}")
                return

            est_sec = len(selected) * ((self.EV_DELAY_MIN + self.EV_DELAY_MAX) / 2)
            print(
                f"[LOG] Cloud Lines scrape: {len(selected)} sequential call(s) for "
                f"filters={filters} (~{est_sec:.0f}s with human pacing)"
            )

            all_games = []
            for idx, league in enumerate(selected):
                stype = str(league.get("SportType") or "").strip()
                ssub = str(league.get("SportSubType") or "").strip()
                period = str(league.get("PeriodDescription") or "Game").strip()
                pnum = league.get("PeriodNumber", 0)
                display = str(league.get("SportSubTypeDisplay") or ssub).strip()
                try:
                    json_text = await self.fetch_lines_json(
                        session,
                        keyword="",
                        sport_type=stype,
                        sport_subtype=ssub,
                        period=period,
                        period_number=pnum,
                        delay=(idx > 0),
                    )
                    batch = self.parse_games_from_lines_json(json_text)
                    print(
                        f"[LOG] Get_LeagueLines2 {stype!r}/{ssub!r} "
                        f"period={period!r} ({display}) -> {len(batch)} lines"
                    )
                    all_games.extend(batch)
                except Exception as e:
                    import traceback
                    logger.error(
                        f"[BetBCK Async] Lines fetch failed ({stype}/{ssub}/{period}): {e}\n"
                        f"{traceback.format_exc()}"
                    )

            deduped_games = self.deduplicate_games(all_games)
            out_dir = os.path.dirname(self.output_file)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
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


async def _get_betbck_outright_games_async(market_sport_filter: str) -> list[dict]:
    """Fetch BetBCK outright winner props (e.g. 'epl_winner') bypassing the
    prop filter so that rows like "Arsenal | TO WIN OUTRIGHT" are kept.

    The underlying parse_games filter is bypassed only for rows whose away_team
    matches an outright-winner pattern; all other rows remain filtered normally.
    """
    scraper = BetBCKAsyncScraper(sport_filters=[market_sport_filter])
    scraper._allow_outright_props = True   # bypass is_prop_market_by_name for outrights
    await scraper.run()
    with open(scraper.output_file, "r", encoding="utf-8") as f:
        return json.load(f)

if __name__ == "__main__":
    games = get_all_betbck_games()
    print(f"Scraped {len(games)} games")
    print(json.dumps(games[:2], indent=2, ensure_ascii=False)) 