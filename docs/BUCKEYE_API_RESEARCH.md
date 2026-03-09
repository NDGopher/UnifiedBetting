# Buckeye PPH API Research - Real-Time Odds

## Critical Discovery

**betbck.com is a skin for Buckeye PPH**. This means:
- The **real backend** is Buckeye PPH
- betbck.com just displays Buckeye's data
- There **MUST be an API** that powers the real-time updates
- Services like **BetStamp PRO** and **SpotOdds** have access to this API

## How to Find the API

### The Key Insight

When you look at betbck.com in your browser and odds update in real-time, **something is making API calls**. We need to intercept those calls.

### Method 1: Browser DevTools Network Interception (EASIEST)

**Step-by-Step Instructions:**

1. **Open betbck.com in Chrome**
   - Login to your account

2. **Open Chrome DevTools**
   - Press `F12` or `Ctrl+Shift+I`
   - Go to **Network** tab

3. **Filter Network Requests**
   - Click the **Filter** button
   - Select **Fetch/XHR** (for AJAX calls)
   - Also check **WS** (for WebSocket connections)
   - Clear the filter and look for URLs containing: `api`, `ajax`, `data`, `json`, `odds`

4. **Trigger an Odds Update**
   - Navigate to a game with live odds
   - Wait for odds to update (if they auto-refresh)
   - OR manually refresh the page
   - **Watch the Network tab for NEW requests**

5. **Look For:**
   - Requests to URLs with `/api/`, `/ajax/`, `/json`, `/data/`
   - POST/GET requests that return JSON data
   - WebSocket connections (`ws://` or `wss://`)
   - Requests with `betbck.com` but different paths than the main pages
   - Requests with query parameters like `?format=json` or `?callback=`

6. **Capture the Request Details:**
   - Click on any interesting request
   - Go to **Headers** tab - Note the full URL
   - Go to **Payload** tab - Note any POST data
   - Go to **Response** tab - See if it's JSON
   - **Right-click → Copy → Copy as cURL** (for testing later)

### What to Look For

#### Pattern 1: AJAX Polling
```
Every few seconds, a request like:
GET https://betbck.com/api/odds?game_id=12345
OR
POST https://betbck.com/ajax/get_odds.php
```

#### Pattern 2: WebSocket
```
In Network tab, look for:
Type: websocket
URL: wss://betbck.com/ws/odds
OR
wss://api.buckeye.com/...
```

#### Pattern 3: JSONP Callback
```
GET https://betbck.com/api/odds?callback=jQuery123456789
Response: jQuery123456789({...JSON data...})
```

#### Pattern 4: Hidden Buckeye API
```
Since betbck.com is a skin, look for:
https://*.buckeye*.com/...
https://*.pph*.com/...
https://api.*.com/odds...
```

### Method 2: JavaScript Injection (Advanced)

If DevTools doesn't show the requests (they might be obfuscated), inject JavaScript to intercept:

1. Open betbck.com and login
2. Open Console tab in DevTools
3. Paste this code:

```javascript
// Intercept all fetch requests
const originalFetch = window.fetch;
window.fetch = function(...args) {
    console.log('[FETCH INTERCEPT]', args[0], args[1]);
    return originalFetch.apply(this, args).then(response => {
        const clonedResponse = response.clone();
        clonedResponse.text().then(text => {
            if (text.includes('odds') || text.includes('json') || text.startsWith('{')) {
                console.log('[FETCH RESPONSE]', args[0], text);
            }
        });
        return response;
    });
};

// Intercept XMLHttpRequest
const originalXHROpen = XMLHttpRequest.prototype.open;
const originalXHRSend = XMLHttpRequest.prototype.send;

XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this._url = url;
    this._method = method;
    return originalXHROpen.apply(this, [method, url, ...rest]);
};

XMLHttpRequest.prototype.send = function(...args) {
    this.addEventListener('load', function() {
        if (this.responseText && (this.responseText.includes('odds') || this.responseText.startsWith('{'))) {
            console.log('[XHR INTERCEPT]', this._method, this._url, this.responseText);
        }
    });
    return originalXHRSend.apply(this, args);
};

console.log('🔍 Network interceptor installed! Monitor odds updates now.');
```

