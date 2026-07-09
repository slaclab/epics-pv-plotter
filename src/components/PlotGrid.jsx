// src/components/PlotGrid.jsx
import { useMemo } from 'react';
import { Responsive, WidthProvider } from "react-grid-layout";

import { usePlotStore } from '../stores/usePlotStore';
import MultiPVPlot from './MultiPVPlot';
import { PLOT_CONFIG } from '../utils/constants';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import './PlotGrid.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

export default function PlotGrid() {
  const { plots, updateLayout } = usePlotStore();

  const layout = useMemo(() => 
    plots.map((plot) => ({
      i: plot.id.toString(),
      x: plot.x,
      y: plot.y,
      w: plot.w,
      h: plot.h,
      minW: 3,
      minH: 2,
      maxH: 6,        // Optional
    })), 
    [plots]
  );

  const handleLayoutChange = (newLayout) => {
    updateLayout(newLayout);
  };

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
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="plot-grid-container">
      <ResponsiveGridLayout
        className="plot-grid"
        layouts={{ lg: layout }}           // use layouts not layout
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={PLOT_CONFIG.ROW_HEIGHT}
        onLayoutChange={handleLayoutChange}
        draggableHandle=".plot-header"
        compactType="vertical"             // recommend vertical
        preventCollision={false}
        isDraggable={true}
        isResizable={true}
        margin={[16, 16]}
      >
        {plots.map((plot) => (
          <div key={plot.id.toString()}>
            <MultiPVPlot 
              plotId={plot.id} 
              pvNames={plot.pvNames} 
            />
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  );
}
