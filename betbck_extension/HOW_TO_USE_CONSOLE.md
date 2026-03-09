# How to Decode and Intercept Socket.IO Messages

## Option 1: Decode the Binary Message You Already Have

1. **Open browser console** on `plive.becoms.co` (F12 → Console tab)
2. **Copy-paste this entire block:**

```javascript
// Load pako library
const script = document.createElement('script');
script.src = 'https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js';
document.head.appendChild(script);
script.onload = function() {
  // Your binary base64 string
  const b64 = `H4sIAAAAAAACA43Qz2rDMAwG8HfxuSSSLMtWznuLsYP/KKyQ0bKlg1Hy7nMOY+2pBZ9k/77P9tUdv16O8+ym9fNiB3fOP8spNze9Xt3p7Cb3aeclV3P71vreB2MdP0aE8TTSCH38nZeLuYkHwu3wDMJ/hAOmSCLPQH/bps+JuypgIHgECWOXTBribR/CEPgBDfvrhnDLZHhY+KfufwUk+bS9Hdx6dNPV7aezBUavxpkYivoQsTXQGLNmTpmCKuscaDMjSYQ5NZPoSxIVyoStRuWev8x7EEgNrXCVIJ6LzaAhi1IsyWZVnwg1p+qpUNJi1rgUMFbiyNUKlh609ktG6SskTKC4bb8UucouSAIAAA==`;
  
  // Decode
  const bin = atob(b64.replace(/\s/g, ''));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const inflated = pako.inflate(bytes, { to: 'string' });
  const json = JSON.parse(inflated);
  
  console.log('✅ DECODED:');
  console.log(JSON.stringify(json, null, 2));
  window.lastDecodedOdds = json;
};
```

3. **Press Enter** - you should see the decoded JSON

---

## Option 2: Intercept Live Socket.IO Messages

1. **Before navigating to a live game**, paste this in console:

```javascript
// Load pako
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
      console.log('🎯 Intercepted:', url);
      
      ws.addEventListener('message', (event) => {
        if (event.data instanceof ArrayBuffer) {
          const bytes = new Uint8Array(event.data);
          const inflated = pako.inflate(bytes, { to: 'string' });
          const json = JSON.parse(inflated);
          console.log('📦 ODDS UPDATE:', json);
          messages.push({type: 'binary', data: json, time: new Date().toISOString()});
        } else {
          console.log('📝 EVENT:', event.data);
          messages.push({type: 'text', data: event.data, time: new Date().toISOString()});
        }
      });
    }
    return ws;
  };
  
  window.exportSocketMessages = () => {
    const json = JSON.stringify(messages, null, 2);
    console.log('%c📋 EXPORT:', 'font-size: 16px; color: blue');
    console.log(json);
    return messages;
  };
  
  console.log('✅ Interceptor ready! Navigate to a live game.');
};
```

2. **Navigate to a live game** - you'll see messages in console
3. **Run `window.exportSocketMessages()`** to get all messages as JSON

---

## Option 3: Use the Files in This Directory

The files `decode_binary.js` and `intercept_socket.js` can be loaded directly if you prefer to save them locally and reference them.

