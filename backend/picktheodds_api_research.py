"""
Research script for PickTheOdds.app GraphQL API
This script explores the API to find queries for odds/lines data
"""

import requests
import json
import time
from typing import Dict, List, Any, Optional

# GraphQL endpoint
API_URL = "https://api.picktheodds.app/graphql"

# Bearer token from user's browser DevTools
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3JvbGUiOiJ1c2VyIiwic3ViamVjdCI6ImZlY2ZkMWI3LWI0YzQtNGVjZi05MmJlLThhNmRiNzA4NmE5OSIsInBhY2thZ2UiOiJBZHZhbmNlZCIsIm5iZiI6MTc2MjM3MTUzNSwiZXhwIjoxNzYyMzcxODM1LCJpYXQiOjE3NjIzNzE1MzUsImlzcyI6Imh0dHBzOi8vcGlja3RoZW9kZHMuYXBwIiwiYXVkIjoiUGlja1RoZU9kZHMifQ.YFZKEHsAgcGERV9ec9Qff6E6lFLqM4s_ZBgRvhfPiG4"

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


def make_graphql_request(query: str, variables: Dict[str, Any] = None, delay: float = 0.5) -> Optional[Dict]:
    """Make a GraphQL request to PickTheOdds API with rate limiting"""
    payload = {
        "query": query,
        "variables": variables or {}
    }
    
    # Rate limiting - be respectful
    time.sleep(delay)
    
    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error making request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text[:500]}")
        return None


def test_get_games_query():
    """Test the GetGamesWithRequest query (from user's example)"""
    query = """
    query GetGamesWithRequest($league: LeagueEnum!, $request: InputGameRequestType) {
      games(league: $league, request: $request) {
        ... on BasketballGameType {
          id
          awayTeam {
            id
            name
            abbreviations
            city
          }
          homeTeam {
            id
            name
            abbreviations
            city
          }
          awayScore
          homeScore
          isCancelled
          actualStartDateTime
          isCompleted
          leagueEnum
          startDateTime
        }
      }
    }
    """
    
    variables = {
        "league": "NBA",
        "request": {
            # Try without gameIds first to get all games
        }
    }
    
    print("\n=== Testing GetGamesWithRequest (all NBA games) ===")
    result = make_graphql_request(query, variables)
    if result:
        print(json.dumps(result, indent=2)[:2000])  # First 2000 chars
    return result


