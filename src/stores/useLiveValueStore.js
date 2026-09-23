// src/stores/useLiveValueStore.js
import { create } from "zustand";

export const useLiveValueStore = create((set) => ({
  latestValues: {},

  updateLatestValue: (pvName, value, timestamp) => {
    set((state) => ({
      latestValues: {
        ...state.latestValues,
        [pvName]: {
          value,
          timestamp,
        },
      },
    }));
  },

  removeLatestValue: (pvName) => {
    set((state) => {
      if (!(pvName in state.latestValues)) {
        return state;
      }

      const nextValues = {
        ...state.latestValues,
      };

      delete nextValues[pvName];

      return {
        latestValues: nextValues,
      };
    });
  },

  clearLatestValues: () => {
    set({
      latestValues: {},
    });
  },
}));
