import math
import re
from typing import Optional

# Team aliases for better matching
TEAM_ALIASES = {
    'north korea': ['korea dpr', 'dpr korea', 'democratic people\'s republic of korea'],
    'south korea': ['korea republic', 'republic of korea'],
    'ivory coast': ['cote d\'ivoire'],
    'czech republic': ['czechia'],
    'united states': ['usa', 'us', 'united states of america'],
    'iran': ['iran', 'iran isl', 'islamic republic of iran'],
    'russia': ['russian federation'],
    'tottenham': ['tottenham hotspur', 'spurs'],
    'psg': ['paris saint germain', 'paris sg'],
    'inter': ['inter milan', 'internazionale'],
    'altach': ['rheindorf altach', 'scr altach'],
    # Scottish clubs
    'hearts': ['heart of midlothian', 'hearts fc', 'heart of midlothian fc'],
    'hibs': ['hibernian', 'hibernian fc'],
    'rangers': ['glasgow rangers', 'rangers fc'],
    'celtic': ['celtic fc', 'celtic glasgow'],
    'aberdeen': ['aberdeen fc'],
    'motherwell': ['motherwell fc'],
    'dundee': ['dundee fc'],
    'dundee united': ['dundee utd'],
    'ny': ['new york'],
    'la': ['los angeles'],
    'st. louis': ['st louis'],
    'orense': ['orenseecuador', 'orense ecuador', 'cd orense', 'club deportivo orense'],
    'manta': ['manta fc', 'manta futbol club', 'club deportivo manta'],
    'barcelona': ['barcelona sc', 'barcelona sporting club', 'barcelona ecuador'],
    'emelec': ['club sport emelec', 'cs emelec'],
    'independiente': ['independiente del valle', 'idv'],
    'universidad catolica': ['uc', 'universidad catolica quito'],
    'deportivo cuenca': ['cuenca', 'cd cuenca'],
    'el nacional': ['nacional', 'club deportivo el nacional'],
    'liga de quito': ['ldu', 'liga de quito quito'],
    'aucas': ['aucas quito', 'sociedad deportiva aucas'],
}

# Prop market indicators
PROP_INDICATORS_IN_TEAM_NAMES = [
    "to lift the trophy", "lift the trophy", "mvp", "futures", "outright",
    "coach of the year", "player of the year", "series correct score",
    "when will series finish", "most points in series", "most assists in series",
    "most rebounds in series", "most threes made in series", "margin of victory",
    "exact outcome", "winner", "to win the tournament", "to win group", "series price",
    "(corners)", "to win", "wins", "(match)", "series price", "to win series",
    "hits+runs+errors", "h+r+e", "hre"
]

def is_prop_market_by_name(home_team_name: str, away_team_name: str) -> bool:
    """Check if a market is a prop/future market based on team names."""
    if not home_team_name or not away_team_name:
        return False
    
    for name in [home_team_name, away_team_name]:
        name_lower = name.lower()
        for indicator in PROP_INDICATORS_IN_TEAM_NAMES:
            if indicator in name_lower:
                return True
    
    if "field" in away_team_name.lower() and "the" in away_team_name.lower():
        return True
    if home_team_name.lower() == "yes" and away_team_name.lower() == "no":
        return True
    
    return False

def alias_normalize(name: str) -> str:
    """Normalize team names using aliases."""
    name = name.lower().strip()
    for canonical, aliases in TEAM_ALIASES.items():
        if name == canonical or name in aliases:
            return canonical
    return name

