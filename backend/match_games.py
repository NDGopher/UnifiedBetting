import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from utils.pod_utils import normalize_team_name_for_matching

# Use the specialized matching logger
logger = logging.getLogger("matching")

try:
    from rapidfuzz.fuzz import token_sort_ratio, token_set_ratio
except ImportError:
    token_sort_ratio = None
    token_set_ratio = None
    logger.warning("rapidfuzz not installed, falling back to basic similarity.")

# Manual event overrides for known edge cases (event_id: betbck_game_id)
MANUAL_EVENT_OVERRIDES = {
    # Example: '1611309203': '65c7d0e1',
    # Add more as needed
}

# Expanded team name mapping for known quirks/aliases
TEAM_NAME_MAP = {
    "internazionale": "inter milan",
    "manchester united": "man united",
    "manchester city": "man city",
    "bayern munich": "bayern",
    "psg": "paris saint germain",
    "athletic bilbao": "athletic club",
    "real sociedad": "sociedad",
    "juventus": "juve",
    "roma": "as roma",
    "napoli": "ssc napoli",
    "sporting": "sporting cp",
    "porto": "fc porto",
    "benfica": "sl benfica",
    "sevilla": "fc sevilla",
    "betis": "real betis",
    # Add more as needed
}

# --- Aggressive normalization and prop filtering ---
PROP_INDICATORS = [
    "to lift the trophy", "lift the trophy", "mvp", "futures", "outright",
    "coach of the year", "player of the year", "series correct score",
    "when will series finish", "most points in series", "most assists in series",
    "most rebounds in series", "most threes made in series", "margin of victory",
    "exact outcome", "winner", "to win the tournament", "to win group", "series price",
    "(corners)", "bookings", "cards", "fouls", "hits+runs+errors", "corners", "bookings", "games", "sets",
    "1st half", "2nd half", "1st quarter", "2nd quarter", "3rd quarter", "4th quarter",
    "overtime", "extra time", "penalties", "total", "over", "under", "spread", "ml", "pk", "draw",
    "to win", "to advance", "handicap", "double chance", "clean sheet", "both teams to score",
    "anytime scorer", "first scorer", "last scorer", "win either half", "win both halves",
    "scorecast", "assist", "shots on target", "saves", "goalscorer", "player props", "team props", "props"
]

FUZZY_MATCH_THRESHOLD = 65  # Lowered from 82 to catch more matches
MIN_COMPONENT_MATCH_SCORE = 60  # Lowered from 78
ORIENTATION_CONFIDENCE_MARGIN = 10  # Lowered from 15

# --- Normalization ---
def is_prop_market_by_name(home_team_name, away_team_name):
    if not home_team_name or not away_team_name: return False
    for name in [home_team_name, away_team_name]:
        name_lower = name.lower()
        for indicator in PROP_INDICATORS:
            if indicator in name_lower: return True
    if "field" in away_team_name.lower() and "the" in away_team_name.lower(): return True
    if home_team_name.lower() == "yes" and away_team_name.lower() == "no": return True
    return False

# Helper to strip all prop/market info, pitcher names, and extra text from team names
def strip_extra_info(name: str) -> str:
    # Remove pitcher info (e.g., 'M Fried - L', 'must start')
    name = re.sub(r' [A-Z][a-z]+ [A-Z] - [LR]( must start)?', '', name)
    # Remove market types and prop-type bets
    prop_patterns = [
        r'\([^)]*\)',  # Anything in parentheses
        r'hits\+runs\+errors', r'corners', r'bookings', r'games', r'sets', r'cards',
        r'1st half', r'2nd half', r'1st quarter', r'2nd quarter', r'3rd quarter', r'4th quarter',
        r'overtime', r'extra time', r'penalties', r'\btotal\b', r'\bover\b', r'\bunder\b',
        r'\bspread\b', r'\bml\b', r'\bpk\b', r'\bdraw\b', r'\bto win\b', r'\bto advance\b',
        r'\bhandicap\b', r'\bdouble chance\b', r'\bclean sheet\b', r'\bboth teams to score\b',
        r'\banytime scorer\b', r'\bfirst scorer\b', r'\blast scorer\b', r'\bwin either half\b',
        r'\bwin both halves\b', r'\bscorecast\b', r'\bassist\b', r'\bshots on target\b',
        r'\bsaves\b', r'\bgoalscorer\b', r'\bplayer props?\b', r'\bteam props?\b', r'\bprops?\b',
    ]
    for pat in prop_patterns:
        name = re.sub(pat, '', name, flags=re.IGNORECASE)
    # Remove extra spaces
    return name.strip()

