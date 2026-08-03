/**
 * Keep-alive utility for Chrome MV3 background service worker idle timer.
 * Chrome automatically stops service workers after 30 seconds of inactivity.
 * By maintaining a long-lived runtime port connection and regularly sending
 * ping messages between active content scripts and the service worker, we reset
 * Chrome's internal 30-second idle timer.
 */

export const KEEPALIVE_PORT_NAME = 'keep-alive';
export const KEEPALIVE_PING_KIND = 'keep-alive-ping';
export const KEEPALIVE_PONG_KIND = 'keep-alive-pong';

export interface KeepAlivePing {
  kind: typeof KEEPALIVE_PING_KIND;
}

export interface KeepAlivePong {
  kind: typeof KEEPALIVE_PONG_KIND;
}

/**
 * Establishes a long-lived runtime port connection to the service worker from an active content script.
 * Sends periodic ping messages every `intervalMs` milliseconds (default: 20 seconds).
 * Automatically reconnects if the port disconnects (e.g. during worker cycle).
 *
 * @param intervalMs Time between pings in ms (must be < 30000ms idle limit)
 * @returns A function to clean up timers and disconnect the port.
 */
export function setupKeepAliveClient(intervalMs = 20_000): () => void {
  let port: chrome.runtime.Port | null = null;
  let intervalId: ReturnType<typeof setInterval> | null = null;
  let isCleanedUp = false;

  function connect(): void {
    if (isCleanedUp) return;
    try {
      if (!chrome.runtime?.id) return;
      port = chrome.runtime.connect({ name: KEEPALIVE_PORT_NAME });

      intervalId = setInterval(() => {
        try {
          if (port) {
            port.postMessage({ kind: KEEPALIVE_PING_KIND } satisfies KeepAlivePing);
          }
        } catch {
          // If postMessage fails, port.onDisconnect will trigger cleanup/reconnect
        }
      }, intervalMs);

      port.onDisconnect.addListener(() => {
        if (intervalId !== null) {
          clearInterval(intervalId);
          intervalId = null;
        }
        port = null;
        if (!isCleanedUp && chrome.runtime?.id) {
          setTimeout(connect, 1_000);
        }
      });
    } catch {
      // Runtime context invalidated
    }
  }

  connect();

  return function disconnect(): void {
    isCleanedUp = true;
    if (intervalId !== null) {
      clearInterval(intervalId);
      intervalId = null;
    }
    if (port) {
      try {
        port.disconnect();
      } catch {
        // Ignore disconnect errors
      }
      port = null;
    }
  };
}

/**
 * Registers an onConnect listener in the background service worker to accept keep-alive ports.
 * Responds to ping messages to reset Chrome's 30-second service worker idle timer.
 *
 * @returns A function to unregister the listener.
 */
export function setupKeepAliveServer(): () => void {
  const onConnectListener = (port: chrome.runtime.Port): void => {
    if (port.name !== KEEPALIVE_PORT_NAME) return;

    const onMessageListener = (msg: unknown): void => {
      if (
        typeof msg === 'object' &&
        msg !== null &&
        (msg as { kind?: string }).kind === KEEPALIVE_PING_KIND
      ) {
        try {
          port.postMessage({ kind: KEEPALIVE_PONG_KIND } satisfies KeepAlivePong);
        } catch {
          // Port closed
        }
      }
    };

    port.onMessage.addListener(onMessageListener);
    port.onDisconnect.addListener(() => {
      try {
        port.onMessage.removeListener(onMessageListener);
      } catch {
        // Ignore
      }
    });
  };

  chrome.runtime.onConnect.addListener(onConnectListener);

  return function cleanup(): void {
    chrome.runtime.onConnect.removeListener(onConnectListener);
  };
}
