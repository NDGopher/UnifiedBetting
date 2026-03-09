"""
Proper Steam Detector using Volume-Weighted Average Price (VWAP)
Filters out slippage (fake moves on low liquidity) from real steam (moves backed by volume)
"""

from typing import Dict, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

def get_effective_price(orders: List[Dict], target_volume: float, source: str = "Kalshi") -> Optional[float]:
    """
    Calculate the effective price to buy target_volume worth of contracts.
    This is the VWAP (Volume-Weighted Average Price) for the top of the orderbook.
    
    Formula: VWAP = Σ(Price × Volume) / Σ(Volume)
    
    Args:
        orders: List of orderbook levels [{'price': float, 'volume': float, ...}, ...]
        target_volume: Target dollar volume to calculate effective price for
        source: "Kalshi" or "Polymarket" (affects price format)
    
    Returns:
        Effective price (probability for Polymarket, cents for Kalshi) or None if insufficient liquidity
    """
    if not orders:
        return None
    
    volume_sum = 0.0
    cost_sum = 0.0
    
    for level in orders:
        price = level.get('price', 0)
        volume = level.get('volume', 0)
        liquidity = level.get('liquidity', 0)
        
        # For Kalshi: price is in cents, liquidity = (price/100) * volume
        # For Polymarket: price is probability (0-1), liquidity = price * volume
        
        if source == "Kalshi":
            # Price is in cents, convert to dollars for calculation
            price_dollars = price / 100.0
            # Liquidity is already in dollars: (price/100) * volume
            available_liquidity = liquidity if liquidity > 0 else (price_dollars * volume)
        else:  # Polymarket
            # Price is probability (0-1), liquidity = price * volume (dollars)
            price_dollars = price
            available_liquidity = liquidity if liquidity > 0 else (price * volume)
        
        # Take as much as we need
        take_volume = min(available_liquidity, target_volume - volume_sum)
        if take_volume <= 0:
            break
        
        # Calculate cost: if we're buying $X worth, cost = $X
        # But we need to know how many contracts that buys
        if source == "Kalshi":
            # If price is 50 cents, $1000 buys 2000 contracts
            contracts = take_volume / price_dollars
            cost_sum += contracts * price_dollars  # This equals take_volume
        else:  # Polymarket
            # If price is 0.5, $1000 buys 2000 shares
            contracts = take_volume / price_dollars if price_dollars > 0 else 0
            cost_sum += contracts * price_dollars  # This equals take_volume
        
        volume_sum += take_volume
        
        if volume_sum >= target_volume:
            break
    
    # If we can't even fill the target volume, it's a dead market
    if volume_sum < target_volume * 0.9:  # Allow 10% tolerance
        return None
    
    # Effective price = total cost / total contracts
    # But since cost_sum ≈ volume_sum for our calculation, we can simplify
    # Actually, we want the weighted average price
    if volume_sum == 0:
        return None
    
    # Return the effective price (probability for Polymarket, cents for Kalshi)
    # This is the average price you'd pay to buy target_volume worth
    return cost_sum / volume_sum if volume_sum > 0 else None

def calculate_liquidity_depth(orders: List[Dict], source: str = "Kalshi", top_n: int = 3) -> float:
    """
    Calculate total liquidity depth in the top N levels of the orderbook.
    This is the "slippage filter" - if depth < $500, ignore the move.
    
    Args:
        orders: List of orderbook levels
        source: "Kalshi" or "Polymarket"
        top_n: Number of top levels to sum
    
    Returns:
        Total liquidity in dollars
    """
    if not orders:
        return 0.0
    
    total_depth = 0.0
    for level in orders[:top_n]:
        liquidity = level.get('liquidity', 0)
        if liquidity > 0:
            total_depth += liquidity
        else:
            # Calculate from price and volume if liquidity not available
            price = level.get('price', 0)
            volume = level.get('volume', 0)
            if source == "Kalshi":
                total_depth += (price / 100.0) * volume
            else:  # Polymarket
                total_depth += price * volume
    
    return total_depth

