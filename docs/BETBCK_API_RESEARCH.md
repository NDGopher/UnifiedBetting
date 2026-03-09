# BetBCK.com Real-Time Odds Research & Analysis

## Current Implementation

### How It Currently Works
1. **HTML Form-Based Scraping**: The system uses POST requests to search endpoints
2. **Search Flow**: 
   - Login → `StraightSportSelection.php` → Get `inetWagerNumber` → POST to `PlayerGameSelection.php`
   - Response is **HTML**, not JSON/API format
3. **URLs Used**:
   - Login: `https://betbck.com/Qubic/SecurityPage.php`
   - Main page: `https://betbck.com/Qubic/StraightSportSelection.php`
   - Search: `https://betbck.com/Qubic/PlayerGameSelection.php`

### Current Rate Limiting Issues
- The system is already experiencing rate limiting (403/429 errors)
- Current approach: Sequential POST requests with delays
- Problem: Each search requires a full page load/parsing cycle

## Research Findings

### ❌ No Public API Found
- **No REST API endpoints** discovered
- **No WebSocket connections** detected
- **No JSON endpoints** for odds data
- Site appears to be **legacy PHP-based** with server-side rendered HTML

### ✅ Potential Optimization Strategies

#### 1. **Reverse Engineer the Sport Selection Mechanism**
When you "click into a sport" on betbck.com, the site likely:
- Makes an AJAX request or form POST to load games
- Uses JavaScript to update the DOM
- May have hidden endpoints we're not currently using

**Investigation Needed:**
```javascript
// Monitor network requests in browser DevTools:
// 1. Open betbck.com
// 2. Open DevTools → Network tab
// 3. Filter: XHR/Fetch
// 4. Click into a sport (e.g., "Soccer", "NBA")
// 5. Look for:
//    - POST requests we're not making
//    - JSON responses
//    - Any endpoint patterns like: /api/*, /ajax/*, /data/*
```

#### 2. **Optimal Scraping Strategy (Current Approach Optimized)**

The current `BetBCKAsyncScraper` already uses async requests, but we could:

**A. Batch Sport Requests (Already Partially Implemented)**
- ✅ Currently: Async scraper fetches all sports at once
- ❌ Missing: Real-time updates for Camped games
- 💡 **Solution**: Periodic refresh of camped games without full searches

**B. Smart Caching with Timestamps**
```python
# Instead of searching every time:
# 1. Cache odds with timestamp
# 2. Only refresh if odds are "stale" (> 5 minutes old)
# 3. Use WebSocket/background polling for active events
```

**C. Leverage the Checkbox Pattern**
The async scraper already uses checkboxes to load specific leagues:
```python
# Example: SOCCER_ENG_Premier_League_Game_*
# This loads ALL games in that league at once
# Much more efficient than individual searches!
```

#### 3. **Browser Extension Approach (Most Promising)**

Since you already have a Chrome extension, we could:

**Option A: Extract Data from Already-Loaded Pages**
```javascript
// Content script watches for odds changes on the page
// No additional requests needed - just read DOM updates
const observer = new MutationObserver((mutations) => {
  // Detect when odds change on the page
  // Extract new values without making requests
});
```

**Option B: Intercept Network Requests**
```javascript
// Use chrome.webRequest API to intercept AJAX calls
// If betbck.com uses any API internally, we can capture it
chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    // Log all requests to see hidden endpoints
  },
  { urls: ["*://betbck.com/*"] }
);
```

#### 4. **Main Game Lines - Specific Strategy**

For **main game lines only** (moneyline, non-prop markets):

**Current Problem**: 
- Searching for each game individually = many requests
- Rate limiting kicks in

**Solution**: Use the main board scraping
```python
# scrape_all_betbck_games() already exists!
# This loads ALL games from main board with ONE request
# Then filter for games you care about

# Modified approach:
1. Load main board (StraightSportSelection.php)
2. Parse ALL games with main lines
3. Cache in memory/database
4. Update every 60-120 seconds (less aggressive)
5. Only search individual games if not on main board
```

## Recommended Implementation Plan

### Phase 1: Network Traffic Analysis (No Rate Limiting Risk)
**Goal**: Understand what happens when clicking sports/leagues

**Steps**:
1. Open betbck.com in Chrome with DevTools
2. Monitor Network tab (filter: XHR/Fetch/WS)
3. Document ALL requests made when:
   - Clicking into a sport category
   - Expanding a league
   - Games load
