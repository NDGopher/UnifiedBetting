// content.js
// Do not touch the new cloud/sbsports login splash — injecting fetch/XHR
// hooks there made the Login button unclickable on Chromium profiles.

function isBetbckLoginSplash() {
  try {
    const u = new URL(location.href);
    const path = u.pathname.replace(/\/+$/, '') || '/';
    if (/sbsports\.html|\/skin\/|\/cloud\/|StraightSport|PlayerGame/i.test(u.href)) {
      return false;
    }
    return path === '/' || /login/i.test(path + u.search);
  } catch {
    return false;
  }
}

(function() {
  if (isBetbckLoginSplash()) {
    console.log('[BetBCK Helper] Login splash — skipping API interceptor');
    return;
  }
  const script = document.createElement('script');
  script.src = chrome.runtime.getURL('api_interceptor.js');
  script.onload = function() {
    console.log('[BetBCK Helper] API interceptor injected successfully');
    this.remove();
  };
  script.onerror = function() {
    console.error('[BetBCK Helper] Failed to load API interceptor');
    this.remove();
  };
  const injectTarget = document.head || document.documentElement || document;
  if (injectTarget) {
    injectTarget.appendChild(script);
  } else {
    const checkAndInject = setInterval(() => {
      const target = document.head || document.documentElement || document;
      if (target) {
        target.appendChild(script);
        clearInterval(checkAndInject);
      }
    }, 10);
  }
})();

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

function isLoggedOut() {
  if (isBetbckLoginSplash()) return true;
  return !!document.querySelector('input[type="password"], input[name="password"]');
}

function findSearchInput() {
  return document.querySelector(
    'input.keyword_search_qubic#keyword_search[name="keyword_search"], input#keyword_search, input[name="keyword_search"], input[type="search"], input[placeholder*="search" i]'
  );
}

function findSearchButton() {
  return document.querySelector(
    'button[type="Submit"], button[type="submit"], input[name="action"][value="Search"], input[type="submit"][value="Search"], input[value="GO"], button.go'
  );
}

async function handleBetbckAction(message) {
  console.log('[BetBCK Helper][Content] handleBetbckAction called:', message);
  // Never auto-click Login on the new splash — that is what broke Chromium login.
  if (isLoggedOut()) {
    console.warn('[BetBCK Helper] Not logged in. Log in on the splash, then use Place Bet.');
    return;
  }
  if (message.type === 'SEARCH_BETBCK') {
    const keyword = message.keyword;
    const betInfo = message.betInfo || {};
    // Use the correct selectors for the search input and button
    const searchInput = findSearchInput();
    const goButton = findSearchButton();
    console.log('[BetBCK Helper][Content] Found search input:', searchInput);
    console.log('[BetBCK Helper][Content] Found GO button:', goButton);
    if (searchInput && goButton) {
      searchInput.focus();
      searchInput.value = '';
      // Simulate typing
      (async () => {
        for (let i = 0; i < keyword.length; i++) {
          searchInput.value += keyword[i];
          await sleep(50 + Math.random() * 50);
        }
        searchInput.dispatchEvent(new Event('input', { bubbles: true }));
        await sleep(200);
        // Click the GO button instead of submitting the form
        goButton.click();
        // Show the popup with bet info
        showBetPopup(betInfo, keyword);
      })();
    } else {
      console.log('[BetBCK Helper][Content] Could not find search input or GO button.');
    }
  } else if (message.type === 'FOCUS_BETBCK_TAB') {
    console.log('[BetBCK Helper][Content] Relaying FOCUS_BETBCK_TAB from window to background:', message);
    chrome.runtime.sendMessage({
      type: 'FOCUS_BETBCK_TAB',
      keyword: message.keyword,
      betInfo: message.betInfo || {}
    });
  }
}

let betPopup = null;
let pollInterval = null;
window.lastBetInfo = null;
window.lastKeyword = null;