def normalize_team_name(name: str) -> str:
    if not name:
        return ""
    name = name.lower()
    name = strip_extra_info(name)
    # Map known team name differences
    name = TEAM_NAME_MAP.get(name, name)
    name = re.sub(r'[^a-z ]+', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()

def fuzzy_similarity(name1: str, name2: str) -> float:
    n1 = normalize_team_name(name1)
    n2 = normalize_team_name(name2)
    if not n1 or not n2:
        return 0.0
    if token_sort_ratio:
        return token_sort_ratio(n1, n2) / 100.0
    # fallback: basic set similarity
    if n1 == n2:
        return 1.0
    words1 = set(n1.split())
    words2 = set(n2.split())
    if not words1 or not words2:
        return 0.0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)

def find_best_match(pinnacle_team: str, betbck_games: List[Dict[str, Any]], threshold: float = 0.8) -> Optional[Dict[str, Any]]:
    best_match = None
    best_similarity = 0.0
    for game in betbck_games:
        home_team = normalize_team_name(game.get("betbck_site_home_team", ""))
        away_team = normalize_team_name(game.get("betbck_site_away_team", ""))
        # Log attempted match
        logger.info(f"[MATCH-DEBUG] Pinnacle: '{pinnacle_team}' vs BetBCK Home: '{home_team}' | Away: '{away_team}'")
        # Fuzzy similarity with both home and away teams
        home_similarity = fuzzy_similarity(pinnacle_team, home_team)
        away_similarity = fuzzy_similarity(pinnacle_team, away_team)
        logger.info(f"[MATCH-DEBUG] Normalized: '{normalize_team_name(pinnacle_team)}' vs '{normalize_team_name(home_team)}' (home sim: {home_similarity:.2f}) | vs '{normalize_team_name(away_team)}' (away sim: {away_similarity:.2f})")
        max_similarity = max(home_similarity, away_similarity)
        logger.info(f"[MATCH-DEBUG] Similarity score: {max_similarity:.2f}")
        if max_similarity > best_similarity and max_similarity >= threshold:
            best_similarity = max_similarity
            best_match = {
                **game,
                "similarity": max_similarity,
                "matched_team": pinnacle_team,
                "betbck_home": home_team,
                "betbck_away": away_team
            }
    return best_match

