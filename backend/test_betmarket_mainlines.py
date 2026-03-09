"""Test betMarket query for mainlines (moneyline, spread, totals)"""
import requests
import json
import time

API_URL = "https://api.picktheodds.app/graphql"
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3JvbGUiOiJ1c2VyIiwic3ViamVjdCI6ImZlY2ZkMWI3LWI0YzQtNGVjZi05MmJlLThhNmRiNzA4NmE5OSIsInBhY2thZ2UiOiJBZHZhbmNlZCIsIm5iZiI6MTc2MjM3MjQ0OSwiZXhwIjoxNzYyMzcyNzQ5LCJpYXQiOjE3NjIzNzI0NDksImlzcyI6Imh0dHBzOi8vcGlja3RoZW9kZHMuYXBwIiwiYXVkIjoiUGlja1RoZU9kZHMifQ.xdnSx7y4zMDpiGSyyin6BJqqaCXpFFSV7lb51GxYmMI"

HEADERS = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "authorization": f"bearer {BEARER_TOKEN}",
    "content-type": "application/json",
    "origin": "https://picktheodds.app",
    "referer": "https://picktheodds.app/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0"
}

def make_request(query, variables=None, delay=0.8):
    payload = {"query": query, "variables": variables or {}}
    time.sleep(delay)
    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text[:500]}")
        return None

# Use a fresh game ID from user's example
KNOWN_GAME_ID = "01995501-aec4-7d4a-9859-666c00e8c83a"

print("=== Step 1: Get Games with Request (correct structure) ===")
games_query = """
query GetGamesWithRequest($league: LeagueEnum!, $request: InputGameRequestType) {
  games(league: $league, request: $request) {
    ... on BasketballGameType {
      id
      awayTeam {
        name
        abbreviations
      }
      homeTeam {
        name
        abbreviations
      }
      startDateTime
    }
  }
}
"""

# Try with empty request (all games)
print("Trying to get NBA games...")
games_result = make_request(games_query, {"league": "NBA", "request": {}})
if games_result:
    print("Games response:")
    print(json.dumps(games_result, indent=2)[:2000])
    if "data" in games_result and games_result["data"]:
        games = games_result["data"].get("games", [])
        if games:
            print(f"\n[SUCCESS] Found {len(games)} games!")
            game = games[0]
            KNOWN_GAME_ID = game["id"]
            print(f"Using first game: {game['awayTeam']['name']} @ {game['homeTeam']['name']}")
            print(f"Game ID: {KNOWN_GAME_ID}")
        else:
            print("No games in response")
            KNOWN_GAME_ID = "01995501-aec4-7d4a-9859-666c00e8c83a"  # Use user's example
    else:
        KNOWN_GAME_ID = "01995501-aec4-7d4a-9859-666c00e8c83a"  # Use user's example
else:
    KNOWN_GAME_ID = "01995501-aec4-7d4a-9859-666c00e8c83a"  # Use user's example

print(f"\n=== Step 2: Get Bet Cache Categories (this might give us hash codes!) ===")
bet_cache_query = """
query GetBetCacheCategories($league: LeagueEnum!, $gameId: Guid) {
  betCacheCategories(league: $league, gameId: $gameId)
}
"""

# Try with the game ID we just got
print(f"Using game ID: {KNOWN_GAME_ID}")
cache_result = make_request(bet_cache_query, {"league": "NBA", "gameId": KNOWN_GAME_ID})
if cache_result:
    print("Bet Cache Categories response:")
    print(json.dumps(cache_result, indent=2)[:3000])
    if "data" in cache_result and cache_result["data"]:
        categories = cache_result["data"].get("betCacheCategories")
        if categories:
            print(f"\n[SUCCESS] Got categories! Type: {type(categories)}")
            print(f"Categories: {categories}")
        else:
            print("\n⚠️  Empty categories - trying with NO gameId (all categories?)")
            cache_result_all = make_request(bet_cache_query, {"league": "NBA", "gameId": None})
            if cache_result_all:
                print("Categories (no gameId) response:")
                print(json.dumps(cache_result_all, indent=2)[:2000])

