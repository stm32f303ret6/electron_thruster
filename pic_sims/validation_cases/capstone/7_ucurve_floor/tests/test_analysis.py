"""Analysis math + fail-closed policy wiring on synthetic CSV fixtures
(no WarpX, no openPMD)."""

import io
from pathlib import Path

import numpy as np
import pytest

import analyze
import ladder_contract as lc
from helpers import load_config

STAGE_DIR = Path(__file__).resolve().parents[1]
CONFIG = STAGE_DIR / "config.yaml"
POLICY = STAGE_DIR / "acceptance.yaml"


def _ledger_array(rows):
    """Build a numpy structured array shaped like contactor_log.csv."""
    names = ("step,t,phi_body,V_cathode,Q_body,I_cathode,I_body,I_escape,"
             "I_amb_e,I_amb_i,F_beam_N,F_net_N,pct_cathode,pct_body,"
             "pct_escape,pct_inflight,beam_escape_KE_mean").split(",")
    text = ",".join(names) + "\n" + "\n".join(
        ",".join(f"{row[k]:.6e}" for k in names) for row in rows)
    return np.atleast_1d(np.genfromtxt(io.StringIO(text), delimiter=",",
                                       names=True))


def _row(step, t, **over):
    base = dict(step=step, t=t, phi_body=16.0, V_cathode=-184.0, Q_body=1e-11,
                I_cathode=0.0, I_body=1e-6, I_escape=3.37e-4, I_amb_e=3.4e-4,
                I_amb_i=1.0e-6, F_beam_N=13.6e-9, F_net_N=1.0e-9,
                pct_cathode=0.1, pct_body=1.2, pct_escape=98.5,
                pct_inflight=0.2, beam_escape_KE_mean=146.0)
    base.update(over)
    return base


def _steady_ledger(n=50, dt=5.0e-12, win=100):
    return _ledger_array([_row((i + 1) * win, (i + 1) * win * dt)
                          for i in range(n)])


def test_steady_tail_mean():
    d = _steady_ledger()
    assert analyze.steady(d, "phi_body", 0.2) == pytest.approx(16.0)
    assert analyze.steady(d, "pct_escape", 0.2) == pytest.approx(98.5)


def test_steady_ignores_nan():
    rows = [_row((i + 1) * 100, (i + 1) * 100 * 5e-12) for i in range(10)]
    rows[-1]["beam_escape_KE_mean"] = float("nan")
    d = _ledger_array(rows)
    assert np.isfinite(analyze.steady(d, "beam_escape_KE_mean", 0.5))


def test_late_slope_flat_plateau_is_zero():
    d = _steady_ledger(n=200)
    assert analyze.late_slope(d, window_s=50e-9) == pytest.approx(0.0, abs=1e-6)


def test_csv_charge_reconstructs_accumulation():
    # 10 windows of 100 steps at constant current I: Q = I * 1000 * dt
    dt, win, I = 5.0e-12, 100, 3.4e-4
    d = _ledger_array([_row((i + 1) * win, (i + 1) * win * dt, I_amb_e=I)
                       for i in range(10)])
    assert analyze.csv_charge(d, "I_amb_e", dt) == pytest.approx(
        I * 10 * win * dt, rel=1e-12)


def test_csv_charge_handles_final_partial_window():
    # 3 full windows + a forced 60-step flush at end-of-run: the window length
    # comes from the step diff, so the integral stays exact.
    dt, I = 5.0e-12, 3.4e-4
    rows = [_row(100, 100 * dt, I_amb_e=I), _row(200, 200 * dt, I_amb_e=I),
            _row(300, 300 * dt, I_amb_e=I), _row(360, 360 * dt, I_amb_e=I)]
    d = _ledger_array(rows)
    assert analyze.csv_charge(d, "I_amb_e", dt) == pytest.approx(
        I * 360 * dt, rel=1e-12)


def _metrics(**over):
    # Plausible H1 values at 78 V / 0.840 mA: delivered thrust on the 13.65 nN
    # demand, float near +47.3 V (model/ucurve_targeting.py, pre-registered
    # in ../UCURVE_PLAN.md).
    base = dict(escape_fraction_pct=96.5, f_beam_nN=13.65, phi_body_V=47.3,
                current_balance=0.01, f_net_over_f_beam=0.1,
                edge_phi_max_V=0.2, scrape_charge_consistency=0.001,
                scrape_charge_consistency_beam_escape=0.001)
    base.update(over)
    return {k: lc.Metric.measure(k, v, "-") for k, v in base.items()}


