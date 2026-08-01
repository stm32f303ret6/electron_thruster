"""Analysis math + policy wiring on synthetic fixtures (no WarpX/openPMD).

The most valuable check here is that the metric IDs analyze.py emits line up
with the metric names acceptance.yaml references -- a realistic synthetic cohort
must evaluate to PASS, and a broken demonstration must not."""

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
    cfg = load_config(CONFIG, scenario="A_low_current_small_hole")
    sp, dt = cfg.scrape_period, cfg.time_step
    # collector hits at both dumps; anode only at the 2nd.
    it = np.array([sp, sp, 2 * sp])
    bnd = np.array(["zhi", "zhi", "eb"])
    w = np.array([1.0, 1.0, 0.5])
    s = {"it": it, "bnd": bnd, "w": w,
         "px": np.zeros(3), "py": np.zeros(3), "pz": np.zeros(3)}
    steps, hist, steady = analyze.steady_currents(s, cfg)
    assert list(steps) == [sp, 2 * sp]
    assert hist["anode"][0] == 0.0  # zero bin present, not dropped
    assert hist["collector"][0] == pytest.approx(2.0 * scc.e / (sp * dt))


def _meas(coll, anode, ke_err=0.0, closure=0.0):
    return {"frac": {"collector": coll, "anode": anode, "cathode": 0.0,
                     "radial": 0.0},
            "ke_err": ke_err, "ke_expect": 99.0, "closure": closure}


def test_realistic_cohort_passes_policy():
    # A: stiff, ~all transmits; B: space-charge loss on the plate; C: restored.
    meas = {
        ORDER[0]: _meas(0.973, 0.027),
        ORDER[1]: _meas(0.80, 0.18),
        ORDER[2]: _meas(0.995, 0.004),
    }
    metrics = analyze.build_metrics(ORDER, {}, meas)
    verdict = lc.evaluate_gates(metrics, lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail


def test_broken_demonstration_fails_policy():
    # B does NOT lose current onto the plate -> the B gates must fail.
    meas = {
        ORDER[0]: _meas(0.973, 0.027),
        ORDER[1]: _meas(0.972, 0.028),   # no drop, no plate loss
        ORDER[2]: _meas(0.995, 0.004),
    }
    metrics = analyze.build_metrics(ORDER, {}, meas)
    verdict = lc.evaluate_gates(metrics, lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_nonfinite_metric_errors_policy():
    meas = {
        ORDER[0]: _meas(float("nan"), 0.027),
        ORDER[1]: _meas(0.80, 0.18),
        ORDER[2]: _meas(0.995, 0.004),
    }
    metrics = analyze.build_metrics(ORDER, {}, meas)
    verdict = lc.evaluate_gates(metrics, lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2


def test_cross_scenario_metrics():
    meas = {ORDER[0]: _meas(0.97, 0.03), ORDER[1]: _meas(0.80, 0.18),
            ORDER[2]: _meas(0.99, 0.005)}
    metrics = analyze.build_metrics(ORDER, {}, meas)
    assert metrics["collector_drop_A_to_B"].value == pytest.approx(0.17)
    assert metrics["anode_reduction_B_to_C"].value == pytest.approx(0.175)
