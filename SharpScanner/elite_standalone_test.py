"""
Elite-Level Standalone Testing - Direct API Testing
Tests core functionality without Streamlit dependencies
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

# Import only the utility functions we need
import sys
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

# Copy essential utility functions
def cents_to_american(cents: int) -> Optional[int]:
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
    if prob <= 0 or prob >= 1:
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
    if odds is None:
        return "N/A"
    if odds > 0:
        return f"+{odds}"
    return str(odds)

# Kalshi Auth (simplified)
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
-----END RSA PRIVATE KEY-----
"""

# Simple Kalshi auth (just use basic auth for testing)
from requests.auth import HTTPBasicAuth
kalshi_auth = HTTPBasicAuth(KALSHI_KEY_ID, "")

def fetch_kalshi_sample():
    """Fetch sample Kalshi markets"""
    try:
        url = "https://api.elections.kalshi.com/trade-api/v2/markets"
        params = {'limit': 20, 'status': 'open', 'series_ticker': 'KXNFLGAME'}
        res = requests.get(url, auth=kalshi_auth, params=params, timeout=5.0)
        if res.status_code == 200:
            return res.json().get('markets', [])
    except:
        pass
    return []

def fetch_polymarket_sample():
    """Fetch sample Polymarket markets"""
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        url = "https://gamma-api.polymarket.com/events"
        params = {"tag_slug": "nfl", "limit": 20, "active": "true", "closed": "false"}
        res = requests.get(url, params=params, headers=headers, timeout=5.0)
        if res.status_code == 200:
            events = res.json()
            if isinstance(events, dict):
                return events.get('data', events.get('events', []))
            return events if isinstance(events, list) else []
    except:
        pass
    return []

def analyze_market_data(kalshi_data, polymarket_data):
    """Analyze the fetched data"""
    print("=" * 80)
    print("ELITE SHARP MONEY SCANNER - LIVE DATA ANALYSIS")
    print("=" * 80)
    print(f"\n📊 DATA FETCHED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Analyze Kalshi
    print("🟢 KALSHI ANALYSIS")
    print("-" * 80)
    print(f"  Markets Fetched: {len(kalshi_data)}")
    
    high_liquidity = []
    for m in kalshi_data[:10]:  # Analyze first 10
        title = m.get('title', '')
        yes_bid = m.get('yes_bid', 0)
        no_bid = m.get('no_bid', 0)
        yes_bid_dollars = float(m.get('yes_bid_dollars', 0) or 0)
        no_bid_dollars = float(m.get('no_bid_dollars', 0) or 0)
        
        total_liq = yes_bid_dollars + no_bid_dollars
        
        if total_liq > 10000:  # $10k+ liquidity
            yes_odds = cents_to_american(yes_bid) if yes_bid else None
            no_odds = cents_to_american(no_bid) if no_bid else None
            
            imbalance = (yes_bid_dollars / no_bid_dollars) if no_bid_dollars > 0 else 0
            
            high_liquidity.append({
                'title': title,
                'yes_odds': yes_odds,
                'no_odds': no_odds,
                'yes_liq': yes_bid_dollars,
                'no_liq': no_bid_dollars,
                'total_liq': total_liq,
                'imbalance': imbalance
            })
    
    if high_liquidity:
        print(f"  High Liquidity Markets Found: {len(high_liquidity)}")
        for m in sorted(high_liquidity, key=lambda x: x['total_liq'], reverse=True)[:5]:
            print(f"\n  💰 {m['title'][:60]}")
            print(f"     Yes: {format_odds(m['yes_odds'])} (${m['yes_liq']:,.0f})")
            print(f"     No:  {format_odds(m['no_odds'])} (${m['no_liq']:,.0f})")
            print(f"     Total: ${m['total_liq']:,.0f} | Imbalance: {m['imbalance']:.2f}x")
            if m['imbalance'] > 2.0:
                print(f"     🔥 SHARP MONEY SIGNAL: {m['imbalance']:.2f}x imbalance!")
    else:
        print("  No high liquidity markets found in sample")
    
    # Analyze Polymarket
    print("\n🔵 POLYMARKET ANALYSIS")
    print("-" * 80)
    print(f"  Events Fetched: {len(polymarket_data)}")
    
    if polymarket_data:
        for e in polymarket_data[:5]:  # Analyze first 5
            title = e.get('title', 'Unknown')
            liquidity = e.get('liquidity', 0)
            markets = e.get('markets', [])
            
            if liquidity > 10000:  # $10k+ liquidity
                print(f"\n  💰 {title[:60]}")
                print(f"     Liquidity: ${liquidity:,.0f}")
                if markets:
                    m = markets[0]
                    outcome_prices = m.get('outcomePrices', '[]')
                    try:
                        if isinstance(outcome_prices, str):
                            prices = json.loads(outcome_prices)
                        else:
                            prices = outcome_prices
                        if len(prices) >= 2:
                            prob_a = float(prices[0])
                            prob_b = float(prices[1])
                            odds_a = probability_to_american(prob_a)
                            odds_b = probability_to_american(prob_b)
                            print(f"     Side A: {format_odds(odds_a)} | Side B: {format_odds(odds_b)}")
                    except:
                        pass
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 EXECUTIVE SUMMARY")
    print("=" * 80)
    print(f"  Kalshi Markets Analyzed: {len(kalshi_data)}")
    print(f"  Polymarket Events Analyzed: {len(polymarket_data)}")
    print(f"  High Liquidity Signals: {len(high_liquidity)}")
    print("\n💡 PRIMARY PURPOSE:")
    print("   1. Find LARGE MOVES quickly (10%+ price changes)")
    print("   2. Find LIQUIDITY STACKING (imbalance > 2x = sharp money)")
    print("   3. Capitalize on SOFT BOOKS that don't move as fast")
    print("   4. Execute when exchange price beats soft book")
    print("=" * 80)

def main():
    print("\n🔬 ELITE TESTING MODE - FETCHING LIVE DATA...\n")
    
    print("Fetching Kalshi markets...")
    kalshi_data = fetch_kalshi_sample()
    print(f"  ✓ Fetched {len(kalshi_data)} markets")
    
    print("Fetching Polymarket markets...")
    polymarket_data = fetch_polymarket_sample()
    print(f"  ✓ Fetched {len(polymarket_data)} events")
    
    print("\nAnalyzing data...")
    analyze_market_data(kalshi_data, polymarket_data)
    
    print("\n✅ ELITE TESTING COMPLETE\n")

if __name__ == "__main__":
    main()

