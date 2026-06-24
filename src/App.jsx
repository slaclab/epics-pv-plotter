// src/App.jsx
import { useState } from 'react';
import { usePlotStore } from './stores/usePlotStore';
import PlotGrid from './components/PlotGrid';
import { Plus, Trash2, Activity } from 'lucide-react';
import './App.css';

function App() {
  const [pvInput, setPvInput] = useState('');
  const { plots, addPlot, clearAll } = usePlotStore();

  const handleAddPlot = () => {
    const trimmedInput = pvInput.trim();
    
    if (!trimmedInput) {
      alert('Please enter a PV name');
      return;
    }

    // Support comma-separated multiple PVs
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

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>
            <Activity size={32} />
            EPICS Real-time Monitor
          </h1>
          <p>Real-time Process Variable monitoring and visualization</p>
        </div>
      </header>

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
            onClick={clearAll}
            disabled={plots.length === 0}
          >
            <Trash2 size={18} />
            Clear All
          </button>
        </div>

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
      </div>

      <PlotGrid />
    </div>
  );
}

export default App;
