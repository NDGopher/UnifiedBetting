import streamlit as st
import requests
import pandas as pd
import time
import sys
import logging
from datetime import datetime

# --- 🛠️ LOGGING SETUP (The "Huge" Logging you asked for) ---
# This forces all logs to show up in your PowerShell window immediately
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger()

# --- ⚙️ CONFIGURATION ---
ST_PAGE_TITLE = "🦈 Sharp Money Debugger"
REFRESH_RATE = 30  
MAX_PAGES = 5 # Safety break to prevent infinite loops

# --- 🔒 HEADERS ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

# --- 🛠️ HELPER FUNCTIONS ---

def cents_to_american(cents):
    if cents <= 0 or cents >= 100: return "N/A"
    prob = cents / 100.0
    if prob == 0.5: return "+100"
    elif prob > 0.5: return f"{int(-1 * (prob / (1 - prob)) * 100)}"
    else: return f"+{int(((1 - prob) / prob) * 100)}"

# --- 📡 API SCANNERS (With Verbose Logging) ---

def scan_kalshi(status_box):
    logger.info("--- STARTED KALSHI SCAN ---")
    status_box.write("📡 Kalshi: Sending Request...")
    opportunities = []
    
    # Correct Endpoint: EVENTS (High level)
    url = "https://api.elections.kalshi.com/trade-api/v2/events"
    params = {'limit': 100, 'status': 'open'} # Max limit is usually 100-200
    
    pages = 0
    try:
        while pages < MAX_PAGES:
            pages += 1
            logger.info(f"Requesting Kalshi Page {pages}...")
            
            # TIMEOUT ADDED: Prevents hanging
            res = requests.get(url, headers=HEADERS, params=params, timeout=4)
            
            if res.status_code != 200:
                logger.error(f"Kalshi Failed: Status {res.status_code} - {res.text}")
                break
            
            data = res.json()
            events = data.get('events', [])
            cursor = data.get('cursor')
            
            logger.info(f"Page {pages}: Received {len(events)} events. Cursor: {cursor}")
            
            if not events:
                logger.warning("Kalshi returned empty event list.")
                break

            # Filter for Sports
            sports_keywords = ["NBA", "NFL", "NHL", "NCAA", "Basketball", "Football", "Hockey", "Soccer", "MLB"]
            
            for e in events:
                title = e.get('title', '')
                series = e.get('series_ticker', '')
                full_text = f"{title} {series}".lower()
                
                # LOGGING THE FILTER
                # logger.info(f"Checking: {title}") # Uncomment to see EVERY event checked (spammy)

                if not any(k.lower() in full_text for k in sports_keywords): 
                    continue # Skip non-sports
                
                logger.info(f"✅ MATCH FOUND: {title}")

                # Fetch Markets for this Event
                event_ticker = e['event_ticker']
                m_url = "https://api.elections.kalshi.com/trade-api/v2/markets"
                m_params = {'event_ticker': event_ticker}
                
                m_res = requests.get(m_url, headers=HEADERS, params=m_params, timeout=3)
                markets = m_res.json().get('markets', [])
                
                for m in markets:
                    # Skip boring sub-markets
                    if "winner" not in m.get('subtitle', '').lower() and "spread" not in m.get('subtitle', '').lower():
                        continue
                        
                    ticker = m['ticker']
                    # Get Liquidity
                    book_url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook"
                    book_res = requests.get(book_url, headers=HEADERS, timeout=3)
                    book = book_res.json().get('orderbook', {})
                    
                    yes_bids = book.get('yes', [])
                    no_bids = book.get('no', [])
                    
                    yes_cash = sum([(p[0]*p[1])/100 for p in yes_bids[-3:]]) if yes_bids else 0
                    no_cash = sum([(p[0]*p[1])/100 for p in no_bids[-3:]]) if no_bids else 0
                    
                    if yes_cash + no_cash == 0: continue

                    if yes_cash > no_cash:
                        side, heavy, light, price = "YES", yes_cash, no_cash, yes_bids[-1][0] if yes_bids else 0
                    else:
                        side, heavy, light, price = "NO", no_cash, yes_bids[-1][0], no_bids[-1][0] if no_bids else 0
                    
                    ratio = (heavy / light) if light > 5 else 20
                    
                    logger.info(f"   -> Market: {m['subtitle']} | Wall: ${heavy:.0f}")

                    opportunities.append({
                        "Source": "Kalshi",
                        "Event": e['title'],
                        "Market": m['subtitle'],
                        "Side": side,
                        "Liquidity": heavy,
                        "Ratio": ratio,
                        "Odds": cents_to_american(price)
                    })
            
            if not cursor:
                logger.info("No cursor returned. End of Kalshi data.")
                break
            params['cursor'] = cursor

    except Exception as e:
        logger.error(f"CRITICAL KALSHI ERROR: {e}")
        status_box.error(f"Kalshi Error: {e}")
        
    logger.info(f"--- KALSHI DONE. Found {len(opportunities)} items. ---")
    status_box.write(f"✅ Kalshi: Found {len(opportunities)} Sports Markets")
    return opportunities

