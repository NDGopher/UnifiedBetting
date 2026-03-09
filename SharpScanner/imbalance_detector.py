"""
Liquidity Imbalance / Order Wall Detector
Identifies markets where "Smart Money" is sitting on the order book with large limit orders.
This detects static pressure (whales) vs. active movement (steam).
"""

from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

def calculate_market_depth(orders: List[Dict], source: str = "Kalshi", top_n: int = 3) -> float:
    """
    Calculate market depth in dollars for the top N orderbook levels.
    Formula: Sum of (Price * Size) for each level.
    
    This ensures we're looking at REAL MONEY, not just contract counts.
    
    Args:
        orders: List of orderbook levels [{'price': float, 'volume': float, 'liquidity': float}, ...]
        source: "Kalshi" or "Polymarket" (affects price format)
        top_n: Number of top levels to sum (default 3)
    
    Returns:
        Total market depth in dollars
    """
    if not orders:
        return 0.0
    
    total_depth = 0.0
    for level in orders[:top_n]:
        price = level.get('price', 0)
        volume = level.get('volume', 0)
        liquidity = level.get('liquidity', 0)
        
        if liquidity > 0:
            # Use pre-calculated liquidity if available
            total_depth += liquidity
        else:
            # Calculate: Price * Size (in dollars)
            if source == "Kalshi":
                # Price is in cents, volume is in contracts
                # Liquidity = (Price / 100) * Volume
                total_depth += (price / 100.0) * volume
            else:  # Polymarket
                # Price is probability (0-1), volume is in shares
                # Liquidity = Price * Volume (dollars)
                total_depth += price * volume
    
    return total_depth

def check_imbalance(
    orderbook: Dict,
    source: str = "Kalshi",
    min_dominant_size: float = 5000.0,  # $5,000 minimum
    min_imbalance_ratio: float = 4.0,  # 4x minimum
    max_spread_cents: float = 2.0,  # 2 cents max spread
    max_spread_pct: float = 0.03  # 3% max spread (for Polymarket)
) -> Dict:
    """
    Detects liquidity imbalance / order walls (whales).
    
    This finds static pressure where smart money is sitting on the order book
    with large limit orders, indicating a strong defensive position.
    
    Trigger Conditions (ALL must be met):
    A. Tight Spread: <= 2 cents or <= 3% probability difference
    B. Significant Size: Dominant side > $5,000 USD
    C. High Ratio: imbalance_ratio > 4.0
    
    Args:
        orderbook: Orderbook dict with 'side_a' and 'side_b' containing 'levels'
        source: "Kalshi" or "Polymarket"
        min_dominant_size: Minimum $ size for dominant side ($5,000 default)
        min_imbalance_ratio: Minimum imbalance ratio (4.0 default)
        max_spread_cents: Maximum spread in cents for Kalshi (2.0 default)
        max_spread_pct: Maximum spread in % for Polymarket (0.03 = 3% default)
    
    Returns:
        Dict with:
        - 'is_whale': bool
        - 'dominant_side': "A" or "B" or None
        - 'bid_depth': float (dollars)
        - 'ask_depth': float (dollars)
        - 'imbalance_ratio': float
        - 'spread': float
        - 'message': str (human-readable message)
        - 'team_name': str (for display)
        - 'odds': int (American odds for dominant side)
    """
    result = {
        'is_whale': False,
        'dominant_side': None,
        'bid_depth': 0.0,
        'ask_depth': 0.0,
        'imbalance_ratio': 1.0,
        'spread': 0.0,
        'message': "No Imbalance",
        'team_name': None,
        'odds': None
    }
    
    # Get orderbook levels for both sides
    side_a_levels = orderbook.get('side_a', {}).get('levels', [])
    side_b_levels = orderbook.get('side_b', {}).get('levels', [])
    
    if not side_a_levels or not side_b_levels:
        result['message'] = "IGNORE: Missing orderbook data"
        return result
    
    # Calculate market depth for top 3 levels on both sides
    # For Kalshi: Side A = Yes (asks), Side B = No (asks)
    # For Polymarket: Side A = Yes (asks), Side B = No (bids)
    
    if source == "Kalshi":
        # Kalshi: Side A asks = Yes side, Side B asks = No side
        ask_depth = calculate_market_depth(side_a_levels, source, top_n=3)  # Yes side
        bid_depth = calculate_market_depth(side_b_levels, source, top_n=3)  # No side (inverted)
    else:  # Polymarket
        # Polymarket: Side A asks = Yes side, Side B bids = No side
        ask_depth = calculate_market_depth(side_a_levels, source, top_n=3)  # Yes side (asks)
        bid_depth = calculate_market_depth(side_b_levels, source, top_n=3)  # No side (bids)
    
    result['bid_depth'] = bid_depth
    result['ask_depth'] = ask_depth
    
    # Determine dominant side
    if bid_depth > ask_depth:
        dominant_side = "B"
        dominant_depth = bid_depth
        smaller_depth = ask_depth
    elif ask_depth > bid_depth:
        dominant_side = "A"
        dominant_depth = ask_depth
        smaller_depth = bid_depth
    else:
        # Equal depth, no imbalance
        result['message'] = "No Imbalance: Equal depth on both sides"
        return result
    
    # Calculate imbalance ratio
    if smaller_depth > 0:
        imbalance_ratio = dominant_depth / smaller_depth
    else:
        imbalance_ratio = 999.0  # Infinite imbalance (one side has zero)
    
    result['imbalance_ratio'] = imbalance_ratio
    result['dominant_side'] = dominant_side
    
    # Condition A: Check tight spread
    # Get best bid and best ask prices
    if side_a_levels and side_b_levels:
        best_ask_price = side_a_levels[0].get('price', 0)  # Side A = asks
        if source == "Kalshi":
            best_bid_price = side_b_levels[0].get('price', 0)  # Side B = No asks (inverted)
            # For Kalshi, spread is in cents
            spread = abs(best_ask_price - best_bid_price)
            is_tight_spread = spread <= max_spread_cents
        else:  # Polymarket
            best_bid_price = side_b_levels[0].get('price', 0)  # Side B = bids
            # For Polymarket, spread is in probability (0-1)
            spread = abs(best_ask_price - best_bid_price)
            is_tight_spread = spread <= max_spread_pct
    else:
        is_tight_spread = False
        spread = 0.0
    
    result['spread'] = spread
    
    # Condition B: Check significant size
    is_significant_size = dominant_depth >= min_dominant_size
    
    # Condition C: Check high ratio
    is_high_ratio = imbalance_ratio >= min_imbalance_ratio
    
    # Trigger: ALL conditions must be met
    if is_tight_spread and is_significant_size and is_high_ratio:
        result['is_whale'] = True
        
        # Get odds for dominant side
        if dominant_side == "A":
            dominant_levels = side_a_levels
            side_name = "Yes" if source == "Kalshi" else "Yes"
        else:
            dominant_levels = side_b_levels
            side_name = "No" if source == "Kalshi" else "No"
        
        if dominant_levels:
            best_price = dominant_levels[0].get('price', 0)
            # Convert to American odds (simplified - would need full conversion function)
            if source == "Kalshi":
                # Price in cents, convert to probability then odds
                prob = best_price / 100.0
            else:
                prob = best_price
            
            # Simple odds conversion (would use proper function in production)
            if prob > 0.5:
                odds = int(-100 * (prob / (1 - prob)))
            else:
                odds = int(100 * ((1 - prob) / prob))
            
            result['odds'] = odds
            
            # Format message
            result['message'] = f"WHALE 🐋: ${dominant_depth:,.0f} Buy Wall on {side_name} @ {odds}. (Imbalance: {imbalance_ratio:.1f}x vs {('Ask' if dominant_side == 'B' else 'Bid')} side)"
        else:
            result['message'] = f"WHALE 🐋: ${dominant_depth:,.0f} Buy Wall. (Imbalance: {imbalance_ratio:.1f}x)"
    else:
        # Not a whale - explain why
        reasons = []
        if not is_tight_spread:
            reasons.append(f"spread too wide ({spread:.2f})")
        if not is_significant_size:
            reasons.append(f"size too small (${dominant_depth:,.0f} < ${min_dominant_size:,.0f})")
        if not is_high_ratio:
            reasons.append(f"ratio too low ({imbalance_ratio:.1f}x < {min_imbalance_ratio:.1f}x)")
        
        result['message'] = f"No Whale: {', '.join(reasons)}"
    
    return result

