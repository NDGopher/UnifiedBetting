"""
Market Quality Filters - "Gatekeeper Filters"
Eliminates noise and ensures we only analyze high-quality, actionable sports lines.
"""

from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

def calculate_midpoint_price(orderbook: Dict, source: str = "Kalshi") -> Optional[float]:
    """
    Calculate the midpoint price from the orderbook.
    
    Args:
        orderbook: Orderbook dict with 'side_a' and 'side_b' containing 'levels'
        source: "Kalshi" or "Polymarket"
    
    Returns:
        Midpoint price (0.0-1.0 probability) or None if unavailable
    """
    side_a_levels = orderbook.get('side_a', {}).get('levels', [])
    side_b_levels = orderbook.get('side_b', {}).get('levels', [])
    
    if not side_a_levels or not side_b_levels:
        return None
    
    # Get best ask (side_a) and best bid (side_b)
    best_ask = side_a_levels[0].get('price', 0)
    
    if source == "Kalshi":
        # Kalshi: side_a = Yes asks, side_b = No asks (inverted)
        best_bid = side_b_levels[0].get('price', 0)
        # Convert cents to probability
        ask_prob = best_ask / 100.0
        bid_prob = best_bid / 100.0
    else:  # Polymarket
        # Polymarket: side_a = Yes asks, side_b = No bids
        best_bid = side_b_levels[0].get('price', 0)
        ask_prob = best_ask  # Already probability
        bid_prob = best_bid  # Already probability
    
    # Calculate midpoint
    if ask_prob > 0 and bid_prob > 0:
        midpoint = (ask_prob + bid_prob) / 2.0
        return midpoint
    
    return None

def calculate_spread_width(orderbook: Dict, source: str = "Kalshi") -> Optional[float]:
    """
    Calculate the spread width (BestAsk - BestBid).
    
    Args:
        orderbook: Orderbook dict with 'side_a' and 'side_b' containing 'levels'
        source: "Kalshi" or "Polymarket"
    
    Returns:
        Spread width (in cents for Kalshi, probability for Polymarket) or None
    """
    side_a_levels = orderbook.get('side_a', {}).get('levels', [])
    side_b_levels = orderbook.get('side_b', {}).get('levels', [])
    
    if not side_a_levels or not side_b_levels:
        return None
    
    best_ask = side_a_levels[0].get('price', 0)
    
    if source == "Kalshi":
        # Kalshi: side_a = Yes asks, side_b = No asks (inverted)
        best_bid = side_b_levels[0].get('price', 0)
        # Spread in cents
        spread = abs(best_ask - best_bid)
    else:  # Polymarket
        # Polymarket: side_a = Yes asks, side_b = No bids
        best_bid = side_b_levels[0].get('price', 0)
        # Spread in probability (0-1)
        spread = abs(best_ask - best_bid)
    
    return spread

def passes_gold_zone_filter(orderbook: Dict, source: str = "Kalshi") -> Tuple[bool, Optional[float], Optional[float]]:
    """
    "Gold Zone" Price Filter: Only process markets where midpoint is between 20-80 cents.
    
    This eliminates:
    - Extreme longshots (1-10 cents)
    - Lock-ins (>90 cents)
    - Junk liquidity
    
    Args:
        orderbook: Orderbook dict
        source: "Kalshi" or "Polymarket"
    
    Returns:
        Tuple of (passes_filter, midpoint_price, spread_width)
        - passes_filter: True if midpoint is between 0.20 and 0.80
        - midpoint_price: The calculated midpoint (0.0-1.0)
        - spread_width: The spread width (for logging)
    """
    midpoint = calculate_midpoint_price(orderbook, source)
    spread_width = calculate_spread_width(orderbook, source)
    
    if midpoint is None:
        return (False, None, spread_width)
    
    # Gold Zone: 20-80 cents (0.20 - 0.80 probability)
    passes = 0.20 <= midpoint <= 0.80
    
    return (passes, midpoint, spread_width)

def passes_tight_spread_filter(orderbook: Dict, source: str = "Kalshi", max_spread: float = 0.04) -> Tuple[bool, Optional[float]]:
    """
    "Tight Spread" Guarantee: Only process markets with spread <= 4 cents (or 4% for Polymarket).
    
    This ensures we only analyze accurate, real-time lines.
    Wide spreads indicate stale or broken markets.
    
    Args:
        orderbook: Orderbook dict
        source: "Kalshi" or "Polymarket"
        max_spread: Maximum allowed spread (0.04 = 4 cents for Kalshi, 0.04 = 4% for Polymarket)
    
    Returns:
        Tuple of (passes_filter, spread_width)
    """
    spread_width = calculate_spread_width(orderbook, source)
    
    if spread_width is None:
        return (False, None)
    
    # For Kalshi: spread is in cents, max_spread = 0.04 means 4 cents
    # For Polymarket: spread is in probability, max_spread = 0.04 means 4%
    passes = spread_width <= max_spread
    
    return (passes, spread_width)