4. Look for patterns, endpoints, or data formats we're missing

**Deliverable**: Document any hidden API endpoints or better request patterns

### Phase 2: Optimize Main Board Scraping (Low Risk)
**Goal**: Get main game lines without individual searches

**Implementation**:
```python
# Create a background service that:
1. Runs every 2-5 minutes
2. Calls scrape_all_betbck_games() 
3. Stores results in cache/database
4. Frontend queries cached data (no new requests)
5. Only searches individually if game not on main board
```

**Benefits**:
- ✅ Fewer requests (one every 2-5 min vs many per search)
- ✅ Covers most popular games
- ✅ Less likely to trigger rate limits

### Phase 3: Browser Extension Real-Time Monitor (Medium Risk)
**Goal**: Get live updates from already-loaded betbck.com tabs

**Implementation**:
```javascript
// Content script that:
1. Detects when user has betbck.com open
2. Monitors DOM for odds changes
3. Sends updates to backend via WebSocket
4. No additional requests to betbck.com needed
```

**Benefits**:
- ✅ Zero rate limit risk (no requests from our side)
- ✅ True real-time updates
- ✅ Works as long as user has tab open

### Phase 4: Smart Request Optimization (Current System)
**Enhancements**:
1. **Request Deduplication**: Don't search same game within 60 seconds
2. **Circuit Breaker**: Back off faster when rate limited
3. **Priority Queue**: Main game lines first, props later
4. **Session Reuse**: Already implemented, but optimize refresh timing

## Risks & Mitigation

### Risk: Getting Banned
**Mitigation**:
- ✅ Use established sessions (already doing)
- ✅ Respect rate limits (already doing)
- ✅ Random delays (already doing)
- ➕ Add: User-agent rotation (low priority)

### Risk: Missing Real-Time Updates
**Mitigation**:
- Main board refresh every 2-5 min is "good enough" for most cases
- Browser extension provides true real-time when tab is open
- WebSocket polling can fill gaps

### Risk: Breaking Changes
**Mitigation**:
- Monitor HTML structure changes
- Have fallback parsing logic
- Alert on parsing failures

## Alternative: Third-Party Odds Aggregators

If betbck.com continues to be problematic:

### Consider These Services:
1. **The Odds API** (odds-api.io)
   - Covers 250+ bookmakers
   - Real-time updates
   - **Does NOT include betbck.com** (most don't)

2. **Sportsbook API** (sportsbookapi.com)
   - Custom integrations possible
   - Might be able to add betbck.com if you have relationship

3. **Direct Partnership**
   - Contact betbck.com directly
   - Ask about API/data feed access
   - Mention you're building a comparison tool

## Next Steps

1. **Immediate** (Today):
   - ✅ Review network traffic in DevTools when clicking sports
   - ✅ Document any hidden endpoints discovered
   - ✅ Test if main board scraping covers your use case

2. **Short-term** (This Week):
   - ✅ Implement Phase 2 (optimized main board scraping)
   - ✅ Add request deduplication
   - ✅ Create caching layer for main game lines

3. **Long-term** (Next Month):
   - ✅ Implement Phase 3 (browser extension monitor)
   - ✅ Build WebSocket polling service
   - ✅ Consider alternative data sources

## Code Investigation Tasks

### Task 1: Network Request Monitor Script
Create a script to capture all network requests from betbck.com:

```python
# monitor_betbck_requests.py
# Uses selenium to capture network traffic
# Logs all requests/responses to JSON file
```

### Task 2: Main Board Optimizer
Enhance `scrape_all_betbck_games()` to:
- Cache results
- Update incrementally
- Filter for active games only

### Task 3: Extension Enhancement
Add to Chrome extension:
- Network request interception
- DOM change monitoring
- Real-time odds extraction

## Conclusion

**Bottom Line**: Betbck.com does NOT appear to have a public API. However:

1. **Main board scraping** (already implemented) is the most efficient approach
2. **Browser extension monitoring** can provide real-time updates without rate limit risk
3. **Optimized caching** can reduce request frequency significantly

The best path forward is to:
- ✅ Optimize main board scraping for "camped" games
- ✅ Use browser extension for real-time monitoring
- ✅ Only search individually when absolutely necessary

This approach should give you near real-time odds for main game lines while minimizing rate limit risk.