print(f"\n=== Step 3: Try betMarket query with hash codes from categories ===")
print(f"Game ID: {KNOWN_GAME_ID}")

# If we got categories, they might be hash codes
hash_codes = []
if cache_result and "data" in cache_result and cache_result["data"]:
    categories = cache_result["data"].get("betCacheCategories")
    if isinstance(categories, list):
        # Try using categories as hash codes
        hash_codes = categories
        print(f"Using categories as hash codes: {hash_codes[:10]}...")  # Show first 10
    elif isinstance(categories, dict):
        # Maybe it's a dict with hash codes
        print(f"Categories is dict, keys: {list(categories.keys())[:10]}")
        # Try to extract hash codes from dict
        # This is exploratory, we'll see what structure it has

# Try betMarket with empty hash code array (maybe it returns all markets?)
betmarket_query_1 = """
query GetBetMarket($league: LeagueEnum!, $gameId: Guid!, $betMarketHashCode: [Int!]!) {
  betMarket(league: $league, gameId: $gameId, betMarketHashCode: $betMarketHashCode) {
    gameId
    hashCode
    marketType
    conditions {
      marketType
      teamId
      overUnder
      betValue
      isGameBet
    }
    listings {
      siteId
      site {
        name
      }
      americanOdds
      isPrimary
      maxWager
    }
  }
}
"""

print("\nTrying betMarket with hash codes...")
if hash_codes:
    print(f"Using {len(hash_codes)} hash codes from categories")
    betmarket_result = make_request(betmarket_query_1, {"league": "NBA", "gameId": KNOWN_GAME_ID, "betMarketHashCode": hash_codes[:10]})  # Try first 10
else:
    print("Trying with empty array first...")
    betmarket_result = make_request(betmarket_query_1, {"league": "NBA", "gameId": KNOWN_GAME_ID, "betMarketHashCode": []})
if betmarket_result:
    print("Response:")
    print(json.dumps(betmarket_result, indent=2)[:3000])
    if "data" in betmarket_result and betmarket_result["data"]:
        markets = betmarket_result["data"].get("betMarket", [])
        if markets:
            print(f"\n✅ SUCCESS! Found {len(markets)} markets")
            for market in markets[:3]:  # Show first 3
                print(f"\nMarket: {market.get('marketType')}")
                print(f"  Hash Code: {market.get('hashCode')}")
                print(f"  Listings: {len(market.get('listings', []))}")
                for listing in market.get('listings', [])[:2]:
                    site_name = listing.get('site', {}).get('name', 'Unknown')
                    odds = listing.get('americanOdds')
                    print(f"    {site_name}: {odds}")
        else:
            print("\n⚠️  Empty array returned - need hash codes")
            print("\n📝 NEXT STEP: Check browser Network tab for a betMarket request")
            print("   Look for a GraphQL request to 'betMarket' with:")
            print("   - betMarketHashCode array with values")
            print("   - Copy those hash codes and we can test with them")
            print("\n   Or try inspecting the page to see if hash codes are visible")
            
            # Try a few common hash codes that might work (just guessing)
            print("\n🔍 Trying some common hash code patterns...")
            test_hash_codes = [
                [1, 2, 3],  # Sequential
                [100, 200, 300],  # Multiples
                [12345, 12346, 12347],  # Common patterns
            ]
            
            for test_codes in test_hash_codes:
                print(f"\nTrying hash codes: {test_codes}")
                test_result = make_request(betmarket_query_1, {
                    "league": "NBA", 
                    "gameId": KNOWN_GAME_ID, 
                    "betMarketHashCode": test_codes
                })
                if test_result and "data" in test_result:
                    markets = test_result["data"].get("betMarket", [])
                    if markets:
                        print(f"[SUCCESS] Found {len(markets)} markets with hash codes {test_codes}")
                        print(json.dumps(test_result, indent=2)[:2000])
                        break
                    else:
                        print("  No markets found")
