import re
import math
import copy
from typing import Dict, Any, Optional, List, Union
import logging
try:
    from fuzzywuzzy import fuzz
    FUZZY_MATCH_THRESHOLD = 82
except ImportError:
    fuzz = None
    FUZZY_MATCH_THRESHOLD = 101

logger = logging.getLogger(__name__)

# NOTE: This is the canonical location for analyze_markets_for_ev and all odds/EV processing logic. Do not duplicate in odds_processing.py.

def american_to_decimal(american_odds_str: Union[str, int, float, None]) -> Optional[float]:
    """Convert American odds to decimal odds."""
    if american_odds_str is None:
        return None
    try:
        if isinstance(american_odds_str, str) and not re.match(r"^[+-]?\d+$", american_odds_str.strip()):
            return None
        odds = float(str(american_odds_str).strip())
        if odds > 0:
            return (odds / 100.0) + 1.0
        if odds < 0:
            return (100.0 / abs(odds)) + 1.0
        return None
    except ValueError:
        return None

def decimal_to_american(decimal_odds: Union[float, int, None]) -> Optional[str]:
    """Convert decimal odds to American odds."""
    if decimal_odds is None or not isinstance(decimal_odds, (float, int)):
        return None
    if decimal_odds <= 1.0001:
        return None
    if decimal_odds >= 2.0:
        return f"+{int(round((decimal_odds - 1) * 100))}"
    return f"{int(round(-100 / (decimal_odds - 1)))}"

def calculate_ev(bet_decimal: float, true_decimal: float) -> float:
    """Calculate expected value for a bet as (bet_decimal / true_decimal) - 1, matching PODBot logic."""
    if not bet_decimal or not true_decimal or bet_decimal <= 0 or true_decimal <= 0:
        return 0.0
    return (bet_decimal / true_decimal) - 1

def adjust_power_probabilities(probabilities: List[float], tolerance: float = 1e-4, max_iterations: int = 100) -> List[float]:
    """Adjust probabilities using power method to remove overround."""
    k = 1.0
    valid_probs_for_power = [p for p in probabilities if p is not None and p > 0]
    if not valid_probs_for_power or len(valid_probs_for_power) < 2:
        return [0] * len(valid_probs_for_power)

    for i in range(max_iterations):
        current_powered_probs = []
        for p_val in valid_probs_for_power:
            try:
                current_powered_probs.append(math.pow(p_val, k))
            except ValueError:
                sum_original_probs = sum(valid_probs_for_power)
                if sum_original_probs == 0:
                    return [0] * len(valid_probs_for_power)
                return [p/sum_original_probs for p in valid_probs_for_power]

        sum_powered_probs = sum(current_powered_probs)
        if sum_powered_probs == 0:
            break

        overround_metric = sum_powered_probs - 1.0
        if abs(overround_metric) < tolerance:
            break

        derivative_terms = []
        for p_val in valid_probs_for_power:
            try:
                derivative_terms.append(math.pow(p_val, k) * math.log(p_val))
            except ValueError:
                derivative_terms.append(0)

        derivative = sum(derivative_terms)
        if abs(derivative) < 1e-9:
            break
        k -= overround_metric / derivative

    final_powered_probs = [math.pow(p, k) for p in valid_probs_for_power]
    sum_final_powered_probs = sum(final_powered_probs)

    if sum_final_powered_probs == 0:
        return [1.0 / len(valid_probs_for_power) if valid_probs_for_power else 0] * len(valid_probs_for_power)

    normalized_true_probs = [p_pow / sum_final_powered_probs for p_pow in final_powered_probs]
    return normalized_true_probs

def calculate_nvp_for_market(odds_list: List[Union[float, int, None]]) -> List[Optional[float]]:
    """Calculate No Vig Price (NVP) for a market."""
    valid_odds_indices = [i for i, odd in enumerate(odds_list) if odd is not None and isinstance(odd, (int, float)) and odd > 1.0001]
    if len(valid_odds_indices) < 2:
        return [None] * len(odds_list)

    current_valid_odds = [odds_list[i] for i in valid_odds_indices]
    implied_probs = []
    for odd in current_valid_odds:
        if odd == 0:
            return [None] * len(odds_list)
        implied_probs.append(1.0 / odd)

    if sum(implied_probs) == 0:
        return [None] * len(odds_list)

    if sum(implied_probs) <= 1.0001:
        nvps_for_valid = current_valid_odds
    else:
        true_probs = adjust_power_probabilities(implied_probs)
        nvps_for_valid = [round(1.0 / p, 3) if p is not None and p > 1e-9 else None for p in true_probs]

    final_nvp_list = [None] * len(odds_list)
    for i, original_idx in enumerate(valid_odds_indices):
        if i < len(nvps_for_valid):
            final_nvp_list[original_idx] = nvps_for_valid[i]
    return final_nvp_list

