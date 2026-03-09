import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

# --- ⚙️ CONFIGURATION ---
ST_PAGE_TITLE = "🦈 Sharp Money Scanner (Direct API)"
REFRESH_RATE = 15  

# --- 🔒 HEADERS ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

# --- 🛠️ HELPER FUNCTIONS ---

def cents_to_american(cents):
    """Converts probability (cents) to American Odds."""
    if cents <= 0 or cents >= 100: return "N/A"
    prob = cents / 100.0
    if prob == 0.5: return "+100"
    elif prob > 0.5: return f"{int(-1 * (prob / (1 - prob)) * 100)}"
    else: return f"+{int(((1 - prob) / prob) * 100)}"

def decimal_to_american(decimal):
    """Converts Decimal Odds (e.g. 1.90) to American."""
    if decimal <= 1: return "N/A"
    if decimal >= 2.0: return f"+{int((decimal - 1) * 100)}"
    else: return f"{int(-100 / (decimal - 1))}"

# --- 📡 API SCANNERS ---

def scan_kalshi(status_box):
    """Scans Kalshi EVENTS (High Level) instead of Markets (Low Level)."""
    status_box.write("📡 Kalshi: Fetching Active Sports Events...")
    opportunities = []
    
    # 1. Fetch Events (Not Markets) - This is 100x faster
    # We fetch ALL open events, then filter for sports in Python to be safe
    url = "https://api.elections.kalshi.com/trade-api/v2/events"
    params = {'limit': 200, 'status': 'open'} 
    
    try:
        # Loop for pagination (usually only 1-2 pages for Events)
        while True:
            res = requests.get(url, headers=HEADERS, params=params, timeout=5)
            if res.status_code != 200: break
            
            data = res.json()
            events = data.get('events', [])
            cursor = data.get('cursor')
            
            # Keywords to identify sports events
            sports_keywords = ["NBA", "NFL", "NHL", "NCAA", "Basketball", "Football", "Hockey", "Soccer", "MLB", "Tennis"]
            
            for e in events:
                # Filter: Is this a sport?
                title_cat = (e.get('title', '') + e.get('series_ticker', '')).lower()
                if not any(k.lower() in title_cat for k in sports_keywords): continue

                # 2. Get Markets for this Event
                event_ticker = e['event_ticker']
                # We need the markets inside this event to check liquidity
                # Kalshi events usually have "markets" embedded if we ask, or we fetch separate
                # For speed, we just check the first "Yes/No" market in the event
                
                # Fetch specific markets for this event to get the orderbook
                m_url = f"https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker={event_ticker}"
                m_res = requests.get(m_url, headers=HEADERS, timeout=1)
                if m_res.status_code != 200: continue
                
                markets = m_res.json().get('markets', [])
                
                for m in markets:
                    # Look for "Winner" or "Spread" type markets (skip complicated props for now)
                    if "winner" not in m.get('subtitle', '').lower() and "spread" not in m.get('subtitle', '').lower():
                        continue

                    # 3. Check Orderbook
                    ticker = m['ticker']
                    book_url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook"
                    book_res = requests.get(book_url, headers=HEADERS, timeout=1)
                    if book_res.status_code != 200: continue
                    
                    book = book_res.json().get('orderbook', {})
                    yes_bids = book.get('yes', [])
                    no_bids = book.get('no', [])
                    
                    # Sum Liquidity
                    yes_cash = sum([(p[0]*p[1])/100 for p in yes_bids[-3:]]) if yes_bids else 0
                    no_cash = sum([(p[0]*p[1])/100 for p in no_bids[-3:]]) if no_bids else 0
                    
                    if yes_cash > no_cash:
                        side, heavy, light, price = "YES", yes_cash, no_cash, yes_bids[-1][0] if yes_bids else 0
                    else:
                        side, heavy, light, price = "NO", no_cash, yes_bids[-1][0], no_bids[-1][0] if no_bids else 0
                    
                    ratio = (heavy / light) if light > 5 else 20
                    
                    opportunities.append({
                        "Source": "Kalshi",
                        "Event": e['title'],
                        "Market": m['subtitle'],
                        "Side": side,
                        "Liquidity": heavy,
                        "Ratio": ratio,
                        "Odds": cents_to_american(price)
                    })
            
            if not cursor: break
            params['cursor'] = cursor

    except Exception as e:
        status_box.write(f"⚠️ Kalshi Error: {e}")
        
    status_box.write(f"✅ Kalshi: Found {len(opportunities)} Sports Markets")
    return opportunities

