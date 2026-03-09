# PickTheOdds API - Final Findings & Next Steps

## ✅ What We Discovered

### 1. Correct Query Structures

#### Get Games
```graphql
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
```

**Variables:**
```json
{
  "league": "NBA",
  "request": {
    "gameIds": ["01995880-04f1-7d72-b570-8db37218b793", ...]  // Optional
  }
}
```

#### Get Bet Cache Categories (KEY DISCOVERY!)
```graphql
query GetBetCacheCategories($league: LeagueEnum!, $gameId: Guid) {
  betCacheCategories(league: $league, gameId: $gameId)
}
```

**This might give us hash codes!** The categories returned could be:
- Hash codes for `betMarket` query
- Market type identifiers
- Category groupings

#### Get Bet Markets
```graphql
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
      site { name }
      americanOdds
      isPrimary
      maxWager
    }
  }
}
```

## 🎯 The Workflow

1. **Get Games**: Use `GetGamesWithRequest` to get game IDs
2. **Get Categories**: Use `GetBetCacheCategories` with game ID to get hash codes
3. **Get Markets**: Use `GetBetMarket` with hash codes to get odds from multiple sportsbooks

## 📊 What We Need to Test

Once you have a fresh token:

1. **Test `GetBetCacheCategories`**:
   - This is the KEY query - it might return hash codes
   - Structure: `{"league": "NBA", "gameId": "01995501-aec4-7d4a-9859-666c00e8c83a"}`
   - Expected: Array of hash codes or category identifiers

2. **Use hash codes in `GetBetMarket`**:
   - If categories returns hash codes, use them in `betMarketHashCode` array
   - Should return markets with:
     - `marketType` (SPREAD, TOTAL_GAME_POINTS, MONEY_LINE_GAME)
     - `listings` with odds from multiple sportsbooks
     - `conditions` with line values

3. **Check for EV Data**:
   - Look in response for:
     - `expectedValue`
     - `fairValue`
     - `roi` (return on investment)
     - Any EV-related fields

## 🔑 Key Insights

1. **Token Lifetime**: ~5 minutes - need to refresh frequently
2. **Hash Codes Required**: `betMarket` requires hash codes - can't get markets without them
3. **Categories Query**: `betCacheCategories` is likely the key to getting hash codes
4. **Game IDs**: Can get from `GetGamesWithRequest` or use known IDs

## 🚀 Next Steps

1. **Get Fresh Token** (expires in ~5 min)
2. **Run Test Script**: `python test_betmarket_mainlines.py`
3. **Check Categories Response**: See what structure `betCacheCategories` returns
4. **Extract Hash Codes**: Use categories as hash codes in `betMarket` query
5. **Get Mainlines**: Filter for SPREAD, TOTAL_GAME_POINTS, MONEY_LINE_GAME
6. **Check for EV**: Look for EV/fair value in response

## 📝 Files Ready

- `test_betmarket_mainlines.py` - Updated with correct queries
- `PTO_API_FINDINGS.md` - Initial research
- `PTO_API_TEST_RESULTS.md` - Test results
- `pto_introspection_result.json` - Full GraphQL schema

## 💡 Expected Result

Once we have hash codes, `betMarket` should return:
```json
{
  "data": {
    "betMarket": [
      {
        "marketType": "SPREAD",
        "hashCode": 12345,
        "conditions": {
          "betValue": -5.5,
          "teamId": 1,
          "isGameBet": true
        },
        "listings": [
          {
            "site": {"name": "DraftKings"},
            "americanOdds": -110,
            "isPrimary": true
          },
          {
            "site": {"name": "FanDuel"},
            "americanOdds": -105,
            "isPrimary": false
          }
        ]
      },
      // ... more markets
    ]
  }
}
```

## ⚠️ Challenges

1. **Token Management**: Need automatic refresh or manual refresh every ~5 min
2. **Hash Code Structure**: Need to verify what `betCacheCategories` actually returns
3. **EV Calculation**: May need to calculate EV ourselves if API doesn't provide it
4. **Rate Limits**: Unknown - need to be careful with requests

