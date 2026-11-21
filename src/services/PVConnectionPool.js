import { PVWebSocket } from "./WebSocketManager";
import { useLiveValueStore } from "../stores/useLiveValueStore";
import { isEnergyPV } from "../utils/energy";

class PVConnectionPool {
  constructor() {
    // pvName -> { ws: PVWebSocket, subscribers: Set<Subscriber> }
    this.pool = new Map();
  }

  createConnection(pvName, subscribers) {
    return new PVWebSocket(
      pvName,
      (value, timestamp) => {
        useLiveValueStore
          .getState()
          .updateLatestValue(pvName, value, timestamp);

        subscribers.forEach((subscriber) => {
          subscriber.onData?.(value, timestamp);
        });
      },
      (error) => {
        useLiveValueStore.getState().removeLatestValue(pvName);

        subscribers.forEach((subscriber) => {
          subscriber.onError?.(error);
        });
      },
      () => {
        subscribers.forEach((subscriber) => {
          subscriber.onConnect?.();
        });
      },
      () => {
        useLiveValueStore.getState().removeLatestValue(pvName);

        subscribers.forEach((subscriber) => {
          subscriber.onDisconnect?.();
        });
      },
    );
  }

  subscribe(pvName, callbacks = {}) {
    let entry = this.pool.get(pvName);

    if (!entry) {
      console.log(
        `[POOL] creating new connection for ${pvName}`
      );

      const subscribers = new Set();
      const ws = this.createConnection(pvName, subscribers);

      ws.connect();

      entry = {
        ws,
        subscribers,
      };

      this.pool.set(pvName, entry);
    } else {
      console.log(
        `[POOL] reusing connection for ${pvName}`
      );
    }

    const subscriber = {
      onData: callbacks.onData,
      onError: callbacks.onError,
      onConnect: callbacks.onConnect,
      onDisconnect: callbacks.onDisconnect,
    };

    entry.subscribers.add(subscriber);
    if (entry.ws.isConnected()) {
      subscriber.onConnect?.();
    }
    console.log(
      `[POOL] ${pvName} ` +
        `subscribers=${entry.subscribers.size}, ` +
        `activeConns=${this.pool.size}`
    );

    return () => {
      const currentEntry = this.pool.get(pvName);

      if (!currentEntry) {
        return;
      }

      currentEntry.subscribers.delete(subscriber);

      console.log(
        `[POOL] ${pvName} unsubscribed, ` +
          `subscribers=${currentEntry.subscribers.size}`
      );

      if (currentEntry.subscribers.size === 0) {
        currentEntry.ws.disconnect();
        this.pool.delete(pvName);

        useLiveValueStore
          .getState()
          .removeLatestValue(pvName);

        console.log(
          `[POOL] closed connection for ${pvName}, ` +
            `activeConns=${this.pool.size}`
        );
      }
    };
  }

  reconnectEnergyConnections() {
    this.pool.forEach((entry, pvName) => {
      if (!isEnergyPV(pvName)) return;

      entry.ws.disconnect();
      useLiveValueStore.getState().removeLatestValue(pvName);
      entry.ws = this.createConnection(pvName, entry.subscribers);
      entry.ws.connect();
    });
  }

  getActiveConnectionCount() {
    return this.pool.size;
  }
}

export const pvConnectionPool =
  new PVConnectionPool();
