import { API_BASE } from "./constants";

export const configPresetUrl = (filename) =>
  `${API_BASE}/api/config-presets/${encodeURIComponent(filename)}`;

export const energyConfigUrl = (filename) =>
  `${API_BASE}/api/energy-config?config_file=${encodeURIComponent(filename)}`;
