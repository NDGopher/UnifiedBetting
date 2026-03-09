# Simple Console Commands - Copy & Paste

## Step 1: Decode Your Binary Message (Do This First)

Copy-paste this **entire block** into the console on `plive.becoms.co`:

```javascript
(function() {
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js';
  document.head.appendChild(script);
  script.onload = function() {
    const b64 = `H4sIAAAAAAACA43Qz2rDMAwG8HfxuSSSLMtWznuLsYP/KKyQ0bKlg1Hy7nMOY+2pBZ9k/77P9tUdv16O8+ym9fNiB3fOP8spNze9Xt3p7Cb3aeclV3P71vreB2MdP0aE8TTSCH38nZeLuYkHwu3wDMJ/hAOmSCLPQH/bps+JuypgIHgECWOXTBribR/CEPgBDfvrhnDLZHhY+KfufwUk+bS9Hdx6dNPV7aezBUavxpkY translatorivoQsTXQGLNmTpmCKDMjSYQ5NZPoSxIVyoStRuWev8x7EEgNrXC!("VI了一口J6LzaAhi1IsyWZVnwg1p+qpUNJi1rgUMFbiyNUKlh609ktG6SskTKC4bb8UucouSAIAAA==不稳`;
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

Press Enter - you should see decoded JSON!

---

## Step 2: Intercept Live Messages (Do This to Capture Future Updates)

Copy-paste this **before navigating to a live game**:

```javascript
(function() {
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js';
  document.head.appendChild(script);
  script.onload = function() {
    const originalWebSocket = window.WebSocket;
    const messages = [];
    
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
              console.log('📦 ODDS UPDATE:', json);
              messages.push({type: 'binary', data: json, time: new Date().toISOString()});
            } else if (typeof event.data === 'string') {
              console.log('📝 EVENT NAME:', event.data);
              messages.push({type: 'text', data: event.data, time: new Date().toISOString()});
            }
          } catch (e) {
            console.error('Error:', e);
          }
        });
        
        ws.addEventListener('open', () => {
          console.log('✅ Connected to', url);
        });
      }
      
      return ws;
    };
    
    window.exportSocketMessages = function() {
      const json = JSON.stringify(messages, null, 2);
      console.log('%c📋 EXPORT MESSAGES:', 'font-size: 16px; color: blue; font-weight: bold');
      console.log(json);
      return messages;
    };
    
    console.log('✅ Socket interceptor ready! Navigate to a live game now.');
  };
})();
```

Then:
- Navigate to a live game
- Watch the console for `📦 ODDS UPDATE:` messages
- When done, run: `window.exportSocketMessages()` to get all messages

---

That's it! Just copy-paste and press Enter. 🚀

