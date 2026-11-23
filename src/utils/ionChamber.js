export function ionChamberGasPressurePV(pvName) {
  if (typeof pvName !== "string") return null;

  const parts = pvName.trim().split(":");
  if (parts.length < 2) return null;

  const beamline = parts[0].trim();
  if (!/^BL\d+$/i.test(beamline)) return null;

  const lastPart = parts[parts.length - 1].trim();
  const recordField = lastPart.split(".")[0];
  const match = /^ADC([123])$/i.exec(recordField);
  if (!match) return null;

  return `${beamline.toUpperCase()}:GAS.IC${match[1]}P`;
}
