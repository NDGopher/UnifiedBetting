#!/usr/bin/env python3
import requests
import json
import time

def test_buckeye_pipeline():
    """Test the Buckeye pipeline and show detailed logs"""
    print("🚀 Testing Buckeye Pipeline...")
    print("=" * 50)
    
    try:
        # Test if backend is running
        print("1. Checking if backend is running...")
        health_response = requests.get("http://localhost:5001/healthz", timeout=5)
        if health_response.status_code == 200:
            print("✅ Backend is running")
        else:
            print(f"❌ Backend health check failed: {health_response.status_code}")
            return
    except Exception as e:
        print(f"❌ Backend is not running: {e}")
        return
    
    # Trigger the pipeline
    print("\n2. Triggering Buckeye pipeline...")
    start_time = time.time()
    
    try:
        response = requests.post("http://localhost:5001/api/run-pipeline", timeout=300)  # 5 minute timeout
        end_time = time.time()
        
        print(f"✅ Pipeline completed in {end_time - start_time:.2f} seconds")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n📊 Pipeline Results:")
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ Pipeline failed with status {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Pipeline timed out after 5 minutes")
    except Exception as e:
        print(f"❌ Pipeline failed with error: {e}")

if __name__ == "__main__":
    test_buckeye_pipeline()
