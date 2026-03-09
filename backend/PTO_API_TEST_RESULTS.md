# PickTheOdds API Test Results

## ✅ What Works

1. **Authentication**: Token works (fresh token from user)
2. **Query Structure**: `betMarket` query syntax is correct
3. **API Endpoint**: `https://api.picktheodds.app/graphql` responds correctly

## ⚠️ What We Found

### betMarket Query
- **Status**: Query executes successfully
- **Result**: Returns empty array `[]` when hash codes are empty
- **Conclusion**: Need specific hash codes to get market data

### betMarketInfos Query
- **Status**: Returns 400 Bad Request
- **Possible Issue**: Query structure or access permissions

### Games Query
- **Status**: Returns "Invalid Request Params"
- **Possible Issue**: Need specific request structure or parameters

## 🔍 Key Finding

The `betMarket` query requires:
```graphql
betMarket(league: $league, gameId: $gameId, betMarketHashCode: [Int!]!)
```

**Hash codes are required** - we can't get markets without them. The empty array `[]` returns no results.

## 💡 Next Steps

### Option 1: Extract Hash Codes from Browser
1. Open picktheodds.app in browser
2. DevTools → Network tab → Filter "graphql"
3. Navigate to a game page with odds
4. Look for `betMarket` queries
5. Copy the `betMarketHashCode` array values from the request

### Option 2: Check Browser Network Requests
Look at the actual GraphQL requests the website makes:
- What hash codes are used?
- How are they calculated?
- Can we reverse-engineer the hash code generation?

### Option 3: Try Different Query
Maybe there's a query that returns all markets for a game without needing hash codes:
- `completedBetMarkets` - tried, got 400 error
- `betMarketListingHistory` - not tried yet
- Some other query in the schema

## 📊 Current Status

| Query | Status | Notes |
|-------|--------|-------|
| `betMarket` | ✅ Syntax works | Needs hash codes |
| `betMarketInfos` | ❌ 400 Error | Structure issue? |
| `games` | ❌ Invalid Params | Need correct structure |
| `completedBetMarkets` | ❌ 400 Error | Structure issue? |

## 🎯 Goal

Get mainline markets (SPREAD, TOTAL_GAME_POINTS, MONEY_LINE_GAME) with:
- Odds from multiple sportsbooks
- EV calculations (if available in API)
- Line values

## 📝 Test Script

All tests saved in `backend/test_betmarket_mainlines.py`

Game ID used: `01995880-04f1-7d72-b570-8db37218b793` (from user's original example)

