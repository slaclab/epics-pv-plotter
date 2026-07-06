// src/components/MultiPVPlot.jsx
import { useState, useEffect, useRef } from 'react';
import Plot from 'react-plotly.js';
import { X, Wifi, WifiOff, AlertCircle, Download } from 'lucide-react';
import { PVWebSocket } from '../services/WebSocketManager';
import { DataBuffer } from '../services/DataBuffer';
import { PLOT_CONFIG, PLOT_LAYOUT_TEMPLATE } from '../utils/constants';
import { usePlotStore } from '../stores/usePlotStore';
import './MultiPVPlot.css';

export default function MultiPVPlot({ plotId, pvNames }) {
  const [plotData, setPlotData] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState({});
  const [yAxisRange, setYAxisRange] = useState(null);
  const [xAxisRange, setXAxisRange] = useState(null);
  const [revision, setRevision] = useState(0);
  const buffersRef = useRef({});
  const websocketsRef = useRef({});
  const updateTimerRef = useRef(null);
  
  const { 
    removePlot, 
    removePVFromPlot,
    timeSyncEnabled,
    globalTimeWindow
  } = usePlotStore();

  // Export data functions (unchanged)
  const exportData = (pvName) => {
    const buffer = buffersRef.current[pvName];
    
    if (!buffer || buffer.getPointCount() === 0) {
      alert('No data to export');
      return;
    }
    
    const data = buffer.getData();
    
    const csv = ['Timestamp,Value']
      .concat(data.x.map((time, i) => 
        `$${time.toISOString()},$${data.y[i]}`
      ))
      .join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    link.download = `$${pvName}_$${timestamp}.csv`;
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    
    console.log(`✅ Exported $${data.x.length} data points for $${pvName}`);
  };

  const exportAllData = () => {
    if (pvNames.length === 1) {
      exportData(pvNames[0]);
      return;
    }

    const allData = pvNames.map(pvName => {
      const buffer = buffersRef.current[pvName];
      return buffer ? buffer.getData() : { x: [], y: [] };
    });

    if (allData.every(d => d.x.length === 0)) {
      alert('No data to export');
      return;
    }
    
    const header = ['Timestamp'].concat(pvNames.map(pv => `${pv}_Value`));
    const allTimestamps = new Set();
    allData.forEach(data => {
      data.x.forEach(time => allTimestamps.add(time.getTime()));
    });
    
    const sortedTimestamps = Array.from(allTimestamps).sort();
    
    const rows = sortedTimestamps.map(timestamp => {
      const row = [new Date(timestamp).toISOString()];
      
      pvNames.forEach((pvName, idx) => {
        const data = allData[idx];
        const timeIndex = data.x.findIndex(t => t.getTime() === timestamp);
        row.push(timeIndex >= 0 ? data.y[timeIndex] : '');
      });
      
      return row.join(',');
    });
    
    const csv = [header.join(',')].concat(rows).join('\n');
<<<<<<< HEAD
    // Blob (Binary Large Object) URL
=======
   
>>>>>>> 00f082d (added the code sync all the plots)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    link.download = `multi-pv_${timestamp}.csv`;
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    
    console.log(`✅ Exported data for ${pvNames.length} PVs`);
  };

  // Initialize buffers and websockets
  useEffect(() => {
    console.log(`🔧 Initializing plot for PVs:`, pvNames);

    pvNames.forEach((pvName) => {
      if (!buffersRef.current[pvName]) {
        buffersRef.current[pvName] = new DataBuffer(PLOT_CONFIG.MAX_POINTS);
        
        const ws = new PVWebSocket(
          pvName,
          (value, timestamp) => {
            buffersRef.current[pvName].addPoint(value, timestamp);
          },
          (error) => {
            console.error(`Error for ${pvName}:`, error);
            setConnectionStatus((prev) => ({ ...prev, [pvName]: 'error' }));
          },
          () => {
            setConnectionStatus((prev) => ({ ...prev, [pvName]: 'connected' }));
          }
        );

        ws.connect();
        websocketsRef.current[pvName] = ws;
        setConnectionStatus((prev) => ({ ...prev, [pvName]: 'connecting' }));
      }
    });
    
    Object.keys(buffersRef.current).forEach((pvName) => {
      if (!pvNames.includes(pvName)) {
        websocketsRef.current[pvName]?.disconnect();
        delete websocketsRef.current[pvName];
        delete buffersRef.current[pvName];
        setConnectionStatus((prev) => {
          const newStatus = { ...prev };
          delete newStatus[pvName];
          return newStatus;
        });
      }
    });

    // Periodic plot update
    let updateCount = 0;
