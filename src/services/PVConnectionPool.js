import { PVWebSocket } from "./WebSocketManager";

class PVConnectionPool {
  constructor() {
    // pvName -> { ws: PVWebSocket, subscribers: Set<Subscriber> }
    this.pool = new Map();
  }

  //called in MultiPVPlot.jsx,  e.g. pool.subscribe("ADC1", { onData, onError, onConnect })
  //returns on unsubscribe() function
  subscribe(pvName, callbacks) {
    let entry = this.pool.get(pvName);
    //if the PV doesn't exist in the pool
    if (!entry) {
      

      console.log(`[POOL] creating new connection for ${pvName}`);
      const subscribers = new Set();

      // Create ONE shared PVWebSocket for this PV
      // 
      const ws = new PVWebSocket(
        pvName,
        (value, timestamp) => {
          // Fan-out to all subscribers of this PV
	  // optional chaining(?.) means the callback is only called if it exists
          subscribers.forEach((s) => s.onData?.(value, timestamp));
        },
        (error) => {
          subscribers.forEach((s) => s.onError?.(error));
        },
        () => {
          subscribers.forEach((s) => s.onConnect?.());
        }
      );
      //websocket connection,
      ws.connect();
      //create a new entry and add to the pool
      entry = { ws, subscribers };
      this.pool.set(pvName, entry);
    } else{
      console.log(`[POOL] reusing connection for ${pvName}`);
	
    }

    // Register this subscriber (one per plot per PV)
    const subscriber = {
      onData: callbacks.onData,
      onError: callbacks.onError,
      onConnect: callbacks.onConnect,
    };

    entry.subscribers.add(subscriber);
    console.log(`[POOL] ${pvName} subscribers=${entry.subscribers.size}, activeConns=${this.pool.size}`);

    // Return an unsubscribe function
    return () => {
      const e = this.pool.get(pvName);
      if (!e) return;

      e.subscribers.delete(subscriber);

      // If no more subscribers, close the shared connection
      if (e.subscribers.size === 0) {
        e.ws.disconnect();
        this.pool.delete(pvName);
      }
    };
  }

  getActiveConnectionCount() {
    return this.pool.size;
  }
}

export const pvConnectionPool = new PVConnectionPool();
