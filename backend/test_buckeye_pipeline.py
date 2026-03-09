#!/usr/bin/env python3
"""
Test script for Buckeye EV pipeline
Tests Get Event IDs -> Run Buckeye calculations
"""

import requests
import json
import time
from datetime import datetime

API_BASE = "http://localhost:5001"

def test_get_event_ids():
    """Test getting event IDs from Pinnacle"""
    print("\n" + "="*60)
    print("STEP 1: Getting Event IDs from Pinnacle")
    print("="*60)
    
    start_time = time.time()
    try:
        response = requests.post(f"{API_BASE}/buckeye/get-event-ids", timeout=310)
        elapsed = time.time() - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Time Elapsed: {elapsed:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Status: {data.get('status')}")
            print(f"Message: {data.get('message')}")
            
            event_data = data.get('data', {})
            event_count = event_data.get('event_count', 0)
            print(f"Event Count: {event_count}")
            
            if event_count > 0:
                event_ids = event_data.get('event_ids', [])
                print(f"Sample Event IDs (first 5): {event_ids[:5]}")
                return True, event_count
            else:
                print("⚠️  No events found!")
                return False, 0
        else:
            print(f"❌ Error: {response.text[:500]}")
            return False, 0
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Exception after {elapsed:.2f}s: {e}")
        return False, 0

def test_run_buckeye():
    """Test running Buckeye EV calculations"""
    print("\n" + "="*60)
    print("STEP 2: Running Buckeye EV Calculations")
    print("="*60)
    print("⚠️  This may take several minutes...")
    
    start_time = time.time()
    try:
        # Start the streaming pipeline
        response = requests.post(f"{API_BASE}/api/run-streaming-pipeline", timeout=600)
        elapsed = time.time() - start_time
        
        print(f"Initial Response Status: {response.status_code}")
        print(f"Time to Start: {elapsed:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Status: {data.get('status')}")
            print(f"Message: {data.get('message')}")
            
            # Poll for completion
            print("\nPolling for results...")
            max_wait = 600  # 10 minutes max
            poll_interval = 5
            waited = 0
            
            while waited < max_wait:
                status_response = requests.get(f"{API_BASE}/api/pipeline-status")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get('status') == 'success':
                        pipeline_data = status_data.get('data', {})
                        running = pipeline_data.get('running', False)
                        
                        if not running:
                            print(f"\n✅ Pipeline completed after {waited} seconds")
                            break
                        else:
                            print(f"⏳ Still running... ({waited}s elapsed)", end='\r')
                
                time.sleep(poll_interval)
                waited += poll_interval
            
            # Get final results
            print("\nFetching final results...")
            results_response = requests.get(f"{API_BASE}/buckeye/results")
            total_time = time.time() - start_time
            
            if results_response.status_code == 200:
                results_data = results_response.json()
                print(f"\nTotal Pipeline Time: {total_time:.2f} seconds ({total_time/60:.1f} minutes)")
                
                if results_data.get('status') == 'success':
                    results = results_data.get('data', {})
                    markets = results.get('markets', [])
                    total_events = results.get('total_events', 0)
                    last_update = results.get('last_update')
                    
                    print(f"\n📊 RESULTS:")
                    print(f"  Total Markets Found: {len(markets)}")
                    print(f"  Total Events: {total_events}")
                    print(f"  Last Update: {last_update}")
                    
                    if markets:
                        # Show top 10 by EV
                        sorted_markets = sorted(markets, key=lambda x: float(x.get('ev', '0').replace('%', '') or '0'), reverse=True)
                        print(f"\n  Top 10 Markets by EV:")
                        for i, market in enumerate(sorted_markets[:10], 1):
                            ev = market.get('ev', '0%')
                            matchup = market.get('matchup', 'N/A')
                            bet = market.get('bet', 'N/A')
                            book_odds = market.get('betbck_odds', 'N/A')
                            pin_nvp = market.get('pinnacle_nvp', 'N/A')
                            print(f"    {i}. EV: {ev:>8} | {matchup} | {bet} | Book: {book_odds} | Pin: {pin_nvp}")
                    
                    return True, len(markets)
                else:
                    print(f"❌ Error in results: {results_data.get('message')}")
                    return False, 0
            else:
                print(f"❌ Failed to fetch results: {results_response.text[:500]}")
                return False, 0
        else:
            print(f"❌ Error starting pipeline: {response.text[:500]}")
            return False, 0
            
    except Exception as e:
        total_time = time.time() - start_time
        print(f"❌ Exception after {total_time:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        return False, 0

def main():
    print("\n" + "="*60)
    print("BUCKEYE EV PIPELINE TEST")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Step 1: Get Event IDs
    success, event_count = test_get_event_ids()
    
    if not success:
        print("\n❌ Failed to get event IDs. Cannot proceed with calculations.")
        return
    
    if event_count == 0:
        print("\n⚠️  No events found. Skipping calculations.")
        return
    
    # Small delay before starting calculations
    print(f"\n⏳ Waiting 3 seconds before starting calculations...")
    time.sleep(3)
    
    # Step 2: Run Buckeye calculations
    success, market_count = test_run_buckeye()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    if success:
        print(f"✅ Successfully found {market_count} markets")
    else:
        print("❌ Pipeline failed")

if __name__ == "__main__":
    main()

