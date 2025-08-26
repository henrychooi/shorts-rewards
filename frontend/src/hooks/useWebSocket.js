import { useState, useCallback } from 'react';

export const useWebSocket = (url) => {
  const [socket, setSocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(() => {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      reconnectAttempts.current = 0;
    };

    ws.onclose = () => {
      console.log('WebSocket closed');
      setIsConnected(false);
      
      // Attempt to reconnect
      if (reconnectAttempts.current < maxReconnectAttempts) {
        console.log(`Attempting to reconnect (${reconnectAttempts.current + 1}/${maxReconnectAttempts})`);
        reconnectAttempts.current += 1;
        setTimeout(connect, 1000 * Math.min(reconnectAttempts.current, 5));
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    setSocket(ws);
    return ws;
  }, [url]);

  const disconnect = useCallback(() => {
    if (socket) {
      socket.close();
    }
  }, [socket]);

  const sendMessage = useCallback((message) => {
    if (socket && isConnected) {
      socket.send(JSON.stringify(message));
    }
  }, [socket, isConnected]);

  return {
    socket,
    isConnected,
    connect,
    disconnect,
    sendMessage,
  };
};
