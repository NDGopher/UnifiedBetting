import streamlit as st
import requests
import pandas as pd
import time
import sys
import logging
import uuid
import re
import base64
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

# --- 🔐 CREDENTIALS ---
KALSHI_KEY_ID = "4c67f48e-3c17-43e5-8eaa-8be0bf26ac37"

# ⚠️ PASTE THE PRIVATE KEY MATCHING THE ID ABOVE ⚠️
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

logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger()

st.set_page_config(page_title="🦈 Sharp Money v45", layout="wide")

# --- 🔐 AUTH ---
class KalshiAuth(requests.auth.AuthBase):
    def __init__(self, key_id, private_key_str):
        self.key_id = key_id
        try:
            self.private_key = serialization.load_pem_private_key(
                private_key_str.strip().encode('utf-8'), password=None
            )
        except Exception: st.error("❌ Key Error. Check Private Key.")

    def __call__(self, r):
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

# --- 🧮 HELPERS ---
def cents_to_american(cents):
    """Converts 1-99 cents to American Odds."""
    if cents <= 1 or cents >= 99: return None
    prob = cents / 100.0
    if prob == 0.5: return "+100"
    
    if prob > 0.5:
        # Favorite: - (p / (1-p)) * 100
        val = (prob / (1 - prob)) * 100
        return int(-val)
    else:
        # Underdog: + ((1-p) / p) * 100
        val = ((1 - prob) / prob) * 100
        return int(val)

def format_odds(odds):
    if odds is None: return "N/A"
    return f"+{odds}" if odds > 0 else f"{odds}"

def parse_matchup(title):
    clean = re.sub(r"(Winner\?|Game Winner|Will | win\?)", "", title, flags=re.IGNORECASE).strip()
    if " vs " in clean: return clean.split(" vs ")
    if " at " in clean: return clean.split(" at ")[1], clean.split(" at ")[0]
    return clean, "Opponent"

def get_smart_bet(title, subtitle, side_code, m_type):
    home, away = parse_matchup(title)
    
    # SPREAD: "Detroit wins by over 3.5 points"
    if m_type == "Spread":
        # Extract the line number
        num = re.search(r"\d+\.?\d*", subtitle)
        line = num.group(0) if num else ""
        
        # If text is "Detroit wins by...", and we bet Yes -> Bet Detroit
        if "wins by" in subtitle:
            team_in_sub = subtitle.split(" wins")[0]
            if side_code == "Yes": return f"Bet: {team_in_sub} -{line}"
            # If we bet No, we are fading Detroit -3.5, so we bet Opponent +3.5
            return f"Bet: {away if team_in_sub == home else home} +{line}"

    # TOTAL: "Over 54.5 points"
    if m_type == "Total":
        num = re.search(r"\d+\.?\d*", subtitle)
        line = num.group(0) if num else ""
        if side_code == "Yes":
            return f"Bet: Over {line}" if "Over" in subtitle else f"Bet: Under {line}"
        else:
            return f"Bet: Under {line}" if "Over" in subtitle else f"Bet: Over {line}"

    # MONEYLINE
    if "Will " in title:
        subject = title.split("Will ")[1].split(" win")[0].strip()
        if side_code == "Yes": return f"Bet: {subject} ML"
        # If Sharp on No, bet the OTHER team
        return f"Bet: {home if subject in away else away} ML"

    if side_code == "Yes": return f"Bet: {home} ML"
    return f"Bet: {away} ML"

# --- 📡 SCANNER ---

