"""Analysis math + fail-closed policy wiring on synthetic fixtures.

No WarpX and no openPMD: the ledger is a synthetic CSV array and the metric
dictionary is built directly, so every gate in acceptance.yaml can be flipped
individually and shown to fail.  A gate that has never been seen to fail is not
known to be wired up.
"""

import io
import math
from pathlib import Path

import numpy as np
import pytest
import yaml

import analyze
import ladder_contract as lc
from helpers import load_config, scenario_names

STAGE_DIR = Path(__file__).resolve().parents[1]
CONFIG = STAGE_DIR / "config.yaml"
POLICY = STAGE_DIR / "acceptance.yaml"

ORDER = ["A_day_p95", "B_night_worst"]


# ======================================================================
# synthetic ledger
# ======================================================================

_COLS = ("step,t,phi_body,V_cathode,Q_body,I_cathode,I_body,I_escape,"
         "I_amb_e,I_amb_i,F_beam_N,F_net_N,pct_cathode,pct_body,"
         "pct_escape,pct_inflight,beam_escape_KE_mean").split(",")


def _ledger_array(rows):
    text = ",".join(_COLS) + "\n" + "\n".join(
        ",".join(f"{row[k]:.6e}" for k in _COLS) for row in rows)
    return np.atleast_1d(np.genfromtxt(io.StringIO(text), delimiter=",",
                                       names=True))


def _row(step, t, **over):
    base = dict(step=step, t=t, phi_body=26.35, V_cathode=-273.65, Q_body=1e-11,
                I_cathode=0.0, I_body=1e-6, I_escape=6.367e-4, I_amb_e=6.38e-4,
                I_amb_i=1.3e-6, F_beam_N=31.57e-9, F_net_N=1.0e-9,
                pct_cathode=0.1, pct_body=1.3, pct_escape=98.4,
                pct_inflight=0.2, beam_escape_KE_mean=220.6)
    base.update(over)
    return base


def _ledger(n=50, dt=4.1354e-12, win=6045, **over):
    return _ledger_array([_row((i + 1) * win, (i + 1) * win * dt, **over)
                          for i in range(n)])


# ======================================================================
# the readers
# ======================================================================

def test_steady_takes_the_tail_mean():
    d = _ledger()
    assert analyze.steady(d, "phi_body", 0.2) == pytest.approx(26.35)
    assert analyze.steady(d, "pct_escape", 0.2) == pytest.approx(98.4)


def test_steady_ignores_the_transient():
    rows = [_row(i * 100, i * 100 * 4e-12, phi_body=(1.0 if i < 40 else 26.35))
            for i in range(1, 51)]
    d = _ledger_array(rows)
    assert analyze.steady(d, "phi_body", 0.2) == pytest.approx(26.35)


def test_late_slope_is_zero_on_a_flat_plateau():
    assert analyze.late_slope(_ledger(), window_s=1e-7) == pytest.approx(0.0, abs=1e-6)


def test_late_slope_catches_a_still_climbing_float():
    rows = [_row(i * 1000, i * 1000 * 4e-12, phi_body=20.0 + 0.01 * i)
            for i in range(1, 101)]
    d = _ledger_array(rows)
    slope = analyze.late_slope(d, window_s=1e-7)
    assert slope > 0.0


def test_csv_charge_reconstructs_the_integral():
    """Each row records acc/win, so I*win must re-sum to the accumulated charge."""
    dt, win, n, I = 4.0e-12, 100, 50, 1.0e-3
    d = _ledger_array([_row((i + 1) * win, (i + 1) * win * dt, I_amb_e=I)
                       for i in range(n)])
    assert analyze.csv_charge(d, "I_amb_e", dt) == pytest.approx(I * n * win * dt)


def test_observed_settle_time_finds_the_1_minus_1_over_e_crossing():
    phi_final = 50.0
    target = (1.0 - 1.0 / math.e) * phi_final
    rows = [_row(i * 100, i * 1e-9, phi_body=min(phi_final, 2.0 * i))
            for i in range(1, 51)]
    d = _ledger_array(rows)
    t = analyze.observed_settle_time_s(d, phi_final)
    assert np.isfinite(t)
    idx = int(np.nonzero(np.atleast_1d(d["phi_body"]) >= target)[0][0])
    assert t == pytest.approx(float(np.atleast_1d(d["t"])[idx]))


def test_observed_settle_time_is_nan_when_the_float_never_gets_there():
    d = _ledger(phi_body=1.0)
    assert math.isnan(analyze.observed_settle_time_s(d, 50.0))


