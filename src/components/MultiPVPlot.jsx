// src/components/MultiPVPlot.jsx
import { useState, useEffect, useRef } from 'react';
import Plot from 'react-plotly.js';
import { X, Wifi, WifiOff, AlertCircle } from 'lucide-react';
import { PVWebSocket } from '../services/WebSocketManager';
import { DataBuffer } from '../services/DataBuffer';
import { PLOT_CONFIG, PLOT_LAYOUT_TEMPLATE } from '../utils/constants';
import { usePlotStore } from '../stores/usePlotStore';
import './MultiPVPlot.css';

export default function MultiPVPlot({ plotId, pvNames }) {
  const [plotData, setPlotData] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState({});
  const buffersRef = useRef({});
  const websocketsRef = useRef({});
  const updateTimerRef = useRef(null);
  const { removePlot, removePVFromPlot } = usePlotStore();

  // Initialize buffers and websockets for each PV
  useEffect(() => {
    pvNames.forEach((pvName) => {
      if (!buffersRef.current[pvName]) {
        buffersRef.current[pvName] = new DataBuffer(PLOT_CONFIG.MAX_POINTS);
        
        const ws = new PVWebSocket(
          pvName,
          (value, timestamp) => {
            buffersRef.current[pvName].addPoint(value, timestamp || Date.now());
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

    // Cleanup removed PVs
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

    // Periodic update for plot rendering
    updateTimerRef.current = setInterval(() => {
      const traces = pvNames.map((pvName) => {
        const buffer = buffersRef.current[pvName];
        const data = buffer ? buffer.getData() : { x: [], y: [] };
        
        return {
          x: data.x,
          y: data.y,
          type: 'scatter',
          mode: 'lines',
          name: pvName,
          line: { width: 2 }
        };
      });

      setPlotData(traces);
    }, PLOT_CONFIG.UPDATE_INTERVAL);

    return () => {
      if (updateTimerRef.current) {
        clearInterval(updateTimerRef.current);
      }
      Object.values(websocketsRef.current).forEach((ws) => ws.disconnect());
    };
  }, [pvNames]);

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

  return (
    <div className="plot-widget">
      <div className="plot-header">
        <div className="pv-tags">
          {pvNames.map((pvName) => (
            <div key={pvName} className="pv-tag">
              {getStatusIcon(connectionStatus[pvName])}
              <span className="pv-name">{pvName}</span>
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
        <button
          className="plot-close"
          onClick={() => removePlot(plotId)}
          title="Close plot"
        >
          <X size={18} />
        </button>
      </div>

      <div className="plot-container">
        <Plot
          data={plotData}
          layout={{
            ...PLOT_LAYOUT_TEMPLATE,
            title: pvNames.length === 1 ? pvNames[0] : 'Multi-PV Plot',
            uirevision: 'true' // Preserve zoom/pan state
          }}
          config={{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d']
          }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler={true}
        />
      </div>
    </div>
  );
}
