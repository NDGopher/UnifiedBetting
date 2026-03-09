"""
Arbitrage Spot Finder - Compare Soft Book Lines vs Exchange Best Prices
Highlights outsized liquidity and arbitrage opportunities
"""
import streamlit as st
import pandas as pd
from typing import List, Dict, Optional
from sharp_scanner_auth import (
    fetch_all_markets,
    aggregate_markets_across_exchanges,
    format_odds,
    calculate_no_vig_price
)

def calculate_arbitrage_edge(soft_book_odds: int, exchange_best_odds: int) -> float:
    """Calculate edge percentage when soft book has better odds than exchange."""
    if not soft_book_odds or not exchange_best_odds:
        return 0.0
    
    # Convert to implied probabilities
    def odds_to_prob(odds):
        if odds > 0:
            return 100.0 / (odds + 100.0)
        else:
            return abs(odds) / (abs(odds) + 100.0)
    
    soft_prob = odds_to_prob(soft_book_odds)
    exchange_prob = odds_to_prob(exchange_best_odds)
    
    # Edge = (soft book prob - exchange prob) / exchange prob
    if exchange_prob > 0:
        edge = ((soft_prob - exchange_prob) / exchange_prob) * 100
        return edge
    return 0.0

def highlight_outsized_liquidity(row, liquidity_threshold: float = 50000):
    """Highlight rows with outsized liquidity."""
    side_a_liq = row.get('SideA_TotalLiquidity', 0)
    side_b_liq = row.get('SideB_TotalLiquidity', 0)
    max_liq = max(side_a_liq, side_b_liq)
    
    if max_liq >= liquidity_threshold:
        return ['background-color: #2d5016; color: white; font-weight: bold'] * len(row)
    return [''] * len(row)

