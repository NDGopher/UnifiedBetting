# How to Use the BetBCK Extension to Find the API

## Step 1: Load the Extension

1. Open Chrome
2. Go to `chrome://extensions/`
3. Enable **Developer mode** (toggle in top-right)
4. Click **Load unpacked**
5. Select the `betbck_extension` folder
6. ✅ Extension should now be active

## Step 2: Open betbck.com

1. Navigate to `https://betbck.com`
2. **Login to your account**
3. **Open DevTools Console**:
   - Press `F12` OR
   - Press `Ctrl+Shift+I` (Windows) OR
   - Press `Cmd+Option+I` (Mac)
   - Click the **Console** tab

4. You should see:
   ```
   🔍 BetBCK API Interceptor Initialized
   ✅ API Interceptor Ready!
   ```

## Step 3: Trigger Odds Updates

1. **Navigate to a game page** with odds displayed
2. **Wait for odds to update** (they may auto-refresh)
3. **OR manually refresh** the page
4. **OR navigate between different games/sports**

## Step 4: Watch the Console

As odds update, you'll see logs like:
```
🎯 [FETCH] GET /api/odds?game_id=12345
🎯 [XHR] POST /ajax/get_odds.php
🔌 [WEBSOCKET] Connection attempt: wss://...
📨 [WEBSOCKET] Message: {...}
```

## Step 5: Export the Data

After you've seen some interesting requests, run this in the console:

```javascript
window.exportInterceptedRequests()
```

This will output a formatted JSON object. **Copy everything between the `=====` lines**.

## Step 6: What to Look For

The interceptor automatically highlights requests containing:

### High Priority (Likely the API):
- ✅ URLs with `/api/` in the path
- ✅ URLs with `/ajax/` in the path  
- ✅ URLs with `buckeye` or `pph` in domain
- ✅ URLs with `odds`, `live`, or `realtime` in path
- ✅ WebSocket connections (`ws://` or `wss://`)
- ✅ Requests that return JSON responses

### Medium Priority:
- ✅ Requests with `.json` extension
- ✅ Requests with `callback=` parameter (JSONP)
- ✅ Requests with `/data/` in path
- ✅ POST requests (might be API calls)

### What to Copy:

From the export, look for these fields in each request:
1. **`url`** - The full endpoint URL
2. **`method`** - GET, POST, etc.
3. **`data`** - Any POST data or parameters
4. **`response`** - The actual response (likely JSON with odds)
5. **`headers`** - Request headers (might contain auth tokens)

## Step 7: Analyze the Output

Once you've copied the export, look for patterns:

1. **WebSocket connections** - These are for real-time updates!
2. **Repeating requests** - If you see the same URL called every few seconds, that's polling
3. **JSON responses with odds data** - These are the API endpoints we need!

## Example of What You Might Find:

```json
{
  "id": 1,
  "type": "FETCH",
  "method": "GET",
  "url": "https://betbck.com/api/v1/odds/live?game_id=12345",
  "response": {
    "game_id": "12345",
    "home_odds": "-110",
    "away_odds": "+105",
    "spread": "-3.5",
    "total": "45.5"
  }
}
```

## Troubleshooting

### Extension not loading?
- Check that `icon128.png` is removed from manifest.json (it's fixed now)
- Make sure all files are in the `betbck_extension` folder
- Reload the extension after fixing issues

### No requests showing?
- Make sure you're on betbck.com (not a different domain)
- Try navigating to different pages
- Check if odds actually update on the page
- Try refreshing the page

### Console shows errors?
- The extension will still work with some errors
- Check that the API interceptor loaded (you should see the green message)

## What to Do Once You Find the API

1. **Test the endpoint manually**:
   ```python
   import requests
   
   session = requests.Session()
   # Login first to get cookies
   session.post('https://betbck.com/Qubic/SecurityPage.php', data={...})
   
   # Test the API endpoint you found
   response = session.get('https://betbck.com/api/v1/odds/live?game_id=12345')
   print(response.json())
   ```

2. **Check authentication**:
   - Do you need session cookies? (Probably yes)
   - Do you need API keys? (Maybe)
   - Do you need special headers? (Check the headers in export)

3. **Build the real-time fetcher**:
   - If it's WebSocket, connect and listen
   - If it's polling, call it every 1-5 seconds
   - Cache results and only process changes

Good luck! 🎯

