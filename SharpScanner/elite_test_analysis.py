"""
Elite-Level Testing & Analysis for Sharp Money Scanner
Purpose: Find large moves quickly and liquidity stacking to capitalize on soft books
"""

import sys
import json
import time
from datetime import datetime
from typing import Dict, List

# Mock the Streamlit imports for testing
class MockStreamlit:
    class session_state:
        data = []
        last_update = datetime.now()
        previous_prices = {}
    
    @staticmethod
    def set_page_config(*args, **kwargs): pass
    @staticmethod
    def title(*args): pass
    @staticmethod
    def sidebar(*args): pass
    @staticmethod
    def slider(*args): return 0
    @staticmethod
    def checkbox(*args): return True
    @staticmethod
    def button(*args): return False
    @staticmethod
    def caption(*args): pass
    @staticmethod
    def dataframe(*args): pass
    @staticmethod
    def success(*args): pass
    @staticmethod
    def expander(*args): return MockContext()
    @staticmethod
    def columns(*args): return [MockContext(), MockContext()]
    @staticmethod
    def write(*args): pass
    @staticmethod
    def metric(*args): pass
    @staticmethod
    def markdown(*args): pass
    @staticmethod
    def info(*args): pass
    @staticmethod
    def warning(*args): pass
    @staticmethod
    def spinner(*args): return MockContext()
    @staticmethod
    def rerun(*args): pass

class MockContext:
    def __enter__(self): return self
    def __exit__(self, *args): pass

sys.modules['streamlit'] = MockStreamlit()

# Now import the actual scanner functions
from sharp_scanner_auth import (
    fetch_kalshi_markets,
    fetch_polymarket_markets,
    fetch_sx_bet_markets,
    aggregate_markets_across_exchanges,
    track_price_movements,
    extract_both_sides
)

def analyze_sharp_money_signals(markets: List[Dict]) -> Dict:
    """Analyze markets for sharp money signals"""
    analysis = {
        'high_imbalance': [],  # Imbalance > 2x
        'massive_liquidity': [],  # > $100k liquidity
        'price_moves': [],  # 10%+ moves
        'arbitrage_opportunities': [],  # Cross-exchange price differences
        'sharp_side_opportunities': []  # Clear sharp money signals
    }
    
    for market in markets:
        # High imbalance (sharp money stacking)
        imbalance = market.get('ImbalanceRatio', 1.0)
        if imbalance >= 2.0:
            analysis['high_imbalance'].append({
                'event': market.get('Event'),
                'type': market.get('Type'),
                'imbalance': imbalance,
                'sharp_side': market.get('SharpSide'),
                'sharp_liquidity': market.get('SharpLiquidity', 0),
                'side_a_liq': market.get('SideA_TotalLiquidity', 0),
                'side_b_liq': market.get('SideB_TotalLiquidity', 0)
            })
        
        # Massive liquidity (big money moving)
        total_liq = market.get('SideA_TotalLiquidity', 0) + market.get('SideB_TotalLiquidity', 0)
        if total_liq >= 100000:
            analysis['massive_liquidity'].append({
                'event': market.get('Event'),
                'type': market.get('Type'),
                'total_liquidity': total_liq,
                'sharp_side': market.get('SharpSide'),
                'sharp_odds': market.get('SharpOdds')
            })
        
        # Price movements
        if market.get('PriceMove'):
            analysis['price_moves'].append({
                'event': market.get('Event'),
                'type': market.get('Type'),
                'move': market.get('PriceMove'),
                'direction': market.get('PriceMoveDirection'),
                'current_odds': market.get('SharpOdds'),
                'previous_odds': market.get('PreviousOdds')
            })
        
        # Arbitrage opportunities (price differences across exchanges)
        side_a_odds = market.get('SideA_BestOdds')
        side_b_odds = market.get('SideB_BestOdds')
        if side_a_odds and side_b_odds:
            # Calculate implied probability
            if side_a_odds < 0:
                prob_a = abs(side_a_odds) / (abs(side_a_odds) + 100)
            else:
                prob_a = 100 / (side_a_odds + 100)
            
            if side_b_odds < 0:
                prob_b = abs(side_b_odds) / (abs(side_b_odds) + 100)
            else:
                prob_b = 100 / (side_b_odds + 100)
            
            total_prob = prob_a + prob_b
            if total_prob < 0.98:  # Less than 2% vig = arbitrage opportunity
                analysis['arbitrage_opportunities'].append({
                    'event': market.get('Event'),
                    'type': market.get('Type'),
                    'side_a_odds': side_a_odds,
                    'side_b_odds': side_b_odds,
                    'vig': (1 - total_prob) * 100,
                    'sources': market.get('Sources', '')
                })
        
        # Sharp side opportunities (clear signal)
        if imbalance >= 1.5 and market.get('SharpLiquidity', 0) >= 50000:
            analysis['sharp_side_opportunities'].append({
                'event': market.get('Event'),
                'type': market.get('Type'),
                'bet': market.get('Bet'),
                'sharp_odds': market.get('SharpOdds'),
                'sharp_liquidity': market.get('SharpLiquidity'),
                'imbalance': imbalance,
                'side_a_best': market.get('SideA_BestOdds'),
                'side_b_best': market.get('SideB_BestOdds')
            })
    
    return analysis