def fetch_kalshi_snapshot(status_box):
    # 1. DISCOVERY (Bulk by Series Ticker to minimize filtering errors)
    all_markets = []
    
    # We grab specific sport series to ensure we get Spreads/Totals natively
    # KXNCAAMB = NCAA Men's Basketball (General)
    # KXNCAAMBGAME = NCAA Games (Specific)
    targets = ["KXNBAGAME", "KXNFLGAME", "KXNHL", "KXNCAAMBGAME", "KXMLB"]
    
    for t in targets:
        try:
            url = "https://api.elections.kalshi.com/trade-api/v2/markets"
            params = {'limit': 100, 'status': 'open', 'series_ticker': t}
            res = requests.get(url, auth=kalshi_auth, params=params, timeout=3)
            data = res.json().get('markets', [])
            for m in data:
                m['sport'] = t.replace("KX","").replace("GAME","").replace("MB","")
                all_markets.append(m)
        except: pass
        
    results = []
    
    # 2. DEPTH SCAN
    def check_depth(m):
        try:
            # Filter
            full = (m.get('title', '') + m.get('subtitle', '')).lower()
            m_type = None
            
            if "wins by" in full or "spread" in full: m_type = "Spread"
            elif "total" in full or "over" in full or "under" in full: m_type = "Total"
            elif "winner" in full: m_type = "Moneyline"
            
            if not m_type: return None

            # Get Book
            url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{m['ticker']}/orderbook"
            res = requests.get(url, auth=kalshi_auth, timeout=1)
            book = res.json().get('orderbook', {})
            
            yes_bids = book.get('yes', [])
            no_bids = book.get('no', [])
            
            # --- CRITICAL FIX: DOLLAR VALUE ---
            # Value = (Price in Cents / 100) * Quantity
            yes_val = sum([(p[0]/100 * p[1]) for p in yes_bids[-5:]]) 
            no_val = sum([(p[0]/100 * p[1]) for p in no_bids[-5:]])
            
            if yes_val + no_val < 100: return None
            
            # --- SHARP LOGIC ---
            if yes_val > no_val:
                heavy, light, side = yes_val, no_val, "Yes"
                # If Yes is sharp, target odds = Yes Price
                price_cents = yes_bids[-1][0] if yes_bids else 50
                depth = yes_bids[-5:]
                opp_depth = no_bids[-5:]
            else:
                heavy, light, side = no_val, yes_val, "No"
                # If No is sharp, target odds = 100 - Yes Price (aka No Price)
                price_cents = no_bids[-1][0] if no_bids else 50
                depth = no_bids[-5:]
                opp_depth = yes_bids[-5:]

            # Avoid noise
            ratio = (heavy / light) if light > 50 else 10.0
            
            american = cents_to_american(price_cents)
            
            return {
                "Sport": m['sport'],
                "Event": m['title'].replace("Winner?", "").strip(),
                "Bet": get_smart_bet(m['title'], m['subtitle'], side, m_type),
                "Type": m_type,
                "Odds": format_odds(american),
                "RawOdds": american,
                "Liquidity": heavy,
                "OppLiquidity": light,
                "Ratio": ratio,
                "ChartSharp": [[cents_to_american(p[0]), p[1], (p[0]/100)*p[1]] for p in depth],
                "ChartOpp": [[cents_to_american(p[0]), p[1], (p[0]/100)*p[1]] for p in opp_depth]
            }
        except: return None

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(check_depth, m) for m in all_markets]
        for f in as_completed(futures):
            r = f.result()
            if r: results.append(r)
            
    return results

# --- 🖥️ UI ---

st.title("🦈 Sharp Money v45 (Calibrated)")
st.caption(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

with st.sidebar:
    st.header("Filters")
    min_liq = st.slider("Min Liquidity ($)", 100, 10000, 500)
    imb_ratio = st.slider("Min Imbalance", 1.2, 20.0, 2.0)
    max_odds = st.slider("Max Odds (+/-)", 100, 1000, 300)
    st.divider()
    if st.button("Force Refresh", type="primary"): st.rerun()

main_area = st.empty()

if 'scanning' not in st.session_state: st.session_state['scanning'] = True

while st.session_state['scanning']:
    
    # 1. FETCH
    data = fetch_kalshi_snapshot(None)
    
    # 2. FILTER
    df = pd.DataFrame(data)
    if not df.empty:
        # Filter Logic
        df = df[df['Ratio'] >= imb_ratio]
        df = df[df['Liquidity'] >= min_liq]
        # Odds Filter (remove -1100)
        df = df[df['RawOdds'].apply(lambda x: x is not None and abs(x) <= max_odds)]
        
        # Sort by Ratio (Best Opportunities First)
        df = df.sort_values('Ratio', ascending=False)
        
    # 3. RENDER
    with main_area.container():
        if df.empty:
            st.info("Scanning... (No imbalances found yet)")
        else:
            st.success(f"🔥 Found {len(df)} Sharp Plays (Spreads & Totals)")
            
            for _, row in df.iterrows():
                # Card
                label = f"**{row['Bet']}** ({row['Odds']}) | ⚡ **{row['Ratio']:.1f}x Imbalance**"
                
                with st.expander(label):
                    c1, c2 = st.columns([1, 2])
                    
                    with c1:
                        st.write(f"**Event:** {row['Event']}")
                        st.write(f"**Market:** {row['Type']}")
                        st.metric("Sharp Wall", f"${row['Liquidity']:,.0f}", delta="Sharp Side")
                        st.metric("Public", f"${row['OppLiquidity']:,.0f}", delta="Opponent", delta_color="inverse")
                        
                    with c2:
                        if PLOTLY_AVAILABLE:
                            # Chart: Price on X Axis
                            # We use strings for X to handle the +100 / -110 format nicely
                            s_x = [format_odds(x[0]) if x[0] else "N/A" for x in row['ChartSharp']]
                            s_y = [x[2] for x in row['ChartSharp']] # Dollar Value
                            o_x = [format_odds(x[0]) if x[0] else "N/A" for x in row['ChartOpp']]
                            o_y = [x[2] for x in row['ChartOpp']]
                            
                            fig = go.Figure()
                            fig.add_trace(go.Bar(x=s_x, y=s_y, name='Sharp', marker_color='#00cc96'))
                            fig.add_trace(go.Bar(x=o_x, y=o_y, name='Public', marker_color='#ef553b'))
                            
                            fig.update_layout(
                                title="Liquidity Depth ($)", 
                                yaxis_title="Volume ($)", 
                                xaxis_title="Odds",
                                barmode='group', height=250, margin=dict(l=20, r=20, t=40, b=20)
                            )
                            st.plotly_chart(fig, use_container_width=True, key=f"c_{uuid.uuid4()}")

    time.sleep(1)