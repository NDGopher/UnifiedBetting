import json
import logging
import re
import unicodedata
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from utils.pod_utils import alias_normalize, normalize_team_name_for_matching
from rapidfuzz import fuzz

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
    # Italian Serie A
    "internazionale": "inter milan",
    "inter": "inter milan",
    "juventus": "juve",
    "roma": "as roma",
    "napoli": "ssc napoli",
    # Spanish La Liga
    "athletic bilbao": "athletic club",
    "real sociedad": "sociedad",
    "betis": "real betis",
    "sevilla": "fc sevilla",
    # Portuguese
    "sporting": "sporting cp",
    "porto": "fc porto",
    "benfica": "sl benfica",
    # French Ligue 1
    "psg": "paris saint germain",
    "paris sg": "paris saint germain",
    "paris saint-germain": "paris saint germain",
    "olympique lyonnais": "lyon",
    "olympique de marseille": "marseille",
    "stade rennais": "rennes",
    # German Bundesliga
    "bayern munich": "bayern",
    "fc bayern": "bayern",
    "borussia dortmund": "dortmund",
    "rb leipzig": "leipzig",
    "bayer leverkusen": "leverkusen",
    # English
    "manchester united": "man united",
    "manchester city": "man city",
    "tottenham hotspur": "tottenham",
    "spurs": "tottenham",
    "newcastle united": "newcastle",
    "west ham united": "west ham",
    "wolverhampton wanderers": "wolves",
    "nottingham forest": "forest",
    # Scottish clubs
    "heart of midlothian": "hearts",
    "heart of midlothian fc": "hearts",
    "hearts fc": "hearts",
    "hibernian": "hibs",
    "hibernian fc": "hibs",
    "glasgow rangers": "rangers",
    "rangers fc": "rangers",
    "celtic fc": "celtic",
    "dundee utd": "dundee united",
    # US Soccer / MLS
    "la galaxy": "la galaxy",
    "lafc": "los angeles fc",
    "la fc": "los angeles fc",
    "nycfc": "new york city fc",
    "nyrb": "new york red bulls",
    "new york red bull": "new york red bulls",
    # NBA common short forms
    "philadelphia 76ers": "76ers",
    "76ers": "76ers",
    "golden state warriors": "warriors",
    "golden state": "warriors",
    "los angeles lakers": "lakers",
    "los angeles clippers": "clippers",
    "los angeles rams": "rams",
    "oklahoma city thunder": "thunder",
    "new orleans pelicans": "pelicans",
    "san antonio spurs": "spurs",
    "memphis grizzlies": "grizzlies",
    "minnesota timberwolves": "timberwolves",
    "portland trail blazers": "trail blazers",
    # MLB
    "athletics": "oakland athletics",
    "a's": "oakland athletics",
    "white sox": "chicago white sox",
    "red sox": "boston red sox",
    "blue jays": "toronto blue jays",
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

# Words that appear in many unrelated club names. Used to compare the
# distinctive core ("Cardiff" vs "Cardiff City") without treating
# "Manchester United" as the same team as "Manchester City".
_GENERIC_TEAM_WORDS = frozenset({
    "city", "town", "united", "utd", "fc", "sc", "afc", "cf", "ac", "if", "bk",
    "rovers", "county", "athletic", "wanderers", "hotspur", "villa", "palace",
    "albion", "wednesday", "vale", "club", "calcio", "de", "the", "sv", "vfb",
    "vfl", "as", "ss", "us", "sk", "fk", "deportivo", "cd", "rc", "kf",
})

# Same-club suffix spellings. "united" vs "utd" is not a different club;
# "united" vs "city" is (Manchester United ≠ Manchester City).
_GENERIC_SYNONYMS = (
    frozenset({"united", "utd", "u"}),
    frozenset({"fc", "cf", "afc", "sc", "ac", "fk", "sk", "bk", "if", "sv", "kf", "cd", "rc"}),
)

# Short cores that belong to more than one real club. Subset matching
# ("Inter" ⊂ "Inter Miami") is not allowed for these.
_AMBIGUOUS_SHORT_CORES = frozenset({
    "inter", "real", "sporting", "athletic", "rangers", "dynamo", "dinamito",
    "olympique", "olympic", "racing", "sport", "union", "madrid", "milan",
})


