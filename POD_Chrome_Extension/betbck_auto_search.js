// pod_alert_extension/betbck_auto_search.js
console.log("BetBCK Auto-Search script loaded.");

// Configurable backend port for posting alerts
let BACKEND_PORT = 8000;
chrome.storage.sync.get({ backendPort: '8000' }, function(items) {
  BACKEND_PORT = parseInt(items.backendPort, 10);
});
let BACKEND_URL = `http://localhost:${BACKEND_PORT}/pod_alert`;

function sendPodAlertToBackend(alertData) {
    fetch(BACKEND_URL, {
        method: 'POST',
        body: JSON.stringify(alertData),
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => {
        if (!res.ok) throw new Error('POST failed: ' + res.status);
        console.log('[ALERT POST] Success:', alertData);
        return res.json();
    })
    .then(data => {
        if (data && data.status !== 'success') {
            console.warn('[ALERT POST] Server responded with error:', data);
        }
    })
    .catch(err => {
        console.error('[ALERT POST] Failed:', err, alertData);
    });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'do_betbck_search') {
        console.log("Search term received by content script:", request.searchTerm);
        
        // Give the page a moment to ensure all elements are loaded
        setTimeout(() => {
            const searchInput = document.querySelector('input[name="keyword_search"]');
            const searchButton = document.querySelector('input[name="action"][value="Search"]');

            if (searchInput && searchButton) {
                console.log("Found search input and button.");
                searchInput.value = request.searchTerm;
                searchButton.click();
                sendResponse({status: "Search initiated"});
            } else {
                console.error("Could not find the search input or button on BetBCK page.");
                sendResponse({status: "Error: Search elements not found"});
            }
        }, 500); // 0.5-second delay

        // Return true to indicate you wish to send a response asynchronously
        return true;
    }
});