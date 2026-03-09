# SharpAlert.py - RSA Authentication Version
# Uses Kalshi API Key + RSA Private Key for stable, permanent authentication.

import requests
import json
import time
from datetime import datetime
import threading
from websocket import create_connection
from fuzzywuzzy import process
import sqlite3
import smtplib
from email.mime.text import MIMEText
from flask import Flask, jsonify
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
import base64

# --- Configuration ---
SPORTS_TAGS_POLY = ['NBA', 'NFL', 'MLB', 'NHL', 'NCAAF', 'NCAAB', 'Soccer']
POLL_INTERVAL = 30           
LIQ_WALL_THRESH = 20000      
STEAM_THRESH = 0.05          
DAM_BREAK_THRESH = 0.3       
SIGNAL_SCORE_MIN = 80        
DB_PATH = 'sharp_alerts.db'

# --- API CREDENTIALS ---
KALSHI_KEY_ID = "fde955f3-ca86-487f-87ba-c964acf7e28d"
KALSHI_KEY_FILE = "kalshi.key"  # Must be in the same folder

# --- Endpoints ---
POLY_GAMMA_BASE = 'https://gamma-api.polymarket.com'
POLY_CLOB_BASE = 'https://clob.polymarket.com'
POLY_WS = 'wss://ws-subscriptions-clob.polymarket.com/ws/market'

KALSHI_BASE = 'https://api.elections.kalshi.com/trade-api/v2'
KALSHI_WS = 'wss://api.elections.kalshi.com/trade-api/ws/v2'

# --- Global Caches ---
poly_markets = {}
kalshi_markets = {}

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            market_id TEXT,
            exchange TEXT,
            event_name TEXT,
            signal_type TEXT,
            score INTEGER,
            bet_rec TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized.")

# --- RSA Signing Logic ---
def load_private_key():
    with open(KALSHI_KEY_FILE, "r") as key_file:
        key_data = key_file.read()
        # Strip label if present
        if 'KALSHI_PRIVATE_KEY=' in key_data:
            key_data = key_data.split('KALSHI_PRIVATE_KEY=')[1].strip()
        return serialization.load_pem_private_key(
            key_data.encode('utf-8'),
            password=None
        )

