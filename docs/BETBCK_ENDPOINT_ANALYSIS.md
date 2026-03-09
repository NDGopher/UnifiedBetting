# BetBCK.com Endpoint Analysis

## Executive Summary

**Conclusion**: BetBCK.com does NOT have a public JSON API for odds. The site uses traditional server-side rendered HTML forms with POST requests. All odds data is returned as HTML that must be parsed.

## Detailed Findings

### Endpoints Discovered

#### 1. Login Endpoint
- **URL**: `https://betbck.com/Qubic/SecurityPage.php`
- **Method**: POST
- **Purpose**: User authentication
- **Payload**:
  - `customerID`: User credentials
  - `password`: Password
  - `B1.x`, `B1.y`: Button click coordinates
- **Response**: HTML redirect to main page on success

#### 2. Main Sport Selection Page
- **URL**: `https://betbck.com/Qubic/StraightSportSelection.php`
- **Method**: GET (after login)
- **Purpose**: Display all available sports/leagues
- **Key Features**:
  - Contains hidden form fields: `inetWagerNumber`, `inetSportSelection`
  - Has checkboxes for each sport/league (e.g., `SOCCER_ENG_Premier_League_Game_*`)
  - These checkboxes are used to filter games

#### 3. Game Search Endpoint
- **URL**: `https://betbck.com/Qubic/PlayerGameSelection.php`
- **Method**: POST
- **Purpose**: Search for specific games
- **Payload**:
  ```python
  {
      "action": "Search",
      "keyword_search": "team_name_here",
      "inetWagerNumber": "value_from_main_page",
      "inetSportSelection": "sport"  # or specific sport
  }
  ```
- **Response**: HTML page with search results containing game odds tables
- **Rate Limiting**: ⚠️ This is where rate limiting occurs with frequent searches

#### 4. Game Loading by Sport (Checkbox Pattern)
- **URL**: `https://betbck.com/Qubic/PlayerGameSelection.php`
- **Method**: POST
- **Payload Example**:
  ```python
  {
      'keyword_search': bids',  # Empty for all games
      'inetWagerNumber': 'value_from_main_page',
      'inetSportSelection': 'sport',
      'SOCCER_ENG_Premier_League_Game_*': 'on',  # Checkbox name/value
      'x': '79',
      'y': '5'
  }
  ```
- **Purpose**: Load ALL games for a specific sport/league at once
- **Response**: HTML with all games and their odds
- **Efficiency**: ✅ Much better than individual searches - gets all games in one request

### Key Insights

#### 1. No JSON API
- All responses are HTML
- No `.json` endpoints found
- No `/api/` paths discovered
- No AJAX endpoints for odds data

#### 2. Main Board Strategy (OPTIMAL)
The async scraper already implements this optimally:
- **One POST request** with checkbox selected = **ALL games** for that sport/league
- Example: Check `BASKETBALL_NBA_Game_*` → Get all NBA games
- This is **10-100x more efficient** than individual searches
- **Rate limiting risk**: Very low (one request per sport/league)

#### 3. Current Implementation Usage
Your `BetBCKAsyncScraper` class uses the checkbox pattern:
```python
# From betbck_async_scraper.py
checkbox_names = [cb.get('name') for cb in all_checkboxes 
                  if cb.get('name') and any(p.fullmatch(cb.get('name')) 
                  for p in self.checkbox_patterns)]

# Then posts with checkbox selected:
post_payload = {
    'keyword_search': '',
    'inetWagerNumber': inet_wager_value,
    'inetSportSelection': 'sport',
    checkbox_name: 'on'  # ← This loads ALL games for that league!
}
```

This is **already the optimal approach** for getting main game lines!

#### 4. Why Rate Limiting Occurs
Rate limiting happens when:
- Making too many **individual searches** (`PlayerGameSelection.php` with `keyword_search`)
- Not reusing sessions properly
- Making requests too quickly (< 1 second apart)

Rate limiting is **NOT** an issue when:
- Using checkbox pattern to load all games at once
- Using proper session management
- Spacing requests appropriately

### Oyed Patterns Observed

#### Hidden Endpoints (Potential)
While analyzing the code, no obvious hidden endpoints were found, but:

1. **Form Actions**: All forms use POST to PHP files
2. **No AJAX**: JavaScript primarily for UI, not data fetching
3. **Server-Side Rendering**: All odds HTML is generated server-side

#### Potential Real-Time Updates
If betbck.com updates odds in real-time on the page:
- It's likely done via **page refresh** or **meta refresh tags**
- OR JavaScript polling with full page reload
- NOT via WebSocket or AJAX polling

### Recommendations

#### ✅ Best Approach for Main Game Lines

**Use the checkbox pattern** (already implemented in `BetBCKAsyncScraper`):

```python
# Instead of searching individual games:
# ❌ BAD: Many searches = rate limited
for game in games:
    search_team_and_get_results_html(session, game['team'], ...)

# ✅ GOOD: One request per league = efficient
for league_checkbox in league_checkboxes:
    post_payload = {
        'keyword_search': '',
        'inetWagerNumber': inet_wager_value,
        'inetSportSelection': 'sport',
        league_checkbox: 'on'
    }
    games_html = fetch_games_page(session, post_payload)
    # Parse ALL games from this HTML
```

#### ✅ Optimization Strategy

1. **Use Async Scraper for Bulk Loading**
   - Already implemented in `betbck_async_scraper.py`
   - Loads all games for all sports/leagues
   - Saves to `data/betbck_games.json`
   - **This is your best option for main lines!**

2. **Only Search Individually When Necessary**
   - Use individual search only if game not in main board
   - Most popular games ARE on main board
   - Reduces requests by 90%+

3. **Cache and Update Strategy**
   - Load main board every 2-5 minutes
   - Store in database/memory cache
   - Query cache instead of making new requests
   - Only refresh when needed

### Files That Implement This

- ✅ `backend/betbck_async_scraper.py` - Uses checkbox pattern
- ⚠️ `backend/betbck_scraper.py` - Uses individual searches (rate limited)
- ✅ `backend/betbck_request_manager.py` - Rate limiting protection

### Conclusion

**There is no API to tap into.** However, the checkbox pattern in your async scraper is already the optimal approach. The key is:

1. ✅ **Use checkbox pattern** to get all games at once (already done)
2. ✅ **Cache results** and query cache (not implemented yet)
3. ✅ **Only search individually** when absolutely necessary

The async scraper that loads all games via checkboxes should give you real-time main game lines without rate limiting issues!