def scan_polymarket(status_box):
    """Scans Polymarket using Dynamic Tag Search."""
    status_box.write("📡 Polymarket: Finding 'Sports' Tag...")
    opportunities = []
    
    try:
        # 1. Get Sports ID dynamically
        tags_res = requests.get("https://gamma-api.polymarket.com/tags", headers=HEADERS, timeout=5)
        if tags_res.status_code == 403: 
            status_box.error("❌ Polymarket: 403 Forbidden (VPN Required)")
            return []
            
        tags = tags_res.json()
        sports_tag_id = next((t['id'] for t in tags if t['label'] == 'Sports' or t['slug'] == 'sports'), None)
        
        if not sports_tag_id: 
            status_box.write("⚠️ Polymarket: Could not find 'Sports' tag.")
            return []

        # 2. Fetch Active Sports Events
        status_box.write(f"📡 Polymarket: Fetching Events for Tag {sports_tag_id}...")
        events_url = "https://gamma-api.polymarket.com/events"
        params = {"limit": 50, "active": "true", "closed": "false", "tag_id": sports_tag_id}
        
        res = requests.get(events_url, params=params, headers=HEADERS, timeout=5)
        events = res.json()
        
        for e in events:
            # Check markets inside event
            for m in e.get('markets', []):
                if float(m.get('volume_24h', 0)) == 0: continue
                
                # Check Orderbook (CLOB)
                clob_id = m.get('id')
                clob_res = requests.get(f"https://clob.polymarket.com/book?token_id={clob_id}", headers=HEADERS, timeout=1)
                if clob_res.status_code != 200: continue
                
                book = clob_res.json()
                bids = book.get('bids', [])
                asks = book.get('asks', [])
                
                yes_cash = sum([float(x['size']) * float(x['price']) for x in bids[:3]]) if bids else 0
                no_cash = sum([float(x['size']) * float(x['price']) for x in asks[:3]]) if asks else 0

                if yes_cash > no_cash:
                    side, heavy, light, price = "YES", yes_cash, no_cash, float(bids[0]['price']) if bids else 0
                else:
                    side, heavy, light, price = "NO", no_cash, yes_cash, float(asks[0]['price']) if asks else 0
                    
                ratio = (heavy / light) if light > 5 else 20
                
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
        status_box.write(f"⚠️ Polymarket Error: {e}")
        
    status_box.write(f"✅ Polymarket: Found {len(opportunities)} Markets")
    return opportunities

def scan_sx_bet(status_box):
    """Scans SX Bet (Blockchain Exchange)."""
    status_box.write("📡 SX Bet: Fetching Active Markets...")
    opportunities = []
    
    try:
        # SX Bet has a clean API for active markets
        url = "https://api.sx.bet/markets/active"
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code != 200: 
            status_box.write(f"⚠️ SX Bet Error: {res.status_code}")
            return []
            
        data = res.json().get('data', {}).get('markets', [])
        
        for m in data:
            if m.get('status') != 'ACTIVE': continue
            
            # Filter for Major Sports
            league = m.get('leagueLabel', '').lower()
            if not any(x in league for x in ['nba', 'nfl', 'nhl', 'ncaa']): continue
            
            # SX Bet provides liquidity info directly in the market object often, 
            # or we assume liquidity based on "volume" for this lightweight scan.
            # Real-time orderbook would require a separate call per market, 
            # so we use Total Volume as a proxy for "Action" here to keep it fast.
            
            volume = float(m.get('volume', 0))
            if volume < 1000: continue # Skip low volume
            
            # Get Odds
            outcomeOne = float(m.get('outcomeOneOdds', 0)) / 10**18 # SX uses 18 decimals
            outcomeTwo = float(m.get('outcomeTwoOdds', 0)) / 10**18
            
            opportunities.append({
                "Source": "SX Bet",
                "Event": m.get('teamOneName') + " vs " + m.get('teamTwoName'),
                "Market": "Moneyline", # Usually main line
                "Side": "High Vol",
                "Liquidity": volume, # Using Volume as proxy for Liquidity here
                "Ratio": 1.0, # Cannot calculate imbalance without orderbook depth call
                "Odds": decimal_to_american(outcomeOne) # Showing Home Odds
            })
            
    except Exception as e:
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

log_container.update(label="Scan Complete!", state="complete", expanded=False)

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
    st.error("No markets found. Check the logs above for specific errors.")

time.sleep(REFRESH_RATE)
st.rerun()