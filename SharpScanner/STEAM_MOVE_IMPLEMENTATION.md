# Steam Move Detection - Implementation Complete

## ✅ Features Implemented

### 1. **Frontend Threshold Control**
- **Location:** Sidebar → "Steam Move Detection" section
- **Control:** Slider "Steam Move Threshold (%)"
- **Range:** 1% to 20%
- **Default:** 3% (lowered from 6% to catch more moves)
- **Behavior:** Real-time adjustment, stored in session state
- **Help Text:** "Percentage price change required to trigger steam move alert (lower = more sensitive)"

### 2. **Enhanced Steam Move Alerts**
- **Section Title:** "🔥 STEAM MOVES DETECTED - ACT NOW!"
- **Display Location:** Top of dashboard (before main table)
- **Information Shown:**
  - Event name, Type, Line
  - Move percentage
  - Direction (FAVORITE_WORSE, FAVORITE_BETTER, UNDERDOG_WORSE, UNDERDOG_BETTER)
  - Bet recommendation
  - Previous → Current odds
  - Side A and Side B best odds (as metrics)
- **Sorting:** By move percentage (largest first)
- **Visual:** Red error boxes for each move
- **Always Visible:** Shows status even when no moves detected

### 3. **Real-Time Monitoring**
- **Refresh Rate:** 15 seconds (auto-refresh)
- **Price Tracking:** Stores previous prices in session state
- **Time Window:** Detects moves within 15-second window
- **Status Indicator:** 
  - Green checkmark if last update < 20s ago
  - Warning if > 20s ago
- **Timestamp:** Shows last update time and seconds since update

### 4. **Price Movement Logic**
- **Tracks:** Both Side A and Side B prices separately
- **Calculates:** Percentage change for each side
- **Detects:** Largest move across both sides
- **Directions:**
  - `FAVORITE_WORSE`: Favorite odds got worse (e.g., -150 → -125) → Bet other side
  - `FAVORITE_BETTER`: Favorite odds got better (e.g., -125 → -150) → Bet favorite
  - `UNDERDOG_WORSE`: Underdog odds got worse (e.g., +125 → +150) → Bet favorite
  - `UNDERDOG_BETTER`: Underdog odds got better (e.g., +150 → +125) → Bet underdog

## 🎯 How to Use

### Step 1: Start the Scanner
```bash
streamlit run sharp_scanner_auth.py
```

### Step 2: Adjust Threshold
1. Look at sidebar → "Steam Move Detection" section
2. Use slider to set threshold (default: 3%)
3. **Lower threshold (1-2%):** More sensitive, catches smaller moves
4. **Higher threshold (5-10%):** Only major moves, fewer alerts

### Step 3: Monitor for Moves
- Watch the top section: "🔥 STEAM MOVES DETECTED"
- Check timestamp to verify real-time updates
- Look for red highlighted rows in main table

### Step 4: Act on Alerts
- Read the bet recommendation
- Check previous → current odds
- Compare to your soft book
- Execute if edge exists

## 📊 What You'll See

### When Moves Detected:
```
🔥 STEAM MOVES DETECTED - ACT NOW!

[Red Error Box]
Spurs vs Pelicans | Spread Spurs -9.5 | 8.5% move | FAVORITE_WORSE
💡 Bet OTHER SIDE - Favorite got worse
Odds moved: -110 → -125
Side A: -125 | Side B: +105
```

### When No Moves:
```
📊 No steam moves detected (3%+ threshold). 
Monitoring for price movements in real-time...
```

## 🔧 Technical Details

### Threshold Calculation
- User sets percentage (e.g., 3%)
- Converted to decimal (0.03)
- Stored in `st.session_state['movement_threshold']`
- Passed to `track_price_movements()` function

### Price Tracking
- Previous prices stored in `st.session_state['previous_prices']`
- Key: `(Event, Type, Line)`
- Value: `{'timestamp': float, 'side_a_odds': int, 'side_b_odds': int}`
- Updated after each fetch cycle

### Movement Detection
- Compares current prices to previous prices
- Calculates percentage change: `abs((new - old) / old)`
- Checks if change >= threshold
- Records direction and recommendation

## 🚀 Testing Recommendations

1. **Start with 3% threshold** (default)
2. **Run for 5-10 minutes** to establish baseline
3. **Lower to 1-2%** if no moves detected
4. **Watch active markets** (NFL/NBA games in progress)
5. **Verify recommendations** make sense
6. **Check real-time updates** via timestamp

## ⚠️ Important Notes

- **Threshold is per-side:** If Side A moves 2% and Side B moves 4%, the 4% move is detected
- **15-second window:** Only detects moves within 15 seconds of previous fetch
- **Requires 2+ cycles:** First fetch establishes baseline, second fetch detects moves
- **Real-time means:** Updates every 15 seconds, not instant

## 📈 Expected Results

- **Active markets:** Should see moves during game time
- **Inactive markets:** Fewer moves, mostly during news/lineup changes
- **High liquidity markets:** More stable, fewer moves
- **Low liquidity markets:** More volatile, more moves

## 🎯 Success Criteria

✅ Threshold slider visible and functional
✅ Moves detected when prices change
✅ Alerts show correct information
✅ Recommendations make sense
✅ Real-time updates working (timestamp < 20s)
✅ Can adjust threshold on the fly

---

**Ready to test!** Run the scanner and watch for steam moves. Adjust threshold as needed to catch the moves you want.

