"""Unit tests for calc/energy.py (pure math, no EPICS needed).

Run from the repo root:  python -m pytest tests/test_energy_calc.py
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calc.energy import (  # noqa: E402
    EnergyCalcError,
    bragg_energy_ev,
    encoder_angle_deg,
    energy_from_encoder,
)

SI111_D = 3.135601  # Angstrom, BL22:STORE:CRYSTAL_D


def test_cu_k_edge_with_si111():
    # Cu K-edge 8979 eV with Si(111) is at a Bragg angle of about 12.72 deg
    theta = math.degrees(math.asin(12398.419843320026 / (2 * SI111_D * 8979.0)))
    assert theta == pytest.approx(12.72, abs=0.01)
    assert bragg_energy_ev(theta, SI111_D) == pytest.approx(8979.0)


def test_offset_in_counts():
    assert encoder_angle_deg(1100, 0.01, 100, "counts") == pytest.approx(10.0)


def test_offset_in_degrees():
    assert encoder_angle_deg(1000, 0.01, 2.5, "deg") == pytest.approx(12.5)


def test_energy_from_encoder_matches_two_steps():
    theta = encoder_angle_deg(109184, 1.14329e-5, 10.75, "deg")
    assert energy_from_encoder(109184, 1.14329e-5, SI111_D, 10.75, "deg") == (
        pytest.approx(bragg_energy_ev(theta, SI111_D))
    )


@pytest.mark.parametrize("theta", [0.0, -5.0, 90.0001, 180.0])
def test_unphysical_bragg_angle_is_rejected(theta):
    with pytest.raises(EnergyCalcError):
        bragg_energy_ev(theta, SI111_D)


@pytest.mark.parametrize("bad", [None, "abc", float("nan"), float("inf")])
def test_bad_inputs_are_rejected(bad):
    with pytest.raises(EnergyCalcError):
        energy_from_encoder(bad, 1e-5, SI111_D)
    with pytest.raises(EnergyCalcError):
        energy_from_encoder(1000, 1e-5, bad)


def test_zero_d_spacing_is_rejected():
    with pytest.raises(EnergyCalcError):
        bragg_energy_ev(12.0, 0.0)


def test_unknown_offset_units_rejected():
    with pytest.raises(EnergyCalcError):
        encoder_angle_deg(1000, 1e-5, 0, "radians")