def render_arbitrage_comparison_view():
    """Render the arbitrage spot finder view."""
    st.title("🎯 Arbitrage Spot Finder")
    st.markdown("**Compare your soft book lines vs exchange best prices + liquidity**")
    
    # Sidebar controls
    with st.sidebar:
        st.header("Spot Finder Settings")
        
        # Liquidity threshold for "outsized"
        liquidity_threshold = st.slider(
            "Outsized Liquidity Threshold ($)",
            min_value=10000,
            max_value=500000,
            value=50000,
            step=10000,
            help="Markets with liquidity above this are highlighted as 'outsized'"
        )
        
        # Minimum edge to show
        min_edge = st.slider(
            "Minimum Edge to Show (%)",
            min_value=0.0,
            max_value=10.0,
            value=1.0,
            step=0.5,
            help="Only show opportunities with edge above this percentage"
        )
        
        # Sort options
        sort_by = st.selectbox(
            "Sort By",
            ["Liquidity (High to Low)", "Edge (High to Low)", "Imbalance (High to Low)", "Event Name"]
        )
        
        st.divider()
        st.header("Data Sources")
        enable_kalshi = st.checkbox("Kalshi", value=True)
        enable_polymarket = st.checkbox("Polymarket", value=True)
        enable_sx = st.checkbox("SX Bet", value=True)
    
    # Fetch exchange data
    if st.button("🔄 Refresh Exchange Data", type="primary"):
        st.session_state['exchange_data'] = None
    
    if 'exchange_data' not in st.session_state or st.session_state['exchange_data'] is None:
        with st.spinner("Fetching exchange data..."):
            raw_data = fetch_all_markets()
            aggregated = aggregate_markets_across_exchanges(raw_data)
            st.session_state['exchange_data'] = aggregated
            st.session_state['exchange_data_time'] = pd.Timestamp.now()
    
    exchange_data = st.session_state.get('exchange_data', [])
    
    if not exchange_data:
        st.warning("No exchange data available. Click 'Refresh Exchange Data' to fetch.")
        return
    
    # Display last update time
    if 'exchange_data_time' in st.session_state:
        st.caption(f"📊 Exchange data last updated: {st.session_state['exchange_data_time'].strftime('%H:%M:%S')}")
    
    # Create comparison dataframe
    comparison_data = []
    for market in exchange_data:
        event = market.get('Event', '')
        m_type = market.get('Type', '')
        line = market.get('Line', '')
        league = market.get('League', '')
        
        side_a_odds = market.get('SideA_BestOdds')
        side_b_odds = market.get('SideB_BestOdds')
        side_a_source = market.get('SideA_BestSource', '')
        side_b_source = market.get('SideB_BestSource', '')
        side_a_liq = market.get('SideA_TotalLiquidity', 0)
        side_b_liq = market.get('SideB_TotalLiquidity', 0)
        max_liq = max(side_a_liq, side_b_liq)
        imbalance = market.get('ImbalanceRatio', 1.0)
        
        # Calculate no-vig prices
        no_vig = calculate_no_vig_price(side_a_odds, side_b_odds)
        side_a_fair = no_vig.get('side_a_fair')
        side_b_fair = no_vig.get('side_b_fair')
        
        comparison_data.append({
            'League': league,
            'Event': event,
            'Type': m_type,
            'Line': line,
            'SideA_Exchange': format_odds(side_a_odds) if side_a_odds else 'N/A',
            'SideA_Source': side_a_source,
            'SideA_Liquidity': f"${side_a_liq:,.0f}",
            'SideA_Fair': format_odds(side_a_fair) if side_a_fair else 'N/A',
            'SideB_Exchange': format_odds(side_b_odds) if side_b_odds else 'N/A',
            'SideB_Source': side_b_source,
            'SideB_Liquidity': f"${side_b_liq:,.0f}",
            'SideB_Fair': format_odds(side_b_fair) if side_b_fair else 'N/A',
            'Max_Liquidity': max_liq,
            'Imbalance': imbalance,
            'Raw_SideA_Odds': side_a_odds,
            'Raw_SideB_Odds': side_b_odds,
            'Raw_SideA_Liq': side_a_liq,
            'Raw_SideB_Liq': side_b_liq
        })
    
    df = pd.DataFrame(comparison_data)
    
    if df.empty:
        st.info("No markets found. Check your data sources.")
        return
    
    # Filter by liquidity threshold
    df_filtered = df[df['Max_Liquidity'] >= liquidity_threshold].copy()
    
    # Sort
    if sort_by == "Liquidity (High to Low)":
        df_filtered = df_filtered.sort_values('Max_Liquidity', ascending=False)
    elif sort_by == "Edge (High to Low)":
        # For now, sort by liquidity (edge requires soft book input)
        df_filtered = df_filtered.sort_values('Max_Liquidity', ascending=False)
    elif sort_by == "Imbalance (High to Low)":
        df_filtered = df_filtered.sort_values('Imbalance', ascending=False)
    else:
        df_filtered = df_filtered.sort_values('Event')
    
    # Display stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Markets", len(df))
    with col2:
        st.metric("Outsized Liquidity", len(df_filtered), f"≥${liquidity_threshold:,}")
    with col3:
        avg_liq = df['Max_Liquidity'].mean()
        st.metric("Avg Max Liquidity", f"${avg_liq:,.0f}")
    with col4:
        max_liq = df['Max_Liquidity'].max()
        st.metric("Highest Liquidity", f"${max_liq:,.0f}")
    
    st.divider()
    
    # Display comparison table
    st.subheader("📊 Exchange Best Prices + Liquidity")
    
    # Select columns for display
    display_cols = [
        'League', 'Event', 'Type', 'Line',
        'SideA_Exchange', 'SideA_Source', 'SideA_Liquidity', 'SideA_Fair',
        'SideB_Exchange', 'SideB_Source', 'SideB_Liquidity', 'SideB_Fair',
        'Max_Liquidity', 'Imbalance'
    ]
    
    display_df = df_filtered[display_cols].copy()
    
    # Style the dataframe
    styled_df = display_df.style.apply(highlight_outsized_liquidity, axis=1, liquidity_threshold=liquidity_threshold)
    
    st.dataframe(styled_df, height=600, use_container_width=True)
    
    # Show top opportunities
    st.divider()
    st.subheader("🔥 Top Opportunities (Highest Liquidity)")
    
    top_5 = df_filtered.head(5)
    for idx, row in top_5.iterrows():
        with st.expander(f"**{row['Event']}** | {row['Type']} {row['Line']} | Max Liquidity: {row['Max_Liquidity']:,.0f}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Side A (Exchange Best)**")
                st.metric("Price", row['SideA_Exchange'])
                st.caption(f"Source: {row['SideA_Source']}")
                st.caption(f"Liquidity: {row['SideA_Liquidity']}")
                st.caption(f"Fair Price: {row['SideA_Fair']}")
            
            with col2:
                st.write("**Side B (Exchange Best)**")
                st.metric("Price", row['SideB_Exchange'])
                st.caption(f"Source: {row['SideB_Source']}")
                st.caption(f"Liquidity: {row['SideB_Liquidity']}")
                st.caption(f"Fair Price: {row['SideB_Fair']}")
            
            st.caption(f"Imbalance Ratio: {row['Imbalance']:.2f}x")

if __name__ == "__main__":
    render_arbitrage_comparison_view()

