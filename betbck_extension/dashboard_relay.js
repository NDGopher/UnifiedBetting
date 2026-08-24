// Relays dashboard "Place Bet" postMessage to the extension background.
if (!/^https?:\/\/(localhost|127\.0\.0\.1):(8000|5000)\b/i.test(location.origin || '')) {
  // never run on betbck.com
} else {
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
}