def test_get_games_with_ids():
    """Test getting specific games by ID"""
    query = """
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
    
    # Use a game ID from user's example
    variables = {
        "league": "NBA",
        "request": {
            "gameIds": ["01995880-04f1-7d72-b570-8db37218b793"]
        }
    }
    
    print("\n=== Testing GetGamesWithRequest (specific game) ===")
    result = make_graphql_request(query, variables)
    if result:
        print(json.dumps(result, indent=2)[:2000])
    return result


def test_get_odds_query():
    """Try to find odds/lines query - common patterns"""
    # Try common GraphQL query names for odds
    possible_queries = [
        """
        query GetOdds($gameId: ID!) {
          odds(gameId: $gameId) {
            moneyline
            spread
            total
          }
        }
        """,
        """
        query GetLines($gameId: ID!) {
          lines(gameId: $gameId) {
            moneyline
            spread
            total
          }
        }
        """,
        """
        query GetMarkets($gameId: ID!) {
          markets(gameId: $gameId) {
            name
            odds
            line
          }
        }
        """,
        """
        query GetGameOdds($gameId: ID!) {
          game(id: $gameId) {
            odds {
              moneyline
              spread
              total
            }
          }
        }
        """,
    ]
    
    game_id = "01995880-04f1-7d72-b570-8db37218b793"
    
    for i, query in enumerate(possible_queries):
        print(f"\n=== Testing Odds Query Pattern {i+1} ===")
        try:
            variables = {"gameId": game_id}
            result = make_graphql_request(query, variables)
            if result and "errors" not in result:
                print(f"SUCCESS with pattern {i+1}!")
                print(json.dumps(result, indent=2)[:2000])
            elif result and "errors" in result:
                print(f"Errors: {result['errors']}")
            else:
                print("No result")
        except Exception as e:
            print(f"Error: {e}")


def test_introspection_query():
    """Use GraphQL introspection to discover available queries"""
    query = """
    query IntrospectionQuery {
      __schema {
        queryType {
          name
          fields {
            name
            description
            args {
              name
              type {
                name
                kind
              }
            }
            type {
              name
              kind
            }
          }
        }
      }
    }
    """
    
    print("\n=== Testing GraphQL Introspection ===")
    result = make_graphql_request(query)
    if result:
        # Try to extract useful query names
        if "data" in result and result["data"]:
            schema = result["data"].get("__schema", {})
            query_type = schema.get("queryType", {})
            fields = query_type.get("fields", [])
            
            print("\nAvailable queries:")
            for field in fields:
                print(f"  - {field.get('name')}: {field.get('description', 'No description')}")
                args = field.get("args", [])
                if args:
                    print(f"    Args: {[arg.get('name') for arg in args]}")
        
        # Also print full result (truncated)
        print(f"\nFull result (first 3000 chars):")
        print(json.dumps(result, indent=2)[:3000])
    
    return result


def test_game_with_odds():
    """Try to get game data with nested odds"""
    query = """
    query GetGameWithOdds($gameId: ID!) {
      game(id: $gameId) {
        ... on BasketballGameType {
          id
          awayTeam {
            name
          }
          homeTeam {
            name
          }
          odds {
            moneyline {
              away
              home
            }
            spread {
              line
              away
              home
            }
            total {
              line
              over
              under
            }
          }
        }
      }
    }
    """
    
    game_id = "01995880-04f1-7d72-b570-8db37218b793"
    
    print("\n=== Testing Game with Nested Odds ===")
    result = make_graphql_request(query, {"gameId": game_id})
    if result:
        print(json.dumps(result, indent=2)[:2000])
    return result


def test_league_enum_values():
    """Try to get all available leagues"""
    query = """
    query GetLeagues {
      __type(name: "LeagueEnum") {
        enumValues {
          name
          description
        }
      }
    }
    """
    
    print("\n=== Testing League Enum Values ===")
    result = make_graphql_request(query)
    if result:
        print(json.dumps(result, indent=2))
    return result


def test_sportsbooks_query():
    """Try to find sportsbooks/books query"""
    query = """
    query GetSportsbooks {
      sportsbooks {
        id
        name
        odds {
          gameId
          market
          line
          odds
        }
      }
    }
    """
    
    print("\n=== Testing Sportsbooks Query ===")
    result = make_graphql_request(query)
    if result:
        print(json.dumps(result, indent=2)[:2000])
    return result


def test_props_query():
    """Try to find player props queries - this is what PTO primarily displays"""
    game_id = "01995880-04f1-7d72-b570-8db37218b793"
    
    possible_queries = [
        # Query 1: Get props for a game
        """
        query GetProps($gameId: ID!) {
          props(gameId: $gameId) {
            id
            playerName
            propType
            line
            odds
            fairValue
            expectedValue
            sportsbooks {
              id
              name
              odds
            }
          }
        }
        """,
        # Query 2: Get props with filters (like EV threshold)
        """
        query GetPropsWithFilters($filters: PropFiltersInput) {
          props(filters: $filters) {
            id
            playerName
            propType
            line
            odds
            expectedValue
            sportsbooks {
              name
              odds
            }
          }
        }
        """,
        # Query 3: Props nested in game query
        """
        query GetGameWithProps($gameId: ID!) {
          game(id: $gameId) {
            ... on BasketballGameType {
              id
              props {
                id
                playerName
                propType
                line
                odds
                expectedValue
              }
            }
          }
        }
        """,
        # Query 4: Expected value query (since PTO page is /expectedvalue)
        """
        query GetExpectedValueProps($league: LeagueEnum, $minEv: Float) {
          expectedValueProps(league: $league, minEv: $minEv) {
            id
            gameId
            playerName
            propType
            line
            odds
            expectedValue
            fairValue
            sportsbooks {
              name
              odds
            }
          }
        }
        """,
    ]
    
    for i, query in enumerate(possible_queries):
        print(f"\n=== Testing Props Query Pattern {i+1} ===")
        try:
            if i == 0:  # Game ID query
                variables = {"gameId": game_id}
            elif i == 1:  # Filters query
                variables = {"filters": {"minEv": 3.0, "league": "NBA"}}
            elif i == 2:  # Game with props
                variables = {"gameId": game_id}
            elif i == 3:  # Expected value query
                variables = {"league": "NBA", "minEv": 3.0}
            
            result = make_graphql_request(query, variables)
            if result and "errors" not in result:
                print(f"SUCCESS with pattern {i+1}!")
                print(json.dumps(result, indent=2)[:2000])
            elif result and "errors" in result:
                print(f"Errors: {result['errors']}")
            else:
                print("No result")
        except Exception as e:
            print(f"Error: {e}")


def test_markets_query():
    """Try to find markets/betting markets queries"""
    game_id = "01995880-04f1-7d72-b570-8db37218b793"
    
    possible_queries = [
        """
        query GetMarkets($gameId: ID!) {
          markets(gameId: $gameId) {
            id
            type
            line
            odds {
              sportsbook {
                id
                name
              }
              odds
              fairValue
            }
          }
        }
        """,
        """
        query GetPlayerMarkets($gameId: ID!) {
          playerMarkets(gameId: $gameId) {
            id
            playerName
            markets {
              type
              line
              odds {
                sportsbook {
                  name
                }
                odds
                expectedValue
              }
            }
          }
        }
        """,
    ]
    
    for i, query in enumerate(possible_queries):
        print(f"\n=== Testing Markets Query Pattern {i+1} ===")
        try:
            variables = {"gameId": game_id}
            result = make_graphql_request(query, variables)
            if result and "errors" not in result:
                print(f"SUCCESS with pattern {i+1}!")
                print(json.dumps(result, indent=2)[:2000])
            elif result and "errors" in result:
                print(f"Errors: {result['errors']}")
            else:
                print("No result")
        except Exception as e:
            print(f"Error: {e}")


def test_odds_aggregation_query():
    """Try to find odds aggregation queries (comparing multiple sportsbooks)"""
    game_id = "01995880-04f1-7d72-b570-8db37218b793"
    
    possible_queries = [
        """
        query GetOddsComparison($gameId: ID!, $marketType: MarketTypeEnum) {
          oddsComparison(gameId: $gameId, marketType: $marketType) {
            marketType
            line
            bestOdds {
              sportsbook {
                name
              }
              odds
            }
            fairValue
            expectedValue
          }
        }
        """,
        """
        query GetBestOdds($gameId: ID!) {
          bestOdds(gameId: $gameId) {
            marketType
            line
            sportsbooks {
              name
              odds
              expectedValue
            }
          }
        }
        """,
    ]
    
    for i, query in enumerate(possible_queries):
        print(f"\n=== Testing Odds Aggregation Query Pattern {i+1} ===")
        try:
            if i == 0:
                variables = {"gameId": game_id, "marketType": "PLAYER_PROP"}
            else:
                variables = {"gameId": game_id}
            
            result = make_graphql_request(query, variables)
            if result and "errors" not in result:
                print(f"SUCCESS with pattern {i+1}!")
                print(json.dumps(result, indent=2)[:2000])
            elif result and "errors" in result:
                print(f"Errors: {result['errors']}")
            else:
                print("No result")
        except Exception as e:
            print(f"Error: {e}")


def test_mainlines_with_ev():
    """Test queries for mainlines (moneyline, spread, totals) with EV calculations"""
    game_id = "01995880-04f1-7d72-b570-8db37218b793"
    
    possible_queries = [
        # Query 1: Game with mainline markets and EV
        """
        query GetGameMainlines($gameId: ID!) {
          game(id: $gameId) {
            ... on BasketballGameType {
              id
              awayTeam {
                name
              }
              homeTeam {
                name
              }
              moneyline {
                away {
                  odds
                  fairValue
                  expectedValue
                  sportsbooks {
                    name
                    odds
                  }
                }
                home {
                  odds
                  fairValue
                  expectedValue
                  sportsbooks {
                    name
                    odds
                  }
                }
              }
              spread {
                line
                away {
                  odds
                  fairValue
                  expectedValue
                  sportsbooks {
                    name
                    odds
                  }
                }
                home {
                  odds
                  fairValue
                  expectedValue
                  sportsbooks {
                    name
                    odds
                  }
                }
              }
              total {
                line
                over {
                  odds
                  fairValue
                  expectedValue
                  sportsbooks {
                    name
                    odds
                  }
                }
                under {
                  odds
                  fairValue
                  expectedValue
                  sportsbooks {
                    name
                    odds
                  }
                }
              }
            }
          }
        }
        """,
        # Query 2: Mainlines with EV filters
        """
        query GetMainlinesWithEV($league: LeagueEnum!, $minEv: Float) {
          mainlines(league: $league, minEv: $minEv) {
            gameId
            game {
              awayTeam {
                name
              }
              homeTeam {
                name
              }
            }
            moneyline {
              away {
                odds
                fairValue
                expectedValue
                bestSportsbook {
                  name
                  odds
                }
              }
              home {
                odds
                fairValue
                expectedValue
                bestSportsbook {
                  name
                  odds
                }
              }
            }
            spread {
              line
              away {
                odds
                fairValue
                expectedValue
                bestSportsbook {
                  name
                  odds
                }
              }
              home {
                odds
                fairValue
                expectedValue
                bestSportsbook {
                  name
                  odds
                }
              }
            }
            total {
              line
              over {
                odds
                fairValue
                expectedValue
                bestSportsbook {
                  name
                  odds
                }
              }
              under {
                odds
                fairValue
                expectedValue
                bestSportsbook {
                  name
                  odds
                }
              }
            }
          }
        }
        """,
        # Query 3: Odds comparison with EV
        """
        query GetOddsComparison($gameId: ID!) {
          oddsComparison(gameId: $gameId) {
            marketType
            line
            selection
            odds {
              sportsbook {
                name
              }
              odds
              fairValue
              expectedValue
            }
            bestOdds {
              sportsbook {
                name
              }
              odds
              expectedValue
            }
          }
        }
        """,
    ]
    
    for i, query in enumerate(possible_queries):
        print(f"\n=== Testing Mainlines Query Pattern {i+1} ===")
        try:
            if i == 0:  # Game ID query
                variables = {"gameId": game_id}
            elif i == 1:  # League query with EV filter
                variables = {"league": "NBA", "minEv": 3.0}
            elif i == 2:  # Odds comparison
                variables = {"gameId": game_id}
            
            result = make_graphql_request(query, variables, delay=0.8)
            if result and "errors" not in result:
                print(f"✅ SUCCESS with pattern {i+1}!")
                print(json.dumps(result, indent=2)[:3000])
                # Save successful results
                with open(f"pto_mainlines_result_{i+1}.json", "w") as f:
                    json.dump(result, f, indent=2)
                print(f"   Saved to pto_mainlines_result_{i+1}.json")
            elif result and "errors" in result:
                print(f"❌ Errors: {result['errors']}")
            else:
                print("⚠️  No result")
        except Exception as e:
            print(f"❌ Error: {e}")


def test_full_introspection():
    """Get full introspection including all types and their fields"""
    query = """
    query FullIntrospection {
      __schema {
        queryType {
          name
          fields {
            name
            description
            args {
              name
              type {
                ...TypeRef
              }
            }
            type {
              ...TypeRef
            }
          }
        }
        mutationType {
          name
          fields {
            name
            description
          }
        }
        subscriptionType {
          name
          fields {
            name
            description
          }
        }
        types {
          ...FullType
        }
      }
    }
    
    fragment FullType on __Type {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args {
          ...InputValue
        }
        type {
          ...TypeRef
        }
        isDeprecated
        deprecationReason
      }
      inputFields {
        ...InputValue
      }
      interfaces {
        ...TypeRef
      }
      enumValues(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
      }
      possibleTypes {
        ...TypeRef
      }
    }
    
    fragment InputValue on __InputValue {
      name
      description
      type {
        ...TypeRef
      }
      defaultValue
    }
    
    fragment TypeRef on __Type {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                  ofType {
                    kind
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    
    print("\n=== Testing Full GraphQL Introspection ===")
    result = make_graphql_request(query)
    if result:
        # Save to file for analysis
        with open("pto_introspection_result.json", "w") as f:
            json.dump(result, f, indent=2)
        print("Full introspection saved to pto_introspection_result.json")
        
        # Extract and print key information
        if "data" in result and result["data"]:
            schema = result["data"].get("__schema", {})
            
            # Print all query types
            query_type = schema.get("queryType", {})
            fields = query_type.get("fields", [])
            print(f"\n=== Found {len(fields)} queries ===")
            for field in fields:
                print(f"  - {field.get('name')}: {field.get('description', 'No description')}")
            
            # Look for interesting types
            types = schema.get("types", [])
            prop_related_types = [t for t in types if t.get("name") and (
                "prop" in t.get("name", "").lower() or 
                "odds" in t.get("name", "").lower() or
                "market" in t.get("name", "").lower() or
                "expected" in t.get("name", "").lower() or
                "value" in t.get("name", "").lower()
            )]
            
            if prop_related_types:
                print(f"\n=== Found {len(prop_related_types)} prop/odds/market related types ===")
                for t in prop_related_types[:20]:  # First 20
                    print(f"  - {t.get('name')}: {t.get('description', 'No description')}")
            
            print(f"\nFull result saved to pto_introspection_result.json for detailed analysis")
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("PickTheOdds.app GraphQL API Research")
    print("=" * 60)
    
    if BEARER_TOKEN == "YOUR_TOKEN_HERE":
        print("\n⚠️  WARNING: Please set BEARER_TOKEN in the script!")
        print("You can extract it from browser DevTools Network tab")
        print("Look for 'authorization: bearer ...' header")
        print("\nContinuing with tests anyway (will likely fail)...")
    
    # Run tests in logical order - FOCUSED ON MAINLINES
    print("\n🔍 Phase 1: GraphQL Schema Discovery (CRITICAL)")
    print("   This will show us ALL available queries and types")
    test_full_introspection()  # Full introspection first - most important
    
    print("\n🔍 Phase 2: Basic Game Queries")
    test_get_games_query()
    test_get_games_with_ids()
    test_league_enum_values()
    
    print("\n🔍 Phase 3: MAINLINES with EV (YOUR PRIORITY)")
    print("   Testing moneyline, spread, totals with expected value calculations")
    test_mainlines_with_ev()
    test_get_odds_query()
    test_game_with_odds()
    test_markets_query()
    
    print("\n🔍 Phase 4: Additional Queries (Optional)")
    test_odds_aggregation_query()
    test_sportsbooks_query()
    
    # Skip props tests since user doesn't need them
    # test_props_query()
    
    print("\n" + "=" * 60)
    print("Research complete!")
    print("=" * 60)

