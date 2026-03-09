"""
Polymarket Fetcher using CLOB Client
Uses py-clob-client for real-time orderbook data
"""

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BookParams
import requests
import asyncio
import aiohttp
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

def create_polymarket_clob_client() -> ClobClient:
    """Create CLOB client for real-time Polymarket prices"""
    host = "https://clob.polymarket.com"
    return ClobClient(host)

async def fetch_polymarket_events_async(limit: int = 500) -> List[Dict]:
    """
    Fetch ALL active events using async requests (faster than sync).
    This replaces the sync requests.get() calls.
    """
    events_url = "https://gamma-api.polymarket.com/events"
    params = {"limit": limit, "active": "true", "closed": "false"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(events_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, dict):
                        events = data.get('data', data.get('events', []))
                    elif isinstance(data, list):
                        events = data
                    else:
                        events = []
                    
                    logger.info(f"Polymarket Async: Fetched {len(events)} total events")
                    return events
                else:
                    logger.error(f"Polymarket API Error: Status {response.status}")
                    return []
    except Exception as e:
        logger.error(f"Polymarket Async Error: {e}")
        return []

def get_polymarket_orderbook(clob_client: ClobClient, token_id: str) -> Optional[Dict]:
    """
    Get real-time orderbook from CLOB for a specific token_id.
    This is the REAL-TIME price data (not cached like Gamma API).
    """
    try:
        # Get orderbook using CLOB client
        book_params = BookParams(token_id=token_id)
        book = clob_client.get_order_book(book_params)
        
        if book:
            # Extract best bid/ask
            bids = book.get('bids', [])
            asks = book.get('asks', [])
            
            best_bid = float(bids[0]['price']) if bids else None
            best_ask = float(asks[0]['price']) if asks else None
            
            # Calculate midpoint (fair value)
            if best_bid and best_ask:
                midpoint = (best_bid + best_ask) / 2
            elif best_ask:
                midpoint = best_ask
            elif best_bid:
                midpoint = best_bid
            else:
                midpoint = None
            
            return {
                'best_bid': best_bid,
                'best_ask': best_ask,
                'midpoint': midpoint,
                'bids': bids[:10],  # Top 10 levels
                'asks': asks[:10]
            }
    except Exception as e:
        logger.warning(f"CLOB Error for token {token_id}: {e}")
        return None

def fetch_polymarket_markets_clob(clob_client: ClobClient, events: List[Dict]) -> List[Dict]:
    """
    Process events and fetch real-time prices from CLOB.
    This is the key difference - we use CLOB for REAL-TIME prices, not Gamma API.
    """
    results = []
    
    for event in events:
        markets = event.get('markets', [])
        for market in markets:
            # Get token_id for CLOB lookup
            clob_token_ids = market.get('clobTokenIds', [])
            if not clob_token_ids:
                continue
            
            token_id = clob_token_ids[0]  # Usually first is "Yes" token
            
            # Get REAL-TIME orderbook from CLOB
            orderbook = get_polymarket_orderbook(clob_client, token_id)
            
            if orderbook and orderbook.get('midpoint'):
                # This is REAL-TIME data, not cached!
                results.append({
                    'event': event,
                    'market': market,
                    'orderbook': orderbook,
                    'token_id': token_id
                })
    
    return results

# Example usage:
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.StreamHandler(sys.stdout)])
    
    # Test CLOB client
    clob_client = create_polymarket_clob_client()
    print("✅ CLOB client created")
    
    # Test async event fetching
    events = asyncio.run(fetch_polymarket_events_async(limit=10))
    print(f"✅ Fetched {len(events)} events using async")
    
    if events:
        # Test CLOB orderbook fetch (need a real token_id)
        first_market = events[0].get('markets', [{}])[0]
        token_ids = first_market.get('clobTokenIds', [])
        if token_ids:
            print(f"✅ Testing CLOB with token_id: {token_ids[0][:20]}...")
            orderbook = get_polymarket_orderbook(clob_client, token_ids[0])
            if orderbook:
                print(f"✅ Got real-time orderbook: midpoint={orderbook.get('midpoint')}")

