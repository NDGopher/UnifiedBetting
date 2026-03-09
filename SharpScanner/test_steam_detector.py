"""
Test the VWAP-based Steam Detector
Verifies the exact requirements from the prompt:
- price_delta >= 0.025 (2.5% move)
- orderbook_bid_depth > 1000 ($1000+ liquidity)
"""

import sys
sys.path.insert(0, '.')

from steam_detector_vwap import analyze_steam, calculate_liquidity_depth
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

def test_steam_detection():
    """Test steam detection with exact requirements"""
    
    print("=" * 80)
    print("TESTING STEAM DETECTOR - Exact Requirements")
    print("=" * 80)
    print()
    
    # Test Case 1: REAL STEAM (Should Alert)
    print("TEST 1: REAL STEAM - Price moved 3% with $1500 liquidity")
    print("-" * 80)
    
    prev_book = {
        'side_a': {
            'levels': [
                {'price': 0.50, 'volume': 2000, 'liquidity': 1000},  # $1000 at 50 cents
                {'price': 0.51, 'volume': 1000, 'liquidity': 510},   # $510 at 51 cents
                {'price': 0.52, 'volume': 500, 'liquidity': 260},    # $260 at 52 cents
            ]
        }
    }
    
    curr_book = {
        'side_a': {
            'levels': [
                {'price': 0.53, 'volume': 2000, 'liquidity': 1060},  # Price moved up 3%
                {'price': 0.54, 'volume': 1000, 'liquidity': 540},
                {'price': 0.55, 'volume': 500, 'liquidity': 275},
            ]
        }
    }
    
    result = analyze_steam(
        previous_orderbook=prev_book,
        current_orderbook=curr_book,
        min_liquidity=1000.0,
        min_depth=1000.0,  # $1000 requirement
        movement_threshold=0.025,  # 2.5%
        source="Polymarket"
    )
    
    print(f"✅ Is Steam: {result['is_steam']}")
    print(f"✅ Direction: {result['direction']}")
    print(f"✅ Move %: {result['move_pct']*100:.2f}%")
    print(f"✅ Liquidity Depth: ${result['liquidity_depth']:.0f}")
    print(f"✅ Message: {result['message']}")
    print()
    
    assert result['is_steam'] == True, "Should detect steam!"
    assert result['liquidity_depth'] >= 1000, "Should have $1000+ liquidity!"
    assert abs(result['move_pct']) >= 0.025, "Should have 2.5%+ move!"
    
    # Test Case 2: SLIPPAGE (Should Ignore - Low Liquidity)
    print("TEST 2: SLIPPAGE - Price moved 5% but only $200 liquidity")
    print("-" * 80)
    
    prev_book2 = {
        'side_a': {
            'levels': [
                {'price': 0.50, 'volume': 200, 'liquidity': 100},  # Only $100
            ]
        }
    }
    
    curr_book2 = {
        'side_a': {
            'levels': [
                {'price': 0.55, 'volume': 200, 'liquidity': 110},  # Moved 5% but thin
            ]
        }
    }
    
    result2 = analyze_steam(
        previous_orderbook=prev_book2,
        current_orderbook=curr_book2,
        min_liquidity=1000.0,
        min_depth=1000.0,
        movement_threshold=0.025,
        source="Polymarket"
    )
    
    print(f"✅ Is Steam: {result2['is_steam']}")
    print(f"✅ Message: {result2['message']}")
    print()
    
    assert result2['is_steam'] == False, "Should ignore slippage!"
    assert "IGNORE" in result2['message'], "Should say IGNORE!"
    
    # Test Case 3: NO MOVE (Should Ignore - Move < 2.5%)
    print("TEST 3: NO MOVE - Only 1% move with good liquidity")
    print("-" * 80)
    
    prev_book3 = {
        'side_a': {
            'levels': [
                {'price': 0.50, 'volume': 2000, 'liquidity': 1000},
            ]
        }
    }
    
    curr_book3 = {
        'side_a': {
            'levels': [
                {'price': 0.505, 'volume': 2000, 'liquidity': 1010},  # Only 1% move
            ]
        }
    }
    
    result3 = analyze_steam(
        previous_orderbook=prev_book3,
        current_orderbook=curr_book3,
        min_liquidity=1000.0,
        min_depth=1000.0,
        movement_threshold=0.025,
        source="Polymarket"
    )
    
    print(f"✅ Is Steam: {result3['is_steam']}")
    print(f"✅ Move %: {result3['move_pct']*100:.2f}%")
    print(f"✅ Message: {result3['message']}")
    print()
    
    assert result3['is_steam'] == False, "Should ignore small moves!"
    
    # Test Case 4: KALSHI Format (Cents)
    print("TEST 4: KALSHI Format - Price in cents")
    print("-" * 80)
    
    prev_book4 = {
        'side_a': {
            'levels': [
                {'price': 50, 'volume': 2000, 'liquidity': 1000},  # 50 cents = $1000
            ]
        }
    }
    
    curr_book4 = {
        'side_a': {
            'levels': [
                {'price': 53, 'volume': 2000, 'liquidity': 1060},  # 53 cents = 3% move
            ]
        }
    }
    
    result4 = analyze_steam(
        previous_orderbook=prev_book4,
        current_orderbook=curr_book4,
        min_liquidity=1000.0,
        min_depth=1000.0,
        movement_threshold=0.025,
        source="Kalshi"
    )
    
    print(f"✅ Is Steam: {result4['is_steam']}")
    print(f"✅ Move %: {result4['move_pct']*100:.2f}%")
    print(f"✅ Message: {result4['message']}")
    print()
    
    assert result4['is_steam'] == True, "Should detect steam for Kalshi!"
    
    print("=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print()
    print("Requirements Verified:")
    print("  ✅ price_delta >= 0.025 (2.5% move threshold)")
    print("  ✅ orderbook_bid_depth > 1000 ($1000+ liquidity requirement)")
    print("  ✅ Filters out slippage (low liquidity moves)")
    print("  ✅ Works with both Kalshi (cents) and Polymarket (probabilities)")

if __name__ == "__main__":
    test_steam_detection()

