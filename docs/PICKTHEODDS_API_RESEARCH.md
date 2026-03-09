# PickTheOdds.app GraphQL API Research

## Overview

This document explores the PickTheOdds.app GraphQL API to determine if we can use it to fetch betting lines/odds more efficiently than our current Selenium scraping approach.

## Current Approach

**Current Method**: Selenium-based scraping of the PickTheOdds website
- **Pros**: Works with existing authentication
- **Cons**: 
  - Slow (requires browser automation)
  - Resource-intensive (Chrome instances)
  - Fragile (breaks on UI changes)
  - Requires page refreshes every 2-2.5 hours
  - Scrapes every 2-3 seconds (inefficient)

## API Discovery

### Endpoint
- **URL**: `https://api.picktheodds.app/graphql`
- **Method**: POST
- **Authentication**: Bearer token (JWT)
- **Content-Type**: `application/json`

### Authentication
The API requires a bearer token in the Authorization header:
```
Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Token Extraction**: The token can be extracted from browser DevTools:
1. Open Network tab in DevTools
2. Navigate to picktheodds.app
3. Filter by "graphql"
4. Look at request headers for `authorization: bearer ...`
5. Token appears to be a JWT with user info and subscription level

### Known Query: GetGamesWithRequest

From the user's example, we know this query exists:

```graphql
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
    # Also supports: FootballGameType, IceHockeyGameType, SoccerGameType, TennisGameType, GolfGameType, BaseballGameType
  }
}
```

**What it returns**: Game metadata (teams, scores, dates) but **NOT odds/lines**

**Variables**:
```json
{
  "league": "NBA",  // or other leagues
  "request": {
    "gameIds": ["01995880-04f1-7d72-b570-8db37218b793", ...]  // Optional: specific games
  }
}
```

## Research Questions

### 1. Does the API provide odds/lines data?

**Status**: Unknown - needs investigation

**Possible Query Patterns to Test**:
- `GetOdds(gameId: ID!)`
- `GetLines(gameId: ID!)`
- `GetMarkets(gameId: ID!)`
- `game(id: ID!) { odds { ... } }`
- Nested odds in game query

### 2. What leagues are supported?

From the fragments, we can see support for:
- NBA (BasketballGameType)
- NFL/NCAAF (FootballGameType)
- NHL (IceHockeyGameType)
- Soccer (SoccerGameType)
- Tennis (TennisGameType)
- Golf (GolfGameType)
- MLB (BaseballGameType)

**Research Needed**: Query `LeagueEnum` to get all supported leagues

### 3. What sportsbooks are available?

**Status**: Unknown - needs investigation

### 4. What betting markets are available?

**Status**: Unknown - needs investigation

Possible markets:
- Moneyline
- Spread
- Total (Over/Under)
- Player props
- Team props
- Alternate lines

## Research Plan

### Phase 1: API Discovery (Current)

1. **GraphQL Introspection**
   - Query `__schema` to discover all available queries
   - Find queries related to odds, lines, markets, sportsbooks

2. **Test Common Query Patterns**
   - Try `GetOdds`, `GetLines`, `GetMarkets`
   - Try nested odds in game queries
   - Try sportsbook-specific queries

3. **League Enumeration**
   - Query `LeagueEnum` to get all supported leagues
   - Test queries for different sports

### Phase 2: Data Structure Analysis

1. **Odds Data Structure**
   - What format are odds returned in? (American, Decimal, Fractional)
   - What markets are available?
   - Are sportsbooks included?

2. **Update Frequency**
   - How often does the API update?
   - Is there real-time data or polling needed?

3. **Rate Limits**
   - What are the API rate limits?
   - Do we need to respect specific limits?

### Phase 3: Comparison with Current Approach

| Aspect | Selenium Scraping | GraphQL API |
|--------|------------------|-------------|
| **Speed** | Slow (2-3s per scrape) | Fast (API calls) |
| **Resources** | High (Chrome instances) | Low (HTTP requests) |
| **Reliability** | Fragile (UI changes break it) | Stable (API contract) |
| **Maintenance** | High (UI changes) | Low (API changes) |
| **Authentication** | Browser profile | Bearer token |
| **Data Completeness** | Full page data | API-defined fields |
| **Rate Limits** | Unknown | Need to discover |

## Implementation Plan (If API Works)

### Step 1: Create GraphQL Client

```python
class PickTheOddsAPIClient:
    def __init__(self, bearer_token: str):
        self.token = bearer_token
        self.base_url = "https://api.picktheodds.app/graphql"
    
    def query(self, query: str, variables: dict = None):
        # Make GraphQL request
        pass
    
    def get_games(self, league: str, game_ids: list = None):
        # Get games for league
        pass
    
    def get_odds(self, game_id: str):
        # Get odds for specific game
        pass
