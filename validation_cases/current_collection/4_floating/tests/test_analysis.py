"""Analysis math + policy wiring on synthetic fixtures (no WarpX/openPMD)."""

from pathlib import Path

import numpy as np
import pytest

import analyze
import ladder_contract as lc
from helpers import load_config

STAGE_DIR = Path(__file__).resolve().parents[1]
CONFIG = STAGE_DIR / "config.yaml"
POLICY = STAGE_DIR / "acceptance.yaml"


def _ledger(n=10, phi=-0.35, Ie=4.0e-9, Ii=4.0e-9, sp=500, dt=6e-11):
    rows = [(k * sp, k * sp * dt, phi, -1e-14, Ie, Ii) for k in range(1, n + 1)]
    return np.array(rows, dtype=[("step", float), ("t", float),
                                 ("phi_V", float), ("Q_C", float),
                                 ("I_e_A", float), ("I_i_A", float)])


def test_steady_tail_mean():
    cfg = load_config(CONFIG)   # steady_window_frac = 0.4
    d = _ledger(n=10)
    d["phi_V"][:6] = -0.1       # transient outside the tail
    assert analyze.steady(d, "phi_V", 0.4) == pytest.approx(-0.35)


def test_csv_charge_reconstructs_accumulation():
    d = _ledger(n=5, Ie=2.0e-9)
    q = analyze.csv_charge(d, "I_e_A", dt=6e-11)
    assert q == pytest.approx(2.0e-9 * 5 * 500 * 6e-11, rel=1e-12)


def test_late_slope_flat_plateau_is_zero():
    d = _ledger(n=20)
    assert analyze.late_slope(d) == pytest.approx(0.0, abs=1e-9)


def _metrics(**over):
    base = dict(phi_float_V=-0.30, current_balance=0.03,
                capacitance_over_analytic=1.05,
                scrape_charge_consistency=0.001,
                far_density_e_over_n0=1.0, quasineutrality=0.005,
                edge_phi_max_V=0.01)
    base.update(over)
    return {k: lc.Metric.measure(k, v, "-") for k, v in base.items()}


def test_expected_equilibrium_passes_policy():
    verdict = lc.evaluate_gates(_metrics(), lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail


def test_both_model_anchors_pass():
    cfg = load_config(CONFIG)
    for phi in (cfg.phi_float_thermal_ion, cfg.phi_float_oml_ion):
        verdict = lc.evaluate_gates(_metrics(phi_float_V=phi),
                                    lc.load_policy(POLICY))
        assert verdict.status == lc.V_PASS


def test_undercharged_sphere_fails():
    # a pump that loses electrons (e.g. sign error) never floats down
    verdict = lc.evaluate_gates(_metrics(phi_float_V=-0.05),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_overcharged_sphere_fails():
    verdict = lc.evaluate_gates(_metrics(phi_float_V=-0.8),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_broken_current_balance_fails():
    verdict = lc.evaluate_gates(_metrics(current_balance=0.5),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_bad_capacitance_fails():
    # a factor-2 C error (wrong Gauss face, double count) leaves the band
    verdict = lc.evaluate_gates(_metrics(capacitance_over_analytic=2.0),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_ledger_dump_disagreement_fails():
    verdict = lc.evaluate_gates(_metrics(scrape_charge_consistency=0.10),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_missing_metric_is_error_exit2():
    m = _metrics()
    del m["phi_float_V"]
    verdict = lc.evaluate_gates(m, lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2


def test_nonfinite_metric_is_error_exit2():
    verdict = lc.evaluate_gates(_metrics(phi_float_V=float("nan")),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2
