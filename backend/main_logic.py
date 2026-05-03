import traceback
import re
import math
import datetime as _dt
from hashlib import sha256
try:
    from betbck_scraper import scrape_betbck_for_game
    from betbck_request_manager import scrape_betbck_for_game_queued
    print("[MainLogic] SUCCESS: 'scrape_betbck_for_game' imported successfully.")
except ImportError as e:
    print(f"[MainLogic] CRITICAL_ERROR: {e}")
    raise
from utils import normalize_team_name_for_matching, process_event_odds_for_display
from utils.pod_utils import analyze_markets_for_ev, analyze_markets_multi_row, clean_pod_team_name_for_search
from pinnacle_fetcher import fetch_live_pinnacle_event_odds
try:
    from alert_logger import get_logger_for_event
except ImportError:
    def get_logger_for_event(event_id):
        return None

def american_to_decimal(american_odds):
    if american_odds is None or american_odds == "N/A": return None
    try:
        odds = float(str(american_odds).replace('PK', '0'))
        if odds > 0: return (odds / 100) + 1
        return (100 / abs(odds)) + 1
    except (ValueError, TypeError): return None

def calculate_ev(bet_decimal_odds, true_decimal_odds):
    if not all([bet_decimal_odds, true_decimal_odds]) or true_decimal_odds <= 1.0: return None
    ev = (bet_decimal_odds / true_decimal_odds) - 1
    return ev if -0.5 < ev < 0.20 else None