```

### Step 2: Replace Selenium Scraper

- Replace `pto_scraper.py` Selenium logic with API calls
- Keep same data structure for compatibility
- Update polling interval (could be faster with API)

### Step 3: Multi-Sport Support

- Support all leagues from API
- Map to our internal sport names
- Handle different game types (basketball, football, etc.)

## Potential Benefits

1. **Speed**: API calls are much faster than Selenium
2. **Reliability**: No browser automation issues
3. **Efficiency**: Lower resource usage
4. **Maintainability**: API contracts are more stable than UI
5. **Multi-Sport**: Could easily support all sports PTO offers

## Potential Challenges

1. **Authentication**: Token expiration/refresh
2. **Rate Limits**: May have strict limits
3. **Data Completeness**: May not have all data we need
4. **Cost**: May require subscription level
5. **Documentation**: May not have public docs

## Next Steps

1. **Run Research Script**: Execute `picktheodds_api_research.py` with valid token
2. **Analyze Results**: See what queries are available
3. **Test Odds Queries**: Try to get actual odds/lines data
4. **Compare Performance**: Benchmark API vs Selenium
5. **Implement If Viable**: Replace scraper if API works well

## Token Extraction Instructions

1. Open picktheodds.app in browser (logged in)
2. Open DevTools (F12)
3. Go to Network tab
4. Filter by "graphql"
5. Make any action on the site (load games, etc.)
6. Click on a GraphQL request
7. Look at Request Headers
8. Copy the `authorization: bearer ...` value
9. Use in research script

## Current System Architecture

### How We Currently Get Lines/Odds:

1. **Pinnacle Odds (NVP)**: Swordfish API (`swordfish-production.up.railway.app`)
   - Used for: EV calculations (comparing BetBCK vs Pinnacle)
   - Method: REST API
   - Speed: Fast (async requests)
   - Status: ✅ Working well

2. **BetBCK Lines**: HTML Scraping
   - Used for: Main betting lines (moneyline, spread, totals)
   - Method: HTML parsing with BeautifulSoup
   - Speed: Medium (async scraping)
   - Status: ⚠️ Fragile (HTML changes break it)

3. **Ace Lines (action23.ag)**: HTML Scraping
   - Used for: Additional sportsbook lines
   - Method: HTML parsing
   - Speed: Medium
   - Status: ⚠️ Fragile

4. **PTO Props**: Selenium Scraping
   - Used for: Player props with EV calculations
   - Method: Selenium browser automation
   - Speed: Slow (2-3 seconds per scrape)
   - Status: ⚠️ Resource-intensive, fragile

5. **Buckeye/Arcadia**: REST API
   - Used for: Game/sport data
   - Method: REST API
   - Speed: Fast
   - Status: ✅ Working

### What PickTheOdds API Could Replace:

**Potential Replacement For:**
- ✅ **PTO Props Scraping** (Selenium) - This is the main opportunity
- ❓ **BetBCK/Ace Lines** - If API provides sportsbook odds aggregation
- ❓ **Pinnacle NVP** - If API provides fair value calculations

## Key Findings from User's Example

### What the `GetGamesWithRequest` Query Returns:

```json
{
  "id": "01995880-04f1-7d72-b570-8db37218b793",
  "awayTeam": { "name": "Timberwolves", "abbreviations": ["MIN"] },
  "homeTeam": { "name": "Knicks", "abbreviations": ["NY", "NYK"] },
  "startDateTime": 1762389000,
  "leagueEnum": "NBA"
}
```

**What it DOESN'T return:**
- ❌ Odds/lines
- ❌ Sportsbooks
- ❌ Markets (moneyline, spread, total)
- ❌ Player props
- ❌ Fair value calculations

**Conclusion**: This query only provides game metadata, not betting data.

## Critical Questions to Answer

### 1. Does PickTheOdds API Provide Odds?

**Status**: ❓ Unknown - needs investigation

**Hypothesis**: The API likely has odds data because:
- PickTheOdds is an odds comparison site
- They display odds on their website
- The site wouldn't exist without odds data

**What to Test**:
- GraphQL introspection to find odds-related queries
- Try queries like `GetOdds`, `GetLines`, `GetMarkets`, `GetSportsbooks`
- Check if game queries have nested odds fields

### 2. What Sportsbooks Are Included?

**Status**: ❓ Unknown

**Hypothesis**: Likely includes major US books:
- DraftKings
- FanDuel
- BetMGM
- Caesars
- etc.

**What to Test**:
- Query for sportsbooks list
- Check if odds are aggregated or per-book

### 3. What Markets Are Available?

**Status**: ❓ Unknown

**Hypothesis**: Likely includes:
- Moneyline
- Spread
- Total (Over/Under)
- Player props (if subscription tier supports it)
- Team props

**What to Test**:
- Query market types
- Check subscription tier requirements

### 4. Does It Provide Fair Value/NVP?

**Status**: ❓ Unknown

**Hypothesis**: Possibly, since:
- PTO website shows EV calculations
- They have "Prop Builder" with EV filters
- They may calculate fair value from multiple sources

**What to Test**:
- Look for `fairValue`, `nvp`, `expectedValue` fields
- Check if calculations are included or need to be done client-side

## Comparison: Current vs. API Approach

### For PTO Props (Main Use Case):

| Aspect | Current (Selenium) | Potential (GraphQL API) |
|--------|-------------------|------------------------|
| **Speed** | 2-3 seconds per scrape | < 100ms per request |
| **Resources** | High (Chrome ~200MB RAM) | Low (HTTP requests) |
| **Reliability** | Fragile (UI changes) | Stable (API contract) |
| **Maintenance** | High (UI selectors break) | Low (API changes) |
| **Authentication** | Browser profile | Bearer token |
| **Rate Limits** | Unknown | Need to discover |
| **Data Completeness** | Full page (parsed) | API-defined fields |
| **Multi-Sport** | Yes (all PTO supports) | Yes (if API supports) |

**Winner**: GraphQL API (if it provides the data we need)

### For Other Sports Lines (BetBCK/Ace):

| Aspect | Current (HTML Scraping) | Potential (GraphQL API) |
|--------|------------------------|-------------------------|
| **Speed** | Medium (async scraping) | Fast (API calls) |
| **Reliability** | Fragile (HTML changes) | Stable (API contract) |
| **Sportsbooks** | BetBCK, Ace only | Multiple (if API aggregates) |
| **Data Quality** | Direct from books | May be aggregated |

**Winner**: Depends on API coverage and aggregation quality

## Implementation Strategy

### Phase 1: Discovery (Current)

1. **Extract Bearer Token**
   - From browser DevTools
   - Note expiration time
   - Test if it works from Python

2. **Run Introspection Query**
   - Discover all available queries
   - Find odds/lines-related queries
   - Document query structure

3. **Test Odds Queries**
   - Try common patterns
   - Test with NBA game ID
   - Check response structure

### Phase 2: Validation

1. **Test Data Completeness**
   - Compare API data vs Selenium scraped data
   - Check if all needed fields are available
   - Verify data accuracy

2. **Test Multi-Sport**
   - Try queries for NBA, NFL, NHL, MLB
   - Check if structure is consistent
   - Verify league enum values

3. **Test Rate Limits**
   - Make multiple requests
   - Check for rate limit headers
   - Test subscription tier requirements

### Phase 3: Implementation (If Viable)

1. **Create API Client**
   ```python
   class PickTheOddsAPIClient:
       def get_games(self, league: str) -> List[Dict]
       def get_odds(self, game_id: str) -> Dict
       def get_props(self, filters: Dict) -> List[Dict]
   ```

2. **Replace Selenium Scraper**
   - Keep same data structure for compatibility
   - Update polling interval (can be faster)
   - Handle token refresh

3. **Add Multi-Sport Support**
   - Map leagues to our internal names
   - Handle different game types
   - Support all PTO sports

## Expected Benefits

1. **10-30x Faster**: API calls vs Selenium
2. **Lower Resource Usage**: No Chrome instances
3. **More Reliable**: API contracts vs UI scraping
4. **Easier Maintenance**: Less code to maintain
5. **Better Scalability**: Can handle more sports easily

## Potential Challenges

1. **Token Management**: Expiration, refresh, subscription tier
2. **Rate Limits**: May have strict limits
3. **Data Completeness**: May not have all fields we need
4. **Cost**: May require specific subscription tier
5. **CORS**: May need proxy if called from frontend
6. **Documentation**: May not have public docs

## Next Steps

1. ✅ **Created Research Script**: `backend/picktheodds_api_research.py`
2. ⏳ **Extract Bearer Token**: Get from browser DevTools
3. ⏳ **Run Research Script**: Discover available queries
4. ⏳ **Test Odds Queries**: Verify we can get odds data
5. ⏳ **Compare with Current**: Benchmark performance
6. ⏳ **Implement If Viable**: Replace scraper if API works

## HTML Analysis Guide

If you have HTML from the PTO odds table, look for these clues:

### 1. Data Attributes
- Look for `data-*` attributes that might contain IDs or references:
  - `data-game-id`, `data-prop-id`, `data-market-id`
  - `data-sportsbook-id`, `data-odds-id`
  - These IDs might be used in GraphQL queries

### 2. CSS Classes
- The PTO scraper uses:
  - `div.css-ndwsoy` - prop card containers
  - `div[data-testid='prop-card']` - prop cards
  - `.css-hp68mp img` - sportsbook logos
- These classes might correspond to GraphQL data structures

### 3. JavaScript/React Props
- If you see React component props or data in the HTML:
  - Look for `data` or `props` attributes
  - These might reveal the GraphQL query structure
  - Check for `__NEXT_DATA__` or similar hydration data

### 4. Sportsbook Information
- Sportsbook logos have `aria-label` or `alt` attributes
- These indicate which books are included in the API
- Example: "DraftKings", "FanDuel", "BetMGM", etc.

### 5. Expected Value Data
- Look for EV percentages, fair values, or odds comparisons
- These might be calculated client-side or from the API
- Check if they're in data attributes or calculated from API responses

## Extracting GraphQL Queries from Browser

### Method 1: Network Tab (Recommended)

1. Open picktheodds.app in Chrome
2. Open DevTools (F12)
3. Go to **Network** tab
4. Filter by **"graphql"** or **"Fetch/XHR"**
5. Interact with the page (load games, change filters, etc.)
6. Click on GraphQL requests in the network tab
7. Look at the **Payload** tab to see:
   - The GraphQL query
   - Variables being sent
   - Request headers (including bearer token)

### Method 2: Console Network Interception

Run this in the browser console to log all GraphQL requests:

```javascript
// Intercept fetch requests
const originalFetch = window.fetch;
window.fetch = function(...args) {
    const url = args[0];
    if (url.includes('graphql')) {
        console.log('GraphQL Request:', url);
        console.log('Payload:', args[1]?.body);
    }
    return originalFetch.apply(this, args);
};

