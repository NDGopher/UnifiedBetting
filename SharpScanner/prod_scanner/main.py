"""
High-Speed Terminal - Final UI.

1. Normalizes all keys (Sport vs sport) to guarantee data display.

2. Implements real-time price updates for BOTH books.
"""

import streamlit as st
import pandas as pd
import asyncio
import time
import threading
from datetime import datetime
import logging
import connectors

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# --- CACHE ---
MARKET_CACHE = {"bets": [], "updates": {}, "last_update": 0, "latency": 0, "ws_running": False}

# --- CSS ---
st.markdown("""<style>
.stApp { background-color: #000000; } 
* { color: #E0E0E0 !important; } 
[data-testid="stDataFrame"] { border: 1px solid #333; } 
[data-testid="stDataFrame"] th { background-color: #222; color: #FFF; } 
[data-testid="stDataFrame"] td { background-color: #000; }
div[data-testid="stMetric"] { background-color: #111; border: 1px solid #333; border-radius: 5px; padding: 10px; }
div[data-testid="stMetricValue"] { color: #00FF41 !important; font-size: 1.8rem; }
</style>""", unsafe_allow_html=True)

# --- WORKERS ---
def ws_callback(market_id, data):
    try:
        price = 0
        liquidity = 0
        # POLYMARKET PARSING
        if "POLY" in market_id:
            bids = data.get('bids', [])
            if bids:
                best_bid = float(bids[0].get('price', 0) if isinstance(bids[0], dict) else bids[0][0])
                price = connectors.probability_to_american(best_bid)
                liquidity = sum(float(x.get('size', 0) if isinstance(x, dict) else x[1]) for x in bids[:3])
        # KALSHI PARSING
        elif "KALSHI" in market_id:
            yes_bids = data.get('yes', [])
            if yes_bids:
                if isinstance(yes_bids, list) and len(yes_bids) > 0:
                    if isinstance(yes_bids[0], list):
                        best_bid_cents = max([x[0] for x in yes_bids if len(x) > 0])
                        price = connectors.probability_to_american(best_bid_cents / 100.0)
                        liquidity = sum([x[1] for x in yes_bids if len(x) > 1]) * 10
                    elif isinstance(yes_bids[0], dict):
                        best_bid_cents = max([x.get('price', 0) for x in yes_bids])
                        price = connectors.probability_to_american(best_bid_cents / 100.0)
                        liquidity = sum([x.get('size', 0) for x in yes_bids]) * 10
        if price != 0:
            MARKET_CACHE["updates"][market_id] = {'price': price, 'liquidity': liquidity}
    except Exception as e:
        logger.debug(f"WS callback error: {e}")

def background_poller():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        try:
            bets, latency = loop.run_until_complete(connectors.fetch_all_markets(False))
            MARKET_CACHE["bets"] = bets
            MARKET_CACHE["latency"] = latency
            MARKET_CACHE["last_update"] = time.time()
            logger.info(f"✅ Background: Fetched {len(bets)} bets in {latency}ms")
            
            if not MARKET_CACHE["ws_running"]:
                poly, kalshi = connectors.get_websocket_tokens(bets)
                def run_async(coro): 
                    asyncio.run(coro)
                if poly: 
                    threading.Thread(target=run_async, args=(connectors.polymarket_websocket_handler(poly, ws_callback),), daemon=True).start()
                if kalshi: 
                    threading.Thread(target=run_async, args=(connectors.kalshi_websocket_handler(kalshi, ws_callback),), daemon=True).start()
                MARKET_CACHE["ws_running"] = True
            time.sleep(30)
        except Exception as e:
            logger.error(f"Background poller error: {e}")
            time.sleep(5)

if "bg_thread" not in st.session_state:
    threading.Thread(target=background_poller, daemon=True).start()
    st.session_state["bg_thread"] = True

# --- UI ---
st.title("🔴 Sharp Terminal - ELITE")

with st.sidebar:
    min_liq = st.slider("Min Liquidity", 0, 50000, 0)
    st.metric("Total Bets", len(MARKET_CACHE["bets"]))
    st.metric("Live Updates", len(MARKET_CACHE["updates"]))
    st.metric("Latency", f"{MARKET_CACHE['latency']}ms")
    if MARKET_CACHE["last_update"] > 0:
        last_update_str = datetime.fromtimestamp(MARKET_CACHE["last_update"]).strftime('%H:%M:%S')
        st.caption(f"Last update: {last_update_str}")

# --- MERGE & DISPLAY ---
base = MARKET_CACHE["bets"]
live = MARKET_CACHE["updates"]
rows = []

for b in base:
    # Get Static Data
    p = b.get('price', 0)
    l = b.get('liquidity', 0)
    # Override with Live Data
    if b.get('id') in live:
        p = live[b['id']].get('price', p)
        l = live[b['id']].get('liquidity', l)
    
    # NORMALIZATION: Ensure keys match exactly
    rows.append({
        'Sport': b.get('sport', 'Unknown'), 
        'Game': b.get('game', 'Unknown'), 
        'Team': b.get('team', 'Unknown'),
        'Price': p, 
        'Liquidity': l, 
        'Book': b.get('book', 'Unknown'), 
        'ID': b.get('id', '')
    })

df = pd.DataFrame(rows)
if not df.empty:
    df = df[df['Liquidity'] >= min_liq].sort_values('Liquidity', ascending=False)
    st.dataframe(df, height=600, hide_index=True, use_container_width=True, column_config={
        "Liquidity": st.column_config.ProgressColumn(format="$%d", min_value=0, max_value=50000)
    })
    st.caption(f"Showing {len(df)} markets (Total: {len(base)})")
else:
    st.info(f"Wait... Fetching Data (Found: {len(base)} markets)")

time.sleep(1)
st.rerun()
