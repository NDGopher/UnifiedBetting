"""
Network Monitor for BetBCK.com
Captures all network requests to identify hidden API endpoints or better request patterns.

Usage:
    python betbck_network_monitor.py
    
This will:
1. Open betbck.com in Chrome
2. Monitor all network traffic
3. Save requests/responses to data/betbck_network_log.json
4. Identify potential API endpoints, AJAX calls, or WebSocket connections
"""

import json
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
# DesiredCapabilities no longer needed - using options.set_capability instead
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def setup_driver():
    """Setup Chrome driver with performance logging"""
    options = Options()
    # Run headless if you want, but visible is better for debugging
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--enable-logging")
    options.add_argument("--v=1")
    
    # Enable performance logging (newer Selenium way)
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    driver = webdriver.Chrome(options=options)
    return driver

def get_network_logs(driver):
    """Extract network logs from Chrome performance logs"""
    logs = driver.get_log('performance')
    network_events = []
    
    for log in logs:
        message = json.loads(log['message'])
        message_type = message.get('message', {}).get('method', '')
        
        # Filter for network-related events
        network_events_to_capture = [
            'Network.requestWillBeSent',
            'Network.responseReceived',
            'Network.responseReceivedExtraInfo',
            'Network.dataReceived',
            'Network.loadingFinished',
            'Network.requestWillBeSentExtraInfo',
        ]
        
        if message_type in network_events_to_capture:
            network_events.append({
                'timestamp': log['timestamp'],
                'type': message_type,
                'data': message.get('message', {}).get('params', {})
            })
    
    return network_events

def analyze_network_traffic(network_events):
    """Analyze network traffic to find interesting endpoints"""
    requests = {}
    responses = {}
    
    for event in network_events:
        event_type = event['type']
        params = event.get('data', {})
        
        if event_type == 'Network.requestWillBeSent':
            request_id = params.get('requestId')
            request_info = params.get('request', {})
            url = request_info.get('url', '')
            method = request_info.get('method', '')
            
            # Only track betbck.com URLs
            if 'betbck.com' in url:
                if request_id not in requests:
                    requests[request_id] = {
                        'url': url,
                        'method': method,
                        'headers': request_info.get('headers', {}),
                        'postData': request_info.get('postData'),
                        'timestamp': event['timestamp']
                    }
        
        elif event_type == 'Network.responseReceived':
            request_id = params.get('requestId')
            response = params.get('response', {})
            url = response.get('url', '')
            
            if 'betbck.com' in url:
                if request_id not in responses:
                    responses[request_id] = {
                        'url': url,
                        'status': response.get('status', 0),
                        'statusText': response.get('statusText', ''),
                        'headers': response.get('headers', {}),
                        'mimeType': response.get('mimeType', ''),
                        'timestamp': event['timestamp']
                    }
    
    return requests, responses

def find_potential_api_endpoints(requests, responses):
    """Identify potential API endpoints"""
    api_patterns = {
        'json_responses': [],
        'ajax_endpoints': [],
        'post_endpoints': [],
        'interesting_urls': []
    }
    
    for req_id, req_data in requests.items():
        url = req_data['url']
        
        # Check for JSON responses
        if req_id in responses:
            resp = responses[req_id]
            content_type = resp.get('mimeType', '').lower()
            if 'json' in content_type:
                api_patterns['json_responses'].append({
                    'url': url,
                    'method': req_data['method'],
                    'status': resp.get('status'),
                    'postData': req_data.get('postData')
                })
        
        # Check for AJAX-style endpoints
        if any(pattern in url for pattern in ['/ajax/', '/api/', '/data/', '/json', 'callback=', '.json']):
            api_patterns['ajax_endpoints'].append({
                'url': url,
                'method': req_data['method'],
                'postData': req_data.get('postData')
            })
        
        # Check for POST requests (might be form submissions we can optimize)
        if req_data['method'] == 'POST':
            api_patterns['post_endpoints'].append({
                'url': url,
                'method': req_data['method'],
                'postData': req_data.get('postData', '')[:500],  # First 500 chars
                'headers': {k: v for k, v in req_data.get('headers', {}).items() 
                           if k.lower() in ['content-type', 'referer']}
            })
        
        # Other interesting URLs (not main pages)
        if all(not url.endswith(ext) for ext in ['.html', '.php', '/', '.css', '.js', '.png', '.jpg', '.gif', '.ico']):
            if 'betbck.com' in url and '?' in url:  # Has query parameters
                api_patterns['interesting_urls'].append(url)
    
    return api_patterns

def monitor_sport_click(driver, sport_text="Soccer"):
    """Monitor network traffic when clicking into a sport"""
    print(f"\n[Monitor] Waiting for page to load...")
    time.sleep(3)
    
    # Clear previous logs
    driver.get_log('performance')
    
    print(f"\n[Monitor] Looking for sport: '{sport_text}'...")
    
    try:
        # Try different selectors for sport links
        sport_selectors = [
            f"//a[contains(text(), '{sport_text}')]",
            f"//span[contains(text(), '{sport_text}')]",
            f"//div[contains(text(), '{sport_text}')]",
            f"//*[contains(@class, 'sport') and contains(text(), '{sport_text}')]",
        ]
        
        sport_element = None
        for selector in sport_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    sport_element = elements[0]
                    print(f"[Monitor] Found sport element with selector: {selector}")
                    break
            except:
                continue
        
        if sport_element:
            print(f"[Monitor] Clicking on sport: '{sport_text}'...")
            sport_element.click()
            time.sleep(5)  # Wait for page to load
            
            print(f"[Monitor] Collecting network logs...")
            network_events = get_network_logs(driver)
            print(f"[Monitor] Captured {len(network_events)} network events")
            
            return network_events
        else:
            print(f"[Monitor] Could not find sport element: '{sport_text}'")
            return []
            
    except Exception as e:
        print(f"[Monitor] Error clicking sport: {e}")
        return []

