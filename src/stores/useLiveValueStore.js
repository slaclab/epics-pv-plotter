// src/stores/useLiveValueStore.js
import { create } from "zustand";

export const useLiveValueStore = create((set) => ({
  latestValues: {},

  updateLatestValue: (pvName, value, timestamp) => {
    set((state) => ({
      latestValues: {
        ...state.latestValues,
        [pvName]: { value, timestamp },
      },
    }));
  },
}));
