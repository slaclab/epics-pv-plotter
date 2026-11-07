// src/utils/energy.js
// The energy Live PV is named "<beamline>:MONO_CALC.ENERGY", e.g.
// "BL22:MONO_CALC.ENERGY". It is not a real EPICS PV (MONO_CALC marks it as
// calculated): the gateway calculates it from the encoder PV saved in
// /api/energy-config (routers/energy.py); the frontend only names and
// displays it.

// Must match ENERGY_SUFFIX and CALC_RECORD in routers/energy.py
export const ENERGY_SUFFIX = ".ENERGY";
export const CALC_RECORD = "MONO_CALC";
// Older name formats, still accepted so saved traces load. Their encoder is
// taken from the name instead of the energy config:
//   "<encoder record>.ENERGY"  e.g. "BL22:SCAN:MASTER:MOTOR1.ENERGY"
//   "ENERGY:<encoder PV>"
const LEGACY_PREFIX = "ENERGY:";

export const isEnergyPV = (pvName) =>
  pvName.endsWith(ENERGY_SUFFIX) || pvName.startsWith(LEGACY_PREFIX);

const isCalcEnergyPV = (pvName) =>
  pvName.endsWith(`:${CALC_RECORD}${ENERGY_SUFFIX}`);

// "BL22:SCAN:MASTER:MOTOR1.REP" or "...MOTOR1" -> "BL22:SCAN:MASTER:MOTOR1"
const recordOf = (name) => {
  const lastColon = name.lastIndexOf(":");
  const dot = name.indexOf(".", lastColon + 1);
  return dot === -1 ? name : name.slice(0, dot);
};

// Encoder PV to request from /ws/energy, or null for "BL22:MONO_CALC.ENERGY"
// (the gateway then uses encoder_pv from the energy config).
//   legacy "BL22:SCAN:MASTER:MOTOR1.ENERGY" -> "BL22:SCAN:MASTER:MOTOR1.REP"
//   legacy "ENERGY:<encoder PV>"            -> "<encoder PV>"
export const encoderOf = (pvName) => {
  if (pvName.startsWith(LEGACY_PREFIX)) return pvName.slice(LEGACY_PREFIX.length);
  if (isCalcEnergyPV(pvName)) return null;
  return `${recordOf(pvName)}.REP`;
};

// Add .REP when the user typed a record name without a field.
export const normalizeEncoderPV = (input) => {
  const name = input.trim();
  const lastPart = name.split(":").pop();
  return lastPart.includes(".") ? name : `${name}.REP`;
};

// Encoder PV "BL22:SCAN:MASTER:MOTOR1.REP" -> "BL22:MONO_CALC.ENERGY"
export const toEnergyPVName = (encoder) => {
  const beamline = encoder.trim().split(":")[0];
  return `${beamline}:${CALC_RECORD}${ENERGY_SUFFIX}`;
};

// Default label when no alias is set ("Show PV Names" still shows the full name):
//   "BL22:MONO_CALC.ENERGY"                 -> "Energy (BL22)"
//   legacy "BL22:SCAN:MASTER:MOTOR1.ENERGY" -> "Energy (MOTOR1)"
export const energyDisplayName = (pvName) => {
  if (isCalcEnergyPV(pvName)) return `Energy (${pvName.split(":")[0]})`;
  const record = recordOf(encoderOf(pvName)).split(":").pop();
  return `Energy (${record})`;
};

export const ENERGY_EGU = "eV";
