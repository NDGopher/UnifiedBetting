"""
🦈 Sharp Money Scanner - Production Grade
High-Frequency Sports Betting Arbitrage Detection
Context-Aware Parsing Engine
"""

import streamlit as st
import requests
import pandas as pd
import time
import sys
import logging
import uuid
import re
import base64
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from typing import List, Dict, Optional, Callable

# --- 🟢 LIFE SIGNS ---
print("--- 🟢 SCRIPT STARTING 🟢 ---")
logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger()

# --- 🔐 CREDENTIALS ---
KALSHI_KEY_ID = "4c67f48e-3c17-43e5-8eaa-8be0bf26ac37"
PRIVATE_KEY_BLOCK = """
-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAqMO3W9q3hIXHdKEvZ/J9q/hFvIiFdYOnpgcbOrM5+L26BDjM
7Ih1CKQT6mcQ627dvuQGMVFZbLBRf/xPS3Om0MuEF1AIAjApACYfQ/nqMVZZnR+u
ay+VOMLl917ryiJXXMsX8z+Zf2fkDzelonYYO/1djVCVF4HtUhHTbV9g7G0HuNG0
mdQTKdI1EU2KpJMZEIRIjJGS3y6GrV3GHT9NAy+WIUTJqUnBrAtBG96K+4OnekUt
ttiqPcWlpDirllt7UZB8KERK1PhOkLvE8hdLWb62Qx5vQdSYU0+gt4WDvx7B1tgH
JmUlDAyzfkAJhWgBHZF4WZEqCuJch6jaaq0mewIDAQABAoIBAAIohp2lr7dvco6R
t2+iLCNGv2xtHotA6Vr4E3Ck4v/phUB/JFM08LI6TvZS5kHH+nrfftHsEyEhJUdm
LITdgn3t9YYT8c0h7x1xzRTZCzqzurjO/HzGJyevHCBew6/H9PARS7eLrWS7BLGB
INOWW1b8fqyCIghHXBoOKk55ostDPhb0tDMo/xj93w7ZJHbrpfQVkXd2LakxC5sk
QN/nYMtmwPMEZT622TLrU2NtaSY2RaA2kks1Qqoq/DvKpQmrYGyOOdi6+/N3hT6Y
AwN/om2qtjwC6YmnVmOo9/GgGmpnDTWFh2AnLPlSrjVhJ+x9laXiJ+WHStrAaq8g
a2G77VkCgYEA3MjDLs/PP+Y9+NpRdaREl08orewWf7G1agZXX6BqHrtkpg+F6NLo
m/3PIz07gEywvYM4FaBkn889layuWHN0a8uXv9APLqTq2Jc8cJ/VYvqFcel8df7q
tjPiKfhf0icXVIYHqKSQ3a0d4uAYswIhdCFjRMjx9cF3Gq4MbTUtDx8CgYEAw67X
7sUovpXLdeWtW7ZmacBIPKFf5a91/QxMbYIfXP4O/J5cDgIz+BEfnfeGom0Gtpc2
6kCQtBST+5Ig9Ri9fhy/D05PhMVxHxu3IEjleEWRWa8ylUw+6aDpMxt2UQ1ZRZu5
4q8gmWy9TXrJQgaLqwlq9p4XNhsgunZxd2qCKSUCgYApUoIFfuuBQCyVKPdaF1an
Iy+v7aIAYFhd8bXktfdmrRgXZIxhmSfkGkrsg4dhafkiXy7eDVkH+BfErb8r2uAN
VNugEObmigNSamvrgF7F2bGkMlkTFJUFaQyJYm08vghFz5gbXkGm28HeNqcoydtN
CvqzYxC2OHF8UtsMjYlTbQKBgCRBzjKoh08g1C0JHGDk3/7yKLBLOkiFhTgYwkR8
GrGRRVebQ/U4hUaObaxIQ8LurpLAW+V1hxpGwdCYF9Ex/1JRozkDyooQR1B7QygR
OataQH88jgPJt9J0BSF6EicccRELtJqC1mh3FHA5svav3csYGKCPVD+rMRo7ffSh
YHKdAoGALIvT1Pc2e3k1vc3GhkNXKvHUs59DQTetBPupHpUy8DG50djN04OeG7dM
j3EW8ppWqWb9hIuBmhk4qg6zuTtoz8mu8zvC57gtfv+y2H9gcKTa9FL/XL644Tkh
homIQ9oXbpR/hpG1+t9b2EfUQfVLyYdFRr62EWZRwTVx3cy/je8=
-----END RSA PRIVATE KEY-----
"""

# --- 📦 IMPORTS ---
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

st.set_page_config(page_title="Sharp Money Scanner", layout="wide")

# --- 🔐 AUTH ---
class KalshiAuth(requests.auth.AuthBase):
    def __init__(self, key_id, private_key_str):
        self.key_id = key_id
        try:
            self.private_key = serialization.load_pem_private_key(
                private_key_str.strip().encode('utf-8'), password=None
            )
        except Exception: 
            st.error("❌ Key Error. Please paste your PRIVATE KEY in the code.")
            self.private_key = None

    def __call__(self, r):
        if not self.private_key: return r
        timestamp = str(int(time.time() * 1000))
        path = r.path_url.split("?")[0]
        msg = timestamp + r.method + path
        signature = self.private_key.sign(
            msg.encode('utf-8'),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256()
        )
        r.headers["KALSHI-ACCESS-KEY"] = self.key_id
        r.headers["KALSHI-ACCESS-TIMESTAMP"] = timestamp
        r.headers["KALSHI-ACCESS-SIGNATURE"] = base64.b64encode(signature).decode('utf-8')
        r.headers["Content-Type"] = "application/json"
        return r

kalshi_auth = KalshiAuth(KALSHI_KEY_ID, PRIVATE_KEY_BLOCK)

# --- 🏈 LEAGUE MAP (The Brain) ---

LEAGUE_MAP = {
    "NFL": ["Cowboys", "Lions", "Chiefs", "Ravens", "49ers", "Eagles", "Bills", "Bengals", "Giants", "Jets", "Patriots", "Dolphins", "Steelers", "Browns", "Packers", "Bears", "Vikings", "Broncos", "Raiders", "Chargers", "Seahawks", "Rams", "Cardinals", "Saints", "Buccaneers", "Falcons", "Panthers", "Jaguars", "Titans", "Colts", "Texans", "Commanders"],
    "NBA": ["Lakers", "Celtics", "Warriors", "Knicks", "Nets", "76ers", "Bucks", "Bulls", "Suns", "Mavericks", "Nuggets", "Heat", "Magic", "Clippers", "Kings", "Grizzlies", "Pelicans", "Jazz", "Thunder", "Spurs", "Rockets", "Pistons", "Pacers", "Cavaliers", "Hornets", "Hawks", "Wizards", "Raptors", "Timberwolves", "Blazers"],
    "NHL": ["Bruins", "Leafs", "Oilers", "Rangers", "Stars", "Avalanche", "Lightning", "Devils", "Islanders", "Flyers", "Penguins", "Capitals", "Hurricanes", "Panthers", "Red Wings", "Sabres", "Senators", "Canadiens", "Jets", "Wild", "Predators", "Blues", "Blackhawks", "Coyotes", "Golden Knights", "Kings", "Ducks", "Sharks", "Canucks", "Flames", "Kraken"]
}

# Abbreviation mappings for partial matches
LEAGUE_ABBREVIATIONS = {
    "NFL": ["LA", "NY", "SF", "KC", "GB", "TB", "NO", "ATL", "CAR", "JAX", "TEN", "IND", "HOU", "WAS"],
    "NBA": ["LA C", "Los Angeles C", "LA L", "Los Angeles L", "LA Lakers", "LA Clippers", "NY K", "New York K", "GSW", "Golden State", "PHI", "MIL", "CHI", "PHX", "DAL", "DEN", "MIA", "ORL", "SAC", "MEM", "NO", "UTA", "OKC", "SA", "HOU", "DET", "IND", "CLE", "CHA", "ATL", "WAS", "TOR", "MIN", "POR"],
    "NHL": ["LA", "NY", "NYI", "NYR", "TB", "FLA", "CAR", "NJ", "PHI", "PIT", "WSH", "DET", "BUF", "OTT", "MTL", "WPG", "MIN", "NSH", "STL", "CHI", "ARI", "VGK", "ANA", "SJ", "VAN", "CGY", "SEA", "COL", "DAL", "EDM", "TOR", "BOS"]
}

def detect_league(title: str) -> str:
    """
    Detect league from team names in title.
    Handles abbreviations and partial matches.
    Defaults to NCAA if valid matchup but no pro team found.
    """
    title_upper = title.upper()
    
    # Check full team names first
    for league, teams in LEAGUE_MAP.items():
        for team in teams:
            if team.upper() in title_upper:
                return league
    
    # Check abbreviations
    for league, abbrevs in LEAGUE_ABBREVIATIONS.items():
        for abbrev in abbrevs:
            if abbrev.upper() in title_upper:
                return league
    
    # Special cases for common abbreviations
    if "LOS ANGELES C" in title_upper or "LA C" in title_upper:
        return "NBA"  # Clippers
    if "LOS ANGELES L" in title_upper or "LA L" in title_upper:
        return "NBA"  # Lakers
    
    # If it's a valid matchup but no pro team found, default to NCAA
    if is_valid_game(title):
        return "NCAA"
    
    return "Unknown"

# --- 🧮 CORE HELPERS ---

def cents_to_american(cents: int) -> Optional[int]:
    """Converts 1-99 cents to American Odds (Integer)."""
    if cents is None or cents <= 1 or cents >= 99:
        return None
    prob = cents / 100.0
    
    if prob == 0.5:
        return 100
    
    if prob > 0.5:
        val = (prob / (1 - prob)) * 100
        return int(-val)
    else:
        val = ((1 - prob) / prob) * 100
        return int(val)

def probability_to_american(prob: float) -> Optional[int]:
    """Converts 0-1 probability to American Odds (Integer)."""
    if prob is None or prob <= 0 or prob >= 1:
        return None
    
    if prob == 0.5:
        return 100
    
    if prob > 0.5:
        val = (prob / (1 - prob)) * 100
        return int(-val)
    else:
        val = ((1 - prob) / prob) * 100
        return int(val)

def format_odds(odds: Optional[int]) -> str:
    """Formats American odds as string."""
    if odds is None:
        return "N/A"
    try:
        odds_int = int(odds)
        return f"+{odds_int}" if odds_int > 0 else f"{odds_int}"
    except (TypeError, ValueError):
        return "N/A"

# --- 🎯 THE GATEKEEPER: GAME VALIDATOR ---

def is_valid_game(title: str) -> bool:
    """
    Structural Game Validator - Entity A vs Entity B only.
    MUST match "vs/@/at" pattern.
    MUST NOT contain prop-specific garbage.
    CRITICAL: Do NOT ban "Winner" (valid for Moneylines).
    """
    if not title:
        return False
    
    title_lower = title.lower()
    
    # MUST match: Entity A vs/@/at Entity B
    matchup_pattern = r".+\s+(vs\.?|@|at)\s+.+"
    if not re.search(matchup_pattern, title, re.IGNORECASE):
        return False
    
    # Prop-specific blacklist (NOT "Winner")
    prop_blacklist = [
        "halftime", "show", "anthem", "song", "coin toss", 
        "gatorade", "mvp", "draft", "coach", "temperature"
    ]
    
    for word in prop_blacklist:
        if word in title_lower:
            return False
    
    return True

# --- 🎯 MAIN LINE HEURISTIC (The Garbage Collector) ---

def is_main_line(market_type: str, line_value: Optional[float], league: str) -> bool:
    """
    Filter out props/derivatives using statistical ranges.
    Only allow Full Game lines.
    """
    if market_type == "Moneyline":
        return True  # Moneylines are always valid
    
    if line_value is None:
        return False
    
    if market_type == "Total":
        # NFL: 30-70 points
        if league == "NFL":
            return 30 < line_value < 70
        # NBA: 180-260 points
        elif league == "NBA":
            return 180 < line_value < 260
        # NCAA: 100-200 points
        elif league == "NCAA":
            return 100 < line_value < 200
        # NHL/Soccer: 4.5-10 goals
        elif league in ["NHL", "Soccer"]:
            return 4.5 < line_value < 10
        # Default: allow reasonable range
        else:
            return 20 < line_value < 100
    
    if market_type == "Spread":
        # RELAXED: Valid spread range: -50 to +50 (was -25 to +25)
        return -50 < line_value < 50
    
    return False

# --- 🔍 TYPE DETECTION ENGINE (Context-Aware Parsing) ---

