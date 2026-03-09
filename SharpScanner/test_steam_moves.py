"""
Deep dive test script for steam move detection.
Runs the scanner and analyzes results for price movements.
"""
import sys
import time
from datetime import datetime
from typing import Dict, List

# Mock Streamlit for testing
class MockStreamlit:
    def __init__(self):
        self.session_state = {
            'data': [],
            'previous_prices': {},
            'movement_threshold': 0.03,  # 3% default
            'last_update': datetime.now()
        }
    
    def set_page_config(self, *args, **kwargs):
        pass
    
    def title(self, *args, **kwargs):
        pass
    
    def sidebar(self):
        return self
    
    def header(self, *args, **kwargs):
        pass
    
    def slider(self, *args, **kwargs):
        return 3  # 3%
    
    def checkbox(self, *args, **kwargs):
        return True
    
    def button(self, *args, **kwargs):
        return False
    
    def get(self, key, default=None):
        return self.session_state.get(key, default)

# Replace streamlit with mock
sys.modules['streamlit'] = MockStreamlit()
import streamlit as st
st = MockStreamlit()

# Now import the scanner functions
from sharp_scanner_auth import (
    fetch_all_markets,
    aggregate_markets_across_exchanges,
    track_price_movements
)

def test_steam_moves():
    """Test steam move detection with real data."""
    print("=" * 80)
    print("STEAM MOVE DETECTION TEST")
    print("=" * 80)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Movement threshold: {st.session_state['movement_threshold'] * 100}%")
    print()
    
    # Fetch initial data
    print("📡 Fetching initial market data...")
    raw_data = fetch_all_markets()
    print(f"✅ Fetched {len(raw_data)} raw markets")
    
    if not raw_data:
        print("❌ No data fetched. Check API connections.")
        return
    
    # Aggregate across exchanges
    print("\n🔄 Aggregating markets across exchanges...")
    aggregated = aggregate_markets_across_exchanges(raw_data)
    print(f"✅ Aggregated to {len(aggregated)} unique markets")
    
    # Store initial prices
    print("\n💾 Storing initial prices for tracking...")
    initial_prices = {}
    for market in aggregated:
        key = (market.get('Event', ''), market.get('Type', ''), market.get('Line', ''))
        initial_prices[key] = {
            'timestamp': time.time(),
            'side_a_odds': market.get('SideA_BestOdds'),
            'side_b_odds': market.get('SideB_BestOdds')
        }
    st.session_state['previous_prices'] = initial_prices
    print(f"✅ Stored prices for {len(initial_prices)} markets")
    
    # Wait and fetch again to detect moves
    print("\n⏳ Waiting 20 seconds to detect price movements...")
    print("   (This simulates real-time monitoring)")
    time.sleep(20)
    
    # Fetch again
    print("\n📡 Fetching updated market data...")
    raw_data_2 = fetch_all_markets()
    print(f"✅ Fetched {len(raw_data_2)} raw markets")
    
    # Aggregate again
    print("\n🔄 Aggregating updated markets...")
    aggregated_2 = aggregate_markets_across_exchanges(raw_data_2)
    print(f"✅ Aggregated to {len(aggregated_2)} unique markets")
    
    # Track movements
    print("\n🔍 Tracking price movements...")
    threshold = st.session_state['movement_threshold']
    markets_with_moves = track_price_movements(aggregated_2, initial_prices, threshold)
    
    # Analyze results
    moves_detected = [m for m in markets_with_moves if m.get('PriceMove')]
    
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Total markets analyzed: {len(markets_with_moves)}")
    print(f"Steam moves detected: {len(moves_detected)}")
    print(f"Threshold used: {threshold * 100}%")
    print()
    
    if moves_detected:
        print("🔥 STEAM MOVES DETECTED:")
        print("-" * 80)
        for idx, market in enumerate(moves_detected, 1):
            event = market.get('Event', 'Unknown')
            m_type = market.get('Type', '')
            line = market.get('Line', '')
            move_pct = market.get('PriceMove', '')
            direction = market.get('PriceMoveDirection', '')
            recommendation = market.get('BetRecommendation', '')
            prev_odds = market.get('PreviousOdds', '')
            current_odds = market.get('CurrentOdds', '')
            side_a_odds = market.get('SideA_BestOdds', 'N/A')
            side_b_odds = market.get('SideB_BestOdds', 'N/A')
            
            print(f"\n{idx}. {event} | {m_type} {line}")
            print(f"   Move: {move_pct} | Direction: {direction}")
            print(f"   Previous Odds: {prev_odds} → Current: {current_odds}")
            print(f"   Side A: {side_a_odds} | Side B: {side_b_odds}")
            if recommendation:
                print(f"   💡 {recommendation}")
    else:
        print("📊 No steam moves detected at current threshold.")
        print(f"   Try lowering the threshold below {threshold * 100}% to catch smaller moves.")
    
    # Show sample markets for reference
    print("\n" + "=" * 80)
    print("SAMPLE MARKETS (for reference)")
    print("=" * 80)
    for idx, market in enumerate(aggregated_2[:5], 1):
        event = market.get('Event', 'Unknown')
        m_type = market.get('Type', '')
        line = market.get('Line', '')
        side_a = market.get('SideA_BestOdds', 'N/A')
        side_b = market.get('SideB_BestOdds', 'N/A')
        sharp_side = market.get('SharpSide', '')
        sharp_odds = market.get('SharpOdds', 'N/A')
        imbalance = market.get('ImbalanceRatio', 1.0)
        
        print(f"{idx}. {event} | {m_type} {line}")
        print(f"   Side A: {side_a} | Side B: {side_b}")
        print(f"   Sharp Side: {sharp_side} @ {sharp_odds} | Imbalance: {imbalance}x")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_steam_moves()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