def is_league_compatible(betbck_game: Dict[str, Any], pinnacle_event: Dict[str, Any]) -> bool:
    """
    Check if two games are likely from the same league/competition based on team names and context.
    This helps prevent mismatches like Wigan Athletic vs Wycombe Wanderers when they're in different competitions.
    """
    betbck_home = betbck_game.get("betbck_site_home_team", "").lower()
    betbck_away = betbck_game.get("betbck_site_away_team", "").lower()
    pin_home = pinnacle_event.get("home_team", "").lower()
    pin_away = pinnacle_event.get("away_team", "").lower()
    
    # Check for obvious mismatches based on team name patterns
    # English football leagues
    english_premier_teams = ["manchester united", "manchester city", "arsenal", "chelsea", "liverpool", "tottenham", "newcastle", "brighton", "west ham", "crystal palace", "fulham", "brentford", "everton", "nottingham forest", "sheffield united", "burnley", "luton town", "bournemouth", "wolves", "wolverhampton"]
    english_championship_teams = ["leeds united", "leicester city", "southampton", "norwich city", "west brom", "hull city", "middlesbrough", "coventry city", "sunderland", "birmingham city", "blackburn rovers", "bristol city", "cardiff city", "huddersfield town", "ipswich town", "millwall", "plymouth argyle", "preston north end", "queens park rangers", "rotherham united", "sheffield wednesday", "stoke city", "swansea city", "watford"]
    english_league1_teams = ["barnsley", "blackpool", "bolton wanderers", "bristol rovers", "burton albion", "cambridge united", "carlisle united", "charlton athletic", "cheltenham town", "derby county", "exeter city", "fleetwood town", "grimsby town", "leyton orient", "lincoln city", "northampton town", "oxford united", "peterborough united", "port vale", "reading", "shrewsbury town", "stevenage", "wigan athletic", "wycombe wanderers"]
    english_league2_teams = ["accrington stanley", "afc wimbledon", "barrow", "bradford city", "colchester united", "crewe alexandra", "crawley town", "doncaster rovers", "forest green rovers", "gillingham", "harrogate town", "mansfield town", "mk dons", "morecambe", "newport county", "notts county", "salford city", "stockport county", "sutton united", "swindon town", "tranmere rovers", "walsall"]
    
    # Check if teams are from different English football divisions
    betbck_english_teams = []
    pin_english_teams = []
    
    for team_list, division in [(english_premier_teams, "Premier"), (english_championship_teams, "Championship"), (english_league1_teams, "League1"), (english_league2_teams, "League2")]:
        if any(team in betbck_home or team in betbck_away for team in team_list):
            betbck_english_teams.append(division)
        if any(team in pin_home or team in pin_away for team in team_list):
            pin_english_teams.append(division)
    
    # If both have English teams but from different divisions, likely incompatible
    if betbck_english_teams and pin_english_teams:
        if not any(div in betbck_english_teams for div in pin_english_teams):
            logger.debug(f"[LEAGUE-MISMATCH] English divisions don't match: BetBCK={betbck_english_teams} vs Pinnacle={pin_english_teams}")
            return False
    
    # Check for cup competitions vs league games
    cup_indicators = ["cup", "trophy", "champions league", "europa league", "conference league", "fa cup", "carabao cup", "efl cup"]
    betbck_cup = any(indicator in betbck_home or indicator in betbck_away for indicator in cup_indicators)
    pin_cup = any(indicator in pin_home or indicator in pin_away for indicator in cup_indicators)
    
    # If one is clearly a cup game and the other isn't, be more cautious
    if betbck_cup != pin_cup:
        logger.debug(f"[CUP-MISMATCH] Cup vs league mismatch: BetBCK_cup={betbck_cup} vs Pinnacle_cup={pin_cup}")
        # Don't completely reject, but log for awareness
    
    # Check for international vs club competitions
    international_indicators = ["national team", "country", "international", "fifa", "uefa nations"]
    betbck_international = any(indicator in betbck_home or indicator in betbck_away for indicator in international_indicators)
    pin_international = any(indicator in pin_home or indicator in pin_away for indicator in international_indicators)
    
    if betbck_international != pin_international:
        logger.debug(f"[INTL-MISMATCH] International vs club mismatch: BetBCK_intl={betbck_international} vs Pinnacle_intl={pin_international}")
        return False
    
    # If we get here, the games seem compatible
    return True

