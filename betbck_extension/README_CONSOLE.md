# How to Decode Socket.IO Messages - Simple Steps

Just copy and paste these into your browser console!

---

## Step 1: Decode Your Binary Message (Do This First!)

1. Go to `plive.becoms.co` and open Console (F12)
2. Copy-paste this entire block and press Enter:

```javascript
(function() {
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js';
  document.head.appendChild(script);
  script.onload = function() {
    const b64 = `H4sIAAAAAAACA43Qz2rDMAwG8HfxuSSSLMtWznuLsYP/KKyQ0bKlg1Hy7nMOY+2pBZ9k/77P9tUdv16O8+ym9fNiB3fOP8spNze9Xt3p7Cb3aeclV3P71vreB2MdP0aE8TTSCH38nZeLuYkHwu3wDMJ/hAOmSCLPQH/bps+JuypgIHgECWOXTBribR/CEPgBDfvrhnDLZHhY+KfufwUk+bS9Hdx6dNPV7aezBUavxpkYivoQsTXQGLNmTpmCKDMjSYQ5NZPoSxIVyoStRuWev8x7EEgNrXCVIJ6LzaAhi1IsyWZVnwg1p+qpUNJi1rgUMFbiyNUKlh609ktG6SskTKC4bb8UucouSAIAAA==`;
    const bin = atob(b64.replace(/\s/g, ''));
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const inflated = pako.inflate(bytes, { to: 'string' });
    const json = JSON.parse(inflated);
    console.log('✅ DECODED ODDS DATA:');
    console.log(JSON.stringify(json, null, 2));
    window.lastDecodedOdds = json;
  };
})();
```

3. You should see the decoded JSON! 🎉

---

## Step 2: Intercept Live Messages with Parsing (RECOMMEND Evening)

1. **BEFORE** navigating to a live game, paste this (loads from `betbck_extension/intercept_and_parse.js`):

```javascript
(function() {
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js';
  document.head.appendChild(script);
  script.onload = function() {
    const originalWebSocket = window.WebSocket;
    const messages = [];
    let oddsState = {};
    
    function parsePath(path) {
      const parts = path.split('/').filter(p => p);
      if (parts.length >= 5 && parts[0] === 'c' && parts[1] === 'm' && parts[3] === 'o') {
        return {
          market: parseInt(parts[2]),
          outcome: parts[4],
          index: parts.length > 5 ? parseInt(parts[5]) : null,
          fullPath: path
        };
      }
      return null;
    }
    
    function formatOdds(value, index) {
      if (index === 0) {
        return `$${value.toFixed(2)} (${(value - 1).toFixed(2)}x)`;
      } else if (index === 1) {
        const usOdds = value > 1 ? `+${Math.round((value - 1) * 100)}` : `${Math.round((value - 1) * 100)}`;
        const prob = ((1 / value) * 100).toFixed(2);
        return `${usOdds} (${prob}% implied)`;
      }
      return value;
    }
    
    window.WebSocket = function(...args) {
      const ws = new originalWebSocket(...args);
      const url = args[0];
      
      if (url && url.includes('pandora.ganchrow.com')) {
        console.log('🎯 Intercepted WebSocket:', url);
        
        ws.addEventListener('message', (event) => {
          try {
            if (event.data instanceof ArrayBuffer) {
              const bytes = new Uint8Array(event.data);
              const inflated = pako.inflate(bytes, { to: 'string' });
              const json = JSON.parse(inflated);
              
              if (json.isDiff && json.payload) {
                console.group('%c📦 ODDS UPDATE', 'font-size: 14px; font-weight: bold; color: #4CAF50');
                json.payload.forEach(op => {
                  if (op.op === 'replace' && op.path) {
                    const parsed = parsePath(op.path);
                    if (parsed) {
                      const key = `${parsed.market}.${parsed.outcome}.${parsed.index}`;
                      oddsState[key] = op.value;
                      const oddsStr = formatOdds(op.value, parsed.index);
                      console.log(`Market ${parsed.market}, Outcome ${parsed.outcome}, Index ${parsed.index}:`, oddsStr);
                    } else {
                      console.log('Path:', op.path, 'Value:', op.value);
                    }
                  }
                });
                if (json.ti && json.ti.t) {
                  console.log(`⏰ ${new Date(json.ti.t).toISOString()}`);
                }
                console.groupEnd();
              } else {
                console.log('📦 Other:', json);
              }
              messages.push({type: 'binary', data: json, time: new Date().toISOString()});
            } else if (typeof event.data === 'string') {
              console.log('📝 Event:', event.data);
              messages.push({type: 'text', data: event.data, time: new Date().toISOString()});
            }
          } catch (e) {
            console.error('Error:', e);
          }
        });
        
        ws.addEventListener('open', () => console.log('✅ Connected'));
        ws.addEventListener('close', () => console.log('🔌 Disconnected'));
      }
      return ws;
    };
    
    window.exportSocketMessages = () => {
      const json = JSON.stringify(messages, null, 2);
      console.log('%c📋 EXPORT:', 'font-size: 16px; color: blue; font-weight: bold');
      console.log(json);
      return messages;
    };
    
    window.getOddsState = () => {
      console.table(oddsState);
      return oddsState;
    };
    
    console.log('✅ Enhanced interceptor ready! Navigate to a live game.');
  };
})();
```

2. Then **navigate to a live game** - you'll see formatted odds updates like:
   - `Market 10, Outcome 2, Index 0: $4.21 (3.21x)`
   - `Market 10, Outcome 2, Index 1: +187 (18.73% implied)`

3. Commands:
   - `window.exportSocketMessages()` - Get all raw messages
   - `window.getOddsState()` - Show current odds state as table

---

## Understanding the Data Structure

The decoded data uses **JSON Patch** format:
- `isDiff: true` = These are incremental updates (not full snapshots)
- `path` format: `/c/m/{market_id}/o/{outcome_id}/{index}`
  - Index 0 = Price/decimal odds (like 4.21 = $4.21 or +321 US)
  - Index 1 = Implied probability (like 1.187266 = -187 US or 84.2% implied)
- Example: `/c/m/10/o/2/0` = Market 10, Outcome 2, Price = 4.21
- Example: `/c/m/5/o/2.5/0` = Market 5, Outcome "2.5" (totals), Price = 6.09

---

That's it! Just copy-paste and press Enter! 🚀
