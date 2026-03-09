"""
Debug script to see raw Polymarket data and understand the structure
"""
import json
import requests
from sharp_scanner_auth import detect_league, is_valid_game

# Fetch Polymarket data
print("=" * 80)
print("DEBUGGING POLYMARKET RAW DATA")
print("=" * 80)
print()

tag_slugs = ['nba']
all_events = []

for tag_slug in tag_slugs:
    try:
        events_url = "https://gamma-api.polymarket.com/events"
        params = {"tag_slug": tag_slug, "limit": 10, "active": "true", "closed": "false"}
        res = requests.get(events_url, params=params, timeout=5.0)
        
        if res.status_code == 200:
            events = res.json()
            for e in events:
                event_title = e.get('title', '')
                if is_valid_game(event_title):
                    markets = e.get('markets', [])
                    for m in markets[:2]:  # Just first 2 markets per event
                        print(f"\n{'='*80}")
                        print(f"EVENT: {event_title}")
                        print(f"MARKET: {m.get('question', 'N/A')}")
                        print(f"MARKET NAME: {m.get('name', 'N/A')}")
                        print(f"GROUP ITEM TITLE: {m.get('groupItemTitle', 'N/A')}")
                        
                        # Get outcomes
                        outcomes = m.get('outcomes', [])
                        print(f"OUTCOMES: {len(outcomes)}")
                        for idx, outcome in enumerate(outcomes):
                            print(f"  Outcome {idx}: {outcome}")
                        
                        # Get outcome prices
                        outcome_prices_raw = m.get('outcomePrices', None)
                        print(f"OUTCOME PRICES (raw): {outcome_prices_raw}")
                        
                        # Get liquidity
                        liquidity = m.get('liquidity', 0)
                        print(f"LIQUIDITY: {liquidity}")
                        
                        # Get orderbook
                        orderbook = m.get('orderbook', {})
                        if orderbook:
                            print(f"ORDERBOOK KEYS: {orderbook.keys()}")
                            asks = orderbook.get('asks', [])
                            bids = orderbook.get('bids', [])
                            print(f"ASKS (first 3): {asks[:3] if asks else 'None'}")
                            print(f"BIDS (first 3): {bids[:3] if bids else 'None'}")
                        
                        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

