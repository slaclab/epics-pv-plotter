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


def test_offset_in_degrees_added_after_scaling():
    # Same as xas_bluesky: REP * (UREV / EREV) + offset
    assert encoder_angle_deg(1000, 360, 36000, 2.5) == pytest.approx(12.5)


def test_bl22_live_values():
    # BL22:SCAN:MASTER:MOTOR1 on 2026-11-09: REP 109046, UREV 360,
    # EREV 31488000, RBV 12.00052 deg -> offset ~10.7538 deg, ~9508.6 eV
    theta = encoder_angle_deg(109046, 360, 31488000, 10.7538)
    assert theta == pytest.approx(12.0005, abs=1e-3)
    assert energy_from_encoder(109046, 360, 31488000, SI111_D, 10.7538) == (
        pytest.approx(bragg_energy_ev(theta, SI111_D))
    )
    assert bragg_energy_ev(theta, SI111_D) == pytest.approx(9508.6, abs=0.5)


@pytest.mark.parametrize("theta", [0.0, -5.0, 90.0001, 180.0])
def test_unphysical_bragg_angle_is_rejected(theta):
    with pytest.raises(EnergyCalcError):
        bragg_energy_ev(theta, SI111_D)


@pytest.mark.parametrize("bad", [None, "abc", float("nan"), float("inf")])
def test_bad_inputs_are_rejected(bad):
    with pytest.raises(EnergyCalcError):
        energy_from_encoder(bad, 360, 31488000, SI111_D, 10.0)
    with pytest.raises(EnergyCalcError):
        energy_from_encoder(1000, 360, 31488000, bad, 10.0)


def test_zero_d_spacing_is_rejected():
    with pytest.raises(EnergyCalcError):
        bragg_energy_ev(12.0, 0.0)


@pytest.mark.parametrize("urev, erev", [(0, 31488000), (360, 0)])
def test_zero_urev_or_erev_is_rejected(urev, erev):
    with pytest.raises(EnergyCalcError):
        encoder_angle_deg(1000, urev, erev, 10.0)