def process_event_odds_for_display(pinnacle_event_json_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add NVP (No Vig Price) and American Odds to Pinnacle odds data."""
    if not pinnacle_event_json_data or 'data' not in pinnacle_event_json_data:
        return pinnacle_event_json_data

    event_detail = pinnacle_event_json_data['data']
    if not isinstance(event_detail, dict):
        return pinnacle_event_json_data

    periods = event_detail.get("periods", {})
    if not isinstance(periods, dict):
        return pinnacle_event_json_data

    for period_key, period_data in periods.items():
        if not isinstance(period_data, dict):
            continue

        # Remove the 'history' key from each period
        if 'history' in period_data:
            del period_data['history']

        # Moneyline
        if period_data.get("money_line") and isinstance(period_data["money_line"], dict):
            ml = period_data["money_line"]
            odds_dec = [ml.get("home"), ml.get("draw"), ml.get("away")]
            nvps_dec = calculate_nvp_for_market(odds_dec)

            if len(nvps_dec) == 3:
                ml["nvp_home"] = nvps_dec[0]
                ml["nvp_draw"] = nvps_dec[1]
                ml["nvp_away"] = nvps_dec[2]
            ml["american_home"] = decimal_to_american(ml.get("home"))
            ml["american_draw"] = decimal_to_american(ml.get("draw"))
            ml["american_away"] = decimal_to_american(ml.get("away"))
            ml["nvp_american_home"] = decimal_to_american(ml.get("nvp_home"))
            ml["nvp_american_draw"] = decimal_to_american(ml.get("nvp_draw"))
            ml["nvp_american_away"] = decimal_to_american(ml.get("nvp_away"))

        # Spreads
        if period_data.get("spreads") and isinstance(period_data["spreads"], dict):
            for hdp_key, spread_details in period_data["spreads"].items():
                if isinstance(spread_details, dict):
                    odds_dec = [spread_details.get("home"), spread_details.get("away")]
                    nvps_dec = calculate_nvp_for_market(odds_dec)
                    if len(nvps_dec) == 2:
                        spread_details["nvp_home"], spread_details["nvp_away"] = nvps_dec[0], nvps_dec[1]
                    spread_details["american_home"] = decimal_to_american(spread_details.get("home"))
                    spread_details["american_away"] = decimal_to_american(spread_details.get("away"))
                    spread_details["nvp_american_home"] = decimal_to_american(spread_details.get("nvp_home"))
                    spread_details["nvp_american_away"] = decimal_to_american(spread_details.get("nvp_away"))

        # Totals
        if period_data.get("totals") and isinstance(period_data["totals"], dict):
            for points_key, total_details in period_data["totals"].items():
                if isinstance(total_details, dict):
                    odds_dec = [total_details.get("over"), total_details.get("under")]
                    nvps_dec = calculate_nvp_for_market(odds_dec)
                    if len(nvps_dec) == 2:
                        total_details["nvp_over"], total_details["nvp_under"] = nvps_dec[0], nvps_dec[1]
                    total_details["american_over"] = decimal_to_american(total_details.get("over"))
                    total_details["american_under"] = decimal_to_american(total_details.get("under"))
                    total_details["nvp_american_over"] = decimal_to_american(total_details.get("nvp_over"))
                    total_details["nvp_american_under"] = decimal_to_american(total_details.get("nvp_under"))

    return pinnacle_event_json_data

# Team aliases for better matching
TEAM_ALIASES = {
    # International soccer — nations
    'north korea': ['korea dpr', 'dpr korea', "democratic people's republic of korea"],
    'south korea': ['korea republic', 'republic of korea'],
    'ivory coast': ["cote d'ivoire", 'cote divoire'],
    'czech republic': ['czechia'],
    'united states': ['usa', 'us', 'united states of america'],
    'iran': ['iran isl', 'islamic republic of iran'],
    'russia': ['russian federation'],
    # European clubs
    'inter': ['inter milan', 'internazionale', 'fc internazionale'],
    'tottenham': ['tottenham hotspur', 'spurs'],
    'psg': ['paris saint germain', 'paris sg', 'paris saint-germain'],
    'altach': ['rheindorf altach', 'scr altach'],
    'man city': ['manchester city'],
    'man united': ['manchester united', 'manchester utd'],
    'athletic club': ['athletic bilbao'],
    'wolves': ['wolverhampton', 'wolverhampton wanderers'],
    'newcastle': ['newcastle united'],
    'west ham': ['west ham united'],
    'brighton': ['brighton hove albion', 'brighton & hove albion'],
    'bournemouth': ['afc bournemouth'],
    # Scottish clubs
    'hearts': ['heart of midlothian', 'hearts fc', 'heart of midlothian fc'],
    'hibs': ['hibernian', 'hibernian fc'],
    'rangers': ['glasgow rangers', 'rangers fc'],
    'celtic': ['celtic fc', 'celtic glasgow'],
    'aberdeen': ['aberdeen fc'],
    'motherwell': ['motherwell fc'],
    'dundee': ['dundee fc'],
    'dundee united': ['dundee utd'],
    'bayer leverkusen': ['leverkusen'],
    'rb leipzig': ['rasenballsport leipzig', 'red bull leipzig'],
    'sporting': ['sporting cp', 'sporting clube de portugal'],
    'benfica': ['sl benfica'],
    'porto': ['fc porto'],
    'ajax': ['afc ajax'],
    'psv': ['psv eindhoven'],
    'napoli': ['ssc napoli'],
    'juventus': ['juve'],
    'roma': ['as roma'],
    'lazio': ['ss lazio'],
    'sevilla': ['sevilla fc'],
    'real sociedad': ['sociedad'],
    'real betis': ['betis'],
    'villarreal': ['villarreal cf'],
    # CFL
    'tiger cats': ['tiger-cats', 'hamilton tiger cats', 'hamilton tiger-cats'],
    'blue bombers': ['winnipeg blue bombers'],
    'roughriders': ['saskatchewan roughriders'],
    'stampeders': ['calgary stampeders'],
    'eskimos': ['edmonton eskimos', 'edmonton elks'],
    'redblacks': ['ottawa redblacks'],
    'argonauts': ['toronto argonauts'],
    'alouettes': ['montreal alouettes'],
    'lions cfl': ['bc lions', 'british columbia lions'],
    # Geographic shorthands
    'new york': ['ny'],
    'los angeles': ['la'],
    'st louis': ['st. louis', 'saint louis'],
    # MLB
    'brewers': ['milwaukee brewers'],
    'phillies': ['philadelphia phillies'],
    'dodgers': ['los angeles dodgers'],
    'angels': ['los angeles angels', 'anaheim angels'],
    'yankees': ['new york yankees', 'ny yankees'],
    'mets': ['new york mets', 'ny mets'],
    'cubs': ['chicago cubs'],
    'white sox': ['chicago white sox'],
    'red sox': ['boston red sox'],
    'giants sf': ['san francisco giants'],
    'braves': ['atlanta braves'],
    'astros': ['houston astros'],
    'cardinals': ['st. louis cardinals', 'st louis cardinals'],
    'rockies': ['colorado rockies'],
    'mariners': ['seattle mariners'],
    'rays': ['tampa bay rays'],
    'blue jays': ['toronto blue jays'],
    'twins': ['minnesota twins'],
    'tigers': ['detroit tigers'],
    'guardians': ['cleveland guardians'],
    'orioles': ['baltimore orioles'],
    'royals': ['kansas city royals'],
    'rangers': ['texas rangers'],
    'athletics': ['oakland athletics', "oakland a's"],
    'diamondbacks': ['arizona diamondbacks'],
    'padres': ['san diego padres'],
    'marlins': ['miami marlins'],
    'pirates': ['pittsburgh pirates'],
    'reds': ['cincinnati reds'],
    'nationals': ['washington nationals'],
    # NBA
    'lakers': ['los angeles lakers', 'la lakers'],
    'clippers': ['los angeles clippers', 'la clippers'],
    'knicks': ['new york knicks', 'ny knicks'],
    'warriors': ['golden state warriors'],
    'bulls': ['chicago bulls'],
    'celtics': ['boston celtics'],
    'heat': ['miami heat'],
    'mavericks': ['dallas mavericks'],
    'nets': ['brooklyn nets'],
    '76ers': ['philadelphia 76ers', 'sixers'],
    'bucks': ['milwaukee bucks'],
    'suns': ['phoenix suns'],
    'nuggets': ['denver nuggets'],
    'jazz': ['utah jazz'],
    'blazers': ['portland trail blazers', 'trail blazers'],
    'thunder': ['oklahoma city thunder'],
    'spurs': ['san antonio spurs'],
    'hawks': ['atlanta hawks'],
    'hornets': ['charlotte hornets'],
    'cavaliers': ['cleveland cavaliers'],
    'pistons': ['detroit pistons'],
    'pacers': ['indiana pacers'],
    'grizzlies': ['memphis grizzlies'],
    'timberwolves': ['minnesota timberwolves'],
    'pelicans': ['new orleans pelicans'],
    'magic': ['orlando magic'],
    'kings': ['sacramento kings'],
    'raptors': ['toronto raptors'],
    'wizards': ['washington wizards'],
    'rockets': ['houston rockets'],
    # NFL
    'patriots': ['new england patriots'],
    'chiefs': ['kansas city chiefs'],
    'packers': ['green bay packers'],
    'cowboys': ['dallas cowboys'],
    '49ers': ['san francisco 49ers'],
    'bears': ['chicago bears'],
    'giants nfl': ['new york giants', 'ny giants'],
    'jets': ['new york jets', 'ny jets'],
    'eagles': ['philadelphia eagles'],
    'steelers': ['pittsburgh steelers'],
    'seahawks': ['seattle seahawks'],
    'raiders': ['las vegas raiders', 'oakland raiders'],
    'rams': ['los angeles rams', 'la rams'],
    'chargers': ['los angeles chargers', 'la chargers'],
    'dolphins': ['miami dolphins'],
    'bills': ['buffalo bills'],
    'ravens': ['baltimore ravens'],
    'browns': ['cleveland browns'],
    'bengals': ['cincinnati bengals'],
    'titans': ['tennessee titans'],
    'jaguars': ['jacksonville jaguars'],
    'texans': ['houston texans'],
    'colts': ['indianapolis colts'],
    'broncos': ['denver broncos'],
    'vikings': ['minnesota vikings'],
    'lions': ['detroit lions'],
    'panthers': ['carolina panthers'],
    'falcons': ['atlanta falcons'],
    'saints': ['new orleans saints'],
    'buccaneers': ['tampa bay buccaneers'],
    'cardinals nfl': ['arizona cardinals'],
    'commanders': ['washington commanders', 'washington football team'],
    # NHL
    'maple leafs': ['toronto maple leafs'],
    'canadiens': ['montreal canadiens'],
    'bruins': ['boston bruins'],
    'rangers nhl': ['new york rangers', 'ny rangers'],
    'islanders': ['new york islanders', 'ny islanders'],
    'blackhawks': ['chicago blackhawks'],
    'red wings': ['detroit red wings'],
    'penguins': ['pittsburgh penguins'],
    'flyers': ['philadelphia flyers'],
    'capitals': ['washington capitals'],
    'avalanche': ['colorado avalanche'],
    'oilers': ['edmonton oilers'],
    'flames': ['calgary flames'],
    'canucks': ['vancouver canucks'],
    'senators': ['ottawa senators'],
    'winnipeg jets': ['jets winnipeg'],
    'wild': ['minnesota wild'],
    'blues': ['st. louis blues', 'st louis blues'],
    'predators': ['nashville predators'],
    'stars': ['dallas stars'],
    'lightning': ['tampa bay lightning'],
    'florida panthers': ['panthers florida'],
    'hurricanes': ['carolina hurricanes'],
    'devils': ['new jersey devils'],
    'sabres': ['buffalo sabres'],
    'coyotes': ['arizona coyotes', 'utah hockey club'],
    'kraken': ['seattle kraken'],
    'golden knights': ['vegas golden knights', 'las vegas golden knights'],
    'ducks': ['anaheim ducks'],
    'la kings': ['los angeles kings'],
    'sharks': ['san jose sharks'],
    'blue jackets': ['columbus blue jackets'],
    # South American clubs
    'flamengo': ['cr flamengo', 'clube de regatas do flamengo'],
    'fluminense': ['fluminense fc'],
    'palmeiras': ['se palmeiras'],
    'corinthians': ['sport club corinthians paulista', 'sc corinthians'],
    'sao paulo': ['sao paulo fc'],
    'atletico mineiro': ['atletico mg', 'atletico-mg'],
    'boca juniors': ['boca'],
    'river plate': ['river'],
}

def alias_normalize(name):
    """Normalize team names using aliases."""
    name = name.lower().strip()
    for canonical, aliases in TEAM_ALIASES.items():
        if name == canonical or name in aliases:
            return canonical
    return name

def normalize_team_name_for_matching(name):
    original_name_for_debug = name
    if not name: return ""
    # Strip leading numbers and spaces
    name = re.sub(r'^\d+\s*', '', name).strip()
    
    # Handle pitcher names in MLB (e.g., "Houston AstrosJ Alexander - R must start")
    # Remove pitcher information that appears after the team name
    pitcher_patterns = [
        r'^([A-Za-z\s]+?)[A-Z][a-z]*\s+[A-Z][a-z]*\s*-\s*[LR]\s+must\s+start$',  # "Team NamePitcher Name - L must start"
        r'^([A-Za-z\s]+?)[A-Z][a-z]*\s*-\s*[LR]\s+must\s+start$',  # "Team NamePitcher - L must start"
        r'^([A-Za-z\s]+?)[A-Z]\s*-\s*[LR]\s+must\s+start$',  # "Team NameP - L must start"
    ]
    for pattern in pitcher_patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            break
    
    # Handle common phrases indicating a prop/future first
    trophy_match = re.match(r'(.+?)\s*(?:to lift the trophy|lift the trophy|to win.*|wins.*|\(match\)|series price|to win series|\(corners\))', name, re.IGNORECASE)
    if trophy_match:
        name = trophy_match.group(1).strip()
    norm_name = name.lower()
    norm_name = re.sub(r'\s*\((?:games|sets|match|hits\+runs\+errors|h\+r\+e|hre|corners)\)$', '', norm_name).strip()
    norm_name = re.sub(r'\s*\([^)]*\)', '', norm_name).strip()
    # Strip trailing punctuation/dashes that POD sometimes appends (e.g. "ENPPIEgypt -" → "ENPPIEgypt")
    # This must happen before country suffix stripping so the suffix appears at the true end of the string
    norm_name = re.sub(r'[\s\-–—/\\|]+$', '', norm_name).strip()
    league_country_suffixes = [
        # Sports abbreviations
        'mlb', 'nba', 'nfl', 'nhl', 'ncaaf', 'ncaab', 'wnba', 'afl', 'cfl', 'mls', 'soccer', 'tennis', 'ufc', 'pfl', 'bellator', 'bkfc', 'lfa', 'rizin', 'one fc', 'one championship',
        
        # Full league names
        'nippon professional baseball', 'japanese professional baseball',
        'major league baseball', 'national football league', 'national basketball association',
        'national hockey league', 'college football', 'college basketball',
        'premier league', 'la liga', 'serie a', 'bundesliga', 'ligue 1', 'major league soccer',
        'championship', 'league one', 'league two', 'national league', 'conference',
        'eredivisie', 'primeira liga', 'liga mx', 'a-league', 'j-league', 'k-league',
        'liga profesional', 'brasileirão', 'ligue 2', 'serie b', '2. bundesliga',
        'scottish premiership', 'scottish championship', 'scottish league one',
        'welsh premier league', 'northern ireland football league',
        'belgian pro league', 'swiss super league', 'austrian bundesliga',
        'danish superliga', 'norwegian eliteserien', 'swedish allsvenskan',
        'finnish veikkausliiga', 'icelandic úrvalsdeild', 'russian premier league',
        'ukrainian premier league', 'turkish süper lig', 'greek super league',
        'croatian first football league', 'serbian superliga', 'bulgarian first league',
        'romanian liga i', 'czech first league', 'hungarian nemzeti bajnokság',
        'slovak super liga', 'slovenian prvaliga', 'polish ekstraklasa',
        'portuguese primeira liga', 'spanish la liga', 'italian serie a',
        'german bundesliga', 'french ligue 1', 'english premier league',
        'dutch eredivisie', 'belgian first division a', 'tipico bundesliga',
        
        # Countries (full names)
        'denmark', 'iceland', 'finland', 'russia', 'germany', 'france', 'italy', 'spain',
        'england', 'scotland', 'wales', 'northern ireland', 'ireland', 'netherlands',
        'belgium', 'switzerland', 'austria', 'norway', 'sweden', 'poland', 'czech republic',
        'slovakia', 'slovenia', 'croatia', 'serbia', 'bulgaria', 'romania', 'hungary',
        'ukraine', 'turkey', 'greece', 'portugal', 'brazil', 'argentina', 'mexico',
        'united states', 'canada', 'australia', 'japan', 'south korea', 'korea republic', 'republic of korea', 'china', 'china pr',
        'india', 'indonesia', 'malaysia', 'thailand', 'vietnam', 'philippines', 'singapore',
        'myanmar', 'cambodia', 'laos', 'brunei', 'timor-leste',
        'taiwan', 'chinese taipei', 'hong kong', 'macau',
        'belarus', 'moldova', 'georgia', 'armenia', 'azerbaijan',
        'kazakhstan', 'uzbekistan', 'kyrgyzstan', 'tajikistan', 'turkmenistan',
        'lithuania', 'latvia', 'estonia',
        'south africa', 'new zealand', 'egypt', 'morocco', 'algeria', 'tunisia',
        'nigeria', 'kenya', 'ethiopia', 'ghana', 'senegal', 'ivory coast', 'cameroon',
        'zambia', 'zimbabwe', 'uganda', 'tanzania', 'angola', 'mozambique', 'sudan',
        'south sudan', 'democratic republic of the congo', 'republic of the congo',
        'madagascar', 'botswana', 'namibia', 'lesotho', 'eswatini', 'malawi', 'rwanda',
        'burundi', 'somalia', 'eritrea', 'djibouti', 'seychelles', 'mauritius', 'comoros',
        'cape verde', 'sao tome and principe', 'gambia', 'guinea', 'guinea-bissau',
        'sierra leone', 'liberia', 'mali', 'niger', 'chad', 'central african republic',
        'gabon', 'equatorial guinea', 'benin', 'togo', 'burkina faso', 'mauritania',
        'uruguay', 'colombia', 'peru', 'poland', 'austria',
        'costa rica', 'venezuela', 'ecuador', 'paraguay', 'bolivia', 'chile',
        'panama', 'honduras', 'guatemala', 'el salvador', 'nicaragua', 'cuba',
        'dominican republic', 'puerto rico', 'jamaica', 'haiti', 'belize',
        'guyana', 'suriname', 'trinidad and tobago', 'barbados',
        # Middle East / Central Asia (these were missing — POD concatenates without space)
        'qatar', 'israel', 'saudi arabia', 'uae', 'united arab emirates',
        'jordan', 'kuwait', 'bahrain', 'oman', 'lebanon', 'syria', 'iraq', 'iran',
        'palestine', 'west bank', 'gaza', 'yemen', 'libya', 'afghanistan', 'pakistan',
        'cyprus', 'malta', 'luxembourg', 'andorra', 'monaco', 'liechtenstein',
        'san marino', 'kosovo', 'north macedonia', 'albania', 'bosnia', 'bosnia and herzegovina',
        'montenegro', 'moldova', 'north korea',
        
        # Country abbreviations (3-letter codes)
        'cyp', 'cyprus',
        'den', 'isl', 'fin', 'rus', 'ger', 'fra', 'ita', 'esp', 'eng', 'sco', 'wal',
        'nir', 'irl', 'ned', 'bel', 'sui', 'aut', 'nor', 'swe', 'pol', 'cze', 'svk',
        'slo', 'cro', 'srb', 'bul', 'rou', 'hun', 'ukr', 'tur', 'gre', 'por', 'bra',
        'arg', 'mex', 'usa', 'can', 'aus', 'jpn', 'kor', 'chn', 'ind', 'zaf', 'nzl',
        'egy', 'mar', 'dza', 'tun', 'nga', 'ken', 'eth', 'gha', 'sen', 'civ', 'cmr',
        'zmb', 'zwe', 'uga', 'tza', 'ago', 'moz', 'sdn', 'ssd', 'cod', 'cog', 'mdg',
        'bwa', 'nam', 'lso', 'swz', 'mwi', 'rwa', 'bdi', 'som', 'eri', 'dji', 'syc',
        'mus', 'com', 'cpv', 'stp', 'gmb', 'gin', 'gnb', 'sle', 'lbr', 'mli', 'ner',
        'tcd', 'caf', 'gab', 'gnq', 'ben', 'tgo', 'bfa', 'mrt',
        
        # Regional/League indicators
        'uefa', 'conmebol', 'concacaf', 'caf', 'afc', 'ofc', 'fifa',
        'uefa champions league', 'uefa europa league', 'uefa conference league',
        'copa libertadores', 'copa sudamericana', 'concacaf champions league',
        'afc champions league', 'caf champions league', 'ofc champions league',
        'fifa club world cup', 'uefa nations league', 'copa américa', 'gold cup',
        'african cup of nations', 'asian cup', 'oceania nations cup', 'european championship',
        'world cup', 'olympics', 'olympic games', 'summer olympics', 'winter olympics',
        'paralympics', 'youth olympics', 'commonwealth games', 'pan american games',
        'asian games', 'african games', 'mediterranean games', 'baltic games',
        'nordic games', 'balkan games', 'caribbean games', 'central american games',
        'south american games', 'pacific games', 'indian ocean games', 'arctic games',
        'island games', 'microstate games', 'small states games',
        
        # Legacy entries
        'liga 1', 'epl'
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
    norm_name = re.sub(r'^[^\w]+|[^\w]+$', '', norm_name) 
    norm_name = re.sub(r'[^\w\s\.\-\+]', '', norm_name) 
    final_normalized_name = " ".join(norm_name.split()).strip() 
    return final_normalized_name if final_normalized_name else (original_name_for_debug.lower().strip() if original_name_for_debug else "")

def clean_pod_team_name_for_search(name: str) -> str:
    """Clean team name for search by removing common suffixes and normalizing."""
    print(f"[DEBUG] clean_pod_team_name_for_search input: '{name}'")
    result = normalize_team_name_for_matching(name)
    print(f"[DEBUG] clean_pod_team_name_for_search output: '{result}'")
    return result

def strip_team_name_for_display(name: str) -> str:
    """Strip country/league suffix from a POD team name, preserving original casing.

    Handles all POD concatenation patterns:
      'SionSwitzerland'                      → 'Sion'
      'HeredianoCosta Rica'                  → 'Herediano'
      'Orange CountyUSA - USL Championship'  → 'Orange County'
      'CeutaSpain - Segunda Division'        → 'Ceuta'
      'Taila SantosPFL'                      → 'Taila Santos'
    """
    if not name or name == "?":
        return name
    # Step 1: strip " - League/competition" trailer
    cleaned = re.sub(r'\s+-\s+.+$', '', name).strip()
    # Step 2: get the normalised (lowercase, suffix-stripped) version
    stripped_lower = normalize_team_name_for_matching(cleaned)
    if not stripped_lower:
        return cleaned
    cleaned_lower = cleaned.lower()
    # Step 3: direct prefix match (most common case)
    if cleaned_lower.startswith(stripped_lower):
        return cleaned[:len(stripped_lower)].strip()
    # Step 4: normalize may have also stripped a leading club prefix (fc, sc…).
    # Try to recover the display name by locating stripped_lower after that prefix.
    common_prefixes = ['fc ', 'sc ', 'bk ', 'sk ', 'ac ', 'as ', 'fk ', 'cd ', 'ca ', 'afc ']
    for pfx in common_prefixes:
        if cleaned_lower.startswith(pfx):
            remainder_lower = cleaned_lower[len(pfx):]
            if remainder_lower.startswith(stripped_lower):
                return cleaned[len(pfx):len(pfx) + len(stripped_lower)].strip()
    return cleaned

def normalize_total_line(line):
    if line is None:
        return None
    if isinstance(line, (int, float)):
        return float(line)
    line = str(line).replace('½','.5').replace(' ', '').replace(',', '.')
    # Handle Asian lines like '2.5,3' or '2.5/3'
    m = re.match(r'([0-9]+\.?[0-9]*)[,/ ]([0-9]+\.?[0-9]*)', line)
    if m:
        return (float(m.group(1)) + float(m.group(2))) / 2
    try:
        return float(line)
    except Exception:
        return None

def format_bet_description(market: str, selection: str, line: str, home_team: str = "", away_team: str = "") -> str:
    """Format bet description with proper team names and clean formatting"""
    if market == "Moneyline":
        if selection == "Home" and home_team:
            return f"ML - {home_team}"
        elif selection == "Away" and away_team:
            return f"ML - {away_team}"
        else:
            return f"ML - {selection}"
    elif market == "Spread":
        if selection == "Home" and home_team:
            return f"{home_team} {line}"
        elif selection == "Away" and away_team:
            return f"{away_team} {line}"
        else:
            return f"{selection} {line}"
    elif market == "Total":
        if selection == "Over":
            return f"Over {line}"
        elif selection == "Under":
            return f"Under {line}"
        else:
            return f"{selection} {line}"
    else:
        return f"{market} - {selection}"


def _validate_period_separation(bet_data: Dict, pinnacle_data: Dict) -> bool:
    """
    Validate that we're not mixing full game and 1H data.
    Returns True if separation is correct, False if there's a problem.
    
    CRITICAL: This validation ensures data integrity before EV calculation.
    """
    try:
        if not bet_data or not pinnacle_data:
            logger.warning("[PeriodValidation] Missing bet_data structures")
            return False
        
        # Check if we have 1H data in BetBCK
        bet_1h_data = bet_data.get('1H_data')
        has_1h_betbck = bool(bet_1h_data and isinstance(bet_1h_data, dict))
        
        # Check if we have 1H data in Pinnacle
        pin_data = pinnacle_data.get('data', {})
        if not isinstance(pin_data, dict):
            logger.warning("[PeriodValidation] Pinnacle data is not a dict")
            return False
            
        periods = pin_data.get('periods', {})
        if not isinstance(periods, dict):
            logger.warning("[PeriodValidation] Pinnacle periods is not a dict")
            return False
        
        first_half = periods.get('num_1') or periods.get('1')
        has_1h_pinnacle = bool(first_half and isinstance(first_half, dict))
        
        # Check if we have full game data in Pinnacle
        full_game = periods.get('num_0') or periods.get('0')
        has_full_game_pinnacle = bool(full_game and isinstance(full_game, dict))
        
        # Log the validation
        logger.info(f"[PeriodValidation] BetBCK 1H: {has_1h_betbck}, Pinnacle 1H: {has_1h_pinnacle}, Pinnacle Full: {has_full_game_pinnacle}")
        
        # CRITICAL: We must have full game data to proceed
        if not has_full_game_pinnacle:
            logger.error("[PeriodValidation] ERROR: No full game Pinnacle data found - cannot proceed with EV calculation!")
            return False
        
        # If we have 1H data, validate it's properly structured
        if has_1h_betbck:
            if not has_1h_pinnacle:
                logger.warning("[PeriodValidation] WARNING: Have 1H BetBCK data but no 1H Pinnacle data - 1H markets will be skipped")
            elif not isinstance(bet_1h_data, dict):
                logger.error("[PeriodValidation] ERROR: BetBCK 1H data is not a dict!")
                return False
        
        # Validate that period 0 (full game) contains expected market structure
        if has_full_game_pinnacle:
            if not (full_game.get('money_line') or full_game.get('spreads') or full_game.get('totals')):
                logger.error("[PeriodValidation] ERROR: Full game Pinnacle data missing expected market structure!")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"[PeriodValidation] Error validating period separation: {e}")
        import traceback
        logger.debug(f"[PeriodValidation] Traceback: {traceback.format_exc()}")
        return False


def _analyze_1h_markets_for_ev(bet_1h_data: Dict, pinnacle_1h_data: Dict, pin_data: Dict) -> List[Dict]:
    """
    Analyze 1H markets for expected value opportunities.
    CRITICAL: This function ONLY processes 1H data to prevent mixing with full game data.
    
    Validates period data and uses strict matching with break logic to prevent incorrect matches.
    """
    potential_bets = []
    
    try:
        # CRITICAL: Validate that we have valid 1H period data
        if not isinstance(pinnacle_1h_data, dict) or not pinnacle_1h_data:
            logger.warning("[1H-Analysis] Invalid or empty Pinnacle 1H data provided")
            return []
        
        if not isinstance(bet_1h_data, dict) or not bet_1h_data:
            logger.warning("[1H-Analysis] Invalid or empty BetBCK 1H data provided")
            return []
        
        # Verify this is actually 1H data by checking for expected structure
        if not (pinnacle_1h_data.get('money_line') or pinnacle_1h_data.get('spreads') or pinnacle_1h_data.get('totals')):
            logger.warning("[1H-Analysis] Pinnacle 1H data missing expected market structure")
            return []
        
        # Get team names from pinnacle data
        home_team = pin_data.get('home', '')
        away_team = pin_data.get('away', '')
        
        # --- 1H Moneyline ---
        pin_ml = pinnacle_1h_data.get('money_line', {})
        meta_limits = pinnacle_1h_data.get('meta', {})
        
        if bet_1h_data.get('home_moneyline_american') and pin_ml.get('nvp_american_home'):
            bet_odds = american_to_decimal(bet_1h_data['home_moneyline_american'])
            true_odds = pin_ml.get('nvp_home')
            if bet_odds and true_odds:
                ev = calculate_ev(bet_odds, true_odds)
                potential_bets.append({
                    'market': '1H Moneyline',
                    'selection': 'Home',
                    'line': '',
                    'pinnacle_nvp': pin_ml.get('nvp_american_home', 'N/A'),
                    'pinnacle_limit': pin_ml.get('max_money_line') or meta_limits.get('max_money_line'),
                    'betbck_odds': bet_1h_data['home_moneyline_american'],
                    'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                    'home_team': home_team,
                    'away_team': away_team,
                    'bet': format_bet_description('1H Moneyline', 'Home', '', home_team, away_team)
                })
        
        if bet_1h_data.get('away_moneyline_american') and pin_ml.get('nvp_american_away'):
            bet_odds = american_to_decimal(bet_1h_data['away_moneyline_american'])
            true_odds = pin_ml.get('nvp_away')
            if bet_odds and true_odds:
                ev = calculate_ev(bet_odds, true_odds)
                potential_bets.append({
                    'market': '1H Moneyline',
                    'selection': 'Away',
                    'line': '',
                    'pinnacle_nvp': pin_ml.get('nvp_american_away', 'N/A'),
                    'pinnacle_limit': pin_ml.get('max_money_line') or meta_limits.get('max_money_line'),
                    'betbck_odds': bet_1h_data['away_moneyline_american'],
                    'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                    'home_team': home_team,
                    'away_team': away_team,
                    'bet': format_bet_description('1H Moneyline', 'Away', '', home_team, away_team)
                })
        
        # --- 1H Spreads ---
        pin_spreads = pinnacle_1h_data.get('spreads', {})
        if not isinstance(pin_spreads, dict):
            pin_spreads = {}
        
        # Home spreads: Match BetBCK home spreads to Pinnacle 1H spreads
        for spread in bet_1h_data.get('home_spreads', []):
            bet_line = spread.get('line')
            if bet_line is None:
                continue
            
            matched = False
            for spread_key, pin_spread in pin_spreads.items():
                if not isinstance(pin_spread, dict):
                    continue
                    
                line = pin_spread.get('hdp')
                try:
                    # Match home spread: BetBCK line should match Pinnacle hdp
                    if line is not None and math.isclose(float(bet_line), float(line), abs_tol=0.01) and pin_spread.get('nvp_american_home'):
                        bet_odds = american_to_decimal(spread.get('odds'))
                        true_odds = pin_spread.get('nvp_home')
                        if bet_odds and true_odds:
                            ev = calculate_ev(bet_odds, true_odds)
                            potential_bets.append({
                                'market': '1H Spread',
                                'selection': 'Home',
                                'line': str(line),
                                'pinnacle_nvp': pin_spread.get('nvp_american_home', 'N/A'),
                                'pinnacle_limit': pin_spread.get('max') or meta_limits.get('max_spread'),
                                'betbck_odds': spread.get('odds'),
                                'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                                'home_team': home_team,
                                'away_team': away_team,
                                'bet': format_bet_description('1H Spread', 'Home', str(line), home_team, away_team)
                            })
                            matched = True
                            break  # CRITICAL: Break after finding first match to prevent duplicates
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"[1H-Analysis] Error matching home spread: {e}")
                    continue
            
            if matched:
                continue  # Move to next spread
        
        # Away spreads: Match BetBCK away spreads to Pinnacle 1H spreads (negated)
        for spread in bet_1h_data.get('away_spreads', []):
            bet_line = spread.get('line')
            if bet_line is None:
                continue
            
            matched = False
            for spread_key, pin_spread in pin_spreads.items():
                if not isinstance(pin_spread, dict):
                    continue
                    
                line = pin_spread.get('hdp')
                try:
                    # Match away spread: BetBCK line should match -Pinnacle hdp
                    if line is not None and math.isclose(float(bet_line), -float(line), abs_tol=0.01) and pin_spread.get('nvp_american_away'):
                        bet_odds = american_to_decimal(spread.get('odds'))
                        true_odds = pin_spread.get('nvp_away')
                        if bet_odds and true_odds:
                            ev = calculate_ev(bet_odds, true_odds)
                            potential_bets.append({
                                'market': '1H Spread',
                                'selection': 'Away',
                                'line': str(-line),
                                'pinnacle_nvp': pin_spread.get('nvp_american_away', 'N/A'),
                                'pinnacle_limit': pin_spread.get('max') or meta_limits.get('max_spread'),
                                'betbck_odds': spread.get('odds'),
                                'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                                'home_team': home_team,
                                'away_team': away_team,
                                'bet': format_bet_description('1H Spread', 'Away', str(-line), home_team, away_team)
                            })
                            matched = True
                            break  # CRITICAL: Break after finding first match to prevent duplicates
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"[1H-Analysis] Error matching away spread: {e}")
                    continue
            
            if matched:
                continue  # Move to next spread
        
        # --- 1H Totals ---
        pin_totals = pinnacle_1h_data.get('totals', {})
        if not isinstance(pin_totals, dict):
            pin_totals = {}

        # ── Primary path: game_total_line / game_total_over_odds / game_total_under_odds
        # (populated by _build_1h_data_dict in the scraper — exact Over/Under known)
        if bet_1h_data.get('game_total_line') is not None:
            bck_line = normalize_total_line(bet_1h_data['game_total_line'])
            for total_key, pin_total in pin_totals.items():
                if not isinstance(pin_total, dict):
                    continue
                pin_line = normalize_total_line(pin_total.get('points'))
                try:
                    if pin_line is not None and bck_line is not None and math.isclose(bck_line, pin_line, abs_tol=0.01):
                        # Over
                        if bet_1h_data.get('game_total_over_odds') and pin_total.get('nvp_american_over'):
                            bet_odds = american_to_decimal(bet_1h_data['game_total_over_odds'])
                            true_odds = pin_total.get('nvp_over')
                            if bet_odds and true_odds:
                                ev = calculate_ev(bet_odds, true_odds)
                                potential_bets.append({
                                    'market': '1H Total',
                                    'selection': 'Over',
                                    'line': str(pin_line),
                                    'pinnacle_nvp': pin_total.get('nvp_american_over', 'N/A'),
                                    'pinnacle_limit': pin_total.get('max') or meta_limits.get('max_total'),
                                    'betbck_odds': bet_1h_data['game_total_over_odds'],
                                    'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                                    'home_team': home_team,
                                    'away_team': away_team,
                                    'bet': format_bet_description('1H Total', 'Over', str(pin_line), home_team, away_team)
                                })
                        # Under
                        if bet_1h_data.get('game_total_under_odds') and pin_total.get('nvp_american_under'):
                            bet_odds = american_to_decimal(bet_1h_data['game_total_under_odds'])
                            true_odds = pin_total.get('nvp_under')
                            if bet_odds and true_odds:
                                ev = calculate_ev(bet_odds, true_odds)
                                potential_bets.append({
                                    'market': '1H Total',
                                    'selection': 'Under',
                                    'line': str(pin_line),
                                    'pinnacle_nvp': pin_total.get('nvp_american_under', 'N/A'),
                                    'pinnacle_limit': pin_total.get('max') or meta_limits.get('max_total'),
                                    'betbck_odds': bet_1h_data['game_total_under_odds'],
                                    'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                                    'home_team': home_team,
                                    'away_team': away_team,
                                    'bet': format_bet_description('1H Total', 'Under', str(pin_line), home_team, away_team)
                                })
                        break  # Only one Pinnacle line can match; stop searching
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"[1H-Analysis] Error matching game_total line: {e}")

        else:
            # ── Fallback path: home_totals/away_totals (legacy format)
            # home column = Over odds, away column = Under odds at the same line
            betbck_totals_ov: Dict[str, str] = {}  # line -> over_odds
            betbck_totals_un: Dict[str, str] = {}  # line -> under_odds
            for total in bet_1h_data.get('home_totals', []):
                line = total.get('line'); odds = total.get('odds')
                if line is not None and odds is not None:
                    betbck_totals_ov[str(line)] = odds
            for total in bet_1h_data.get('away_totals', []):
                line = total.get('line'); odds = total.get('odds')
                if line is not None and odds is not None:
                    betbck_totals_un[str(line)] = odds

            all_lines = set(betbck_totals_ov) | set(betbck_totals_un)
            for bet_line in all_lines:
                for total_key, pin_total in pin_totals.items():
                    if not isinstance(pin_total, dict):
                        continue
                    pin_line = normalize_total_line(pin_total.get('points'))
                    try:
                        if pin_line is not None and math.isclose(float(bet_line), pin_line, abs_tol=0.01):
                            # Over
                            if bet_line in betbck_totals_ov and pin_total.get('nvp_american_over'):
                                bet_odds = american_to_decimal(betbck_totals_ov[bet_line])
                                true_odds = pin_total.get('nvp_over')
                                if bet_odds and true_odds:
                                    ev = calculate_ev(bet_odds, true_odds)
                                    potential_bets.append({
                                        'market': '1H Total', 'selection': 'Over',
                                        'line': str(pin_line),
                                        'pinnacle_nvp': pin_total.get('nvp_american_over', 'N/A'),
                                        'pinnacle_limit': pin_total.get('max') or meta_limits.get('max_total'),
                                        'betbck_odds': betbck_totals_ov[bet_line],
                                        'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                                        'home_team': home_team, 'away_team': away_team,
                                        'bet': format_bet_description('1H Total', 'Over', str(pin_line), home_team, away_team)
                                    })
                            # Under
                            if bet_line in betbck_totals_un and pin_total.get('nvp_american_under'):
                                bet_odds = american_to_decimal(betbck_totals_un[bet_line])
                                true_odds = pin_total.get('nvp_under')
                                if bet_odds and true_odds:
                                    ev = calculate_ev(bet_odds, true_odds)
                                    potential_bets.append({
                                        'market': '1H Total', 'selection': 'Under',
                                        'line': str(pin_line),
                                        'pinnacle_nvp': pin_total.get('nvp_american_under', 'N/A'),
                                        'pinnacle_limit': pin_total.get('max') or meta_limits.get('max_total'),
                                        'betbck_odds': betbck_totals_un[bet_line],
                                        'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                                        'home_team': home_team, 'away_team': away_team,
                                        'bet': format_bet_description('1H Total', 'Under', str(pin_line), home_team, away_team)
                                    })
                            break
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.debug(f"[1H-Analysis] Error matching legacy total line {bet_line}: {e}")

        logger.info(f"[AnalyzeMarkets] Found {len(potential_bets)} 1H EV opportunities")
        return potential_bets
        
    except Exception as e:
        logger.error(f"[AnalyzeMarkets] Error analyzing 1H markets: {e}")
        return []


def analyze_markets_for_ev(bet_data: Dict, pinnacle_data: Dict) -> List[Dict]:
    """
    Analyze markets for expected value opportunities, matching the logic from PODBot:
    - Use processed Pinnacle data (with NVP and American odds fields)
    - Match BetBCK and Pinnacle by market type and line
    - Calculate EV using BetBCK American odds (converted to decimal) and Pinnacle NVP odds (decimal)
    - CRITICAL: Properly separate full game and 1H data to prevent mixing periods
    - Return all relevant info for frontend display
    """
    # Defensive copying to prevent race conditions and data mutation
    bet_data_copy = copy.deepcopy(bet_data) if bet_data else {}
    pinnacle_data_copy = copy.deepcopy(pinnacle_data) if pinnacle_data else {}
    
    potential_bets = []
    
    # CRITICAL: Validate period separation before processing
    if not _validate_period_separation(bet_data_copy, pinnacle_data_copy):
        logger.error("[AnalyzeMarkets] Period separation validation failed - aborting EV calculation")
        return potential_bets
    
    # Enhanced null checks
    if not pinnacle_data_copy:
        logger.info("[AnalyzeMarkets] No Pinnacle data available (None)")
        return potential_bets
    
    if not isinstance(pinnacle_data_copy, dict):
        logger.info(f"[AnalyzeMarkets] Pinnacle data is not a dict: {type(pinnacle_data_copy)}")
        return potential_bets
    
    # Check for 'data' key with better error handling
    if not pinnacle_data_copy.get('data'):
        logger.info("[AnalyzeMarkets] No 'data' key in Pinnacle data")
        return potential_bets
    
    # Additional check to ensure data is not None
    if pinnacle_data_copy['data'] is None:
        logger.info("[AnalyzeMarkets] Pinnacle data['data'] is None")
        return potential_bets
    
    try:
        pin_data = pinnacle_data_copy['data']
        
        # Additional null checks for pin_data
        if pin_data is None:
            logger.info("[AnalyzeMarkets] pin_data is None")
            return potential_bets
        
        if not isinstance(pin_data, dict):
            logger.info(f"[AnalyzeMarkets] pin_data is not a dict: {type(pin_data)}")
            return potential_bets
        
        periods = pin_data.get('periods', {})
        
        # Additional null checks for periods
        if periods is None:
            logger.info("[AnalyzeMarkets] periods is None")
            return potential_bets
        
        if not isinstance(periods, dict):
            logger.info(f"[AnalyzeMarkets] periods is not a dict: {type(periods)}")
            return potential_bets
        
        # Try both 'num_0' and '0' for period data
        full_game = periods.get('num_0') or periods.get('0')
        
        # Additional null checks for full_game
        if full_game is None:
            logger.info("[AnalyzeMarkets] full_game is None")
            return potential_bets
        
        if not isinstance(full_game, dict):
            logger.info(f"[AnalyzeMarkets] full_game is not a dict: {type(full_game)}")
            return potential_bets
        
        if not full_game:
            logger.error(f"[AnalyzeMarkets] No 'num_0' or '0' period found in periods: {periods}")
            return []
        
        # --- Moneyline ---
        ml = full_game.get('money_line', {})
        meta_limits = full_game.get('meta') if isinstance(full_game.get('meta'), dict) else {}
        
        # Additional null checks for moneyline
        if ml is None:
            logger.info("[AnalyzeMarkets] money_line is None")
            ml = {}
        elif not isinstance(ml, dict):
            logger.info(f"[AnalyzeMarkets] money_line is not a dict: {type(ml)}")
            ml = {}

        # Detect home/away NVP mismatch: POD extension sometimes sends teams in
        # reversed order vs Pinnacle. BetBCK scraper already corrects its own side
        # via bck_local_is_pod_home, but Pinnacle NVP sides must also be flipped.
        _nvp_swapped = False
        _pod_home_norm = normalize_team_name_for_matching(bet_data_copy.get('pod_home_team', ''))
        _pin_home_norm = normalize_team_name_for_matching(pin_data.get('home', ''))
        _pin_away_norm = normalize_team_name_for_matching(pin_data.get('away', ''))
        if _pod_home_norm and _pin_home_norm and _pin_away_norm:
            if fuzz:
                _h_score = fuzz.ratio(_pod_home_norm, _pin_home_norm)
                _a_score = fuzz.ratio(_pod_home_norm, _pin_away_norm)
            else:
                _h_score = 100 if _pod_home_norm == _pin_home_norm else 0
                _a_score = 100 if _pod_home_norm == _pin_away_norm else 0
            # Only swap when we are very confident teams are genuinely reversed:
            # 1. POD home clearly matches Pinnacle away (score >= 80)
            # 2. POD home clearly does NOT match Pinnacle home (score < 50)
            # 3. Away score leads home score by a large margin (>= 30 pts)
            # This prevents accidental flips for teams with similar names.
            if _a_score >= 80 and _h_score < 50 and (_a_score - _h_score) >= 30:
                _nvp_swapped = True
                logger.warning(
                    f"[AnalyzeMarkets] NVP home/away swap (high confidence): "
                    f"POD home '{bet_data_copy.get('pod_home_team')}' "
                    f"matches Pinnacle away '{pin_data.get('away')}' (score {_a_score}) "
                    f"vs Pinnacle home '{pin_data.get('home')}' (score {_h_score}) "
                    f"— swapping NVP sides"
                )
                ml['nvp_home'], ml['nvp_away'] = ml.get('nvp_away'), ml.get('nvp_home')
                ml['nvp_american_home'], ml['nvp_american_away'] = ml.get('nvp_american_away'), ml.get('nvp_american_home')

        if bet_data_copy.get('home_moneyline_american') and ml.get('nvp_american_home'):
            bet_odds = american_to_decimal(bet_data_copy['home_moneyline_american'])
            true_odds = ml.get('nvp_home')
            if bet_odds and true_odds:
                ev = calculate_ev(bet_odds, true_odds)
                # Get team names from pinnacle data
                home_team = pin_data.get('home', '')
                away_team = pin_data.get('away', '')
                potential_bets.append({
                    'market': 'Moneyline',
                    'selection': 'Home',
                    'line': '',
                    'pinnacle_nvp': ml.get('nvp_american_home', 'N/A'),
                    'pinnacle_limit': ml.get('max_money_line') or meta_limits.get('max_money_line') or meta_limits.get('max_spread') or meta_limits.get('max_total'),
                    'betbck_odds': bet_data_copy['home_moneyline_american'],
                    'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                    'home_team': home_team,
                    'away_team': away_team,
                    'bet': format_bet_description('Moneyline', 'Home', '', home_team, away_team)
                })
            
        if bet_data_copy.get('away_moneyline_american') and ml.get('nvp_american_away'):
            bet_odds = american_to_decimal(bet_data_copy['away_moneyline_american'])
            true_odds = ml.get('nvp_away')
            if bet_odds and true_odds:
                ev = calculate_ev(bet_odds, true_odds)
                # Get team names from pinnacle data
                home_team = pin_data.get('home', '')
                away_team = pin_data.get('away', '')
                potential_bets.append({
                    'market': 'Moneyline',
                    'selection': 'Away',
                    'line': '',
                    'pinnacle_nvp': ml.get('nvp_american_away', 'N/A'),
                    'pinnacle_limit': ml.get('max_money_line') or meta_limits.get('max_money_line') or meta_limits.get('max_spread') or meta_limits.get('max_total'),
                    'betbck_odds': bet_data_copy['away_moneyline_american'],
                    'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                    'home_team': home_team,
                    'away_team': away_team,
                    'bet': format_bet_description('Moneyline', 'Away', '', home_team, away_team)
                })
            
        if bet_data_copy.get('draw_moneyline_american') and ml.get('nvp_american_draw'):
            bet_odds = american_to_decimal(bet_data_copy['draw_moneyline_american'])
            true_odds = ml.get('nvp_draw')
            if bet_odds and true_odds:
                ev = calculate_ev(bet_odds, true_odds)
                # Get team names from pinnacle data
                home_team = pin_data.get('home', '')
                away_team = pin_data.get('away', '')
                potential_bets.append({
                    'market': 'Moneyline',
                    'selection': 'Draw',
                    'line': '',
                    'pinnacle_nvp': ml.get('nvp_american_draw', 'N/A'),
                    'pinnacle_limit': ml.get('max_money_line') or meta_limits.get('max_money_line') or meta_limits.get('max_spread') or meta_limits.get('max_total'),
                    'betbck_odds': bet_data_copy['draw_moneyline_american'],
                    'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                    'home_team': home_team,
                    'away_team': away_team,
                    'bet': format_bet_description('Moneyline', 'Draw', '', home_team, away_team)
                })

        # --- Spreads ---
        pin_spreads = full_game.get('spreads')
        if not isinstance(pin_spreads, dict):
            pin_spreads = {}

        # Apply the same home/away NVP swap to each spread entry if teams are reversed
        if _nvp_swapped:
            for _sk, _sp in pin_spreads.items():
                if isinstance(_sp, dict):
                    _sp['nvp_home'], _sp['nvp_away'] = _sp.get('nvp_away'), _sp.get('nvp_home')
                    _sp['nvp_american_home'], _sp['nvp_american_away'] = _sp.get('nvp_american_away'), _sp.get('nvp_american_home')

        for spread_key, pin_spread in pin_spreads.items():
            line = pin_spread.get('hdp')
            
            # Home
            for s in bet_data_copy.get('home_spreads', []):
                bet_line = s.get('line')
                try:
                    if bet_line is not None and line is not None and math.isclose(float(bet_line), float(line), abs_tol=0.01) and pin_spread.get('nvp_american_home'):
                        bet_odds = american_to_decimal(s.get('odds'))
                        true_odds = pin_spread.get('nvp_home')
                        if bet_odds and true_odds:
                            ev = calculate_ev(bet_odds, true_odds)
                            # Get team names from pinnacle data
                            home_team = pin_data.get('home', '')
                            away_team = pin_data.get('away', '')
                            potential_bets.append({
                                'market': 'Spread',
                                'selection': 'Home',
                                'line': str(line),
                                'pinnacle_nvp': pin_spread.get('nvp_american_home', 'N/A'),
                                'pinnacle_limit': pin_spread.get('max') or meta_limits.get('max_spread'),
                                'betbck_odds': s.get('odds'),
                                'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                                'home_team': home_team,
                                'away_team': away_team,
                                'bet': format_bet_description('Spread', 'Home', str(line), home_team, away_team)
                            })
                except Exception as e:
                    continue
            
            # Away
            for s in bet_data_copy.get('away_spreads', []):
                bet_line = s.get('line')
                try:
                    if bet_line is not None and line is not None and math.isclose(float(bet_line), -float(line), abs_tol=0.01) and pin_spread.get('nvp_american_away'):
                        bet_odds = american_to_decimal(s.get('odds'))
                        true_odds = pin_spread.get('nvp_away')
                        if bet_odds and true_odds:
                            ev = calculate_ev(bet_odds, true_odds)
                            # Get team names from pinnacle data
                            home_team = pin_data.get('home', '')
                            away_team = pin_data.get('away', '')
                            potential_bets.append({
                                'market': 'Spread',
                                'selection': 'Away',
                                'line': str(-line),
                                'pinnacle_nvp': pin_spread.get('nvp_american_away', 'N/A'),
                                'pinnacle_limit': pin_spread.get('max') or meta_limits.get('max_spread'),
                                'betbck_odds': s.get('odds'),
                                'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                                'home_team': home_team,
                                'away_team': away_team,
                                'bet': format_bet_description('Spread', 'Away', str(-line), home_team, away_team)
                            })
                except Exception as e:
                    continue

        # --- Totals ---
        pin_totals = full_game.get('totals')
        if not isinstance(pin_totals, dict):
            pin_totals = {}
        
        # Gather all BetBCK total lines/odds
        betbck_totals = []
        if bet_data_copy.get('game_total_line') is not None:
            betbck_totals.append({
                'line': normalize_total_line(bet_data_copy.get('game_total_line')),
                'over_odds': bet_data_copy.get('game_total_over_odds'),
                'under_odds': bet_data_copy.get('game_total_under_odds')
            })
        
        best_over = None
        best_under = None
        for bck_total in betbck_totals:
            bck_line = bck_total['line']
            for total_key, pin_total in pin_totals.items():
                pin_line = normalize_total_line(pin_total.get('points'))
                if bck_line is not None and pin_line is not None and math.isclose(bck_line, pin_line, abs_tol=0.01):
                    # Over
                    if bck_total['over_odds'] and pin_total.get('nvp_american_over'):
                        bet_odds = american_to_decimal(bck_total['over_odds'])
                        true_odds = pin_total.get('nvp_over')
                        if bet_odds and true_odds:
                            ev = calculate_ev(bet_odds, true_odds)
                            if best_over is None or (ev is not None and ev > best_over['ev_val']):
                                # Get team names from pinnacle data
                                home_team = pin_data.get('home', '')
                                away_team = pin_data.get('away', '')
                                best_over = {
                                    'market': 'Total',
                                    'selection': 'Over',
                                    'line': str(pin_line),
                                    'pinnacle_nvp': pin_total.get('nvp_american_over', 'N/A'),
                                    'pinnacle_limit': pin_total.get('max') or meta_limits.get('max_total'),
                                    'betbck_odds': bck_total['over_odds'],
                                    'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                                    'ev_val': ev,
                                    'home_team': home_team,
                                    'away_team': away_team,
                                    'bet': format_bet_description('Total', 'Over', str(pin_line), home_team, away_team)
                                }
                    # Under
                    if bck_total['under_odds'] and pin_total.get('nvp_american_under'):
                        bet_odds = american_to_decimal(bck_total['under_odds'])
                        true_odds = pin_total.get('nvp_under')
                        if bet_odds and true_odds:
                            ev = calculate_ev(bet_odds, true_odds)
                            if best_under is None or (ev is not None and ev > best_under['ev_val']):
                                # Get team names from pinnacle data
                                home_team = pin_data.get('home', '')
                                away_team = pin_data.get('away', '')
                                best_under = {
                                    'market': 'Total',
                                    'selection': 'Under',
                                    'line': str(pin_line),
                                    'pinnacle_nvp': pin_total.get('nvp_american_under', 'N/A'),
                                    'pinnacle_limit': pin_total.get('max') or meta_limits.get('max_total'),
                                    'betbck_odds': bck_total['under_odds'],
                                    'ev': f"{ev*100:.2f}%" if ev is not None else 'N/A',
                                    'ev_val': ev,
                                    'home_team': home_team,
                                    'away_team': away_team,
                                    'bet': format_bet_description('Total', 'Under', str(pin_line), home_team, away_team)
                                }
        # Add best totals to potential bets
        if best_over:
            del best_over['ev_val']
            potential_bets.append(best_over)
        if best_under:
            del best_under['ev_val']
            potential_bets.append(best_under)
        
        # --- 1H DATA PROCESSING (CRITICAL: Separate from full game) ---
        if bet_data_copy.get('1H_data'):
            logger.info("[AnalyzeMarkets] Processing 1H data separately from full game data")
            first_half = periods.get('num_1') or periods.get('1')
            
            if first_half and isinstance(first_half, dict):
                logger.info("[AnalyzeMarkets] Found 1H Pinnacle data, processing 1H BetBCK data")
                # Apply the same home/away NVP swap to 1H period if teams are reversed
                if _nvp_swapped:
                    first_half = copy.deepcopy(first_half)
                    _1h_ml = first_half.get('money_line')
                    if isinstance(_1h_ml, dict):
                        _1h_ml['nvp_home'], _1h_ml['nvp_away'] = _1h_ml.get('nvp_away'), _1h_ml.get('nvp_home')
                        _1h_ml['nvp_american_home'], _1h_ml['nvp_american_away'] = _1h_ml.get('nvp_american_away'), _1h_ml.get('nvp_american_home')
                    for _sk, _sp in (first_half.get('spreads') or {}).items():
                        if isinstance(_sp, dict):
                            _sp['nvp_home'], _sp['nvp_away'] = _sp.get('nvp_away'), _sp.get('nvp_home')
                            _sp['nvp_american_home'], _sp['nvp_american_away'] = _sp.get('nvp_american_away'), _sp.get('nvp_american_home')
                potential_bets.extend(_analyze_1h_markets_for_ev(bet_data_copy['1H_data'], first_half, pin_data))
            else:
                logger.warning("[AnalyzeMarkets] No 1H Pinnacle data found, skipping 1H BetBCK data")
        else:
            logger.info("[AnalyzeMarkets] No 1H BetBCK data found")
        
        return potential_bets
    
    except Exception as e:
        logger.error(f"[AnalyzeMarkets] Error analyzing markets: {e}")
        return []

# ── Multi-row EV analysis ─────────────────────────────────────────────────────

# Maps BetBCK row_type → Pinnacle period key
_ROW_TYPE_TO_PERIOD = {
    "full_game": "num_0",
    "alt_line":  "num_0",
    "reg_time":  "num_0",
    "period_1":  "num_1",
    "half_1":    "num_1",
    "period_2":  "num_2",
    "half_2":    "num_2",
    "period_3":  "num_3",
}

# Human-readable prefix added to market labels for non-full-game rows
_ROW_TYPE_LABEL = {
    "alt_line": "Alt ",
    "period_1": "1P ",
    "half_1":   "1H ",
    "period_2": "2P ",
    "half_2":   "2H ",
    "period_3": "3P ",
    "reg_time": "RT ",
}


def analyze_markets_multi_row(bet_data: Dict, pinnacle_data: Dict) -> List[Dict]:
    """
    Analyze EV across ALL BetBCK row types collected in bet_data['row_data'].
    Falls back to analyze_markets_for_ev() when row_data is absent (backward compat).

    Row-type → Pinnacle period mapping:
      full_game / alt_line / reg_time → num_0
      period_1  / half_1              → num_1
      period_2  / half_2              → num_2
      period_3                        → num_3

    Each non-full-game row gets its market labels prefixed (e.g. "1P Spread").
    """
    row_data = bet_data.get("row_data") if isinstance(bet_data, dict) else None
    if not row_data:
        return analyze_markets_for_ev(bet_data, pinnacle_data)

    if not pinnacle_data or not isinstance(pinnacle_data.get("data"), dict):
        return analyze_markets_for_ev(bet_data, pinnacle_data)

    pin_data = pinnacle_data["data"]
    periods = pin_data.get("periods") or {}
    if not isinstance(periods, dict):
        periods = {}

    all_bets: List[Dict] = []

    # 1. Full-game row — ONLY when primary is actually the full_game entry.
    #
    #    If row_data has no "full_game" key, primary was set via date/index fallback
    #    and could be a period row (e.g. "period_1").  Calling analyze_markets_for_ev
    #    on that data with the real Pinnacle feed would compare period-specific spreads
    #    against Pinnacle num_0 (full-game) — exactly the cross-period contamination
    #    we must prevent.  In that case every row is handled safely by step 2 below.
    if "full_game" in row_data:
        step1_bets = analyze_markets_for_ev(bet_data, pinnacle_data)
        for bet in step1_bets:
            mkt = bet.get("market", "")
            if mkt.startswith("1H ") or mkt in ("1H Moneyline", "1H Spread", "1H Total"):
                bet["pinnacle_period"] = "num_1"
            else:
                bet["pinnacle_period"] = "num_0"
        all_bets.extend(step1_bets)
        logger.debug("[MultiRow] Step 1: full_game row processed via analyze_markets_for_ev")
    else:
        logger.warning(
            f"[MultiRow] No full_game match in row_data {list(row_data.keys())} — "
            "skipping step 1 to avoid cross-period contamination; "
            "all rows will be handled by per-period loop"
        )

    # 2. Additional row types — wrap the target Pinnacle period as "num_0" and re-run
    SKIP_TYPES = {"full_game"}  # full_game already handled in step 1 above
    # half_1 is handled inside analyze_markets_for_ev (via _analyze_1h_markets_for_ev)
    # ONLY when full_game was also present in row_data (step 1 ran).
    # If full_game is absent, half_1 was never processed — do NOT skip it here or the
    # 1H data is silently discarded.  Let step 2 compare it against Pinnacle num_1.
    if "full_game" in row_data and bet_data.get("1H_data"):
        SKIP_TYPES = SKIP_TYPES | {"half_1"}

    for row_type, row_bet_data in row_data.items():
        if row_type in SKIP_TYPES:
            continue

        period_key = _ROW_TYPE_TO_PERIOD.get(row_type)
        if not period_key:
            continue

        # Get the Pinnacle period data; support both "num_N" and "N" key formats
        period_pin = periods.get(period_key) or periods.get(period_key.replace("num_", ""))
        if not period_pin or not isinstance(period_pin, dict):
            logger.info(f"[MultiRow] No Pinnacle data for {row_type} ({period_key}) — skipping")
            continue

        # Re-wrap: make this period look like the full-game period to reuse existing logic
        fake_pinnacle = {
            "data": {
                **pin_data,
                "periods": {"num_0": period_pin},
            }
        }

        try:
            period_bets = analyze_markets_for_ev(row_bet_data, fake_pinnacle)

            # reg_time is BetBCK's 2-way (home/away) regulation-only market.
            # Pinnacle's num_0 for soccer is 3-way (home/draw/away), so its NVP for
            # home and away already absorbs the draw probability into the vig.
            # Comparing a 2-way ML against that NVP overstates EV — drop ML here.
            if row_type == "reg_time":
                before = len(period_bets)
                period_bets = [b for b in period_bets if b.get("market") != "Moneyline"]
                dropped = before - len(period_bets)
                if dropped:
                    logger.info(
                        f"[MultiRow] reg_time: dropped {dropped} Moneyline bet(s) "
                        "(2-way BetBCK vs 3-way Pinnacle NVP is invalid)"
                    )

            label = _ROW_TYPE_LABEL.get(row_type, "")
            for bet in period_bets:
                if label:
                    bet["market"] = f"{label}{bet['market']}"
                bet["row_type"] = row_type
                bet["pinnacle_period"] = period_key
            if period_bets:
                logger.info(f"[MultiRow] {row_type}: +{len(period_bets)} markets (Pinnacle period: {period_key})")
            all_bets.extend(period_bets)
        except Exception as exc:
            logger.error(f"[MultiRow] Error analyzing {row_type}: {exc}")

    # Stamp full_game bets with their row_type too
    for bet in all_bets:
        if "row_type" not in bet:
            bet["row_type"] = "full_game"

    # Deduplicate: same (market, selection, line) can only appear once
    seen: set = set()
    deduped: List[Dict] = []
    for bet in all_bets:
        key = (bet.get("market", ""), bet.get("selection", ""), str(bet.get("line", "")))
        if key not in seen:
            seen.add(key)
            deduped.append(bet)
        else:
            logger.debug(f"[MultiRow] Dedup dropped duplicate: {key}")

    return deduped


skip_indicators = ["1H", "1st Half", "First Half", "1st 5 Innings", "First Five Innings", "1st Period", "2nd Period", "3rd Period", "hits+runs+errors", "h+r+e", "hre", "corners", "series"]
prop_keywords = ['(Corners)', '(Bookings)', '(Hits+Runs+Errors)']

def is_prop_or_corner_alert(home_team, away_team):
    for keyword in prop_keywords:
        if keyword.lower() in home_team.lower() or keyword.lower() in away_team.lower():
            return True
    for ind in skip_indicators:
        if ind.lower() in home_team.lower() or ind.lower() in away_team.lower():
            return True
    return False

def fuzzy_team_match(team1, team2):
    if not fuzz:
        return normalize_team_name_for_matching(team1) == normalize_team_name_for_matching(team2)
    t1 = normalize_team_name_for_matching(team1)
    t2 = normalize_team_name_for_matching(team2)
    score = fuzz.token_set_ratio(t1, t2)
    return score >= FUZZY_MATCH_THRESHOLD

def calculate_name_similarity(team1, team2):
    """Calculate similarity score between two team names (0-1)."""
    if not fuzz:
        # Fallback to exact match if fuzzywuzzy is not available
        return 1.0 if normalize_team_name_for_matching(team1) == normalize_team_name_for_matching(team2) else 0.0
    t1 = normalize_team_name_for_matching(team1)
    t2 = normalize_team_name_for_matching(team2)
    score = fuzz.token_set_ratio(t1, t2)
    return score / 100.0  # Convert to 0-1 scale

def get_team_aliases(team_name):
    """Get aliases for a team name."""
    normalized_name = normalize_team_name_for_matching(team_name).lower()
    
    # Check if the team name is in our aliases dictionary
    if normalized_name in TEAM_ALIASES:
        return TEAM_ALIASES[normalized_name]
    
    # Check if the team name is an alias of another team
    for main_name, aliases in TEAM_ALIASES.items():
        if normalized_name in [alias.lower() for alias in aliases]:
            return [main_name] + aliases
    
    return [team_name]  # Return the original name if no aliases found 

def determine_betbck_search_term(pod_home_team_raw, pod_away_team_raw):
    # Clean team names FIRST before determining search term - use clean_pod_team_name_for_search to remove UEFA suffixes
    pod_home_clean = clean_pod_team_name_for_search(pod_home_team_raw)
    pod_away_clean = clean_pod_team_name_for_search(pod_away_team_raw)

    known_terms = {
        "south korea": "Korea", "faroe islands": "Faroe", "milwaukee brewers": "Brewers",
        "philadelphia phillies": "Phillies", "los angeles angels": "Angels", "pittsburgh pirates": "Pirates",
        "arizona diamondbacks": "Diamondbacks", "san diego padres": "Padres", "italy": "Italy",
        "st. louis cardinals": "Cardinals", "china pr": "China", "bahrain": "Bahrain", "czechia": "Czech Republic",
        "athletic club": "Athletic Club", "romania": "Romania", "cyprus": "Cyprus"
    }
    if pod_home_clean.lower() in known_terms:
        return known_terms[pod_home_clean.lower()]
    if pod_away_clean.lower() in known_terms:
        return known_terms[pod_away_clean.lower()]

    parts = pod_home_clean.split()
    if parts:
        if len(parts) > 1 and len(parts[-1]) > 3 and parts[-1].lower() not in ['fc', 'sc', 'united', 'city', 'club', 'de', 'do', 'ac', 'if', 'bk', 'aif', 'kc', 'sr', 'mg', 'us', 'br']:
            return parts[-1]
        elif len(parts[0]) > 2 and parts[0].lower() not in ['fc', 'sc', 'ac', 'if', 'bk', 'de', 'do', 'aif', 'kc', 'sr', 'mg', 'us', 'br']:
            return parts[0]
        else:
            return pod_home_clean
    return pod_home_clean if pod_home_clean else "" 

PROP_INDICATORS_IN_TEAM_NAMES = [
    "to lift the trophy", "lift the trophy", "mvp", "futures", "outright",
    "coach of the year", "player of the year", "series correct score",
    "when will series finish", "most points in series", "most assists in series",
    "most rebounds in series", "most threes made in series", "margin of victory",
    "exact outcome", "winner", "to win the tournament", "to win group", "series price",
    "(corners)"
]
def is_prop_market_by_name(home_team_name, away_team_name):
    if not home_team_name or not away_team_name: return False
    for name in [home_team_name, away_team_name]:
        name_lower = name.lower()
        for indicator in PROP_INDICATORS_IN_TEAM_NAMES:
            if indicator in name_lower: return True
    if "field" in away_team_name.lower() and "the" in away_team_name.lower(): return True
    if home_team_name.lower() == "yes" and away_team_name.lower() == "no": return True
    return False 