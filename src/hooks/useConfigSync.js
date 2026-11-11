// src/hooks/useConfigSync.js
// Keep this browser in step with config.json on the server.
//
// The plot layout normally comes from localStorage, and aliases/EGUs/
// thresholds/value formats are fetched once on mount, so edits made from
// elsewhere (the epvpm CLI, another browser) would otherwise only show up
// after someone reloads the page on the display.
//
// Polls GET /api/config/version, which returns separate hashes for the
// layout and for everything else:
//   - layout changed   -> replace plots / Live PVs with the server layout
//   - settings changed -> bump settingsRevision so components re-fetch
// The first response only records a baseline, so a layout restored from
// localStorage on startup is left alone until the server copy changes.

import { useEffect } from "react";

import { usePlotStore } from "../stores/usePlotStore";
import { API_BASE } from "../utils/constants";

const POLL_INTERVAL_MS = 5000;

export function useConfigSync() {
  useEffect(() => {
    let last = null;
    let stopped = false;

    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/config/version`);
        if (!res.ok) return;
        const version = await res.json();

        if (last && !stopped) {
          if (version.layout !== last.layout) {
            const configRes = await fetch(`${API_BASE}/api/config`);
            // On failure keep the old baseline so the next tick retries
            if (!configRes.ok) return;
            const config = await configRes.json();
            const layout = config?.layouts?.default;
            if (layout && !stopped) {
              console.log("Server layout changed, reloading it");
              usePlotStore.getState().loadLayout(layout);
            }
          }
          if (version.settings !== last.settings) {
            console.log("Server settings changed, re-fetching them");
            usePlotStore.getState().bumpSettingsRevision();
          }
        }
        last = version;
      } catch {
        // Backend unreachable: try again next tick
      }
    };

    check();
    const timer = setInterval(check, POLL_INTERVAL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, []);
}