def normalize_team_name_for_matching(name):
    original_name_for_debug = name
    if name is None or not name:
        print(f"[Utils] WARNING: normalize_team_name_for_matching received None or empty input: '{original_name_for_debug}'")
        return ""
    
    # Debug logging for UEFA cases
    if 'uefa' in name.lower():
        print(f"[UEFA_DEBUG] Processing UEFA team name: '{name}'")

    # Remove common phrases indicating a prop/future
    trophy_match = re.match(r'(.+?)\s*(?:to lift the trophy|lift the trophy|to win.*|wins.*|\(match\)|series price|to win series|\(corners\))', name, re.IGNORECASE)
    if trophy_match:
        name = trophy_match.group(1).strip()

    norm_name = name.lower()
    norm_name = re.sub(r'\s*\((?:games|sets|match|hits\+runs\+errors|h\+r\+e|hre|corners)\)$', '', norm_name).strip()
    norm_name = re.sub(r'\s*\([^)]*\)', '', norm_name).strip()

    # Remove country/competition suffixes if not the whole name
    suffix_patterns = [
        r'\s*usa$', r'\s*u21$', r'\s*u19$', r'\s*uefa.*$', r'uefa.*$', r'\s*fifa.*$', r'fifa.*$', r'\s*euro.*$', r'euro.*$', r'\s*afc.*$', r'afc.*$', r'\s*concacaf.*$', r'concacaf.*$', r'\s*conmebol.*$', r'conmebol.*$', r'\s*olympics.*$', r'olympics.*$', r'\s*championship.*$', r'championship.*$', r'\s*cup.*$', r'cup.*$', r'\s*league.*$', r'league.*$', r'\s*mls$', r'mls$', r'\s*england$', r'england$', r'\s*scotland$', r'scotland$', r'\s*france$', r'france$', r'\s*spain$', r'spain$', r'\s*italy$', r'italy$', r'\s*germany$', r'germany$', r'\s*netherlands$', r'netherlands$', r'\s*portugal$', r'portugal$', r'\s*denmark$', r'denmark$', r'\s*sweden$', r'sweden$', r'\s*norway$', r'norway$', r'\s*switzerland$', r'switzerland$', r'\s*belgium$', r'belgium$', r'\s*austria$', r'austria$', r'\s*poland$', r'poland$', r'\s*croatia$', r'croatia$', r'\s*serbia$', r'serbia$', r'\s*romania$', r'romania$', r'\s*bulgaria$', r'bulgaria$', r'\s*slovakia$', r'slovakia$', r'\s*slovenia$', r'slovenia$', r'\s*hungary$', r'hungary$', r'\s*czech republic$', r'czech republic$', r'\s*russia$', r'russia$', r'\s*ukraine$', r'ukraine$', r'\s*turkey$', r'turkey$', r'\s*greece$', r'greece$', r'\s*ireland$', r'ireland$', r'\s*wales$', r'wales$', r'\s*northern ireland$', r'northern ireland$', r'\s*iceland$', r'iceland$'
    ]
    for pattern in suffix_patterns:
        if norm_name != pattern.strip('\\s*$'):
            norm_name = re.sub(pattern, '', norm_name, flags=re.IGNORECASE).strip()

    league_country_suffixes = [
        'mlb', 'nba', 'nfl', 'nhl', 'ncaaf', 'ncaab', 'wnba',
        'poland', 'bulgaria', 'uruguay', 'colombia', 'peru', 'argentina',
        'sweden', 'romania', 'finland', 'england', 'japan', 'austria',
        'liga 1', 'serie a', 'bundesliga', 'la liga', 'ligue 1', 'premier league',
        'epl', 'mls', 'tipico bundesliga', 'belarus', 'iceland'
    ]
    for suffix in league_country_suffixes:
        pattern = r'(\s+' + re.escape(suffix) + r'|' + re.escape(suffix) + r')$'
        if re.search(pattern, norm_name, flags=re.IGNORECASE):
            temp_name = re.sub(pattern, '', norm_name, flags=re.IGNORECASE, count=1).strip()
            if temp_name or len(norm_name) == len(suffix):
                norm_name = temp_name

    common_prefixes = ['if ', 'fc ', 'sc ', 'bk ', 'sk ', 'ac ', 'as ', 'fk ', 'cd ', 'ca ', 'afc ', 'cfr ', 'kc ', 'scr ']
    for prefix in common_prefixes:
        if norm_name.startswith(prefix): norm_name = norm_name[len(prefix):].strip()
    for prefix in common_prefixes:
        if norm_name.startswith(prefix): norm_name = norm_name[len(prefix):].strip()

    if "tottenham hotspur" in name.lower(): norm_name = "tottenham"
    elif "paris saint germain" in name.lower() or "paris sg" in name.lower(): norm_name = "psg"
    elif "new york" in name.lower(): norm_name = norm_name.replace("new york", "ny")
    elif "los angeles" in name.lower(): norm_name = norm_name.replace("los angeles", "la")
    elif "st louis" in name.lower(): norm_name = norm_name.replace("st louis", "st. louis")
    elif "inter milan" in name.lower() or name.lower() == "internazionale": norm_name = "inter"
    elif "rheindorf altach" in name.lower(): norm_name = "altach"
    elif "scr altach" in name.lower(): norm_name = "altach"

    # Convert to lowercase and strip whitespace
    normalized = norm_name.lower().strip()
    # Remove common suffixes like 'Chile', 'USA', 'UEFA - U21 European Championship', 'CONCACAF', 'Nippon Professional Baseball', etc.
    suffixes = ["chile", "usa", "uefa - u21 european championship", "concacaf", "nippon professional baseball"]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
    
    # Additional UEFA cleanup - remove UEFA suffix if it appears at the end
    if normalized.endswith('uefa'):
        normalized = normalized[:-4]  # Remove 'uefa' (4 characters)
        print(f"[UEFA_DEBUG] Removed 'uefa' suffix: '{normalized}'")
    
    # Also remove any remaining UEFA with variations
    normalized = re.sub(r'uefa.*$', '', normalized, flags=re.IGNORECASE).strip()
    
    # Additional check for UEFA without space (like "akureyriuefa")
    if 'uefa' in normalized.lower():
        normalized = re.sub(r'uefa', '', normalized, flags=re.IGNORECASE).strip()
        print(f"[UEFA_DEBUG] Removed embedded 'uefa': '{normalized}'")
    
    # Final check - if the name still contains UEFA, try to remove it completely
    if 'uefa' in normalized.lower():
        normalized = normalized.lower().replace('uefa', '').strip()
        print(f"[UEFA_DEBUG] Final UEFA removal: '{normalized}'")
    
    # Additional comprehensive UEFA cleanup for edge cases
    # Handle cases like "iberia 1999uefa" -> "iberia 1999"
    normalized = re.sub(r'(\d+)\s*uefa', r'\1', normalized, flags=re.IGNORECASE).strip()
    # Handle cases like "salzburguefa" -> "salzburg"
    normalized = re.sub(r'([a-z]+)uefa', r'\1', normalized, flags=re.IGNORECASE).strip()
    # Handle any remaining UEFA
    normalized = re.sub(r'uefa', '', normalized, flags=re.IGNORECASE).strip()
    
    # Additional UEFA cleanup for specific cases like "rfsuefa" -> "rfs"
    if 'uefa' in normalized.lower():
        print(f"[UEFA_DEBUG] Found UEFA in normalized name: '{normalized}'")
        # Try more aggressive UEFA removal
        normalized = re.sub(r'uefa', '', normalized, flags=re.IGNORECASE).strip()
        print(f"[UEFA_DEBUG] After aggressive removal: '{normalized}'")
    
    if 'uefa' in normalized.lower():
        print(f"[UEFA_DEBUG] WARNING: UEFA still present after all cleanup attempts: '{normalized}'")

    # Additional comprehensive CONMEBOL cleanup for edge cases
    # Handle cases like "club bolivarconmebol" -> "club bolivar"
    # Handle cases like "paraguayconmebol - copa america femenina" -> "paraguay - copa america femenina"
    if 'conmebol' in normalized.lower():
        print(f"[CONMEBOL_DEBUG] Found CONMEBOL in: '{normalized}'")
        # First, handle CONMEBOL attached to letters (no space)
        normalized = re.sub(r'([a-z]+)conmebol', r'\1', normalized, flags=re.IGNORECASE).strip()
        print(f"[CONMEBOL_DEBUG] After pattern removal: '{normalized}'")
        # Then handle CONMEBOL with spaces around it
        normalized = re.sub(r'\s*conmebol\s*', ' ', normalized, flags=re.IGNORECASE).strip()
        print(f"[CONMEBOL_DEBUG] After space removal: '{normalized}'")
        # Handle any remaining CONMEBOL
        normalized = re.sub(r'conmebol', '', normalized, flags=re.IGNORECASE).strip()
        print(f"[CONMEBOL_DEBUG] After final removal: '{normalized}'")
        # Clean up any double spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        print(f"[CONMEBOL_DEBUG] After space cleanup: '{normalized}'")
    
    if 'conmebol' in normalized.lower():
        print(f"[CONMEBOL_DEBUG] WARNING: CONMEBOL still present after all cleanup attempts: '{normalized}'")

    # Additional comprehensive country cleanup for edge cases
    # Handle cases like "union magdalenacolombia" -> "union magdalena"
    country_names = ['colombia', 'argentina', 'brazil', 'chile', 'peru', 'uruguay', 'paraguay', 'ecuador', 'bolivia', 'venezuela', 'mexico', 'canada', 'usa', 'england', 'spain', 'france', 'germany', 'italy', 'portugal', 'netherlands', 'belgium', 'switzerland', 'austria', 'poland', 'czech republic', 'slovakia', 'hungary', 'romania', 'bulgaria', 'serbia', 'croatia', 'slovenia', 'ukraine', 'russia', 'turkey', 'greece', 'japan', 'china', 'korea', 'australia', 'new zealand']
    for country in country_names:
        if country in normalized.lower():
            print(f"[COUNTRY_DEBUG] Found {country} in: '{normalized}'")
            # Handle cases like "union magdalenacolombia" -> "union magdalena"
            normalized = re.sub(r'([a-z]+)' + country, r'\1', normalized, flags=re.IGNORECASE).strip()
            print(f"[COUNTRY_DEBUG] After pattern removal: '{normalized}'")
            # Handle any remaining country name
            normalized = re.sub(r'\b' + country + r'\b', '', normalized, flags=re.IGNORECASE).strip()
            print(f"[COUNTRY_DEBUG] After final removal: '{normalized}'")
    
    # Check if any country names are still present
    for country in country_names:
        if country in normalized.lower():
            print(f"[COUNTRY_DEBUG] WARNING: {country} still present after all cleanup attempts: '{normalized}'")

    # Additional comprehensive league cleanup for edge cases
    # Handle cases like "teamnamemls" -> "teamname"
    league_names = ['mls', 'mlb', 'nba', 'nfl', 'nhl', 'ncaaf', 'ncaab', 'wnba', 'pfl', 'ufc', 'bellator', 'bkfc', 'lfa', 'rizin', 'liga', 'serie', 'bundesliga', 'premier', 'epl', 'la liga', 'ligue']
    for league in league_names:
        if league in normalized.lower():
            print(f"[LEAGUE_DEBUG] Found {league} in: '{normalized}'")
            # Handle cases like "teamnamemls" -> "teamname"
            normalized = re.sub(r'([a-z]+)' + league, r'\1', normalized, flags=re.IGNORECASE).strip()
            print(f"[LEAGUE_DEBUG] After pattern removal: '{normalized}'")
            # Handle any remaining league name
            normalized = re.sub(r'\b' + league + r'\b', '', normalized, flags=re.IGNORECASE).strip()
            print(f"[LEAGUE_DEBUG] After final removal: '{normalized}'")
    
    # Check if any league names are still present
    for league in league_names:
        if league in normalized.lower():
            print(f"[LEAGUE_DEBUG] WARNING: {league} still present after all cleanup attempts: '{normalized}'")

    norm_name = re.sub(r'^[^\w]+|[^\w]+$', '', normalized)
    norm_name = re.sub(r'[^\w\s\.\-\+]', '', norm_name)
    final_normalized_name = " ".join(norm_name.split()).strip()
    
    # Debug logging for UEFA cases
    if 'uefa' in original_name_for_debug.lower():
        print(f"[UEFA_DEBUG] FINAL RESULT: '{original_name_for_debug}' ---> '{final_normalized_name}'")
        if 'uefa' in final_normalized_name.lower():
            print(f"[UEFA_DEBUG] ⚠️ UEFA STILL PRESENT in final result!")
    
    print(f"[NORM_DEBUG] Original: '{original_name_for_debug}' ---> Normalized: '{final_normalized_name}'")
    return final_normalized_name if final_normalized_name else (original_name_for_debug.lower().strip() if original_name_for_debug else "")

