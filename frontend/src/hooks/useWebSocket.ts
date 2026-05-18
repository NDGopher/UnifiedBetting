import { useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketHook {
  lastMessage: MessageEvent | null;
  sendMessage: (message: string) => void;
  isConnected: boolean;
}

const SSE_URL = '/api/events/stream';

export const useWebSocket = (_url: string): WebSocketHook => {
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let closed = false;

    const connect = () => {
      if (closed) return;
      const es = new EventSource(SSE_URL);
      esRef.current = es;

      es.onopen = () => {
        console.log('[SSE] Connected');
        setIsConnected(true);
      };

      es.onmessage = (event) => {
        setLastMessage(event);
      };

      es.onerror = () => {
        setIsConnected(false);
        es.close();
        if (!closed) {
          setTimeout(connect, 1000);
        }
      };
    };

    connect();

    return () => {
      closed = true;
      esRef.current?.close();
    };
  }, []);

  const sendMessage = useCallback((_message: string) => {
    // SSE is server→client only; no-op kept for interface compatibility
  }, []);

  return { lastMessage, sendMessage, isConnected };
};