def determine_sport_from_teams(home_team: str, away_team: str) -> str:
    """Determine sport based on team names"""
    teams_combined = f"{home_team} {away_team}".lower()
    
    # MLB teams - use partial matching for BetBCK format
    mlb_teams = ['blue jays', 'dodgers', 'mariners', 'braves', 'cubs', 'angels', 'padres', 
                 'rangers', 'phillies', 'yankees', 'white sox', 'giants', 'marlins', 
                 'athletics', 'guardians', 'orioles', 'red sox', 'astros', 'rockies', 
                 'cardinals', 'twins', 'brewers', 'tigers', 'royals', 'rays', 'nationals',
                 'mets', 'pirates', 'diamondbacks', 'twins', 'royals', 'tigers', 'astros']
    
    # Soccer teams (expanded)
    soccer_teams = ['united', 'city', 'arsenal', 'chelsea', 'liverpool', 'tottenham', 'brighton', 
                   'wolves', 'wanderers', 'forest', 'leeds', 'villa', 'palace', 'fulham', 'bournemouth',
                   'lyon', 'rennais', 'laval', 'boulogne', 'galaxy', 'sounders', 'real', 'barcelona',
                   'madrid', 'atletico', 'sevilla', 'valencia', 'betis', 'sociedad', 'athletic',
                   'bayern', 'dortmund', 'leipzig', 'leverkusen', 'frankfurt', 'stuttgart',
                   'juventus', 'milan', 'inter', 'napoli', 'roma', 'lazio', 'fiorentina',
                   'psg', 'monaco', 'lyon', 'marseille', 'lille', 'rennes', 'nice']
    
    # Basketball teams (expanded)
    basketball_teams = ['lakers', 'warriors', 'celtics', 'heat', 'bulls', 'knicks', 'nets', 'suns', 'mavs',
                       'bucks', 'sixers', 'raptors', 'pistons', 'pacers', 'cavaliers', 'magic', 'hawks',
                       'hornets', 'wizards', 'nuggets', 'trail blazers', 'jazz', 'thunder', 'spurs',
                       'rockets', 'pelicans', 'grizzlies', 'timberwolves', 'kings', 'clippers']
    
    # Football teams (expanded)
    football_teams = ['patriots', 'bills', 'dolphins', 'jets', 'ravens', 'bengals', 'browns', 'steelers',
                     'texans', 'colts', 'jaguars', 'titans', 'broncos', 'chiefs', 'raiders', 'chargers',
                     'cowboys', 'giants', 'eagles', 'commanders', 'bears', 'lions', 'packers', 'vikings',
                     'falcons', 'panthers', 'saints', 'buccaneers', 'cardinals', 'rams', 'seahawks', '49ers']
    
    # UFC/Boxing fighters (individual names)
    if any(word in teams_combined for word in ['amanda', 'tatiana', 'keith', 'devin', 'fernando', 'anthony', 'stephen']):
        return 'ufc_boxing'
    
    # Check for partial matches (BetBCK format includes pitcher names)
    if any(team in teams_combined for team in mlb_teams):
        return 'mlb'
    elif any(team in teams_combined for team in soccer_teams):
        return 'soccer'
    elif any(team in teams_combined for team in basketball_teams):
        return 'basketball'
    elif any(team in teams_combined for team in football_teams):
        return 'football'
    else:
        return 'other'

