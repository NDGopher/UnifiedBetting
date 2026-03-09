# PickTheOdds API Test Summary

## ✅ What Works

1. **GetGamesWithRequest** - ✅ SUCCESS
   - Gets 50 NBA games
   - Returns game IDs, teams, start times
   - Structure: `{"league": "NBA", "request": {}}`

2. **GetBetCacheCategories** - ✅ PARTIAL SUCCESS
   - Without gameId: Returns array of market type strings
   - With gameId: Returns empty array (game might not have markets yet)
   - Returns categories like: "PLAYER_PROP_POINTS", "TEAM_SCORE_FIRST", etc.
   - **Note**: These are market type NAMES, not hash codes

## ❌ What We Need

1. **Hash Codes for betMarket Query**
   - `betMarket` requires `betMarketHashCode: [Int!]!` (array of integers)
   - `betCacheCategories` returns strings, not integers
   - Need to find where hash codes come from

2. **Mainline Market Types**
   - `betCacheCategories` doesn't show SPREAD, TOTAL_GAME_POINTS, MONEY_LINE_GAME
   - These might be:
     - In a different category query
     - Require different parameters
     - Only available when markets are active

## 🔍 Next Steps

### Option 1: Check Browser Network Tab
1. Navigate to picktheodds.app
2. Go to a game page with active odds (moneyline, spread, totals visible)
3. Open DevTools → Network → Filter "graphql"
4. Find a `betMarket` request
5. Look at the `betMarketHashCode` array in the request payload
6. Copy those integer values

### Option 2: Try Different Queries
- Maybe there's a query that returns hash codes directly
- Maybe hash codes are calculated from market types
- Check if there's a `betMarketHashCode` query or similar

### Option 3: WebSocket Connection
- The WebSocket (`wss://api.picktheodds.app/graphql`) might provide:
  - Real-time market updates
  - Hash codes in subscription messages
  - Different data structure

## 📊 Current Status

| Query | Status | Result |
|-------|--------|--------|
| `GetGamesWithRequest` | ✅ Works | Returns 50 games |
| `GetBetCacheCategories` (no gameId) | ✅ Works | Returns market type strings |
| `GetBetCacheCategories` (with gameId) | ⚠️ Empty | No categories for that game |
| `GetBetMarket` (empty hash codes) | ❌ Empty | Needs hash codes |

## 💡 Key Insight

The `betCacheCategories` query returns **market type names** (strings), but `betMarket` needs **hash codes** (integers). These are likely:
- Calculated from market type + game + conditions
- Stored server-side and returned in a different query
- Available in the WebSocket subscription
- Visible in the browser's Network tab when markets load

## 🎯 Recommendation

**Check the browser Network tab** for an actual `betMarket` request when viewing a game with active odds. That's the fastest way to get the hash codes we need.

