const BETBCK_BOARD = 'https://betbck.com/skin/sbsports.html?url=StraightSportSelection.php';
const SBSPORTS_QUERY = [
  '*://betbck.com/skin/sbsports.html*',
  '*://www.betbck.com/skin/sbsports.html*',
];

function isSbsportsUrl(url) {
  return typeof url === 'string' && /https?:\/\/(www\.)?betbck\.com\/skin\/sbsports\.html/i.test(url);
}

function injectHelper(tabId) {
  return new Promise((resolve) => {
    chrome.scripting.executeScript(
      { target: { tabId }, files: ['content.js'] },
      () => {
        if (chrome.runtime.lastError) {
          console.warn('[BetBCK Helper] inject skipped:', chrome.runtime.lastError.message);
        }
        resolve();
      }
    );
  });
}

function sendSearch(tabId, message) {
  chrome.tabs.sendMessage(tabId, {
    type: 'SEARCH_BETBCK',
    keyword: message.keyword,
    betInfo: message.betInfo || {},
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== 'FOCUS_BETBCK_TAB') return;
  chrome.tabs.query({ url: SBSPORTS_QUERY }, (tabs) => {
    const target = (tabs || [])[0];
    if (target) {
      chrome.tabs.update(target.id, { active: true }, () => {
        injectHelper(target.id).then(() => sendSearch(target.id, message));
      });
    } else {
      chrome.tabs.create({ url: BETBCK_BOARD }, (tab) => {
        const listener = (tabId, info, updated) => {
          if (tabId !== tab.id || info.status !== 'complete') return;
          const url = (updated && updated.url) || tab.url || '';
          if (!isSbsportsUrl(url)) return;
          chrome.tabs.onUpdated.removeListener(listener);
          injectHelper(tabId).then(() => sendSearch(tabId, message));
        };
        chrome.tabs.onUpdated.addListener(listener);
      });
    }
  });
  sendResponse({ status: 'ok' });
  return true;
});

// Overlay only after the sports board is already open. Never inject on /.
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== 'complete') return;
  if (!isSbsportsUrl(tab.url || '')) return;
  injectHelper(tabId);
});
