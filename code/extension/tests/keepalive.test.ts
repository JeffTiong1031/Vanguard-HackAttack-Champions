// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  setupKeepAliveClient,
  setupKeepAliveServer,
  KEEPALIVE_PORT_NAME,
  KEEPALIVE_PING_KIND,
  KEEPALIVE_PONG_KIND,
} from '../src/util/keepalive';

describe('keepalive module', () => {
  let onConnectListeners: Array<(port: any) => void> = [];
  let connectedPorts: any[] = [];

  beforeEach(() => {
    vi.useFakeTimers();
    onConnectListeners = [];
    connectedPorts = [];

    vi.stubGlobal('chrome', {
      runtime: {
        id: 'test-extension-id',
        onConnect: {
          addListener: vi.fn((listener: (port: any) => void) => {
            onConnectListeners.push(listener);
          }),
          removeListener: vi.fn((listener: (port: any) => void) => {
            onConnectListeners = onConnectListeners.filter((l) => l !== listener);
          }),
        },
        connect: vi.fn(({ name }: { name: string }) => {
          const messageListeners: Array<(msg: any) => void> = [];
          const disconnectListeners: Array<() => void> = [];

          const port = {
            name,
            postMessage: vi.fn((msg: any) => {
              // Simulate server/client message relaying if connected
            }),
            disconnect: vi.fn(() => {
              disconnectListeners.forEach((l) => l());
            }),
            onMessage: {
              addListener: vi.fn((listener: (msg: any) => void) => {
                messageListeners.push(listener);
              }),
              removeListener: vi.fn((listener: (msg: any) => void) => {
                const idx = messageListeners.indexOf(listener);
                if (idx !== -1) messageListeners.splice(idx, 1);
              }),
            },
            onDisconnect: {
              addListener: vi.fn((listener: () => void) => {
                disconnectListeners.push(listener);
              }),
            },
            _triggerMessage: (msg: any) => {
              messageListeners.forEach((l) => l(msg));
            },
            _triggerDisconnect: () => {
              disconnectListeners.forEach((l) => l());
            },
          };

          connectedPorts.push(port);

          // Notify server onConnect listeners
          onConnectListeners.forEach((listener) => listener(port));

          return port;
        }),
      },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('setupKeepAliveServer', () => {
    it('registers onConnect listener and replies PONG to PING on keep-alive port', () => {
      const cleanupServer = setupKeepAliveServer();
      expect(onConnectListeners.length).toBe(1);

      // Connect a port named keep-alive
      const clientPort = chrome.runtime.connect({ name: KEEPALIVE_PORT_NAME });
      expect(connectedPorts.length).toBe(1);

      // Simulate sending ping from client to server
      clientPort._triggerMessage({ kind: KEEPALIVE_PING_KIND });

      // Server should post PONG back
      expect(clientPort.postMessage).toHaveBeenCalledWith({ kind: KEEPALIVE_PONG_KIND });

      cleanupServer();
      expect(onConnectListeners.length).toBe(0);
    });

    it('ignores ports with different names', () => {
      setupKeepAliveServer();

      const otherPort = chrome.runtime.connect({ name: 'other-channel' });
      otherPort._triggerMessage({ kind: KEEPALIVE_PING_KIND });

      expect(otherPort.postMessage).not.toHaveBeenCalled();
    });
  });

  describe('setupKeepAliveClient', () => {
    it('establishes runtime port connection and sends periodic ping every 20s', () => {
      setupKeepAliveServer();
      const cleanupClient = setupKeepAliveClient(20_000);

      expect(chrome.runtime.connect).toHaveBeenCalledWith({ name: KEEPALIVE_PORT_NAME });
      const clientPort = connectedPorts[0];

      // Fast forward 20 seconds
      vi.advanceTimersByTime(20_000);
      expect(clientPort.postMessage).toHaveBeenLastCalledWith({ kind: KEEPALIVE_PING_KIND });

      // Fast forward another 20 seconds
      vi.advanceTimersByTime(20_000);
      expect(clientPort.postMessage).toHaveBeenCalledTimes(2);

      cleanupClient();
    });

    it('handles cleanup correctly', () => {
      const cleanupClient = setupKeepAliveClient(20_000);
      const clientPort = connectedPorts[0];

      cleanupClient();
      vi.advanceTimersByTime(40_000);

      // No pings should be sent after cleanup
      expect(clientPort.postMessage).not.toHaveBeenCalled();
    });

    it('attempts reconnection when disconnected', () => {
      setupKeepAliveClient(20_000);
      expect(chrome.runtime.connect).toHaveBeenCalledTimes(1);

      const firstPort = connectedPorts[0];
      firstPort._triggerDisconnect();

      // Fast forward 1 second (reconnect delay)
      vi.advanceTimersByTime(1000);
      expect(chrome.runtime.connect).toHaveBeenCalledTimes(2);
    });
  });
});
