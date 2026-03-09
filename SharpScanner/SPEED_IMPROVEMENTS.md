# Speed & Data Flow Improvements

## Changes Made

### 1. ✅ Disabled Main Line Selector
- **Problem:** Filtering out 144 out of 146 Kalshi markets (only 2 remaining)
- **Fix:** Completely disabled `select_main_line()` for now
- **Result:** All valid markets will show, not just "main lines"

### 2. ✅ Relaxed Filters
- **Odds Filter:** Changed from -150/+150 to -200/+200
- **Liquidity Filter:** Lowered from $1,000 to $500 minimum
- **Spread Range:** Expanded from -25/+25 to -50/+50
- **Result:** More markets will pass filters

### 3. ✅ Fixed Data Flow
- **Problem:** Data not reaching UI
- **Fix:** Ensured `st.session_state['data']` is always updated
- **Added:** Logging to show how many markets are sent to frontend
- **Result:** Data should now appear in UI

### 4. ✅ Added Missing Fields
- **Added:** `SideA_BestSource` and `SideB_BestSource` fields
- **Added:** `SideA_TotalLiquidity` and `SideB_TotalLiquidity` fields
- **Result:** Aggregation should work correctly

### 5. ✅ Fixed Sharp Side Detection
- **Changed:** Lower liquidity = sharp side (was backwards)
- **Result:** Sharp side detection should be correct

## Expected Results

After these changes:
- **Kalshi:** Should show all valid markets (not just 2)
- **Polymarket:** Should show all valid markets (not filtered out)
- **SX Bet:** Still needs investigation (0 markets found)
- **UI:** Should display data immediately
- **Speed:** Faster because less filtering

## Next Steps

1. Run scanner and verify data appears
2. Check if spreads are correct
3. Verify Kalshi markets show up
4. Check if Polymarket markets show up
5. Debug SX Bet if still showing 0

