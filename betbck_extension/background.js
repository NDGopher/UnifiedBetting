// background.js
// Track current captured tab for forwarding events
let currentCapturedTabId = null;
let workerCheckInterval = null;
let attachedWorkers = new Set();

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[BetBCK Helper][Background] Received message:', message);
  if (message.type === 'START_CAPTURE') {
    // Attach simply to the active tab's page
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
      const tab = tabs && tabs[0];
      if (!tab) return sendResponse({status:'error', message:'No active tab'});
      const pageTarget = { tabId: tab.id };
      currentCapturedTabId = tab.id;
      
      // If already attached, detach first (can only attach once)
      chrome.debugger.detach(pageTarget, () => {
        chrome.debugger.attach(pageTarget, '1.3', () => {
          if (chrome.runtime.lastError) {
            const err = chrome.runtime.lastError.message;
            console.warn('[BetBCK][Background] Page debugger attach error:', err);
            // Don't fail completely, try workers anyway
          } else {
            console.log('[BetBCK][Background] ✅ Attached to page:', tab.id);
            chrome.debugger.sendCommand(pageTarget, 'Network.enable', {}, () => {
              if (chrome.runtime.lastError) {
                console.warn('[BetBCK][Background] Network.enable error:', chrome.runtime.lastError.message);
              } else {
                console.log('[BetBCK][Background] ✅ Network.enable on page');
              }
            });
          }

          // Relay debugger events to the content script
          if (!chrome.debugger.onEvent.hasListener(onDebuggerEvent)) {
            chrome.debugger.onEvent.addListener(onDebuggerEvent);
            console.log('[BetBCK][Background] ✅ Debugger event listener attached');
          }

          // Start monitoring for workers periodically (they can be created after page load)
          if (workerCheckInterval) clearInterval(workerCheckInterval);
          attachedWorkers.clear();
          
          const attachToWorkers = () => {
            chrome.tabs.get(tab.id, (tinfo) => {
              if (chrome.runtime.lastError || !tinfo) return;
              let origin = null;
              try { origin = tinfo.url ? new URL(tinfo.url).origin : null; } catch {}
              
              chrome.debugger.getTargets((targets) => {
                if (chrome.runtime.lastError) {
                  console.warn('[BetBCK][Background] getTargets error:', chrome.runtime.lastError.message);
                  return;
                }
                const workers = (targets || []).filter(t => 
                  (t.type === 'worker' || t.type === 'shared_worker') && !attachedWorkers.has(t.id)
                );
                
                // Log all target types for debugging
                const targetTypes = {};
                (targets || []).forEach(t => {
                  targetTypes[t.type] = (targetTypes[t.type] || 0) + 1;
                });
                console.log(`[BetBCK][Background] Target breakdown:`, targetTypes);
                
                // Log all SharedWorkers specifically (these handle WebSocket connections)
                const sharedWorkers = targets.filter(t => t.type === 'shared_worker');
                if (sharedWorkers.length > 0) {
                  console.log(`[BetBCK][Background] SharedWorkers found:`, sharedWorkers.map(t => t.url));
                }
                
                console.log(`[BetBCK][Background] Found ${workers.length} new worker(s) (total targets: ${targets.length})`);
                
                workers.forEach(t => {
                  try {
                    // Allow cross-origin workers if from becoms.co domains
                    const tOrigin = t.url ? new URL(t.url).origin : '';
                    const allowed = !origin || tOrigin.includes('becoms.co') || tOrigin.includes('betbck.com') || t.url.startsWith(origin);
                    if (!allowed) {
                      console.log(`[BetBCK][Background] Skipping worker (origin mismatch): ${t.url}`);
                      return;
                    }
                    
                    console.log(`[BetBCK][Background] Attempting to attach to ${t.type}: ${t.url} (ID: ${t.id}, tabId: ${t.tabId || 'none'})`);
                    
                    attachedWorkers.add(t.id);
                    chrome.debugger.attach({ targetId: t.id }, '1.3', (err) => {
                      if (chrome.runtime.lastError) {
                        console.warn(`[BetBCK][Background] Worker attach error (${t.id}):`, chrome.runtime.lastError.message);
                        attachedWorkers.delete(t.id);
                      } else {
                        console.log(`[BetBCK][Background] ✅ Attached to worker: ${t.type} ${t.url} (targetId: ${t.id})`);
                        
                        // Enable Network domain
                        chrome.debugger.sendCommand({ targetId: t.id }, 'Network.enable', {}, () => {
                          if (chrome.runtime.lastError) {
                            console.warn(`[BetBCK][Background] Network.enable on worker error:`, chrome.runtime.lastError.message);
                          } else {
                            console.log(`[BetBCK][Background] ✅ Network.enable on worker ${t.id}`);
                          }
                        });
                        
                        // Also enable Runtime domain to see worker messages
                        chrome.debugger.sendCommand({ targetId: t.id }, 'Runtime.enable', {}, () => {
                          if (!chrome.runtime.lastError) {
                            console.log(`[BetBCK][Background] ✅ Runtime.enable on worker ${t.id}`);
                          }
                        });
                      }
                    });
                  } catch (e) {
                    console.error('[BetBCK][Background] Error processing worker:', e, t);
                  }
                });
              });
            });
          };
          
          // Check immediately and then every 2 seconds
          attachToWorkers();
          workerCheckInterval = setInterval(attachToWorkers, 2000);
          
          sendResponse({status:'ok', message: 'Debugger attached, monitoring for workers...'});
        });
      });
    });
    return true;
  }
  if (message.type === 'FOCUS_BETBCK_TAB') {
    chrome.tabs.query({ url: '*://betbck.com/*' }, (tabs) => {
      console.log('[BetBCK Helper][Background] Found BetBCK tabs:', tabs);
      if (tabs.length > 0) {
        chrome.tabs.update(tabs[0].id, { active: true }, () => {
          console.log('[BetBCK Helper][Background] Activated BetBCK tab:', tabs[0].id);
          chrome.tabs.sendMessage(tabs[0].id, {
            type: 'SEARCH_BETBCK',
            keyword: message.keyword,
            betInfo: message.betInfo || {}
          }, () => {
            console.log('[BetBCK Helper][Background] Sent SEARCH_BETBCK to content script.');
          });
        });
      } else {
        // Optionally open a new tab if not found
        chrome.tabs.create({ url: 'https://betbck.com' }, (tab) => {
          console.log('[BetBCK Helper][Background] Created new BetBCK tab:', tab.id);
          // Wait for tab to load, then send message
          chrome.tabs.onUpdated.addListener(function listener(tabId, info) {
            if (tabId === tab.id && info.status === 'complete') {
              chrome.tabs.onUpdated.removeListener(listener);
              chrome.tabs.sendMessage(tabId, {
                type: 'SEARCH_BETBCK',
                keyword: message.keyword,
                betInfo: message.betInfo || {}
              }, () => {
                console.log('[BetBCK Helper][Background] Sent SEARCH_BETBCK to new content script.');
              });
            }
          });
        });
      }
    });
    sendResponse({ status: 'ok' });
    return true;
  }
}); 

