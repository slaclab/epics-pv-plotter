#!/usr/bin/env python3
"""
Monochromator energy from a raw encoder reading (pure math, no EPICS).

    theta (deg) = (REP - offset) * ERES        offset in encoder counts
            or  =  REP * ERES + offset         offset in degrees
    E (eV)      = hc / (2 * d * sin(theta))    d in Angstrom

Used by routers/energy.py. Can also be run by hand to check a value:

    python -m calc.energy REP ERES D_SPACING [OFFSET] [counts|deg]
    python -m calc.energy 109184 1.14329e-5 3.135601 0 counts
"""

import math

# h*c in eV*Angstrom (CODATA 2018 exact values of h, c and e)
# eV·Å 
HC_EV_ANGSTROM = 12398.419843320026

OFFSET_UNITS = ("counts", "deg")


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


def encoder_angle_deg(rep, eres, offset=0.0, offset_units="counts"):
    """Bragg angle in degrees from raw encoder counts and resolution (deg/count)."""
    rep = _finite("REP", rep)
    eres = _finite("ERES", eres)
    offset = _finite("offset", offset)
    if offset_units == "counts":
        return (rep - offset) * eres
    if offset_units == "deg":
        return rep * eres + offset
    raise EnergyCalcError(
        f"offset_units must be one of {OFFSET_UNITS}, got {offset_units!r}"
    )


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


def energy_from_encoder(rep, eres, d_spacing, offset=0.0, offset_units="counts"):
    """Photon energy in eV straight from the encoder inputs."""
    theta = encoder_angle_deg(rep, eres, offset, offset_units)
    return bragg_energy_ev(theta, d_spacing)


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if not 3 <= len(args) <= 5:
        print(__doc__)
        sys.exit(1)
    rep, eres, d = args[:3]
    offset = args[3] if len(args) > 3 else 0.0
    units = args[4] if len(args) > 4 else "counts"
    try:
        theta = encoder_angle_deg(rep, eres, offset, units)
        energy = bragg_energy_ev(theta, d)
    except EnergyCalcError as e:
        print(f"error: {e}")
        sys.exit(2)
    print(f"theta  = {theta:.6f} deg")
    print(f"energy = {energy:.3f} eV")