def test_predicted_h1_values_pass_policy():
    verdict = lc.evaluate_gates(_metrics(), lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail


def test_h2_thrust_shortfall_is_a_finding_not_a_failure():
    # The perveance-tax hypothesis predicts delivered thrust short of demand;
    # thrust_meets_demand is required: false, so the run stays valid evidence.
    verdict = lc.evaluate_gates(_metrics(f_beam_nN=8.0), lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail
    gate = next(g for g in verdict.gates if g.id == "thrust_meets_demand")
    assert gate.status == lc.GATE_FAIL and not gate.required


def test_h2_escape_collapse_is_a_finding_not_a_failure():
    # Escape is THE measurement here (H1 >= 96 %, H2 collapse): reported only.
    verdict = lc.evaluate_gates(_metrics(escape_fraction_pct=40.0),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail
    gate = next(g for g in verdict.gates if g.id == "beam_escapes")
    assert gate.status == lc.GATE_FAIL and not gate.required


def test_high_float_is_a_finding_not_a_failure():
    verdict = lc.evaluate_gates(_metrics(phi_body_V=75.0), lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail
    gate = next(g for g in verdict.gates if g.id == "body_floats_benign")
    assert gate.status == lc.GATE_FAIL and not gate.required


def test_broken_current_balance_is_the_boundary_finding():
    # H2 predicts NO steady state at this demand; current balance is reported,
    # so a broken balance is the pre-registered finding, not a bad run.
    verdict = lc.evaluate_gates(_metrics(current_balance=0.5),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail
    gate = next(g for g in verdict.gates if g.id == "steady_current_balance")
    assert gate.status == lc.GATE_FAIL and not gate.required


def test_clipped_plume_fails_containment():
    verdict = lc.evaluate_gates(_metrics(edge_phi_max_V=3.0),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_ledger_dump_disagreement_fails():
    verdict = lc.evaluate_gates(_metrics(scrape_charge_consistency=0.10),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_beam_escape_ledger_dump_disagreement_fails():
    verdict = lc.evaluate_gates(
        _metrics(scrape_charge_consistency_beam_escape=0.10),
        lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_missing_required_metric_is_error_exit2():
    # edge_phi_max_V backs a REQUIRED gate; its absence is ERROR, not SKIP.
    m = _metrics()
    del m["edge_phi_max_V"]
    verdict = lc.evaluate_gates(m, lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2


def test_missing_reported_metric_is_skip_not_error():
    m = _metrics()
    del m["f_beam_nN"]
    verdict = lc.evaluate_gates(m, lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS
    gate = next(g for g in verdict.gates if g.id == "thrust_meets_demand")
    assert gate.status == lc.GATE_SKIP


def test_nonfinite_metric_is_error_exit2():
    verdict = lc.evaluate_gates(_metrics(f_net_over_f_beam=float("nan")),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2


def test_energy_ledger_math_on_synthetic_field():
    """energy_ledger interpolates phi at the injection plane; feed it a fake
    time series with a linear phi(z) ramp and check the interpolation."""
    cfg = load_config(CONFIG)
    geom = cfg.geometry()

    class FakeInfo:
        def __init__(self, r, z):
            self.r = r
            self.z = z
            self.axes = {0: "r", 1: "z"}

    class FakeTS:
        iterations = [100]

        def get_field(self, field, iteration, m, theta):
            r = np.arange(-cfg.nr, cfg.nr) * cfg.dx + cfg.dx / 2
            z = np.linspace(cfg.zmin, cfg.zmax, cfg.nz)
            F = np.tile(z * 1000.0, (len(r), 1))   # phi = 1000*z, r-independent
            return F, FakeInfo(r, z)

    led = analyze.energy_ledger(cfg, FakeTS(), tail_frac=0.2)
    assert led["phi_inject_axis_V"] == pytest.approx(1000.0 * geom.z_emit,
                                                     rel=1e-6)
    assert led["ke_pred_eV"] == pytest.approx(-1000.0 * geom.z_emit, rel=1e-6)
