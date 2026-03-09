// This will intercept and decode Socket.IO messages in real-time
// Paste this into the browser console on plive.becoms.co

(async function() {
  // Load pako if needed
  if (!window.pako) {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js';
    document.head.appendChild(script);
    await new Promise(resolve => script.onload = resolve);
  }
  
  // Intercept WebSocket messages
  const originalWebSocket = window.WebSocket;
  const interceptedMessages = [];
  
  window.WebSocket = function(...args) {
    const ws = new originalWebSocket(...args);
    const url = args[0];
    
    // Only intercept pandora.ganchrow.com
    if (url && url.includes('pandora.ganchrow.com')) {
      console.log('🎯 Intercepted WebSocket:', url);
      
      ws.addEventListener('message', (event) => {
        try {
          // Socket.IO sends both text (event names) and binary (data)
          if (event.data instanceof ArrayBuffer) {
            // Binary message - decompress
            const bytes = new Uint8Array(event.data);
            const inflated = pako.inflate(bytes, { to: 'string' });
            const json = JSON.parse(inflated);
            
            console.log('📦 [BINARY MESSAGE]', json);
            interceptedMessages.push({
              type: 'binary',
              data: json,
              timestamp: new Date().toISOString()
            });
            
          } else if (typeof event.data === 'string') {
            // Text message - event nameId
            console.log('📝 [TEXT MESSAGE]', event.data);
            interceptedMessages.push({
              type: 'text',
              data: event.data,
              timestamp: new Date().toISOString()
            });
          }
        } catch (e) {
          console.error('❌ Error processing message:', e, event.data);
        }
      });
      
      ws.addEventListener('open', () => {
        console.log('✅ WebSocket connected to', url);
      });
    }
    
    return ws;
  };
  
  // Save intercepted messages
  window.getInterceptedSocketMessages = function() {
    return interceptedMessages;
  };
  
  // Export function
  window.exportSocketMessages = function() {
    const json = JSON.stringify(interceptedMessages, null, 2);
    console.log('%c📋 EXPORTED SOCKET MESSAGES:', 'color: #2196F3; font-weight: bold; font-size: 16px');
    console.log('%c' + '='.repeat(80), 'color: #2196F3');
    console.log(json);
    console.log('%c' + '='.repeat(80), 'color: #2196F3');
    console.log('%c💡 Copy the JSON above!', 'color: #4CAF50; font-weight: bold');
    return interceptedMessages;
  };
  
  console.log('✅ Socket.IO interceptor loaded!');
  console.log('   • Messages will be logged as they arrive');
  console.log('   • Run window.exportSocketMessages() to get all messages');
  console.log('   • Run window.getInterceptedSocketMessages() to get array');
})();