# ======================================================================
# the policy: every gate flipped
# ======================================================================

def _passing_metrics():
    """A metric dict that satisfies every gate in acceptance.yaml."""
    cfgs = {n: load_config(CONFIG, n) for n in ORDER}
    m = {}

    def add(mid, value, unit="-"):
        m[mid] = lc.Metric.measure(mid, value, unit)

    for name in ORDER:
        cfg = cfgs[name]
        p = f"{name}__"
        pred = cfg.predicted
        add(p + "current_balance", 0.03)
        add(p + "f_net_over_f_beam", 0.004)
        add(p + "edge_phi_max_V", 0.04, "V")
        add(p + "scrape_charge_consistency", 3e-9)
        add(p + "scrape_charge_consistency_beam_escape", 5e-9)
        add(p + "phi_body_V", float(pred["phi_body_V"]), "V")
        add(p + "f_beam_nN", float(pred["f_beam_nN"]), "nN")
        add(p + "escape_fraction_pct", 98.4, "%")
        add(p + "f_beam_over_pred", 1.0)
        add(p + "phi_body_over_pred", 1.0)
        add(p + "prediction_consistency", 0.0)
    add("day_minus_night_f_beam_nN",
        float(cfgs[ORDER[0]].predicted["f_beam_nN"])
        - float(cfgs[ORDER[1]].predicted["f_beam_nN"]), "nN")
    add("beta_log_spread", 0.0)
    return m


def test_the_policy_parses_and_is_this_stage():
    policy = lc.load_policy(POLICY)
    assert policy.stage_id == "capstone.mission_envelope"
    assert policy.policy_id == "capstone.mission_envelope.v1"
    assert policy.evidence_kind == "model_validation"
    assert len(policy.gates) == 22


def test_the_policy_covers_both_scenarios_symmetrically():
    """An asymmetric policy would gate one scenario harder than the other."""
    policy = lc.load_policy(POLICY)
    suffixes = {"A": set(), "B": set()}
    cross = set()
    for g in policy.gates:
        if g.metric_id.startswith("A_day_p95__"):
            suffixes["A"].add(g.metric_id.split("__", 1)[1])
        elif g.metric_id.startswith("B_night_worst__"):
            suffixes["B"].add(g.metric_id.split("__", 1)[1])
        else:
            cross.add(g.metric_id)
    assert suffixes["A"] == suffixes["B"]
    assert len(suffixes["A"]) == 10
    assert cross == {"day_minus_night_f_beam_nN", "beta_log_spread"}


