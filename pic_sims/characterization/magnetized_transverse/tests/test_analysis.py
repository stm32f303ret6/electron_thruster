"""Analysis math + fail-closed policy wiring on synthetic fixtures
(no WarpX, no openPMD)."""

import io
from pathlib import Path

import numpy as np
import pytest

import analyze
import ladder_contract as lc

STAGE_DIR = Path(__file__).resolve().parents[1]
POLICY = STAGE_DIR / "acceptance.yaml"

COLS = ("step,t,phi_body,Q_body,I_emit,I_body,I_escape,I_amb_e,I_amb_i,"
        "F_beam_N,F_beam_y_N,F_net_N,F_lorentz_z_N,F_lorentz_y_N,"
        "F_lorentz_beam_z_N,F_thrust_N,pct_body,pct_escape,pct_inflight,"
        "beam_escape_KE_mean").split(",")


def _ledger_array(rows):
    text = ",".join(COLS) + "\n" + "\n".join(
        ",".join(f"{row[k]:.6e}" for k in COLS) for row in rows)
    return np.atleast_1d(np.genfromtxt(io.StringIO(text), delimiter=",", names=True))


def _row(step, t, **over):
    base = dict(step=step, t=t, phi_body=17.0, Q_body=1e-11, I_emit=3.42e-4,
                I_body=1e-6, I_escape=3.41e-4, I_amb_e=3.42e-4, I_amb_i=1.0e-6,
                F_beam_N=13.6e-9, F_beam_y_N=0.0, F_net_N=0.05e-9,
                F_lorentz_z_N=-0.5e-9, F_lorentz_y_N=0.0, F_lorentz_beam_z_N=-0.5e-9,
                F_thrust_N=14.1e-9, pct_body=0.3, pct_escape=99.5,
                pct_inflight=0.2, beam_escape_KE_mean=147.0)
    base.update(over)
    return base


def _steady_ledger(n=50, dt=3.67e-11, win=100):
    return _ledger_array([_row((i + 1) * win, (i + 1) * win * dt) for i in range(n)])


def test_steady_tail_mean():
    d = _steady_ledger()
    assert analyze.steady(d, "phi_body", 0.2) == pytest.approx(17.0)
    assert analyze.steady(d, "F_thrust_N", 0.2) == pytest.approx(14.1e-9)


def test_late_slope_flat_plateau_is_zero():
    d = _steady_ledger(n=2000)
    assert analyze.late_slope(d, window_s=50e-9) == pytest.approx(0.0, abs=1e-6)


def test_csv_charge_handles_final_partial_window():
    dt, I = 3.67e-11, 3.4e-4
    rows = [_row(100, 100 * dt, I_amb_e=I), _row(200, 200 * dt, I_amb_e=I),
            _row(260, 260 * dt, I_amb_e=I)]
    assert analyze.csv_charge(_ledger_array(rows), "I_amb_e", dt) == pytest.approx(
        I * 260 * dt, rel=1e-12)


def test_edge_phi_and_axis_probe_on_synthetic_field():
    x = np.linspace(-0.032, 0.032, 65)
    y = np.linspace(-0.032, 0.032, 65)
    z = np.linspace(-0.030, 0.042, 73)
    phi = np.zeros((65, 65, 73))
    phi[3, 10, 10] = 0.7                     # three nodes inside x_lo
    phi[20, 20, 69] = 0.9                    # three nodes inside z_hi
    phi[32, 32, 5:-5] = 1000.0 * z[5:-5]     # a ramp on the axis (interior only)
    assert analyze.edge_phi(phi) == pytest.approx(0.9)
    assert analyze.phi_on_axis(phi, x, y, z, 0.0025) == pytest.approx(2.5, rel=1e-6)


def _per(**over):
    base = dict(escape_fraction_pct=99.5, f_beam_nN=13.6, f_thrust_nN=13.6,
                f_lorentz_z_nN=0.0, f_lorentz_beam_z_nN=0.0,
                lorentz_correction_pct=0.0, phi_body_V=17.0, current_balance=0.01,
                f_net_over_f_beam=0.01, emitted_current_ratio=1.0,
                edge_phi_max_V=0.05, phi_inject_axis_V=16.0, ke_predicted_eV=148.5,
                scrape_charge_consistency=1e-6,
                scrape_charge_consistency_beam_escape=1e-6, c_float_pF=0.66,
                exhaust_ke_mean_eV=147.5, late_dphidt_V_per_ns=0.01)
    base.update(over)
    return {k: (v, "-", "synthetic") for k, v in base.items()}


