"""
Quick analysis script to show top opportunities from the scanner
"""
import sys
from sharp_scanner_auth import (
    fetch_kalshi_markets,
    fetch_polymarket_markets,
    fetch_sx_bet_markets,
    aggregate_markets_across_exchanges,
    format_odds
)

print("=" * 80)
print("SCANNER ANALYSIS - TOP OPPORTUNITIES")
print("=" * 80)
print()

# Fetch data from all sources
print("📡 Fetching market data...")
raw_data = []
raw_data.extend(fetch_kalshi_markets())
raw_data.extend(fetch_polymarket_markets())
raw_data.extend(fetch_sx_bet_markets())
print(f"✅ Fetched {len(raw_data)} raw markets")
print()

# Aggregate
print("🔄 Aggregating across exchanges...")
aggregated = aggregate_markets_across_exchanges(raw_data)
print(f"✅ Aggregated to {len(aggregated)} unique markets")
print()

if not aggregated:
    print("❌ No markets found. Check API connections.")
    sys.exit(1)

# Calculate max liquidity for each market
for market in aggregated:
    side_a_liq = market.get('SideA_TotalLiquidity', 0) or 0
    side_b_liq = market.get('SideB_TotalLiquidity', 0) or 0
    market['Max_Liquidity'] = max(side_a_liq, side_b_liq)

# Sort by liquidity
sorted_markets = sorted(aggregated, key=lambda x: x.get('Max_Liquidity', 0), reverse=True)

print("=" * 80)
print("TOP 15 MARKETS BY LIQUIDITY (Outsized Opportunities)")
print("=" * 80)
print()

for idx, market in enumerate(sorted_markets[:15], 1):
    event = market.get('Event', 'Unknown')
    league = market.get('League', '')
    m_type = market.get('Type', '')
    line = market.get('Line', '')
    max_liq = market.get('Max_Liquidity', 0)
    side_a_odds = market.get('SideA_BestOdds')
    side_b_odds = market.get('SideB_BestOdds')
    side_a_source = market.get('SideA_BestSource', '')
    side_b_source = market.get('SideB_BestSource', '')
    side_a_liq = market.get('SideA_TotalLiquidity', 0) or 0
    side_b_liq = market.get('SideB_TotalLiquidity', 0) or 0
    imbalance = market.get('ImbalanceRatio', 1.0)
    vig = market.get('Vig', 0)
    team_a = market.get('TeamA', '')
    team_b = market.get('TeamB', '')
    side_a_fair = market.get('SideA_FairOdds')
    side_b_fair = market.get('SideB_FairOdds')
    
    print(f"\n{idx}. {event}")
    print(f"   📊 {league} | {m_type} | {line}")
    if team_a and team_b and team_a != 'Over' and team_b != 'Under':
        print(f"   👥 {team_a} vs {team_b}")
    print(f"   💰 Max Liquidity: ${max_liq:,.0f}")
    print(f"   📈 Side A: {format_odds(side_a_odds) if side_a_odds else 'N/A'} ({side_a_source}) | Liq: ${side_a_liq:,.0f} | Fair: {format_odds(side_a_fair) if side_a_fair else 'N/A'}")
    print(f"   📉 Side B: {format_odds(side_b_odds) if side_b_odds else 'N/A'} ({side_b_source}) | Liq: ${side_b_liq:,.0f} | Fair: {format_odds(side_b_fair) if side_b_fair else 'N/A'}")
    if vig:
        print(f"   ⚖️  Imbalance: {imbalance:.2f}x | Vig: {vig:.2f}%")
    else:
        print(f"   ⚖️  Imbalance: {imbalance:.2f}x")
    if max_liq >= 50000:
        print(f"   🔥 OUTSIZED LIQUIDITY - Check your soft book!")
    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total Markets: {len(aggregated)}")
print(f"Markets with >$50k liquidity: {len([m for m in aggregated if m.get('Max_Liquidity', 0) >= 50000])}")
print(f"Markets with >$100k liquidity: {len([m for m in aggregated if m.get('Max_Liquidity', 0) >= 100000])}")
print(f"Highest Liquidity: ${max([m.get('Max_Liquidity', 0) for m in aggregated]):,.0f}")
print(f"Average Max Liquidity: ${sum([m.get('Max_Liquidity', 0) for m in aggregated]) / len(aggregated):,.0f}")
print()

