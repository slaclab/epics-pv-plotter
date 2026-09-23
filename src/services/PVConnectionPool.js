import { PVWebSocket } from "./WebSocketManager";
import { useLiveValueStore } from "../stores/useLiveValueStore";

class PVConnectionPool {
  constructor() {
    this.pool = new Map();
  }

  subscribe(pvName, callbacks) {
    let entry = this.pool.get(pvName);

    if (!entry) {
      console.log(`[POOL] creating new connection for ${pvName}`);

      const subscribers = new Set();

      const ws = new PVWebSocket(
        pvName,

        // Received PV data
        (value, timestamp) => {
          // each  WebSocket message only update once  sidebar store
          useLiveValueStore
            .getState()
            .updateLatestValue(pvName, value, timestamp);

          // distribute to all the Plot buffer used this PV
          subscribers.forEach((subscriber) => {
            subscriber.onData?.(value, timestamp);
          });
        },

        // Connection error
        (error) => {
          subscribers.forEach((subscriber) => {
            subscriber.onError?.(error);
          });
        },

        // Connected
        () => {
          subscribers.forEach((subscriber) => {
            subscriber.onConnect?.();
          });
        }
      );

      ws.connect();

      entry = { ws, subscribers };
      this.pool.set(pvName, entry);
    } else {
      console.log(`[POOL] reusing connection for ${pvName}`);
    }

    const subscriber = {
      onData: callbacks.onData,
      onError: callbacks.onError,
      onConnect: callbacks.onConnect,
    };

    entry.subscribers.add(subscriber);

    console.log(
      `[POOL] ${pvName} subscribers=${entry.subscribers.size}, ` +
      `activeConns=${this.pool.size}`
    );

    return () => {
      const currentEntry = this.pool.get(pvName);
      if (!currentEntry) return;

      currentEntry.subscribers.delete(subscriber);

      if (currentEntry.subscribers.size === 0) {
        currentEntry.ws.disconnect();
        this.pool.delete(pvName);
      }
    };
  }

  getActiveConnectionCount() {
    return this.pool.size;
  }
}

export const pvConnectionPool = new PVConnectionPool();