_CHAR_FOLD = str.maketrans({
    "ø": "o", "Ø": "o",
    "æ": "ae", "Æ": "ae",
    "å": "a", "Å": "a",
    "ö": "o", "Ö": "o",
    "ä": "a", "Ä": "a",
    "ü": "u", "Ü": "u",
    "ß": "ss",
    "ł": "l", "Ł": "l",
    "đ": "d", "Đ": "d",
    "ð": "d", "Ð": "d",
    "þ": "th", "Þ": "th",
    "ñ": "n", "Ñ": "n",
    "ş": "s", "Ş": "s",
    "ç": "c", "Ç": "c",
})


def _fold_team_text(name: str) -> str:
    # ø/æ/å do not NFKD-decompose; map them first, then strip accents (é → e).
    s = (name or "").translate(_CHAR_FOLD)
    nk = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nk if not unicodedata.combining(c)).strip().lower()


def canonical_team_name(name: str) -> str:
    """Strip props/suffixes, fold accents, then collapse known club aliases."""
    n = normalize_team_name_for_matching(name)
    if not n:
        return ""
    n = _fold_team_text(n)
    n = alias_normalize(n)
    mapped = TEAM_NAME_MAP.get(n)
    if mapped:
        n = alias_normalize(_fold_team_text(mapped))
    return n


def _core_and_generic_tokens(name: str):
    toks = [t for t in (name or "").lower().split() if t]
    core = {t for t in toks if t not in _GENERIC_TEAM_WORDS and len(t) > 2}
    generic = {t for t in toks if t in _GENERIC_TEAM_WORDS or len(t) <= 2}
    return core, generic


def _generics_conflict(ga, gb) -> bool:
    """True when leftover suffixes point at different clubs (united vs city)."""
    if not ga or not gb:
        return False
    if ga & gb:
        return False
    for group in _GENERIC_SYNONYMS:
        if (ga & group) and (gb & group):
            return False
    return True


def names_are_same_team(a: str, b: str) -> bool:
    """True when two labels are the same club, allowing City/FC/Town aliases.

    Rejects Manchester United vs Manchester City (same core, conflicting generic)
    and Crawley Town vs Athlone Town (generic-only overlap).
    """
    if not a or not b:
        return False
    a = _fold_team_text(a)
    b = _fold_team_text(b)
    if a == b:
        return True
    ca, ga = _core_and_generic_tokens(a)
    cb, gb = _core_and_generic_tokens(b)
    tsr = fuzz.token_set_ratio(a, b) if fuzz else (100 if a == b else 0)
    if ca and cb:
        if ca == cb:
            return not _generics_conflict(ga, gb)
        if ca < cb or cb < ca:
            shorter, longer = (ca, cb) if ca < cb else (cb, ca)
            extra = longer - shorter
            if shorter <= _AMBIGUOUS_SHORT_CORES and extra and not extra <= _GENERIC_TEAM_WORDS:
                return False
            return True
        overlap = ca & cb
        if not overlap:
            return False
        smaller = ca if len(ca) <= len(cb) else cb
        if len(overlap) / len(smaller) >= 0.67 and tsr >= 80:
            return True
        return False
    # Generic-only labels ("United", "FC") are not an identity.
    return False


def pair_orientation_score(bck_h: str, bck_a: str, pin_h: str, pin_a: str):
    """Return (score, direct) for a two-team matchup. 0 if either side is a different club."""
    _tsr = fuzz.token_set_ratio

    def _side(a, b):
        raw = _tsr(a, b)
        if names_are_same_team(a, b) and raw >= 55:
            return raw
        return 0

    h_d, a_d = _side(bck_h, pin_h), _side(bck_a, pin_a)
    direct = (h_d + a_d) / 2 if h_d and a_d else 0
    h_f, a_f = _side(bck_h, pin_a), _side(bck_a, pin_h)
    flipped = (h_f + a_f) / 2 if h_f and a_f else 0
    if direct >= flipped:
        return direct, True
    return flipped, False