def main():
    """Main monitoring function"""
    print("=" * 80)
    print("BetBCK.com Network Monitor")
    print("=" * 80)
    print("\nThis script will:")
    print("1. Open betbck.com and login")
    print("2. Monitor network traffic")
    print("3. Click into a sport to see what requests are made")
    print("4. Save findings to data/betbck_network_log.json")
    print("\n" + "=" * 80 + "\n")
    
    driver = None
    try:
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        betbck_config = config.get('betbck', {})
        login_url = betbck_config.get('login_page_url', 'https://betbck.com/')
        credentials = betbck_config.get('credentials', {})
        
        # Setup driver
        driver = setup_driver()
        print(f"[Monitor] Opening {login_url}...")
        driver.get(login_url)
        time.sleep(3)
        
        # Login
        print("[Monitor] Attempting to login...")
        try:
            customer_id_field = driver.find_element(By.NAME, "customerID")
            password_field = driver.find_element(By.NAME, "password")
            
            customer_id_field.send_keys(credentials.get('customerID', ''))
            password_field.send_keys(credentials.get('password', ''))
            
            login_button = driver.find_element(By.XPATH, "//input[@type='submit']")
            login_button.click()
            time.sleep(5)
            
            print("[Monitor] Login completed (or attempted)")
        except Exception as e:
            print(f"[Monitor] Login error (may already be logged in): {e}")
        
        # Monitor initial page load
        print("\n[Monitor] Capturing initial page load network traffic...")
        time.sleep(3)
        initial_events = get_network_logs(driver)
        print(f"[Monitor] Initial load: {len(initial_events)} events")
        
        # Monitor sport click
        print("\n[Monitor] Now will monitor what happens when clicking into a sport...")
        time.sleep(2)
        
        # Try different sports
        sports_to_try = ["Soccer", "NBA", "Baseball", "Basketball"]
        all_sport_events = []
        
        for sport in sports_to_try:
            print(f"\n{'='*80}")
            print(f"[Monitor] Trying sport: {sport}")
            print(f"{'='*80}")
            
            # Navigate back to main page first
            main_url = betbck_config.get('main_page_url_after_login', 
                                        'https://betbck.com/Qubic/StraightSportSelection.php')
            driver.get(main_url)
            time.sleep(3)
            
            # Clear logs before clicking
            driver.get_log('performance')
            
            # Click sport and monitor
            sport_events = monitor_sport_click(driver, sport)
            if sport_events:
                all_sport_events.extend(sport_events)
                print(f"[Monitor] Captured {len(sport_events)} events for {sport}")
        
        # Analyze all events
        print("\n" + "="*80)
        print("[Monitor] Analyzing network traffic...")
        print("="*80)
        
        all_events = initial_events + all_sport_events
        requests, responses = analyze_network_traffic(all_events)
        api_patterns = find_potential_api_endpoints(requests, responses)
        
        # Print findings
        print(f"\n[Monitor] Analysis Results:")
        print(f"  Total network events: {len(all_events)}")
        print(f"  Unique requests: {len(requests)}")
        print(f"  Unique responses: {len(responses)}")
        print(f"\n  JSON responses found: {len(api_patterns['json_responses'])}")
        print(f"  AJAX endpoints found: {len(api_patterns['ajax_endpoints'])}")
        print(f"  POST endpoints found: {len(api_patterns['post_endpoints'])}")
        print(f"  Interesting URLs found: {len(api_patterns['interesting_urls'])}")
        
        # Save results
        output_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'betbck_network_log.json')
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_events': len(all_events),
                'unique_requests': len(requests),
                'unique_responses': len(responses),
            },
            'api_patterns': api_patterns,
            'sample_requests': dict(list(requests.items())[:20]),  # First 20
            'sample_responses': dict(list(responses.items())[:20]),
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n[Monitor] Results saved to: {output_file}")
        
        # Print interesting findings
        if api_patterns['json_responses']:
            print("\n[Monitor] ⭐ JSON RESPONSES FOUND (Potential API endpoints):")
            for item in api_patterns['json_responses']:
                print(f"  - {item['method']} {item['url']} (Status: {item['status']})")
        
        if api_patterns['ajax_endpoints']:
            print("\n[Monitor] ⭐ AJAX ENDPOINTS FOUND:")
            for item in api_patterns['ajax_endpoints']:
                print(f"  - {item['method']} {item['url']}")
        
        if api_patterns['post_endpoints']:
            print("\n[Monitor] 📤 POST ENDPOINTS (May be optimizable):")
            for item in api_patterns['post_endpoints'][:5]:  # First 5
                print(f"  - POST {item['url']}")
                if item.get('postData'):
                    print(f"    Data: {item['postData'][:100]}...")
        
        print("\n" + "="*80)
        print("[Monitor] Monitoring complete!")
        print("="*80)
        
        # Keep browser open for manual inspection
        print("\n[Monitor] Keeping browser open for 30 seconds for manual inspection...")
        print("[Monitor] Close the browser window or wait for auto-close.")
        time.sleep(30)
        
    except Exception as e:
        print(f"\n[Monitor] ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if driver:
            print("\n[Monitor] Closing browser...")
            driver.quit()

if __name__ == "__main__":
    main()