def determine_betbck_search_term(pod_home_team_raw, pod_away_team_raw):
    pod_home_clean = clean_pod_team_name_for_search(pod_home_team_raw)
    pod_away_clean = clean_pod_team_name_for_search(pod_away_team_raw)
    
    print(f"[DEBUG] determine_betbck_search_term - Raw: Home='{pod_home_team_raw}', Away='{pod_away_team_raw}'")
    print(f"[DEBUG] determine_betbck_search_term - Cleaned: Home='{pod_home_clean}', Away='{pod_away_clean}'")

    known_terms = {
        # International soccer
        "south korea": "Korea", "north korea": "Korea DPR", "faroe islands": "Faroe",
        "ivory coast": "Cote d'Ivoire", "czechia": "Czech Republic",
        "china pr": "China", "bahrain": "Bahrain", "italy": "Italy",
        "romania": "Romania", "cyprus": "Cyprus", "athletic club": "Athletic Club",
        # MLB — city+nickname → nickname (critical for short/ambiguous last words)
        "milwaukee brewers": "Brewers",
        "philadelphia phillies": "Phillies",
        "los angeles angels": "Angels",
        "pittsburgh pirates": "Pirates",
        "arizona diamondbacks": "Diamondbacks",
        "san diego padres": "Padres",
        "st. louis cardinals": "Cardinals",
        "chicago white sox": "White Sox",
        "boston red sox": "Red Sox",
        "new york yankees": "Yankees",
        "new york mets": "Mets",
        "los angeles dodgers": "Dodgers",
        "san francisco giants": "Giants",
        "atlanta braves": "Braves",
        "houston astros": "Astros",
        "colorado rockies": "Rockies",
        "seattle mariners": "Mariners",
        "tampa bay rays": "Rays",
        "toronto blue jays": "Blue Jays",
        "minnesota twins": "Twins",
        "detroit tigers": "Tigers",
        "cleveland guardians": "Guardians",
        "baltimore orioles": "Orioles",
        "kansas city royals": "Royals",
        "texas rangers": "Rangers",
        "oakland athletics": "Athletics",
        "miami marlins": "Marlins",
        "chicago cubs": "Cubs",
        "cincinnati reds": "Reds",
        "washington nationals": "Nationals",
        # NBA — full names for teams whose last word is ambiguous or short
        "golden state warriors": "Warriors",
        "los angeles lakers": "Lakers",
        "los angeles clippers": "Clippers",
        "new york knicks": "Knicks",
        "chicago bulls": "Bulls",
        "boston celtics": "Celtics",
        "miami heat": "Heat",
        "dallas mavericks": "Mavericks",
        "brooklyn nets": "Nets",
        "philadelphia 76ers": "76ers",
        "milwaukee bucks": "Bucks",
        "phoenix suns": "Suns",
        "denver nuggets": "Nuggets",
        "utah jazz": "Jazz",
        "portland trail blazers": "Trail Blazers",
        "oklahoma city thunder": "Thunder",
        "san antonio spurs": "Spurs",
        "atlanta hawks": "Hawks",
        "charlotte hornets": "Hornets",
        "cleveland cavaliers": "Cavaliers",
        "detroit pistons": "Pistons",
        "indiana pacers": "Pacers",
        "memphis grizzlies": "Grizzlies",
        "minnesota timberwolves": "Timberwolves",
        "new orleans pelicans": "Pelicans",
        "orlando magic": "Magic",
        "sacramento kings": "Kings",
        "toronto raptors": "Raptors",
        "washington wizards": "Wizards",
        "houston rockets": "Rockets",
        # NFL — full names for teams whose last word is ambiguous
        "new england patriots": "Patriots",
        "kansas city chiefs": "Chiefs",
        "green bay packers": "Packers",
        "dallas cowboys": "Cowboys",
        "san francisco 49ers": "49ers",
        "chicago bears": "Bears",
        "new york giants": "Giants",
        "new york jets": "Jets",
        "philadelphia eagles": "Eagles",
        "pittsburgh steelers": "Steelers",
        "seattle seahawks": "Seahawks",
        "las vegas raiders": "Raiders",
        "los angeles rams": "Rams",
        "los angeles chargers": "Chargers",
        "miami dolphins": "Dolphins",
        "buffalo bills": "Bills",
        "baltimore ravens": "Ravens",
        "cleveland browns": "Browns",
        "cincinnati bengals": "Bengals",
        "tennessee titans": "Titans",
        "jacksonville jaguars": "Jaguars",
        "houston texans": "Texans",
        "indianapolis colts": "Colts",
        "denver broncos": "Broncos",
        "minnesota vikings": "Vikings",
        "detroit lions": "Lions",
        "carolina panthers": "Panthers",
        "atlanta falcons": "Falcons",
        "new orleans saints": "Saints",
        "tampa bay buccaneers": "Buccaneers",
        "arizona cardinals": "Cardinals",
        "washington commanders": "Commanders",
        # NHL — full names for teams whose last word is short/ambiguous
        "toronto maple leafs": "Maple Leafs",
        "montreal canadiens": "Canadiens",
        "boston bruins": "Bruins",
        "new york rangers": "Rangers",
        "new york islanders": "Islanders",
        "chicago blackhawks": "Blackhawks",
        "detroit red wings": "Red Wings",
        "pittsburgh penguins": "Penguins",
        "philadelphia flyers": "Flyers",
        "washington capitals": "Capitals",
        "colorado avalanche": "Avalanche",
        "edmonton oilers": "Oilers",
        "calgary flames": "Flames",
        "vancouver canucks": "Canucks",
        "ottawa senators": "Senators",
        "winnipeg jets": "Jets",
        "minnesota wild": "Wild",
        "st. louis blues": "Blues",
        "nashville predators": "Predators",
        "dallas stars": "Stars",
        "tampa bay lightning": "Lightning",
        "florida panthers": "Panthers",
        "carolina hurricanes": "Hurricanes",
        "new jersey devils": "Devils",
        "buffalo sabres": "Sabres",
        "arizona coyotes": "Coyotes",
        "utah hockey club": "Utah HC",
        "seattle kraken": "Kraken",
        "vegas golden knights": "Golden Knights",
        "anaheim ducks": "Ducks",
        "los angeles kings": "Kings",
        "san jose sharks": "Sharks",
        "columbus blue jackets": "Blue Jackets",
    }
    if pod_home_clean.lower() in known_terms:
        search_term = known_terms[pod_home_clean.lower()]
        print(f"[DEBUG] Using known term for home team: '{search_term}'")
        return search_term, f"known_term map for '{pod_home_clean}'"
    if pod_away_clean.lower() in known_terms:
        search_term = known_terms[pod_away_clean.lower()]
        print(f"[DEBUG] Using known term for away team: '{search_term}'")
        return search_term, f"known_term map for away '{pod_away_clean}'"

    parts = pod_home_clean.split()
    if parts:
        if len(parts) > 1 and len(parts[-1]) > 3 and parts[-1].lower() not in ['fc', 'sc', 'united', 'city', 'club', 'de', 'do', 'ac', 'if', 'bk', 'aif', 'kc', 'sr', 'mg', 'us', 'br']:
            search_term = parts[-1]
            print(f"[DEBUG] Using last part of home team: '{search_term}'")
            return search_term, f"last word of home team '{pod_home_clean}'"
        elif len(parts[0]) > 2 and parts[0].lower() not in ['fc', 'sc', 'ac', 'if', 'bk', 'de', 'do', 'aif', 'kc', 'sr', 'mg', 'us', 'br']:
            search_term = parts[0]
            print(f"[DEBUG] Using first part of home team: '{search_term}'")
            return search_term, f"first word of home team '{pod_home_clean}'"
        else:
            print(f"[DEBUG] Using full cleaned home team: '{pod_home_clean}'")
            return pod_home_clean, f"full cleaned home team"
    print(f"[DEBUG] Using full cleaned home team (fallback): '{pod_home_clean}'")
    return (pod_home_clean if pod_home_clean else ""), "fallback to full cleaned home team"