function onDebuggerEvent(source, method, params) {
  try {
    const tabId = source.tabId || currentCapturedTabId;
    const targetId = source.targetId;
    
    // Log ALL events for debugging (not just Network)
    console.log(`[BetBCK][Background] 🔔 Debugger event: ${method} (tab: ${tabId || 'none'}, target: ${targetId || 'none'})`);
    
    if (!tabId && !targetId) {
      // Still log it even if we can't route it
      console.warn('[BetBCK][Background] Event with no tabId or targetId:', method, source);
      return;
    }
    
    // Send to tab if we have tabId, otherwise try to find tab from targetId
    const sendToTab = (tid) => {
      if (!tid) return;
      chrome.tabs.sendMessage(tid, { type: 'DBG_EVENT', method, params }, (response) => {
        if (chrome.runtime.lastError) {
          // Ignore "Receiving end doesn't exist" - tab might not have loaded content script yet
          if (!chrome.runtime.lastError.message.includes("Receiving end doesn't exist")) {
            console.warn(`[BetBCK][Background] Failed to send to tab ${tid}:`, chrome.runtime.lastError.message);
          }
        } else {
          console.log(`[BetBCK][Background] ✅ Forwarded ${method} to tab ${tid}`);
        }
      });
    };
    
    if (tabId) {
      sendToTab(tabId);
    } else if (targetId) {
      // For worker targets (especially SharedWorkers which have no tabId), always use current captured tab
      if (currentCapturedTabId) {
        console.log(`[BetBCK][Background] Routing worker event ${method} (target: ${targetId}) to captured tab ${currentCapturedTabId}`);
        sendToTab(currentCapturedTabId);
      } else {
        // Last resort: try to find the parent tab
        chrome.debugger.getTargets((targets) => {
          const target = targets.find(t => t.id === targetId);
          if (target && target.tabId) {
            console.log(`[BetBCK][Background] Found parent tab ${target.tabId} for worker target ${targetId}`);
            sendToTab(target.tabId);
          } else {
            console.warn(`[BetBCK][Background] No tab found for target ${targetId}, method: ${method}`);
          }
        });
      }
    }
  } catch (e) {
    console.error('[BetBCK][Background] onDebuggerEvent error:', e, source, method);
  }
}