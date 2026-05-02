const BACKEND_PORT = 8000;

const getBackendUrl = (): string => {
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host.includes('.replit.dev') || host.includes('.repl.co') || host.includes('.replit.app')) {
      const replId = host.split('.')[0];
      const domain = host.split('.').slice(1).join('.');
      return `https://${replId}-${BACKEND_PORT}.${domain}`;
    }
  }
  return `http://localhost:${BACKEND_PORT}`;
};

const getBackendWsUrl = (): string => {
  const httpUrl = getBackendUrl();
  return httpUrl.replace(/^https:\/\//, 'wss://').replace(/^http:\/\//, 'ws://');
};

export const API_BASE = getBackendUrl();
export const WS_BASE = getBackendWsUrl();