function showBetPopup(betInfo, keyword) {
  // Only show if body exists
  if (!document.body) {
    setTimeout(() => showBetPopup(betInfo, keyword), 100);
    return;
  }
  
  console.log('[BetBCK Helper][Content] Injecting popup for bet:', betInfo, keyword);
  window.lastBetInfo = betInfo;
  window.lastKeyword = keyword;
  if (betPopup) betPopup.remove();
  betPopup = document.createElement('div');
  betPopup.style.position = 'fixed';
  betPopup.style.top = '80px';
  betPopup.style.right = '40px';
  betPopup.style.zIndex = 2147483647;
  betPopup.style.background = '#181c24';
  betPopup.style.color = '#fff';
  betPopup.style.padding = '18px 22px 18px 18px';
  betPopup.style.borderRadius = '12px';
  betPopup.style.boxShadow = '0 4px 24px rgba(0,0,0,0.25)';
  betPopup.style.minWidth = '260px';
  betPopup.style.fontFamily = 'Inter, Roboto, Arial, sans-serif';
  betPopup.style.cursor = 'move';
  betPopup.style.userSelect = 'none';
  betPopup.style.pointerEvents = 'auto';
  betPopup.innerHTML = `
    <div style="font-weight:700;font-size:1.1em;margin-bottom:6px;">BetBCK Helper</div>
    <div><b>Match:</b> ${betInfo.matchup || ''}</div>
    <div><b>Market:</b> ${betInfo.market || ''}</div>
    <div><b>Selection:</b> ${betInfo.selection || ''}</div>
    <div><b>Line:</b> ${betInfo.line || ''}</div>
    <div><b>Bet:</b> ${betInfo.betDescription || ''}</div>
    <div><b>EV:</b> <span id="ev-value">${betInfo.ev || ''}</span></div>
    <div><b>BetBCK Odds:</b> <span id="betbck-odds">${betInfo.betbck_odds || ''}</span></div>
    <div><b>NVP:</b> <span id="nvp-value">${betInfo.nvp || ''}</span></div>
    <button id="close-betbck-popup" style="margin-top:10px;padding:4px 12px;border:none;background:#ff6b35;color:#fff;border-radius:6px;cursor:pointer;">Close</button>
  `;
  document.body.appendChild(betPopup);
  // Drag logic
  let isDragging = false, offsetX = 0, offsetY = 0;
  betPopup.addEventListener('mousedown', (e) => {
    isDragging = true;
    offsetX = e.clientX - betPopup.getBoundingClientRect().left;
    offsetY = e.clientY - betPopup.getBoundingClientRect().top;
    betPopup.style.transition = 'none';
  });
  document.addEventListener('mousemove', (e) => {
    if (isDragging) {
      betPopup.style.left = (e.clientX - offsetX) + 'px';
      betPopup.style.top = (e.clientY - offsetY) + 'px';
      betPopup.style.right = '';
    }
  });
  document.addEventListener('mouseup', () => { isDragging = false; betPopup.style.transition = ''; });
  document.getElementById('close-betbck-popup').onclick = () => {
    betPopup.remove();
    if (pollInterval) clearInterval(pollInterval);
  };
  // Poll for real-time NVP/EV
  if (betInfo.eventId) {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
      try {
        const res = await fetch('http://localhost:8000/get_active_events_data');
        const data = await res.json();
        for (let eid in data) {
          if (eid === betInfo.eventId) {
            const event = data[eid];
            if (event && event.markets && event.markets.length > 0) {
              document.getElementById('ev-value').textContent = event.markets[0].ev;
              document.getElementById('nvp-value').textContent = event.markets[0].pinnacle_nvp;
            }
          }
        }
      } catch (e) { console.log('Polling error:', e); }
    }, 3000);
  }
}

// MutationObserver to re-inject popup if removed (wait for body to exist)
function setupMutationObserver() {
  if (document.body) {
    const observer = new MutationObserver(() => {
      if (window.lastBetInfo && betPopup && !document.body.contains(betPopup)) {
        showBetPopup(window.lastBetInfo, window.lastKeyword);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  } else {
    // Wait for body to be created
    setTimeout(setupMutationObserver, 100);
  }
}

// Wait for DOM to be ready before setting up MutationObserver
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupMutationObserver);
} else {
  setupMutationObserver();
}

// Add logging for debugging message flow
console.log('BetBCK Auto-Search content script loaded.');
chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
  console.log('[BetBCK Helper][Content] Received message:', message);
  if (message.type === 'SEARCH_BETBCK' || message.type === 'FOCUS_BETBCK_TAB') {
    handleBetbckAction(message);
  } else if (message.type === 'DBG_EVENT') {
    // Forward debugger network events into page context for the interceptor to record
    try {
      console.log('[BetBCK Helper][Content] Forwarding DBG_EVENT:', message.method);
      window.postMessage({ type: 'DBG_EVENT', payload: { method: message.method, params: message.params } }, '*');
    } catch (e) {
      console.warn('[BetBCK Helper][Content] Failed to post DBG_EVENT:', e);
    }
  }
});

// Expose a helper to start capture via console: window.startNetworkCapture()
window.startNetworkCapture = function() {
  chrome.runtime.sendMessage({ type: 'START_CAPTURE' }, (res) => {
    console.log('[BetBCK Helper] START_CAPTURE result:', res);
  });
};

// Listen for window.postMessage from the web app
window.addEventListener('message', function(event) {
  // Only accept messages from the same window
  if (event.source !== window) return;
  const message = event.data;
  // Allow page to request START_CAPTURE safely
  if (message && message.type === 'START_CAPTURE') {
    try {
      chrome.runtime.sendMessage({ type: 'START_CAPTURE' }, (res) => {
        console.log('[BetBCK Helper] START_CAPTURE via postMessage:', res);
      });
    } catch (e) {
      console.warn('[BetBCK Helper] Failed to relay START_CAPTURE:', e);
    }
    return;
  }
  if (message && message.type === 'FOCUS_BETBCK_TAB') {
    console.log('[BetBCK Helper][Content] Relaying FOCUS_BETBCK_TAB from window to background:', message);
    chrome.runtime.sendMessage({
      type: 'FOCUS_BETBCK_TAB',
      keyword: message.keyword,
      betInfo: message.betInfo || {}
    });
  }
});