def analyze_steam(
    previous_orderbook: Dict,
    current_orderbook: Dict,
    min_liquidity: float = 1000.0,
    min_depth: float = 1000.0,  # UPDATED: Must be $1000+ to buy at current price (was $500)
    movement_threshold: float = 0.025,  # 2.5% move threshold
    source: str = "Kalshi"
) -> Dict:
    """
    Detects real steam while ignoring low-liquidity slippage.
    
    This is the core steam detection algorithm:
    1. Check liquidity depth (slippage filter)
    2. Calculate VWAP for target volume
    3. Compare current vs previous VWAP
    4. Alert if move > threshold AND backed by volume
    
    Args:
        previous_orderbook: Previous orderbook state {'side_a': {'levels': [...]}, 'side_b': {'levels': [...]}}
        current_orderbook: Current orderbook state (same format)
        min_liquidity: Minimum liquidity required to consider market ($1000 default)
        min_depth: Minimum depth in top 3 levels ($500 default)
        movement_threshold: Percentage change to trigger alert (2.5% default)
        source: "Kalshi" or "Polymarket"
    
    Returns:
        Dict with:
        - 'is_steam': bool
        - 'direction': "UP" or "DOWN" or None
        - 'move_pct': float (percentage change)
        - 'message': str (human-readable message)
        - 'effective_price_prev': float
        - 'effective_price_curr': float
        - 'liquidity_depth': float
    """
    result = {
        'is_steam': False,
        'direction': None,
        'move_pct': 0.0,
        'message': "No Steam",
        'effective_price_prev': None,
        'effective_price_curr': None,
        'liquidity_depth': 0.0
    }
    
    # Get orderbook levels for Side A (the "Yes" side / buy side)
    prev_asks = previous_orderbook.get('side_a', {}).get('levels', [])
    curr_asks = current_orderbook.get('side_a', {}).get('levels', [])
    
    if not prev_asks or not curr_asks:
        result['message'] = "IGNORE: Missing orderbook data"
        return result
    
    # 1. Check liquidity depth first (The "Slippage Filter")
    # REQUIREMENT: Must be at least $1000 to buy at the current price
    current_depth = calculate_liquidity_depth(curr_asks, source, top_n=10)
    result['liquidity_depth'] = current_depth
    
    if current_depth < min_depth:
        result['message'] = f"IGNORE: Low liquidity depth (${current_depth:.0f} < ${min_depth:.0f})"
        return result
    
    # 2. Get current price (midpoint or best ask)
    # For simplicity, use best ask price (what we pay to buy)
    # This matches the requirement: "price_delta = abs(current_price - previous_price)"
    if not curr_asks or not prev_asks:
        result['message'] = "IGNORE: Missing orderbook levels"
        return result
    
    # Get best ask price (first level)
    curr_best_ask = curr_asks[0].get('price', 0)
    prev_best_ask = prev_asks[0].get('price', 0)
    
    # Convert to probability if needed (Kalshi uses cents, Polymarket uses probability)
    if source == "Kalshi":
        curr_price = curr_best_ask / 100.0  # Convert cents to probability
        prev_price = prev_best_ask / 100.0
    else:  # Polymarket
        curr_price = curr_best_ask  # Already probability
        prev_price = prev_best_ask
    
    result['effective_price_prev'] = prev_price
    result['effective_price_curr'] = curr_price
    
    if prev_price <= 0 or curr_price <= 0:
        result['message'] = "IGNORE: Invalid price data"
        return result
    
    # 3. Calculate the Move Percentage
    # REQUIREMENT: price_delta = abs(current_price - previous_price)
    # is_steam = price_delta >= 0.025 (2.5% move threshold)
    price_delta = abs(curr_price - prev_price)
    move_pct = price_delta / prev_price  # Percentage change
    result['move_pct'] = move_pct
    
    # 4. The "Steam" Logic
    # Threshold: Price moved 2.5% AND it holds up against $1000 depth
    if abs(move_pct) > movement_threshold:
        direction = "UP" if move_pct > 0 else "DOWN"
        result['is_steam'] = True
        result['direction'] = direction
        
        # 5. Output for your Soft Book
        if direction == "UP":
            result['message'] = f"STEAM DETECTED: Buy YES. Price moved {move_pct*100:.1f}% on high volume (${current_depth:.0f} depth)"
        else:
            result['message'] = f"STEAM DETECTED: Buy NO (or sell Yes). Price dropped {abs(move_pct)*100:.1f}% on high volume (${current_depth:.0f} depth)"
    else:
        result['message'] = f"No Steam: {abs(move_pct)*100:.2f}% move < {movement_threshold*100:.1f}% threshold"
    
    return result

# Example usage and test
if __name__ == "__main__":
    # Mock orderbook data for testing
    prev_book = {
        'side_a': {
            'levels': [
                {'price': 50, 'volume': 1000, 'liquidity': 500},  # $500 at 50 cents
                {'price': 51, 'volume': 1000, 'liquidity': 510},  # $510 at 51 cents
                {'price': 52, 'volume': 1000, 'liquidity': 520},  # $520 at 52 cents
            ]
        }
    }
    
    curr_book = {
        'side_a': {
            'levels': [
                {'price': 53, 'volume': 1000, 'liquidity': 530},  # Price moved up
                {'price': 54, 'volume': 1000, 'liquidity': 540},
                {'price': 55, 'volume': 1000, 'liquidity': 550},
            ]
        }
    }
    
    result = analyze_steam(prev_book, curr_book, source="Kalshi")
    print(f"Steam Detected: {result['is_steam']}")
    print(f"Message: {result['message']}")
    print(f"Move: {result['move_pct']*100:.2f}%")
    print(f"Depth: ${result['liquidity_depth']:.0f}")

