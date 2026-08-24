// API Interceptor for BetBCK/Buckeye PPH
// Captures all network requests and formats output for easy copy-paste analysis

(function() {
    console.log('%c🔍 BetBCK API Interceptor Initialized', 'color: #4CAF50; font-weight: bold; font-size: 14px');
    
    const interceptedRequests = [];
    const maxLogs = 500;
    let requestCounter = 0;
    
    // Function to check if a request might be API-related
    function isInterestingRequest(url, response) {
        if (!url) return false;
        const urlLower = url.toLowerCase();
        const interestingPatterns = [
            'api', 'ajax', 'json', 'odds', 'data', 'buckeye', 'pph',
            'fetch', 'query', 'update', 'refresh', 'live', 'realtime',
            'ws://', 'wss://', '/ws/', '/socket', 'periods', 'game',
            'websocket', 'stream', 'event', 'push', 'subscribe'
        ];
        
        // Check URL - more lenient for plive.becoms.co
        if (interestingPatterns.some(pattern => urlLower.includes(pattern))) {
            return true;
        }
        
        // Check if URL is from plive.becoms.co domain (likely API calls)
        if (urlLower.includes('plive.becoms.co') || urlLower.includes('becoms.co')) {
            // Include most requests from this domain
            if (urlLower.includes('.php') || urlLower.includes('/api/') || urlLower.includes('/ajax/')) {
                return true;
            }
        }
        
        // Check if response looks like JSON/API response
        if (response) {
            if (typeof response === 'object') return true;
            if (typeof response === 'string') {
                const trimmed = response.trim();
                if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
                    return true;
                }
                // Also catch HTML responses that might contain odds data
                if (trimmed.includes('<table') && (trimmed.includes('odds') || trimmed.includes('bet'))) {
                    return true;
                }
            }
        }
        
        return false;
    }
    
    // Function to log requests with formatted output
    function logRequest(type, url, method, data, response, headers) {
        requestCounter++;
        const timestamp = new Date().toISOString();
        
        const logEntry = {
            id: requestCounter,
            timestamp: timestamp,
            type: type,
            method: method || 'GET',
            url: url,
            data: data,
            response: response,
            headers: headers || {}
        };
        
        interceptedRequests.push(logEntry);
        if (interceptedRequests.length > maxLogs) {
            interceptedRequests.shift();
        }
        
        // Always log to console, but format nicely
        const isInteresting = isInterestingRequest(url, response);
        
        if (isInteresting) {
            // Handle relative URLs safely
            let pathname = '';
            try {
                if (url.startsWith('http://') || url.startsWith('https://')) {
                    pathname = new URL(url).pathname;
                } else {
                    pathname = new URL(url, window.location.origin).pathname;
                }
            } catch (e) {
                pathname = url; // Use full URL if parsing fails
            }
            console.group(`%c🎯 [${type}] ${method || 'GET'} ${pathname}`, 'color: #FF9800; font-weight: bold');
            console.log('%cURL:', 'color: #2196F3; font-weight: bold', url);
            if (data) {
                console.log('%cData:', 'color: #9C27B0; font-weight: bold', typeof data === 'string' ? data : JSON.stringify(data, null, 2));
            }
            if (response) {
                try {
                    const formatted = typeof response === 'object' ? JSON.stringify(response, null, 2) : response;
                    console.log('%cResponse:', 'color: #4CAF50; font-weight: bold', formatted.substring(0, 1000));
                    if (formatted.length > 1000) {
                        console.log('%c... (truncated, see full in export)', 'color: #999; font-style: italic');
                    }
                } catch (e) {
                    console.log('%cResponse:', 'color: #4CAF50; font-weight: bold', String(response).substring(0, 500));
                }
            }
            console.groupEnd();
        }
    }
    
    // Intercept fetch
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = typeof args[0] === 'string' ? args[0] : args[0].url;
        const options = args[1] || {};
        const method = options.method || 'GET';
        
        return originalFetch.apply(this, args)
            .then(response => {
                const clonedResponse = response.clone();
                const contentType = response.headers.get('content-type') || '';
                
                // Get headers
                const headers = {};
                response.headers.forEach((value, key) => {
                    headers[key] = value;
                });
                
                // Try to parse response - capture more types
                if (contentType.includes('application/json') || url.toLowerCase().includes('.json')) {
                    clonedResponse.json()
                        .then(json => {
                            logRequest('FETCH', url, method, options.body, json, headers);
                        })
                        .catch(() => {
                            // Fall back to text if JSON parsing fails
                            clonedResponse.text()
                                .then(text => {
                                    logRequest('FETCH', url, method, options.body, text, headers);
                                });
                        });
                } else {
                    // Always try to get text for HTML/XML responses (might contain odds)
                    clonedResponse.text()
                        .then(text => {
                            logRequest('FETCH', url, method, options.body, text, headers);
                        })
                        .catch(() => {
                            logRequest('FETCH', url, method, options.body, null, headers);
                        });
                }
                
                return response;
            })
            .catch(error => {
                console.error('[FETCH ERROR]', url, error);
                return Promise.reject(error);
            });
    };
    
    // Intercept XMLHttpRequest
    const originalXHROpen = XMLHttpRequest.prototype.open;
    const originalXHRSend = XMLHttpRequest.prototype.send;
    
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        this._url = url;
        this._method = method;
        this._requestHeaders = {};
        return originalXHROpen.apply(this, [method, url, ...rest]);
    };
    
    // Intercept setRequestHeader to capture headers
    const originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
    XMLHttpRequest.prototype.setRequestHeader = function(header, value) {
        if (!this._requestHeaders) this._requestHeaders = {};
        this._requestHeaders[header] = value;
        return originalSetRequestHeader.apply(this, [header, value]);
    };
    
    XMLHttpRequest.prototype.send = function(...args) {
        const xhr = this;
        const url = xhr._url;
        const method = xhr._method;
        const data = args[0];
        
        xhr.addEventListener('load', function() {
            try {
                const contentType = xhr.getResponseHeader('content-type') || '';
                
                // Get response headers
                const headers = {};
                const headerStr = xhr.getAllResponseHeaders();
                if (headerStr) {
                    headerStr.split('\r\n').forEach(line => {
                        const parts = line.split(': ');
                        if (parts.length === 2) {
                            headers[parts[0]] = parts[1];
                        }
                    });
                }
                
                // Capture all XHR responses, especially from plive.becoms.co
                try {
                    if (contentType.includes('application/json') || url.toLowerCase().includes('.json')) {
                        try {
                            const json = JSON.parse(xhr.responseText);
                            logRequest('XHR', url, method, data, json, headers);
                        } catch {
                            // Not valid JSON, log as text
                            logRequest('XHR', url, method, data, xhr.responseText, headers);
                        }
                    } else {
                        // Always log HTML/XML/text responses (might contain odds in HTML)
                        logRequest('XHR', url, method, data, xhr.responseText, headers);
                    }
                } catch (e) {
                    // Log even if there's an error
                    logRequest('XHR', url, method, data, `[Error: ${e.message}]`, headers);
                }
            } catch (e) {
                logRequest('XHR', url, method, data, xhr.responseText, {});
            }
        });
        
        xhr.addEventListener('error', function() {
            console.error('[XHR ERROR]', method, url);
        });
        
        return originalXHRSend.apply(this, args);
    };
    
    // Intercept WebSocket
    const originalWebSocket = window.WebSocket;
    window.WebSocket = function(url, protocols) {
        console.group(`%c🔌 [WEBSOCKET] Connection: ${url}`, 'color: #9C27B0; font-weight: bold');
        console.log('Protocols:', protocols);
        console.groupEnd();
        
        const ws = new originalWebSocket(url, protocols);
        
        ws.addEventListener('open', () => {
            console.log(`%c✅ [WEBSOCKET] Connected: ${url}`, 'color: #4CAF50; font-weight: bold');
            logRequest('WEBSOCKET', url, 'CONNECT', null, { status: 'connected' }, {});
        });
        
        // Intercept send() to record outbound messages (useful for socket.io handshakes)
        const originalSend = ws.send;
        ws.send = function(data) {
            try {
                let parsed = null;
                if (typeof data === 'string') {
                    try { parsed = JSON.parse(data); } catch { /* not json */ }
                }
                logRequest('WEBSOCKET', url, 'SEND', null, parsed ?? String(data), {});
            } catch {}
            return originalSend.apply(ws, arguments);
        };

        ws.addEventListener('message', (event) => {
            try {
                const data = JSON.parse(event.data);
                console.group(`%c📨 [WEBSOCKET] Message from ${url}`, 'color: #FF9800; font-weight: bold');
                console.log(JSON.stringify(data, null, 2).substring(0, 1000));
                console.groupEnd();
                logRequest('WEBSOCKET', url, 'MESSAGE', null, data, {});
            } catch {
                console.log(`%c📨 [WEBSOCKET] Message (text): ${url}`, 'color: #FF9800', event.data.substring(0, 200));
                logRequest('WEBSOCKET', url, 'MESSAGE', null, event.data, {});
            }
        });
        
        ws.addEventListener('error', (error) => {
            console.error(`%c❌ [WEBSOCKET] Error: ${url}`, 'color: #F44336', error);
        });
        
        ws.addEventListener('close', () => {
            console.log(`%c🔌 [WEBSOCKET] Closed: ${url}`, 'color: #999');
        });
        
        return ws;
    };

    // Intercept EventSource (Server-Sent Events)
    if ('EventSource' in window) {
        const OriginalEventSource = window.EventSource;
        window.EventSource = function(url, config) {
            try { logRequest('SSE', url, 'CONNECT', null, { status: 'connected' }, {}); } catch {}
            const es = new OriginalEventSource(url, config);
            es.addEventListener('message', (evt) => {
                try {
                    const maybeJson = (() => { try { return JSON.parse(evt.data); } catch { return null; } })();
                    logRequest('SSE', url, 'MESSAGE', null, maybeJson ?? evt.data, {});
                } catch {}
            });
            es.addEventListener('error', (e) => {
                try { logRequest('SSE', url, 'ERROR', null, String(e), {}); } catch {}
            });
            return es;
        };
    }

    // Intercept navigator.sendBeacon (sometimes used for lightweight telemetry/push)
    if (navigator && typeof navigator.sendBeacon === 'function') {
        const originalBeacon = navigator.sendBeacon.bind(navigator);
        navigator.sendBeacon = function(url, data) {
            try { logRequest('BEACON', url, 'SEND', null, (typeof data === 'string' ? data : '[binary]'), {}); } catch {}
            return originalBeacon(url, data);
        };
    }

    // Convenience: Summaries to quickly see endpoints without scrolling logs
    window.exportNetworkSummary = function() {
        const reqs = window.getInterceptedRequests();
        const origins = [...new Set(reqs.map(r => { try { return new URL(r.url, location.origin).origin } catch { return null } }).filter(Boolean))];
        const websockets = reqs.filter(r => r.type === 'WEBSOCKET').map(r => r.url);
        const sse = reqs.filter(r => r.type === 'SSE').map(r => r.url);
        const ajaxPhp = reqs.filter(r => /\.php(\?|$)/i.test(r.url || '')).map(r => r.url);
        const polling = reqs.filter(r => /socket\.io|engine\.io|transport=polling/i.test(r.url || '')).map(r => r.url);
        const jsonApis = reqs.filter(r => /\/api\//i.test(r.url || '') || /\.json(\?|$)/i.test(r.url || '')).map(r => r.url);
        const out = { origins, websockets, sse, polling, ajaxPhp, jsonApis };
        console.log('[NetworkSummary]', out);
        return out;
    };
    
    // Export function - formats output for copy-paste
    window.exportInterceptedRequests = function(filterInteresting = true) {
        let requests = interceptedRequests;
        
        if (filterInteresting) {
            requests = requests.filter(req => isInterestingRequest(req.url, req.response));
        }
        
        const output = {
            summary: {
                total_requests: interceptedRequests.length,
                interesting_requests: requests.length,
                timestamp: new Date().toISOString()
            },
            requests: requests.map(req => ({
                id: req.id,
                timestamp: req.timestamp,
                type: req.type,
                method: req.method,
                url: req.url,
                data: req.data,
                response: typeof req.response === 'object' ? req.response : 
                         (req.response ? String(req.response).substring(0, 5000) : null),
                headers: req.headers
            }))
        };
        
        const jsonStr = JSON.stringify(output, null, 2);
        
        console.log('%c📋 EXPORTED REQUESTS FOR COPY-PASTE:', 'color: #2196F3; font-weight: bold; font-size: 16px');
        console.log('%c' + '='.repeat(80), 'color: #2196F3');
        console.log(jsonStr);
        console.log('%c' + '='.repeat(80), 'color: #2196F3');
        console.log('%c💡 Copy the JSON above and paste it to analyze!', 'color: #4CAF50; font-weight: bold');
        
        return output;
    };
    
    // Get all requests (no formatting)
    window.getInterceptedRequests = function() {
        return interceptedRequests;
    };
    
    // Get only interesting requests
    window.getInterestingRequests = function() {
        return interceptedRequests.filter(req => isInterestingRequest(req.url, req.response));
    };
    
    // Status update
    setInterval(() => {
        const interesting = interceptedRequests.filter(req => isInterestingRequest(req.url, req.response));
        if (interceptedRequests.length > 0) {
            console.log(
                `%c📊 [STATUS] ${interceptedRequests.length} total requests, ${interesting.length} potentially interesting`,
                'color: #999; font-style: italic'
            );
            console.log('%c💾 Commands:', 'color: #999; font-style: italic');
            console.log('%c   window.exportInterceptedRequests() - Export all interesting requests', 'color: #999');
            console.log('%c   window.exportInterceptedRequests(false) - Export ALL requests', 'color: #999');
            console.log('%c   window.getInterestingRequests() - Get interesting requests (array)', 'color: #999');
        }
    }, 30000);
    
    console.log('%c✅ API Interceptor Ready!', 'color: #4CAF50; font-weight: bold; font-size: 14px');
    console.log('%c📋 Commands available:', 'color: #2196F3; font-weight: bold');
    console.log('   • window.exportInterceptedRequests() - Export interesting requests for copy-paste');
    console.log('   • window.exportInterceptedRequests(false) - Export ALL requests');
    console.log('   • window.getInterestingRequests() - Get array of interesting requests');
    console.log('   • window.getInterceptedRequests() - Get all requests');
    console.log('');
    console.log('%c🔍 Monitoring network traffic... Navigate to games and watch for odds updates!', 'color: #FF9800; font-weight: bold');
    
    // Listen for forwarded Chrome Debugger events from content script and record them
    const wsRequestIdToUrl = {};
    window.addEventListener('message', (evt) => {
        const msg = evt.data;
        if (!msg || msg.type !== 'DBG_EVENT' || !msg.payload) return;
        const { method, params } = msg.payload;
        try {
            console.log('[API-Interceptor] 📡 DBG_EVENT received:', method, params ? Object.keys(params) : 'no params');
            
            if (method === 'Network.webSocketCreated') {
                const url = params.url || '(no-ws-url)';
                const reqId = params.requestId || 'unknown';
                wsRequestIdToUrl[reqId] = url;
                console.log(`%c🔌 [WEBSOCKET-CREATE] ${url} (ID: ${reqId})`, 'color: #9C27B0; font-weight: bold');
                logRequest('WEBSOCKET', url, 'CREATE', null, { status: 'created', requestId: reqId }, {});
            } else if (method === 'Network.webSocketFrameReceived') {
                const reqId = params.requestId || 'unknown';
                const url = wsRequestIdToUrl[reqId] || '(unknown-ws)';
                const frame = params.response;
                const payload = frame && frame.payloadData !== undefined ? frame.payloadData : (frame && frame.opcode ? `[opcode:${frame.opcode}]` : null);
                console.log(`%c📨 [WEBSOCKET-MSG-RECV] ${url}`, 'color: #FF9800; font-weight: bold', payload ? String(payload).substring(0, 200) : 'no payload');
                let parsed = null;
                if (typeof payload === 'string') { 
                    try { parsed = JSON.parse(payload); } catch {} 
                }
                logRequest('WEBSOCKET', url, 'MESSAGE', null, parsed ?? String(payload || ''), { requestId: reqId });
            } else if (method === 'Network.webSocketFrameSent') {
                const reqId = params.requestId || 'unknown';
                const url = wsRequestIdToUrl[reqId] || '(unknown-ws)';
                const frame = params.response;
                const payload = frame && frame.payloadData !== undefined ? frame.payloadData : (frame && frame.opcode ? `[opcode:${frame.opcode}]` : null);
                console.log(`%c📤 [WEBSOCKET-MSG-SENT] ${url}`, 'color: #9C27B0', payload ? String(payload).substring(0, 200) : 'no payload');
                let parsed = null;
                if (typeof payload === 'string') { 
                    try { parsed = JSON.parse(payload); } catch {} 
                }
                logRequest('WEBSOCKET', url, 'SEND', null, parsed ?? String(payload || ''), { requestId: reqId });
            } else if (method === 'Network.requestWillBeSent') {
                const u = params.request && params.request.url;
                const m = params.request && params.request.method;
                if (u) {
                    console.log(`%c🌐 [REQUEST] ${m || 'GET'} ${u}`, 'color: #2196F3');
                    logRequest('XHR', u, m || 'GET', params.request.postData || null, null, params.request.headers || {});
                }
            } else if (method === 'Network.responseReceived') {
                const u = params.response && params.response.url;
                if (u) {
                    console.log(`%c✅ [RESPONSE] ${u}`, 'color: #4CAF50');
                    logRequest('XHR', u, 'GET', null, '[Response body - use DevTools Network tab for details]', params.response.headers || {});
                }
            } else {
                console.log(`[API-Interceptor] Other network event: ${method}`, params);
            }
        } catch (e) {
            console.error('[DBG_EVENT Handler] error:', e, method, params);
        }
    });
})();