def print_elite_analysis(analysis: Dict, raw_markets: List[Dict]):
    """Print elite-level analysis"""
    print("=" * 80)
    print("ELITE SHARP MONEY SCANNER - REAL-TIME ANALYSIS")
    print("=" * 80)
    print(f"\n📊 TOTAL MARKETS ANALYZED: {len(raw_markets)}")
    print(f"⏰ Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. HIGH IMBALANCE SIGNALS (Sharp Money Stacking)
    print("🔥 HIGH IMBALANCE SIGNALS (Sharp Money Stacking)")
    print("-" * 80)
    if analysis['high_imbalance']:
        for signal in sorted(analysis['high_imbalance'], key=lambda x: x['imbalance'], reverse=True)[:10]:
            print(f"  ⚡ {signal['event']} | {signal['type']}")
            print(f"     Imbalance: {signal['imbalance']:.2f}x | Sharp Side: {signal['sharp_side']}")
            print(f"     Sharp Liquidity: ${signal['sharp_liquidity']:,.0f}")
            print(f"     Side A: ${signal['side_a_liq']:,.0f} | Side B: ${signal['side_b_liq']:,.0f}")
            print()
    else:
        print("  No high imbalance signals detected\n")
    
    # 2. MASSIVE LIQUIDITY (Big Money Moving)
    print("💰 MASSIVE LIQUIDITY SIGNALS (Big Money Moving)")
    print("-" * 80)
    if analysis['massive_liquidity']:
        for signal in sorted(analysis['massive_liquidity'], key=lambda x: x['total_liquidity'], reverse=True)[:10]:
            print(f"  💵 {signal['event']} | {signal['type']}")
            print(f"     Total Liquidity: ${signal['total_liquidity']:,.0f}")
            print(f"     Sharp Side: {signal['sharp_side']} @ {signal['sharp_odds']}")
            print()
    else:
        print("  No massive liquidity signals detected\n")
    
    # 3. PRICE MOVEMENTS (Injury/News Alerts)
    print("📈 PRICE MOVEMENTS (10%+ Moves - Injury/News Alerts)")
    print("-" * 80)
    if analysis['price_moves']:
        for move in analysis['price_moves']:
            print(f"  🚨 {move['event']} | {move['type']}")
            print(f"     Move: {move['move']} {move['direction']}")
            print(f"     Previous: {move['previous_odds']} → Current: {move['current_odds']}")
            print(f"     ⚠️  ACTION: Check for injury/news - Soft books may not have moved yet!")
            print()
    else:
        print("  No significant price movements detected (check again in 15 seconds)\n")
    
    # 4. ARBITRAGE OPPORTUNITIES
    print("🎯 ARBITRAGE OPPORTUNITIES (Cross-Exchange Price Differences)")
    print("-" * 80)
    if analysis['arbitrage_opportunities']:
        for arb in sorted(analysis['arbitrage_opportunities'], key=lambda x: x['vig'])[:10]:
            print(f"  ✅ {arb['event']} | {arb['type']}")
            print(f"     Side A: {arb['side_a_odds']} | Side B: {arb['side_b_odds']}")
            print(f"     Vig: {arb['vig']:.2f}% (Negative vig = arbitrage!)")
            print(f"     Sources: {arb['sources']}")
            print()
    else:
        print("  No arbitrage opportunities detected\n")
    
    # 5. SHARP SIDE OPPORTUNITIES (Actionable Signals)
    print("🎲 SHARP SIDE OPPORTUNITIES (Actionable Signals for Soft Books)")
    print("-" * 80)
    if analysis['sharp_side_opportunities']:
        for opp in sorted(analysis['sharp_side_opportunities'], key=lambda x: x['sharp_liquidity'], reverse=True)[:15]:
            print(f"  🎯 {opp['event']} | {opp['type']}")
            print(f"     {opp['bet']} @ {opp['sharp_odds']} or better")
            print(f"     Sharp Liquidity: ${opp['sharp_liquidity']:,.0f} | Imbalance: {opp['imbalance']:.2f}x")
            print(f"     Best Prices: Side A {opp['side_a_best']} | Side B {opp['side_b_best']}")
            print(f"     💡 STRATEGY: Check soft books for better price than {opp['sharp_odds']}")
            print()
    else:
        print("  No clear sharp side opportunities detected\n")
    
    # SUMMARY
    print("=" * 80)
    print("📋 EXECUTIVE SUMMARY")
    print("=" * 80)
    print(f"  High Imbalance Signals: {len(analysis['high_imbalance'])}")
    print(f"  Massive Liquidity Signals: {len(analysis['massive_liquidity'])}")
    print(f"  Price Movements Detected: {len(analysis['price_moves'])}")
    print(f"  Arbitrage Opportunities: {len(analysis['arbitrage_opportunities'])}")
    print(f"  Actionable Sharp Signals: {len(analysis['sharp_side_opportunities'])}")
    print()
    print("💡 PRIMARY PURPOSE REMINDER:")
    print("   1. Find LARGE MOVES quickly (10%+ price changes)")
    print("   2. Find LIQUIDITY STACKING (imbalance > 2x = sharp money)")
    print("   3. Capitalize on SOFT BOOKS that don't move as fast as exchanges")
    print("   4. Execute when exchange price is better than soft book")
    print("=" * 80)

def main():
    """Run elite-level testing"""
    print("\n🔬 ELITE TESTING MODE - FETCHING LIVE DATA...\n")
    
    # Fetch data from all sources
    print("Fetching Kalshi markets...")
    kalshi_markets = fetch_kalshi_markets()
    print(f"  ✓ Found {len(kalshi_markets)} Kalshi markets")
    
    print("Fetching Polymarket markets...")
    polymarket_markets = fetch_polymarket_markets()
    print(f"  ✓ Found {len(polymarket_markets)} Polymarket markets")
    
    print("Fetching SX Bet markets...")
    sx_markets = fetch_sx_bet_markets()
    print(f"  ✓ Found {len(sx_markets)} SX Bet markets")
    
    # Combine all markets
    all_markets = kalshi_markets + polymarket_markets + sx_markets
    print(f"\n📦 Total Raw Markets: {len(all_markets)}")
    
    # Aggregate across exchanges
    print("\nAggregating across exchanges...")
    aggregated = aggregate_markets_across_exchanges(all_markets)
    print(f"  ✓ Aggregated to {len(aggregated)} unique markets")
    
    # Track price movements (simulate previous prices)
    previous_prices = {}
    tracked = track_price_movements(aggregated, previous_prices)
    
    # Analyze for sharp money signals
    print("\nAnalyzing sharp money signals...")
    analysis = analyze_sharp_money_signals(tracked)
    
    # Print elite analysis
    print_elite_analysis(analysis, tracked)
    
    # Save detailed data for review
    with open('elite_analysis_output.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_markets': len(tracked),
            'analysis': analysis,
            'markets': tracked[:20]  # Top 20 for review
        }, f, indent=2, default=str)
    
    print("\n💾 Detailed analysis saved to: elite_analysis_output.json")
    print("\n✅ ELITE TESTING COMPLETE\n")

if __name__ == "__main__":
    main()

