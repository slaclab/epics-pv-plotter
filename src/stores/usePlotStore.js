// src/stores/usePlotStore.js
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
<<<<<<< HEAD
=======
import { PLOT_CONFIG } from '../utils/constants';
>>>>>>> feature/work-space

let nextPlotId = 1;

export const usePlotStore = create(
  persist(
    (set, get) => ({
      plots: [],
      
      // Time synchronization settings
      timeSyncEnabled: true,
<<<<<<< HEAD
      globalTimeWindow: 60, // seconds to display (default 60s)
      
=======
      globalTimeWindow: 60,

      latestValues: {},

      // Update a single PV's latest value
      updateLatestValue: (pvName, value, timestamp) => {
        set((state) => ({
          latestValues: {
            ...state.latestValues,
            [pvName]: { value, timestamp }
          }
        }));
      },



>>>>>>> feature/work-space
      // Toggle time synchronization
      toggleTimeSync: () => {
        set((state) => ({
          timeSyncEnabled: !state.timeSyncEnabled
        }));
<<<<<<< HEAD
        console.log(`🕐 Time sync: ${get().timeSyncEnabled ? 'ON' : 'OFF'}`);
=======
        console.log(`Time sync: ${get().timeSyncEnabled ? 'ON' : 'OFF'}`);
>>>>>>> feature/work-space
      },
      
      // Set global time window
      setTimeWindow: (seconds) => {
        set({ globalTimeWindow: seconds });
<<<<<<< HEAD
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

=======
        console.log(`Time window set to: ${seconds}s`);
      },

      // Add plot with automatic layout calculation
      addPlot: (pvNames, width, height) => {
        const plots = get().plots;
        
        const newPlotWidth = PLOT_CONFIG.DEFAULT_WIDTH * width;
        const newPlotHeight = PLOT_CONFIG.DEFAULT_HEIGHT * height;
        
        // Find the best position for the new plot
        const position = findBestPosition(plots, newPlotWidth, newPlotHeight);
        
        const newPlot = {
          id: nextPlotId++,
          pvNames: Array.isArray(pvNames) ? pvNames : [pvNames],
          x: position.x,
          y: position.y,
          w: newPlotWidth,
          h: newPlotHeight
        };
        
        set({ plots: [...plots, newPlot] });
        console.log(`Plot added at (${newPlot.x}, ${newPlot.y}), size: ${newPlot.w}x${newPlot.h}`, newPlot);
      },

      // Remove Plot 
>>>>>>> feature/work-space
      removePlot: (plotId) => {
        set((state) => ({
          plots: state.plots.filter((plot) => plot.id !== plotId)
        }));
<<<<<<< HEAD
        console.log(`🗑️ Plot removed: ${plotId}`);
=======
        console.log(`Plot removed: ${plotId}`);
>>>>>>> feature/work-space
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
<<<<<<< HEAD
        console.log(`🗑️ PV removed: ${pvName} from plot ${plotId}`);
=======
        console.log(`PV removed: ${pvName} from plot ${plotId}`);
>>>>>>> feature/work-space
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
<<<<<<< HEAD
        console.log('🗑️ All plots cleared');
=======
        console.log('All plots cleared');
>>>>>>> feature/work-space
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
          
<<<<<<< HEAD
          console.log(`🔄 State rehydrated: ${state.plots.length} plots restored`);
          console.log(`📊 Next plot ID will be: ${nextPlotId}`);
=======
          console.log(`State rehydrated: ${state.plots.length} plots restored`);
          console.log(`Next plot ID will be: ${nextPlotId}`);
>>>>>>> feature/work-space
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
<<<<<<< HEAD
=======

// Helper function to find the best position for a new plot
function findBestPosition(existingPlots, width, height) {
  if (existingPlots.length === 0) {
    return { x: 0, y: 0 };
  }

  const gridCols = PLOT_CONFIG.GRID_COLS;
  
  // Try to place in rows, starting from y=0
  let currentRow = 0;
  
  while (true) {
    // Try each column position in this row
    for (let col = 0; col <= gridCols - width; col++) {
      const candidate = { x: col, y: currentRow };
      
      // Check if this position conflicts with any existing plot
      const hasConflict = existingPlots.some(plot => 
        rectanglesOverlap(
          candidate.x, candidate.y, width, height,
          plot.x, plot.y, plot.w, plot.h
        )
      );
      
      if (!hasConflict) {
        return candidate;
      }
    }
    
    // Move to next row
    currentRow += PLOT_CONFIG.DEFAULT_HEIGHT;
    
    // Safety check: don't go beyond reasonable rows
    if (currentRow > 100) {
      console.warn('Could not find position, placing at end');
      return { x: 0, y: currentRow };
    }
  }
}

// Helper function to check if two rectangles overlap
function rectanglesOverlap(x1, y1, w1, h1, x2, y2, w2, h2) {
  return !(
    x1 + w1 <= x2 ||  // rect1 is left of rect2
    x2 + w2 <= x1 ||  // rect2 is left of rect1
    y1 + h1 <= y2 ||  // rect1 is above rect2
    y2 + h2 <= y1     // rect2 is above rect1
  );
}
>>>>>>> feature/work-space