def match_pinnacle_to_betbck(pinnacle_events: List[Dict[str, Any]], betbck_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    betbck_games = betbck_data.get("games", [])
    matched_events = []
    processed_pinnacle_event_ids = set()
    unmatched_betbck = []
    unmatched_pinnacle = []
    
    logger.info(f"[MATCH] Starting matching: {len(betbck_games)} BetBCK games, {len(pinnacle_events)} Pinnacle events.")
    
    # Group Pinnacle events by sport for efficient matching
    events_by_sport = {}
    minor_events = []
    
    for event in pinnacle_events:
        home_team = event.get('home_team', '').lower()
        away_team = event.get('away_team', '').lower()
        
        # Define minor league indicators to filter out
        minor_indicators = [
            'durham bulls', 'salt lake bees', 'st. paul saints', 'columbus clippers',
            'tacoma rainiers', 'norfolk tides', 'jumbo shrimp', 'mud hens', 'reno aces',
            'oklahoma city comets', 'red wings', 'syracuse mets', 'indianapolis indians',
            'storm chasers', 'railriders', 'bees', 'clippers', 'mud hens', 'aces',
            'comets', 'wings', 'mets', 'indians', 'storm chasers', 'railriders'
        ]
        
        # Check if this is a minor league event
        is_minor = any(indicator in home_team or indicator in away_team for indicator in minor_indicators)
        
        if is_minor:
            minor_events.append(event)
            continue
            
        # Determine sport based on team names
        sport = determine_sport_from_teams(home_team, away_team)
        if sport not in events_by_sport:
            events_by_sport[sport] = []
        events_by_sport[sport].append(event)
    
    logger.info(f"[MATCH] Grouped events by sport: {dict((k, len(v)) for k, v in events_by_sport.items())}")
    logger.info(f"[MATCH] Minor league events filtered out: {len(minor_events)}")
    
    # Use all major sports events for matching (will be filtered by sport during matching)
    pinnacle_events = [event for events in events_by_sport.values() for event in events]
    
    # Log all Pinnacle events for debugging (limited)
    logger.info(f"[MATCH] Pinnacle events to match:")
    for i, event in enumerate(pinnacle_events):
        logger.info(f"[MATCH]   {i+1}. {event.get('home_team', '?')} vs {event.get('away_team', '?')} (ID: {event.get('event_id', '?')})")
    
    for game_idx, betbck_game in enumerate(betbck_games):
        # Progress logging every 10 games
        if game_idx % 10 == 0:
            logger.info(f"[MATCH] Progress: {game_idx}/{len(betbck_games)} games processed")
        
        # Skip if this BetBCK game was already matched
        matched_betbck_ids = getattr(match_pinnacle_to_betbck, 'matched_betbck_ids', set())
        betbck_game_id = betbck_game.get('betbck_game_id', f"{betbck_game.get('betbck_site_home_team', '')}_{betbck_game.get('betbck_site_away_team', '')}")
        if betbck_game_id in matched_betbck_ids:
            logger.debug(f"[SKIP] BetBCK game already matched: {betbck_game_id}")
            continue
            
        betbck_home_raw = betbck_game.get("betbck_site_home_team", "")
        betbck_away_raw = betbck_game.get("betbck_site_away_team", "")
        logger.info(f"[BETBCK] Raw teams: home='{betbck_home_raw}', away='{betbck_away_raw}'")
        logger.info(f"[BETBCK] Raw odds: {betbck_game.get('betbck_site_odds', {})}")
        norm_bck_home = normalize_team_name_for_matching(betbck_home_raw)
        norm_bck_away = normalize_team_name_for_matching(betbck_away_raw)
        logger.info(f"[NORM] BetBCK normalized: '{betbck_home_raw}' -> '{norm_bck_home}', '{betbck_away_raw}' -> '{norm_bck_away}'")
        
        if not norm_bck_home or not norm_bck_away:
            logger.warning(f"[SKIP] Could not normalize: '{betbck_home_raw}' vs '{betbck_away_raw}' -> '{norm_bck_home}' vs '{norm_bck_away}'")
            unmatched_betbck.append({
                "betbck_home": betbck_home_raw,
                "betbck_away": betbck_away_raw,
                "norm_home": norm_bck_home,
                "norm_away": norm_bck_away,
                "reason": "normalization_failed"
            })
            continue
            
        logger.info(f"[MATCH] Normalized BetBCK: '{norm_bck_home}' vs '{norm_bck_away}'")
        
        # Determine sport of this BetBCK game
        betbck_sport = determine_sport_from_teams(norm_bck_home, norm_bck_away)
        logger.info(f"[MATCH] BetBCK game sport: {betbck_sport}")
        
        # Only match against events from the same sport
        relevant_events = events_by_sport.get(betbck_sport, [])
        logger.info(f"[MATCH] Found {len(relevant_events)} {betbck_sport} events to match against")
        
        best_match = None
        best_score = 0
        best_orientation = None
        best_pinnacle_event = None
        
        for pinnacle_event in relevant_events:
            if pinnacle_event.get("event_id") in processed_pinnacle_event_ids:
                continue
                
            pin_home_raw = pinnacle_event.get("home_team", "")
            pin_away_raw = pinnacle_event.get("away_team", "")
            
            if is_prop_market_by_name(pin_home_raw, pin_away_raw):
                continue
                
            # --- ENHANCED LEAGUE & TIME CONTEXT CHECK ---
            # Check if games are from the same day (within 24 hours)
            betbck_time = betbck_game.get("event_datetime", "")
            pinnacle_time = pinnacle_event.get("event_datetime", "")
            
            if betbck_time and pinnacle_time:
                try:
                    from datetime import datetime
                    betbck_dt = datetime.fromisoformat(betbck_time.replace('Z', '+00:00'))
                    pinnacle_dt = datetime.fromisoformat(pinnacle_time.replace('Z', '+00:00'))
                    time_diff = abs((betbck_dt - pinnacle_dt).total_seconds())
                    
                    # Only match games within 24 hours of each other
                    if time_diff > 86400:  # 24 hours in seconds
                        logger.debug(f"[TIME-SKIP] Time difference too large: {time_diff/3600:.1f} hours between {betbck_time} and {pinnacle_time}")
                        continue
                except Exception as e:
                    logger.warning(f"[TIME-CHECK] Error parsing times: {e}")
                    # Continue if we can't parse times, but log the issue
                    pass
            
            # Check for league/competition context compatibility
            if not is_league_compatible(betbck_game, pinnacle_event):
                logger.debug(f"[LEAGUE-SKIP] Incompatible leagues: BetBCK={betbck_game.get('league', 'Unknown')} vs Pinnacle={pinnacle_event.get('league', 'Unknown')}")
                continue
            
            # Define sport categories for loose matching
            basketball_sports = ["basketball", "nba", "wnba", "ncaab", "ncaa basketball", "euroleague", "fib", "basketball"]
            football_sports = ["football", "nfl", "ncaaf", "ncaa football", "college football", "american football"]
            baseball_sports = ["baseball", "mlb", "minor league", "college baseball", "ncaa baseball"]
            soccer_sports = ["soccer", "football", "mls", "premier league", "la liga", "bundesliga", "serie a", "ligue 1", "champions league", "europa league"]
            hockey_sports = ["hockey", "nhl", "ncaa hockey", "college hockey"]
            
            # Check if sports are compatible (loose matching)
            betbck_sport_category = None
            pinnacle_sport_category = None
            
            # Get league/sport info from the games
            betbck_league = betbck_game.get('league', '').lower()
            pinnacle_league = pinnacle_event.get('league', '').lower()
            betbck_sport = betbck_game.get('sport', '').lower()
            pinnacle_sport = pinnacle_event.get('sport', '').lower()
            
            if any(sport in betbck_league or sport in betbck_sport for sport in basketball_sports):
                betbck_sport_category = "basketball"
            elif any(sport in betbck_league or sport in betbck_sport for sport in football_sports):
                betbck_sport_category = "football"
            elif any(sport in betbck_league or sport in betbck_sport for sport in baseball_sports):
                betbck_sport_category = "baseball"
            elif any(sport in betbck_league or sport in betbck_sport for sport in soccer_sports):
                betbck_sport_category = "soccer"
            elif any(sport in betbck_league or sport in betbck_sport for sport in hockey_sports):
                betbck_sport_category = "hockey"
                
            if any(sport in pinnacle_league or sport in pinnacle_sport for sport in basketball_sports):
                pinnacle_sport_category = "basketball"
            elif any(sport in pinnacle_league or sport in pinnacle_sport for sport in football_sports):
                pinnacle_sport_category = "football"
            elif any(sport in pinnacle_league or sport in pinnacle_sport for sport in baseball_sports):
                pinnacle_sport_category = "baseball"
            elif any(sport in pinnacle_league or sport in pinnacle_sport for sport in soccer_sports):
                pinnacle_sport_category = "soccer"
            elif any(sport in pinnacle_league or sport in pinnacle_sport for sport in hockey_sports):
                pinnacle_sport_category = "hockey"
            
            # Skip if sports don't match (but allow if we can't determine sport for either)
            if betbck_sport_category and pinnacle_sport_category and betbck_sport_category != pinnacle_sport_category:
                logger.debug(f"[LEAGUE-CHECK] Skipping - BetBCK: {betbck_sport_category} vs Pinnacle: {pinnacle_sport_category}")
                continue
            # --- END LEAGUE CHECK ---
                
            norm_pin_home = normalize_team_name_for_matching(pin_home_raw)
            norm_pin_away = normalize_team_name_for_matching(pin_away_raw)
            logger.info(f"[NORM] Pinnacle normalized: '{pin_home_raw}' -> '{norm_pin_home}', '{pin_away_raw}' -> '{norm_pin_away}'")
            
            if not norm_pin_home or not norm_pin_away:
                continue
                
            # Try both orientations
            score_direct = token_set_ratio(f"{norm_bck_home} {norm_bck_away}", f"{norm_pin_home} {norm_pin_away}")
            score_flipped = token_set_ratio(f"{norm_bck_home} {norm_bck_away}", f"{norm_pin_away} {norm_pin_home}")
            
            logger.debug(f"[MATCH] Comparing: '{norm_bck_home} {norm_bck_away}' vs '{norm_pin_home} {norm_pin_away}' (direct: {score_direct}, flipped: {score_flipped})")
            
            if score_direct > best_score:
                best_score = score_direct
                best_match = pinnacle_event
                best_orientation = True
                # Early termination: if we have a very high score, stop searching
                if score_direct >= 95:  # Very high confidence match
                    logger.info(f"[MATCH] Early termination: High confidence match found (score: {score_direct})")
                    break
            if score_flipped > best_score:
                best_score = score_flipped
                best_match = pinnacle_event
                best_orientation = False
                # Early termination: if we have a very high score, stop searching
                if score_flipped >= 95:  # Very high confidence match
                    logger.info(f"[MATCH] Early termination: High confidence match found (score: {score_flipped})")
                    break
                
        if best_match and best_score >= FUZZY_MATCH_THRESHOLD:
            processed_pinnacle_event_ids.add(best_match["event_id"])
            logger.info(f"[MATCHED] SUCCESS: '{betbck_home_raw}' vs '{betbck_away_raw}' <-> '{best_match['home_team']}' vs '{best_match['away_team']}' | Score: {best_score} | Orientation: {'direct' if best_orientation else 'flipped'}")
            
            # Add this BetBCK game to a "matched" set to avoid reprocessing
            matched_betbck_ids = getattr(match_pinnacle_to_betbck, 'matched_betbck_ids', set())
            matched_betbck_ids.add(betbck_game.get('betbck_game_id', f"{betbck_home_raw}_{betbck_away_raw}"))
            match_pinnacle_to_betbck.matched_betbck_ids = matched_betbck_ids

            # --- Explicitly map BetBCK odds to event ID home/away ---
            # Get normalized names
            norm_event_home = normalize_team_name_for_matching(best_match["home_team"])
            norm_event_away = normalize_team_name_for_matching(best_match["away_team"])
            # Map BetBCK normalized names to event ID home/away
            betbck_odds = betbck_game.get("betbck_site_odds", {})
            # BetBCK top/bottom teams (as shown in UI)
            betbck_top_team = norm_bck_home
            betbck_bottom_team = norm_bck_away
            top_ml = betbck_odds.get("site_top_team_moneyline_american")
            bottom_ml = betbck_odds.get("site_bottom_team_moneyline_american")
            # Map odds to event home/away
            if betbck_top_team == norm_event_home and betbck_bottom_team == norm_event_away:
                betbck_home_odds = top_ml
                betbck_away_odds = bottom_ml
            elif betbck_top_team == norm_event_away and betbck_bottom_team == norm_event_home:
                betbck_home_odds = bottom_ml
                betbck_away_odds = top_ml
            else:
                # Fallback: log and assign None
                logger.warning(f"[MAPPING] Could not confidently map BetBCK teams to event ID home/away: top='{betbck_top_team}', bottom='{betbck_bottom_team}', event_home='{norm_event_home}', event_away='{norm_event_away}'")
                betbck_home_odds = None
                betbck_away_odds = None
            logger.info(f"[MAPPING] Event: {best_match['home_team']} vs {best_match['away_team']} | BetBCK home odds: {betbck_home_odds}, away odds: {betbck_away_odds}")
            # Determine sport for this match
            sport = determine_sport_from_teams(norm_bck_home, norm_bck_away)
            
            matched_events.append({
                "pinnacle_event_id": best_match["event_id"],
                "pinnacle_home_team": best_match["home_team"],
                "pinnacle_away_team": best_match["away_team"],
                "betbck_game": betbck_game,
                "match_confidence": best_score / 100.0,
                "betbck_home_team": betbck_home_raw,
                "betbck_away_team": betbck_away_raw,
                "normalized_betbck_home": norm_bck_home,
                "normalized_betbck_away": norm_bck_away,
                "normalized_pinnacle_home": norm_event_home,
                "normalized_pinnacle_away": norm_event_away,
                "match_score": best_score,
                "orientation": "direct" if best_orientation else "flipped",
                "betbck_home_odds": betbck_home_odds,
                "betbck_away_odds": betbck_away_odds,
                "sport": sport
            })
        else:
            best_score_str = f" (best score: {best_score})" if best_match else " (no candidates)"
            logger.warning(f"[NO MATCH] FAILED: '{betbck_home_raw}' vs '{betbck_away_raw}' (normalized: '{norm_bck_home}' vs '{norm_bck_away}'){best_score_str}")
            
            unmatched_betbck.append({
                "betbck_home": betbck_home_raw,
                "betbck_away": betbck_away_raw,
                "norm_home": norm_bck_home,
                "norm_away": norm_bck_away,
                "best_score": best_score if best_match else 0,
                "best_pinnacle": f"{best_match['home_team']} vs {best_match['away_team']}" if best_match else None,
                "reason": "below_threshold" if best_match else "no_candidates"
            })
    
    # Log unmatched Pinnacle events
    for pinnacle_event in pinnacle_events:
        if pinnacle_event.get("event_id") not in processed_pinnacle_event_ids:
            unmatched_pinnacle.append({
                "pinnacle_home": pinnacle_event.get("home_team", ""),
                "pinnacle_away": pinnacle_event.get("away_team", ""),
                "event_id": pinnacle_event.get("event_id", ""),
                "norm_home": normalize_team_name_for_matching(pinnacle_event.get("home_team", "")),
                "norm_away": normalize_team_name_for_matching(pinnacle_event.get("away_team", ""))
            })
    
    # Summary logging
    logger.info(f"[MATCH] SUMMARY:")
    logger.info(f"[MATCH]   [MATCHED] Matched: {len(matched_events)} games")
    logger.info(f"[MATCH]   [UNMATCHED] Unmatched BetBCK: {len(unmatched_betbck)} games")
    logger.info(f"[MATCH]   [UNMATCHED] Unmatched Pinnacle: {len(unmatched_pinnacle)} events")
    logger.info(f"[MATCH]   [STATS] Match rate: {len(matched_events)}/{len(betbck_games)} = {len(matched_events)/len(betbck_games)*100:.1f}%")
    
    # Log unmatched details for debugging
    if unmatched_betbck:
        logger.info(f"[MATCH] UNMATCHED BETBCK GAMES:")
        for i, unmatched in enumerate(unmatched_betbck[:10]):  # Limit to first 10
            logger.info(f"[MATCH]   {i+1}. '{unmatched['betbck_home']}' vs '{unmatched['betbck_away']}' (norm: '{unmatched['norm_home']}' vs '{unmatched['norm_away']}') - {unmatched['reason']}")
        if len(unmatched_betbck) > 10:
            logger.info(f"[MATCH]   ... and {len(unmatched_betbck) - 10} more unmatched BetBCK games")
    
    if unmatched_pinnacle:
        logger.info(f"[MATCH] UNMATCHED PINNACLE EVENTS:")
        for i, unmatched in enumerate(unmatched_pinnacle[:10]):  # Limit to first 10
            logger.info(f"[MATCH]   {i+1}. '{unmatched['pinnacle_home']}' vs '{unmatched['pinnacle_away']}' (norm: '{unmatched['norm_home']}' vs '{unmatched['norm_away']}')")
        if len(unmatched_pinnacle) > 10:
            logger.info(f"[MATCH]   ... and {len(unmatched_pinnacle) - 10} more unmatched Pinnacle events")
    
    return matched_events

def save_matched_games(matched_games: List[Dict[str, Any]], filename: str = "data/matched_games.json") -> bool:
    try:
        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        data = {
            "matched_games": matched_games,
            "total_matches": len(matched_games),
            "timestamp": datetime.now().isoformat()
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(matched_games)} matched games to {filename}")
        return True
    except Exception as e:
        logger.error(f"Error saving matched games: {e}")
        return False

def load_matched_games(filename: str = "data/matched_games.json") -> Optional[List[Dict[str, Any]]]:
    try:
        import os
        if not os.path.exists(filename):
            logger.warning(f"Matched games file not found: {filename}")
            return None
        with open(filename, 'r') as f:
            data = json.load(f)
        matched_games = data.get("matched_games", [])
        logger.info(f"Loaded {len(matched_games)} matched games from {filename}")
        return matched_games
    except Exception as e:
        logger.error(f"Error loading matched games: {e}")
        return None

if __name__ == "__main__":
    # Test the matching logic
    pinnacle_events = [
        {"event_id": "123", "home_team": "Lakers", "away_team": "Warriors"},
        {"event_id": "456", "home_team": "Celtics", "away_team": "Heat"}
    ]
    betbck_data = {
        "games": [
            {"id": "1", "betbck_site_home_team": "Los Angeles Lakers", "betbck_site_away_team": "Golden State Warriors", "lines": []},
            {"id": "2", "betbck_site_home_team": "Boston Celtics", "betbck_site_away_team": "Miami Heat", "lines": []}
        ]
    }
    matched = match_pinnacle_to_betbck(pinnacle_events, betbck_data)
    print(f"Matched {len(matched)} games")
    print(json.dumps(matched, indent=2)) 