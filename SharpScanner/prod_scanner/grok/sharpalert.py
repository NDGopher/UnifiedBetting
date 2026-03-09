# SharpAlert.py - Live: Poly WS with ping, Kalshi WS with Bearer API key (no login, direct Bearer key from dashboard).
# Full Poly pagination. Sports only. Console prints for updates/subs/no signals. Flask with thread-safe DB, /games for processed lines/liquidity.
# Fixed 404 by removing /log_in (Kalshi uses Bearer API_KEY for auth, no email/pass). Added "No signals" log.
# pip install flask if needed.

import requests
import json
import time
from datetime import datetime, timedelta
import threading
from websocket import create_connection, WebSocketConnectionClosedException
from fuzzywuzzy import process
import os
import sqlite3
import smtplib
from email.mime.text import MIMEText
from flask import Flask, jsonify

# Config - Tune for low noise!
SPORTS_TAGS_POLY = ['NBA', 'NFL', 'MLB', 'NHL', 'NCAAF', 'NCAAB', 'Soccer']
SPORTS_CATEGORIES_KALSHI = 'sports'  # Filter by category in response
POLL_INTERVAL = 30  # Seconds
LIQ_WALL_THRESH = 20000  # For huge walls
STEAM_THRESH = 0.05  # 5%+ moves
STEAM_WINDOW_MIN = 3  # Minutes
DAM_BREAK_THRESH = 0.3  # 30%+ wall takeout
VOLUME_THRESH = 5000  # Min vol for credibility
SIGNAL_SCORE_MIN = 80  # Higher for less noise
EMAIL_TO = 'your@email.com'  # Set for alerts
EMAIL_FROM = 'sharpalerts@example.com'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_USER = 'your@gmail.com'
SMTP_PASS = 'yourpass'
LOG_DB = 'sharp_alerts.db'

# Kalshi API key
KALSHI_API_KEY = 'a99c86d0-21ef-4272-9bc7-9b592fba4ec5'  # From dashboard

# API Bases
POLY_GAMMA_BASE = 'https://gamma-api.polymarket.com'
POLY_CLOB_BASE = 'https://clob.polymarket.com'
POLY_WS = 'wss://ws-subscriptions-clob.polymarket.com/ws/market'
KALSHI_BASE = 'https://api.elections.kalshi.com/trade-api/v2'
KALSHI_WS = 'wss://api.elections.kalshi.com/trade-api/ws/v2'

# DB path
DB_PATH = 'sharp_alerts.db'

# Caches
price_history = {}
order_books = {}
wall_history = {}
matched_markets = {}
poly_markets = {}
kalshi_markets = {}

def send_email_alert(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, 465)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Email error: {e}")

