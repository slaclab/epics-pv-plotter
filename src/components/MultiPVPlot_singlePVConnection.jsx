// src/components/MultiPVPlot.jsx
import { useState, useEffect, useRef } from 'react';
import Plot from 'react-plotly.js';
import { X, Wifi, WifiOff, AlertCircle, Download } from 'lucide-react';
import { PVWebSocket } from '../services/WebSocketManager';
import { DataBuffer } from '../services/DataBuffer';
import { PLOT_CONFIG, PLOT_LAYOUT_TEMPLATE, getPVColor } from '../utils/constants';
import { usePlotStore } from '../stores/usePlotStore';
import './MultiPVPlot.css';

export default function MultiPVPlot({ plotId, pvNames }) {
  // Toggle to show/hide the per-PV tags (status icon, point count, remove button).
  const SHOW_PV_TAGS = false;

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
    globalTimeWindow,
    updateLatestValue
  } = usePlotStore();

  // Returns a stable, cross-plot-consistent color for each PV name
  const getTraceColor = (pvName) => {
    return getPVColor(pvName);
  };

  // ============================================================
  // Export data function for a single PV
  // ============================================================
  const exportData = (pvName) => {
    const buffer = buffersRef.current[pvName];

    if (!buffer || buffer.getPointCount() === 0) {
      alert('No data to export');
      return;
    }
    
    const data = buffer.getData();

    const csv = ['Timestamp,Value']
      .concat(data.x.map((time, i) =>
        `${time.toISOString()},${data.y[i]}`
      ))
      .join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    link.download = `${pvName}_${timestamp}.csv`;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    console.log(`✅ Exported ${data.x.length} data points for ${pvName}`);
  };

  // ============================================================
  // Export all data for multi-PV plots
  // ============================================================
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

  // ============================================================
  // Effect 1: Manage WebSocket connections + buffers
  //   Depends ONLY on pvNames.
  // ============================================================
  useEffect(() => {
    console.log(`🔧 Initializing connections for PVs:`, pvNames);

    pvNames.forEach((pvName) => {
      if (!buffersRef.current[pvName]) {
        buffersRef.current[pvName] = new DataBuffer(PLOT_CONFIG.MAX_POINTS);

        const ws = new PVWebSocket(
          pvName,
          (value, timestamp) => {
            buffersRef.current[pvName].addPoint(value, timestamp);
            updateLatestValue(pvName, value, timestamp);
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

    // No cleanup here: pvNames changes are handled above (connect new PVs / disconnect removed PVs).
    // Cleanup happens on unmount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pvNames]);

  // Disconnect everything on unmount only
  useEffect(() => {
    return () => {
      console.log('🛑 Disconnecting all websockets (unmount)');
      Object.values(websocketsRef.current).forEach((ws) => ws.disconnect());
      websocketsRef.current = {};
      buffersRef.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ============================================================
  // Effect 2: Periodic plot redraw timer
  //   Depends on pvNames + time settings.
  // ============================================================
  useEffect(() => {
    let updateCount = 0;

    updateTimerRef.current = setInterval(() => {
      updateCount++;

      let xMin = null;
      let xMax = null;
      
      // use the last point data time stamp to replace current time
      
      if (timeSyncEnabled) {
        // Anchor the window's right edge to the newest DATA timestamp,
        // not the front-end wall clock (they can differ if clocks aren't synced).
        let latest = null;
        pvNames.forEach((pvName) => {
          const buffer = buffersRef.current[pvName];
          const ts = buffer ? buffer.getLatestTimestamp() : null;
          if (ts && (!latest || ts > latest)) {
            latest = ts;
          }
        });
      
        // Use latest data time as the right edge; fall back to now if no data yet
        xMax = latest || new Date();
        xMin = new Date(xMax.getTime() - globalTimeWindow * 1000);
      }
      


      
      //if (timeSyncEnabled) {
      //  const now = new Date();
      //  xMax = now;
      //  xMin = new Date(now.getTime() - globalTimeWindow * 1000);
      //}

      const traces = pvNames.map((pvName) => {
        const buffer = buffersRef.current[pvName];
        let data = buffer ? buffer.getData() : { x: [], y: [] };

        if (timeSyncEnabled && xMin && xMax && data.x.length > 0) {
          const filteredIndices = [];
          data.x.forEach((time, idx) => {
            if (time >= xMin && time <= xMax) {
              filteredIndices.push(idx);
            }
          });

          data = {
            x: filteredIndices.map(i => data.x[i]),
            y: filteredIndices.map(i => data.y[i])
          };
        }

        return {
          x: data.x,
          y: data.y,
          type: 'scatter',
          mode: 'lines+markers',
          name: pvName,
          line: { width: 2, color: getTraceColor(pvName) },
          marker: { size: 4 }
        };
      });

      let allValues = [];
      traces.forEach((trace) => {
        allValues = allValues.concat(trace.y);
      });

      if (allValues.length > 0) {
        const min = Math.min(...allValues);
        const max = Math.max(...allValues);
        const range = max - min;
        const padding = range * 0.2 || 0.0001;
        setYAxisRange([min - padding * 0.8, max + padding * 3.]);
      }

      if (timeSyncEnabled && xMin && xMax) {
        setXAxisRange([xMin, xMax]);
      } else {
        setXAxisRange(null);
      }

      if (updateCount % 10 === 0) {
        const totalPoints = pvNames.reduce((sum, pvName) => {
          const buffer = buffersRef.current[pvName];
          return sum + (buffer ? buffer.getPointCount() : 0);
        }, 0);
        console.log(`🔄 Plot update #${updateCount}: ${totalPoints} total points across ${pvNames.length} PV(s)`);

        if (timeSyncEnabled) {
          console.log(`🕐 Time window: ${xMin?.toLocaleTimeString()} - ${xMax?.toLocaleTimeString()}`);
        }
      }

      setPlotData(traces);
      setRevision(prev => prev + 1);
    }, PLOT_CONFIG.UPDATE_INTERVAL);

    console.log(`✅ Plot update timer started (interval: ${PLOT_CONFIG.UPDATE_INTERVAL}ms)`);

    return () => {
      if (updateTimerRef.current) {
        clearInterval(updateTimerRef.current);
        console.log(`✅ Plot update timer stopped`);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pvNames, timeSyncEnabled, globalTimeWindow]);

  // ============================================================
  // Connection status icon helper (used by pv-tags when enabled)
  // ============================================================
  const getStatusIcon = (status) => {
    switch (status) {
      case 'connected':
        return <Wifi size={14} className="status-icon connected" />;
      case 'error':
        return <AlertCircle size={14} className="status-icon error" />;
      default:
        return <WifiOff size={14} className="status-icon connecting" />;
    }
  };

  // ============================================================
  // Plot layout
  // ============================================================
  const plotLayout = {
    ...PLOT_LAYOUT_TEMPLATE,
    // title removed intentionally
    datarevision: revision,
    showlegend: true,

    yaxis: {
      ...PLOT_LAYOUT_TEMPLATE.yaxis,
      autorange: yAxisRange ? false : true,
      range: yAxisRange,
      exponentformat: 'e',
      tickformat: '.2e'
    },
    xaxis: {
      ...PLOT_LAYOUT_TEMPLATE.xaxis,
      type: 'date',
      tickformat: '%H:%M:%S',
      autorange: xAxisRange ? false : true,
      range: xAxisRange
    },
    margin: { l: 85, r: 30, t: 10, b: 50 }
  };

  return (
    <div className="plot-widget">
      <div className="plot-header">

        {/*
          Per-PV tags. Controlled by SHOW_PV_TAGS (top of component).
          Hidden by default; logic preserved and re-enabled by SHOW_PV_TAGS = true.
        */}
        <div className="pv-tags">
          {SHOW_PV_TAGS && pvNames.map((pvName) => (
            <div key={pvName} className="pv-tag">
              {getStatusIcon(connectionStatus[pvName])}
              <span className="pv-name">{pvName}</span>
              {buffersRef.current[pvName] && (
                <span className="pv-count">
                  ({buffersRef.current[pvName].getPointCount()})
                </span>
              )}
              {pvNames.length > 1 && (
                <button
                  className="pv-remove"
                  onClick={() => removePVFromPlot(plotId, pvName)}
                  title="Remove this PV"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="plot-actions">
          <button
            className="plot-action-btn"
            onClick={exportAllData}
            title="Export data to CSV"
          >
            <Download size={16} />
          </button>

          <button
            className="plot-close"
            onClick={() => removePlot(plotId)}
            title="Close plot"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="plot-container">
        <Plot
          data={plotData}
          layout={plotLayout}
          config={{
            responsive: true,
            displayModeBar: false,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d'],
            toImageButtonOptions: {
              format: 'png',
              filename: pvNames.join('_'),
              height: 600,
              width: 1000
            }
          }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler={true}
        />
      </div>
    </div>
  );
}
