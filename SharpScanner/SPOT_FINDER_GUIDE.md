# 🎯 Arbitrage Spot Finder - User Guide

## Overview

The **Spot Finder** view helps you identify arbitrage opportunities by highlighting markets with **outsized liquidity** on exchanges. Compare exchange best prices to your soft book to find profitable spots.

## How to Use

### 1. **Switch to Spot Finder View**
- At the top of the dashboard, select **"🎯 Spot Finder (Outsized Liquidity)"**
- This switches from the Sharp Money Scanner to the Spot Finder view

### 2. **Set Liquidity Threshold**
- In the sidebar, find **"Spot Finder Settings"**
- Adjust **"Outsized Liquidity Threshold ($)"** slider
- Default: $50,000
- Markets above this threshold are highlighted in **green**
- Lower threshold = more markets highlighted
- Higher threshold = only very high liquidity markets

### 3. **View Exchange Best Prices**
The main table shows:
- **League, Event, Type, Line**
- **Side A Best Odds** (best price across all exchanges)
- **Side A Source** (which exchange has the best price)
- **Side A Liquidity** (total liquidity available)
- **Side A Fair Price** (no-vig price)
- **Side B Best Odds** (best price across all exchanges)
- **Side B Source** (which exchange has the best price)
- **Side B Liquidity** (total liquidity available)
- **Side B Fair Price** (no-vig price)
- **Max Liquidity** (highest liquidity between Side A and Side B)
- **Imbalance Ratio** (liquidity imbalance)
- **Vig** (vig percentage)

### 4. **Identify Opportunities**
- **Green highlighted rows** = Outsized liquidity (above threshold)
- **Top Opportunities section** = Markets with highest liquidity
- **Compare exchange prices to your soft book:**
  - If exchange has better odds than your book → You have an edge
  - If exchange has worse odds than your book → No edge

### 5. **Take Action**
1. Find a market with high liquidity (green highlighted)
2. Check the exchange best price
3. Compare to your soft book price
4. If exchange is better → Bet on your soft book
5. If exchange is worse → No action needed

## Key Features

### **Outsized Liquidity Highlighting**
- Markets with liquidity above threshold are highlighted in **green**
- Makes it easy to spot high-liquidity opportunities
- Adjustable threshold lets you focus on what matters

### **Exchange Best Prices**
- Shows the **best available price** across all exchanges (Kalshi, Polymarket, SX Bet)
- Shows which exchange has the best price
- Shows total liquidity available at that price

### **Fair Price Comparison**
- Shows **no-vig fair prices** for both sides
- Helps you understand the true market price
- Compare fair price to your soft book for edge calculation

### **Top Opportunities**
- Expandable sections showing top 5 markets by liquidity
- Detailed breakdown of both sides
- Easy comparison format

## Example Workflow

1. **Set threshold to $50,000** (or your preferred amount)
2. **Look for green highlighted rows** (outsized liquidity)
3. **Check "Top Opportunities"** section for highest liquidity markets
4. **Compare exchange prices to your soft book:**
   - Example: Exchange shows -110, your book shows -105
   - You have a 5-point edge → Bet on your book
5. **Execute quickly** - High liquidity means sharp money is moving

## Tips

- **Lower threshold** (e.g., $20,000) to see more opportunities
- **Higher threshold** (e.g., $100,000) to focus on only the biggest spots
- **Watch for imbalances** - High imbalance ratio can indicate sharp money
- **Compare fair prices** - No-vig prices show true market value
- **Check sources** - Different exchanges may have different prices

## What Makes a Good Spot?

1. **High Liquidity** - More liquidity = more confidence in the price
2. **Better Exchange Price** - Exchange price better than your book = edge
3. **Low Vig** - Lower vig = more efficient market
4. **Reasonable Imbalance** - Extreme imbalance (3x+) can indicate sharp money

## Real-Time Updates

- Data refreshes every 15 seconds (if auto-refresh enabled)
- Check timestamp to verify data is current
- Green checkmark = data is fresh (< 20 seconds old)

---

**Ready to find spots!** Switch to Spot Finder view and start identifying arbitrage opportunities.

