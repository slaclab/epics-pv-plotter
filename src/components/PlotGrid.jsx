// src/components/PlotGrid.jsx
import { useEffect, useMemo, useState } from "react";
import { Responsive, WidthProvider } from "react-grid-layout";

import { usePlotStore } from "../stores/usePlotStore";
import { pvConnectionPool } from "../services/PVConnectionPool";
import MultiPVPlot from "./MultiPVPlot";
import { API_BASE, PLOT_CONFIG } from "../utils/constants";
import { configPresetUrl } from "../utils/configApi";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import "./PlotGrid.css";

const ResponsiveGridLayout = WidthProvider(Responsive);

export default function PlotGrid({ onLayoutLoaded }) {
  const plots = usePlotStore((state) => state.plots);
  const updateLayout = usePlotStore((state) => state.updateLayout);
  const loadLayout = usePlotStore((state) => state.loadLayout);
  const activeConfigFile = usePlotStore((state) => state.activeConfigFile);
  const setActiveConfigFile = usePlotStore(
    (state) => state.setActiveConfigFile,
  );
  const bumpSettingsRevision = usePlotStore(
    (state) => state.bumpSettingsRevision,
  );
  const [configFiles, setConfigFiles] = useState([]);
  const [selectedConfig, setSelectedConfig] = useState("");
  const [configError, setConfigError] = useState("");
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);

  useEffect(() => {
    let active = true;

    fetch(`${API_BASE}/api/config-presets`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        if (!Array.isArray(data.files)) {
          throw new Error("The server returned an invalid configuration list");
        }
        if (active) {
          setConfigFiles(data.files);
          setSelectedConfig(
            activeConfigFile !== "config.json" &&
              data.files.includes(activeConfigFile)
              ? activeConfigFile
              : "",
          );
        }
      })
      .catch((error) => {
        if (active) {
          setConfigError(`Failed to load configuration list: ${error.message}`);
        }
      });

    return () => {
      active = false;
    };
  }, [activeConfigFile]);

  const layout = useMemo(
    () =>
      plots.map((plot) => ({
        i: plot.id.toString(),
        x: plot.x,
        y: plot.y,
        w: plot.w,
        h: plot.h,
        minW: 3,
        minH: 2,
        maxH: 6,
      })),
    [plots],
  );
  const handleConfigLoad = async (filename = "config.json") => {
    setIsLoadingConfig(true);
    setConfigError("");
    try {
      const response = await fetch(configPresetUrl(filename));
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const config = await response.json();
      const layout = config?.layouts?.default;
      if (!layout || typeof layout !== "object") {
        throw new Error("The selected configuration has no default layout");
      }

      onLayoutLoaded?.(layout);
      loadLayout(layout);
      setActiveConfigFile(filename);
      pvConnectionPool.reconnectEnergyConnections();
      bumpSettingsRevision();
    } catch (error) {
      console.error(`Failed to load configuration ${filename}:`, error);
      setConfigError(`Failed to load ${filename}: ${error.message}`);
    } finally {
      setIsLoadingConfig(false);
    }
  };

  const configControls = (
    <div className="config-loader">
      <button
        className="btn-load-config"
        onClick={() => handleConfigLoad()}
        disabled={isLoadingConfig}
      >
        Load Standard Configuration
      </button>
      <div className="config-preset-controls">
        <select
          aria-label="Configuration preset"
          value={selectedConfig}
          onChange={(event) => setSelectedConfig(event.target.value)}
          disabled={isLoadingConfig || configFiles.length === 0}
        >
          <option value="">
            {configFiles.length === 0
              ? "No configuration presets found"
              : "Select a configuration"}
          </option>
          {configFiles
            .filter((filename) => filename !== "config.json")
            .map((filename) => (
              <option key={filename} value={filename}>
                {filename}
              </option>
            ))}
        </select>
        <button
          type="button"
          onClick={() => handleConfigLoad(selectedConfig)}
          disabled={!selectedConfig || isLoadingConfig}
        >
          {isLoadingConfig ? "Loading..." : "Load Selected Configuration"}
        </button>
      </div>
      {configError && (
        <p className="config-load-error" role="alert">
          {configError}
        </p>
      )}
    </div>
  );

  //if not plots, show the default panel
  if (plots.length === 0) {
    return (
      <div className="plot-grid-container">
        <div className="empty-state">
          <div className="empty-content">
            <h2>No plots yet</h2>
            <p>Enter a PV name above to start monitoring</p>

            <div className="example-pvs">
              <p className="example-title">Example PV names:</p>
              <code>TEST:PV:01</code>
              <code>SYS:TEMP:CPU</code>
              <code>BEAM:CURRENT</code>
            </div>
            <p> Or</p>
            {configControls}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="plot-grid-container">
      {configControls}
      <ResponsiveGridLayout
        className="plot-grid"
        layouts={{ lg: layout }}
        breakpoints={{
          lg: 1200,
          md: 996,
          sm: 768,
          xs: 480,
          xxs: 0,
        }}
        cols={{
          lg: 12,
          md: 10,
          sm: 6,
          xs: 4,
          xxs: 2,
        }}
        rowHeight={PLOT_CONFIG.ROW_HEIGHT}
        onDragStop={(newLayout) => {
          updateLayout(newLayout);
        }}
        onResizeStop={(newLayout) => {
          updateLayout(newLayout);
        }}
        draggableHandle=".plot-header"
        draggableCancel="button"
        compactType="vertical"
        preventCollision={false}
        isDraggable={true}
        isResizable={true}
        margin={[16, 16]}
      >
        {plots.map((plot) => (
          <div key={plot.id.toString()}>
            <MultiPVPlot plotId={plot.id} pvNames={plot.pvNames} />
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  );
}
