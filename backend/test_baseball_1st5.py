#!/usr/bin/env python3
"""
Test script to verify 1st 5 innings data extraction for baseball
"""

import sys
import os
import json
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from betbck_request_manager import scrape_betbck_for_game_queued
from utils.pod_utils import analyze_markets_for_ev

def test_baseball_1st5_extraction():
    """Test 1st 5 innings data extraction for Phillies vs Brewers."""
    print("=" * 60)
    print("Testing Baseball 1st 5 Innings Data Extraction")
    print("=" * 60)
    
    # Test parameters for the specific game
    home_team = "Milwaukee Brewers"
    away_team = "Philadelphia Phillies" 
    event_id = 1614324058
    search_term = "Phillies"
    
    print(f"Testing 1st 5 innings extraction for: {home_team} vs {away_team}")
    print(f"Event ID: {event_id}")
    print()
    
    try:
        # Step 1: Get BetBCK data (including 1st 5 innings data)
        print("Step 1: Scraping BetBCK data...")
        betbck_data = scrape_betbck_for_game_queued(home_team, away_team, search_term, event_id)
        
        if not betbck_data:
            print("✗ Failed to get BetBCK data")
            return
        
        print("✓ BetBCK data retrieved successfully")
        print(f"  - Full game data: {bool(betbck_data.get('home_moneyline_american'))}")
        print(f"  - 1H/1st 5 data: {bool(betbck_data.get('1H_data'))}")
        
        if betbck_data.get('1H_data'):
            print("\n1H/1st 5 Innings Data Found:")
            print(json.dumps(betbck_data['1H_data'], indent=2))
        else:
            print("\n⚠ No 1H/1st 5 innings data found")
        
        # Step 2: Mock Pinnacle data with 1st 5 innings
        print("\nStep 2: Preparing Pinnacle data with 1st 5 innings...")
        pinnacle_data = {
            "data": {
                "home": "Milwaukee Brewers",
                "away": "Philadelphia Phillies",
                "periods": {
                    "num_0": {  # Full game
                        "money_line": {
                            "nvp_american_home": "-115",
                            "nvp_american_away": "-105",
                            "nvp_home": 1.87,
                            "nvp_away": 1.95
                        },
                        "spreads": {
                            "-1.5": {
                                "hdp": -1.5,
                                "nvp_american_home": "+170",
                                "nvp_american_away": "-210",
                                "nvp_home": 2.7,
                                "nvp_away": 1.48
                            }
                        },
                        "totals": {
                            "8.0": {
                                "points": 8.0,
                                "nvp_american_over": "-115",
                                "nvp_american_under": "-105",
                                "nvp_over": 1.87,
                                "nvp_under": 1.95
                            }
                        }
                    },
                    "num_1": {  # 1st 5 innings
                        "money_line": {
                            "nvp_american_home": "-120",
                            "nvp_american_away": "+100",
                            "nvp_home": 1.83,
                            "nvp_away": 2.0
                        },
                        "spreads": {
                            "-0.5": {
                                "hdp": -0.5,
                                "nvp_american_home": "-110",
                                "nvp_american_away": "-110",
                                "nvp_home": 1.91,
                                "nvp_away": 1.91
                            }
                        },
                        "totals": {
                            "4.0": {
                                "points": 4.0,
                                "nvp_american_over": "-110",
                                "nvp_american_under": "-110",
                                "nvp_over": 1.91,
                                "nvp_under": 1.91
                            }
                        }
                    }
                }
            }
        }
        print("✓ Pinnacle data prepared")
        
        # Step 3: Calculate EV with period separation
        print("\nStep 3: Calculating EV with period separation...")
        ev_results = analyze_markets_for_ev(betbck_data, pinnacle_data)
        
        print(f"✓ EV calculation completed")
        print(f"Found {len(ev_results)} total EV opportunities")
        
        # Step 4: Analyze results
        print("\nStep 4: Analyzing results...")
        
        # Separate by period
        full_game_results = [r for r in ev_results if not r['market'].startswith('1H')]
        first_half_results = [r for r in ev_results if r['market'].startswith('1H')]
        
        print(f"\nFull Game EV Opportunities: {len(full_game_results)}")
        for result in full_game_results:
            print(f"  - {result['market']} {result['selection']} {result['line']}: {result['ev']}")
        
        print(f"\n1H/1st 5 EV Opportunities: {len(first_half_results)}")
        for result in first_half_results:
            print(f"  - {result['market']} {result['selection']} {result['line']}: {result['ev']}")
        
        # Step 5: Validate period separation
        print("\nStep 5: Validating period separation...")
        
        # Check for any mixing
        mixed_results = []
        for result in ev_results:
            market = result['market']
            if '1H' in market and not market.startswith('1H'):
                mixed_results.append(result)
            elif not market.startswith('1H') and '1H' in str(result):
                mixed_results.append(result)
        
        if mixed_results:
            print(f"❌ ERROR: Found {len(mixed_results)} mixed period results!")
            for result in mixed_results:
                print(f"  - {result['market']} {result['selection']} {result['line']}")
        else:
            print("✓ SUCCESS: No period mixing detected")
        
        # Check that we have both periods if data is available
        if betbck_data.get('1H_data') and len(first_half_results) == 0:
            print("⚠ WARNING: Have 1H BetBCK data but no 1H EV results")
        elif not betbck_data.get('1H_data') and len(first_half_results) > 0:
            print("⚠ WARNING: No 1H BetBCK data but have 1H EV results")
        else:
            print("✓ Period data consistency verified")
        
        print("\n" + "=" * 60)
        if betbck_data.get('1H_data') and len(first_half_results) > 0:
            print("FINAL RESULT: 1st 5 innings data extraction and EV calculation working correctly!")
        else:
            print("FINAL RESULT: 1st 5 innings data extraction needs improvement")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_baseball_1st5_extraction()
