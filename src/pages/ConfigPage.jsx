// src/pages/ConfigPage.jsx
import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { usePlotStore } from "../stores/usePlotStore";
import { configPresetUrl, energyConfigUrl } from "../utils/configApi";
import { DEFAULT_ENERGY_CONFIG } from "../utils/energy";
import { ionChamberGasPressurePV } from "../utils/ionChamber";

function objectOrEmpty(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

function diffSettings(previous, current) {
  const changes = {};
  const keys = new Set([...Object.keys(previous), ...Object.keys(current)]);
  keys.forEach((key) => {
    if (!Object.prototype.hasOwnProperty.call(current, key)) {
      changes[key] = null;
    } else if (
      !Object.prototype.hasOwnProperty.call(previous, key) ||
      JSON.stringify(previous[key]) !== JSON.stringify(current[key])
    ) {
      changes[key] = current[key];
    }
  });
  return changes;
}

function ConfigPage() {
  const navigate = useNavigate();

  // Get all the plots / live PVs from store
  const plots = usePlotStore((state) => state.plots);
  const livePVNames = usePlotStore((state) => state.livePVNames);
  const globalTimeWindow = usePlotStore((state) => state.globalTimeWindow);
  const activeConfigFile = usePlotStore((state) => state.activeConfigFile);
  const bumpSettingsRevision = usePlotStore(
    (state) => state.bumpSettingsRevision,
  );

  // Collect all monitored PV names (from plots + live list, de-duplicated)
  const plotPVNames = plots.flatMap((plot) => plot.pvNames);
  const displayedPVNames = Array.from(
    new Set([...plotPVNames, ...livePVNames]),
  );
  const gasPressurePVNames = Array.from(
    new Set(displayedPVNames.map(ionChamberGasPressurePV).filter(Boolean)),
  );
  const configPVNames = Array.from(
    new Set([...displayedPVNames, ...gasPressurePVNames]),
  );

  // Alias state (loaded from backend)
  const [aliases, setAliases] = useState({});

  const [selectedEgus, setSelectedEgus] = useState({});
  // Thresholds are kept as raw input strings ({ upper, lower } per PV)
  // so the user can type freely
  const [thresholds, setThresholds] = useState({});
  // "regular" or "exponential" per PV (missing means regular)
  const [valueFormats, setValueFormats] = useState({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [saveStatus, setSaveStatus] = useState("");
  const initialSettingsRef = useRef(null);

  // Shared settings for the <beamline>:MONO_CALC.ENERGY PV (calculated in routers/energy.py)
  const [energyConfig, setEnergyConfig] = useState(null);
  const [energySaveStatus, setEnergySaveStatus] = useState("");

  const handleEnergyConfigChange = (key, value) => {
    setEnergyConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleSaveEnergyConfig = async () => {
    if (!initialSettingsRef.current) return;
    try {
      setEnergySaveStatus("Saving...");
      const res = await fetch(energyConfigUrl(activeConfigFile), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(energyConfig),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      bumpSettingsRevision();
      setEnergySaveStatus("Saved! Re-add or reload energy PVs to apply.");
      setTimeout(() => setEnergySaveStatus(""), 4000);
    } catch (err) {
      console.error(err);
      setEnergySaveStatus("Save failed (PV names must not be empty)");
    }
  };

  const handleEguChange = (pvName, newEguValue) => {
    setSelectedEgus((prevEgus) => ({
      ...prevEgus,
      [pvName]: newEguValue, // Dynamically updates EGU for this specific PV
    }));
  };

  // bound is "upper" or "lower"
  const handleThresholdChange = (pvName, bound, newThreshold) => {
    setThresholds((prev) => ({
      ...prev,
      [pvName]: { upper: "", lower: "", ...prev[pvName], [bound]: newThreshold },
    }));
  };

  const handleValueFormatChange = (pvName, newFormat) => {
    setValueFormats((prev) => ({ ...prev, [pvName]: newFormat }));
  };

  // Load all settings from the active preset on page mount.
  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError("");
    initialSettingsRef.current = null;
    fetch(configPresetUrl(activeConfigFile))
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((config) => {
        if (!active) return;
        const asStrings = {};
        for (const [pvName, value] of Object.entries(
          objectOrEmpty(config.thresholds),
        )) {
          const threshold =
            typeof value === "number" ? { upper: value } : objectOrEmpty(value);
          asStrings[pvName] = {
            upper: threshold.upper != null ? String(threshold.upper) : "",
            lower: threshold.lower != null ? String(threshold.lower) : "",
          };
        }
        const loadedAliases = Object.fromEntries(
          Object.entries(objectOrEmpty(config.aliases)).filter(
            ([, value]) => typeof value === "string" && value,
          ),
        );
        const loadedEgus = Object.fromEntries(
          Object.entries(objectOrEmpty(config.egus)).filter(
            ([, value]) =>
              typeof value === "string" && value && value !== "default",
          ),
        );
        const loadedFormats = Object.fromEntries(
          Object.entries(objectOrEmpty(config.value_formats)).filter(
            ([, value]) => value === "exponential",
          ),
        );
        const savedThresholds = {};
        for (const [pvName, { upper, lower }] of Object.entries(asStrings)) {
          if (upper.trim() === "" && lower.trim() === "") continue;
          savedThresholds[pvName] = {};
          if (upper.trim() !== "") savedThresholds[pvName].upper = Number(upper);
          if (lower.trim() !== "") savedThresholds[pvName].lower = Number(lower);
        }
        initialSettingsRef.current = {
          aliases: loadedAliases,
          egus: loadedEgus,
          thresholds: savedThresholds,
          value_formats: loadedFormats,
        };
        setAliases(loadedAliases);
        setSelectedEgus(loadedEgus);
        setThresholds(asStrings);
        setValueFormats(loadedFormats);
        setEnergyConfig({
          ...DEFAULT_ENERGY_CONFIG,
          ...objectOrEmpty(config.energy),
        });
        setLoading(false);
      })
      .catch((err) => {
        if (active) {
          console.error(
            `Failed to load settings from ${activeConfigFile}:`,
            err,
          );
          setLoading(false);
          setLoadError(`Failed to load settings from ${activeConfigFile}.`);
        }
      });

    return () => {
      active = false;
    };
  }, [activeConfigFile, loadAttempt]);

  // Update alias locally while typing
  const handleAliasChange = (pvName, newAlias) => {
    setAliases((prev) => ({ ...prev, [pvName]: newAlias }));
  };

  // Save all edited settings to the active preset.
  const handleSave = async () => {
    if (!initialSettingsRef.current) return;

    // Validate thresholds before saving anything
    for (const [pvName, { upper, lower }] of Object.entries(thresholds)) {
      const upperTrimmed = upper.trim();
      const lowerTrimmed = lower.trim();
      if (upperTrimmed !== "" && !Number.isFinite(Number(upperTrimmed))) {
        setSaveStatus(`Invalid upper threshold for ${pvName}`);
        return;
      }
      if (lowerTrimmed !== "" && !Number.isFinite(Number(lowerTrimmed))) {
        setSaveStatus(`Invalid lower threshold for ${pvName}`);
        return;
      }
      if (
        upperTrimmed !== "" &&
        lowerTrimmed !== "" &&
        Number(lowerTrimmed) > Number(upperTrimmed)
      ) {
        setSaveStatus(`Lower threshold exceeds upper threshold for ${pvName}`);
        return;
      }
    }

    try {
      setSaveStatus("Saving...");

      const savedThresholds = {};
      for (const [pvName, { upper, lower }] of Object.entries(thresholds)) {
        const upperTrimmed = upper.trim();
        const lowerTrimmed = lower.trim();
        if (upperTrimmed === "" && lowerTrimmed === "") continue;
        savedThresholds[pvName] = {};
        if (upperTrimmed !== "") {
          savedThresholds[pvName].upper = Number(upperTrimmed);
        }
        if (lowerTrimmed !== "") {
          savedThresholds[pvName].lower = Number(lowerTrimmed);
        }
      }

      const currentSettings = {
        aliases: Object.fromEntries(
          Object.entries(aliases).filter(([, alias]) => Boolean(alias)),
        ),
        egus: Object.fromEntries(
          Object.entries(selectedEgus).filter(
            ([, egu]) => Boolean(egu) && egu !== "default",
          ),
        ),
        thresholds: savedThresholds,
        value_formats: Object.fromEntries(
          Object.entries(valueFormats).filter(
            ([, format]) => format === "exponential",
          ),
        ),
      };
      const updates = Object.fromEntries(
        Object.entries(currentSettings)
          .map(([section, settings]) => [
            section,
            diffSettings(initialSettingsRef.current[section] || {}, settings),
          ])
          .filter(([, changes]) => Object.keys(changes).length > 0),
      );
      if (Object.keys(updates).length === 0) {
        setSaveStatus("Saved!");
        setTimeout(() => setSaveStatus(""), 2000);
        return;
      }

      const res = await fetch(configPresetUrl(activeConfigFile), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      initialSettingsRef.current = currentSettings;
      bumpSettingsRevision();
      setSaveStatus("Saved!");
      setTimeout(() => setSaveStatus(""), 2000);
    } catch (err) {
      console.error(err);
      setSaveStatus("Save failed");
    }
  };

  if (loading) {
    return <div style={{ padding: "20px" }}>Loading configurations...</div>;
  }

  return (
    <div style={{ padding: "20px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "20px",
        }}
      >
        <div>
          <h1>Configurations</h1>
          <p>Saving settings to: {activeConfigFile}</p>
        </div>
        <button className="btn btn-secondary" onClick={() => navigate("/")}>
          ← Back to Plots
        </button>
      </div>
      {loadError && (
        <p role="alert">
          {loadError} Saving is disabled until the preset loads successfully.{" "}
          <button type="button" onClick={() => setLoadAttempt((n) => n + 1)}>
            Retry
          </button>
        </p>
      )}

      {/* Layout Info */}
      <section style={{ marginBottom: "30px" }}>
        <h2>Current Layout</h2>
        <p>Active plots: {plots.length}</p>
        <p>Monitored PVs: {configPVNames.length}</p>
        <p>Time window: {globalTimeWindow}s</p>
      </section>

      {/* PV Aliases */}
      <section>
        <h2>PV Aliases</h2>
        {configPVNames.length === 0 ? (
          <p>No PVs are being monitored. Add some PVs first.</p>
        ) : (
          <>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                maxWidth: "1100px",
              }}
            >
              <thead>
                <tr>
                  <th
                    style={{
                      textAlign: "left",
                      padding: "8px",
                      borderBottom: "2px solid #ccc",
                    }}
                  >
                    PV Name
                  </th>
                  <th
                    style={{
                      textAlign: "center",
                      padding: "8px",
                      borderBottom: "2px solid #ccc",
                    }}
                  >
                    In Plot?
                  </th>
                  <th
                    style={{
                      textAlign: "center",
                      padding: "8px",
                      borderBottom: "2px solid #ccc",
                    }}
                  >
                    Live Only
                  </th>
                  <th
                    style={{
                      textAlign: "left",
                      padding: "8px",
                      borderBottom: "2px solid #ccc",
                    }}
                  >
                    Alias (optional)
                  </th>
                  <th
                    style={{
                      textAlign: "left",
                      padding: "8px",
                      borderBottom: "2px solid #ccc",
                      minWidth: "160px",
                    }}
                  >
                    EGU
                  </th>
                  <th
                    style={{
                      textAlign: "left",
                      padding: "8px",
                      borderBottom: "2px solid #ccc",
                    }}
                  >
                    Lower Threshold (optional)
                  </th>
                  <th
                    style={{
                      textAlign: "left",
                      padding: "8px",
                      borderBottom: "2px solid #ccc",
                    }}
                  >
                    Upper Threshold (optional)
                  </th>
                  <th
                    style={{
                      textAlign: "left",
                      padding: "8px",
                      borderBottom: "2px solid #ccc",
                      minWidth: "130px",
                    }}
                  >
                    Value Format
                  </th>
                </tr>
              </thead>
              <tbody>
                {configPVNames.map((pvName) => {
                  const inPlot = plotPVNames.includes(pvName);
                  const liveOnly =
                    (livePVNames.includes(pvName) ||
                      gasPressurePVNames.includes(pvName)) &&
                    !inPlot;
                  return (
                    <tr key={pvName}>
                      <td
                        style={{
                          padding: "8px",
                          borderBottom: "2px solid #eee",
                        }}
                      >
                        {pvName}
                      </td>
                      <td
                        style={{
                          textAlign: "center",
                          padding: "8px",
                          borderBottom: "2px solid #eee",
                        }}
                      >
                        {inPlot ? (
                          <span style={{ color: "#22c55e", fontSize: "18px" }}>
                            ✓
                          </span>
                        ) : (
                          <span style={{ color: "#ef4444", fontSize: "18px" }}>
                            ✗
                          </span>
                        )}
                      </td>
                      <td
                        style={{
                          textAlign: "center",
                          padding: "8px",
                          borderBottom: "2px solid #eee",
                        }}
                      >
                        {liveOnly ? (
                          <span style={{ color: "#22c55e", fontSize: "18px" }}>
                            ✓
                          </span>
                        ) : (
                          <span style={{ color: "#ef4444", fontSize: "18px" }}>
                            ✗
                          </span>
                        )}
                      </td>
                      <td
                        style={{
                          padding: "8px",
                          borderBottom: "2px solid #eee",
                        }}
                      >
                        <input
                          type="text"
                          value={aliases[pvName] || ""}
                          onChange={(e) =>
                            handleAliasChange(pvName, e.target.value)
                          }
                          placeholder="(no alias)"
                          style={{ width: "100%", padding: "4px" }}
                        />
                      </td>
                      <td
                        style={{
                          padding: "8px",
                          borderBottom: "2px solid #eee",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                          }}
                        >
                          <span style={{ minWidth: "40px", color: "#666" }}>
                            {selectedEgus[pvName] &&
                            selectedEgus[pvName] !== "default"
                              ? selectedEgus[pvName]
                              : "—"}
                          </span>

                          <select
                            id={`egu-${pvName}`}
                            value={selectedEgus[pvName] || "default"}
                            onChange={(e) =>
                              handleEguChange(pvName, e.target.value)
                            }
                            style={{ width: "100%", padding: "4px" }}
                          >
                            <option value="default">Arb.</option>
                            <option value="mm">mm</option>
                            <option value="deg">deg</option>
                            <option value="Volts">Volts</option>
                            <option value="mA">mA</option>
                            <option value="Counts">Counts</option>
                            <option value="bar">bar</option>
                            <option value="eV">eV</option>
                          </select>
                        </div>
                      </td>
                      <td
                        style={{
                          padding: "8px",
                          borderBottom: "2px solid #eee",
                        }}
                      >
                        <input
                          type="text"
                          inputMode="decimal"
                          value={thresholds[pvName]?.lower ?? ""}
                          onChange={(e) =>
                            handleThresholdChange(
                              pvName,
                              "lower",
                              e.target.value,
                            )
                          }
                          placeholder="(no lower)"
                          style={{ width: "100%", padding: "4px" }}
                        />
                      </td>
                      <td
                        style={{
                          padding: "8px",
                          borderBottom: "2px solid #eee",
                        }}
                      >
                        <input
                          type="text"
                          inputMode="decimal"
                          value={thresholds[pvName]?.upper ?? ""}
                          onChange={(e) =>
                            handleThresholdChange(
                              pvName,
                              "upper",
                              e.target.value,
                            )
                          }
                          placeholder="(no upper)"
                          style={{ width: "100%", padding: "4px" }}
                        />
                      </td>
                      <td
                        style={{
                          padding: "8px",
                          borderBottom: "2px solid #eee",
                        }}
                      >
                        <select
                          id={`value-format-${pvName}`}
                          value={valueFormats[pvName] || "regular"}
                          onChange={(e) =>
                            handleValueFormatChange(pvName, e.target.value)
                          }
                          style={{ width: "100%", padding: "4px" }}
                        >
                          <option value="regular">Regular</option>
                          <option value="exponential">Exponential</option>
                        </select>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <div style={{ marginTop: "20px" }}>
              <button
                className="btn btn-primary"
                onClick={handleSave}
                disabled={Boolean(loadError) || !initialSettingsRef.current}
              >
                Save Configs
              </button>
              {saveStatus && (
                <span style={{ marginLeft: "10px" }}>{saveStatus}</span>
              )}
            </div>
          </>
        )}
      </section>

      {/* Energy calculation settings (used by the <beamline>:MONO_CALC.ENERGY PV) */}
      <section style={{ marginTop: "30px", maxWidth: "1100px" }}>
        <h2>Energy Calculation</h2>
        <p style={{ color: "#666" }}>
          E (eV) = 12398.42 / (2 · d · sin θ), with θ (deg) = REP × (UREV /
          EREV) + offset, read from the encoder's record (same as xas_bluesky). The result is
          the PV "&lt;beamline&gt;:MONO_CALC.ENERGY", which can be added with "Add Plot" or
          "Add Live PV" like any other PV. The encoder PV is set here.
        </p>
        {!energyConfig ? (
          <p>Energy settings could not be loaded.</p>
        ) : (
          <>
            <table style={{ borderCollapse: "collapse", width: "100%" }}>
              <tbody>
                {[
                  ["encoder_pv", "Encoder PV (raw counts, e.g. ...MOTOR1.REP)"],
                  ["d_spacing_pv", "D-spacing PV (Å)"],
                  ["offset_pv", "Encoder offset PV (degrees)"],
                ].map(([key, label]) => (
                  <tr key={key}>
                    <td style={{ padding: "8px", width: "280px" }}>{label}</td>
                    <td style={{ padding: "8px" }}>
                      <input
                        type="text"
                        value={energyConfig[key] ?? ""}
                        onChange={(e) =>
                          handleEnergyConfigChange(key, e.target.value)
                        }
                        style={{ width: "100%", padding: "4px" }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: "12px" }}>
              <button
                className="btn btn-primary"
                onClick={handleSaveEnergyConfig}
                disabled={Boolean(loadError) || !initialSettingsRef.current}
              >
                Save Energy Settings
              </button>
              {energySaveStatus && (
                <span style={{ marginLeft: "10px" }}>{energySaveStatus}</span>
              )}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

export default ConfigPage;
