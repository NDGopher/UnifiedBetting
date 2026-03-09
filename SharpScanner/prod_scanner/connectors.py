"""
High-Speed Engine - Final "Search & Slug" Version.

1. Kalshi: Keeps the working "Deep Drill" (Capped at 2000 for speed).

2. Polymarket: Uses 'slug=' and 'q=' to find sports by name. No more IDs.
"""

import aiohttp
import asyncio
import logging
import time
import json
import os
from typing import List, Dict, Optional, Callable
from collections import defaultdict

# --- AUTH SETUP ---
try:
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    import base64
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

try:
    import websockets
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

try:
    from config import KALSHI_KEY_ID, KALSHI_PRIVATE_KEY, KALSHI_PRIVATE_KEY_PATH
except ImportError:
    KALSHI_KEY_ID = os.getenv("KALSHI_KEY_ID", "") or os.getenv("KALSHI_API_KEY", "")
    KALSHI_PRIVATE_KEY = os.getenv("KALSHI_PRIVATE_KEY", "")
    KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH", "kalshi.key")

logger = logging.getLogger(__name__)

# --- ENDPOINTS ---
POLY_GAMMA_URL = "https://gamma-api.polymarket.com"
POLY_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
KALSHI_WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"

# --- POLYMARKET TARGETS (Slugs & Search Terms) ---
# We use both to ensure we catch everything
POLY_TARGETS = [
    {'slug': 'nfl', 'q': 'NFL'},
    {'slug': 'nba', 'q': 'NBA'},
    {'slug': 'nhl', 'q': 'NHL'},
    {'slug': 'mlb', 'q': 'MLB'},
    {'slug': 'ufc', 'q': 'UFC'},
    {'slug': 'soccer', 'q': 'Soccer'},
    {'slug': 'ncaa', 'q': 'NCAA'}
]

# --- GLOBAL THREAD-SAFE DATA STRUCTURES ---
ORDER_BOOKS = defaultdict(lambda: {'yes': {}, 'no': {}})
TRADE_QUEUES = defaultdict(lambda: [])

# --- THREADING LOCKS ---
import threading
ORDER_BOOKS_LOCK = threading.Lock()
TRADE_QUEUES_LOCK = threading.Lock()

# --- HELPERS ---
def probability_to_american(prob: float) -> int:
    if prob <= 0 or prob >= 1: return 0
    if prob > 0.5:
        return int(round(-100 * (prob / (1 - prob))))
    else:
        return int(round(100 * ((1 - prob) / prob)))

def extract_sport_from_text(text: str) -> str:
    s = text.upper()
    if 'NFL' in s: return 'NFL'
    if 'NBA' in s: return 'NBA'
    if 'NHL' in s: return 'NHL'
    if 'UFC' in s or 'MMA' in s: return 'UFC'
    if 'NCAAB' in s or 'COLLEGE BASKETBALL' in s: return 'NCAAB'
    if 'NCAAF' in s or 'COLLEGE FOOTBALL' in s: return 'NCAAF'
    if 'MLB' in s or 'BASEBALL' in s: return 'MLB'
    if 'SOCCER' in s or 'EPL' in s or 'LEAGUE' in s: return 'Soccer'
    return 'Other'

def get_kalshi_headers(method: str, path: str) -> Dict[str, str]:
    if not KALSHI_KEY_ID or not CRYPTO_AVAILABLE: return {}
    try:
        ts = str(int(time.time() * 1000))
        msg = f"{ts}{method}{path}".encode('utf-8')
        
        # Load Key
        key_data = None
        if KALSHI_PRIVATE_KEY: 
            key_data = KALSHI_PRIVATE_KEY
        elif KALSHI_PRIVATE_KEY_PATH:
            try:
                from pathlib import Path
                key_path = Path(KALSHI_PRIVATE_KEY_PATH)
                if not key_path.is_absolute():
                    key_path = Path(__file__).parent / key_path
                if key_path.exists():
                    with open(key_path, "r") as f: 
                        key_data = f.read()
            except: pass
        
        if key_data:
            key_data = key_data.replace('KALSHI_PRIVATE_KEY=', '').strip()
            private_key = serialization.load_pem_private_key(key_data.encode('utf-8'), password=None)
            signature = private_key.sign(
                msg,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256()
            )
            sig_b64 = base64.b64encode(signature).decode('utf-8')
            
            return {
                'KALSHI-ACCESS-KEY': KALSHI_KEY_ID,
                'KALSHI-ACCESS-TIMESTAMP': ts,
                'KALSHI-ACCESS-SIGNATURE': sig_b64,
                'Content-Type': 'application/json'
            }
    except: pass
    return {}