# Example usage and test
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.StreamHandler(sys.stdout)])
    
    # Test Case 1: WHALE DETECTED
    print("=" * 80)
    print("TEST 1: WHALE DETECTED - $20k on Bid, $2k on Ask, tight spread")
    print("-" * 80)
    
    orderbook = {
        'side_a': {
            'levels': [
                {'price': 0.50, 'volume': 4000, 'liquidity': 2000},  # $2k Ask
            ]
        },
        'side_b': {
            'levels': [
                {'price': 0.49, 'volume': 40000, 'liquidity': 20000},  # $20k Bid
            ]
        }
    }
    
    result = check_imbalance(orderbook, source="Polymarket")
    print(f"✅ Is Whale: {result['is_whale']}")
    print(f"✅ Dominant Side: {result['dominant_side']}")
    print(f"✅ Bid Depth: ${result['bid_depth']:,.0f}")
    print(f"✅ Ask Depth: ${result['ask_depth']:,.0f}")
    print(f"✅ Imbalance Ratio: {result['imbalance_ratio']:.1f}x")
    print(f"✅ Message: {result['message']}")
    print()
    
    # Test Case 2: NO WHALE (spread too wide)
    print("TEST 2: NO WHALE - Spread too wide")
    print("-" * 80)
    
    orderbook2 = {
        'side_a': {
            'levels': [
                {'price': 0.60, 'volume': 10000, 'liquidity': 6000},  # Wide spread
            ]
        },
        'side_b': {
            'levels': [
                {'price': 0.40, 'volume': 1000, 'liquidity': 400},
            ]
        }
    }
    
    result2 = check_imbalance(orderbook2, source="Polymarket")
    print(f"✅ Is Whale: {result2['is_whale']}")
    print(f"✅ Message: {result2['message']}")
    print()
    
    print("=" * 80)
    print("✅ TESTS COMPLETE")
    print("=" * 80)

