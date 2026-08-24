// BetBCK Helper — Place Bet overlay. Loaded only on sbsports.html via background inject.
// Never wrap fetch/XHR/WebSocket. Never attach the debugger.
if (globalThis.__UB_BETBCK_HELPER__) {
  // already injected in this tab
} else {
globalThis.__UB_BETBCK_HELPER__ = true;

function isSportsBoard() {
  try {
    const href = location.href || '';
    return /sbsports\.html|StraightSportSelection\.php|PlayerGameSelection\.php/i.test(href);
  } catch {
    return false;
  }
}

function hasPasswordField() {
  return !!document.querySelector('input[type="password"], input[name="password"], input[name="Password"]');
}

function isLoginPage() {
  if (!isSportsBoard()) return true;
  if (hasPasswordField()) return true;
  try {
    const path = (location.pathname || '').replace(/\/+$/, '') || '/';
    if (path === '/' ) return true;
    if (/login|signin|authenticate|securitypage/i.test(path + location.search + location.href)) {
      return !isSportsBoard();
    }
  } catch {}
  return false;
}

if (window.top !== window.self) {
  console.log('[BetBCK Helper] iframe — idle');
} else if (isLoginPage()) {
  console.log('[BetBCK Helper] Login/non-board page — idle (no interceptor, no debugger)');
} else {
  console.log('[BetBCK Helper] Sports board — Place Bet helper ready');
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
  if (isLoginPage()) {
    console.warn('[BetBCK Helper] Ignoring Place Bet on login page. Log in first.');
    return;
  }
  if (message.type !== 'SEARCH_BETBCK') return;
  const keyword = message.keyword;
  const betInfo = message.betInfo || {};
  const searchInput = findSearchInput();
  const goButton = findSearchButton();
  if (!searchInput || !goButton) {
    console.log('[BetBCK Helper] Search box not found on sports board.');
    return;
  }
  searchInput.focus();
  searchInput.value = '';
  for (let i = 0; i < String(keyword || '').length; i++) {
    searchInput.value += keyword[i];
    await sleep(50 + Math.random() * 50);
  }
  searchInput.dispatchEvent(new Event('input', { bubbles: true }));
  await sleep(200);
  goButton.click();
  showBetPopup(betInfo, keyword);
}

let betPopup = null;
let pollInterval = null;
window.lastBetInfo = null;
window.lastKeyword = null;

function showBetPopup(betInfo, keyword) {
  if (!document.body) {
    setTimeout(() => showBetPopup(betInfo, keyword), 100);
    return;
  }
  window.lastBetInfo = betInfo;
  window.lastKeyword = keyword;
  if (betPopup) betPopup.remove();
  betPopup = document.createElement('div');
  betPopup.style.cssText = 'position:fixed;top:80px;right:40px;z-index:2147483647;background:#181c24;color:#fff;padding:18px 22px;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.25);min-width:260px;font-family:Inter,Roboto,Arial,sans-serif;cursor:move;user-select:none;';
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
  let isDragging = false, offsetX = 0, offsetY = 0;
  betPopup.addEventListener('mousedown', (e) => {
    isDragging = true;
    offsetX = e.clientX - betPopup.getBoundingClientRect().left;
    offsetY = e.clientY - betPopup.getBoundingClientRect().top;
  });
  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    betPopup.style.left = (e.clientX - offsetX) + 'px';
    betPopup.style.top = (e.clientY - offsetY) + 'px';
    betPopup.style.right = '';
  });
  document.addEventListener('mouseup', () => { isDragging = false; });
  document.getElementById('close-betbck-popup').onclick = () => {
    betPopup.remove();
    if (pollInterval) clearInterval(pollInterval);
  };
  if (betInfo.eventId) {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
      try {
        const res = await fetch('http://localhost:8000/get_active_events_data');
        const data = await res.json();
        const event = data[betInfo.eventId];
        if (event && event.markets && event.markets[0]) {
          document.getElementById('ev-value').textContent = event.markets[0].ev;
          document.getElementById('nvp-value').textContent = event.markets[0].pinnacle_nvp;
        }
      } catch (e) {}
    }, 3000);
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'SEARCH_BETBCK' || message.type === 'FOCUS_BETBCK_TAB') {
    handleBetbckAction(message);
  }
});

window.addEventListener('message', function (event) {
  if (event.source !== window) return;
  const message = event.data;
  if (message && message.type === 'FOCUS_BETBCK_TAB') {
    chrome.runtime.sendMessage({
      type: 'FOCUS_BETBCK_TAB',
      keyword: message.keyword,
      betInfo: message.betInfo || {},
    });
  }
});
}