def get_kalshi_ws_headers():
    return get_kalshi_headers("GET", "/trade-api/ws/v2")

# --- REST CLIENTS ---

class KalshiREST:
    def __init__(self):
        self.base_url = "https://api.elections.kalshi.com/trade-api/v2"
        
    async def fetch_markets(self) -> List[Dict]:
        """Deep Drill: Paginate through active markets (Capped at 2000)."""
        all_bets = []
        try:
            path = '/trade-api/v2/markets'
            headers = get_kalshi_headers("GET", path)
            params = {'status': 'open', 'limit': 1000}  # Max page size
            
            async with aiohttp.ClientSession() as session:
                cursor = None
                while len(all_bets) < 2000:  # CAP TO PREVENT LAG
                    current_params = params.copy()
                    if cursor: 
                        current_params['cursor'] = cursor
                    
                    async with session.get(f"{self.base_url}/markets", params=current_params, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            markets = data.get('markets', [])
                            cursor = data.get('cursor')
                            if not markets: break
                            
                            for market in markets:
                                ticker = market.get('ticker', '')
                                if not ticker.startswith('KX'): continue  # FAST FILTER
                                
                                # Extract Data
                                title = market.get('title', '')
                                category = market.get('sub_category', '')
                                sport = extract_sport_from_text(f"{ticker} {title} {category}")
                                
                                yes_ask = market.get('yes_ask', 0)
                                yes_bid = market.get('yes_bid', 0)
                                price = 0
                                if yes_bid > 0 and yes_ask > 0:
                                    price = probability_to_american((yes_bid + yes_ask) / 200.0)
                                    
                                all_bets.append({
                                    'id': f"KALSHI_{ticker}",
                                    'sport': sport,
                                    'game': title,
                                    'team': market.get('subtitle', 'Yes'),
                                    'line': 'ML',
                                    'price': price,
                                    'liquidity': float(market.get('open_interest', 0)),
                                    'book': 'Kalshi',
                                    'ticker': ticker
                                })
                            
                            logger.info(f"📡 Kalshi Drill: {len(all_bets)} sports markets found...")
                            if not cursor: break
                            await asyncio.sleep(0.5)  # Rate limiting
                        else:
                            break
        except Exception as e: 
            logger.error(f"Kalshi Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
        return all_bets

class PolymarketREST:
    def __init__(self):
        self.gamma_base = POLY_GAMMA_URL
        
    async def fetch_by_slug(self, session, target) -> List[Dict]:
        bets = []
        try:
            # TRY SLUG FIRST (Cleaner)
            url = f"{self.gamma_base}/events?slug={target['slug']}&closed=false"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Handle both list and dict responses
                    events = data if isinstance(data, list) else data.get('data', [])
                else:
                    events = []
            
            # IF EMPTY, TRY SEARCH (Broad Dragnet)
            if not events:
                url = f"{self.gamma_base}/events?q={target['q']}&closed=false"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        events = data if isinstance(data, list) else data.get('data', [])
                    else:
                        events = []

            # Parse Events
            for event in events:
                title = event.get('title', 'Unknown')
                markets = event.get('markets', [])
                for m in markets:
                    if not m.get('tokens'): continue
                    tokens = m.get('tokens', [])
                    if isinstance(tokens, str):
                        try:
                            tokens = json.loads(tokens)
                        except:
                            continue
                    if not tokens or not isinstance(tokens, list) or len(tokens) == 0:
                        continue
                    token = tokens[0]
                    if not isinstance(token, dict):
                        continue
                    token_id = token.get('token_id')
                    if not token_id:
                        continue
                    
                    bets.append({
                        'id': f"POLY_{token_id}",
                        'sport': extract_sport_from_text(title),
                        'game': title,
                        'team': m.get('groupItemTitle', token.get('outcome', 'Yes')),
                        'line': 'ML',
                        'price': 0,  # WS will fill this
                        'liquidity': 0, 
                        'book': 'Polymarket',
                        'token_id': token_id
                    })
        except Exception as e:
            logger.debug(f"Polymarket slug {target.get('slug')} error: {e}")
        return bets

    async def fetch_markets(self, fetch_orderbooks: bool = False) -> List[Dict]:
        all_bets = []
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_by_slug(session, t) for t in POLY_TARGETS]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    all_bets.extend(res)
                elif isinstance(res, Exception):
                    logger.debug(f"Polymarket fetch exception: {res}")
        logger.info(f"✅ Polymarket: Found {len(all_bets)} sports markets via Slug/Search")
        return all_bets

async def fetch_all_markets(fetch_poly_orderbooks: bool = False) -> tuple:
    k_client = KalshiREST()
    p_client = PolymarketREST()
    start = time.time()
    k_res, p_res = await asyncio.gather(k_client.fetch_markets(), p_client.fetch_markets(fetch_poly_orderbooks), return_exceptions=True)
    k_bets = k_res if isinstance(k_res, list) else []
    p_bets = p_res if isinstance(p_res, list) else []
    latency = int((time.time() - start) * 1000)
    return k_bets + p_bets, latency

def get_websocket_tokens(bets: List[Dict]) -> tuple:
    poly = [b['token_id'] for b in bets if b['book'] == 'Polymarket' and b.get('token_id')]
    kalshi = [b['ticker'] for b in bets if b['book'] == 'Kalshi' and b.get('ticker')]
    # Cap to prevent socket death
    return list(set(poly))[:1000], list(set(kalshi))[:1000]

# --- WEBSOCKET HANDLERS ---

async def polymarket_websocket_handler(token_ids: List[str], update_callback: Optional[Callable] = None):
    if not WEBSOCKET_AVAILABLE: return
    while True:
        try:
            async with websockets.connect(POLY_WS_URL) as ws:
                logger.info("[Poly WS] Connected")
                for i in range(0, len(token_ids), 200):
                    chunk = token_ids[i:i+200]
                    await ws.send(json.dumps({"type": "MARKET", "assets_ids": chunk, "auth": {}}))
                while True:
                    raw = await ws.recv()
                    msg = json.loads(raw)
                    items = msg if isinstance(msg, list) else [msg]
                    for item in items:
                        if item.get('type') == 'orderBookUpdate':
                            data = item.get('data', {})
                            tid = data.get('token_id')
                            if tid and update_callback: 
                                update_callback(f"POLY_{tid}", data)
        except Exception as e:
            logger.error(f"[Poly WS] Error: {e}")
            await asyncio.sleep(5)

async def kalshi_websocket_handler(tickers: List[str], update_callback: Optional[Callable] = None):
    if not WEBSOCKET_AVAILABLE: return
    while True:
        try:
            headers = get_kalshi_ws_headers()
            try:
                async with websockets.connect(KALSHI_WS_URL, extra_headers=headers) as ws:
                    await _run_kalshi_parser(ws, tickers, update_callback)
            except TypeError:
                try:
                    async with websockets.connect(KALSHI_WS_URL, additional_headers=headers) as ws:
                        await _run_kalshi_parser(ws, tickers, update_callback)
                except TypeError:
                    logger.warning("[Kalshi WS] Both header methods failed, retrying in 30s")
                    await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"[Kalshi WS] Error: {e}")
            await asyncio.sleep(5)

async def _run_kalshi_parser(ws, tickers, update_callback):
    logger.info("[Kalshi WS] Connected & Parsing")
    sub_id = 1
    if not tickers: return

    for i in range(0, len(tickers), 50):
        batch = tickers[i:i+50]
        for ticker in batch:
            await ws.send(json.dumps({
                "id": sub_id, 
                "cmd": "subscribe", 
                "params": {"channels": ["orderbook_delta"], "market_ticker": ticker}
            }))
            sub_id += 1
            await asyncio.sleep(0.01)

    while True:
        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get('type') == 'orderbook_delta':
            t = msg.get('msg', {}).get('market_ticker')
            if t and update_callback: 
                update_callback(f"KALSHI_{t}", msg['msg'])

# --- HELPER TO NORMALIZE ORDERBOOK DATA ---
def normalize_orderbook_data(data) -> Dict[float, float]:
    """Converts various orderbook data formats to a consistent dict {price: quantity}."""
    if isinstance(data, dict):
        return {float(k): float(v) for k, v in data.items()}
    elif isinstance(data, list):
        # Assume format is [[price, quantity]]
        return {float(item[0]): float(item[1]) for item in data if len(item) == 2}
    return {}