def normalize_sport_label(raw_sport: str, subtype: str = "") -> str:
    """Map BetBCK SportType / Pinnacle Arcadia sport names onto matcher buckets."""
    blob = f"{raw_sport or ''} {subtype or ''}".lower()
    if not blob.strip():
        return "other"
    if "soccer" in blob:
        return "soccer"
    if "nfl" in blob or "ncaaf" in blob or "american football" in blob or "american-football" in blob:
        return "football"
    # Arcadia uses "Football" for NFL and "Soccer" for soccer. BetBCK uses SOCCER.
    if blob.strip() in ("football",) or (blob.strip().startswith("football") and "soccer" not in blob):
        if "premier" in blob or "liga" in blob or "bundesliga" in blob or "serie" in blob:
            return "soccer"
        return "football"
    if "basketball" in blob or "nba" in blob or "ncaab" in blob or "wnba" in blob:
        return "basketball"
    if "baseball" in blob or "mlb" in blob:
        return "mlb"
    if "hockey" in blob or "nhl" in blob or "ice" in blob:
        return "hockey"
    if "ufc" in blob or "mma" in blob or "boxing" in blob or "martial" in blob:
        return "ufc_boxing"
    return "other"


def related_sport_buckets(sport: str) -> list:
    """Unknown-club games live in 'other'; still search soccer when that's the board."""
    if sport == "soccer":
        return ["soccer", "other"]
    if sport == "other":
        return ["other", "soccer"]
    return [sport]


def resolve_betbck_sport(game: Dict[str, Any], home_norm: str, away_norm: str) -> str:
    labeled = normalize_sport_label(game.get("sport") or "", "")
    if labeled == "other":
        labeled = normalize_sport_label(game.get("sport_type") or "", game.get("sport_subtype") or "")
    if labeled != "other":
        return labeled
    return determine_sport_from_teams(home_norm, away_norm)

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
        r'\b1H\b', r'\b2H\b', r'\b1Q\b', r'\b2Q\b', r'\b3Q\b', r'\b4Q\b',
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
    # (division lists used to reject FA Cup / mixed boards — that dropped real games) 
    # English division lists go stale (promotions, cups). Two team names already
    # identify the matchup; do not reject FA Cup / mixed-division games here.

    # Check for international vs club competitions 
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
                   'psg', 'monaco', 'lyon', 'marseille', 'lille', 'rennes', 'nice',
                   'huddersfield', 'bradford', 'blackpool', 'cheltenham', 'colchester', 'bolton',
                   'wycombe', 'reading', 'lincoln', 'plymouth', 'port vale', 'doncaster',
                   'stevenage', 'mansfield', 'cardiff', 'rotherham', 'wimbledon', 'notts',
                   'gillingham', 'barnet', 'crewe', 'milton', 'keynes', 'chesterfield',
                   'walsall', 'fleetwood', 'bromley', 'oldham', 'salford', 'shrewsbury',
                   'harrogate', 'swindon', 'cambridge', 'grimsby', 'newport', 'tranmere',
                   'barrow', 'bristol', 'rovers']
    
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
    
    # NHL teams — checked before "other" fallback so they get their own bucket
    hockey_teams = ['bruins', 'sabres', 'red wings', 'panthers', 'canadiens', 'senators',
                    'lightning', 'maple leafs', 'coyotes', 'blackhawks', 'avalanche', 'stars',
                    'wild', 'predators', 'blues', 'jets', 'ducks', 'flames', 'oilers', 'kings',
                    'sharks', 'golden knights', 'kraken', 'canucks', 'rangers', 'islanders',
                    'devils', 'flyers', 'penguins', 'capitals', 'hurricanes', 'blue jackets']

    # UFC/Boxing fighters (individual names) - expanded list
    ufc_names = ['amanda', 'tatiana', 'keith', 'devin', 'fernando', 'anthony', 'stephen',
                 'diego', 'david', 'rafa', 'dustin', 'santiago', 'jose', 'joaquim', 'jesus',
                 'sedriques', 'montserrat', 'alice', 'rodrigo', 'daniil', 'alden', 'alessandro']
    
    # Check if this looks like individual fighter names (not team names)
    if any(name in teams_combined for name in ufc_names):
        # Additional check: UFC events typically have individual names, not team names
        if not any(team_word in teams_combined for team_word in ['united', 'city', 'club', 'fc', 'sc', 'athletic', 'rovers', 'town']):
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
    elif any(team in teams_combined for team in hockey_teams):
        return 'hockey'
    else:
        return 'other'

