// src/stores/usePlotStore.js
import { create } from 'zustand';

export const usePlotStore = create((set) => ({
  plots: [],
  nextPlotId: 1,

  addPlot: (pvNames) =>
    set((state) => {
      // New plot configuration - full width, stacked vertically
      const newPlot = {
        id: state.nextPlotId,
        pvNames: Array.isArray(pvNames) ? pvNames : [pvNames],
        x: 0,                           // Always start at column 0 (left edge)
        y: state.plots.length * 4,      // Stack vertically (each plot is 4 rows)
        w: 12,                          // Full width (all 12 columns)
        h: 4                            // 4 rows height (taller for better visibility)
      };

      return {
        plots: [...state.plots, newPlot],
        nextPlotId: state.nextPlotId + 1
      };
    }),

  removePlot: (plotId) =>
    set((state) => ({
      plots: state.plots.filter((plot) => plot.id !== plotId)
    })),

  removePVFromPlot: (plotId, pvName) =>
    set((state) => ({
      plots: state.plots
        .map((plot) => {
          if (plot.id === plotId) {
            const newPvNames = plot.pvNames.filter((pv) => pv !== pvName);
            if (newPvNames.length === 0) return null;
            return { ...plot, pvNames: newPvNames };
          }
          return plot;
        })
        .filter(Boolean)
    })),

  updateLayout: (newLayout) =>
    set((state) => ({
      plots: state.plots.map((plot) => {
        const layoutItem = newLayout.find((item) => item.i === plot.id.toString());
        if (layoutItem) {
          return {
            ...plot,
            x: layoutItem.x,
            y: layoutItem.y,
            w: layoutItem.w,
            h: layoutItem.h
          };
        }
        return plot;
      })
    })),

  clearAll: () =>
    set(() => ({
      plots: [],
      nextPlotId: 1
    }))
}));
