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
//
// Two versions are tracked: `latest` (newest the server reported) and
// `applied` (what this browser has actually loaded). A layout change only
// counts as applied once the reload succeeds; a failed reload is retried,
// so a transient network error can't leave the display stale.
//
// The first message only sets the baseline, so a layout restored from
// localStorage on startup is left alone until the server copy changes.
// EventSource reconnects by itself if the backend restarts; a change made
// while disconnected is picked up from the first message after reconnecting.

import { useEffect } from "react";

import { usePlotStore } from "../stores/usePlotStore";
import { API_BASE } from "../utils/constants";

const RETRY_DELAY_MS = 3000;

export function useConfigSync() {
  useEffect(() => {
    let latest = null;
    let applied = null;
    let reloading = false;
    let retryTimer = null;
    let stopped = false;

    // Load the server layout until `applied` catches up with `latest`.
    // Only one reload runs at a time; a change that arrives during a reload
    // is handled right after it.
    const syncLayout = async () => {
      if (stopped || reloading || !latest || latest.layout === applied.layout) {
        return;
      }
      clearTimeout(retryTimer);
      retryTimer = null;
      reloading = true;
      const target = latest.layout;

      try {
        const res = await fetch(`${API_BASE}/api/config`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const config = await res.json();
        if (stopped) return;
        const layout = config?.layouts?.default;
        if (layout) {
          console.log("Server layout changed, reloading it");
          usePlotStore.getState().loadLayout(layout);
        }
        applied = { ...applied, layout: target };
      } catch (err) {
        console.error(
          `Failed to reload changed layout, retrying in ${RETRY_DELAY_MS / 1000}s:`,
          err,
        );
        if (!stopped) retryTimer = setTimeout(syncLayout, RETRY_DELAY_MS);
        return;
      } finally {
        reloading = false;
      }

      // Another change may have arrived while this reload was in flight
      syncLayout();
    };

    const source = new EventSource(`${API_BASE}/api/config/events`);

    source.onmessage = (event) => {
      let version;
      try {
        version = JSON.parse(event.data);
      } catch {
        return;
      }
      if (stopped) return;

      if (!applied) {
        latest = version;
        applied = version;
        return;
      }

      latest = version;

      if (version.settings !== applied.settings) {
        console.log("Server settings changed, re-fetching them");
        usePlotStore.getState().bumpSettingsRevision();
        applied = { ...applied, settings: version.settings };
      }

      syncLayout();
    };

    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      source.close();
    };
  }, []);
}
