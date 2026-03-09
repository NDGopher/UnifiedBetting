"""
Configuration constants for the Sports Liquidity Scanner.
Loads from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv
from typing import Tuple

# Load environment variables
load_dotenv()

# --- API Credentials ---
# Support both KALSHI_KEY_ID and KALSHI_API_KEY for compatibility
KALSHI_API_KEY = os.getenv("KALSHI_API_KEY", "")
KALSHI_KEY_ID = os.getenv("KALSHI_API_KEY") or os.getenv("KALSHI_KEY_ID", "")  # Alias for compatibility
KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")

# Load private key from file if path is provided, otherwise use direct value
KALSHI_PRIVATE_KEY = os.getenv("KALSHI_PRIVATE_KEY", "")
if KALSHI_PRIVATE_KEY_PATH and not KALSHI_PRIVATE_KEY:
    key_path = os.path.join(os.path.dirname(__file__), KALSHI_PRIVATE_KEY_PATH)
    if os.path.exists(key_path):
        try:
            # Read as binary first, then decode
            with open(key_path, 'rb') as f:
                key_bytes = f.read()
            
            # Try UTF-8 decode
            try:
                key_content = key_bytes.decode('utf-8')
            except:
                # Try other encodings
                key_content = key_bytes.decode('latin-1')
            
            KALSHI_PRIVATE_KEY = key_content
            print(f"✅ Loaded key file: {key_path} ({len(key_content)} chars)")
        except Exception as e:
            print(f"❌ Error: Could not read private key from {key_path}: {e}")
            KALSHI_PRIVATE_KEY = ""

# Polymarket credentials (optional)
POLY_API_KEY = os.getenv("POLY_API_KEY", "")
POLY_API_SECRET = os.getenv("POLY_API_SECRET", "")
POLY_PASSPHRASE = os.getenv("POLY_PASSPHRASE", "")

# --- Quality Filters (Gatekeeper) ---
GOLD_ZONE: Tuple[float, float] = (0.20, 0.80)  # Price range 20-80 cents
MAX_SPREAD_CENTS: float = 0.04  # Max 4 cent spread (or 4% for Polymarket)

# --- Steam Detection ---
STEAM_THRESHOLD: float = 0.025  # 2.5% move threshold
STEAM_MIN_LIQUIDITY: float = 1000.0  # $1k min volume for steam
STEAM_MIN_DEPTH: float = 1000.0  # $1k min depth in top levels
STEAM_TIME_WINDOW: int = 60  # 60 seconds for steam detection

# --- Whale Detection ---
WHALE_MIN_SIZE: float = 5000.0  # $5k min wall size
WHALE_IMBALANCE_RATIO: float = 4.0  # 4x size difference
WHALE_MAX_SPREAD_CENTS: float = 2.0  # 2 cents max for whale detection
WHALE_MAX_SPREAD_PCT: float = 0.03  # 3% max for Polymarket

# --- Dam Break Detection ---
DAM_BREAK_WINDOW: int = 60  # Seconds to remember a wall
DAM_BREAK_VOLUME_DROP: float = 0.80  # 80% volume drop threshold

# --- Market Filters ---
MIN_TOTAL_LIQUIDITY: float = 5000.0  # $5k min total market liquidity

# --- API Settings ---
KALSHI_API_HOST = "https://api.elections.kalshi.com/trade-api/v2"
POLYMARKET_CLOB_HOST = "https://clob.polymarket.com"
POLYMARKET_GAMMA_HOST = "https://gamma-api.polymarket.com"

# --- Sports Tags (Polymarket) ---
# Comprehensive list of sports tag slugs for Polymarket Gamma API
# STRICT SPORTS ONLY - NO POLITICS, NO CRYPTO, NO POP-CULTURE
SPORTS_TAGS = [
    # Major North American Sports
    "nfl",              # NFL
    "nba",              # NBA
    "nhl",              # NHL
    "mlb",              # MLB
    "wnba",             # WNBA
    "ncaa-football",    # NCAA Football
    "ncaa-basketball",  # NCAA Basketball
    "ncaa",             # General NCAA
    
    # Soccer/Football
    "soccer",           # Soccer/Football
    "premier-league",   # Premier League
    "champions-league", # Champions League
    "mls",              # MLS
    
    # Combat Sports
    "mma",              # Mixed Martial Arts
    "ufc",              # UFC
    "boxing",           # Boxing
    
    # Racquet Sports
    "tennis",           # Tennis
    
    # Golf
    "golf",             # Golf
    "pga-tour",         # PGA Tour
    
    # Motorsports
    "formula-1",        # Formula 1
    "nascar",           # NASCAR
    "motorsports",      # General Motorsports
    
    # Global Sports
    "cricket",          # Cricket
    "rugby",            # Rugby
    
    # General (use carefully - may include non-sports)
    "sports",           # General sports
]

# --- Refresh Rate ---
SCAN_INTERVAL: float = 5.0  # 5 seconds between scans

# --- Retry Settings ---
MAX_RETRIES: int = 3
RETRY_BACKOFF: float = 1.5  # Exponential backoff multiplier
REQUEST_TIMEOUT: float = 10.0  # 10 second timeout

# --- Display Settings ---
MAX_ALERTS_DISPLAY: int = 20  # Max alerts to show in table

