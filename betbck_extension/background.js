const BETBCK_BOARD = 'https://betbck.com/skin/sbsports.html?url=StraightSportSelection.php';

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== 'FOCUS_BETBCK_TAB') return;
  chrome.tabs.query({ url: '*://betbck.com/*' }, (tabs) => {
    const board = (tabs || []).find((t) => /sbsports\.html/i.test(t.url || ''));
    const target = board || tabs[0];
    if (target) {
      chrome.tabs.update(target.id, { active: true }, () => {
        chrome.tabs.sendMessage(target.id, {
          type: 'SEARCH_BETBCK',
          keyword: message.keyword,
          betInfo: message.betInfo || {},
        });
      });
    } else {
      chrome.tabs.create({ url: BETBCK_BOARD }, (tab) => {
        const listener = (tabId, info) => {
          if (tabId === tab.id && info.status === 'complete') {
            chrome.tabs.onUpdated.removeListener(listener);
            chrome.tabs.sendMessage(tabId, {
              type: 'SEARCH_BETBCK',
              keyword: message.keyword,
              betInfo: message.betInfo || {},
            });
          }
        };
        chrome.tabs.onUpdated.addListener(listener);
      });
    }
  });
  sendResponse({ status: 'ok' });
  return true;
});
