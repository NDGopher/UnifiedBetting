// All HTTP API requests use relative paths — they go through the React dev-server
// proxy (setupProxy.js) which forwards them to http://localhost:8000.
// WebSocket needs a full wss:// URL, so we derive it from window.location.

export const API_BASE = '';

const getWsBase = (): string => {
  if (typeof window === 'undefined') return 'ws://localhost:8000';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}`;
};

export const WS_BASE = getWsBase();