// Intercept XMLHttpRequest
const originalOpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    if (url.includes('graphql')) {
        console.log('GraphQL XHR Request:', url);
        this.addEventListener('load', function() {
            console.log('Response:', this.responseText);
        });
    }
    return originalOpen.apply(this, [method, url, ...rest]);
};
```

### Method 3: Apollo Client DevTools

If PTO uses Apollo Client:
1. Install Apollo Client DevTools extension
2. Open DevTools → Apollo tab
3. See all GraphQL queries and mutations

## What Queries to Look For

Based on the PTO page structure, look for queries with names like:
- `GetProps` / `GetPlayerProps`
- `GetExpectedValue` / `GetEVProps`
- `GetOddsComparison` / `GetBestOdds`
- `GetMarkets` / `GetPlayerMarkets`
- `GetSportsbooks` / `GetBooks`
- Queries with filters like `minEv`, `league`, `sport`

## Notes

- The token appears to be a JWT with user info and subscription level ("Advanced" package mentioned)
- Token may expire - need to handle refresh
- API may require specific subscription tier for access
- CORS may be restricted to picktheodds.app origin
- The `GetGamesWithRequest` query from user's example only returns metadata, not odds
- Need to find the actual odds/lines query through introspection
- **The HTML snippet you mentioned can help identify:**
  - Data attributes that might be GraphQL IDs
  - Sportsbook names that are available in the API
  - Market types and prop types that are supported
  - Expected value calculations (if they're in the HTML or calculated client-side)

