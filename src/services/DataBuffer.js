// src/services/DataBuffer.js

export class DataBuffer {
  constructor(maxPoints = 1000) {
    this.maxPoints = maxPoints;  //Maximum number of data points to store
    this.timestamps = [];
    this.values = [];
  }

  //add new data including value and timestamp
  addPoint(value, timestamp) {
    // Backend sends Unix timestamp in SECONDS (e.g., 1782321020.304764)
    // JavaScript Date expects MILLISECONDS
    // So multiply by 1000
    
    const time = new Date(timestamp * 1000);
    
    // Validate timestamp is reasonable
    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 3600000);
    const oneHourFromNow = new Date(now.getTime() + 3600000);
   
    //check if timestamp is reasonable (within +/- 1 hour
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

    //push the new elements to the timestamps and values list
    this.timestamps.push(time);
    this.values.push(numValue);

    // Maintain buffer size
    if (this.timestamps.length > this.maxPoints) {
      this.timestamps.shift();
      this.values.shift();
    }
    
    // Debug logging
    // print out the first 3 data point information for debuging 
    if (this.values.length <= 3) {
      console.log(`📊 Point #${this.values.length}:`, {
        backendTimestamp: timestamp,
        jsTime: time.toISOString(),  //YYYY-MM-DDThh:mm:sssZ miliseconds
        localTime: time.toLocaleTimeString(), //hh:mm:ss AM or PM
        value: numValue.toExponential(2)
      });
    }
    
    // Periodic status to log every 50 points
    if (this.values.length % 50 === 0) {
      console.log(`📊 Buffer: ${this.values.length} points`);
    }
  }

  // function to get the data including timestamps and values
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

  //get the lasted value from the list
  getLatestValue() {
    if (this.values.length === 0) return null;
    return this.values[this.values.length - 1];
  }

  //get the lastest time from the list
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
