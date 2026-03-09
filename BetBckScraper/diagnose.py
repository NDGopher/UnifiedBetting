import json
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# --- CONFIGURATION ---
TARGET_URL = "https://www.betbck.com" 
RECORDING_DURATION = 90  # Seconds to keep browser open (gave you extra time)

def get_recorder_browser():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # CRITICAL: This enables the "spy" mode to see hidden APIs
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    driver = webdriver.Chrome(options=options)
    return driver

def main():
    driver = get_recorder_browser()
    
    print("\n" + "="*60)
    print("🎥 NETWORK RECORDER STARTED")
    print(f"⏳ I will keep the browser open for {RECORDING_DURATION} seconds.")
    print("👉 ACTION: Log in manually and click on the betting lines.")
    print("="*60 + "\n")
    
    try:
        driver.get(TARGET_URL)
        
        # We just sleep in small chunks to show a countdown, keeping the browser open
        for remaining in range(RECORDING_DURATION, 0, -1):
            print(f"🔴 Recording... {remaining} seconds remaining (Do your thing!)", end='\r')
            time.sleep(1)
        
        print("\n\n🛑 Time's up! Stopping recording and saving data...")

        # --- 1. CAPTURE HTML (What you saw at the end) ---
        with open("debug_dashboard.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("✅ Saved 'debug_dashboard.html'")

        # --- 2. CAPTURE NETWORK LOGS (The hidden API evidence) ---
        logs = driver.get_log("performance")
        network_urls = []
        
        print("🕵️ Processing network logs...")
        for entry in logs:
            try:
                message = json.loads(entry["message"])["message"]
                if message["method"] == "Network.responseReceived":
                    url = message["params"]["response"]["url"]
                    # We filter out boring stuff like fonts/images to find the data
                    if not any(x in url for x in [".png", ".jpg", ".css", ".js", "font", "favicon"]):
                        network_urls.append(url)
            except:
                continue

        with open("debug_network_logs.txt", "w", encoding="utf-8") as f:
            # Save unique URLs only
            unique_urls = set(network_urls)
            for url in unique_urls:
                f.write(f"{url}\n")
                
        print(f"✅ Saved 'debug_network_logs.txt' ({len(unique_urls)} requests captured)")
        print("📢 Please upload 'debug_dashboard.html' and 'debug_network_logs.txt' to the chat.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()