def process_alert_and_scrape_betbck(event_id, original_alert_details, processed_pinnacle_data, scrape_betbck=True):
    alog = get_logger_for_event(event_id)
    try:
        if alog and original_alert_details:
            alog.log_raw_alert(original_alert_details)

        if not original_alert_details or not processed_pinnacle_data:
            if alog:
                alog.log_error(ValueError("Missing required data: original_alert_details or processed_pinnacle_data is None"), "process_alert_and_scrape_betbck")
            return {"status": "error", "message": "Missing required data"}

        pod_home_team_raw = original_alert_details.get("homeTeam", "")
        pod_away_team_raw = original_alert_details.get("awayTeam", "")
        league = original_alert_details.get("leagueName", "?")

        prop_keywords = ['(Corners)', '(Bookings)', '(Hits+Runs+Errors)']
        if any(keyword.lower() in pod_home_team_raw.lower() for keyword in prop_keywords) or \
           any(keyword.lower() in pod_away_team_raw.lower() for keyword in prop_keywords):
            reason = next((kw for kw in prop_keywords if kw.lower() in pod_home_team_raw.lower() or kw.lower() in pod_away_team_raw.lower()), "prop keyword")
            print(f"[MainLogic] Alert is for a prop bet. Skipping event {event_id}.")
            if alog:
                alog.log_prop_skip(pod_home_team_raw, pod_away_team_raw, reason)
            return {"status": "error_prop_bet", "message": "Alert was for a prop bet, which is not supported."}

        pod_home_clean = clean_pod_team_name_for_search(pod_home_team_raw)
        pod_away_clean = clean_pod_team_name_for_search(pod_away_team_raw)

        if not pod_home_clean or not pod_away_clean:
            return {"status": "error", "message": "Failed to clean team names"}

        search_result = determine_betbck_search_term(pod_home_team_raw, pod_away_team_raw)
        if isinstance(search_result, tuple):
            search_term, search_reason = search_result
        else:
            search_term, search_reason = search_result, "legacy"

        if not search_term:
            return {"status": "error", "message": "Failed to determine search term"}

        if alog:
            alog.log_search_term(search_term, pod_home_team_raw, pod_away_team_raw, search_reason)

        if not scrape_betbck:
            return {"status": "success", "data": {}}

        # Parse the Pinnacle event start time so betbck_scraper can do date-aware matching
        event_date = None
        _start_raw = original_alert_details.get("startTime") or original_alert_details.get("start_time")
        if _start_raw:
            try:
                if isinstance(_start_raw, (int, float)):
                    _ts = _start_raw / 1000 if _start_raw > 1e10 else _start_raw
                    event_date = _dt.datetime.utcfromtimestamp(_ts)
                elif isinstance(_start_raw, str):
                    event_date = _dt.datetime.fromisoformat(_start_raw.replace("Z", ""))
            except Exception:
                pass

        betbck_result = scrape_betbck_for_game_queued(pod_home_team_raw, pod_away_team_raw, search_term, event_id, event_date=event_date)

        # If home-team search failed, retry with away team's significant word
        _first_failed = (
            not betbck_result or
            (isinstance(betbck_result, dict) and betbck_result.get("status") == "error")
        )
        if _first_failed:
            away_parts = pod_away_clean.split()
            if away_parts:
                skip_words = {'fc', 'sc', 'united', 'city', 'club', 'de', 'do', 'ac', 'if', 'bk', 'aif', 'kc', 'sr', 'mg', 'us', 'br'}
                away_search = None
                if len(away_parts) > 1 and len(away_parts[-1]) > 3 and away_parts[-1].lower() not in skip_words:
                    away_search = away_parts[-1]
                elif len(away_parts[0]) > 2 and away_parts[0].lower() not in skip_words:
                    away_search = away_parts[0]
                else:
                    away_search = pod_away_clean
                if away_search and away_search.lower() != search_term.lower():
                    print(f"[MainLogic] Home-team search '{search_term}' failed — retrying with away-team term '{away_search}'")
                    if alog:
                        alog.log_info(f"Retrying with away-team search term: '{away_search}'")
                    betbck_result = scrape_betbck_for_game_queued(pod_home_team_raw, pod_away_team_raw, away_search, event_id, event_date=event_date)

        if not betbck_result:
            if alog:
                alog.log_not_found(pod_home_clean, pod_away_clean, league)
            return {"status": "error", "message": "Failed to scrape BetBCK"}

        if isinstance(betbck_result, dict) and betbck_result.get("status") == "error":
            if alog:
                alog.log_not_found(pod_home_clean, pod_away_clean, league)
            return {"status": "error", "message": betbck_result.get("message", "Failed to scrape BetBCK")}

        betbck_data = betbck_result if isinstance(betbck_result, dict) else {}
        if not betbck_data:
            if alog:
                alog.log_not_found(pod_home_clean, pod_away_clean, league)
            return {"status": "error", "message": "No BetBCK data found"}

        if alog:
            odds_summary = {
                "home_moneyline": betbck_data.get("home_moneyline_american"),
                "away_moneyline": betbck_data.get("away_moneyline_american"),
                "home_spreads": betbck_data.get("home_spreads", []),
                "away_spreads": betbck_data.get("away_spreads", []),
                "home_totals": betbck_data.get("home_totals", []),
                "away_totals": betbck_data.get("away_totals", []),
            }
            alog.log_odds(odds_summary)

        potential_bets = analyze_markets_multi_row(betbck_data, processed_pinnacle_data)
        betbck_data["potential_bets_analyzed"] = potential_bets

        if alog:
            for bet in potential_bets:
                try:
                    from utils.pod_utils import american_to_decimal as a2d
                    bck_dec = a2d(bet.get("betbck_odds"))
                    pin_nvp_str = bet.get("pinnacle_nvp", "")
                    pin_nvp_dec = a2d(pin_nvp_str) if pin_nvp_str and pin_nvp_str != "N/A" else None
                    ev_str = bet.get("ev", "0%").replace("%", "")
                    ev_pct = float(ev_str) / 100.0
                    if bck_dec and pin_nvp_dec:
                        alog.log_ev(
                            bet.get("market", "?"),
                            bet.get("selection", "?"),
                            bck_dec, pin_nvp_dec, ev_pct,
                            line=str(bet.get("line", "") or ""),
                            betbck_american=str(bet.get("betbck_odds", "") or ""),
                            pin_nvp_american=str(bet.get("pinnacle_nvp", "") or ""),
                        )
                except Exception as _ev_log_exc:
                    if alog:
                        alog.log_error(_ev_log_exc, f"EV log for market {bet.get('market', '?')}")

        if alog:
            alog.set_result("ev_found" if any(
                float(b.get("ev", "0%").replace("%", "")) > 0 for b in potential_bets
            ) else "found_no_ev")

        return {"status": "success", "data": betbck_data}

    except Exception as e:
        print(f"[ProcessAlert] Error: {e}")
        traceback.print_exc()
        if alog:
            alog.log_error(e, "process_alert_and_scrape_betbck")
        return {"status": "error", "message": str(e)}

def process_pod_alert(alert_data):
    try:
        event_id = alert_data.get("eventId")
        if not event_id:
            return {"status": "error", "message": "Missing eventId"}

        pinnacle_api_result = fetch_live_pinnacle_event_odds(event_id)
        live_pinnacle_odds_processed = process_event_odds_for_display(pinnacle_api_result.get("data"))

        result = process_alert_and_scrape_betbck(event_id, alert_data, live_pinnacle_odds_processed)
        return result

    except Exception as e:
        print(f"[ProcessPodAlert] Error: {e}")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
