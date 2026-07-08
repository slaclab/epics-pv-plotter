// src/stores/usePlotStore.js
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { PLOT_CONFIG } from '../utils/constants';

let nextPlotId = 1;

export const usePlotStore = create(
  persist(
    (set, get) => ({
      plots: [],
      
      // Time synchronization settings
      timeSyncEnabled: true,
      globalTimeWindow: 60, // seconds to display (default 60s)
      
      // Toggle time synchronization
      toggleTimeSync: () => {
        set((state) => ({
          timeSyncEnabled: !state.timeSyncEnabled
        }));
        console.log(`🕐 Time sync: ${get().timeSyncEnabled ? 'ON' : 'OFF'}`);
      },
      
      // Set global time window
      setTimeWindow: (seconds) => {
        set({ globalTimeWindow: seconds });
        console.log(`🕐 Time window set to: ${seconds}s`);
      },

      // add plot layout
      
      addPlot: (pvNames) => {
        const plots = get().plots;
        
        // calculate number of Plots per row
        const plotsPerRow = Math.floor(PLOT_CONFIG.GRID_COLS / PLOT_CONFIG.DEFAULT_WIDTH);
        // 12 / 4 = 3 ( 3 plots)
        
        const plotIndex = plots.length;
        
        const newPlot = {
          id: nextPlotId++,
          pvNames: Array.isArray(pvNames) ? pvNames : [pvNames],
          
          // ✅ get the precise position of each plot
          x: (plotIndex % plotsPerRow) * PLOT_CONFIG.DEFAULT_WIDTH,
          y: Math.floor(plotIndex / plotsPerRow) * PLOT_CONFIG.DEFAULT_HEIGHT,
          
          w: PLOT_CONFIG.DEFAULT_WIDTH,   // 4
          h: PLOT_CONFIG.DEFAULT_HEIGHT   // 3
        };
        
        set({ plots: [...plots, newPlot] });
        console.log(`✅ Plot added at (${newPlot.x}, ${newPlot.y}):`, newPlot);
      },

      // Remove Plot 
      removePlot: (plotId) => {
        set((state) => ({
          plots: state.plots.filter((plot) => plot.id !== plotId)
        }));
        console.log(`🗑️ Plot removed: ${plotId}`);
      },

      removePVFromPlot: (plotId, pvName) => {
        set((state) => ({
          plots: state.plots.map((plot) => {
            if (plot.id === plotId) {
              const updatedPVs = plot.pvNames.filter((pv) => pv !== pvName);
              return updatedPVs.length > 0
                ? { ...plot, pvNames: updatedPVs }
                : null;
            }
            return plot;
          }).filter(Boolean)
        }));
        console.log(`🗑️ PV removed: ${pvName} from plot ${plotId}`);
      },

      updateLayout: (newLayout) => {
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
        }));
      },

      clearAll: () => {
        set({ plots: [] });
        nextPlotId = 1;
        console.log('🗑️ All plots cleared');
      }
    }),
    {
      name: 'epics-plot-storage',
      storage: createJSONStorage(() => localStorage),
      
      onRehydrateStorage: () => (state) => {
        if (state) {
          const maxId = state.plots.reduce((max, plot) => 
            Math.max(max, plot.id), 0
          );
          nextPlotId = maxId + 1;
          
          console.log(`🔄 State rehydrated: ${state.plots.length} plots restored`);
          console.log(`📊 Next plot ID will be: ${nextPlotId}`);
        }
      },
      
      partialize: (state) => ({ 
        plots: state.plots,
        timeSyncEnabled: state.timeSyncEnabled,
        globalTimeWindow: state.globalTimeWindow
      })
    }
  )
);
