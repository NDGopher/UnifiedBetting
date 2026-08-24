const BETBCK_BOARD = 'https://betbck.com/skin/sbsports.html?url=StraightSportSelection.php';
const SBSPORTS_QUERY = [
  '*://betbck.com/skin/sbsports.html*',
  '*://www.betbck.com/skin/sbsports.html*',
];

function isSbsportsUrl(url) {
  return typeof url === 'string' && /https?:\/\/(www\.)?betbck\.com\/skin\/sbsports\.html/i.test(url);
}

function pageIsLoggedInSportsBoard() {
  const host = (location.hostname || '').replace(/^www\./i, '').toLowerCase();
  if (host !== 'betbck.com') return false;
  if (!/\/skin\/sbsports\.html/i.test(location.href || '')) return false;
  if (document.querySelector('input[type="password"], input[name="Password"], button[data-action="login"]')) {
    return false;
  }
  return true;
}

function injectHelper(tabId, tabUrl) {
  return new Promise((resolve) => {
    if (!isSbsportsUrl(tabUrl || '')) {
      resolve(false);
      return;
    }
    chrome.scripting.executeScript(
      { target: { tabId }, func: pageIsLoggedInSportsBoard },
      (results) => {
        if (chrome.runtime.lastError || !results || !results[0] || !results[0].result) {
          resolve(false);
          return;
        }
        chrome.scripting.executeScript(
          { target: { tabId }, files: ['content.js'] },
          () => {
            if (chrome.runtime.lastError) {
              console.warn('[BetBCK Helper] inject skipped:', chrome.runtime.lastError.message);
              resolve(false);
              return;
            }
            resolve(true);
          }
        );
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
    const loggedIn = (tabs || []).find((t) => isSbsportsUrl(t.url || ''));
    if (loggedIn) {
      chrome.tabs.update(loggedIn.id, { active: true }, () => {
        injectHelper(loggedIn.id, loggedIn.url).then((ok) => {
          if (ok) sendSearch(loggedIn.id, message);
        });
      });
    } else {
      chrome.tabs.create({ url: BETBCK_BOARD }, (tab) => {
        const listener = (tabId, info, updated) => {
          if (tabId !== tab.id || info.status !== 'complete') return;
          const url = (updated && updated.url) || tab.url || '';
          if (!isSbsportsUrl(url)) return;
          chrome.tabs.onUpdated.removeListener(listener);
          injectHelper(tabId, url).then((ok) => {
            if (ok) sendSearch(tabId, message);
          });
        };
        chrome.tabs.onUpdated.addListener(listener);
      });
    }
  });
  sendResponse({ status: 'ok' });
  return true;
});
