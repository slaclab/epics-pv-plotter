// src/utils/constants.js

// ================================================================
// WebSocket Configuration
// ================================================================
export const WS_CONFIG = {
  //  FastAPI  gateway server address
  BASE_URL: 'ws://192.168.22.4:8000',  // Replace 'xxx' with server IP
  
  // Reconnection settings
  MAX_RECONNECT_ATTEMPTS: 5,      // Maximum number of reconnection attempts
  RECONNECT_DELAY: 3000,          // Delay between reconnection attempts (milliseconds)
  
  // Heartbeat configuration
  HEARTBEAT_INTERVAL: 30000,      // Heartbeat interval to keep connection alive (30 seconds)
};

// ================================================================
// Plot Configuration
// ================================================================
export const PLOT_CONFIG = {
  // Data buffer settings
  MAX_POINTS: 6000,               // Maximum number of data points stored per PV
  UPDATE_INTERVAL: 100,           // Plot update interval (milliseconds)
  
  // Grid layout settings
  GRID_COLS: 12,                  // Number of columns in the grid layout
  ROW_HEIGHT: 120,                // Height of each row (pixels)
  
  // Default plot dimensions (in grid units)
  DEFAULT_WIDTH: 4,               // Default width of a plot widget
  DEFAULT_HEIGHT: 3,              // Default height of a plot widget
};

// ================================================================
// Plotly Layout Template
// ================================================================
export const PLOT_LAYOUT_TEMPLATE = {
  autosize: true,
  margin: { l: 50, r: 30, t: 40, b: 40 },
  paper_bgcolor: 'white',
  plot_bgcolor: '#f8f9fa',
  
  font: {
    family: 'Arial, sans-serif',
    size: 12,
    color: '#333'
  },
  
  xaxis: {
    title: 'Time',                // X-axis label
    gridcolor: '#ddd',            // Grid line color
    showgrid: true,               // Show grid lines
    zeroline: false,              // Hide zero line
    type: 'date'                  // X-axis data type (date/time)
  },
  
  yaxis: {
    title: 'Value',               // Y-axis label
    gridcolor: '#ddd',            // Grid line color
    showgrid: true,               // Show grid lines
    zeroline: false               // Hide zero line
  },
  
  hovermode: 'closest',           // Hover tooltip mode
  showlegend: true,               // Show plot legend
 
  legend: {
    x: 0.01,
    y: 1,
    xanchor: 'left',           // 
    yanchor: 'top',
    orientation: 'v',
    width: 0.32,               // 
    bgcolor: 'rgba(255,255,255,0.95)',
    bordercolor: '#d0d0d0',
    borderwidth: 1,
    font: { size: 11 },
    traceorder: 'normal',
    itemclick: false,
    itemdoubleclick: false
  }



};

// ================================================================
// Color Theme Palette
// ================================================================
export const COLORS = {
  primary: '#667eea',             // Primary brand color (purple)
  secondary: '#764ba2',           // Secondary brand color (darker purple)
  success: '#10b981',             // Success state color (green)
  warning: '#f59e0b',             // Warning state color (orange)
  error: '#ef4444',               // Error state color (red)
  info: '#3b82f6'                 // Informational color (blue)
};


export const PV_COLORS = [
  '#1f77b4', // 1. blue
  '#ff7f0e', // 2. orange
  '#2ca02c', // 3. green
  '#d62728', // 4. red
  '#9467bd', // 5. purple
  '#8c564b', // 6. brown
  '#e377c2', // 7. pink
  '#7f7f7f', // 8. gray
  '#bcbd22', // 9. yellow gree
  '#17becf', // 10. 
  '#aec7e8', // 11. light blue
  '#ffbb78', // 12. light orange
  '#98df8a', // 13. light green
  '#ff9896', // 14. light red
  '#c5b0d5'  // 15. light purple

];

export const getPVColor = (pvName) => {
  // Deterministic mapping without unbounded memory growth
  let hash = 0;
  for (let i = 0; i < pvName.length; i++) {
    hash = (hash * 31 + pvName.charCodeAt(i)) >>> 0;
  }
  return PV_COLORS[hash % PV_COLORS.length];
};






