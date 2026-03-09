# BetBCK Extension - API Interceptor

## Installation

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select the `betbck_extension` folder
5. The extension should now be loaded!

## Usage

1. **Navigate to betbck.com** and login
2. **Open DevTools Console** (Press `F12` or `Ctrl+Shift+I`)
3. You should see: `🔍 BetBCK API Interceptor Initialized`
4. **Navigate to games or wait for odds to update**
5. Watch the console for intercepted requests

## Console Commands

### Export interesting requests (for copy-paste):
```javascript
window.exportInterceptedRequests()
```

This will output a formatted JSON object you can copy and paste.

### Export ALL requests:
```javascript
window.exportInterceptedRequests(false)
```

### Get requests as array:
```javascript
window.getInterestingRequests()  // Only interesting ones
window.getInterceptedRequests()  // All requests
```

## What to Look For

The interceptor will automatically highlight requests that contain:
- `api`, `ajax`, `json`, `odds`, `data`
- `buckeye`, `pph`
- WebSocket connections (`ws://`, `wss://`)
- Any response that looks like JSON

## Next Steps

1. Use the extension on betbck.com
2. Navigate to games with live odds
3. Wait for odds to update
4. Run `window.exportInterceptedRequests()` in console
5. Copy the output and analyze it to find the API endpoints!

