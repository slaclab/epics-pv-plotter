// src/App.jsx
import { useState, useEffect } from 'react';
import { usePlotStore } from './stores/usePlotStore';
import PlotGrid from './components/PlotGrid';
import { Plus, Trash2, Activity, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import './App.css';

function App() {
  const [pvInput, setPvInput] = useState('');
  const [showInfo, setShowInfo] = useState(false);
  
  const { 
    plots, 
    addPlot, 
    clearAll,
    timeSyncEnabled,
    globalTimeWindow,
    toggleTimeSync,
    setTimeWindow
  } = usePlotStore();

  useEffect(() => {
    if (plots.length > 0) {
      console.log(`✅ Restored ${plots.length} plot(s) from previous session`);
    }
  }, [plots.length]);

  const handleAddPlot = () => {
    const trimmedInput = pvInput.trim();
    
    if (!trimmedInput) {
      alert('Please enter a PV name');
      return;
    }

    const pvNames = trimmedInput
      .split(',')
      .map(pv => pv.trim())
      .filter(pv => pv.length > 0);

    if (pvNames.length === 0) {
      alert('Please enter valid PV name(s)');
      return;
    }
    
    addPlot(pvNames);
    setPvInput('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleAddPlot();
    }
  };

  const handleClearAll = () => {
    if (plots.length === 0) return;
    
    if (window.confirm('Are you sure you want to clear all plots?')) {
      clearAll();
      localStorage.removeItem('epics-plot-storage');
      console.log('🗑️ All plots and storage cleared');
    }
  };

  return (
    <div className="app">
      {/*
      <header className="app-header">
        <div className="header-content">
          <h1> 
            <Activity size={32} />
            EPICS Real-time Monitor
          </h1>
          <p>Real-time Process Variable monitoring and visualization</p>
        </div>
      </header>
      */}
      <div className="control-panel">
        <div className="input-group">
          <input
            type="text"
            className="pv-input"
            placeholder="Enter PV name (e.g., IOC:ai1 or IOC:ai1,IOC:ai2 for multi-PV plot)"
            value={pvInput}
            onChange={(e) => setPvInput(e.target.value)}
            onKeyPress={handleKeyPress}
          />
          <button
            className="btn btn-primary"
            onClick={handleAddPlot}
            disabled={!pvInput.trim()}
          >
            <Plus size={18} />
            Add Plot
          </button>
          <button
            className="btn btn-danger"
            onClick={handleClearAll}
            disabled={plots.length === 0}
          >
            <Trash2 size={18} />
            Clear All
          </button>
          
          <button
            className="btn btn-info"
            onClick={() => setShowInfo(!showInfo)}
            title="Toggle info panel"
          >
            {showInfo ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            Info Details
          </button>

          {/* Vertical Separator */}
          <div className="separator"></div>

          {/* Time Synchronization Controls - Now Inline */}
          <button
            className={`btn ${timeSyncEnabled ? 'btn-success' : 'btn-secondary'}`}
            onClick={toggleTimeSync}
            title="Toggle time axis synchronization"
          >
            <Clock size={18} />
            {timeSyncEnabled ? 'Time Sync: ON' : 'Time Sync: OFF'}
          </button>
          
          {timeSyncEnabled && (
            <>
              <label className="time-window-label">Time Window:</label>
              <select 
                value={globalTimeWindow} 
                onChange={(e) => setTimeWindow(Number(e.target.value))}
                className="time-window-select"
              >
                <option value={30}>30 seconds</option>
                <option value={60}>1 minute</option>
                <option value={120}>2 minutes</option>
                <option value={300}>5 minutes</option>
                <option value={600}>10 minutes</option>
                <option value={1800}>30 minutes</option>
                <option value={3600}>1 hour</option>
              </select>
            </>
          )}
        </div>

        {/* Collapsible Info Panel */}
        {showInfo && (
          <div className="info-panel">
            <div className="info-item">
              <div className="info-label">Active Plots</div>
              <div className="info-value">{plots.length}</div>
            </div>
            <div className="info-item">
              <div className="info-label">Monitored PVs</div>
              <div className="info-value">
                {plots.reduce((sum, plot) => sum + plot.pvNames.length, 0)}
              </div>
            </div>
          </div>
        )}
      </div>

      <PlotGrid />
    </div>
  );
}

export default App;