def passes_quality_filters(orderbook: Dict, source: str = "Kalshi") -> Dict:
    """
    Apply all quality filters (Gold Zone + Tight Spread).
    
    This is the "Gatekeeper" that eliminates noise before Steam/Whale detection.
    
    Args:
        orderbook: Orderbook dict
        source: "Kalshi" or "Polymarket"
    
    Returns:
        Dict with:
        - 'passes': bool (True if passes all filters)
        - 'midpoint': float (midpoint price)
        - 'spread_width': float (spread width)
        - 'reason': str (reason for rejection if fails)
    """
    result = {
        'passes': False,
        'midpoint': None,
        'spread_width': None,
        'reason': None
    }
    
    # Check Gold Zone filter
    gold_zone_pass, midpoint, spread_width = passes_gold_zone_filter(orderbook, source)
    result['midpoint'] = midpoint
    result['spread_width'] = spread_width
    
    if not gold_zone_pass:
        if midpoint is None:
            result['reason'] = "No orderbook data"
        elif midpoint < 0.20:
            result['reason'] = f"Midpoint too low ({midpoint:.3f} < 0.20) - extreme longshot"
        else:  # midpoint > 0.80
            result['reason'] = f"Midpoint too high ({midpoint:.3f} > 0.80) - lock-in"
        return result
    
    # Check Tight Spread filter
    spread_pass, spread_width_check = passes_tight_spread_filter(orderbook, source, max_spread=0.04)
    
    if not spread_pass:
        result['reason'] = f"Spread too wide ({spread_width_check:.3f} > 0.04) - illiquid/stale"
        return result
    
    # Passed all filters
    result['passes'] = True
    return result

# Example usage and test
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.StreamHandler(sys.stdout)])
    
    print("=" * 80)
    print("TESTING MARKET QUALITY FILTERS")
    print("=" * 80)
    print()
    
    # Test Case 1: PASSES (Gold Zone + Tight Spread)
    print("TEST 1: PASSES - Midpoint 0.50, Spread 0.02")
    print("-" * 80)
    orderbook1 = {
        'side_a': {
            'levels': [
                {'price': 0.51, 'volume': 1000, 'liquidity': 510},  # Ask
            ]
        },
        'side_b': {
            'levels': [
                {'price': 0.49, 'volume': 1000, 'liquidity': 490},  # Bid
            ]
        }
    }
    
    result1 = passes_quality_filters(orderbook1, source="Polymarket")
    print(f"✅ Passes: {result1['passes']}")
    print(f"✅ Midpoint: {result1['midpoint']:.3f}")
    print(f"✅ Spread: {result1['spread_width']:.3f}")
    print(f"✅ Reason: {result1['reason']}")
    print()
    
    # Test Case 2: FAILS (Midpoint too low)
    print("TEST 2: FAILS - Midpoint 0.10 (extreme longshot)")
    print("-" * 80)
    orderbook2 = {
        'side_a': {
            'levels': [
                {'price': 0.11, 'volume': 1000, 'liquidity': 110},
            ]
        },
        'side_b': {
            'levels': [
                {'price': 0.09, 'volume': 1000, 'liquidity': 90},
            ]
        }
    }
    
    result2 = passes_quality_filters(orderbook2, source="Polymarket")
    print(f"✅ Passes: {result2['passes']}")
    print(f"✅ Reason: {result2['reason']}")
    print()
    
    # Test Case 3: FAILS (Spread too wide)
    print("TEST 3: FAILS - Spread 0.06 (too wide)")
    print("-" * 80)
    orderbook3 = {
        'side_a': {
            'levels': [
                {'price': 0.53, 'volume': 1000, 'liquidity': 530},
            ]
        },
        'side_b': {
            'levels': [
                {'price': 0.47, 'volume': 1000, 'liquidity': 470},
            ]
        }
    }
    
    result3 = passes_quality_filters(orderbook3, source="Polymarket")
    print(f"✅ Passes: {result3['passes']}")
    print(f"✅ Reason: {result3['reason']}")
    print()
    
    print("=" * 80)
    print("✅ TESTS COMPLETE")
    print("=" * 80)

