// Enhanced Socket.IO interceptor that parses the odds updates
// Paste this into console BEFORE navigating to a live game

(function() {
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js';
  document.head.appendChild(script);
  script.onload = function() {
    const originalWebSocket = window.WebSocket;
    const messages = [];
    
    // Store the latest state to show readable updates
    let oddsState = {};
    
    function parsePath(path) {
      // Parse paths like /c/m/10/o/2/0
      // Returns: { market: 10, outcome: 2, index: 0 }
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
        // Price/decimal odds
        return `$${value.toFixed(2)} (${(value - 1).toFixed(2)}x)`;
      } else if (index === 1) {
        // Implied probability / US odds
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
              // Binary message - decompress and parse
              const bytes = new Uint8Array(event.data);
              const inflated = pako.inflate(bytes, { to: 'string' });
              const json = JSON.parse(inflated);
              
              if (json.isDiff && json.payload) {
                console.group('%c📦 ODDS UPDATE', 'font-size: 14px; font-weight: bold; color: #4CAF50');
                
                json.payload.forEach(op => {
                  if (op.op === 'replace' && op.path) {
                    const parsed = parsePath(op.path);
                    if (parsed) {
                      // Update state
                      const key = `${parsed.market}.${parsed.outcome}.${parsed.index}`;
                      oddsState[key] = op.value;
                      
                      // Log readable update
                      const oddsStr = formatOdds(op.value, parsed.index);
                      console.log(
                        `Market ${parsed.market}, Outcome ${parsed.outcome}, Index ${parsed.index}:`,
                        oddsStr
                      );
                    } else {
                      console.log('Path:', op.path, 'Value:', op.value);
                    }
                  }
                });
                
                if (json.ti && json.ti.t) {
                  const date = new Date(json.ti.t);
                  console.log(`⏰ Timestamp: ${date.toISOString()}`);
                }
                
                console.groupEnd();
              } else {
                console.log('📦 Other message:', json);
              }
              
              messages.push({
                type: 'binary',
                data: json,
                time: new Date().toISOString()
              });
              
            } else if (typeof event.data === 'string') {
              // Text message - event name (Socket.IO event identifier)
              console.log('📝 Event:', event.data);
              messages.push({
                type: 'text',
                data: event.data,
                time: new Date().toISOString()
              });
            }
          } catch (e) {
            console.error('❌ Error processing message:', e, event.data);
          }
        });
        
        ws.addEventListener('open', () => {
          console.log('✅ Connected to', url);
        });
        
        ws.addEventListener('close', () => {
          console.log('🔌 Disconnected from', url);
        });
      }
      
      return ws;
    };
    
    // Export functions
    window.exportSocketMessages = function() {
      const json = JSON.stringify(messages, null, 2);
      console.log('%c📋 EXPORT ALL MESSAGES:', 'font-size: 16px; color: blue; font-weight: bold');
      console.log(json);
      return messages;
    };
    
    window.getOddsState = function() {
      console.log('%c📊 CURRENT ODDS STATE:', 'font-size: 14px; font-weight: bold; color: #FF9800');
      console.table(oddsState);
      return oddsState;
    };
    
    window.clearOddsState = function() {
      oddsState = {};
      console.log('✅ Odds state cleared');
    };
    
    console.log('%c✅ Enhanced Socket.IO Interceptor Ready!', 'font-size: 16px; font-weight: bold; color: #4CAF50');
    console.log('   Commands:');
    console.log('   • window.exportSocketMessages() - Export all messages');
    console.log('   • window.getOddsState() - Show current odds state');
    console.log('   • window.clearOddsState() - Clear stored state');
    console.log('');
    console.log('   Now navigate to a live game and watch for updates!');
  };
})();