4. Then trigger an odds update and watch the console

### Method 3: Chrome Extension with Request Interception

Create a simple extension that logs all network requests:

**manifest.json:**
```json
{
  "manifest_version": 3,
  "name": "BetBCK API Interceptor",
  "version": "1.0",
  "permissions": ["webRequest", "storage"],
  "host_permissions": ["*://betbck.com/*", "*://*.buckeye.com/*"],
  "background": {
    "service_worker": "background.js"
  }
}
```

**background.js:**
```javascript
chrome.webRequest.onBeforeRequest.addListener(
  function(details) {
    if (details.url.includes('api') || details.url.includes('ajax') || 
        details.url.includes('json') || details.url.includes('odds')) {
      console.log('[API REQUEST]', details.method, details.url, details.requestBody);
    }
  },
  {urls: ["*://betbck.com/*", "*://*.buckeye.com/*"]},
  ["requestBody"]
);

chrome.webRequest.onCompleted.addListener(
  function(details) {
    if (details.url.includes('api') || details.url.includes('ajax') || 
        details.url.includes('json') || details.url.includes('odds')) {
      fetch(details.url).then(r => r.text()).then(text => {
        console.log('[API RESPONSE]', details.url, text);
      });
    }
  },
  {urls: ["*://betbck.com/*", "*://*.buckeye.com/*"]}
);
```

### What BetStamp PRO & SpotOdds Might Be Doing

1. **Direct API Partnership**: They have a formal agreement with Buckeye PPH
   - They get API keys/documents
   - Access to official endpoints
   - This is most likely

2. **Reverse Engineered API**: They figured out the endpoints
   - Intercepted network traffic (like we're doing)
   - Reverse engineered the authentication
   - Replicated the requests

3. **Browser Automation**: They use headless browsers
   - But this would be slow/rate-limited
   - Unlikely for "real-time"

### Next Steps

1. **✅ Do Method 1 (DevTools) FIRST** - It's the easiest
2. **Document everything you find** - URLs, payloads, responses
3. **Test the endpoints** - Try calling them directly
4. **Check for authentication** - Cookies, tokens, API keys

### Expected Findings

Based on typical PPH systems, Buckeye likely has:

1. **WebSocket Connection**: For real-time odds updates
   - `wss://betbck.com/ws` or similar
   - OR `wss://api.buckeye.com/...`

2. **REST API Endpoints**: For fetching odds
   - `/api/v1/odds/{game_id}`
   - `/api/events`
   - `/ajax/get_odds.php`

3. **Authentication**: 
   - Session cookies (which you already have)
   - OR API tokens (might need to request from Buckeye)

### If You Find the API

Once you identify the endpoint:

1. **Test with your session**:
   ```python
   import requests
   
   session = requests.Session()
   # Login first (get cookies)
   session.post('https://betbck.com/Qubic/SecurityPage.php', data={...})
   
   # Then call the API
   response = session.get('https://betbck.com/api/odds?game_id=12345')
   print(response.json())
   ```

2. **Check authentication requirements**
   - Session cookies might be enough
   - OR might need API key in headers
   - OR might need specific tokens

3. **Poll for updates**:
   - If it's a GET endpoint, poll every 1-5 seconds
   - If it's WebSocket, connect and listen for updates

### Contacting Buckeye PPH

If you can't find the API, consider:

1. **Email Buckeye PPH directly**
   - Ask about API access for odds data
   - Mention you're building an odds comparison tool
   - They might have affiliate/partner programs

2. **Check for developer documentation**
   - Look for `/api/docs`, `/developer`, `/integration`
   - Check for `api.buckeye.com` or `developer.buckeye.com`

3. **Ask BetStamp PRO / SpotOdds**
   - Reach out and ask how they get the data
   - They might share or you could partner

## Action Items

1. **✅ Right now**: Open betbck.com in Chrome, use DevTools Network tab, and capture what requests happen when odds update
2. **Document**: Save URLs, headers, payloads, responses
3. **Test**: Try calling those endpoints with your session
4. **Iterate**: Keep monitoring and testing

The API definitely exists - we just need to find it!

