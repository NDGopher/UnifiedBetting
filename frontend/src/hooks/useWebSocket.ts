import { useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketHook {
  lastMessage: MessageEvent | null;
  sendMessage: (message: string) => void;
  isConnected: boolean;
  reconnectCount: number;
}

const SSE_URL = '/api/events/stream';
const WATCHDOG_MS = 45_000; // reconnect if no ping/message for 45s
const MAX_BACKOFF_MS = 15_000;

export const useWebSocket = (_url: string): WebSocketHook => {
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const esRef = useRef<EventSource | null>(null);
  const backoffRef = useRef(1000);
  const watchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedRef = useRef(false);

  const resetWatchdog = useCallback((connectFn: () => void) => {
    if (watchdogRef.current) clearTimeout(watchdogRef.current);
    watchdogRef.current = setTimeout(() => {
      // No ping/message in 45s — connection is silently dead, force reconnect
      console.warn('[SSE] Watchdog triggered — no activity, reconnecting...');
      esRef.current?.close();
      setIsConnected(false);
      connectFn();
    }, WATCHDOG_MS);
  }, []);

  useEffect(() => {
    closedRef.current = false;
    backoffRef.current = 1000;

    const connect = () => {
      if (closedRef.current) return;
      console.log(`[SSE] Connecting (backoff was ${backoffRef.current}ms)...`);
      const es = new EventSource(SSE_URL);
      esRef.current = es;

      es.onopen = () => {
        console.log('[SSE] Connected');
        setIsConnected(true);
        setReconnectCount(c => c + 1);
        backoffRef.current = 1000; // reset backoff on success
        resetWatchdog(connect);
      };

      es.onmessage = (event) => {
        resetWatchdog(connect); // any message resets the watchdog
        setLastMessage(event);
      };

      // Named ping events — reset watchdog, don't propagate to listeners
      es.addEventListener('ping', () => {
        resetWatchdog(connect);
      });

      es.onerror = () => {
        setIsConnected(false);
        es.close();
        if (watchdogRef.current) clearTimeout(watchdogRef.current);
        if (!closedRef.current) {
          const delay = backoffRef.current;
          backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
          console.warn(`[SSE] Error — retrying in ${delay}ms`);
          setTimeout(connect, delay);
        }
      };
    };

    connect();

    return () => {
      closedRef.current = true;
      if (watchdogRef.current) clearTimeout(watchdogRef.current);
      esRef.current?.close();
    };
  }, [resetWatchdog]);

  const sendMessage = useCallback((_message: string) => {
    // SSE is server→client only; no-op kept for interface compatibility
  }, []);

  return { lastMessage, sendMessage, isConnected, reconnectCount };
};
