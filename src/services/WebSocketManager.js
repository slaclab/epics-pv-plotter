// src/services/WebSocketManager.js
// To Manage a Single PV connection
//
import { WS_CONFIG } from '../utils/constants';

export class PVWebSocket {
  constructor(pvName, onData, onError, onConnect) {
    this.pvName = pvName; 

    //callback functions, separation of passing and handling
    this.onData = onData;  //call when data is received
    this.onError = onError; //call when error happens
    this.onConnect = onConnect; //call when connected

    this.ws = null;	
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.messageCount = 0; // Track number of messages received
  }

  connect() {
    try {
      const wsUrl = `${WS_CONFIG.BASE_URL}/ws?pv=${encodeURIComponent(this.pvName)}`;
      
      console.log(`🔗 Connecting to: ${wsUrl}`);
      this.ws = new WebSocket(wsUrl);

      //
      this.ws.onopen = () => {
        console.log(`✅ Connected: ${this.pvName}`);
        this.reconnectAttempts = 0;
        this.messageCount = 0;
        if (this.onConnect) this.onConnect();
      };
      //
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.error) {
            console.error(`❌ PV Error (${this.pvName}):`, data.error);
            if (this.onError) this.onError(data.error);
            return;
          }

          this.messageCount++;
          
          // Log every 10th message to show updates are arriving
          if (this.messageCount % 10 === 0) {
            console.log(`📡 ${this.pvName}: Received ${this.messageCount} messages`);
          }

          // Call data callback
          if (this.onData) {
            this.onData(data.value, data.timestamp);
          }
        } catch (err) {
          console.error('Parse error:', err);
          if (this.onError) this.onError('Data parse error');
        }
      };
      //
      this.ws.onerror = (error) => {
        // Only log error if not initial connection attempt
        if (this.reconnectAttempts > 0) {
          console.error(`❌ WebSocket error (${this.pvName}):`, error);
        }
        if (this.onError && this.reconnectAttempts > 0) {
          this.onError('Connection error');
        }
      };

      // when connection is closed, reconnect
      this.ws.onclose = () => {
        console.log(`🔌 Connection closed: ${this.pvName} (received ${this.messageCount} messages)`);
        this.attemptReconnect();
      };

    } catch (err) {
      console.error('WebSocket creation failed:', err);
      if (this.onError) this.onError(err.message);
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= WS_CONFIG.MAX_RECONNECT_ATTEMPTS) {
      console.error(`❌ ${this.pvName}: Reconnection failed (${WS_CONFIG.MAX_RECONNECT_ATTEMPTS} attempts)`);
      if (this.onError) {
        this.onError(`Reconnection failed (${WS_CONFIG.MAX_RECONNECT_ATTEMPTS} attempts)`);
      }
      return;
    }

    this.reconnectAttempts++;
    console.log(`🔄 ${this.pvName}: Reconnecting in ${WS_CONFIG.RECONNECT_DELAY/1000}s (attempt ${this.reconnectAttempts}/${WS_CONFIG.MAX_RECONNECT_ATTEMPTS})...`);

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, WS_CONFIG.RECONNECT_DELAY);
  }

  disconnect() {
    this.reconnectAttemps = 0;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