def _cohort(**over):
    per = {"b0_control": _per(),
           "transverse_1x": _per(phi_body_V=17.5, lorentz_correction_pct=0.05),
           "transverse_10x": _per(phi_body_V=55.0, f_thrust_nN=11.8, f_beam_nN=11.3,
                                  lorentz_correction_pct=4.4,
                                  lorentz_reduced_consistency=0.1)}
    for scn, changes in over.items():
        per[scn].update({k: (v, "-", "synthetic") for k, v in changes.items()})
    return per


def test_cross_metrics_are_deltas_against_the_control():
    cross = analyze.cross_metrics(_cohort())
    assert cross["dphi_1x_V"][0] == pytest.approx(0.5)
    assert cross["dphi_10x_V"][0] == pytest.approx(38.0)
    assert cross["dthrust_10x_pct"][0] == pytest.approx((11.8 / 13.6 - 1) * 100)
    assert cross["descape_1x_pp"][0] == pytest.approx(0.0)


def test_full_cohort_passes_policy():
    metrics = analyze.build_metrics(_cohort(), {})
    verdict = lc.evaluate_gates(metrics, lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail
    reported = {g.id: g.status for g in verdict.gates if not g.required}
    assert reported["t1x_null_float"] == lc.GATE_PASS
    assert reported["t10x_float_tax_in_band"] == lc.GATE_PASS
    assert reported["t10x_benign_float"] == lc.GATE_FAIL     # 55 V: flagged, not failing


def test_missing_scenario_is_error_exit2():
    per = _cohort()
    del per["transverse_10x"]
    verdict = lc.evaluate_gates(analyze.build_metrics(per, {}), lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2


def test_source_shortfall_fails():
    verdict = lc.evaluate_gates(
        analyze.build_metrics(_cohort(transverse_1x=dict(emitted_current_ratio=0.9)), {}),
        lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_bad_capacitance_fails():
    verdict = lc.evaluate_gates(
        analyze.build_metrics(_cohort(b0_control=dict(c_float_pF=3.0)), {}),
        lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_ledger_dump_disagreement_fails():
    verdict = lc.evaluate_gates(
        analyze.build_metrics(_cohort(transverse_10x=dict(scrape_charge_consistency=0.1)), {}),
        lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_nonfinite_required_metric_is_error():
    verdict = lc.evaluate_gates(
        analyze.build_metrics(_cohort(b0_control=dict(current_balance=float("nan"))), {}),
        lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2


def test_reduced_momentum_parser(tmp_path):
    red = tmp_path / "reducedfiles"; red.mkdir()
    hdr = ("#[0]step() [1]time(s) [2]total_x(kg*m/s) [3]total_y(kg*m/s) [4]total_z(kg*m/s) "
           "[5]beam_electrons_x(kg*m/s) [6]beam_electrons_y(kg*m/s) [7]beam_electrons_z(kg*m/s) "
           "[8]ambient_electrons_x(kg*m/s) [9]ambient_electrons_y(kg*m/s) [10]ambient_electrons_z(kg*m/s) "
           "[11]ambient_ions_x(kg*m/s) [12]ambient_ions_y(kg*m/s) [13]ambient_ions_z(kg*m/s)\n")
    (red / "particle_momentum.txt").write_text(
        hdr + "100 3.67e-9 0 0 0 1 2 3 4 5 6 7 8 9\n200 7.34e-9 0 0 0 1 2 3 4 5 6 7 8 9\n")
    t, P = analyze.reduced_momentum(tmp_path)
    assert t.tolist() == pytest.approx([3.67e-9, 7.34e-9])
    assert P["beam_electrons"][1].tolist() == [2.0, 2.0]
    assert P["ambient_ions"][2].tolist() == [9.0, 9.0]