def sign_request(method, path, timestamp):
    """Generates the RSA signature for Kalshi V2"""
    private_key = load_private_key()
    msg = f"{timestamp}{method}{path}".encode('utf-8')
    signature = private_key.sign(
        msg,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')

def get_kalshi_headers(method, path):
    """Returns headers with the correct signature"""
    ts = str(int(time.time() * 1000))
    signature = sign_request(method, path, ts)
    return {
        'KALSHI-ACCESS-KEY': KALSHI_KEY_ID,
        'KALSHI-ACCESS-TIMESTAMP': ts,
        'KALSHI-ACCESS-SIGNATURE': signature,
        'Content-Type': 'application/json'
    }

# --- Helper Functions ---
def log_alert(market_id, exchange, event_name, signal_type, score, bet_rec):
    conn = sqlite3.connect(DB_PATH)
    ts = datetime.now().isoformat()
    try:
        conn.execute(
            "INSERT INTO alerts (timestamp, market_id, exchange, event_name, signal_type, score, bet_rec) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, market_id, exchange, event_name, signal_type, score, bet_rec)
        )
        conn.commit()
        print(f"\n>>> [{ts}] ALERT {exchange.upper()}: {event_name} | {signal_type} | {bet_rec}\n")
    except Exception as e:
        print(f"DB Logging Error: {e}")
    finally:
        conn.close()

def price_to_odds(price):
    if price <= 0 or price >= 1: return 'N/A'
    if price > 0.5: return f"-{int(100 * price / (1 - price))}"
    else: return f"+{int(100 * (1 - price) / price)}"

# --- Fetch Functions ---
def fetch_poly_sports_markets():
    markets = {}
    print("Fetching Poly markets...")
    for tag in SPORTS_TAGS_POLY:
        offset = 0
        while True:
            try:
                resp = requests.get(f"{POLY_GAMMA_BASE}/markets?tag={tag}&closed=false&limit=100&offset={offset}")
                if resp.status_code == 200:
                    batch = resp.json()
                    if not batch: break
                    for m in batch: markets[m['id']] = m
                    if len(batch) < 100: break
                    offset += 100
                else: break
            except: break
    print(f"Fetched {len(markets)} Poly markets")
    return markets

def fetch_kalshi_sports_markets():
    markets = {}
    print("Fetching Kalshi markets (RSA Auth)...")
    kx_tickers = ['KXNFLGAME', 'KXNFLSPREAD', 'KXNFLTOTAL', 'KXNBAGAME', 'KXNBASPREAD', 'KXNBATOTAL']
    
    path = '/trade-api/v2/events'
    headers = get_kalshi_headers("GET", path)
    
    for ticker in kx_tickers:
        params = {'status': 'open', 'with_nested_markets': 'true', 'limit': 100, 'series_ticker': ticker}
        try:
            resp = requests.get(f"{KALSHI_BASE}/events", params=params, headers=headers)
            
            if resp.status_code == 200:
                events = resp.json().get('events', [])
                for event in events:
                    for m in event.get('markets', []):
                        markets[m['ticker']] = m
            else:
                print(f"Kalshi Fetch Fail {ticker}: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Kalshi fetch error {ticker}: {e}")
            
    print(f"Fetched {len(markets)} Kalshi markets")
    return markets

def fetch_order_book(exchange, market_id):
    if exchange == 'poly':
        token_id = poly_markets.get(market_id, {}).get('tokens', [{}])[0].get('token_id')
        if not token_id: return None
        try:
            resp = requests.get(f"{POLY_CLOB_BASE}/books?token_id={token_id}")
            if resp.status_code == 200:
                book = resp.json()
                return {'bids': sorted([(float(p['price']), float(p['size'])) for p in book.get('bids', [])], reverse=True),
                        'asks': sorted([(float(p['price']), float(p['size'])) for p in book.get('asks', [])])}
        except: pass
    elif exchange == 'kalshi':
        path = f'/markets/{market_id}/orderbook'
        headers = get_kalshi_headers("GET", path)
        try:
            resp = requests.get(f"{KALSHI_BASE}/markets/{market_id}/orderbook", headers=headers)
            if resp.status_code == 200:
                book = resp.json().get('orderbook')
                if not book: return None
                return {'bids': sorted([(p/100, s) for p, s in book.get('yes', []) or []], reverse=True),
                        'asks': sorted([(p/100, s) for p, s in book.get('no', []) or []])}
        except: pass
    return None

def detect_signals(exchange, market_id, current_book, prev_book=None, price_delta=0):
    if not current_book: return
    score = 0
    signals = []
    
    if exchange == 'poly': event_name = poly_markets.get(market_id, {}).get('question', 'Unknown')
    else: event_name = kalshi_markets.get(market_id, {}).get('title', 'Unknown')

    bids = current_book['bids']
    asks = current_book['asks']
    max_bid = max([s for _, s in bids], default=0) if bids else 0
    max_ask = max([s for _, s in asks], default=0) if asks else 0
    
    if max_bid > LIQ_WALL_THRESH or max_ask > LIQ_WALL_THRESH:
        score += 30
        signals.append(f"Wall: ${max_bid:.0f}/${max_ask:.0f}")

    if abs(price_delta) > STEAM_THRESH:
        score += 30
        signals.append(f"Steam: {price_delta:+.1%}")

    if score >= SIGNAL_SCORE_MIN:
        direction = "YES" if price_delta > 0 else "NO"
        best = bids[0][0] if bids else 0
        log_alert(market_id, exchange, event_name, ", ".join(signals), score, f"Bet {direction} @ {best:.2f}")

# --- WebSocket Handlers ---
def poly_ws_handler():
    while True:
        try:
            ws = create_connection(POLY_WS)
            print("[Poly WS] Connected")
            token_ids = [t['token_id'] for m in poly_markets.values() for t in m.get('tokens', []) if t.get('token_id')]
            for i in range(0, len(token_ids), 200):
                ws.send(json.dumps({"type": "MARKET", "assets_ids": token_ids[i:i + 200], "auth": {}}))
            
            last_ping = time.time()
            while True:
                if time.time() - last_ping > 20:
                    ws.send(json.dumps({"type": "ping"}))
                    last_ping = time.time()
                raw = ws.recv()
                if not raw: break
                msg = json.loads(raw)
                if msg.get('type') == 'trade': print(".", end="", flush=True)
        except:
            print("[Poly WS] Reconnecting...")
            time.sleep(5)

def kalshi_ws_handler():
    while True:
        try:
            headers = get_kalshi_headers("GET", "/trade-api/ws/v2")
            ws = create_connection(KALSHI_WS, header=headers)
            print("[Kalshi WS] Connected")
            
            tickers = list(kalshi_markets.keys())[:50]
            sub_id = 1
            for ticker in tickers:
                ws.send(json.dumps({"id": sub_id, "cmd": "subscribe", "params": {"channels": ["orderbook_delta"], "market_ticker": ticker}}))
                sub_id += 1
                
            last_ping = time.time()
            while True:
                if time.time() - last_ping > 20:
                    ws.send(json.dumps({"type": "ping"}))
                    last_ping = time.time()
                raw = ws.recv()
                msg = json.loads(raw)
                if msg.get('type') == 'fill': print("+", end="", flush=True)

        except Exception as e:
            print(f"[Kalshi WS] Error: {e}")
            time.sleep(10)

# --- Flask App ---
app = Flask(__name__)

@app.route('/alerts')
def get_alerts():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 50")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(rows)

def run_flask(): app.run(port=5000, debug=False, use_reloader=False)

# --- Main ---
def poll_loop():
    global poly_markets, kalshi_markets
    while True:
        print(f"\n--- Poll Cycle {datetime.now().strftime('%H:%M:%S')} ---")
        poly_markets = fetch_poly_sports_markets()
        kalshi_markets = fetch_kalshi_sports_markets()
        
        with open('poly_games.json', 'w') as f: json.dump(list(poly_markets.values()), f)
        with open('kalshi_games.json', 'w') as f: json.dump(list(kalshi_markets.values()), f)
        
        time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    print("Starting SharpAlert (RSA Mode)...")
    init_db()
    
    t_poll = threading.Thread(target=poll_loop, daemon=True)
    t_poll.start()
    time.sleep(5) 
    
    threading.Thread(target=poly_ws_handler, daemon=True).start()
    threading.Thread(target=kalshi_ws_handler, daemon=True).start()
    run_flask()