"""
Simple Network Analyzer for BetBCK
Uses requests library to analyze what endpoints are actually being called.
This is a simpler alternative that doesn't require Selenium.
"""

import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup

def analyze_betbck_endpoints():
    """Analyze BetBCK endpoints by making actual requests"""
    
    # Load config
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    betbck_config = config.get('betbck', {})
    credentials = betbck_config.get('credentials', {})
    headers = betbck_config.get('headers', {})
    
    print("=" * 80)
    print("BetBCK Network Endpoint Analyzer")
    print("=" * 80)
    print("\nThis will analyze what endpoints BetBCK uses by:\n")
    print("1. Logging in")
    print("2. Loading the main page")
    print("3. Analyzing the HTML for AJAX calls, forms, and endpoints")
    print("4. Checking for any JavaScript that makes API calls")
    print("\n" + "=" * 80 + "\n")
    
    session = requests.Session()
    session.headers.update(headers)
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'endpoints_found': [],
        'html_analysis': {},
        'javascript_analysis': {}
    }
    
    try:
        login_url = betbck_config.get('login_page_url', 'https://betbck.com/')
        login_action_url = betbck_config.get('login_action_url', 'https://betbck.com/Qubic/SecurityPage.php')
        main_page_url = betbck_config.get('main_page_url_after_login', 
                                         'https://betbck.com/Qubic/StraightSportSelection.php')
        
        print("[Analyzer] Step 1: Loading login page...")
        login_page = session.get(login_url, timeout=10)
        print(f"[Analyzer] Login page status: {login_page.status_code}")
        
        # Analyze login page HTML
        soup = BeautifulSoup(login_page.text, 'html.parser')
        
        # Find all forms
        forms = soup.find_all('form')
        print(f"\n[Analyzer] Found {len(forms)} form(s) on login page:")
        for form in forms:
            action = form.get('action', '')
            method = form.get('method', 'GET')
            print(f"  - {method} {action}")
        
        # Find all script tags (might contain AJAX calls)
        scripts = soup.find_all('script')
        print(f"\n[Analyzer] Found {len(scripts)} script tag(s) on login page")
        
        print("\n[Analyzer] Step 2: Attempting login...")
        login_payload = credentials.copy()
        login_response = session.post(login_action_url, data=login_payload, 
                                     headers=headers, allow_redirects=True, timeout=10)
        print(f"[Analyzer] Login response status: {login_response.status_code}")
        print(f"[Analyzer] Login response URL: {login_response.url}")
        
        if 'logout' in login_response.text.lower():
            print("[Analyzer] ✅ Login successful!")
        else:
            print("[Analyzer] ⚠️ Login may have failed - 'logout' not found in response")
        
        print("\n[Analyzer] Step 3: Loading main page...")
        main_page = session.get(main_page_url, headers=headers, timeout=10)
        print(f"[Analyzer] Main page status: {main_page.status_code}")
        print(f"[Analyzer] Main page size: {len(main_page.text)} bytes")
        
        # Analyze main page
        main_soup = BeautifulSoup(main_page.text, 'html.parser')
        
        # Find all forms on main page
        main_forms = main_soup.find_all('form')
        print(f"\n[Analyzer] Found {len(main_forms)} form(s) on main page:")
        form_details = []
        for form in main_forms:
            action = form.get('action', '')
            method = form.get('method', 'GET')
            name = form.get('name', '')
            form_id = form.get('id', '')
            print(f"  - Form: name='{name}', id='{form_id}'")
            print(f"    Action: {method} {action}")
            
            # Find all inputs in form
            inputs = form.find_all(['input', 'select'])
            input_names = [inp.get('name', '') for inp in inputs if inp.get('name')]
            print(f"    Inputs: {', '.join(input_names[:10])}")
            
            form_details.append({
                'name': name,
                'id': form_id,
                'action': action,
                'method': method,
                'inputs': input_names
            })
        
        results['endpoints_found'] = form_details
        
        # Find all script tags and analyze JavaScript
        main_scripts = main_soup.find_all('script')
        print(f"\n[Analyzer] Found {len(main_scripts)} script tag(s) on main page")
        
        # Look for AJAX patterns in JavaScript
        ajax_patterns = [
            'XMLHttpRequest',
            'fetch(',
            '$.ajax',
            '$.post',
            '$.get',
            'axios.',
            'ajax',
            '/api/',
            '/ajax/',
            '/data/',
            '.json',
            'callback=',
            'jsonp'
        ]
        
        js_code = '\n'.join([script.string or '' for script in main_scripts if script.string])
        found_patterns = []
        
        for pattern in ajax_patterns:
            if pattern.lower() in js_code.lower():
                # Find context around the pattern
                index = js_code.lower().find(pattern.lower())
                context = js_code[max(0, index-50):index+100]
                found_patterns.append({
                    'pattern': pattern,
                    'context': context
                })
                print(f"\n  ⚠️ Found pattern: '{pattern}'")
                print(f"    Context: {context[:150]}...")
        
        results['javascript_analysis'] = {
            'scripts_found': len(main_scripts),
            'ajax_patterns': found_patterns
        }
        
        # Check for any links that might be API endpoints
        links = main_soup.find_all('a', href=True)
        api_links = []
        for link in links:
            href = link.get('href', '')
            if any(pattern in href.lower() for pattern in ['/api/', '/ajax/', '/data/', '.json', 'jsonp']):
                api_links.append(href)
                print(f"\n  ⚠️ Found potential API link: {href}")
        
        # Look for onclick handlers that might make AJAX calls
        onclick_elements = main_soup.find_all(attrs={'onclick': True})
        print(f"\n[Analyzer] Found {len(onclick_elements)} element(s) with onclick handlers")
        for i, elem in enumerate(onclick_elements[:5]):  # First 5
            onclick = elem.get('onclick', '')
            if any(pattern in onclick.lower() for pattern in ['ajax', 'fetch', 'xmlhttp', '.post', '.get']):
                print(f"  ⚠️ Potential AJAX in onclick: {onclick[:100]}...")
        
        # Find all URLs in the page source
        import re
        url_pattern = r'https?://[^\s"\'<>){}]+'
        urls = re.findall(url_pattern, main_page.text)
        betbck_urls = [url for url in urls if 'betbck.com' in url]
        unique_betbck_urls = list(set(betbck_urls))
        
        print(f"\n[Analyzer] Found {len(unique_betbck_urls)} unique BetBCK URLs in page source")
        print("[Analyzer] Checking for API-like endpoints...")
        
        api_like_urls = []
        for url in unique_betbck_urls[:50]:  # First 50
            if any(pattern in url.lower() for pattern in ['/api/', '/ajax/', '/data/', '/json', 'callback=', 'jsonp']):
                api_like_urls.append(url)
                print(f"  ⚠️ API-like URL: {url}")
        
        # Save results
        output_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'betbck_endpoint_analysis.json')
        
        results['api_like_urls'] = api_like_urls
        results['form_analysis'] = {
            'total_forms': len(main_forms),
            'form_details': form_details
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n[Analyzer] Results saved to: {output_file}")
        
        # Summary
        print("\n" + "=" * 80)
        print("ANALYSIS SUMMARY")
        print("=" * 80)
        print(f"Forms found: {len(main_forms)}")
        print(f"Scripts found: {len(main_scripts)}")
        print(f"AJAX patterns found: {len(found_patterns)}")
        print(f"API-like URLs: {len(api_like_urls)}")
        
        if found_patterns or api_like_urls:
            print("\n✅ POTENTIAL API ENDPOINTS FOUND!")
            print("Check the detailed output above and the saved JSON file.")
        else:
            print("\n❌ No obvious API endpoints found.")
            print("BetBCK appears to use server-side rendered HTML only.")
        
        print("=" * 80)
        
        return results
        
    except Exception as e:
        print(f"\n[Analyzer] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return results

if __name__ == "__main__":
    analyze_betbck_endpoints()

