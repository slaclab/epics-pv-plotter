// src/components/PlotGrid.jsx
import { useMemo } from 'react';
import GridLayout from 'react-grid-layout';
import { usePlotStore } from '../stores/usePlotStore';
import MultiPVPlot from './MultiPVPlot';
import { PLOT_CONFIG } from '../utils/constants';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import './PlotGrid.css';

export default function PlotGrid() {
  const { plots, updateLayout } = usePlotStore();

  const layout = useMemo(
    () =>
      plots.map((plot) => ({
        i: plot.id.toString(),
        x: plot.x,
        y: plot.y,
        w: plot.w,
        h: plot.h,
        minW: 3,
        minH: 2
      })),
    [plots]
  );

  const handleLayoutChange = (newLayout) => {
    updateLayout(newLayout);
  };

  if (plots.length === 0) {
    return (
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
        </div>
      </div>
    );
  }

  return (
    <div className="plot-grid-container">
      <GridLayout
        className="plot-grid"
        layout={layout}
        cols={PLOT_CONFIG.GRID_COLS}
        rowHeight={PLOT_CONFIG.ROW_HEIGHT}
        width={1200}
        onLayoutChange={handleLayoutChange}
        draggableHandle=".plot-header"
        compactType={null}
        preventCollision={false}
      >
        {plots.map((plot) => (
          <div key={plot.id.toString()}>
            <MultiPVPlot plotId={plot.id} pvNames={plot.pvNames} />
          </div>
        ))}
      </GridLayout>
    </div>
  );
}
