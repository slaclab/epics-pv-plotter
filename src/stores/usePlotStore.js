// src/stores/usePlotStore.js
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

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

      addPlot: (pvNames) => {
        const plots = get().plots;
        const newPlot = {
          id: nextPlotId++,
          pvNames: Array.isArray(pvNames) ? pvNames : [pvNames],
          x: (plots.length * 3) % 12,
          y: Math.floor((plots.length * 3) / 12) * 3,
          w: 6,
          h: 3
        };
        
        set({ plots: [...plots, newPlot] });
        console.log(`✅ Plot added:`, newPlot);
      },

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
