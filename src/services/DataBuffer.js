// src/services/DataBuffer.js

export class DataBuffer {
  constructor(maxPoints = 1000) {
    this.maxPoints = maxPoints;
    this.timestamps = [];
    this.values = [];
  }

  addPoint(value, timestamp) {
    // Backend sends Unix timestamp in SECONDS (e.g., 1782321020.304764)
    // JavaScript Date expects MILLISECONDS
    // So multiply by 1000
    
    const time = new Date(timestamp * 1000);
    
    // Validate timestamp is reasonable
    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 3600000);
    const oneHourFromNow = new Date(now.getTime() + 3600000);
    
    if (time < oneHourAgo || time > oneHourFromNow) {
      console.warn('⚠️  Suspicious timestamp:', {
        backend: timestamp,
        converted: time.toISOString(),
        now: now.toISOString()
      });
      // Fallback to current time if timestamp seems wrong
      time.setTime(Date.now());
    }
    
    // Ensure value is a number
    const numValue = typeof value === 'number' ? value : parseFloat(value);
    
    this.timestamps.push(time);
    this.values.push(numValue);

    // Maintain buffer size
    if (this.timestamps.length > this.maxPoints) {
      this.timestamps.shift();
      this.values.shift();
    }
    
    // Debug logging
    if (this.values.length <= 3) {
      console.log(`📊 Point #${this.values.length}:`, {
        backendTimestamp: timestamp,
        jsTime: time.toISOString(),
        localTime: time.toLocaleTimeString(),
        value: numValue.toExponential(2)
      });
    }
    
    // Periodic status
    if (this.values.length % 50 === 0) {
      console.log(`📊 Buffer: ${this.values.length} points`);
    }
  }

  getData() {
    return {
      x: this.timestamps,
      y: this.values
    };
  }

  clear() {
    this.timestamps = [];
    this.values = [];
  }

  getLatestValue() {
    if (this.values.length === 0) return null;
    return this.values[this.values.length - 1];
  }

  getLatestTimestamp() {
    if (this.timestamps.length === 0) return null;
    return this.timestamps[this.timestamps.length - 1];
  }

  getPointCount() {
    return this.values.length;
  }

  getValueRange() {
    if (this.values.length === 0) return { min: 0, max: 1 };
    const min = Math.min(...this.values);
    const max = Math.max(...this.values);
    return { min, max };
  }
}
