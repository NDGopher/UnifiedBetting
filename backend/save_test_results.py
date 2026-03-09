"""Save test results to JSON file for analysis"""
import json
import requests
import time

API_URL = "https://api.picktheodds.app/graphql"
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3JvbGUiOiJ1c2VyIiwic3ViamVjdCI6ImZlY2ZkMWI3LWI0YzQtNGVjZi05MmJlLThhNmRiNzA4NmE5OSIsInBhY2thZ2UiOiJBZHZhbmNlZCIsIm5iZiI6MTc2MjM3MjQ0OSwiZXhwIjoxNzYyMzcyNzQ5LCJpYXQiOjE3NjIzNzI0NDksImlzcyI6Imh0dHBzOi8vcGlja3RoZW9kZHMuYXBwIiwiYXVkIjoiUGlja1RoZU9kZHMifQ.xdnSx7y4zMDpiGSyyin6BJqqaCXpFFSV7lb51GxYmMI"

HEADERS = {
    "authorization": f"bearer {BEARER_TOKEN}",
    "content-type": "application/json",
    "origin": "https://picktheodds.app",
    "referer": "https://picktheodds.app/",
}

def make_request(query, variables):
    payload = {"query": query, "variables": variables}
    time.sleep(0.5)
    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# Get games
games_query = """
query GetGamesWithRequest($league: LeagueEnum!, $request: InputGameRequestType) {
  games(league: $league, request: $request) {
    ... on BasketballGameType {
      id
      awayTeam { name, abbreviations }
      homeTeam { name, abbreviations }
      startDateTime
    }
  }
}
"""

# Get categories
categories_query = """
query GetBetCacheCategories($league: LeagueEnum!, $gameId: Guid) {
  betCacheCategories(league: $league, gameId: $gameId)
}
"""

print("Getting games...")
games_result = make_request(games_query, {"league": "NBA", "request": {}})
games = games_result.get("data", {}).get("games", [])[:5]  # First 5 games

print("Getting categories...")
categories_result = make_request(categories_query, {"league": "NBA", "gameId": None})

results = {
    "games": games,
    "categories": categories_result.get("data", {}).get("betCacheCategories", []),
    "test_games": []
}

# Test categories for a few games
for game in games[:3]:
    game_id = game["id"]
    print(f"Getting categories for game: {game_id}")
    cat_result = make_request(categories_query, {"league": "NBA", "gameId": game_id})
    results["test_games"].append({
        "game": game,
        "categories": cat_result.get("data", {}).get("betCacheCategories", [])
    })

with open("pto_test_results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nSaved results to pto_test_results.json")
print(f"Games: {len(games)}")
print(f"Total categories: {len(results['categories'])}")