def match_betbck_to_pinnacle_markets(betbck_data, pinnacle_data):
    """
    For each BetBCK market/line, find the best matching Pinnacle market/line using normalization and fuzzy logic.
    Returns a list of dicts with market, selection, line, pinnacle_nvp, betbck_odds, ev.
    """
    import math
    markets = []
    # Always use the .get('data', {}) level for both
    betbck = betbck_data.get('data', betbck_data) if isinstance(betbck_data, dict) else {}
    pinnacle = pinnacle_data.get('data', pinnacle_data) if isinstance(pinnacle_data, dict) else {}
    pin_periods = pinnacle.get('periods', {})
    pin_full_game = pin_periods.get('num_0', {})
    # --- Moneyline ---
    pin_ml = pin_full_game.get('money_line', {})
    if betbck.get('home_moneyline_american') and pin_ml.get('nvp_american_home'):
        markets.append({
            'market': 'Moneyline',
            'selection': 'Home',
            'line': '',
            'pinnacle_nvp': pin_ml.get('nvp_american_home', 'N/A'),
            'betbck_odds': betbck.get('home_moneyline_american', 'N/A'),
            'ev': '0.00%'
        })
    if betbck.get('away_moneyline_american') and pin_ml.get('nvp_american_away'):
        markets.append({
            'market': 'Moneyline',
            'selection': 'Away',
            'line': '',
            'pinnacle_nvp': pin_ml.get('nvp_american_away', 'N/A'),
            'betbck_odds': betbck.get('away_moneyline_american', 'N/A'),
            'ev': '0.00%'
        })
    if betbck.get('draw_moneyline_american') and pin_ml.get('nvp_american_draw'):
        markets.append({
            'market': 'Moneyline',
            'selection': 'Draw',
            'line': '',
            'pinnacle_nvp': pin_ml.get('nvp_american_draw', 'N/A'),
            'betbck_odds': betbck.get('draw_moneyline_american', 'N/A'),
            'ev': '0.00%'
        })
    # --- Spreads ---
    pin_spreads = pin_full_game.get('spreads', {})
    def find_spread(pin_spreads, bck_line, is_home):
        for spread in pin_spreads.values():
            try:
                hdp = float(spread.get('hdp', 0))
                if is_home and math.isclose(hdp, float(bck_line), abs_tol=0.01):
                    return spread
                if not is_home and math.isclose(hdp, -float(bck_line), abs_tol=0.01):
                    return spread
            except Exception:
                continue
        return None
    for spread in betbck.get('home_spreads', []):
        bck_line = spread.get('line')
        pin_spread = find_spread(pin_spreads, bck_line, True)
        markets.append({
            'market': 'Spread',
            'selection': 'Home',
            'line': str(bck_line),
            'pinnacle_nvp': pin_spread.get('nvp_american_home', 'N/A') if pin_spread else 'N/A',
            'betbck_odds': spread.get('odds', 'N/A'),
            'ev': '0.00%'
        })
    for spread in betbck.get('away_spreads', []):
        bck_line = spread.get('line')
        pin_spread = find_spread(pin_spreads, bck_line, False)
        markets.append({
            'market': 'Spread',
            'selection': 'Away',
            'line': str(bck_line),
            'pinnacle_nvp': pin_spread.get('nvp_american_away', 'N/A') if pin_spread else 'N/A',
            'betbck_odds': spread.get('odds', 'N/A'),
            'ev': '0.00%'
        })
    # --- Totals ---
    pin_totals = pin_full_game.get('totals', {})
    def find_total(pin_totals, bck_line):
        for total in pin_totals.values():
            try:
                points = float(total.get('points', 0))
                if math.isclose(points, float(bck_line), abs_tol=0.01):
                    return total
            except Exception:
                continue
        return None
    if betbck.get('game_total_line') is not None:
        bck_line = betbck.get('game_total_line')
        pin_total = find_total(pin_totals, bck_line)
        markets.append({
            'market': 'Total',
            'selection': 'Over',
            'line': str(bck_line),
            'pinnacle_nvp': pin_total.get('nvp_american_over', 'N/A') if pin_total else betbck.get('game_total_over_odds', 'N/A'),
            'betbck_odds': betbck.get('game_total_over_odds', 'N/A'),
            'ev': '0.00%'
        })
        markets.append({
            'market': 'Total',
            'selection': 'Under',
            'line': str(bck_line),
            'pinnacle_nvp': pin_total.get('nvp_american_under', 'N/A') if pin_total else betbck.get('game_total_under_odds', 'N/A'),
            'betbck_odds': betbck.get('game_total_under_odds', 'N/A'),
            'ev': '0.00%'
        })
    return markets

# ... rest of the file as in POD_Server_Betbck_Scraper/utils.py ... 