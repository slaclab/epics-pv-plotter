// src/components/BeamlineStatus.jsx
// Open/Closed status lights for every beamline, read from BLxx:OpenState.

import { useEffect, useState } from "react";
import { pvConnectionPool } from "../services/PVConnectionPool";
import { useLiveValueStore } from "../stores/useLiveValueStore";
import { API_BASE } from "../utils/constants";
import "./BeamlineStatus.css";

const BEAMLINE_COUNT = 17;

const BEAMLINES = Array.from({ length: BEAMLINE_COUNT }, (_, i) => {
  const number = String(i + 1).padStart(2, "0");
  return { number, pvName: `BL${number}:OpenState` };
});

// BLxx:OpenState is DBF_ENUM: [0] Closed, [1] Open.
// The gateway sends the enum index, but accept the string form too.
const toState = (value) => {
  if (value === 1 || value === "Open") return "open";
  if (value === 0 || value === "Closed") return "closed";
  return "unknown";
};

const STATE_LABELS = {
  open: "Open",
  closed: "Closed",
  unknown: "No data",
};

function BeamlineLight({ pvName }) {
  const valueInfo = useLiveValueStore(
    (state) => state.latestValues[pvName]
  );

  const state = toState(valueInfo?.value);

  return (
    <span title={`${pvName}: ${STATE_LABELS[state]}`}>
      <span
        className={`beamline-light beamline-light-${state}`}
        aria-hidden="true"
      />{" "}
      {STATE_LABELS[state]}
    </span>
  );
}

function BeamlineStatus() {
  const [spearMessages, setSpearMessages] = useState(null);
  const [spearTime, setSpearTime] = useState("");
  const [spearMessageError, setSpearMessageError] = useState("");

  useEffect(() => {
    const unsubscribers = BEAMLINES.map(({ pvName }) =>
      pvConnectionPool.subscribe(pvName, {
        // The connection pool updates useLiveValueStore.
        onData: () => {},

        onError: (error) => {
          console.error(
            `[BEAMLINE STATUS] Error for ${pvName}:`,
            error
          );
        },
      })
    );

    return () => unsubscribers.forEach((unsubscribe) => unsubscribe());
  }, []);

  useEffect(() => {
    let active = true;
    const loadMessages = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/spear-messages`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        if (!Array.isArray(data.messages) || typeof data.TIME !== "string") {
          throw new Error("The server returned an invalid SPEAR message list");
        }

        if (active) {
          setSpearMessages(data.messages);
          setSpearTime(data.TIME);
          setSpearMessageError("");
        }
      } catch (error) {
        if (active) {
          console.error("Failed to load SPEAR status messages:", error);
          setSpearMessageError("SPEAR messages are unavailable");
        }
      }
    };

    loadMessages();
    const refreshTimer = setInterval(loadMessages, 120_000);

    return () => {
      active = false;
      clearInterval(refreshTimer);
    };
  }, []);

  const visibleSpearMessages = (spearMessages ?? []).filter(
    (message) => message.message.trim() !== "",
  );

  return (
    <div className="beamline-status-panel">
      <table className="beamline-status-table">
        <tbody>
          <tr>
            <th scope="row">Beamline</th>
            {BEAMLINES.map(({ number }) => (
              <td key={number}>BL{number}</td>
            ))}
          </tr>
          <tr>
            <th scope="row">Status</th>
            {BEAMLINES.map(({ number, pvName }) => (
              <td key={number}>
                <BeamlineLight pvName={pvName} />
              </td>
            ))}
          </tr>
          {(spearMessageError ||
            spearMessages === null ||
            visibleSpearMessages.length > 0) && (
            <tr className="beamline-spear-message-row">
              <th scope="row">SPEAR</th>
              <td colSpan={BEAMLINES.length}>
                <div
                  className="beamline-spear-messages"
                  role={spearMessageError ? "alert" : "status"}
                  aria-live="polite"
                >
                  {spearMessageError ? (
                    spearMessageError
                  ) : spearMessages === null ? (
                    "Loading SPEAR messages..."
                  ) : (
                    <p className="beamline-spear-line">
                      <span className="beamline-spear-current-time">
                        <span className="beamline-spear-time-label">TIME:</span>
			  {/*<time>{spearTime}</time>*/}
                      </span>
                      {visibleSpearMessages.map((message, index) => (
                        <span
                          className="beamline-spear-message"
                          key={`${message.activationDate}-${index}`}
                        >
                          <time>{message.activationDate}</time>
                          <span>{message.message}</span>
                        </span>
                      ))}
                    </p>
                  )}
                </div>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default BeamlineStatus;
