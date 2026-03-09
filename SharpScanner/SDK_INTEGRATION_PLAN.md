# SDK Integration Plan - Real-Time Access

## Current State
- Using raw `requests` with custom Kalshi auth
- Using raw `requests` for Polymarket Gamma + CLOB APIs
- Polling every 5 seconds (not true real-time)

## Recommended Approach (From Gemini)

### 1. Kalshi - Official SDK + WebSocket
**Package:** `kalshi-python` (official SDK)
**WebSocket:** From `nikhilnd/kalshi-market-making` repo

**Benefits:**
- Handles auth automatically
- Better error handling
- WebSocket for sub-second updates
- No rate limiting issues

### 2. Polymarket - Async Wrapper + CLOB Client
**Package:** `aiopolymarket` (async wrapper) + `py-clob-client` (CLOB API)
**Alternative:** `Poly-Trader` repo for sports filtering logic

**Benefits:**
- Async = faster when scanning 50+ games
- Proper CLOB integration for real-time prices
- Better token_id management

## Implementation Steps

1. **Install Dependencies:**
   ```bash
   pip install kalshi-python
   pip install aiopolymarket py-clob-client
   ```

2. **Refactor Kalshi:**
   - Replace custom `KalshiAuth` with official SDK
   - Add WebSocket support for real-time updates
   - Use SDK's built-in pagination

3. **Refactor Polymarket:**
   - Use `aiopolymarket` for async fetching
   - Use `py-clob-client` for CLOB prices
   - Cache token_ids for faster updates

4. **Add WebSocket Support:**
   - Kalshi: Subscribe to `orderbook_delta` channel
   - Polymarket: Use CLOB WebSocket if available

## Next Steps
1. Test if packages install correctly
2. Create new fetcher functions using SDKs
3. Add WebSocket handlers
4. Compare performance vs current approach