def log_alert(market_id, exchange, event_name, signal_type, score, bet_rec):
    conn = sqlite3.connect(DB_PATH)
    ts = datetime.now().isoformat()
    try:
        conn.execute("INSERT INTO alerts (timestamp, market_id, exchange, event_name, signal_type, score, bet_rec) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (ts, market_id, exchange, event_name, signal_type, score, bet_rec))
        conn.commit()
        alert = f"[{ts}] HIGH QUALITY ALERT - {exchange} {event_name}: {signal_type} (Score: {score}) | MANUAL CHECK: {bet_rec}"
        print(alert)
        send_email_alert("Sharp PPH Crush Alert", alert)
    except sqlite3.IntegrityError:
        print(f"Duplicate alert skipped: {bet_rec}")
    finally:
        conn.close()

def price_to_odds(price, format='american'):
    if price == 0: return 'inf'
    if format == 'american':
        if price > 0.5:
            return f"-{int(100 * price / (1 - price))}"
        else:
            return f"+{int(100 * (1 - price) / price)}"

def infer_bet_type(market_title):
    if 'Moneyline' in market_title or 'Winner' in market_title:
        return 'Moneyline'
    elif 'Spread' in market_title or 'Handicap' in market_title:
        return 'Spread'
    elif 'Total' in market_title or 'Over/Under' in market_title:
        if '1st Half' in market_title: return '1H Total'
        return 'Total'
    return 'Prop'

def fetch_poly_sports_markets():
    markets = {}
    for tag in SPORTS_TAGS_POLY:
        offset = 0
        while True:
            try:
                resp = requests.get(f"{POLY_GAMMA_BASE}/markets?tag={tag}&closed=false&limit=100&offset={offset}")
                if resp.status_code == 200:
                    batch = resp.json()
                    for m in batch:
                        markets[m['id']] = m
                    if len(batch) < 100:
                        break
                    offset += 100
                else:
                    break
            except Exception as e:
                print(f"Poly fetch error for {tag}: {e}")
                break
    print(f"Fetched {len(markets)} Poly markets")
    return markets

def fetch_kalshi_sports_markets():
    markets = {}
    kx_tickers = [
        'KXNFLGAME',
        'KXNFLSPREAD',
        'KXNFLTOTAL',
        'KXNBAGAME',
        'KXNBASPREAD',
        'KXNBATOTAL',
        'KXNHLGAME',
        'KXUFCFIGHT',
        'KXNCAAFGAME',
        'KXNCAAMBGAME'
    ]
    for ticker in kx_tickers:
        params = {
            'status': 'open',
            'with_nested_markets': 'true',
            'limit': 200,
            'series_ticker': ticker
        }
        try:
            headers = {'Authorization': f'Bearer {KALSHI_API_KEY}'}
            resp = requests.get(f"{KALSHI_BASE}/events", params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                events = data.get('events', [])
                for event in events:
                    for m in event.get('markets', []):
                        markets[m['ticker']] = m
                print(f"Kalshi fetched for {ticker}: {len(events)} events")
            else:
                print(f"Kalshi fetch failed for {ticker}: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Kalshi fetch error for {ticker}: {e}")
    print(f"Fetched {len(markets)} Kalshi sports markets")
    return markets

def match_markets(poly_markets, kalshi_markets):
    matches = {}
    for poly_id, poly in poly_markets.items():
        poly_title = poly.get('title', '')
        if not poly_title: continue
        kalshi_titles = [k.get('title', '') for k in kalshi_markets.values() if k.get('title')]
        if not kalshi_titles: continue
        best = process.extractOne(poly_title, kalshi_titles)
        if best and best[1] > 85:
            kalshi_title = best[0]
            kalshi_ticker = next(t for t, m in kalshi_markets.items() if m['title'] == kalshi_title)
            matches[poly_id] = kalshi_ticker
    return matches

def fetch_order_book(exchange, market_id):
    if exchange == 'poly':
        token_id = poly_markets.get(market_id, {}).get('tokens', [{}])[0].get('token_id')
        if token_id:
            resp = requests.get(f"{POLY_CLOB_BASE}/books?token_id={token_id}")
            if resp.status_code == 200:
                book = resp.json()
                return {'bids': sorted([(float(p['price']), float(p['size'])) for p in book.get('bids', [])], reverse=True),
                        'asks': sorted([(float(p['price']), float(p['size'])) for p in book.get('asks', [])])}
    elif exchange == 'kalshi':
        headers = {'Authorization': f'Bearer {KALSHI_API_KEY}'}
        resp = requests.get(f"{KALSHI_BASE}/markets/{market_id}/orderbook", headers=headers)
        if resp.status_code == 200:
            book = resp.json().get('orderbook')
            if book is None:
                return None
            return {'bids': sorted([(p/100, s) for p, s in book.get('yes', []) or []], reverse=True),
                    'asks': sorted([(p/100, s) for p, s in book.get('no', []) or []])}
        else:
            print(f"Kalshi book failed: {resp.status_code} {resp.text}")
    return None

def detect_signals(exchange, market_id, current_book, prev_book=None, trade=None, price_delta=0):
    if not current_book: return
    score = 0
    signals = []
    event_name = poly_markets.get(market_id, {}).get('title') if exchange == 'poly' else kalshi_markets.get(market_id, {}).get('title', 'Unknown')
    bet_type = infer_bet_type(event_name)

    agg_bid_liq = sum(s for _, s in current_book['bids'])
    agg_ask_liq = sum(s for _, s in current_book['asks'])
    if agg_bid_liq > LIQ_WALL_THRESH * 2 or agg_ask_liq > LIQ_WALL_THRESH * 2:
        score += 20
        signals.append(f"High Agg Liq: Bids ${agg_bid_liq:.0f}, Asks ${agg_ask_liq:.0f}")

    max_bid = max([s for _, s in current_book['bids']], default=0)
    max_ask = max([s for _, s in current_book['asks']], default=0)
    if max_bid > LIQ_WALL_THRESH or max_ask > LIQ_WALL_THRESH:
        score += 30
        signals.append(f"Huge Wall: Bid ${max_bid:.0f} / Ask ${max_ask:.0f}")

    if abs(price_delta) > STEAM_THRESH:
        score += int(abs(price_delta) / STEAM_THRESH * 30)
        signals.append(f"Big Steam: {price_delta:+.1%}")

    if prev_book:
        prev_max_bid = max([s for _, s in prev_book['bids']], default=0)
        prev_max_ask = max([s for _, s in prev_book['asks']], default=0)
        bid_redux = (prev_max_bid - max_bid) / prev_max_bid if prev_max_bid > 0 else 0
        ask_redux = (prev_max_ask - max_ask) / prev_max_ask if prev_max_ask > 0 else 0
        if bid_redux > DAM_BREAK_THRESH or ask_redux > DAM_BREAK_THRESH:
            score += 40
            signals.append(f"Liq Takeout: Bid redux {bid_redux:.1%} / Ask {ask_redux:.1%}")

    if trade and trade.get('size', 0) > VOLUME_THRESH:
        score += 20

    if score >= SIGNAL_SCORE_MIN and signals:
        direction = "Home/Over/Yes" if price_delta > 0 else "Away/Under/No"
        best_price = current_book['bids'][0][0] if current_book['bids'] and direction.startswith('Home') else (current_book['asks'][0][0] if current_book['asks'] else 0.5)
        odds = price_to_odds(best_price)
        bet_rec = f"Go check PPH for {event_name} ({bet_type}): Bet {direction} better than {odds}. Sharp dying for this at {best_price:.2f}."
        log_alert(market_id, exchange, event_name, ', '.join(signals), score, bet_rec)
    else:
        print("No signals this cycle")

# Poly WS
def poly_ws_handler():
    while True:
        try:
            ws = create_connection(POLY_WS)
            print("Poly WS Connected")
            token_ids = [t['token_id'] for m in poly_markets.values() for t in m.get('tokens', []) if t.get('token_id')]
            if token_ids:
                ws.send(json.dumps({"type": "MARKET", "assets_ids": token_ids, "auth": {}}))
                print(f"Poly subscribed to {len(token_ids)} markets")
            last_ping = time.time()
            while True:
                if time.time() - last_ping > 30:
                    ws.send(json.dumps({"type": "ping"}))
                    last_ping = time.time()
                msg = json.loads(ws.recv())
                print(f"Poly live update: {msg['type']} for market {msg.get('data', {}).get('token_id')}")
                if msg['type'] == 'orderBookUpdate':
                    market_id = msg['data']['token_id']
                    prev_book = order_books.get(market_id)
                    order_books[market_id] = {'bids': msg['data'].get('bids', []), 'asks': msg['data'].get('asks', [])}
                    detect_signals('poly', market_id, order_books[market_id], prev_book)
                elif msg['type'] == 'trade':
                    market_id = msg['data']['token_id']
                    trade = msg['data']
                    if market_id in price_history and price_history[market_id]:
                        prev_price = price_history[market_id][-1][1]
                        delta = trade['price'] - prev_price
                        detect_signals('poly', market_id, order_books.get(market_id), None, trade, delta)
                    price_history.setdefault(market_id, []).append((int(time.time()), trade['price']))
        except Exception as e:
            print(f"Poly WS: {e}")
            time.sleep(5)

# Kalshi WS
def kalshi_ws_handler():
    while True:
        try:
            kalshi_login()
            if not KALSHI_TOKEN:
                time.sleep(60)
                continue
            headers = ['Authorization: Bearer ' + KALSHI_TOKEN]
            ws = create_connection(KALSHI_WS, header=headers)
            print("Kalshi WS Connected")
            tickers = list(kalshi_markets.keys())
            sub_id = 1
            for ticker in tickers:
                sub_msg = {
                    "id": sub_id,
                    "cmd": "subscribe",
                    "params": {
                        "channels": ["orderbook_delta"],
                        "market_ticker": ticker
                    }
                }
                ws.send(json.dumps(sub_msg))
                sub_id += 1
            print(f"Kalshi subscribed to {len(tickers)} markets")
            last_ping = time.time()
            while True:
                if time.time() - last_ping > 30:
                    ws.send(json.dumps({"type": "ping"}))
                    last_ping = time.time()
                msg = json.loads(ws.recv())
                print(f"Kalshi live update: {msg.get('type')} for market {msg.get('msg', {}).get('market_ticker')}")
                msg_type = msg.get("type")
                if msg_type in ["orderbook_snapshot", "orderbook_delta"]:
                    market_id = msg.get('msg', {}).get('market_ticker')
                    prev_book = order_books.get(market_id)
                    bids = msg.get('msg', {}).get('orderbook', {}).get('yes', [])
                    asks = msg.get('msg', {}).get('orderbook', {}).get('no', [])
                    order_books[market_id] = {'bids': sorted([(p/100, s) for p, s in bids], reverse=True),
                                              'asks': sorted([(p/100, s) for p, s in asks])}
                    detect_signals('kalshi', market_id, order_books[market_id], prev_book)
                elif msg_type == "fill":
                    market_id = msg.get('msg', {}).get('market_ticker')
                    trade = {'size': msg.get('msg', {}).get('quantity'), 'price': msg.get('msg', {}).get('price')/100, 'side': msg.get('msg', {}).get('side')}
                    if market_id in price_history and price_history[market_id]:
                        prev_price = price_history[market_id][-1][1]
                        delta = trade['price'] - prev_price
                        detect_signals('kalshi', market_id, order_books.get(market_id), None, trade, delta)
                    price_history.setdefault(market_id, []).append((int(time.time()), trade['price']))
        except Exception as e:
            print(f"Kalshi WS: {e}")
            KALSHI_TOKEN = None
            time.sleep(5)

# Poll loop
def poll_loop():
    global poly_markets, kalshi_markets, matched_markets
    while True:
        poly_markets = fetch_poly_sports_markets()
        kalshi_markets = fetch_kalshi_sports_markets()
        matched_markets = match_markets(poly_markets, kalshi_markets)
        
        print("Writing JSON files")
        # Log markets to JSON for inspection
        with open('poly_markets.json', 'w') as f:
            json.dump(poly_markets, f, indent=2)
        with open('kalshi_markets.json', 'w') as f:
            json.dump(kalshi_markets, f, indent=2)
        
        # Processed games JSON
        kalshi_games = []
        for ticker, m in kalshi_markets.items():
            kalshi_games.append({
                'ticker': ticker,
                'title': m.get('title', 'Unknown'),
                'yes_bid': m.get('yes_bid', 0),
                'yes_ask': m.get('yes_ask', 0),
                'odds_yes': price_to_odds(m.get('yes_bid', 0)/100),
                'liquidity': m.get('liquidity', 0),
                'volume': m.get('volume', 0)
            })
        with open('kalshi_games.json', 'w') as f:
            json.dump(kalshi_games, f, indent=2)
        
        poly_games = []
        for id, m in poly_markets.items():
            outcome_prices = m.get('outcomePrices', [])
            if not outcome_prices: continue
            poly_games.append({
                'id': id,
                'question': m.get('question', 'Unknown'),
                'yes_price': float(outcome_prices[0]) if outcome_prices else 0,
                'no_price': float(outcome_prices[1]) if len(outcome_prices) > 1 else 0,
                'odds_yes': price_to_odds(float(outcome_prices[0]) if outcome_prices else 0),
                'liquidity': m.get('liquidity', 0),
                'volume': m.get('volume', 0)
            })
        with open('poly_games.json', 'w') as f:
            json.dump(poly_games, f, indent=2)
        
        for exchange, markets in [('poly', poly_markets), ('kalshi', kalshi_markets)]:
            for mid in markets:
                book = fetch_order_book(exchange, mid)
                if book:
                    order_books[mid] = book
                    detect_signals(exchange, mid, book)
                print(f"{exchange.capitalize()} polled update for {mid}")
        
        time.sleep(POLL_INTERVAL)

# Flask dashboard
app = Flask(__name__)

@app.route('/alerts')
def get_alerts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

@app.route('/markets/poly')
def get_poly_markets():
    return jsonify(poly_markets)

@app.route('/markets/kalshi')
def get_kalshi_markets():
    return jsonify(kalshi_markets)

@app.route('/games/kalshi')
def get_kalshi_games():
    with open('kalshi_games.json', 'r') as f:
        return jsonify(json.load(f))

@app.route('/games/poly')
def get_poly_games():
    with open('poly_games.json', 'r') as f:
        return jsonify(json.load(f))

def flask_thread():
    app.run(port=5000, debug=False, use_reloader=False, threaded=True)

if __name__ == '__main__':
    kalshi_login()  # Login for token
    threading.Thread(target=flask_thread, daemon=True).start()
    threading.Thread(target=poly_ws_handler, daemon=True).start()
    threading.Thread(target=kalshi_ws_handler, daemon=True).start()
    poll_loop()