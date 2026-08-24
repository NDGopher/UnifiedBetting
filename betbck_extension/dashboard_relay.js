// Relays dashboard "Place Bet" postMessage to the extension background.
// This script only runs on localhost (the React/FastAPI dashboard), not on betbck.com.
window.addEventListener('message', function (event) {
  if (event.source !== window) return;
  const message = event.data;
  if (message && message.type === 'FOCUS_BETBCK_TAB') {
    chrome.runtime.sendMessage({
      type: 'FOCUS_BETBCK_TAB',
      keyword: message.keyword,
      betInfo: message.betInfo || {}
    });
  }
});
