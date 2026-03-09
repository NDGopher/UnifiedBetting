"""
Deep Diagnostic Script for Sharp Scanner
Tests each exchange individually to identify parsing failures.
"""

import requests
import json
import ast
import sys
import logging
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
import base64
import time

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger()

# --- KALSHI AUTH ---
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
CvqzYxC2OHF8UtsMjYlTbQKBgCRBzjKoh08g1C0JHGDk3/7yKLBLOkiFhTgYwkR8
GrGRRVebQ/U4hUaObaxIQ8LurpLAW+V1hxpGwdCYF9Ex/1JRozkDyooQR1B7QygR
OataQH88jgPJt9J0BSF6EicccRELtJqC1mh3FHA5svav3csYGKCPVD+rMRo7ffSh
YHKdAoGALIvT1Pc2e3k1vc3GhkNXKvHUs59DQTetBPupHpUy8DG50djN04OeG7dM
j3EW8ppWqWb9hIuBmhk4qg6zuTtoz8mu8zvC57gtfv+y2H9gcKTa9FL/XL644Tkh
homIQ9oXbpR/hpG1+t9b2EfUQfVLyYdFRr62EWZRwTVx3cy/je8=
-----END RSA PRIVATE KEY-----
"""

class KalshiAuth(requests.auth.AuthBase):
    def __init__(self, key_id, private_key_str):
        self.key_id = key_id
        try:
            self.private_key = serialization.load_pem_private_key(
                private_key_str.strip().encode('utf-8'), password=None
            )
        except Exception as e:
            logger.error(f"Key Error: {e}")
            self.private_key = None

    def __call__(self, r):
        if not self.private_key:
            return r
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

# --- HEADERS ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

# ============================================================================
# TEST 1: KALSHI - Series Ticker Loop
# ============================================================================

def test_kalshi_series_ticker():
    logger.info("=" * 80)
    logger.info("TEST 1: KALSHI - Series Ticker Fetch")
    logger.info("=" * 80)
    
    try:
        # Fetch ONLY KXNFLGAME (NFL)
        series_ticker = "KXNFLGAME"
        url = "https://api.elections.kalshi.com/trade-api/v2/markets"
        params = {'limit': 100, 'status': 'open', 'series_ticker': series_ticker}
        
        logger.info(f"Fetching Kalshi markets for series: {series_ticker}")
        res = requests.get(url, auth=kalshi_auth, params=params, timeout=5.0)
        
        if res.status_code != 200:
            logger.error(f"Kalshi API Error: Status {res.status_code}")
            logger.error(f"Response: {res.text[:500]}")
            return
        
        data = res.json().get('markets', [])
        logger.info(f"✅ Kalshi: Received {len(data)} markets for {series_ticker}")
        
        if not data:
            logger.warning("❌ Kalshi: No markets returned")
            return
        
        # Print first market
        logger.info("\n" + "-" * 80)
        logger.info("FIRST MARKET RAW DATA:")
        logger.info("-" * 80)
        first_market = data[0]
        logger.info(json.dumps(first_market, indent=2, default=str))
        
        # Check key fields
        logger.info("\n" + "-" * 80)
        logger.info("KEY FIELD EXTRACTION:")
        logger.info("-" * 80)
        logger.info(f"Title: {first_market.get('title', 'N/A')}")
        logger.info(f"Subtitle: {first_market.get('subtitle', 'N/A')}")
        logger.info(f"Ticker: {first_market.get('ticker', 'N/A')}")
        logger.info(f"yes_bid: {first_market.get('yes_bid', 'N/A')}")
        logger.info(f"no_bid: {first_market.get('no_bid', 'N/A')}")
        logger.info(f"yes_bid_dollars: {first_market.get('yes_bid_dollars', 'N/A')}")
        logger.info(f"no_bid_dollars: {first_market.get('no_bid_dollars', 'N/A')}")
        logger.info(f"volume: {first_market.get('volume', 'N/A')}")
        
    except Exception as e:
        logger.error(f"❌ Kalshi Test Failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

# ============================================================================
# TEST 2: POLYMARKET - OutcomePrices Parsing
# ============================================================================

def test_polymarket_outcome_prices():
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: POLYMARKET - OutcomePrices Parsing")
    logger.info("=" * 80)
    
    try:
        # Fetch events
        events_url = "https://gamma-api.polymarket.com/events"
        params = {"limit": 100, "closed": "false"}
        
        logger.info("Fetching Polymarket events...")
        res = requests.get(events_url, params=params, headers=HEADERS, timeout=8.0)
        
        if res.status_code != 200:
            logger.error(f"Polymarket API Error: Status {res.status_code}")
            logger.error(f"Response: {res.text[:500]}")
            return
        
        events = res.json()
        if isinstance(events, dict):
            events = events.get('data', events.get('events', []))
        
        if not isinstance(events, list):
            logger.error(f"Unexpected response format: {type(events)}")
            return
        
        logger.info(f"✅ Polymarket: Received {len(events)} events")
        
        # Find first event with markets
        target_event = None
        target_market = None
        
        for e in events:
            markets = e.get('markets', [])
            if markets:
                target_event = e
                target_market = markets[0]
                break
        
        if not target_event or not target_market:
            logger.warning("❌ Polymarket: No events with markets found")
            return
        
        logger.info(f"\n✅ Found event: {target_event.get('title', 'N/A')}")
        logger.info(f"✅ Found market: {target_market.get('question', 'N/A')}")
        
        # Check outcomePrices
        logger.info("\n" + "-" * 80)
        logger.info("OUTCOMEPRICES PARSING:")
        logger.info("-" * 80)
        
        outcome_prices = target_market.get('outcomePrices', None)
        logger.info(f"Raw outcomePrices type: {type(outcome_prices)}")
        logger.info(f"Raw outcomePrices value: {outcome_prices}")
        
        if outcome_prices is None:
            logger.warning("❌ outcomePrices is None")
            return
        
        # Try different parsing methods
        parsed_prices = None
        
        if isinstance(outcome_prices, str):
            logger.info("→ outcomePrices is a STRING, attempting to parse...")
            logger.info(f"Original String: {outcome_prices}")
            
            # Method 1: json.loads
            try:
                parsed_prices = json.loads(outcome_prices)
                logger.info(f"✅ json.loads() success: {parsed_prices}")
            except json.JSONDecodeError as e:
                logger.warning(f"❌ json.loads() failed: {e}")
                
                # Method 2: ast.literal_eval
                try:
                    parsed_prices = ast.literal_eval(outcome_prices)
                    logger.info(f"✅ ast.literal_eval() success: {parsed_prices}")
                except (ValueError, SyntaxError) as e:
                    logger.error(f"❌ ast.literal_eval() failed: {e}")
        
        elif isinstance(outcome_prices, list):
            logger.info("→ outcomePrices is already a LIST")
            parsed_prices = outcome_prices
            logger.info(f"✅ Direct list: {parsed_prices}")
        
        else:
            logger.warning(f"❌ Unexpected type: {type(outcome_prices)}")
        
        if parsed_prices:
            logger.info("\n" + "-" * 80)
            logger.info("PARSED VALUES:")
            logger.info("-" * 80)
            if len(parsed_prices) >= 2:
                logger.info(f"Index 0 (Yes): {parsed_prices[0]} (type: {type(parsed_prices[0])})")
                logger.info(f"Index 1 (No): {parsed_prices[1]} (type: {type(parsed_prices[1])})")
                
                # Try to convert to float
                try:
                    yes_price = float(parsed_prices[0])
                    no_price = float(parsed_prices[1])
                    logger.info(f"✅ Converted to float - Yes: {yes_price}, No: {no_price}")
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Float conversion failed: {e}")
            else:
                logger.warning(f"❌ Parsed list has only {len(parsed_prices)} elements")
        
        # Check liquidity
        logger.info("\n" + "-" * 80)
        logger.info("LIQUIDITY FIELDS:")
        logger.info("-" * 80)
        logger.info(f"event['liquidity']: {target_event.get('liquidity', 'N/A')}")
        logger.info(f"market['liquidity']: {target_market.get('liquidity', 'N/A')}")
        
    except Exception as e:
        logger.error(f"❌ Polymarket Test Failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

# ============================================================================
# TEST 3: SX BET - Secondary API Call
# ============================================================================

def test_sx_bet_secondary_call():
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: SX BET - Secondary Orderbook Call")
    logger.info("=" * 80)
    
    try:
        # Step 1: Fetch active markets
        url = "https://api.sx.bet/markets/active"
        logger.info("Fetching SX Bet active markets...")
        res = requests.get(url, headers=HEADERS, timeout=5)
        
        if res.status_code != 200:
            logger.error(f"SX Bet API Error: Status {res.status_code}")
            logger.error(f"Response: {res.text[:500]}")
            return
        
        data = res.json()
        
        # Extract markets
        markets = []
        if isinstance(data, dict):
            if 'data' in data:
                if isinstance(data['data'], dict):
                    markets = data['data'].get('markets', [])
                elif isinstance(data['data'], list):
                    markets = data['data']
            else:
                markets = data.get('markets', [])
        elif isinstance(data, list):
            markets = data
        
        logger.info(f"✅ SX Bet: Received {len(markets)} markets")
        
        if not markets:
            logger.warning("❌ SX Bet: No markets returned")
            return
        
        # Step 2: Filter for one sports market
        SPORTS_KEYWORDS = ['NFL', 'NBA', 'NHL', 'MLB', 'NCAA', 'Football', 'Basketball', 'Hockey', 'Baseball', 'Soccer']
        sports_market = None
        
        for m in markets:
            sport = str(m.get('sportLabel', '')).lower()
            league = str(m.get('leagueLabel', '')).lower()
            
            if any(keyword.lower() in sport or keyword.lower() in league for keyword in SPORTS_KEYWORDS):
                sports_market = m
                break
        
        if not sports_market:
            logger.warning("❌ SX Bet: No sports markets found")
            logger.info("First market sample:")
            logger.info(json.dumps(markets[0], indent=2, default=str))
            return
        
        logger.info(f"\n✅ Found sports market:")
        logger.info(f"   Team 1: {sports_market.get('teamOneName', 'N/A')}")
        logger.info(f"   Team 2: {sports_market.get('teamTwoName', 'N/A')}")
        logger.info(f"   Sport: {sports_market.get('sportLabel', 'N/A')}")
        logger.info(f"   League: {sports_market.get('leagueLabel', 'N/A')}")
        
        # Step 3: Get marketHash and make secondary call
        market_hash = sports_market.get('marketHash') or sports_market.get('hash') or sports_market.get('id')
        
        logger.info("\n" + "-" * 80)
        logger.info("SECONDARY API CALL:")
        logger.info("-" * 80)
        logger.info(f"Market Hash: {market_hash}")
        
        # Try different possible endpoints
        endpoints_to_try = [
            f"https://api.sx.bet/markets/{market_hash}",
            f"https://api.sx.bet/markets/{market_hash}/orderbook",
            f"https://api.sx.bet/orderbook/{market_hash}",
        ]
        
        for endpoint_url in endpoints_to_try:
            logger.info(f"\n🔍 Trying endpoint: {endpoint_url}")
            
            try:
                book_res = requests.get(endpoint_url, headers=HEADERS, timeout=5)
                
                logger.info(f"   Status Code: {book_res.status_code}")
                
                if book_res.status_code == 200:
                    logger.info("   ✅ SUCCESS!")
                    book_data = book_res.json()
                    
                    logger.info("\n   Raw Response Structure:")
                    logger.info(f"   Type: {type(book_data)}")
                    if isinstance(book_data, dict):
                        logger.info(f"   Keys: {list(book_data.keys())}")
                    
                    logger.info("\n   Full Response (first 2000 chars):")
                    logger.info(json.dumps(book_data, indent=2, default=str)[:2000])
                    
                    # Check for common fields
                    if isinstance(book_data, dict):
                        if 'data' in book_data:
                            logger.info("\n   Found 'data' key, checking nested structure...")
                            nested = book_data['data']
                            if isinstance(nested, dict):
                                logger.info(f"   Nested keys: {list(nested.keys())}")
                        
                        # Check for orderbook fields
                        for key in ['bids', 'asks', 'buyOrders', 'sellOrders', 'outcomes', 'orderbook']:
                            if key in book_data:
                                logger.info(f"\n   ✅ Found '{key}' field")
                                logger.info(f"   Type: {type(book_data[key])}")
                                if isinstance(book_data[key], list) and len(book_data[key]) > 0:
                                    logger.info(f"   First element: {book_data[key][0]}")
                    
                    break  # Success, stop trying other endpoints
                else:
                    logger.warning(f"   ❌ Failed: {book_res.status_code}")
                    logger.warning(f"   Response: {book_res.text[:500]}")
            
            except Exception as e:
                logger.error(f"   ❌ Exception: {e}")
        
        # Also print the original market structure
        logger.info("\n" + "-" * 80)
        logger.info("ORIGINAL MARKET STRUCTURE:")
        logger.info("-" * 80)
        logger.info(json.dumps(sports_market, indent=2, default=str))
        
    except Exception as e:
        logger.error(f"❌ SX Bet Test Failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info("🔍 Starting Deep Diagnostic Tests...\n")
    
    test_kalshi_series_ticker()
    test_polymarket_outcome_prices()
    test_sx_bet_secondary_call()
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Diagnostic Tests Complete")
    logger.info("=" * 80)