def match_pinnacle_to_betbck(pinnacle_events: List[Dict[str, Any]], betbck_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    betbck_games = betbck_data.get("games", [])
    matched_events = []
    processed_pinnacle_event_ids = set()  # event_ids — used for unmatched Pinnacle logging
    processed_pinnacle_keys = set()      # (event_id, market_suffix) — allows main + 1H to both match the same Pinnacle event
    matched_betbck_ids: set = set()   # LOCAL — reset every call, never persists across runs
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
            
        # Use sport field from Arcadia if available, fall back to team-name detection
        raw_sport = event.get('sport', '').strip()
        sport = normalize_sport_label(raw_sport, event.get('league') or "")
        if sport == "other":
            sport = determine_sport_from_teams(home_team, away_team)
        if sport not in events_by_sport:
            events_by_sport[sport] = []
        events_by_sport[sport].append(event)
    
    logger.info(f"[MATCH] Grouped events by sport: {dict((k, len(v)) for k, v in events_by_sport.items())}")
    logger.info(f"[MATCH] Minor league events filtered out: {len(minor_events)}")
    
    # Use all major sports events for matching (will be filtered by sport during matching)
    pinnacle_events = [event for events in events_by_sport.values() for event in events]
    
    # Log all Pinnacle events for debugging (debug only — 1298 lines at INFO would tank performance)
    logger.debug(f"[MATCH] Pinnacle events to match:")
    for i, event in enumerate(pinnacle_events):
        logger.debug(f"[MATCH]   {i+1}. {event.get('home_team', '?')} vs {event.get('away_team', '?')} (ID: {event.get('event_id', '?')})")

    # --- PRE-NORMALIZE all Pinnacle teams once (avoids ~877K redundant normalize calls in inner loop) ---
    pin_norm_cache: dict = {}
    for event in pinnacle_events:
        eid = event.get("event_id")
        if eid is not None:
            pin_norm_cache[eid] = (
                canonical_team_name(event.get("home_team", "")),
                canonical_team_name(event.get("away_team", "")),
            )
    logger.info(f"[MATCH] Pre-normalized {len(pin_norm_cache)} Pinnacle events")

    # Sport buckets already come from normalize_sport_label (Soccer vs NFL Football).
    pair_candidates = []  # (score, game_idx, pinnacle_event, orientation_direct)

    for game_idx, betbck_game in enumerate(betbck_games):
        # Progress logging every 10 games
        if game_idx % 10 == 0:
            logger.info(f"[MATCH] Progress: {game_idx}/{len(betbck_games)} games processed")
        
        # Skip if this BetBCK game was already matched within this run
        betbck_game_id = betbck_game.get('betbck_game_id', f"{betbck_game.get('betbck_site_home_team', '')}_{betbck_game.get('betbck_site_away_team', '')}")
        _mk_for_skip = betbck_game.get('market_suffix')
        if betbck_game_id in matched_betbck_ids:
            logger.info(f"[SKIP-ID] Already matched, skipping: {betbck_game_id!r} market={_mk_for_skip!r} | home={betbck_game.get('betbck_site_home_team')} away={betbck_game.get('betbck_site_away_team')}")
            continue
            
        betbck_home_raw = betbck_game.get("betbck_site_home_team", "")
        betbck_away_raw = betbck_game.get("betbck_site_away_team", "")
        logger.debug(f"[BETBCK] Raw teams: home='{betbck_home_raw}', away='{betbck_away_raw}'")
        logger.debug(f"[BETBCK] Raw odds: {betbck_game.get('betbck_site_odds', {})}")
        norm_bck_home = canonical_team_name(betbck_home_raw)
        norm_bck_away = canonical_team_name(betbck_away_raw)
        logger.debug(f"[NORM] BetBCK normalized: '{betbck_home_raw}' -> '{norm_bck_home}', '{betbck_away_raw}' -> '{norm_bck_away}'")
        
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
            
        logger.debug(f"[MATCH] Normalized BetBCK: '{norm_bck_home}' vs '{norm_bck_away}'")
        
        betbck_sport = resolve_betbck_sport(betbck_game, norm_bck_home, norm_bck_away)
        logger.debug(f"[MATCH] BetBCK game sport: {betbck_sport}")

        relevant_events = []
        seen_eids = set()
        for bucket in related_sport_buckets(betbck_sport):
            for ev in events_by_sport.get(bucket, []):
                eid = ev.get("event_id")
                if eid in seen_eids:
                    continue
                seen_eids.add(eid)
                relevant_events.append(ev)
        logger.debug(f"[MATCH] Found {len(relevant_events)} {betbck_sport}(+related) events to match against")
        
        # Extra info-level log for ALT MLB games so we can diagnose matching failures
        _is_alt_mlb = (betbck_game.get('market_suffix') == 'ALT' and betbck_sport == 'mlb')
        if _is_alt_mlb:
            logger.info(f"[ALT-DEBUG] Processing ALT game: '{norm_bck_home}' vs '{norm_bck_away}' | relevant_events={len(relevant_events)}")

        best_match = None
        best_score = 0
        best_orientation = None
        best_pinnacle_event = None
        
        for pinnacle_event in relevant_events:
            pin_home_raw = pinnacle_event.get("home_team", "")
            pin_away_raw = pinnacle_event.get("away_team", "")
            
            if is_prop_market_by_name(pin_home_raw, pin_away_raw):
                continue
                
            # --- ENHANCED LEAGUE & TIME CONTEXT CHECK ---
            # Check if games are from the same day (within 24 hours)
            betbck_time = betbck_game.get("event_datetime") or betbck_game.get("game_datetime") or ""
            pinnacle_time = pinnacle_event.get("event_datetime", "")
            
            # Log the teams and times for debugging
            logger.debug(f"[TIME-CHECK] BetBCK: {betbck_game.get('betbck_site_home_team', '?')} vs {betbck_game.get('betbck_site_away_team', '?')} at {betbck_time}")
            logger.debug(f"[TIME-CHECK] Pinnacle: {pin_home_raw} vs {pin_away_raw} at {pinnacle_time}")
            
            if betbck_time and pinnacle_time:
                try:
                    from datetime import datetime
                    betbck_dt = datetime.fromisoformat(betbck_time.replace('Z', '+00:00'))
                    pinnacle_dt = datetime.fromisoformat(pinnacle_time.replace('Z', '+00:00'))
                    time_diff = abs((betbck_dt - pinnacle_dt).total_seconds())
                    
                    # Match games within 72 hours of each other.
                    # 24h is too aggressive — it silently drops valid Ace games
                    # whose times are parsed in a different timezone offset than
                    # the Pinnacle UTC times.  The frontend 24h toggle handles
                    # display-level filtering; the matching layer just needs to
                    # avoid obviously wrong cross-day / cross-week false positives.
                    if time_diff > 259200:  # 72 hours in seconds
                        logger.info(f"[TIME-SKIP] Time diff too large ({time_diff/3600:.1f}h) — skipping: {betbck_time} vs {pinnacle_time}")
                        continue
                    else:
                        logger.debug(f"[TIME-MATCH] Time difference acceptable: {time_diff/3600:.1f} hours between {betbck_time} and {pinnacle_time}")
                except Exception as e:
                    logger.warning(f"[TIME-CHECK] Error parsing times: {e} - BetBCK: {betbck_time}, Pinnacle: {pinnacle_time}")
                    # Continue if we can't parse times, but log the issue
                    pass
            else:
                logger.debug(f"[TIME-CHECK] Missing datetime - BetBCK: {betbck_time}, Pinnacle: {pinnacle_time}")
                pass
            
            # Check for league/competition context compatibility
            if not is_league_compatible(betbck_game, pinnacle_event):
                logger.debug(f"[LEAGUE-SKIP] Incompatible leagues: BetBCK={betbck_game.get('league', 'Unknown')} vs Pinnacle={pinnacle_event.get('league', 'Unknown')}")
                continue

            # Sport-category filter — skip NFL vs soccer etc. Soccer/other is allowed.
            pinnacle_sport_category = normalize_sport_label(
                pinnacle_event.get("sport") or "", pinnacle_event.get("league") or ""
            )
            if pinnacle_sport_category == "other":
                pinnacle_sport_category = determine_sport_from_teams(pin_home_raw, pin_away_raw)
            if (
                betbck_sport not in ("other", "")
                and pinnacle_sport_category not in ("other", "")
                and pinnacle_sport_category not in related_sport_buckets(betbck_sport)
            ):
                logger.debug(f"[LEAGUE-CHECK] Skipping - BetBCK: {betbck_sport} vs Pinnacle: {pinnacle_sport_category}")
                continue
            # --- END LEAGUE CHECK ---

            # Use pre-normalized names from cache (avoids 877K+ normalize calls)
            cached = pin_norm_cache.get(pinnacle_event.get("event_id"))
            if cached is None:
                continue
            norm_pin_home, norm_pin_away = cached
            logger.debug(f"[NORM] Pinnacle normalized: '{pin_home_raw}' -> '{norm_pin_home}', '{pin_away_raw}' -> '{norm_pin_away}'")
            
            if not norm_pin_home or not norm_pin_away:
                continue

            # --- Season win total special matching ---
            # Pinnacle season win total events have away_team="Season Wins" so the
            # normal two-team fuzzy match always fails (away score ~0).  Instead,
            # we only compare the team (home) side, requiring a higher threshold
            # (75) to compensate for the relaxed constraint.  BetBCK sometimes
            # lists the same team name twice for these markets.
            _pin_is_season_wins = (pinnacle_event.get("is_special") is True
                                   and norm_pin_away == "season wins")
            if _pin_is_season_wins:
                home_vs_home = fuzz.token_set_ratio(norm_bck_home, norm_pin_home)
                away_vs_home = fuzz.token_set_ratio(norm_bck_away, norm_pin_home)
                team_match   = max(home_vs_home, away_vs_home)
                if team_match >= 75:
                    pair_candidates.append((team_match, game_idx, pinnacle_event, home_vs_home >= away_vs_home))
                    if team_match > best_score:
                        best_score = team_match
                        best_match = pinnacle_event
                        best_orientation = home_vs_home >= away_vs_home
                    logger.debug(f"[SEASON-WINS] Candidate '{norm_pin_home}' via team_match={team_match}")
                continue  # skip normal two-team scoring for this event

            score, is_direct = pair_orientation_score(
                norm_bck_home, norm_bck_away, norm_pin_home, norm_pin_away
            )
            logger.debug(
                f"[MATCH] Comparing: '{norm_bck_home} {norm_bck_away}' vs "
                f"'{norm_pin_home} {norm_pin_away}' (score={score}, direct={is_direct})"
            )
            if score > best_score:
                best_score = score
                best_match = pinnacle_event
                best_orientation = is_direct
            if score >= FUZZY_MATCH_THRESHOLD:
                pair_candidates.append((score, game_idx, pinnacle_event, is_direct))
                
        if best_match and best_score >= FUZZY_MATCH_THRESHOLD:
            # Assignment happens after all pairs are scored so a weak first
            # game cannot steal the Pinnacle event from a better later match.
            pass
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
                "reason": "below_threshold" if best_match else "no_candidates",
                "game_idx": game_idx,
            })

    # Highest-score pairs first so a weak alias cannot steal a Pinnacle event.
    pair_candidates.sort(key=lambda item: (-item[0], item[1]))
    assigned_bck = set()
    for score, game_idx, best_match, best_orientation in pair_candidates:
        betbck_game = betbck_games[game_idx]
        if game_idx in assigned_bck:
            continue
        _mk = betbck_game.get("market_suffix")
        pin_key = (best_match.get("event_id"), _mk)
        if _mk != "ALT" and pin_key in processed_pinnacle_keys:
            continue
        assigned_bck.add(game_idx)
        processed_pinnacle_event_ids.add(best_match["event_id"])
        if _mk != "ALT":
            processed_pinnacle_keys.add(pin_key)

        betbck_home_raw = betbck_game.get("betbck_site_home_team", "")
        betbck_away_raw = betbck_game.get("betbck_site_away_team", "")
        norm_bck_home = canonical_team_name(betbck_home_raw)
        norm_bck_away = canonical_team_name(betbck_away_raw)
        _cached_best = pin_norm_cache.get(best_match["event_id"], (None, None))
        norm_event_home = _cached_best[0] or canonical_team_name(best_match["home_team"])
        norm_event_away = _cached_best[1] or canonical_team_name(best_match["away_team"])
        betbck_odds = betbck_game.get("betbck_site_odds", {})
        top_ml = betbck_odds.get("site_top_team_moneyline_american")
        bottom_ml = betbck_odds.get("site_bottom_team_moneyline_american")
        if best_orientation:
            betbck_home_odds, betbck_away_odds = top_ml, bottom_ml
        else:
            betbck_home_odds, betbck_away_odds = bottom_ml, top_ml
        sport = resolve_betbck_sport(betbck_game, norm_bck_home, norm_bck_away)
        matched_betbck_ids.add(betbck_game.get("betbck_game_id", f"{betbck_home_raw}_{betbck_away_raw}"))
        logger.info(
            f"[MATCHED] SUCCESS: '{betbck_home_raw}' vs '{betbck_away_raw}' <-> "
            f"'{best_match['home_team']}' vs '{best_match['away_team']}' | "
            f"Score: {score} | Orientation: {'direct' if best_orientation else 'flipped'}"
        )
        matched_events.append({
            "pinnacle_event_id": best_match["event_id"],
            "pinnacle_home_team": best_match["home_team"],
            "pinnacle_away_team": best_match["away_team"],
            "betbck_game": betbck_game,
            "match_confidence": score / 100.0,
            "betbck_home_team": betbck_home_raw,
            "betbck_away_team": betbck_away_raw,
            "normalized_betbck_home": norm_bck_home,
            "normalized_betbck_away": norm_bck_away,
            "normalized_pinnacle_home": norm_event_home,
            "normalized_pinnacle_away": norm_event_away,
            "match_score": score,
            "orientation": "direct" if best_orientation else "flipped",
            "betbck_home_odds": betbck_home_odds,
            "betbck_away_odds": betbck_away_odds,
            "sport": sport,
            "market_suffix": betbck_game.get("market_suffix"),
        })

    unmatched_idxs = {u.get("game_idx") for u in unmatched_betbck}
    for score, game_idx, pin, _orient in pair_candidates:
        if game_idx in assigned_bck or game_idx in unmatched_idxs:
            continue
        g = betbck_games[game_idx]
        unmatched_betbck.append({
            "betbck_home": g.get("betbck_site_home_team", ""),
            "betbck_away": g.get("betbck_site_away_team", ""),
            "norm_home": canonical_team_name(g.get("betbck_site_home_team", "")),
            "norm_away": canonical_team_name(g.get("betbck_site_away_team", "")),
            "best_score": score,
            "best_pinnacle": f"{pin.get('home_team')} vs {pin.get('away_team')}",
            "reason": "pin_taken_by_better_match",
            "game_idx": game_idx,
        })
        unmatched_idxs.add(game_idx)
    
    # Log unmatched Pinnacle events
    for pinnacle_event in pinnacle_events:
        eid = pinnacle_event.get("event_id")
        if eid not in processed_pinnacle_event_ids:
            _cached = pin_norm_cache.get(eid, (None, None))
            unmatched_pinnacle.append({
                "pinnacle_home": pinnacle_event.get("home_team", ""),
                "pinnacle_away": pinnacle_event.get("away_team", ""),
                "event_id": eid or "",
                "norm_home": _cached[0] or canonical_team_name(pinnacle_event.get("home_team", "")),
                "norm_away": _cached[1] or canonical_team_name(pinnacle_event.get("away_team", ""))
            })
    
    # Summary logging
    logger.info(f"[MATCH] SUMMARY:")
    logger.info(f"[MATCH]   [MATCHED] Matched: {len(matched_events)} games")
    logger.info(f"[MATCH]   [UNMATCHED] Unmatched BetBCK: {len(unmatched_betbck)} games")
    logger.info(f"[MATCH]   [UNMATCHED] Unmatched Pinnacle: {len(unmatched_pinnacle)} events")
    total_bck = len(betbck_games)
    match_rate = (len(matched_events) / total_bck * 100) if total_bck else 0.0
    logger.info(f"[MATCH]   [STATS] Match rate: {len(matched_events)}/{total_bck} = {match_rate:.1f}%")
    
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