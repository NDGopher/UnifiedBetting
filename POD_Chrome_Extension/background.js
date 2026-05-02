// pod_alert_extension/background.js
console.log("Background Service Worker v5 (Auto-Search Enabled) Loaded.");

let lastSniffedSwordfishEvent = {
    eventId: null,
    timestamp: 0,
    url: null // Store the URL for debugging
};

// Listener for the API call POD makes when an event's details are loaded (after a click)
chrome.webRequest.onCompleted.addListener(
  (details) => {
    if (details.url.includes("swordfish-production.up.railway.app/events/")) {
      const match = details.url.match(/events\/(\d+)/); // Extracts digits after /events/
      if (match && match[1]) {
        const capturedEventId = match[1];
        const capturedTimestamp = details.timeStamp; // Timestamp of the request completion

        // Update if it's a different event or a newer timestamp for the same event
        if (capturedEventId !== lastSniffedSwordfishEvent.eventId || capturedTimestamp > lastSniffedSwordfishEvent.timestamp) {
            lastSniffedSwordfishEvent.eventId = capturedEventId;
            lastSniffedSwordfishEvent.timestamp = capturedTimestamp;
            lastSniffedSwordfishEvent.url = details.url; // For logging
            console.log(
              `[BG_WebRequest] CAPTURED/UPDATED Swordfish eventId: ${lastSniffedSwordfishEvent.eventId} from URL: ${details.url} at ${new Date(lastSniffedSwordfishEvent.timestamp).toISOString()}`
            );
        }
      }
    }
  },
  { urls: ["https://swordfish-production.up.railway.app/events/*"] }
);

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("[Background] Message received:", message.type);

    if (message.type === "getLatestSniffedEventDetails") {
        console.log(`[Background] Responding to 'getLatestSniffedEventDetails'. Current: ID=${lastSniffedSwordfishEvent.eventId}, TS=${lastSniffedSwordfishEvent.timestamp}`);
        sendResponse({ 
            eventId: lastSniffedSwordfishEvent.eventId, 
            timestamp: lastSniffedSwordfishEvent.timestamp,
            url: lastSniffedSwordfishEvent.url 
        });
        return false; // Synchronous response

    } else if (message.type === "forwardToPython") {
        function getPythonServerUrl(callback) {
          chrome.storage.sync.get({ backendPort: '8000' }, function(items) {
            const port = items.backendPort || '8000';
            callback(`http://localhost:${port}/pod_alert`);
          });
        }
        
        getPythonServerUrl((url) => {
            const payload = message.payload;

            if (!payload || !payload.eventId) {
                console.error("[Background] 'forwardToPython' called BUT payload is missing 'eventId'. Payload:", payload);
                sendResponse({ status: "error", reason: "Missing eventId in payload for forwardToPython" });
                return true;
            }
            
            console.log(`[Background] Forwarding to Python for eventId: ${payload.eventId}.`);
            
            fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(response => {
                if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); }
                return response.json();
            })
            .then(data => {
                console.log("[Background] Python server response:", data);
                sendResponse({ status: data.status || "success", pythonResponse: data });
            })
            .catch(error => {
                console.error("[Background] Error POSTing to Python server:", error.message);
                sendResponse({ status: "error", reason: `Python POST failed: ${error.message}` });
            });
            return true; // Async
        });

    } else if (message.type === "autoSearchBetBCK") {
        console.log(`[Background] Received auto-search request for term: "${message.searchTerm}"`);
        if (!message.searchTerm) {
            console.error("[Background] Auto-search failed: No search term provided.");
            sendResponse({status: "error", reason: "No search term"});
            return true;
        }

        // 1. Open a new tab for BetBCK, making it the active tab
        chrome.tabs.create({ url: "https://betbck.com/Qubic/StraightSportSelection.php", active: true }, (newTab) => {
            
            // 2. We need to wait for the tab to finish loading before we can send a message to its content script.
            const listener = (tabId, info) => {
                if (tabId === newTab.id && info.status === 'complete') {
                    // This listener is no longer needed, so we remove it to prevent it from firing again.
                    chrome.tabs.onUpdated.removeListener(listener);

                    // 3. Send the search term to the content script (`betbck_auto_search.js`) in the new tab.
                    chrome.tabs.sendMessage(newTab.id, {
                        type: 'do_betbck_search',
                        searchTerm: message.searchTerm
                    }, (response) => {
                        if (chrome.runtime.lastError) {
                            console.error(`[Background] Error sending search message: ${chrome.runtime.lastError.message}`);
                            sendResponse({status: "error", reason: `Could not communicate with BetBCK tab: ${chrome.runtime.lastError.message}`});
                        } else {
                            console.log("[Background] Response from content script:", response);
                            sendResponse({status: "success", details: response});
                        }
                    });
                }
            };
            chrome.tabs.onUpdated.addListener(listener);
        });
        
        return true; // Indicate this is an asynchronous response
    }
    
    // Fallback for any unhandled message types
    return true; 
});