def test_the_reference_metrics_pass_every_gate():
    verdict = lc.evaluate_gates(_passing_metrics(), lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail
    assert verdict.exit_code == lc.EXIT_PASS


#: One out-of-bounds value per gated metric.  Kept as a named table so the
#: coverage test below can prove no gate was left unflipped.
_FLIPS = [
    # theory / identity
    ("A_day_p95__current_balance", 0.2),
    ("B_night_worst__current_balance", 0.2),
    ("A_day_p95__f_net_over_f_beam", 1.5),
    ("B_night_worst__f_net_over_f_beam", 1.5),
    ("A_day_p95__edge_phi_max_V", 2.0),
    ("B_night_worst__edge_phi_max_V", 2.0),
    ("A_day_p95__scrape_charge_consistency", 0.1),
    ("B_night_worst__scrape_charge_consistency", 0.1),
    ("A_day_p95__scrape_charge_consistency_beam_escape", 0.1),
    ("B_night_worst__scrape_charge_consistency_beam_escape", 0.1),
    # model validation
    ("A_day_p95__f_beam_over_pred", 1.25),
    ("B_night_worst__f_beam_over_pred", 0.75),
    ("A_day_p95__phi_body_over_pred", 1.30),
    ("B_night_worst__phi_body_over_pred", 0.70),
    ("A_day_p95__escape_fraction_pct", 90.0),
    ("B_night_worst__escape_fraction_pct", 90.0),
    ("A_day_p95__phi_body_V", 80.0),
    ("B_night_worst__phi_body_V", 80.0),
    ("A_day_p95__prediction_consistency", 1e-6),
    ("B_night_worst__prediction_consistency", 1e-6),
    # cross-scenario
    ("day_minus_night_f_beam_nN", 5.0),
    ("beta_log_spread", 0.5),
]


@pytest.mark.parametrize("metric_id,bad_value", _FLIPS)
def test_every_gate_can_fail(metric_id, bad_value):
    m = _passing_metrics()
    m[metric_id] = lc.Metric.measure(metric_id, bad_value, m[metric_id].unit)
    verdict = lc.evaluate_gates(m, lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL, f"{metric_id}={bad_value} did not fail"
    assert verdict.exit_code == lc.EXIT_FAIL
    failed = [g.id for g in verdict.gates if g.status == lc.GATE_FAIL]
    assert len(failed) == 1, f"expected exactly one failure, got {failed}"


def test_every_gated_metric_is_covered_by_the_flip_table():
    """A gate nobody has flipped is a gate nobody knows is wired up."""
    policy = lc.load_policy(POLICY)
    gated = {g.metric_id for g in policy.gates}
    flipped = {metric_id for metric_id, _ in _FLIPS}
    assert gated == flipped
    assert len(_FLIPS) == len(gated), "a metric is flipped twice"


def test_a_missing_metric_errors_rather_than_passes():
    """Fail-closed: a required gate whose metric never arrived is exit 2."""
    m = _passing_metrics()
    del m["B_night_worst__phi_body_over_pred"]
    verdict = lc.evaluate_gates(m, lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR
    assert verdict.exit_code == lc.EXIT_ERROR


def test_a_nonfinite_metric_errors_rather_than_passes():
    m = _passing_metrics()
    m["A_day_p95__f_beam_over_pred"] = lc.Metric.measure(
        "A_day_p95__f_beam_over_pred", float("nan"), "-")
    verdict = lc.evaluate_gates(m, lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR


def test_the_tolerances_are_the_ones_the_readme_documents():
    """Tolerances are the claim; a silent edit must break a test."""
    policy = lc.load_policy(POLICY)
    by_id = {g.id: g for g in policy.gates}
    for prefix in ("A", "B"):
        assert by_id[f"{prefix}_thrust_matches_prediction"].tolerance == 0.20
        assert by_id[f"{prefix}_float_matches_prediction"].tolerance == 0.25
        assert by_id[f"{prefix}_beam_escapes"].minimum == 95.0
        assert by_id[f"{prefix}_float_below_choke_margin"].maximum == 75.0
        assert by_id[f"{prefix}_prediction_is_not_post_hoc"].maximum == 1e-9
        assert by_id[f"{prefix}_steady_current_balance"].maximum == 0.05
    assert by_id["scenarios_are_distinguishable"].minimum == 12.0
    assert by_id["collection_law_form_holds_across_chi"].maximum == pytest.approx(
        math.log(1.25), abs=5e-5)


def test_the_distinguishability_gate_is_about_half_the_predicted_separation():
    cfgs = {n: load_config(CONFIG, n) for n in ORDER}
    sep = (float(cfgs[ORDER[0]].predicted["f_beam_nN"])
           - float(cfgs[ORDER[1]].predicted["f_beam_nN"]))
    policy = lc.load_policy(POLICY)
    bound = {g.id: g for g in policy.gates}["scenarios_are_distinguishable"].minimum
    assert 0.4 * sep < bound < 0.6 * sep


# ======================================================================
# the cohort contract
# ======================================================================

def test_a_mixed_generation_cohort_is_rejected(tmp_path):
    """A smoke run's shortened t_end changes the study hash; it must never be
    analyzable alongside a real run."""
    runs = []
    for scenario, study in (("A_day_p95", {"gen": 1}),
                            ("B_night_worst", {"gen": 2})):
        run = lc.begin_run(run_root=tmp_path / "o",
                           stage_id="capstone.mission_envelope",
                           config={"x": 1.0}, scenario=scenario,
                           study_config=study)
        (run.diags_dir / "f.h5").write_bytes(b"x")
        lc.complete_run(run, expected_artifacts=["f.h5"])
        runs.append(lc.load_run(run.dir))
    with pytest.raises(lc.ContractError, match="configuration generations"):
        lc.check_cohort(runs, stage_id="capstone.mission_envelope",
                        require_scenarios=ORDER)


def test_a_matched_cohort_is_accepted(tmp_path):
    runs = []
    for scenario in ORDER:
        run = lc.begin_run(run_root=tmp_path / "o",
                           stage_id="capstone.mission_envelope",
                           config={"x": 1.0, "s": scenario}, scenario=scenario,
                           study_config={"gen": 1})
        (run.diags_dir / "f.h5").write_bytes(b"x")
        lc.complete_run(run, expected_artifacts=["f.h5"])
        runs.append(lc.load_run(run.dir))
    lc.check_cohort(runs, stage_id="capstone.mission_envelope",
                    require_scenarios=ORDER)


def test_a_single_run_cohort_is_rejected(tmp_path):
    run = lc.begin_run(run_root=tmp_path / "o",
                       stage_id="capstone.mission_envelope",
                       config={"x": 1.0}, scenario="A_day_p95",
                       study_config={"gen": 1})
    (run.diags_dir / "f.h5").write_bytes(b"x")
    lc.complete_run(run, expected_artifacts=["f.h5"])
    with pytest.raises(lc.ContractError, match="!= required"):
        lc.check_cohort([lc.load_run(run.dir)],
                        stage_id="capstone.mission_envelope",
                        require_scenarios=ORDER)


def test_single_run_analysis_is_refused():
    assert analyze.main(["--run", "outputs/whatever"]) == lc.EXIT_ERROR


# ======================================================================
# metric construction
# ======================================================================

class _FakeRun:
    def __init__(self, diags):
        self.diags_dir = diags


def test_build_metrics_names_every_metric_per_scenario():
    cfgs = {n: load_config(CONFIG, n) for n in ORDER}
    meas = {}
    for name in ORDER:
        cfg = cfgs[name]
        pred = {k: float(cfg.predicted[k])
                for k in ("phi_body_V", "f_beam_nN", "exhaust_ke_eV")}
        meas[name] = dict(
            d=_ledger(), s=dict(phi_body=pred["phi_body_V"],
                                F_beam_N=pred["f_beam_nN"] * 1e-9,
                                pct_escape=98.4, beam_escape_KE_mean=pred["exhaust_ke_eV"]),
            window=None, n_tail=10, frozen=pred, recomputed=pred,
            prediction_consistency=0.0,
            refit=dict(k_meas=3.28, ke_ledger_meas=0.80, f_esc_meas=0.984,
                       beta_meas=0.46, chi_meas=200.0 if name == ORDER[0] else 386.0,
                       i_the_A=1e-6),
            edge_phi_max=0.04, current_balance=0.03, f_net_over_f_beam=0.004,
            scrape_consistency=3e-9, scrape_consistency_beam=5e-9,
            late_dphidt=1e7, settle_observed_s=25e-9)
    metrics = analyze.build_metrics(ORDER, cfgs, meas)
    policy = lc.load_policy(POLICY)
    for g in policy.gates:
        assert g.metric_id in metrics, f"gate {g.id} has no metric"
    verdict = lc.evaluate_gates(metrics, policy)
    assert verdict.status == lc.V_PASS, verdict.detail
    # the reported-only extras are present too
    assert metrics["A_day_p95__beta_meas"].value == pytest.approx(0.46)
    assert metrics["chi_ratio"].value == pytest.approx(386.0 / 200.0)
    assert metrics["beta_log_spread"].value == pytest.approx(0.0, abs=1e-12)


def test_beta_log_spread_is_symmetric_and_signless():
    cfgs = {n: load_config(CONFIG, n) for n in ORDER}

    def spread(beta_a, beta_b):
        meas = {}
        for name, beta, chi in ((ORDER[0], beta_a, 200.0), (ORDER[1], beta_b, 386.0)):
            cfg = cfgs[name]
            pred = {k: float(cfg.predicted[k])
                    for k in ("phi_body_V", "f_beam_nN", "exhaust_ke_eV")}
            meas[name] = dict(
                d=_ledger(), s=dict(phi_body=pred["phi_body_V"],
                                    F_beam_N=pred["f_beam_nN"] * 1e-9,
                                    pct_escape=98.4,
                                    beam_escape_KE_mean=pred["exhaust_ke_eV"]),
                window=None, n_tail=10, frozen=pred, recomputed=pred,
                prediction_consistency=0.0,
                refit=dict(k_meas=3.28, ke_ledger_meas=0.80, f_esc_meas=0.984,
                           beta_meas=beta, chi_meas=chi, i_the_A=1e-6),
                edge_phi_max=0.04, current_balance=0.03, f_net_over_f_beam=0.004,
                scrape_consistency=3e-9, scrape_consistency_beam=5e-9,
                late_dphidt=1e7, settle_observed_s=25e-9)
        return analyze.build_metrics(ORDER, cfgs, meas)["beta_log_spread"].value

    assert spread(0.46, 0.69) == pytest.approx(spread(0.69, 0.46))
    assert spread(0.46, 0.46 * 1.25) == pytest.approx(math.log(1.25), rel=1e-9)
