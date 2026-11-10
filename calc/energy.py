#!/usr/bin/env python3
"""
Monochromator energy from a raw encoder reading (pure math, no EPICS).

Same calculation as xas_bluesky (libs/xas-bluesky: BaseEPICSMotor
._calc_encoder_position and utils/mono_utils.angle_to_energy):

    theta (deg) = REP * (UREV / EREV) + offset     offset in degrees
    E (eV)      = hc / (2 * d * sin(theta))        d in Angstrom

Used by routers/energy.py. Can also be run by hand to check a value:

    python -m calc.energy REP UREV EREV D_SPACING [OFFSET_DEG]
    python -m calc.energy 109046 360 31488000 3.135601 10.7538
"""

import math

# h*c in eV*Angstrom (CODATA 2018 exact values of h, c and e)
# eV·Å 
HC_EV_ANGSTROM = 12398.419843320026

# inherit ValueError to check the value
class EnergyCalcError(ValueError):
    """The inputs don't give a physical energy (missing, non-finite, theta outside (0, 90])."""


def _finite(name, value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise EnergyCalcError(f"{name} is not a number: {value!r}") from None
    if not math.isfinite(number):
        raise EnergyCalcError(f"{name} is not finite: {value!r}")
    return number


def encoder_angle_deg(rep, urev, erev, offset=0.0):
    """Bragg angle in degrees: REP * (UREV / EREV) + offset (deg)."""
    rep = _finite("REP", rep)
    urev = _finite("UREV", urev)
    erev = _finite("EREV", erev)
    offset = _finite("offset", offset)
    if urev == 0 or erev == 0:
        raise EnergyCalcError("UREV and EREV must be non-zero")
    return rep * (urev / erev) + offset


def bragg_energy_ev(theta_deg, d_spacing):
    """Photon energy in eV for Bragg angle theta (deg) and d-spacing (Angstrom)."""
    theta_deg = _finite("theta", theta_deg)
    d_spacing = _finite("d_spacing", d_spacing)
    if d_spacing <= 0:
        raise EnergyCalcError(f"d_spacing must be > 0, got {d_spacing}")
    # A Bragg angle is physical only in (0, 90] deg; outside that the encoder
    # offset/resolution is wrong. (Checking sin <= 0 alone would accept
    # 180 deg, whose float sine is ~1e-16, giving an absurd energy.)
    if not 0.0 < theta_deg <= 90.0:
        raise EnergyCalcError(f"theta = {theta_deg} deg is outside (0, 90] deg")
    return HC_EV_ANGSTROM / (2.0 * d_spacing * math.sin(math.radians(theta_deg)))


def energy_from_encoder(rep, urev, erev, d_spacing, offset=0.0):
    """Photon energy in eV straight from the encoder inputs."""
    theta = encoder_angle_deg(rep, urev, erev, offset)
    return bragg_energy_ev(theta, d_spacing)


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if not 4 <= len(args) <= 5:
        print(__doc__)
        sys.exit(1)
    rep, urev, erev, d = args[:4]
    offset = args[4] if len(args) > 4 else 0.0
    try:
        theta = encoder_angle_deg(rep, urev, erev, offset)
        energy = bragg_energy_ev(theta, d)
    except EnergyCalcError as e:
        print(f"error: {e}")
        sys.exit(2)
    print(f"theta  = {theta:.6f} deg")
    print(f"energy = {energy:.3f} eV")