def scan_polymarket(status_box):
    logger.info("--- STARTED POLYMARKET SCAN ---")
    status_box.write("📡 Polymarket: Connecting...")
    opportunities = []
    
    try:
        # 1. Check Permissions
        tags_res = requests.get("https://gamma-api.polymarket.com/tags", headers=HEADERS, timeout=4)
        if tags_res.status_code == 403:
            logger.error("POLYMARKET 403 FORBIDDEN. YOU ARE GEO-BLOCKED.")
            status_box.error("❌ Polymarket: Geo-Blocked (VPN Required)")
            return []
            
        # 2. Fetch Sports Events (Directly asking for active sports)
        # Using specific tag_id for Sports (usually 1002, but we search just in case)
        logger.info("Requesting Polymarket Events...")
        events_url = "https://gamma-api.polymarket.com/events"
        params = {"limit": 20, "active": "true", "closed": "false", "tag_id": "1002"}
        
        res = requests.get(events_url, params=params, headers=HEADERS, timeout=5)
        
        if res.status_code != 200:
            logger.error(f"Polymarket Failed: {res.status_code}")
            return []
            
        events = res.json()
        logger.info(f"Polymarket: Received {len(events)} events.")
        
        for e in events:
            logger.info(f"Checking Poly Event: {e['title']}")
            
            for m in e.get('markets', []):
                # Quick Volume Check
                if float(m.get('volume_24h', 0)) < 100: 
                    continue
                
                # Get Orderbook
                clob_id = m.get('id')
                clob_res = requests.get(f"https://clob.polymarket.com/book?token_id={clob_id}", headers=HEADERS, timeout=3)
                
                if clob_res.status_code != 200: continue
                
                book = clob_res.json()
                bids = book.get('bids', [])
                asks = book.get('asks', [])
                
                yes_cash = sum([float(x['size']) * float(x['price']) for x in bids[:3]]) if bids else 0
                no_cash = sum([float(x['size']) * float(x['price']) for x in asks[:3]]) if asks else 0
                
                if yes_cash + no_cash == 0: continue

                if yes_cash > no_cash:
                    side, heavy, light, price = "YES", yes_cash, no_cash, float(bids[0]['price']) if bids else 0
                else:
                    side, heavy, light, price = "NO", no_cash, yes_cash, float(asks[0]['price']) if asks else 0
                    
                ratio = (heavy / light) if light > 5 else 20
                
                logger.info(f"   -> Market: {m['question']} | Wall: ${heavy:.0f}")

                opportunities.append({
                    "Source": "Polymarket",
                    "Event": e['title'],
                    "Market": m['question'],
                    "Side": side,
                    "Liquidity": heavy,
                    "Ratio": ratio,
                    "Odds": cents_to_american(int(price * 100))
                })

    except Exception as e:
        logger.error(f"POLYMARKET ERROR: {e}")
        status_box.write(f"⚠️ Polymarket Error: {e}")
        
    status_box.write(f"✅ Polymarket: Found {len(opportunities)} Markets")
    return opportunities

def scan_sx_bet(status_box):
    logger.info("--- STARTED SX BET SCAN ---")
    status_box.write("📡 SX Bet: Connecting...")
    opportunities = []
    
    try:
        url = "https://api.sx.bet/markets/active"
        res = requests.get(url, headers=HEADERS, timeout=5)
        
        if res.status_code != 200:
            logger.error(f"SX Bet Failed: {res.status_code}")
            return []
            
        data = res.json().get('data', {}).get('markets', [])
        logger.info(f"SX Bet: Received {len(data)} raw markets.")
        
        for m in data:
            if m.get('status') != 'ACTIVE': continue
            
            league = m.get('leagueLabel', '').lower()
            if not any(x in league for x in ['nba', 'nfl', 'nhl', 'ncaa']): continue
            
            volume = float(m.get('volume', 0))
            if volume < 500: continue 
            
            # Simple Odds Grab
            outcomeOne = float(m.get('outcomeOneOdds', 0)) / 10**18
            
            logger.info(f"✅ SX MATCH: {m['teamOneName']} vs {m['teamTwoName']}")

            opportunities.append({
                "Source": "SX Bet",
                "Event": m.get('teamOneName') + " vs " + m.get('teamTwoName'),
                "Market": "Moneyline", 
                "Side": "High Vol",
                "Liquidity": volume, 
                "Ratio": 1.0, 
                "Odds": "N/A"
            })
            
    except Exception as e:
        logger.error(f"SX BET ERROR: {e}")
        status_box.write(f"⚠️ SX Bet Error: {e}")
        
    status_box.write(f"✅ SX Bet: Found {len(opportunities)} Markets")
    return opportunities

# --- 🖥️ DASHBOARD UI ---

st.set_page_config(page_title=ST_PAGE_TITLE, layout="wide")
st.title(f"📊 {ST_PAGE_TITLE}")

with st.sidebar:
    st.header("Settings")
    min_liq = st.slider("Min Liquidity ($)", 0, 5000, 100)
    imb_ratio = st.slider("Imbalance Ratio", 1.0, 5.0, 1.2)
    if st.button("Force Refresh", type="primary"): st.rerun()

# REAL-TIME LOGGING CONTAINER
log_container = st.status("🚀 Starting Scan...", expanded=True)

# Run Scans
all_ops = []
all_ops += scan_kalshi(log_container)
all_ops += scan_polymarket(log_container)
all_ops += scan_sx_bet(log_container)

log_container.update(label="Scan Complete! Check Console for Details.", state="complete", expanded=False)

# Display Data
if all_ops:
    df = pd.DataFrame(all_ops)
    
    # Filter
    filtered = df[df['Liquidity'] >= min_liq]
    filtered = filtered[filtered['Ratio'] >= imb_ratio]
    filtered = filtered.sort_values('Liquidity', ascending=False)
    
    st.subheader(f"🔥 Found {len(filtered)} Sharp Opportunities")
    
    st.dataframe(
        filtered,
        column_config={
            "Liquidity": st.column_config.ProgressColumn("Liquidity / Vol", format="$%d", min_value=0, max_value=10000),
            "Ratio": st.column_config.NumberColumn("Imbalance", format="%.1fx"),
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.error("No markets found. Check the BLACK CONSOLE WINDOW for the exact error log.")

time.sleep(REFRESH_RATE)
st.rerun()