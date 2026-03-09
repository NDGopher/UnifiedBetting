"""
Dam Break Detector - Detects when a Whale Wall is aggressively consumed.
This is a high-conviction signal indicating a fight happened and one side won.
"""

from typing import Dict, Optional
import time
import logging

logger = logging.getLogger(__name__)

# Global whale tracker (stores detected whales)
whale_tracker: Dict[str, Dict] = {}

def track_whale(market_id: str, side: str, price: float, volume: float, timestamp: float = None):
    """
    Store a detected whale in the tracker.
    
    Args:
        market_id: Unique identifier for the market (Event + Type + Line)
        side: "A" or "B" (dominant side)
        price: Wall price (probability or cents)
        volume: Wall volume (dollars)
        timestamp: Detection timestamp (defaults to current time)
    """
    if timestamp is None:
        timestamp = time.time()
    
    whale_tracker[market_id] = {
        'side': side,
        'price': price,
        'volume': volume,
        'timestamp': timestamp,
        'detected': True
    }
    
    logger.info(f"🐋 Whale tracked: {market_id} | Side {side} | Price {price:.3f} | Volume ${volume:,.0f}")

def check_dam_break(
    market_id: str,
    current_orderbook: Dict,
    current_side_a_depth: float,
    current_side_b_depth: float,
    source: str = "Kalshi",
    time_window: float = 60.0,
    volume_drop_threshold: float = 0.80  # 80% drop
) -> Optional[Dict]:
    """
    Check if a tracked whale wall has been broken (dam break).
    
    Conditions (ALL must be met):
    1. Wall Gone: Liquidity dropped by > 80%
    2. Price Breakthrough: Price moved past the wall price
    3. Time: Within 60 seconds of whale sighting
    
    Args:
        market_id: Unique identifier for the market
        current_orderbook: Current orderbook state
        current_side_a_depth: Current liquidity depth for side A
        current_side_b_depth: Current liquidity depth for side B
        source: "Kalshi" or "Polymarket"
        time_window: Time window in seconds (default 60)
        volume_drop_threshold: Volume drop threshold (default 0.80 = 80%)
    
    Returns:
        Dict with dam break info if detected, None otherwise
    """
    if market_id not in whale_tracker:
        return None
    
    whale_data = whale_tracker[market_id]
    current_time = time.time()
    time_since_detection = current_time - whale_data['timestamp']
    
    # Condition 3: Must be within time window
    if time_since_detection > time_window:
        # Whale expired - remove from tracker
        del whale_tracker[market_id]
        return None
    
    whale_side = whale_data['side']
    whale_price = whale_data['price']
    whale_volume = whale_data['volume']
    
    # Get current price and depth for the whale side
    side_a_levels = current_orderbook.get('side_a', {}).get('levels', [])
    side_b_levels = current_orderbook.get('side_b', {}).get('levels', [])
    
    if not side_a_levels or not side_b_levels:
        return None
    
    # Get current best prices
    if source == "Kalshi":
        current_ask = side_a_levels[0].get('price', 0) / 100.0  # Convert to probability
        current_bid = side_b_levels[0].get('price', 0) / 100.0
    else:  # Polymarket
        current_ask = side_a_levels[0].get('price', 0)
        current_bid = side_b_levels[0].get('price', 0)
    
    # Determine current depth for whale side
    if whale_side == "A":
        current_depth = current_side_a_depth
        current_price = current_ask
    else:  # whale_side == "B"
        current_depth = current_side_b_depth
        current_price = current_bid
    
    # Condition 1: Wall Gone - liquidity dropped by > 80%
    volume_drop = (whale_volume - current_depth) / whale_volume if whale_volume > 0 else 0
    wall_gone = volume_drop >= volume_drop_threshold
    
    # Condition 2: Price Breakthrough
    # If whale was on Side A (asks), price should drop (breakthrough downward)
    # If whale was on Side B (bids), price should rise (breakthrough upward)
    if whale_side == "A":
        # Whale was on asks (selling pressure) - price should drop
        price_breakthrough = current_price < whale_price
        direction = "DOWN"
    else:  # whale_side == "B"
        # Whale was on bids (buying pressure) - price should rise
        price_breakthrough = current_price > whale_price
        direction = "UP"
    
    # All conditions met - DAM BROKEN!
    if wall_gone and price_breakthrough:
        price_change = abs(current_price - whale_price)
        price_change_pct = (price_change / whale_price) * 100 if whale_price > 0 else 0
        
        result = {
            'is_dam_break': True,
            'whale_side': whale_side,
            'whale_price': whale_price,
            'whale_volume': whale_volume,
            'current_price': current_price,
            'current_depth': current_depth,
            'volume_drop': volume_drop,
            'price_change': price_change,
            'price_change_pct': price_change_pct,
            'direction': direction,
            'time_since_detection': time_since_detection,
            'message': f"🚨 DAM BROKEN! Side {whale_side}: ${whale_volume:,.0f} Buy Wall at {whale_price:.3f} was EATEN. Price moved {direction} to {current_price:.3f} ({price_change_pct:.1f}%). CHASE THIS."
        }
        
        # Remove from tracker (already broken)
        del whale_tracker[market_id]
        
        logger.warning(f"🚨 DAM BROKEN: {market_id} | {result['message']}")
        return result
    
    return None

def get_whale_tracker() -> Dict:
    """Get the current whale tracker state (for debugging/monitoring)."""
    return whale_tracker.copy()

def clear_expired_whales(time_window: float = 60.0):
    """Remove expired whales from tracker (older than time_window)."""
    current_time = time.time()
    expired_ids = [
        market_id for market_id, whale_data in whale_tracker.items()
        if current_time - whale_data['timestamp'] > time_window
    ]
    for market_id in expired_ids:
        del whale_tracker[market_id]
    return len(expired_ids)

# Example usage and test
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.StreamHandler(sys.stdout)])
    
    print("=" * 80)
    print("TESTING DAM BREAK DETECTOR")
    print("=" * 80)
    print()
    
    # Test: Track a whale, then detect dam break
    market_id = "Lakers vs Warriors|Spread|-4.5"
    
    # Step 1: Track a whale
    print("STEP 1: Tracking whale...")
    track_whale(market_id, side="A", price=0.55, volume=25000.0)
    print(f"✅ Whale tracked: {get_whale_tracker()}")
    print()
    
    # Step 2: Simulate dam break (wall gone, price moved)
    print("STEP 2: Checking for dam break...")
    current_orderbook = {
        'side_a': {
            'levels': [
                {'price': 0.52, 'volume': 1000, 'liquidity': 520},  # Price dropped, wall gone
            ]
        },
        'side_b': {
            'levels': [
                {'price': 0.48, 'volume': 1000, 'liquidity': 480},
            ]
        }
    }
    
    result = check_dam_break(
        market_id=market_id,
        current_orderbook=current_orderbook,
        current_side_a_depth=2000.0,  # Dropped from $25k to $2k (92% drop)
        current_side_b_depth=480.0,
        source="Polymarket"
    )
    
    if result:
        print(f"✅ DAM BROKEN DETECTED!")
        print(f"✅ Message: {result['message']}")
        print(f"✅ Volume Drop: {result['volume_drop']*100:.1f}%")
        print(f"✅ Price Change: {result['price_change_pct']:.1f}%")
    else:
        print("❌ No dam break detected")
    
    print()
    print("=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)