def extract_line_value(text: str) -> Optional[float]:
    """
    Extract numeric line value from text (spread or total).
    CRITICAL: Only extract numbers that look like betting lines, not dates or other numbers.
    Returns None if not found.
    """
    if not text:
        return None
    
    # Look for decimal numbers with .5 (e.g., -3.5, +7.5, 54.5) - betting lines usually have .5
    # Also look for whole numbers with +/- sign (e.g., -3, +7)
    # Pattern: optional +/- sign, digits, optional .5 or .0
    patterns = [
        r'([+-]?\d+\.5)',  # Numbers ending in .5 (most common for spreads/totals)
        r'([+-]?\d+\.0)',  # Numbers ending in .0
        r'([+-]\d+)',      # Signed whole numbers
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                val = float(match.group(1))
                # Filter out dates and other non-betting numbers
                # Spreads/totals are usually between -60 and +60, or totals > 30
                if -60 <= val <= 60 or (val > 30 and val < 300):
                    return val
            except ValueError:
                pass
    
    return None

def detect_kalshi_type(title: str, subtitle: str, league: str = "Unknown") -> tuple:
    """
    Kalshi Type Detection: Analyze subtitle field structure.
    Uses sport-specific classification.
    Returns: (market_type, line_value)
    """
    subtitle_lower = (subtitle or "").lower()
    
    # Extract line value first
    line_value = extract_line_value(subtitle)
    
    # Check for explicit keywords
    if "wins by" in subtitle_lower or "by more than" in subtitle_lower:
        if line_value is None:
            line_value = extract_line_value(subtitle)
        # Use sport-specific classification
        m_type = classify_market_type(league, line_value, "", subtitle)
        return (m_type, line_value)
    
    # Check for "Total", "Over", "Under"
    if any(word in subtitle_lower for word in ["total", "over", "under"]):
        if line_value is None:
            line_value = extract_line_value(subtitle)
        return ("Total", line_value)
    
    # If we have a line value, use sport-specific classification
    if line_value is not None:
        m_type = classify_market_type(league, line_value, "", subtitle)
        return (m_type, line_value)
    
    # MONEYLINE: Empty subtitle OR "Game Winner" OR "Winner" (if valid game)
    if not subtitle or subtitle_lower in ["game winner", "winner"]:
        if is_valid_game(title):
            return ("Moneyline", None)
    
    # Default to Moneyline if valid game
    if is_valid_game(title):
        return ("Moneyline", None)
    
    return ("Moneyline", None)  # Default fallback

def detect_polymarket_type(title: str, market_question: str, outcome_prices: List, market_name: str = "", outcome_labels: List = None, league: str = "Unknown") -> tuple:
    """
    Polymarket Type Detection: Context-Aware Parsing with Sport-Specific Classification.
    Checks Title, Question, Market Name, AND Outcome Labels for spreads.
    Returns: (market_type, line_value)
    """
    if not is_valid_game(title):
        return ("Moneyline", None)
    
    title_lower = title.lower()
    question_lower = (market_question or "").lower()
    market_name_lower = (market_name or "").lower()
    combined = f"{title_lower} {question_lower} {market_name_lower}"
    
    # If Yes/No outcome and valid game
    if len(outcome_prices) >= 2:
        # CONTEXT-AWARE: Check outcome labels first (Polymarket often puts line here)
        if outcome_labels:
            for label in outcome_labels:
                if label:
                    label_str = str(label)
                    # Check for "Over" or "Under" in outcome name (force Total)
                    if "over" in label_str.lower() or "under" in label_str.lower():
                        line_value = extract_line_value(label_str)
                        return ("Total", line_value)
                    
                    # Look for spread pattern: "Team Name -3.5"
                    spread_pattern = r"([A-Za-z0-9 ]+?)\s*([-+]?\d+\.?\d*)"
                    spread_match = re.search(spread_pattern, label_str)
                    if spread_match:
                        line_value = extract_line_value(spread_match.group(0))
                        if line_value:
                            # Use sport-specific classification
                            m_type = classify_market_type(league, line_value, label_str, "")
                            return (m_type, line_value)
        
        # Check market_name or question for spread pattern
        spread_pattern = r"([A-Za-z0-9 ]+?)\s*([-+]?\d+\.?\d*)"
        spread_match = re.search(spread_pattern, market_name or market_question or title)
        if spread_match:
            line_value = extract_line_value(spread_match.group(0))
            if line_value:
                # Use sport-specific classification
                m_type = classify_market_type(league, line_value, market_name or market_question, "")
                return (m_type, line_value)
        
        # Check for total indicators
        if any(word in combined for word in ["over", "under", "total", "o/u"]):
            line_value = extract_line_value(combined)
            return ("Total", line_value)
        
        # Check for spread in title
        line_value = extract_line_value(title)
        if line_value:
            m_type = classify_market_type(league, line_value, "", "")
            return (m_type, line_value)
        
        return ("Moneyline", None)
    
    return ("Moneyline", None)

def detect_sx_bet_type(outcome_one_name: str, line: str) -> tuple:
    """
    SX Bet Type Detection: Analyze outcomeOneName and line fields.
    Returns: (market_type, line_value)
    """
    outcome_lower = (outcome_one_name or "").lower()
    line_str = str(line or "")
    
    # TOTAL: "Over" in outcome name
    if "over" in outcome_lower or "under" in outcome_lower:
        line_value = extract_line_value(line_str or outcome_one_name)
        return ("Total", line_value)
    
    # SPREAD: Contains "-" or "+" with number
    if re.search(r'[+-]\d+\.?\d*', outcome_lower) or re.search(r'[+-]\d+\.?\d*', line_str):
        line_value = extract_line_value(line_str or outcome_one_name)
        return ("Spread", line_value)
    
    # Default to Moneyline
    return ("Moneyline", None)

# --- 🎯 SPORT-SPECIFIC CLASSIFICATION (The Logic Engine) ---

def classify_market_type(league: str, line_value: Optional[float], outcome_name: str = "", subtitle: str = "") -> str:
    """
    Classify market type based on Sport and Number Range.
    Returns: "Spread", "Total", "Moneyline", "Team Total", or "Prop"
    Team Totals and Props should be DISCARDED.
    """
    if line_value is None:
        return "Moneyline"
    
    outcome_lower = (outcome_name or "").lower()
    subtitle_lower = (subtitle or "").lower()
    combined = f"{outcome_lower} {subtitle_lower}"
    
    # Check for explicit "Over" or "Under" in outcome name (Polymarket fix)
    if "over" in outcome_lower or "under" in outcome_lower:
        return "Total"
    
    # Check for explicit "Total" keyword
    if "total" in combined:
        return "Total"
    
    abs_line = abs(line_value)
    
    # NHL / Hockey
    if league == "NHL":
        if abs_line < 3.0:
            return "Spread"  # Puck Line
        elif line_value > 4.5:
            return "Total"  # Over/Under
        else:
            return "Prop"  # Discard
    
    # NFL / Football
    elif league == "NFL":
        if abs_line < 17.0:
            return "Spread"
        elif line_value > 30.0:
            return "Total"  # Game Total
        elif 17.0 <= abs_line <= 30.0:
            return "Team Total"  # DISCARD
        else:
            return "Prop"  # Discard
    
    # NBA / Basketball
    elif league == "NBA":
        if abs_line < 25.0:
            return "Spread"
        elif line_value > 180.0:
            return "Total"  # Game Total
        elif 80.0 <= line_value <= 150.0:
            return "Team Total"  # DISCARD
        else:
            return "Prop"  # Discard
    
    # NCAA Football
    elif league == "NCAA":
        if abs_line < 17.0:
            return "Spread"
        elif line_value > 30.0:
            return "Total"  # Game Total
        elif 17.0 <= abs_line <= 30.0:
            return "Team Total"  # DISCARD
        else:
            return "Prop"  # Discard
    
    # Soccer
    elif league in ["Soccer", "MLS"]:
        if abs_line < 3.0:
            return "Spread"
        elif line_value > 2.0:
            return "Total"
        else:
            return "Prop"  # Discard
    
    # Default: try to infer from line value
    if abs_line < 20.0:
        return "Spread"
    elif line_value > 30.0:
        return "Total"
    else:
        return "Moneyline"

# --- 📊 DATA NORMALIZATION ---

def normalize_event_title(title: str) -> str:
    """Clean event title for display."""
    # Strip "Winner?" and "Game" prefix
    cleaned = title.replace("Winner?", "").replace("Game Winner", "").strip()
    cleaned = re.sub(r'^Game\s+', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def parse_matchup(title: str) -> tuple:
    """Extract home and away teams from title. Returns (home, away)."""
    clean = normalize_event_title(title)
    
    if " vs " in clean or " vs. " in clean:
        parts = re.split(r'\s+vs\.?\s+', clean, flags=re.IGNORECASE)
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()
    
    if " at " in clean:
        parts = clean.split(" at ")
        if len(parts) >= 2:
            return parts[1].strip(), parts[0].strip()  # home, away
    
    if "@" in clean:
        parts = clean.split("@")
        if len(parts) >= 2:
            return parts[1].strip(), parts[0].strip()  # home, away
    
    return clean, "Opponent"

def extract_team_from_spread_subtitle(subtitle: str, home: str, away: str) -> tuple:
    """
    Extract which team the spread applies to from Kalshi subtitle.
    Examples:
    - "Suns win by more than 9.5" -> ("Suns", "Timberwolves", 9.5, "Spread")
    - "Total points over 223.5" -> (home, away, 223.5, "Total")
    Returns: (team_a_name, team_b_name, line_value, market_type)
    """
    if not subtitle:
        return (home, away, None, "Moneyline")
    
    subtitle_lower = subtitle.lower()
    
    # Check for spread pattern: "Team wins by more than X" or "Team by more than X"
    spread_patterns = [
        r'([A-Za-z\s]+?)\s+win[s]?\s+by\s+more\s+than\s+(\d+\.?\d*)',
        r'([A-Za-z\s]+?)\s+by\s+more\s+than\s+(\d+\.?\d*)',
        r'([A-Za-z\s]+?)\s+win[s]?\s+by\s+(\d+\.?\d*)',
    ]
    
    for pattern in spread_patterns:
        match = re.search(pattern, subtitle, re.IGNORECASE)
        if match:
            team_name = match.group(1).strip()
            line_val = float(match.group(2))
            
            # Determine which team this is
            if team_name.lower() in home.lower() or home.lower() in team_name.lower():
                return (home, away, line_val, "Spread")
            elif team_name.lower() in away.lower() or away.lower() in team_name.lower():
                return (away, home, line_val, "Spread")
            else:
                # Default to home team if we can't match
                return (home, away, line_val, "Spread")
    
    # Check for total pattern: "Total points over/under X" or "Over/Under X"
    total_patterns = [
        r'total\s+points?\s+(over|under)\s+(\d+\.?\d*)',
        r'(over|under)\s+(\d+\.?\d*)',
    ]
    
    for pattern in total_patterns:
        match = re.search(pattern, subtitle_lower)
        if match:
            over_under = match.group(1)
            line_val = float(match.group(2))
            return (home, away, line_val, "Total")
    
    # Default to moneyline
    return (home, away, None, "Moneyline")

def extract_team_from_polymarket_outcome(outcome_labels: List, home: str, away: str, line_value: float, market_type: str) -> tuple:
    """
    Extract which team the spread/total applies to from Polymarket outcome labels.
    CRITICAL: Must extract the ACTUAL spread line with correct sign from outcome labels.
    Examples:
    - ["Suns -9.5", "Timberwolves +9.5"] -> ("Suns", "Timberwolves", -9.5, "Spread")
    - ["Over 223.5", "Under 223.5"] -> (home, away, 223.5, "Total")
    Returns: (team_a_name, team_b_name, line_value, market_type)
    """
    if not outcome_labels:
        return (home, away, line_value, market_type)
    
    if market_type == "Total":
        # For totals, use "Over" and "Under"
        return (home, away, line_value, "Total")
    
    if market_type == "Spread":
        # Look for team name and spread in outcome labels
        # Polymarket typically has: ["Team A -9.5", "Team B +9.5"] or similar
        for label in outcome_labels:
            if not label:
                continue
            label_str = str(label).strip()
            
            # Pattern: "Team Name -9.5" or "Team Name +9.5" - must have sign and .5
            # More specific pattern to avoid matching dates or other numbers
            spread_pattern = r'([A-Za-z\s]+?)\s+([-+]\d+\.5)'
            spread_match = re.search(spread_pattern, label_str)
            if spread_match:
                team_name = spread_match.group(1).strip()
                spread_line_str = spread_match.group(2)
                spread_line = float(spread_line_str)  # Keep the sign!
                
                # Match team name to home or away
                if team_name.lower() in home.lower() or home.lower() in team_name.lower():
                    # This team has the spread, use it with correct sign
                    return (home, away, spread_line, "Spread")
                elif team_name.lower() in away.lower() or away.lower() in team_name.lower():
                    # This team has the spread, use it with correct sign
                    return (away, home, spread_line, "Spread")
        
        # Fallback: Try to find spread in any label
        for label in outcome_labels:
            if not label:
                continue
            label_str = str(label)
            # Look for just the spread number with sign
            spread_match = re.search(r'([-+]\d+\.5)', label_str)
            if spread_match:
                spread_line = float(spread_match.group(1))
                # Use the first team as default
                return (home, away, spread_line, "Spread")
    
    # Default - use provided line_value but ensure it's reasonable
    if line_value and abs(line_value) > 60:
        # Line value seems wrong, return None to skip
        return (home, away, None, market_type)
    
    return (home, away, line_value, market_type)

def generate_bet_recommendation(
    title: str, 
    subtitle: str, 
    market_type: str, 
    side: str, 
    source: str,
    line_value: Optional[float] = None
) -> str:
    """
    Generate normalized bet recommendation with "No" inversion logic.
    Now accepts line_value parameter for cleaner parsing.
    """
    try:
    home, away = parse_matchup(title)
    
        # MONEYLINE
        if market_type == "Moneyline":
            if side == "Yes":
                # Extract team from title (usually first team or "Winner" subject)
                if "will" in title.lower() and "win" in title.lower():
                    # "Dallas will win" -> Bet Dallas
                    team_match = re.search(r'([A-Za-z\s]+)\s+will\s+win', title, re.IGNORECASE)
                    if team_match:
                        team = team_match.group(1).strip()
                        return f"Bet: {team} ML"
                
                # Default: bet first team mentioned
                return f"Bet: {home} ML"
            else:
                # "No" = bet opponent
                if "will" in title.lower() and "win" in title.lower():
                    team_match = re.search(r'([A-Za-z\s]+)\s+will\s+win', title, re.IGNORECASE)
                    if team_match:
                        team = team_match.group(1).strip()
                        opponent = away if team in home or home in team else home
                        return f"Bet: {opponent} ML"
                
                return f"Bet: {away} ML"
        
    # SPREAD
        if market_type == "Spread":
            # Use provided line_value or extract from subtitle
            if line_value is not None:
                line_str = f"{line_value:+.1f}" if line_value != int(line_value) else f"{int(line_value):+d}"
            else:
                line_match = re.search(r'([+-]?\d+\.?\d*)', subtitle or "")
                line_str = line_match.group(1) if line_match else ""
            
            if "wins by" in (subtitle or "").lower():
                # "Dallas wins by 3.5" -> Bet Dallas -3.5
                team_match = re.search(r'([A-Za-z\s]+)\s+wins\s+by', subtitle, re.IGNORECASE)
                if team_match:
                    team = team_match.group(1).strip()
                    if side == "Yes":
                        return f"Bet: {team} {line_str}"
                    else:
                        # "No" = opponent covers
                        opponent = away if team in home or home in team else home
                        # Invert line
                        if line_value is not None:
                            inverted = -line_value
                            inverted_str = f"{inverted:+.1f}" if inverted != int(inverted) else f"{int(inverted):+d}"
                            return f"Bet: {opponent} {inverted_str}"
                        else:
                            try:
                                line_num = float(line_str.replace('+', '').replace('-', ''))
                                inverted = f"+{line_num}" if line_str.startswith('-') else f"-{line_num}"
                                return f"Bet: {opponent} {inverted}"
                            except:
                                return f"Bet: {opponent} +{line_str.replace('-', '').replace('+', '')}"
            
            # Generic spread - combine Team + Line
            if line_str:
                if side == "Yes":
                    return f"Bet: {home} {line_str}"
                else:
                    opponent = away
                    if line_value is not None:
                        inverted = -line_value
                        inverted_str = f"{inverted:+.1f}" if inverted != int(inverted) else f"{int(inverted):+d}"
                        return f"Bet: {opponent} {inverted_str}"
                    else:
                        try:
                            line_num = float(line_str.replace('+', '').replace('-', ''))
                            inverted = f"+{line_num}" if line_str.startswith('-') else f"-{line_num}"
                            return f"Bet: {opponent} {inverted}"
                        except:
                            return f"Bet: {opponent} +{line_str.replace('-', '').replace('+', '')}"
            
            return f"Bet: {home} {line_str}" if side == "Yes" else f"Bet: {away} +{line_str}"

    # TOTAL
        if market_type == "Total":
            # Use provided line_value or extract from subtitle
            if line_value is not None:
                line_str = f"{line_value:.1f}" if line_value != int(line_value) else f"{int(line_value)}"
        else:
                line_match = re.search(r'(\d+\.?\d*)', subtitle or "")
                line_str = line_match.group(1) if line_match else ""
            
            is_over = "over" in (subtitle or "").lower() or "more than" in (subtitle or "").lower()
            
            if side == "Yes":
                return f"Bet: Over {line_str}" if is_over else f"Bet: Under {line_str}"
            else:
                # "No" = invert
                return f"Bet: Under {line_str}" if is_over else f"Bet: Over {line_str}"
        
        # Default
        return f"Bet: {home} ML" if side == "Yes" else f"Bet: {away} ML"
        
    except Exception as e:
        logger.warning(f"Error generating bet recommendation: {e}")
        return f"Bet: {normalize_event_title(title)}"

def get_smart_bet(
    title: str,
    subtitle: str,
    market_type: str,
    line_value: Optional[float],
    league: str,
    side: str,
    market_data: Dict
) -> str:
    """
    Wrapper for generate_bet_recommendation with simplified signature.
    """
    return generate_bet_recommendation(title, subtitle, market_type, side, "Kalshi", line_value)

# --- 💰 ORDERBOOK PARSING (Top of Book) ---

def extract_both_sides(orderbook_data: Dict, source: str, market_type: str) -> Dict:
    """
    Extract BOTH sides of a market (Team A and Team B) with correct prices.
    Returns: {
        'side_a': {'odds': int, 'liquidity': float, 'wall': float, 'levels': []},
        'side_b': {'odds': int, 'liquidity': float, 'wall': float, 'levels': []},
        'total_liquidity_a': float,
        'total_liquidity_b': float
    }
    """
    side_a_levels = []
    side_b_levels = []
    
    if not orderbook_data:
        return {
            'side_a': {'odds': None, 'liquidity': 0.0, 'wall': 0.0, 'levels': []},
            'side_b': {'odds': None, 'liquidity': 0.0, 'wall': 0.0, 'levels': []},
            'total_liquidity_a': 0.0,
            'total_liquidity_b': 0.0
        }
    
    if source == "Kalshi":
        # Kalshi: Yes = Side A, No = Side B
        yes_asks = orderbook_data.get('yes', {}).get('asks', [])
        no_asks = orderbook_data.get('no', {}).get('asks', [])
        yes_bids = orderbook_data.get('yes', {}).get('bids', [])
        no_bids = orderbook_data.get('no', {}).get('bids', [])
        
        # Side A (Yes): Extract all levels
        for level in yes_asks[:10]:
            if isinstance(level, list) and len(level) >= 2:
                price_cents = int(level[0])
                volume = float(level[1])
                odds = cents_to_american(price_cents)
                if odds:
                    liquidity = (price_cents / 100.0) * volume
                    side_a_levels.append({'price': price_cents, 'volume': volume, 'odds': odds, 'liquidity': liquidity})
        
        # Side B (No): Convert No price to Side B odds
        for level in no_asks[:10]:
            if isinstance(level, list) and len(level) >= 2:
                no_price_cents = int(level[0])
                volume = float(level[1])
                # Convert No probability to Side B odds
                no_prob = no_price_cents / 100.0
                side_b_odds = probability_to_american(no_prob)
                if side_b_odds:
                    liquidity = (no_price_cents / 100.0) * volume
                    side_b_levels.append({'price': no_price_cents, 'volume': volume, 'odds': side_b_odds, 'liquidity': liquidity})
    
    elif source == "Polymarket":
        # Polymarket CLOB: asks = buy side (Side A), bids = sell side (Side B)
        # Price is already a probability (0-1), size is in shares
        market_asks = orderbook_data.get('asks', [])
        market_bids = orderbook_data.get('bids', [])
        
        # Side A: Asks (buy side) - price is probability for outcome 1
        for level in market_asks[:10]:
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                price_prob = float(level[0])
                size = float(level[1])
                odds = probability_to_american(price_prob)
                if odds:
                    # Liquidity = price * size (dollar value)
                    liquidity = price_prob * size
                    side_a_levels.append({'price': price_prob, 'volume': size, 'odds': odds, 'liquidity': liquidity})
        
        # Side B: Bids (sell side) - price is probability for outcome 1, so invert for outcome 2
        for level in market_bids[:10]:
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                price_prob = float(level[0])
                size = float(level[1])
                # Invert probability for Side B (outcome 2)
                side_b_prob = 1.0 - price_prob
                side_b_odds = probability_to_american(side_b_prob)
                if side_b_odds:
                    # Liquidity = price * size (dollar value)
                    liquidity = price_prob * size
                    side_b_levels.append({'price': price_prob, 'volume': size, 'odds': side_b_odds, 'liquidity': liquidity})
    
    # Sort: Side A by odds (ascending for favorites), Side B by odds (descending for underdogs)
    if side_a_levels:
        side_a_levels.sort(key=lambda x: x['odds'])
    if side_b_levels:
        side_b_levels.sort(key=lambda x: x['odds'], reverse=True)
    
    # Extract best prices and liquidity
    best_odds_a = side_a_levels[0]['odds'] if side_a_levels else None
    best_odds_b = side_b_levels[0]['odds'] if side_b_levels else None
    liquidity_a = side_a_levels[0]['liquidity'] if side_a_levels else 0.0
    liquidity_b = side_b_levels[0]['liquidity'] if side_b_levels else 0.0
    
    # Calculate total liquidity (sum of all levels)
    total_liq_a = sum(level['liquidity'] for level in side_a_levels)
    total_liq_b = sum(level['liquidity'] for level in side_b_levels)
    
    # Calculate wall (within 5% of best)
    wall_a = 0.0
    if side_a_levels:
        best_price_a = side_a_levels[0]['price']
        for level in side_a_levels:
            if source == "Kalshi":
                price_diff = abs(level['price'] - best_price_a) / 100.0
            else:
                price_diff = abs(level['price'] - best_price_a)
            if price_diff <= 0.05:
                wall_a += level['liquidity']
    
    wall_b = 0.0
    if side_b_levels:
        best_price_b = side_b_levels[0]['price']
        for level in side_b_levels:
            if source == "Kalshi":
                price_diff = abs(level['price'] - best_price_b) / 100.0
            else:
                price_diff = abs(level['price'] - best_price_b)
            if price_diff <= 0.05:
                wall_b += level['liquidity']
    
    return {
        'side_a': {'odds': best_odds_a, 'liquidity': liquidity_a, 'wall': wall_a, 'levels': side_a_levels},
        'side_b': {'odds': best_odds_b, 'liquidity': liquidity_b, 'wall': wall_b, 'levels': side_b_levels},
        'total_liquidity_a': total_liq_a,
        'total_liquidity_b': total_liq_b
    }

def calculate_actionable_liquidity(bid_price_cents: float, bid_volume: float) -> float:
    """
    Calculate actionable liquidity: (Bid_Price_Cents / 100.0) * Bid_Volume
    """
    if bid_price_cents <= 0 or bid_volume <= 0:
        return 0.0
    
    return (bid_price_cents / 100.0) * bid_volume

# --- 🎯 MAIN LINE SELECTOR (The True Line Finder) ---

def calculate_distance_to_even_money(american_odds: Optional[int]) -> float:
    """
    Calculate distance to 50/50 odds (even money = -110 / 52.4 cents).
    Returns distance: abs(Implied_Prob - 0.50)
    Lower distance = closer to main line.
    """
    if american_odds is None:
        return 999.0  # Very far from even money
    
    # Convert American odds to implied probability
    if american_odds > 0:
        prob = 100.0 / (american_odds + 100.0)
    else:
        prob = abs(american_odds) / (abs(american_odds) + 100.0)
    
    # Distance from 50/50
    return abs(prob - 0.50)

def is_strict_main_line(american_odds: Optional[int]) -> bool:
    """
    Strict odds filter: Main lines are between -200 and +200.
    RELAXED for testing - was -150 to +150, now wider range.
    """
    if american_odds is None:
        return False
    
    return -200 <= american_odds <= 200

def select_main_line(markets: List[Dict]) -> List[Dict]:
    """
    Main Line Selector Algorithm:
    - For Moneylines: Take highest liquidity (skip distance filter)
    - For Spreads/Totals: Find closest to 50/50 odds
    """
    if not markets:
        return []
    
    # Group by (Event, Type)
    grouped = {}
    for market in markets:
        event = market.get('Event', '')
        m_type = market.get('Type', '')
        key = (event, m_type)
        
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(market)
    
    # Select main line for each group
    main_lines = []
    for key, group_markets in grouped.items():
        event, m_type = key
        
        if len(group_markets) == 1:
            # Only one market, use it
            main_lines.append(group_markets[0])
        elif m_type == "Moneyline":
            # For Moneylines: Take highest liquidity (trust Kalshi's Yes/No structure)
            best_market = None
            best_liquidity = 0.0
            
            for market in group_markets:
                odds = market.get('RawOdds', 0)
                liquidity = market.get('Liquidity @ Best', 0)
                
                # Apply strict odds filter
                if not is_strict_main_line(odds):
                    continue
                
                if liquidity > best_liquidity:
                    best_liquidity = liquidity
                    best_market = market
            
            if best_market:
                main_lines.append(best_market)
        else:
            # For Spreads/Totals: Find closest to 50/50
            best_market = None
            best_distance = 999.0
            
            for market in group_markets:
                odds = market.get('RawOdds', 0)
                
                # RELAXED: Skip strict odds filter - just find closest to even money
                # if not is_strict_main_line(odds):
                #     continue
                
                distance = calculate_distance_to_even_money(odds)
                if distance < best_distance:
                    best_distance = distance
                    best_market = market
            
            # If no market found, just take the first one (don't filter out everything)
            if best_market:
                main_lines.append(best_market)
            elif group_markets:
                # Fallback: take first market if no "best" found
                main_lines.append(group_markets[0])
    
    return main_lines

# --- 📡 DATA INGESTION ---

def fetch_kalshi_markets() -> List[Dict]:
    """
    Kalshi: FULL DATA DUMP - Get ALL open markets at once.
    Uses credentials to get complete real-time data dump.
    """
    all_markets = []
    results = []
    
        try:
        # FULL DUMP: Get ALL open markets, no filtering on API side
            url = "https://api.elections.kalshi.com/trade-api/v2/markets"
        # Use high limit or pagination to get everything
        params = {'limit': 1000, 'status': 'open'}  # Remove series_ticker filter - get everything
        
        logger.info("Kalshi: Fetching FULL market dump (all open markets)...")
        res = requests.get(url, auth=kalshi_auth, params=params, timeout=10.0)
        
        if res.status_code == 200:
            response_data = res.json()
            data = response_data.get('markets', [])
            all_markets.extend(data)
            
            # Check if there's pagination (cursor for next page)
            cursor = response_data.get('cursor')
            while cursor and len(data) == 1000:  # If we got max results, there might be more
                params['cursor'] = cursor
                res = requests.get(url, auth=kalshi_auth, params=params, timeout=10.0)
                if res.status_code == 200:
                    response_data = res.json()
                    data = response_data.get('markets', [])
                    all_markets.extend(data)
                    cursor = response_data.get('cursor')
                else:
                    break
            
            logger.info(f"Kalshi: FULL DUMP - Fetched {len(all_markets)} total markets")
        else:
            logger.error(f"Kalshi API Error: Status {res.status_code} - {res.text[:200]}")
            return []
        
        if not all_markets:
            return []
    
    except Exception as e:
        logger.error(f"Kalshi CRITICAL ERROR: {e}")
        return []
    
    def process_market(m):
        try:
            title = m.get('title', '')
            subtitle = m.get('subtitle', '')
            
            # GATEKEEPER: Must be valid game
            if not is_valid_game(title):
                return None
            
            # Check if yes_bid exists
            yes_bid_cents = m.get('yes_bid', 0)
            if yes_bid_cents is None or yes_bid_cents <= 0:
                return None
            
            # LEAGUE DETECTION: Use team names, not API tags (do this first for classification)
            league = detect_league(title)
            
            # TYPE DETECTION: Sport-specific classification (returns type, line_value)
            market_type, line_value = detect_kalshi_type(title, subtitle, league)
            
            # FILTER: Discard Team Totals and Props
            if market_type in ["Team Total", "Prop"]:
                return None
            
            # MAIN LINE FILTER: Discard props/derivatives (range check)
            if not is_main_line(market_type, line_value, league):
                return None
            
            # GET ORDERBOOK DATA: Extract Best Ask (Top of Book)
            orderbook = m.get('orderbook', {})
            if not orderbook:
                # Fallback: construct from yes/no bid/ask with proper volume
                yes_ask_cents = m.get('yes_ask', yes_bid_cents)
                no_ask_cents = m.get('no_ask', m.get('no_bid', 0))
                no_bid_cents = m.get('no_bid', 0)
                
                # Get volumes - try multiple field names
                yes_ask_vol = m.get('yes_ask_count', m.get('yes_ask_volume', m.get('volume', 0)))
                yes_bid_vol = m.get('yes_bid_count', m.get('yes_bid_volume', m.get('volume', 0)))
                no_ask_vol = m.get('no_ask_count', m.get('no_ask_volume', 0))
                no_bid_vol = m.get('no_bid_count', m.get('no_bid_volume', 0))
                
                orderbook = {
                    'yes': {
                        'asks': [[yes_ask_cents, yes_ask_vol]] if yes_ask_cents > 0 else [],
                        'bids': [[yes_bid_cents, yes_bid_vol]] if yes_bid_cents > 0 else []
                    },
                    'no': {
                        'asks': [[no_ask_cents, no_ask_vol]] if no_ask_cents > 0 else [],
                        'bids': [[no_bid_cents, no_bid_vol]] if no_bid_cents > 0 else []
                    }
                }
            
            # Extract BOTH sides with correct prices
            sides_data = extract_both_sides(orderbook, "Kalshi", market_type)
            
            side_a = sides_data['side_a']
            side_b = sides_data['side_b']
            
            # Determine which side is sharp (LOWER liquidity = sharp side, because sharps bet early)
            # Higher liquidity = public money (late money)
            if sides_data['total_liquidity_a'] > sides_data['total_liquidity_b']:
                sharp_side = "B"  # Side B has less liquidity = sharp side
                sharp_odds = side_b['odds']
                sharp_liquidity = sides_data['total_liquidity_b']
            elif sides_data['total_liquidity_b'] > sides_data['total_liquidity_a']:
                sharp_side = "A"  # Side A has less liquidity = sharp side
                sharp_odds = side_a['odds']
                sharp_liquidity = sides_data['total_liquidity_a']
            else:
                # Equal liquidity, default to A
                sharp_side = "A"
                sharp_odds = side_a['odds']
                sharp_liquidity = sides_data['total_liquidity_a']
            
            # RELAXED ODDS FILTER: Main lines only (-200 to +200) - check both sides
            # Allow if at least one side is in range
            if not is_strict_main_line(side_a['odds']) and not is_strict_main_line(side_b['odds']):
                # Skip only if BOTH sides are out of range
                if side_a['odds'] and side_b['odds']:
                    return None
            
            # RELAXED FILTER: $500 minimum total liquidity (was $1,000)
            if sides_data['total_liquidity_a'] + sides_data['total_liquidity_b'] < 500:
                return None
            
            # Parse team names FIRST - extract from subtitle for spreads/totals
            home, away = parse_matchup(title)
            
            if market_type == "Moneyline":
                team_a_name = home
                team_b_name = away
            elif market_type == "Spread":
                # Extract which team the spread applies to
                team_a, team_b, extracted_line, extracted_type = extract_team_from_spread_subtitle(subtitle, home, away)
                team_a_name = team_a
                team_b_name = team_b
                # Use extracted line if we got one and it matches
                if extracted_line and abs(extracted_line - abs(line_value or 0)) < 0.1:
                    # CRITICAL: If subtitle says "Team wins by X", that team is the favorite (-X)
                    # If subtitle says "Team by more than X", that team is the favorite (-X)
                    subtitle_lower = (subtitle or "").lower()
                    if "win" in subtitle_lower or "by more" in subtitle_lower:
                        # The team mentioned is the favorite, so their spread is negative
                        # Check which team is mentioned
                        if team_a_name.lower() in subtitle_lower or home.lower() in subtitle_lower:
                            # Team A is the favorite, so their spread is -extracted_line
                            line_value = -abs(extracted_line)
                        elif team_b_name.lower() in subtitle_lower or away.lower() in subtitle_lower:
                            # Team B is the favorite, so their spread is -extracted_line
                            line_value = -abs(extracted_line)
                    else:
                        line_value = extracted_line
            elif market_type == "Total":
                # For totals, use "Over" and "Under" as labels
                team_a_name = "Over"
                team_b_name = "Under"
            else:
                team_a_name = home
                team_b_name = away
            
            # Format line for display (with team names for spreads, Over/Under for Totals)
            if line_value is not None:
                if market_type == "Spread":
                    # Determine which team has the spread from subtitle
                    subtitle_lower = (subtitle or "").lower()
                    # Check which team is mentioned in subtitle
                    if team_a_name.lower() in subtitle_lower or home.lower() in subtitle_lower:
                        # Team A is mentioned, show their spread with correct sign
                        line_display = f"{team_a_name} {line_value:+.1f}" if line_value != int(line_value) else f"{team_a_name} {int(line_value):+d}"
                    elif team_b_name.lower() in subtitle_lower or away.lower() in subtitle_lower:
                        # Team B is mentioned, show their spread with correct sign
                        line_display = f"{team_b_name} {line_value:+.1f}" if line_value != int(line_value) else f"{team_b_name} {int(line_value):+d}"
                    else:
                        # Default: show team A with line (line_value already has correct sign)
                        line_display = f"{team_a_name} {line_value:+.1f}" if line_value != int(line_value) else f"{team_a_name} {int(line_value):+d}"
                elif market_type == "Total":
                    # Extract Over/Under from subtitle
                    subtitle_lower = (subtitle or "").lower()
                    is_over = "over" in subtitle_lower or "more than" in subtitle_lower
                    over_under = "Over" if is_over else "Under"
                    line_display = f"{over_under} {line_value:.1f}" if line_value != int(line_value) else f"{over_under} {int(line_value)}"
                else:
                    line_display = f"{line_value:.1f}" if line_value != int(line_value) else f"{int(line_value)}"
            else:
                line_display = "—"
            
            # Generate bet recommendation for sharp side
            sharp_side_str = "Yes" if sharp_side == "A" else "No"
            bet_recommendation = get_smart_bet(title, subtitle, market_type, line_value, league, sharp_side_str, m)
            
            return {
                "Source": "🟢 Kalshi",
                "League": league,
                "Event": normalize_event_title(title),
                "Type": market_type,
                "Line": line_display,
                "TeamA": team_a_name,
                "TeamB": team_b_name,
                "SideA_Odds": side_a['odds'],
                "SideB_Odds": side_b['odds'],
                "SideA_BestSource": "🟢 Kalshi",
                "SideB_BestSource": "🟢 Kalshi",
                "SideA_Liquidity": int(round(side_a['liquidity'], 0)),
                "SideB_Liquidity": int(round(side_b['liquidity'], 0)),
                "SideA_Wall": int(round(side_a['wall'], 0)),
                "SideB_Wall": int(round(side_b['wall'], 0)),
                "TotalLiquidityA": int(round(sides_data['total_liquidity_a'], 0)),
                "TotalLiquidityB": int(round(sides_data['total_liquidity_b'], 0)),
                "SideA_TotalLiquidity": int(round(sides_data['total_liquidity_a'], 0)),
                "SideB_TotalLiquidity": int(round(sides_data['total_liquidity_b'], 0)),
                "SharpSide": sharp_side,
                "SharpOdds": sharp_odds,
                "SharpLiquidity": int(round(sharp_liquidity, 0)),
                "Bet": bet_recommendation,
                "Orderbook": {
                    'side_a': side_a['levels'],
                    'side_b': side_b['levels']
                }
            }
        except Exception as e:
            logger.warning(f"Error processing Kalshi market: {e}")
            return None
    
    # Process all markets
    try:
        for m in all_markets:
            r = process_market(m)
            if r:
                results.append(r)
    except Exception as e:
        logger.error(f"Kalshi processing error: {e}")
    
    # RELAXED: Skip main line selector for now - show all markets for testing
    # results = select_main_line(results)
    
    logger.info(f"Kalshi: Returning {len(results)} markets (main line selector DISABLED)")
    return results

def fetch_polymarket_markets() -> List[Dict]:
    """
    Polymarket: FULL DATA DUMP - Get ALL active events and markets at once.
    """
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        # FULL DUMP: Get ALL active events, no tag filtering
        events_url = "https://gamma-api.polymarket.com/events"
        params = {"limit": 500, "active": "true", "closed": "false"}  # Remove tag_slug filter - get everything
        
        logger.info("Polymarket: Fetching FULL event dump (all active events)...")
        res = requests.get(events_url, params=params, headers=headers, timeout=10.0)
        
        all_events = []
        if res.status_code == 200:
            try:
                events = res.json()
                if isinstance(events, dict):
                    events = events.get('data', events.get('events', []))
                
                if isinstance(events, list):
                    all_events.extend(events)
                    logger.info(f"Polymarket: FULL DUMP - Fetched {len(all_events)} total events")
                else:
                    logger.warning(f"Polymarket: Unexpected response format")
            except Exception as e:
                logger.error(f"Polymarket: Error parsing response: {e}")
                return []
        else:
            logger.error(f"Polymarket API Error: Status {res.status_code} - {res.text[:200]}")
            return []
        
        if not all_events:
            return []
        
        # Process events - now we have all events from full dump
        def process_market(e, m):
            try:
                event_title = e.get('title', '')
                market_question = m.get('question', '')
                market_name = m.get('name', '')
                
                # GATEKEEPER: Must be valid game
                if not is_valid_game(event_title):
                    return None
                
                # Parse outcome prices
                outcome_prices_raw = m.get('outcomePrices', None)
                if not outcome_prices_raw:
                    return None
                
                outcome_prices = None
                if isinstance(outcome_prices_raw, str):
                    try:
                        outcome_prices = json.loads(outcome_prices_raw)
                    except json.JSONDecodeError:
                        try:
                            import ast
                            outcome_prices = ast.literal_eval(outcome_prices_raw)
                        except:
                            return None
                elif isinstance(outcome_prices_raw, list):
                    outcome_prices = outcome_prices_raw
            else:
                    return None
                
                if not outcome_prices or len(outcome_prices) < 2:
                    return None
                
                try:
                    yes_price = float(outcome_prices[0]) if outcome_prices[0] else 0.0
                    no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 and outcome_prices[1] else 0.0
                except (ValueError, TypeError):
                    return None
                
                # CONTEXT-AWARE PARSING: Get outcome labels for spread detection
                outcome_labels = []
                if 'outcomes' in m:
                    for outcome in m['outcomes']:
                        if isinstance(outcome, dict):
                            outcome_labels.append(outcome.get('title', outcome.get('name', '')))
                        elif isinstance(outcome, str):
                            outcome_labels.append(outcome)
                
                # Also check groupItemTitle if available
                if 'groupItemTitle' in m:
                    outcome_labels.append(m['groupItemTitle'])
                
                # LEAGUE DETECTION: Use team names, not API tags (do this first for classification)
                league = detect_league(event_title)
                
                # TYPE DETECTION: Context-aware with sport-specific classification
                market_type, line_value = detect_polymarket_type(
                    event_title, market_question, outcome_prices, market_name, outcome_labels, league
                )
                
                # FILTER: Discard Team Totals and Props
                if market_type in ["Team Total", "Prop"]:
                    return None
                
                # MAIN LINE FILTER: Discard props/derivatives (range check)
                if not is_main_line(market_type, line_value, league):
                    return None
                
                # GET ORDERBOOK DATA: Polymarket requires CLOB API call
                orderbook = {}
                clob_id = m.get('id')
                if clob_id:
                    try:
                        clob_url = f"https://clob.polymarket.com/book?token_id={clob_id}"
                        clob_res = requests.get(clob_url, timeout=3)
                        if clob_res.status_code == 200:
                            book = clob_res.json()
                            # Polymarket CLOB has bids/asks with price and size
                            bids = book.get('bids', [])
                            asks = book.get('asks', [])
                            # Convert to our format: [[price, size], ...]
                            orderbook = {
                                'asks': [[float(a.get('price', 0)), float(a.get('size', 0))] for a in asks[:10]],
                                'bids': [[float(b.get('price', 0)), float(b.get('size', 0))] for b in bids[:10]]
                            }
                    except Exception:
                        pass
                
                # If no orderbook from CLOB, try to construct from outcome prices
                if not orderbook and yes_price > 0 and no_price > 0:
                    # Fallback: create minimal orderbook from prices
                    total_liq = float(e.get('liquidity', 0))
                    orderbook = {
                        'asks': [[yes_price, total_liq * 0.5]],
                        'bids': [[no_price, total_liq * 0.5]]
                    }
                
                # Extract BOTH sides with correct prices
                sides_data = extract_both_sides(orderbook, "Polymarket", market_type)
                
                side_a = sides_data['side_a']
                side_b = sides_data['side_b']
                
                # Determine which side is sharp (LOWER liquidity = sharp side, because sharps bet early)
                # Higher liquidity = public money (late money)
                if sides_data['total_liquidity_a'] > sides_data['total_liquidity_b']:
                    sharp_side = "B"  # Side B has less liquidity = sharp side
                    sharp_odds = side_b['odds']
                    sharp_liquidity = sides_data['total_liquidity_b']
                elif sides_data['total_liquidity_b'] > sides_data['total_liquidity_a']:
                    sharp_side = "A"  # Side A has less liquidity = sharp side
                    sharp_odds = side_a['odds']
                    sharp_liquidity = sides_data['total_liquidity_a']
                else:
                    # Equal liquidity, default to A
                    sharp_side = "A"
                    sharp_odds = side_a['odds']
                    sharp_liquidity = sides_data['total_liquidity_a']
                
                # RELAXED ODDS FILTER: Main lines only (-200 to +200) - check both sides
                # Allow if at least one side is in range
                if not is_strict_main_line(side_a['odds']) and not is_strict_main_line(side_b['odds']):
                    # Skip only if BOTH sides are out of range
                    if side_a['odds'] and side_b['odds']:
                        return None
                
                # RELAXED FILTER: $500 minimum total liquidity (was $1,000)
                if sides_data['total_liquidity_a'] + sides_data['total_liquidity_b'] < 500:
                    return None
                
                # Parse team names FIRST - extract from outcome labels for spreads/totals
                home, away = parse_matchup(event_title)
                
                if market_type == "Moneyline":
                    team_a_name = home
                    team_b_name = away
                elif market_type == "Spread":
                    # Extract which team the spread applies to from outcome labels
                    team_a, team_b, extracted_line, extracted_type = extract_team_from_polymarket_outcome(
                        outcome_labels, home, away, line_value, market_type
                    )
                    team_a_name = team_a
                    team_b_name = team_b
                    if extracted_line is not None:
                        # Use extracted line (has correct sign)
                        line_value = extracted_line
                    elif line_value and abs(line_value) > 60:
                        # Line value is clearly wrong (too large), skip this market
                        return None
                elif market_type == "Total":
                    # For totals, use "Over" and "Under" as labels
                    team_a_name = "Over"
                    team_b_name = "Under"
                else:
                    team_a_name = home
                    team_b_name = away
                
                # Format line for display (with team names for spreads, Over/Under for Totals)
                if line_value is not None:
                    if market_type == "Spread":
                        # Show team name with spread
                        line_display = f"{team_a_name} {line_value:+.1f}" if line_value != int(line_value) else f"{team_a_name} {int(line_value):+d}"
                    elif market_type == "Total":
                        # Extract Over/Under from outcome labels
                        is_over = False
                        for label in outcome_labels:
                            label_lower = str(label).lower()
                            if "over" in label_lower:
                                is_over = True
                                break
                            elif "under" in label_lower:
                                is_over = False
                                break
                        # Fallback: check market question
                        if not outcome_labels:
                            market_q_lower = (market_question or "").lower()
                            is_over = "over" in market_q_lower or "more than" in market_q_lower
                        over_under = "Over" if is_over else "Under"
                        line_display = f"{over_under} {line_value:.1f}" if line_value != int(line_value) else f"{over_under} {int(line_value)}"
                    else:
                        line_display = f"{line_value:.1f}" if line_value != int(line_value) else f"{int(line_value)}"
                else:
                    line_display = "—"
                
                # Generate bet recommendation for sharp side
                sharp_side_str = "Yes" if sharp_side == "A" else "No"
                bet_recommendation = get_smart_bet(event_title, market_question or "", market_type, line_value, league, sharp_side_str, m)
            
            return {
                    "Source": "🔵 Polymarket",
                    "League": league,
                    "Event": normalize_event_title(event_title),
                    "Type": market_type,
                    "Line": line_display,
                    "TeamA": team_a_name,
                    "TeamB": team_b_name,
                    "SideA_Odds": side_a['odds'],
                    "SideB_Odds": side_b['odds'],
                    "SideA_Liquidity": int(round(side_a['liquidity'], 0)),
                    "SideB_Liquidity": int(round(side_b['liquidity'], 0)),
                    "SideA_Wall": int(round(side_a['wall'], 0)),
                    "SideB_Wall": int(round(side_b['wall'], 0)),
                    "TotalLiquidityA": int(round(sides_data['total_liquidity_a'], 0)),
                    "TotalLiquidityB": int(round(sides_data['total_liquidity_b'], 0)),
                    "SharpSide": sharp_side,
                    "SharpOdds": sharp_odds,
                    "SharpLiquidity": int(round(sharp_liquidity, 0)),
                    "Bet": bet_recommendation,
                    "Orderbook": {
                        'side_a': side_a['levels'],
                        'side_b': side_b['levels']
                    }
                }
            except Exception:
                return None
        
        # Process markets
        try:
            for e in all_events:
                markets = e.get('markets', [])
                for m in markets:
                    r = process_market(e, m)
                    if r:
                        results.append(r)
        except Exception as e:
            logger.error(f"Polymarket processing error: {e}")
    
    except Exception as e:
        logger.error(f"Polymarket CRITICAL ERROR: {e}")
        return []
    
    # RELAXED: Skip main line selector for now - show all markets for testing
    # results = select_main_line(results)
    
    logger.info(f"Polymarket: Returning {len(results)} markets (main line selector DISABLED)")
    return results

def fetch_sx_bet_markets() -> List[Dict]:
    """
    SX Bet: Filter by leagueLabel, Shadow Mode (Odds N/A, Liquidity -1).
    """
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        url = "https://api.sx.bet/markets/active"
        res = requests.get(url, headers=headers, timeout=5.0)
        
        if res.status_code != 200:
            return []
        
        try:
            data = res.json()
        except Exception:
            return []
        
        # Extract markets
        markets = []
        if isinstance(data, dict):
            if 'data' in data:
                if isinstance(data['data'], dict):
                    markets = data['data'].get('markets', [])
                elif isinstance(data['data'], list):
                    markets = data['data']
            else:
                markets = data.get('markets', [])
        elif isinstance(data, list):
            markets = data
        
        logger.info(f"SX Bet: Fetched {len(markets)} markets")
        
        if not markets:
            return []
        
        # Filter by leagueLabel
        target_leagues = ['NFL', 'NBA', 'NHL', 'NCAA']
        sports_markets = []
        
        for m in markets:
            try:
                league = str(m.get('leagueLabel', '')).upper()
                if league in target_leagues:
                    # GATEKEEPER: Must be valid game
                    team1 = m.get('teamOneName', '')
                    team2 = m.get('teamTwoName', '')
                    event_title = f"{team1} vs {team2}"
                    if is_valid_game(event_title):
                        sports_markets.append(m)
            except Exception:
                continue
        
        logger.info(f"SX Bet: Found {len(sports_markets)} valid sports markets")
        
        def process_market(m):
            try:
                team1 = m.get('teamOneName', m.get('team1', 'Team 1'))
                team2 = m.get('teamTwoName', m.get('team2', 'Team 2'))
                event_name = f"{team1} vs {team2}"
                
                line = m.get('line', m.get('spread', m.get('total', '')))
                outcome_one = m.get('outcomeOneName', '')
                
                # TYPE DETECTION: Structural field analysis (returns type, line_value)
                market_type, line_value = detect_sx_bet_type(outcome_one, line)
                
                # LEAGUE DETECTION: Use team names, not API tags
                league = detect_league(event_name)
                
                # MAIN LINE FILTER: Discard props/derivatives
                if not is_main_line(market_type, line_value, league):
                    return None
                
                # Extract team names for spreads/totals
                if market_type == "Moneyline":
                    team_a_name = team1
                    team_b_name = team2
                elif market_type == "Spread":
                    # Extract which team the spread applies to from outcome name
                    outcome_lower = (outcome_one or "").lower()
                    if team1.lower() in outcome_lower or outcome_lower in team1.lower():
                        team_a_name = team1
                        team_b_name = team2
                    elif team2.lower() in outcome_lower or outcome_lower in team2.lower():
                        team_a_name = team2
                        team_b_name = team1
                    else:
                        team_a_name = team1
                        team_b_name = team2
                elif market_type == "Total":
                    team_a_name = "Over"
                    team_b_name = "Under"
                else:
                    team_a_name = team1
                    team_b_name = team2
                
                # Format line for display (with Over/Under for Totals)
                if line_value is not None:
                    if market_type == "Spread":
                        line_display = f"{line_value:+.1f}" if line_value != int(line_value) else f"{int(line_value):+d}"
                    elif market_type == "Total":
                        # Extract Over/Under from outcome name
                        outcome_lower = (outcome_one or "").lower()
                        is_over = "over" in outcome_lower
                        over_under = "Over" if is_over else "Under"
                        line_display = f"{over_under} {line_value:.1f}" if line_value != int(line_value) else f"{over_under} {int(line_value)}"
                    else:
                        line_display = f"{line_value:.1f}" if line_value != int(line_value) else f"{int(line_value)}"
                else:
                    line_display = "—"
                
                # Generate bet recommendation (Shadow Mode: Odds N/A)
                bet_recommendation = get_smart_bet(event_name, outcome_one or "", market_type, line_value, league, "Yes", m)
                
                return {
                    "Source": "🟣 SX Bet",
                    "League": league,
                    "Event": normalize_event_title(event_name),
                    "Type": market_type,
                    "Line": line_display,
                    "TeamA": team_a_name,
                    "TeamB": team_b_name,
                    "Bet": bet_recommendation,
                    "Best Available": "N/A",
                    "RawOdds": 0,
                    "Liquidity @ Best": -1.0,  # Shadow mode
                    "Wall": -1.0,
                    "Orderbook": {'asks': [], 'bids': []}
                }
            except Exception:
                return None
        
        # Process all sports markets
        try:
            for m in sports_markets:
                r = process_market(m)
                if r:
                    results.append(r)
        except Exception as e:
            logger.error(f"SX Bet processing error: {e}")
    
    except Exception as e:
        logger.error(f"SX Bet CRITICAL ERROR: {e}")
        return []
    
    logger.info(f"SX Bet: Returning {len(results)} markets")
    return results

# --- 🔄 AGGREGATOR ---

def fetch_all_opportunities(fetchers: List[Callable[[], List[Dict]]]) -> List[Dict]:
    """
    FULL DATA DUMPS - Fast parallel fetching of complete datasets from all sources.
    """
    all_results = []
    
    logger.info("🚀 Starting FULL DATA DUMP from all sources (parallel)...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=len(fetchers)) as executor:
        futures = {executor.submit(fetcher): fetcher.__name__ for fetcher in fetchers}
        
        for future in as_completed(futures):
            source_name = futures[future].replace('fetch_', '').replace('_markets', '').title()
            try:
                results = future.result()
                if results:
                    all_results.extend(results)
                logger.info(f"✅ {source_name}: Found {len(results)} markets")
            except Exception as e:
                logger.error(f"❌ {source_name} FAILED: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    elapsed = time.time() - start_time
    logger.info(f"⚡ FULL DUMP COMPLETE: {len(all_results)} total markets in {elapsed:.2f}s")
    logger.info(f"📊 UI Update: Sending {len(all_results)} Markets to Frontend")
    return all_results

# --- 🔄 CROSS-EXCHANGE AGGREGATION & PRICE TRACKING ---

def aggregate_markets_across_exchanges(markets: List[Dict]) -> List[Dict]:
    """
    Aggregate markets across exchanges to find best prices for each side.
    Groups by (Event, Type, Line, TeamA, TeamB) to ensure correct game matching.
    CRITICAL: Must match exact games - don't mix Suns vs Timberwolves with Suns vs Thunder.
    """
    if not markets:
        return []
    
    # Group by (Event, Type, Line, TeamA, TeamB) to ensure correct matching
    grouped = {}
    for market in markets:
        event = market.get('Event', '')
        m_type = market.get('Type', '')
        line = market.get('Line', '')
        team_a = market.get('TeamA', '')
        team_b = market.get('TeamB', '')
        
        # Create unique key that includes teams to prevent mixing different games
        # Normalize line by extracting just the number (remove team names)
        line_normalized = line
        if m_type == "Spread":
            # Extract just the number from line (e.g., "Suns +9.5" -> "+9.5")
            line_match = re.search(r'([-+]?\d+\.?\d*)', str(line))
            if line_match:
                line_normalized = line_match.group(1)
        
        # Use normalized line for grouping, but keep original line for display
        key = (event, m_type, line_normalized, team_a, team_b)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(market)
    
    aggregated = []
    for key, group_markets in grouped.items():
        event, m_type, line_normalized, team_a_key, team_b_key = key
        
        # Use the original line from the first market (may include team name)
        line = group_markets[0].get('Line', line_normalized)
        
        # Find best prices across all exchanges for each side
        best_side_a = None
        best_side_b = None
        best_side_a_odds = None
        best_side_b_odds = None
        best_side_a_source = None
        best_side_b_source = None
        total_liq_a = 0.0
        total_liq_b = 0.0
        all_sources = []
        
        for m in group_markets:
            all_sources.append(m.get('Source', ''))
            
            # Check if market has new structure (SideA_Odds) or old structure (RawOdds)
            if 'SideA_Odds' in m:
                # New structure: has both sides
                side_a_odds = m.get('SideA_Odds')
                # Try both field name variations
                side_a_liq = m.get('TotalLiquidityA', m.get('SideA_TotalLiquidity', 0))
                if side_a_odds is not None:
                    total_liq_a += float(side_a_liq or 0)
                    if best_side_a_odds is None or (side_a_odds < best_side_a_odds if side_a_odds < 0 else side_a_odds > best_side_a_odds):
                        best_side_a_odds = side_a_odds
                        best_side_a = m
                        best_side_a_source = m.get('Source', '')
                
                side_b_odds = m.get('SideB_Odds')
                # Try both field name variations
                side_b_liq = m.get('TotalLiquidityB', m.get('SideB_TotalLiquidity', 0))
                if side_b_odds is not None:
                    total_liq_b += float(side_b_liq or 0)
                    if best_side_b_odds is None or (side_b_odds > best_side_b_odds if side_b_odds > 0 else side_b_odds < best_side_b_odds):
                        best_side_b_odds = side_b_odds
                        best_side_b = m
                        best_side_b_source = m.get('Source', '')
            else:
                # Old structure: only has RawOdds (treat as Side A for now)
                raw_odds = m.get('RawOdds')
                raw_liq = m.get('Liquidity @ Best', 0)
                if raw_odds is not None and raw_odds != 0:
                    total_liq_a += raw_liq
                    if best_side_a_odds is None or (raw_odds < best_side_a_odds if raw_odds < 0 else raw_odds > best_side_a_odds):
                        best_side_a_odds = raw_odds
                        best_side_a = m
                        best_side_a_source = m.get('Source', '')
        
        # Determine sharp side (LOWER liquidity = sharp side, because sharps bet early)
        # Higher liquidity = public money (late money)
        sharp_side = "B" if total_liq_a > total_liq_b else "A"
        sharp_odds = best_side_b_odds if sharp_side == "B" else best_side_a_odds
        sharp_liquidity = total_liq_b if sharp_side == "B" else total_liq_a
        
        # Get team names from first market
        first_market = group_markets[0]
        team_a = first_market.get('TeamA', 'Team A')
        team_b = first_market.get('TeamB', 'Team B')
        league = first_market.get('League', 'Unknown')
        
        # Calculate imbalance ratio (higher number = more imbalance)
        # If A has more liquidity, ratio = A/B. If B has more, ratio = B/A
        if total_liq_a > total_liq_b and total_liq_b > 0:
            imbalance_ratio = total_liq_a / total_liq_b
        elif total_liq_b > total_liq_a and total_liq_a > 0:
            imbalance_ratio = total_liq_b / total_liq_a
        else:
            imbalance_ratio = 1.0
        
        # Calculate no-vig (fair) prices
        no_vig = calculate_no_vig_price(best_side_a_odds, best_side_b_odds)
        
        # Generate bet recommendation for sharp side with actual team names
        sharp_side_name = team_a if sharp_side == "A" else team_b
        
        # Extract line value from line string (remove team name if present)
        line_str = str(line)
        # Remove team name from line if present (e.g., "Suns +9.5" -> "+9.5")
        line_match = re.search(r'([-+]?\d+\.?\d*)', line_str)
        clean_line = line_match.group(1) if line_match else line_str
        
        if m_type == "Moneyline":
            bet_rec = f"Bet: {sharp_side_name} ML"
        elif m_type == "Spread":
            # Show team name with spread
            bet_rec = f"Bet: {sharp_side_name} {clean_line}"
        elif m_type == "Total":
            # Line already includes "Over" or "Under"
            bet_rec = f"Bet: {line}"
        else:
            bet_rec = f"Bet: {sharp_side_name}"
        
        aggregated.append({
            "Event": event,
            "League": league,
            "Type": m_type,
            "Line": line,
            "TeamA": team_a,
            "TeamB": team_b,
            "SideA_BestOdds": best_side_a_odds,
            "SideB_BestOdds": best_side_b_odds,
            "SideA_BestSource": best_side_a_source,
            "SideB_BestSource": best_side_b_source,
            "SideA_FairOdds": no_vig.get('side_a_fair'),
            "SideB_FairOdds": no_vig.get('side_b_fair'),
            "Vig": no_vig.get('vig'),
            "SideA_TotalLiquidity": int(round(total_liq_a, 0)),
            "SideB_TotalLiquidity": int(round(total_liq_b, 0)),
            "SharpSide": sharp_side,
            "SharpOdds": sharp_odds,
            "SharpLiquidity": int(round(sharp_liquidity, 0)),
            "ImbalanceRatio": round(imbalance_ratio, 2),
            "Bet": bet_rec,
            "Sources": ", ".join(set(all_sources)),
            "RawMarkets": group_markets  # Keep original for drill-down
        })
    
    return aggregated

def track_price_movements(current_markets: List[Dict], previous_markets: Dict, movement_threshold: float = 0.025) -> List[Dict]:
    """
    Track price movements using VWAP (Volume-Weighted Average Price) to detect REAL steam.
    Filters out slippage (fake moves on low liquidity) from real steam (moves backed by volume).
    
    CRITICAL: Uses orderbook data to calculate VWAP, not just last traded price.
    Only alerts if:
    1. Liquidity depth > $500 in top 3 levels
    2. VWAP move > threshold (2.5% default)
    3. Move is backed by volume (not just one small trade)
    
    previous_markets: Dict keyed by (Event, Type, Line) -> {
        'timestamp': float, 
        'side_a_odds': int, 
        'side_b_odds': int,
        'orderbook': Dict  # Full orderbook for VWAP calculation
    }
    movement_threshold: Percentage change required to trigger alert (default 0.025 = 2.5%)
    """
    if not previous_markets:
        return current_markets
    
    # Import VWAP steam detector functions
    try:
        from steam_detector_vwap import analyze_steam, calculate_liquidity_depth
        use_vwap = True
    except ImportError:
        logger.warning("steam_detector_vwap not found, falling back to simple price tracking")
        use_vwap = False
    
    try:
        from imbalance_detector import check_imbalance
        use_imbalance = True
    except ImportError:
        logger.warning("imbalance_detector not found, skipping whale detection")
        use_imbalance = False
    
    try:
        from market_filters import passes_quality_filters
        use_quality_filters = True
    except ImportError:
        logger.warning("market_filters not found, skipping quality filters")
        use_quality_filters = False
    
    current_time = time.time()
    
    for market in current_markets:
        key = (market.get('Event', ''), market.get('Type', ''), market.get('Line', ''))
        
        # Filter: Ignore markets with <$5k total volume (24h volume check)
        total_liq = market.get('SideA_TotalLiquidity', 0) + market.get('SideB_TotalLiquidity', 0)
        if total_liq < 5000:
            market['PriceMove'] = None
            market['IsWhale'] = False
            continue
        
        # Get current orderbook for VWAP calculation and imbalance detection
        current_orderbook = market.get('Orderbook', {})
        source = "Kalshi" if "🟢" in market.get('Source', '') else "Polymarket"
        
        # GATEKEEPER FILTERS: Apply quality filters BEFORE Steam/Whale detection
        if use_quality_filters and current_orderbook:
            quality_check = passes_quality_filters(current_orderbook, source)
            
            # Store filter results for display
            market['MidpointPrice'] = quality_check.get('midpoint')
            market['SpreadWidth'] = quality_check.get('spread_width')
            market['QualityFilterReason'] = quality_check.get('reason')
            
            if not quality_check['passes']:
                # FAILED quality filters - skip Steam and Whale detection
                market['PriceMove'] = None
                market['IsWhale'] = False
                continue  # Skip to next market
        else:
            # No quality filters available - proceed with analysis
            market['MidpointPrice'] = None
            market['SpreadWidth'] = None
        
        # Check for liquidity imbalance / order walls (WHALES) - runs on every scan
        if use_imbalance and current_orderbook:
            imbalance_result = check_imbalance(
                orderbook=current_orderbook,
                source=source,
                min_dominant_size=5000.0,  # $5,000 minimum
                min_imbalance_ratio=4.0,  # 4x minimum
                max_spread_cents=2.0,  # 2 cents max for Kalshi
                max_spread_pct=0.03  # 3% max for Polymarket
            )
            
            if imbalance_result['is_whale']:
                market['IsWhale'] = True
                market['WhaleMessage'] = imbalance_result['message']
                market['WhaleImbalanceRatio'] = imbalance_result['imbalance_ratio']
                market['WhaleDominantSide'] = imbalance_result['dominant_side']
                market['WhaleBidDepth'] = imbalance_result['bid_depth']
                market['WhaleAskDepth'] = imbalance_result['ask_depth']
                market['WhaleOdds'] = imbalance_result['odds']
                
                # Track whale for dam break detection
                try:
                    from dam_break_detector import track_whale
                    from imbalance_detector import calculate_market_depth
                    
                    # Get whale price and volume
                    dominant_side = imbalance_result['dominant_side']
                    dominant_depth = imbalance_result['bid_depth'] if dominant_side == 'B' else imbalance_result['ask_depth']
                    
                    # Get price from dominant side
                    if dominant_side == "A":
                        dominant_levels = current_orderbook.get('side_a', {}).get('levels', [])
                    else:
                        dominant_levels = current_orderbook.get('side_b', {}).get('levels', [])
                    
                    if dominant_levels:
                        whale_price = dominant_levels[0].get('price', 0)
                        if source == "Kalshi":
                            whale_price_prob = whale_price / 100.0  # Convert cents to probability
                        else:
                            whale_price_prob = whale_price  # Already probability
                        
                        track_whale(
                            market_id=str(key),
                            side=dominant_side,
                            price=whale_price_prob,
                            volume=dominant_depth,
                            timestamp=current_time
                        )
                except ImportError:
                    pass  # Dam break detector not available
                except Exception as e:
                    logger.warning(f"Whale tracking error: {e}")
            else:
                market['IsWhale'] = False
        else:
            market['IsWhale'] = False
        
        # Check for dam break (whale wall consumed) - runs on every scan
        try:
            from dam_break_detector import check_dam_break
            from imbalance_detector import calculate_market_depth
            
            # Calculate current depths for dam break check
            side_a_levels = current_orderbook.get('side_a', {}).get('levels', [])
            side_b_levels = current_orderbook.get('side_b', {}).get('levels', [])
            current_side_a_depth = calculate_market_depth(side_a_levels, source, top_n=3) if side_a_levels else 0
            current_side_b_depth = calculate_market_depth(side_b_levels, source, top_n=3) if side_b_levels else 0
            
            dam_break_result = check_dam_break(
                market_id=str(key),
                current_orderbook=current_orderbook,
                current_side_a_depth=current_side_a_depth,
                current_side_b_depth=current_side_b_depth,
                source=source,
                time_window=60.0,
                volume_drop_threshold=0.80
            )
            
            if dam_break_result and dam_break_result.get('is_dam_break'):
                market['IsDamBreak'] = True
                market['DamBreakMessage'] = dam_break_result['message']
                market['DamBreakDirection'] = dam_break_result['direction']
                market['DamBreakPriceChange'] = dam_break_result['price_change_pct']
                market['DamBreakVolumeDrop'] = dam_break_result['volume_drop']
            else:
                market['IsDamBreak'] = False
        except ImportError:
            market['IsDamBreak'] = False
        except Exception as e:
            logger.warning(f"Dam break check error: {e}")
            market['IsDamBreak'] = False
        
        if key in previous_markets:
            prev_data = previous_markets[key]
            prev_time = prev_data.get('timestamp', 0)
            
            # Use VWAP-based detection if available and orderbook data exists
            if use_vwap and current_orderbook:
                prev_orderbook = prev_data.get('orderbook', {})
                
                # Check if within 60 seconds (expanded from 15s for steam detection)
                if current_time - prev_time <= 60 and prev_orderbook:
                    # Use VWAP-based steam detection (filters out slippage)
                    steam_result = analyze_steam(
                        previous_orderbook=prev_orderbook,
                        current_orderbook=current_orderbook,
                        min_liquidity=1000.0,  # Need $1k liquidity for VWAP calculation
                        min_depth=1000.0,  # REQUIREMENT: Must be $1000+ to buy at current price (was $500)
                        movement_threshold=movement_threshold,  # 2.5% default
                        source=source
                    )
                    
                    if steam_result['is_steam']:
                        # REAL STEAM DETECTED - backed by volume
                        move_pct = abs(steam_result['move_pct'])
                        direction = steam_result['direction']
                        
                        market['PriceMove'] = f"{move_pct*100:.1f}%"
                        market['PriceMoveDirection'] = "UP" if direction == "UP" else "DOWN"
                        market['SteamMessage'] = steam_result['message']
                        market['LiquidityDepth'] = steam_result['liquidity_depth']
                        market['VWAP_Prev'] = steam_result['effective_price_prev']
                        market['VWAP_Curr'] = steam_result['effective_price_curr']
                        
                        # Determine bet recommendation based on direction
                        if direction == "UP":
                            # Price moved UP = YES side got more expensive = bet YES
                            market['BetRecommendation'] = f"STEAM: Buy YES - Price moved {move_pct*100:.1f}% on ${steam_result['liquidity_depth']:.0f} depth"
                        else:  # DOWN
                            # Price moved DOWN = YES side got cheaper = bet NO (or sell YES)
                            market['BetRecommendation'] = f"STEAM: Buy NO - Price dropped {move_pct*100:.1f}% on ${steam_result['liquidity_depth']:.0f} depth"
                    else:
                        # Not steam (either no move or low liquidity)
                        market['PriceMove'] = None
                        if steam_result.get('message', '').startswith("IGNORE"):
                            market['SteamFilterReason'] = steam_result['message']
                else:
                    market['PriceMove'] = None
            else:
                # Fallback to simple price tracking if VWAP not available
                side_a_odds = market.get('SideA_BestOdds')
                side_b_odds = market.get('SideB_BestOdds')
                prev_side_a = prev_data.get('side_a_odds')
                prev_side_b = prev_data.get('side_b_odds')
                
                if (side_a_odds or side_b_odds) and (prev_side_a or prev_side_b):
                    # Check if within 15 seconds
                    if current_time - prev_time <= 15:
                        # Simple price tracking (fallback)
                        max_change = 0.0
                        move_direction = None
                        prev_odds = None
                        current_odds = None
                        
                        # Check Side A movement
                        if prev_side_a and side_a_odds:
                            if prev_side_a < 0 and side_a_odds < 0:
                                change = abs((abs(side_a_odds) - abs(prev_side_a)) / abs(prev_side_a))
                                if change > max_change:
                                    max_change = change
                                    move_direction = "FAVORITE_WORSE" if abs(side_a_odds) < abs(prev_side_a) else "FAVORITE_BETTER"
                                    prev_odds = prev_side_a
                                    current_odds = side_a_odds
                        
                        if max_change >= movement_threshold:
                            market['PriceMove'] = f"{max_change*100:.1f}%"
                            market['PriceMoveDirection'] = move_direction
                            market['PreviousOdds'] = prev_odds
                            market['CurrentOdds'] = current_odds
                            market['BetRecommendation'] = f"Price moved {max_change*100:.1f}%"
                        else:
                            market['PriceMove'] = None
                    else:
                        market['PriceMove'] = None
                else:
                    market['PriceMove'] = None
        else:
            market['PriceMove'] = None
    
    return current_markets

# --- 📊 PRICE LADDER (Order Book Visualization) ---

def calculate_no_vig_price(side_a_odds: Optional[int], side_b_odds: Optional[int]) -> Dict:
    """
    Calculate no-vig (fair) prices from both sides.
    Returns: {'side_a_fair': int, 'side_b_fair': int, 'vig': float}
    """
    if side_a_odds is None or side_b_odds is None:
        return {'side_a_fair': None, 'side_b_fair': None, 'vig': None}
    
    # Convert to implied probabilities
    def odds_to_prob(odds):
        if odds > 0:
            return 100.0 / (odds + 100.0)
        else:
            return abs(odds) / (abs(odds) + 100.0)
    
    prob_a = odds_to_prob(side_a_odds)
    prob_b = odds_to_prob(side_b_odds)
    total_prob = prob_a + prob_b
    
    # Remove vig (normalize to 100%)
    fair_prob_a = prob_a / total_prob
    fair_prob_b = prob_b / total_prob
    
    # Convert back to odds - FIXED: For balanced markets, should show +100/-100
    def prob_to_odds(prob):
        if prob >= 0.5:
            val = (prob / (1 - prob)) * 100
            return int(round(-val))
        else:
            val = ((1 - prob) / prob) * 100
            return int(round(val))
    
    fair_odds_a = prob_to_odds(fair_prob_a)
    fair_odds_b = prob_to_odds(fair_prob_b)
    
    vig = (total_prob - 1.0) * 100  # Vig as percentage
    
    return {
        'side_a_fair': fair_odds_a,
        'side_b_fair': fair_odds_b,
        'vig': vig
    }

def calculate_implied_price(team_a_odds: Optional[int]) -> Optional[int]:
    """
    Calculate implied price for the opponent.
    If Team A is +126, Team B is roughly -126 (minus vig).
    """
    if team_a_odds is None:
        return None
    
    # Simple conversion: +126 -> -126 (approximate, ignoring vig)
    if team_a_odds > 0:
        return -team_a_odds
    else:
        return abs(team_a_odds)

def render_price_ladder(orderbook_levels: Dict, team_a: str = "Team A", team_b: str = "Team B", unique_key: str = ""):
    """
    Render a Price Ladder showing liquidity walls at each price level.
    Horizontal bars: Left (Team A/Yes), Right (Team B/No).
    """
    if not PLOTLY_AVAILABLE:
        st.info("Plotly not available for price ladder")
        return
    
    # Support both old format (asks/bids) and new format (side_a/side_b)
    if 'side_a' in orderbook_levels and 'side_b' in orderbook_levels:
        asks = orderbook_levels.get('side_a', [])[:5]  # Top 5 levels
        bids = orderbook_levels.get('side_b', [])[:5]
    else:
        asks = orderbook_levels.get('asks', [])[:5]  # Top 5 levels
        bids = orderbook_levels.get('bids', [])[:5]
    
    if not asks and not bids:
        st.info("No orderbook data available")
        return
    
    # Prepare data for chart - combine all price levels
    all_prices = set()
    price_to_ask_liq = {}
    price_to_bid_liq = {}
    
    for level in asks:
        odds = level.get('odds')
        if odds:
            all_prices.add(odds)
            price_to_ask_liq[odds] = level.get('liquidity', 0)
    
    for level in bids:
        odds = level.get('odds')
        if odds:
            all_prices.add(odds)
            price_to_bid_liq[odds] = level.get('liquidity', 0)
    
    # Sort prices
    sorted_prices = sorted(all_prices, reverse=True)
    
    # Create data arrays
    ask_liq = [price_to_ask_liq.get(p, 0) for p in sorted_prices]
    bid_liq = [price_to_bid_liq.get(p, 0) for p in sorted_prices]
    price_labels = [format_odds(p) for p in sorted_prices]
    
    # Create figure
    fig = go.Figure()
    
    # Add Team A bars (extending left, negative values)
    if any(ask_liq):
        fig.add_trace(go.Bar(
            y=price_labels,
            x=[-liq for liq in ask_liq],  # Negative to extend left
            orientation='h',
            name=f"{team_a} (Ask/Buy)",
            marker_color='#00cc96',  # Green/Blue
            text=[f'${liq:,.0f}' if liq > 0 else '' for liq in ask_liq],
            textposition='outside',
            hovertemplate=f'{team_a} (Ask/Buy)<br>Price: %{{y}}<br>Liquidity: $%{{text}}<extra></extra>'
        ))
    
    # Add Team B bars (extending right, positive values)
    if any(bid_liq):
        fig.add_trace(go.Bar(
            y=price_labels,
            x=bid_liq,  # Positive to extend right
            orientation='h',
            name=f"{team_b} (Bid/Sell)",
            marker_color='#ef553b',  # Red/Orange
            text=[f'${liq:,.0f}' if liq > 0 else '' for liq in bid_liq],
            textposition='outside',
            hovertemplate=f'{team_b} (Bid/Sell)<br>Price: %{{y}}<br>Liquidity: $%{{text}}<extra></extra>'
        ))
    
    # Update layout for professional look
    fig.update_layout(
        title=f"Market Depth: {team_a} vs {team_b}",
        xaxis_title="Liquidity ($)",
        yaxis_title="Price (American Odds)",
        barmode='overlay',
        height=300,
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white', size=10),
        xaxis=dict(
            gridcolor='#333333',
            zeroline=True,
            zerolinecolor='white',
            zerolinewidth=2,
            showgrid=True
        ),
        yaxis=dict(
            gridcolor='#333333',
            side='right',
            showgrid=True
        ),
        legend=dict(
            bgcolor='rgba(0,0,0,0)',
            bordercolor='white',
            borderwidth=1,
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        margin=dict(l=0, r=0, t=60, b=0)
    )
    
    # Use unique key to prevent duplicate element ID crash
    chart_key = f"price_ladder_{unique_key}_{uuid.uuid4()}" if unique_key else f"price_ladder_{uuid.uuid4()}"
    st.plotly_chart(fig, use_container_width=True, key=chart_key)

# --- 🖥️ UI (Dashboard) ---

# Add view selector
view_mode = st.radio(
    "View Mode",
    ["🎯 Spot Finder (Outsized Liquidity)", "📊 Sharp Money Scanner"],
    horizontal=True,
    help="Spot Finder: Find arbitrage opportunities with high liquidity. Scanner: Track sharp money and price movements."
)

if view_mode == "🎯 Spot Finder (Outsized Liquidity)":
    st.title("🎯 Arbitrage Spot Finder")
    st.markdown("**Find outsized liquidity spots - Compare exchange best prices to your soft book**")
else:
    st.title("Sharp Money Scanner")

# Initialize session state
if 'data' not in st.session_state:
    st.session_state['data'] = []
if 'last_update' not in st.session_state:
    st.session_state['last_update'] = datetime.now()
if 'previous_prices' not in st.session_state:
    st.session_state['previous_prices'] = {}  # Track price movements
if 'movement_threshold' not in st.session_state:
    st.session_state['movement_threshold'] = 0.025  # Default 2.5% for VWAP-based detection

# DRAW FIRST: Display existing data immediately
df = pd.DataFrame(st.session_state['data'])

with st.sidebar:
    st.header("Steam Move Detection")
    # CRITICAL: Allow user to adjust threshold for steam moves
    movement_threshold_pct = st.slider(
        "Steam Move Threshold (%)", 
        min_value=1, 
        max_value=10, 
        value=int(st.session_state.get('movement_threshold', 0.025) * 100),  # Default 2.5% for VWAP-based detection
        help="VWAP change required to trigger steam alert. 2.5% = standard for sharp moves. Lower = more sensitive (may catch noise)."
    )
    movement_threshold = movement_threshold_pct / 100.0  # Convert to decimal
    st.session_state['movement_threshold'] = movement_threshold  # Store in session state
    
    st.info("💡 **VWAP-Based Detection:** Only alerts on moves backed by $500+ liquidity depth. Filters out slippage.")
    
    st.header("Filters")
    # WIDE OPEN DEFAULTS (hard $1k filter enforced in Python)
    min_liq = st.slider("Min Liquidity @ Best ($)", 0, 100000, 0)
    max_odds = st.slider("Max Odds (+/-)", 100, 5000, 5000)
    
    # Spot Finder specific controls
    if view_mode == "🎯 Spot Finder (Outsized Liquidity)":
        st.header("Spot Finder Settings")
        spot_finder_threshold = st.slider(
            "Outsized Liquidity Threshold ($)",
            min_value=10000,
            max_value=500000,
            value=st.session_state.get('spot_finder_threshold', 50000),
            step=10000,
            help="Markets with liquidity above this are highlighted as 'outsized'"
        )
        st.session_state['spot_finder_threshold'] = spot_finder_threshold
    
    st.header("Sources")
    enable_kalshi = st.checkbox("Kalshi", value=True)
    enable_polymarket = st.checkbox("Polymarket", value=True)
    enable_sx = st.checkbox("SX Bet", value=True)
    
    auto_refresh = st.checkbox("Auto-Refresh (5s) - Real-Time", value=True)
    
    if st.button("Force Refresh", type="primary"):
        st.session_state['data'] = []
        st.rerun()

# Display timestamp and refresh status
if 'last_update' in st.session_state:
    last_update_str = st.session_state['last_update'].strftime('%H:%M:%S')
    time_since_update = (datetime.now() - st.session_state['last_update']).total_seconds()
    if time_since_update < 20:
        st.success(f"✅ Last Update: {last_update_str} ({int(time_since_update)}s ago) - Real-time monitoring active")
    else:
        st.warning(f"⚠️ Last Update: {last_update_str} ({int(time_since_update)}s ago) - May need refresh")

# Display existing data immediately (DRAW FIRST)
if view_mode == "🎯 Spot Finder (Outsized Liquidity)":
    # SPOT FINDER VIEW - Focus on outsized liquidity and arbitrage opportunities
    if not df.empty:
        # Initialize threshold if not set
        if 'spot_finder_threshold' not in st.session_state:
            st.session_state['spot_finder_threshold'] = 50000
        
        # Filter by liquidity
        if 'SideA_TotalLiquidity' in df.columns and 'SideB_TotalLiquidity' in df.columns:
            df['Max_Liquidity'] = df[['SideA_TotalLiquidity', 'SideB_TotalLiquidity']].max(axis=1)
            df_filtered = df[df['Max_Liquidity'] >= st.session_state['spot_finder_threshold']].copy()
        else:
            df_filtered = df.copy()
            if 'Max_Liquidity' not in df.columns:
                df['Max_Liquidity'] = 0
        
        # Sort by liquidity (highest first)
        if 'Max_Liquidity' in df_filtered.columns:
            df_filtered = df_filtered.sort_values('Max_Liquidity', ascending=False)
        
        # Display stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Markets", len(df))
        with col2:
            st.metric("Outsized Liquidity", len(df_filtered), f"≥${st.session_state['spot_finder_threshold']:,}")
        with col3:
            if 'Max_Liquidity' in df.columns and len(df) > 0:
                avg_liq = df['Max_Liquidity'].mean()
                st.metric("Avg Max Liquidity", f"${avg_liq:,.0f}")
            else:
                st.metric("Avg Max Liquidity", "N/A")
        with col4:
            if 'Max_Liquidity' in df.columns and len(df) > 0:
                max_liq = df['Max_Liquidity'].max()
                st.metric("Highest Liquidity", f"${max_liq:,.0f}")
            else:
                st.metric("Highest Liquidity", "N/A")
        
        st.divider()
        
        # Display comparison table - Exchange Best Prices + Liquidity
        st.subheader("📊 Exchange Best Prices + Liquidity (Compare to Your Soft Book)")
        
        # Create display columns
        spot_finder_cols = ['League', 'Event', 'Type', 'Line', 'TeamA', 'TeamB',
                           'SideA_BestOdds', 'SideA_BestSource', 'SideA_TotalLiquidity', 'SideA_FairOdds',
                           'SideB_BestOdds', 'SideB_BestSource', 'SideB_TotalLiquidity', 'SideB_FairOdds',
                           'Max_Liquidity', 'ImbalanceRatio', 'Vig']
        available_spot_cols = [col for col in spot_finder_cols if col in df_filtered.columns]
        
        if available_spot_cols:
            display_df = df_filtered[available_spot_cols].copy()
            
            # Format odds
            for col in ['SideA_BestOdds', 'SideB_BestOdds', 'SideA_FairOdds', 'SideB_FairOdds']:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: format_odds(x) if pd.notna(x) and x != 0 else "N/A")
            
            # Format liquidity for display (keep raw for highlighting)
            display_df_display = display_df.copy()
            for col in ['SideA_TotalLiquidity', 'SideB_TotalLiquidity', 'Max_Liquidity']:
                if col in display_df_display.columns:
                    display_df_display[col] = display_df_display[col].apply(lambda x: f"${x:,.0f}" if pd.notna(x) and x > 0 else "N/A")
            
            # Format vig
            if 'Vig' in display_df_display.columns:
                display_df_display['Vig'] = display_df_display['Vig'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
            
            # Highlight outsized liquidity (use raw values from display_df)
            def highlight_outsized(row):
                if 'Max_Liquidity' in row.index:
                    max_liq_val = row.get('Max_Liquidity', 0)
                    if isinstance(max_liq_val, (int, float)) and max_liq_val >= st.session_state['spot_finder_threshold']:
                        return ['background-color: #2d5016; color: white; font-weight: bold'] * len(row)
                return [''] * len(row)
            
            # Apply highlighting to raw dataframe, then format for display
            styled_df = display_df.style.apply(highlight_outsized, axis=1)
            # Convert to display format
            for col in ['SideA_TotalLiquidity', 'SideB_TotalLiquidity', 'Max_Liquidity']:
                if col in styled_df.data.columns:
                    styled_df.data[col] = styled_df.data[col].apply(lambda x: f"${x:,.0f}" if pd.notna(x) and x > 0 else "N/A")
            
            st.dataframe(styled_df, height=600, use_container_width=True)
            
            # Show top opportunities
            st.divider()
            st.subheader("🔥 Top Opportunities (Highest Liquidity)")
            
            top_5 = df_filtered.head(5)
            for idx, row in top_5.iterrows():
                event = row.get('Event', 'Unknown')
                m_type = row.get('Type', '')
                line = row.get('Line', '')
                max_liq = row.get('Max_Liquidity', 0)
                side_a_odds = row.get('SideA_BestOdds', 'N/A')
                side_b_odds = row.get('SideB_BestOdds', 'N/A')
                side_a_source = row.get('SideA_BestSource', '')
                side_b_source = row.get('SideB_BestSource', '')
                side_a_liq = row.get('SideA_TotalLiquidity', 0)
                side_b_liq = row.get('SideB_TotalLiquidity', 0)
                side_a_fair = row.get('SideA_FairOdds', 'N/A')
                side_b_fair = row.get('SideB_FairOdds', 'N/A')
                imbalance = row.get('ImbalanceRatio', 1.0)
                
                with st.expander(f"**{event}** | {m_type} {line} | Max Liquidity: ${max_liq:,.0f}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Side A (Exchange Best)**")
                        st.metric("Price", format_odds(side_a_odds) if isinstance(side_a_odds, (int, float)) else side_a_odds)
                        st.caption(f"Source: {side_a_source}")
                        st.caption(f"Liquidity: ${side_a_liq:,.0f}")
                        st.caption(f"Fair Price: {format_odds(side_a_fair) if isinstance(side_a_fair, (int, float)) else side_a_fair}")
                        st.info("💡 **Compare to your soft book - if better, you have an edge!**")
                    
                    with col2:
                        st.write("**Side B (Exchange Best)**")
                        st.metric("Price", format_odds(side_b_odds) if isinstance(side_b_odds, (int, float)) else side_b_odds)
                        st.caption(f"Source: {side_b_source}")
                        st.caption(f"Liquidity: ${side_b_liq:,.0f}")
                        st.caption(f"Fair Price: {format_odds(side_b_fair) if isinstance(side_b_fair, (int, float)) else side_b_fair}")
                        st.info("💡 **Compare to your soft book - if better, you have an edge!**")
                    
                    st.caption(f"Imbalance Ratio: {imbalance:.2f}x | Vig: {row.get('Vig', 'N/A')}")
        else:
            st.info("No data available for spot finder view.")
    else:
        st.info("No data available. Waiting for market data...")

elif not df.empty:
    # Filter existing data - use SharpLiquidity for filtering
    if 'SharpLiquidity' in df.columns:
        df_filtered = df[df['SharpLiquidity'] >= min_liq]
    else:
        df_filtered = df
    
    # Filter by odds if available
    if 'SharpOdds' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['SharpOdds'].abs() <= max_odds]
    
    # Sort by Sharp Liquidity DESC (sharp money indicator)
    if 'SharpLiquidity' in df_filtered.columns:
        df_filtered = df_filtered.sort_values(by='SharpLiquidity', ascending=False)
    
    # Sort by price moves first (big moves at top), then by sharp liquidity
    if 'PriceMove' in df_filtered.columns:
        df_filtered['HasMove'] = df_filtered['PriceMove'].notna()
        df_filtered = df_filtered.sort_values(by=['HasMove', 'SharpLiquidity'], ascending=[False, False])
    else:
        df_filtered = df_filtered.sort_values(by='SharpLiquidity', ascending=False)
    
    # Select columns for display - show both sides with no-vig prices
    display_cols = ['League', 'Event', 'Type', 'Line', 'TeamA', 'TeamB', 
                   'SideA_BestOdds', 'SideB_BestOdds', 'SideA_FairOdds', 'SideB_FairOdds',
                   'Vig', 'PriceMove', 'BetRecommendation', 'SharpSide', 'SharpOdds', 
                   'SharpLiquidity', 'ImbalanceRatio', 'Bet', 'Sources']
    available_cols = [col for col in display_cols if col in df_filtered.columns]
    
    if available_cols:
        # Create a simplified display dataframe
        display_df = df_filtered[available_cols].copy()
        # Format odds columns
        for col in ['SideA_BestOdds', 'SideB_BestOdds', 'SideA_FairOdds', 'SideB_FairOdds', 'SharpOdds']:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: format_odds(x) if pd.notna(x) and x != 0 else "N/A")
        
        # Format vig
        if 'Vig' in display_df.columns:
            display_df['Vig'] = display_df['Vig'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
        
        # Highlight rows with price moves
        def highlight_moves(row):
            if pd.notna(row.get('PriceMove')):
                return ['background-color: #ff6b6b; font-weight: bold'] * len(row)
            return [''] * len(row)
        
        st.dataframe(display_df.style.apply(highlight_moves, axis=1), height=400)
        
        # Show DAM BREAK alerts (whale wall consumed) - PURPLE/MAGENTA (highest priority)
        dam_breaks_df = df_filtered[df_filtered.get('IsDamBreak', False) == True] if 'IsDamBreak' in df_filtered.columns else pd.DataFrame()
        if not dam_breaks_df.empty:
            st.markdown("### 🚨 DAM BROKEN - WHALE WALLS CONSUMED!")
            for idx, (_, row) in enumerate(dam_breaks_df.head(10).iterrows()):
                dam_break_msg = row.get('DamBreakMessage', '')
                event = row.get('Event', '')
                m_type = row.get('Type', '')
                line = row.get('Line', '')
                direction = row.get('DamBreakDirection', '')
                price_change = row.get('DamBreakPriceChange', 0)
                volume_drop = row.get('DamBreakVolumeDrop', 0)
                
                with st.container():
                    # Use purple/magenta for dam breaks (highest conviction)
                    st.markdown(f"<div style='background-color: #9b59b6; color: white; padding: 10px; border-radius: 5px; margin: 5px 0;'>"
                               f"<strong>🚨 {event}</strong> | {m_type} {line} | {dam_break_msg}</div>", 
                               unsafe_allow_html=True)
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Direction", direction)
                    with col2:
                        st.metric("Price Change", f"{price_change:.1f}%")
                    with col3:
                        st.metric("Volume Drop", f"{volume_drop*100:.0f}%")
                    st.divider()
        
        # Show WHALE alerts (liquidity imbalance) - BLUE/CYAN
        whales_df = df_filtered[df_filtered.get('IsWhale', False) == True] if 'IsWhale' in df_filtered.columns else pd.DataFrame()
        if not whales_df.empty:
            st.markdown("### 🐋 WHALE ALERTS - ORDER WALLS DETECTED")
            for idx, (_, row) in enumerate(whales_df.head(10).iterrows()):
                whale_msg = row.get('WhaleMessage', '')
                event = row.get('Event', '')
                m_type = row.get('Type', '')
                line = row.get('Line', '')
                imbalance_ratio = row.get('WhaleImbalanceRatio', 0)
                bid_depth = row.get('WhaleBidDepth', 0)
                ask_depth = row.get('WhaleAskDepth', 0)
                whale_odds = row.get('WhaleOdds', 'N/A')
                spread_width = row.get('SpreadWidth', None)
                midpoint = row.get('MidpointPrice', None)
                
                with st.container():
                    # Use blue/cyan for whales (static pressure)
                    info_text = f"**🐋 {event}** | {m_type} {line} | {whale_msg}"
                    if spread_width is not None:
                        spread_display = f"{spread_width*100:.1f}¢" if source == "Kalshi" else f"{spread_width*100:.1f}%"
                        info_text += f" | [Spread: {spread_display}]"
                    st.info(info_text)
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Imbalance Ratio", f"{imbalance_ratio:.1f}x")
                    with col2:
                        st.metric("Bid Depth", f"${bid_depth:,.0f}")
                    with col3:
                        st.metric("Ask Depth", f"${ask_depth:,.0f}")
                    with col4:
                        if midpoint is not None:
                            st.metric("Midpoint", f"{midpoint:.3f}")
                    st.divider()
        
        # Show big moves prominently at top (ALWAYS show this section) - RED for STEAM
        moves_df = df_filtered[df_filtered['PriceMove'].notna()] if 'PriceMove' in df_filtered.columns else pd.DataFrame()
        if not moves_df.empty:
            st.markdown("### 🔥 STEAM MOVES DETECTED - ACT NOW!")
            # Sort by move percentage (largest first)
            moves_df_sorted = moves_df.copy()
            if 'PriceMove' in moves_df_sorted.columns:
                moves_df_sorted['MovePctNum'] = moves_df_sorted['PriceMove'].str.rstrip('%').astype(float, errors='ignore')
                moves_df_sorted = moves_df_sorted.sort_values('MovePctNum', ascending=False, na_position='last')
            
            for idx, (_, row) in enumerate(moves_df_sorted.head(10).iterrows()):
                move_pct = row.get('PriceMove', '')
                direction = row.get('PriceMoveDirection', '')
                recommendation = row.get('BetRecommendation', '')
                event = row.get('Event', '')
                m_type = row.get('Type', '')
                line = row.get('Line', '')
                side_a_odds = row.get('SideA_BestOdds', 'N/A')
                side_b_odds = row.get('SideB_BestOdds', 'N/A')
                prev_odds = row.get('PreviousOdds', '')
                current_odds = row.get('CurrentOdds', '')
                
                # Format odds
                if isinstance(side_a_odds, (int, float)):
                    side_a_str = format_odds(side_a_odds)
                else:
                    side_a_str = str(side_a_odds)
                if isinstance(side_b_odds, (int, float)):
                    side_b_str = format_odds(side_b_odds)
                else:
                    side_b_str = str(side_b_odds)
                
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.error(f"**{event}** | {m_type} {line} | {move_pct} move | {direction}")
                        if recommendation:
                            st.warning(f"💡 {recommendation}")
                        if prev_odds and current_odds:
                            st.caption(f"Odds moved: {format_odds(prev_odds) if isinstance(prev_odds, (int, float)) else prev_odds} → {format_odds(current_odds) if isinstance(current_odds, (int, float)) else current_odds}")
                    with col2:
                        st.metric("Side A", side_a_str)
                        st.metric("Side B", side_b_str)
                    st.divider()
        else:
            threshold_pct = int(st.session_state.get('movement_threshold', 0.03) * 100)
            st.info(f"📊 No steam moves detected ({threshold_pct}%+ threshold). Monitoring for price movements in real-time...")
    
    st.success(f"Found {len(df_filtered)} Markets")
    
    # Detailed view (top 20) with Price Ladder
    for idx, (_, row) in enumerate(df_filtered.head(20).iterrows()):
        event = row.get('Event', 'Unknown')
        sharp_odds = row.get('SharpOdds', 'N/A')
        sharp_liquidity = row.get('SharpLiquidity', 0)
        bet_recommendation = row.get('Bet', '')
        team_a = row.get('TeamA', 'Team A')
        team_b = row.get('TeamB', 'Team B')
        side_a_odds = row.get('SideA_BestOdds', 'N/A')
        side_b_odds = row.get('SideB_BestOdds', 'N/A')
        side_a_liq = row.get('SideA_TotalLiquidity', 0)
        side_b_liq = row.get('SideB_TotalLiquidity', 0)
        imbalance = row.get('ImbalanceRatio', 1.0)
        price_move = row.get('PriceMove', '')
        
        # Format odds if they're numbers
        if isinstance(sharp_odds, (int, float)):
            sharp_odds_str = format_odds(sharp_odds)
        else:
            sharp_odds_str = str(sharp_odds)
        
        label = f"**{event}** | {row.get('Type', '')} {row.get('Line', '')} | Sharp: {sharp_odds_str} | ${sharp_liquidity:,.0f} | Imbalance: {imbalance}x"
        if price_move:
            label += f" | 🔥 {price_move}"
        
            with st.expander(label):
            # Explicit Snipe Signal (Large, Prominent)
            if bet_recommendation and sharp_odds_str != "N/A":
                st.markdown(f"""
                <div style="background-color: #1e3a5f; padding: 15px; border-radius: 8px; border: 2px solid #4a9eff; margin-bottom: 20px;">
                    <h3 style="color: #4a9eff; margin: 0;">🎯 TARGET: {bet_recommendation} @ {sharp_odds_str} or better</h3>
                </div>
                """, unsafe_allow_html=True)
            
                c1, c2 = st.columns([1, 2])
                with c1:
                st.write(f"**Event:** {event}")
                st.write(f"**Type:** {row.get('Type', '—')}")
                st.write(f"**Line:** {row.get('Line', '—')}")
                st.write(f"**Sources:** {row.get('Sources', '—')}")
                
                st.markdown("---")
                st.write("**Side A (Best Price):**")
                st.metric(f"{team_a}", format_odds(side_a_odds) if isinstance(side_a_odds, (int, float)) else side_a_odds, 
                         delta=f"${side_a_liq:,.0f} total", delta_color="normal")
                st.write(f"Source: {row.get('SideA_BestSource', '—')}")
                
                st.markdown("---")
                st.write("**Side B (Best Price):**")
                st.metric(f"{team_b}", format_odds(side_b_odds) if isinstance(side_b_odds, (int, float)) else side_b_odds,
                         delta=f"${side_b_liq:,.0f} total", delta_color="normal")
                st.write(f"Source: {row.get('SideB_BestSource', '—')}")
                
                st.markdown("---")
                st.write("**No-Vig Fair Prices:**")
                side_a_fair = row.get('SideA_FairOdds')
                side_b_fair = row.get('SideB_FairOdds')
                vig = row.get('Vig')
                if side_a_fair and side_b_fair:
                    st.metric(f"{team_a} Fair", format_odds(side_a_fair) if isinstance(side_a_fair, (int, float)) else side_a_fair)
                    st.metric(f"{team_b} Fair", format_odds(side_b_fair) if isinstance(side_b_fair, (int, float)) else side_b_fair)
                    if vig:
                        st.caption(f"Vig: {vig:.2f}%")
                
                st.markdown("---")
                st.write("**Sharp Money Signal:**")
                sharp_side_name = team_a if row.get('SharpSide') == 'A' else team_b
                st.metric("Sharp Side", sharp_side_name, delta=f"{imbalance}x imbalance", delta_color="inverse")
                st.metric("Sharp Odds", sharp_odds_str, delta=f"${sharp_liquidity:,.0f} liquidity")
                
                if price_move:
                    recommendation = row.get('BetRecommendation', '')
                    direction = row.get('PriceMoveDirection', '')
                    st.error(f"🔥 BIG MOVE: {price_move} {direction}")
                    if recommendation:
                        st.info(f"💡 {recommendation}")
                    st.warning("⚠️ Check soft book immediately - may not have moved yet!")
            
                with c2:
                # Price Ladder - get from raw markets
                raw_markets = row.get('RawMarkets', [])
                if raw_markets:
                    # Use first market's orderbook
                    first_market = raw_markets[0]
                    orderbook = first_market.get('Orderbook', {})
                    if orderbook:
                        # Use unique key based on event and index
                        unique_key = f"{event}_{idx}_{row.get('Type', '')}"
                        render_price_ladder(orderbook, team_a, team_b, unique_key)
                    else:
                        st.info("No orderbook data available")
                else:
                    st.info("No detailed orderbook data available")
else:
    st.info("Scanning... (Waiting for data)")

# THEN: Check if we need to fetch new data (REAL-TIME)
should_refresh = False
if auto_refresh:
    time_since_update = (datetime.now() - st.session_state['last_update']).total_seconds()
    if time_since_update >= 5:  # 5 second refresh for real-time data (was 15s)
        should_refresh = True

# Fetch new data if needed
if should_refresh or df.empty:
    # Build fetcher list
    fetchers = []
    if enable_kalshi:
        fetchers.append(fetch_kalshi_markets)
    if enable_polymarket:
        fetchers.append(fetch_polymarket_markets)
    if enable_sx:
        fetchers.append(fetch_sx_bet_markets)
    
    if fetchers:
        with st.spinner("Scanning markets..."):
            raw_data = fetch_all_opportunities(fetchers)
            # Aggregate across exchanges
            aggregated_data = aggregate_markets_across_exchanges(raw_data)
            # Track price movements with user-defined threshold
            movement_threshold = st.session_state.get('movement_threshold', 0.025)
            aggregated_data = track_price_movements(aggregated_data, st.session_state.get('previous_prices', {}), movement_threshold)
            # Update previous prices for next cycle (store both sides for proper tracking)
            current_prices = {}
            for market in aggregated_data:
                key = (market.get('Event', ''), market.get('Type', ''), market.get('Line', ''))
                current_prices[key] = {
                    'timestamp': time.time(),
                    'side_a_odds': market.get('SideA_BestOdds'),
                    'side_b_odds': market.get('SideB_BestOdds'),
                    'orderbook': market.get('Orderbook', {})  # Store full orderbook for VWAP calculation
                }
            st.session_state['previous_prices'] = current_prices
            st.session_state['data'] = aggregated_data
            st.session_state['last_update'] = datetime.now()
            logger.info(f"UI Update: Sending {len(aggregated_data)} Markets to Frontend")
        
        # Rerun to display new data
        if should_refresh or df.empty:
            st.rerun()
    else:
        st.warning("Please enable at least one data source.")
