"""Analysis math + policy wiring on synthetic fixtures (no WarpX/openPMD).

The most valuable check here is that the metric IDs analyze.py emits line up
with the metric names acceptance.yaml references -- a realistic synthetic cohort
must evaluate to PASS, and a broken bracket must not."""

import dataclasses
from pathlib import Path

import numpy as np
import pytest
from scipy import constants as scc

import analyze
import ladder_contract as lc
from helpers import load_config, scenario_names

STAGE_DIR = Path(__file__).resolve().parents[1]
CONFIG = STAGE_DIR / "config.yaml"
POLICY = STAGE_DIR / "acceptance.yaml"

ORDER = scenario_names(CONFIG)


def test_ke_eV_roundtrip():
    E = 99.0
    p = np.sqrt(2 * scc.m_e * E * scc.e)
    assert analyze.ke_eV(np.array([0.0]), np.array([0.0]),
                         np.array([p]))[0] == pytest.approx(99.0, rel=1e-4)


def test_steady_currents_zero_bins_and_value():
    cfg = load_config(CONFIG, scenario="A_200v_anchor_drive")
    sp, dt = cfg.scrape_period, cfg.time_step
    cfg = dataclasses.replace(cfg, max_steps=3 * sp)
    it = np.array([sp, sp, 2 * sp])
    bnd = np.array(["zhi", "zhi", "eb"])
    w = np.array([1.0, 1.0, 0.5])
    s = {"it": it, "bnd": bnd, "w": w,
         "px": np.zeros(3), "py": np.zeros(3), "pz": np.zeros(3)}
    steps, hist, steady = analyze.steady_currents(s, cfg)
    assert list(steps) == [sp, 2 * sp, 3 * sp]
    assert hist["anode"][0] == 0.0  # zero bin present, not dropped
    assert hist["collector"][0] == pytest.approx(2.0 * scc.e / (sp * dt))
    assert hist["collector"][2] == 0.0 and hist["anode"][2] == 0.0


def _meas(coll, anode, cathode=0.0, ke_err=0.0, closure=0.0):
    return {"frac": {"collector": coll, "anode": anode, "cathode": cathode,
                     "radial": 0.0},
            "ke_err": ke_err, "ke_expect": 199.0, "closure": closure}


def test_realistic_cohort_passes_policy():
    # The measured shape (v2): all three scenarios transmit alike -- the
    # planar scale is conservative for this geometry, so C loses nothing.
    meas = {
        ORDER[0]: _meas(0.985, 0.012),
        ORDER[1]: _meas(0.988, 0.010),
        ORDER[2]: _meas(0.992, 0.006),
    }
    metrics = analyze.build_metrics(ORDER, {}, meas)
    verdict = lc.evaluate_gates(metrics, lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail


def test_voltage_dependent_transmission_fails_bracket():
    # The bracket claim is |A - B| <= 2 pp; a 5 pp spread must fail.
    meas = {
        ORDER[0]: _meas(0.99, 0.008),
        ORDER[1]: _meas(0.94, 0.055),
        ORDER[2]: _meas(0.992, 0.006),
    }
    metrics = analyze.build_metrics(ORDER, {}, meas)
    verdict = lc.evaluate_gates(metrics, lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_overperveance_transmission_loss_is_a_regression_now():
    # v1 EXPECTED C to lose current; the committed cohort refuted that
    # (C transmitted 0.9999).  Under v2 a C loss is a real defect.
    meas = {
        ORDER[0]: _meas(0.985, 0.012),
        ORDER[1]: _meas(0.988, 0.010),
        ORDER[2]: _meas(0.62, 0.10, cathode=0.25),
    }
    metrics = analyze.build_metrics(ORDER, {}, meas)
    verdict = lc.evaluate_gates(metrics, lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL
    flat = next(g for g in verdict.gates if g.id == "C_transmission_flat_vs_A")
    assert flat.status == lc.GATE_FAIL and flat.required


def test_nonfinite_metric_errors_policy():
    meas = {
        ORDER[0]: _meas(float("nan"), 0.012),
        ORDER[1]: _meas(0.988, 0.010),
        ORDER[2]: _meas(0.992, 0.006),
    }
    metrics = analyze.build_metrics(ORDER, {}, meas)
    verdict = lc.evaluate_gates(metrics, lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2


def test_cross_scenario_metrics():
    meas = {ORDER[0]: _meas(0.97, 0.03), ORDER[1]: _meas(0.95, 0.05),
            ORDER[2]: _meas(0.60, 0.10, cathode=0.28)}
    metrics = analyze.build_metrics(ORDER, {}, meas)
    assert metrics["transmission_spread_A_to_B"].value == pytest.approx(0.02)
    assert metrics["C_collector_drop_vs_A"].value == pytest.approx(0.37)
    assert metrics[f"{ORDER[2]}__cathode_fraction"].value == pytest.approx(0.28)
