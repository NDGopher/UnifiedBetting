# PickTheOdds API Research Findings

## Summary

We successfully explored the PickTheOdds GraphQL API and found the structure for accessing mainline markets (moneyline, spread, totals) with EV calculations.

## Key Findings

### 1. Available Queries

The API has these main queries:
- `games` - Get game listings (requires league enum)
- `betMarket` - Get betting markets for a specific game
- `betMarketInfos` - Get available market types for a league
- `completedBetMarket` - Get completed markets
- `players`, `teams`, `competitions` - Supporting data

### 2. Mainline Market Types Found

The enum `BetMarketTypeEnumTypeTwo` contains these mainline markets:
- **`SPREAD`** - Game spread
- **`TOTAL_GAME_POINTS`** - Game total (over/under)
- **`MONEY_LINE_GAME`** - Game moneyline

Plus many variations:
- `SPREAD_FIRST_HALF`, `SPREAD_SECOND_HALF`, etc.
- `TOTAL_GAME_POINTS_FIRST_HALF`, `TOTAL_GAME_POINTS_SECOND_HALF`, etc.
- `MONEY_LINE_GAME_FIRST_SET`, etc.

### 3. BetMarket Structure

The `betMarket` query returns `BetMarketType` with:
- `gameId` - Game identifier
- `hashCode` - Market hash code
- `marketType` - Type of market (enum)
- `conditions` - Market conditions (line, team, etc.)
- `listings` - Odds from different sportsbooks
  - `siteId` / `site` - Sportsbook info
  - `americanOdds` - Odds in American format
  - `isPrimary` - Primary listing flag
  - `maxWager` - Maximum bet size

### 4. Token Authentication

- **Token Lifetime**: ~5 minutes (300 seconds)
- **Format**: JWT bearer token
- **Extraction**: From browser DevTools Network tab
- **Note**: Token expires quickly, need to refresh frequently

## Query Structure for Mainlines

### Step 1: Get Games
```graphql
query GetGames($league: LeagueEnum!) {
  games(league: $league) {
    ... on BasketballGameType {
      id
      awayTeam { name }
      homeTeam { name }
      startDateTime
    }
  }
}
```

### Step 2: Get Market Info Types
```graphql
query GetBetMarketInfos($league: LeagueEnum!) {
  betMarketInfos(league: $league) {
    marketType
    groupInfo { name }
  }
}
```

### Step 3: Get Bet Markets
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

## Challenges

1. **Token Expiration**: Tokens expire in ~5 minutes, need frequent refresh
2. **Hash Codes**: Need to determine how to calculate `betMarketHashCode` for markets
3. **Access Control**: Some queries may require specific subscription tier
4. **EV Calculations**: Need to verify if EV/fair value is included in API or calculated client-side

## Next Steps

1. **Get Fresh Token**: Extract new bearer token from browser (they expire in ~5 min)
2. **Test betMarket Query**: Try with a known game ID and market hash codes
3. **Find Hash Code Calculation**: Determine how to get hash codes for SPREAD, TOTAL_GAME_POINTS, MONEY_LINE_GAME
4. **Check for EV Data**: See if API includes expected value or if we need to calculate it
5. **Compare with Current Data**: Compare API data structure with current BetBCK/Ace scraped data

## Potential Benefits

If the API works:
- ✅ **Fast**: Direct API calls vs scraping
- ✅ **Reliable**: No HTML parsing fragility
- ✅ **Multiple Sportsbooks**: Aggregated odds from multiple books
- ✅ **Structured Data**: Clean GraphQL responses
- ⚠️ **Token Management**: Need to handle token refresh

## Potential Issues

- ❌ **Token Management**: Short-lived tokens require refresh logic
- ❌ **Hash Codes**: Need to figure out how to generate market hash codes
- ❌ **EV Calculation**: May not include EV, might need to calculate ourselves
- ❌ **Rate Limits**: Unknown rate limits, need to be careful
- ❌ **Subscription Tier**: May require "Advanced" package (which user has)

## Files Created

1. `picktheodds_api_research.py` - Comprehensive research script
2. `test_betmarket_mainlines.py` - Focused test for mainlines
3. `analyze_introspection.py` - Analysis of GraphQL schema
4. `pto_introspection_result.json` - Full schema introspection results

## Usage

Once you have a fresh token:

```python
# Update token in test_betmarket_mainlines.py
BEARER_TOKEN = "your_fresh_token_here"

# Run the test
python test_betmarket_mainlines.py
```

