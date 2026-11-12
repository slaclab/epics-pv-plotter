// src/hooks/useConfigSync.js
// Keep this browser in step with config.json on the server.
//
// The plot layout normally comes from localStorage, and aliases/EGUs/
// thresholds/value formats are fetched once on mount, so edits made from
// elsewhere (the epvpm CLI, another browser) would otherwise only show up
// after someone reloads the page on the display.
//
// Listens to GET /api/config/events (Server-Sent Events). The server sends
// separate hashes for the layout and for everything else, once on connect
// and again whenever config.json changes:
//   - layout changed   -> replace plots / Live PVs with the server layout
//   - settings changed -> bump settingsRevision so components re-fetch
// The first message only records a baseline, so a layout restored from
// localStorage on startup is left alone until the server copy changes.
// EventSource reconnects by itself if the backend restarts; a change made
// while disconnected is picked up from the first message after reconnecting.

import { useEffect } from "react";

import { usePlotStore } from "../stores/usePlotStore";
import { API_BASE } from "../utils/constants";

export function useConfigSync() {
  useEffect(() => {
    let last = null;
    let stopped = false;
    const source = new EventSource(`${API_BASE}/api/config/events`);

    let reloadSequence = 0;
    const reloadLayout = async () => {
      const sequence = ++reloadSequence;
      try {
        const res = await fetch(`${API_BASE}/api/config`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const config = await res.json();
        const layout = config?.layouts?.default;
        if (layout && !stopped && sequence === reloadSequence) {
          console.log("Server layout changed, reloading it");
          usePlotStore.getState().loadLayout(layout);
        }
      } catch (err) {
        console.error("Failed to reload changed layout:", err);
      }
    };

    source.onmessage = (event) => {
      let version;
      try {
        version = JSON.parse(event.data);
      } catch {
        return;
      }

      if (last && !stopped) {
        if (version.layout !== last.layout) reloadLayout();
        if (version.settings !== last.settings) {
          console.log("Server settings changed, re-fetching them");
          usePlotStore.getState().bumpSettingsRevision();
        }
      }
      last = version;
    };

    return () => {
      stopped = true;
      source.close();
    };
  }, []);
}
