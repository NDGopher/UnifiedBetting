# Multi-Book Odds Integration Research

## Overview
Research plan for integrating DraftKings and FanDuel odds into EV calculations, starting with NHL.

## Current State
- **Pinnacle odds**: Fetched via Swordfish API
- **BetBCK odds**: Scraped from betbck.com
- **EV calculation**: Compares BetBCK vs Pinnacle NVP
- **Result display**: Shows BetBCK odds, Pinnacle NVP, and EV%

## Proposed Enhancement
Add DraftKings and FanDuel odds to the pipeline to show:
- Which books have +EV opportunities
- Best EV across all books (BetBCK, DraftKings, FanDuel)
- Comparison of odds across all books

## Target URLs

### DraftKings NHL
- **URL**: `https://sportsbook.draftkings.com/leagues/hockey/nhl`
- **Structure**: All NHL games on one page
- **Rate limiting risk**: Low (one request per sport)

### FanDuel NHL  
- **URL**: `https://sportsbook.fanduel.com/navigation/nhl`
- **Structure**: All NHL games on one page
- **Rate limiting risk**: Low (one request per sport)

## Implementation Plan

### Phase 1: NHL Scrapers (Proof of Concept)

#### 1. DraftKings Scraper (`draftkings_scraper.py`)
```python
class DraftKingsScraper:
    def scrape_nhl_games(self) -> List[Dict]:
        """
        Scrape all NHL games from DraftKings
        Returns: List of games with odds
        Structure:
        {
            "home_team": "Knicks",
            "away_team": "Timberwolves", 
            "moneyline_home": "+110",
            "moneyline_away": "-130",
            "spreads": [...],
            "totals": [...],
            "sport": "nhl"
        }
        """
```

#### 2. FanDuel Scraper (`fanduel_scraper.py`)
```python
class FanDuelScraper:
    def scrape_nhl_games(self) -> List[Dict]:
        """
        Scrape all NHL games from FanDuel
        Returns: Same structure as DraftKings
        """
```

### Phase 2: Integration into EV Pipeline

#### Modified Workflow
```
1. Match Pinnacle events to BetBCK games (existing)
2. Calculate EV vs Pinnacle (existing)
3. If +EV found OR if multi-book mode enabled:
   a. Scrape DraftKings NHL page
   b. Scrape FanDuel NHL page
   c. Match games by team names + date
   d. Calculate EV for each book vs Pinnacle
   e. Show best opportunity across all books
```

#### Modified EV Calculation
```python
def calculate_ev_multi_book(matched_game, pinnacle_data, all_books_data):
    """
    Calculate EV for a game across all books
    Returns:
    {
        "event_id": "12345",
        "pinnacle_nvp": "+110",
        "betbck_odds": "+115",
        "betbck_ev": "+4.5%",
        "draftkings_odds": "+112",
        "draftkings_ev": "+1.8%",
        "fanduel_odds": "+113",
        "fanduel_ev": "+2.7%",
        "best_book": "betbck",
        "best_ev": "+4.5%"
    }
    """
```

### Phase 3: Frontend Display

#### Enhanced Table Columns
- **Current**: Matchup | League | Bet | Book Odds | Pin NVP | EV
- **Enhanced**: Matchup | League | Bet | BetBCK | DK | FD | Pin NVP | Best EV | Best Book

#### Display Logic
- Show all books with odds if available
- Highlight best book (highest EV)
- Show EV for each book
- Only show books that have +EV (optional filter)

## Technical Considerations

### 1. Rate Limiting
- **DraftKings**: One request per sport (NHL page loads all games)
- **FanDuel**: One request per sport (NHL page loads all games)
- **Frequency**: Only scrape when +EV found or on-demand
- **Risk**: Low (not frequent requests)

### 2. Game Matching
- Match by team names (normalized)
- Match by date/time
- Handle team name variations (e.g., "NY Rangers" vs "New York Rangers")

### 3. Performance
- Scrape DraftKings/FanDuel in parallel
- Cache results per game (avoid re-scraping same game)
- Only scrape for games that have +EV vs Pinnacle (optional optimization)

### 4. Data Structure
```python
{
    "event_id": "12345",
    "home_team": "Knicks",
    "away_team": "Timberwolves",
    "pinnacle_nvp": "+110",
    "books": {
        "betbck": {
            "moneyline_home": "+115",
            "ev": "+4.5%"
        },
        "draftkings": {
            "moneyline_home": "+112", 
            "ev": "+1.8%"
        },
        "fanduel": {
            "moneyline_home": "+113",
            "ev": "+2.7%"
        }
    },
    "best_book": "betbck",
    "best_ev": "+4.5%"
}
```

## Implementation Steps

### Step 1: Create DraftKings Scraper
- Scrape NHL page
- Parse HTML for games and odds
- Return structured data

### Step 2: Create FanDuel Scraper  
- Scrape NHL page
- Parse HTML for games and odds
- Return structured data

### Step 3: Integrate into Pipeline
- Add multi-book scraping step (after EV calculation)
- Match games to Pinnacle events
- Calculate EV for each book

### Step 4: Update Frontend
- Add columns for DraftKings and FanDuel
- Show best book indicator
- Display EV for each book

## Questions to Answer

1. **HTML Structure**: How are games structured on DraftKings/FanDuel pages?
2. **Authentication**: Do these pages require login?
3. **Rate Limiting**: What's the actual rate limit behavior?
4. **Team Name Matching**: How do team names differ between books?
5. **Market Matching**: How to match spreads/totals across books (line matching)?

## Next Steps

1. Manually inspect DraftKings NHL page HTML structure
2. Manually inspect FanDuel NHL page HTML structure
3. Create proof-of-concept scraper for one game
4. Test matching logic with real data
5. Integrate into pipeline

## References
- DraftKings NHL: https://sportsbook.draftkings.com/leagues/hockey/nhl
- FanDuel NHL: https://sportsbook.fanduel.com/navigation/nhl

