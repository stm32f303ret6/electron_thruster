"""Config loading, the two-form scenario contract, and the derived numerics.

Per-scenario numeric pins are deliberate: dt, step count and grid are what the
compute estimate and the settle-time argument rest on, so a change to any of
them should be a visible test edit rather than a silent 10-hour surprise.
"""

import copy
import math
from pathlib import Path

import pytest
import yaml

from helpers import (STAGE_ID, ConfigError, Geometry, analytic_capacitance,
                     load_config, scenario_names)

STAGE_DIR = Path(__file__).resolve().parents[1]
CONFIG = STAGE_DIR / "config.yaml"


def _raw():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _write(tmp_path, doc):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return p


# ----------------------------------------------------------------------
# the two-form contract
# ----------------------------------------------------------------------

def test_the_stage_declares_exactly_two_scenarios():
    assert scenario_names(CONFIG) == ["A_day_p95", "B_night_worst"]


def test_a_scenario_must_be_selected():
    """No default operating point: a run that silently picked one would be
    unattributable."""
    with pytest.raises(ConfigError, match="a scenario must be selected"):
        load_config(CONFIG)


def test_an_unknown_scenario_is_rejected():
    with pytest.raises(ConfigError, match="unknown scenario"):
        load_config(CONFIG, "C_made_up")


def test_stage_id_is_this_stage():
    assert load_config(CONFIG, "A_day_p95").stage_id == STAGE_ID


def test_frozen_config_round_trips(tmp_path):
    """A run's frozen config must reload to an identical Config."""
    for name in scenario_names(CONFIG):
        cfg = load_config(CONFIG, name)
        frozen = _write(tmp_path, cfg.effective_config())
        back = load_config(frozen)
        assert back.scenario == name
        assert back.dt == pytest.approx(cfg.dt, rel=1e-15)
        assert back.max_steps == cfg.max_steps
        assert back.n0 == cfg.n0 and back.Te_K == cfg.Te_K
        assert back.i_beam == cfg.i_beam
        assert back.cathode_offset == cfg.cathode_offset
        assert dict(back.predicted) == dict(cfg.predicted)
        assert dict(back.law_anchor) == dict(cfg.law_anchor)


def test_frozen_config_rejects_a_mismatched_scenario_request(tmp_path):
    cfg = load_config(CONFIG, "A_day_p95")
    frozen = _write(tmp_path, cfg.effective_config())
    with pytest.raises(ConfigError, match="!= frozen"):
        load_config(frozen, "B_night_worst")


def test_study_config_is_shared_across_scenarios():
    """The cohort hash must not depend on which scenario you loaded, or the two
    runs could never be analyzed together."""
    a = load_config(CONFIG, "A_day_p95").study_config()
    b = load_config(CONFIG, "B_night_worst").study_config()
    assert a == b
    assert [s["name"] for s in a["scenarios"]] == ["A_day_p95", "B_night_worst"]
    # per-scenario quantities, including the DERIVED ones, must not leak in
    assert "plasma" not in a
    assert "cathode_offset" not in a["electrical"]
    assert "i_beam" not in a["beam"]
    assert "dt" not in a["numerics"]
    assert "max_steps" not in a["run"]


@pytest.mark.parametrize("name", ["A_day_p95", "B_night_worst"])
def test_study_config_changes_when_t_end_changes(name):
    """This is what makes a smoke run structurally unable to join a real cohort.

    t_end is per-scenario, so a `--t-end` override has to be substituted into
    THIS run's own entry of the study table -- otherwise the smoke run would
    keep the committed duration in its study hash and cohort cleanly with a real
    run of the other scenario.
    """
    from dataclasses import replace
    cfg = load_config(CONFIG, name)
    smoke = replace(cfg, t_end=300e-9)
    assert smoke.study_config() != cfg.study_config()
    # and only its OWN entry moved
    entry = {s["name"]: s for s in smoke.study_config()["scenarios"]}
    orig = {s["name"]: s for s in cfg.study_config()["scenarios"]}
    assert entry[name]["t_end"] == 300e-9
    for other in set(orig) - {name}:
        assert entry[other] == orig[other]


def test_a_smoke_run_cannot_cohort_with_a_real_run():
    """The end-to-end version of the guarantee, at the hash level."""
    from dataclasses import replace
    import ladder_contract as lc
    real_a = load_config(CONFIG, "A_day_p95")
    real_b = load_config(CONFIG, "B_night_worst")
    smoke_a = replace(real_a, t_end=300e-9)
    h = lc.config_sha256
    assert h(real_a.study_config()) == h(real_b.study_config())
    assert h(smoke_a.study_config()) != h(real_b.study_config())


def test_a_frozen_run_config_has_no_study_hash():
    """A single frozen scenario cannot reconstruct the study it came from."""
    assert load_config(CONFIG, "A_day_p95")._scenarios
    cfg = load_config(CONFIG, "A_day_p95")
    assert cfg.study_config() is not None


# ----------------------------------------------------------------------
# the pre-registration must be complete
# ----------------------------------------------------------------------

def test_a_scenario_without_predictions_is_rejected(tmp_path):
    doc = _raw()
    doc["scenarios"][0].pop("predicted")
    with pytest.raises(ConfigError, match="missing 'predicted'"):
        load_config(_write(tmp_path, doc), "A_day_p95")


def test_a_partial_prediction_is_rejected(tmp_path):
    doc = _raw()
    doc["scenarios"][0]["predicted"].pop("binding")
    with pytest.raises(ConfigError, match="pre-registration is not optional"):
        load_config(_write(tmp_path, doc), "A_day_p95")


def test_a_scenario_without_row_provenance_is_rejected(tmp_path):
    doc = _raw()
    doc["scenarios"][1]["provenance"].pop("csv_sha256")
    with pytest.raises(ConfigError, match="invented"):
        load_config(_write(tmp_path, doc), "B_night_worst")


def test_a_missing_law_anchor_is_rejected(tmp_path):
    doc = _raw()
    doc.pop("law_anchor")
    with pytest.raises(ConfigError, match="missing 'law_anchor'"):
        load_config(_write(tmp_path, doc), "A_day_p95")


def test_a_partial_law_anchor_is_rejected(tmp_path):
    doc = _raw()
    doc["law_anchor"].pop("beta")
    with pytest.raises(ConfigError, match="law_anchor is missing"):
        load_config(_write(tmp_path, doc), "A_day_p95")


def test_a_truncated_sha_in_the_anchor_is_rejected(tmp_path):
    doc = _raw()
    doc["law_anchor"]["laws_sha256"] = "deadbeef"
    with pytest.raises(ConfigError, match="64 hex characters"):
        load_config(_write(tmp_path, doc), "A_day_p95")


def test_an_unphysical_anchor_constant_is_rejected(tmp_path):
    doc = _raw()
    doc["law_anchor"]["f_esc"] = 1.4
    with pytest.raises(ConfigError, match="f_esc must be in"):
        load_config(_write(tmp_path, doc), "A_day_p95")


# ----------------------------------------------------------------------
# the predictions must be reproducible from the frozen constants
# ----------------------------------------------------------------------

@pytest.mark.parametrize("name", ["A_day_p95", "B_night_worst"])
def test_frozen_predictions_are_exactly_what_the_constants_imply(name):
    """The anti-post-hoc guard, checked without needing a run.

    The gate tolerance is 1e-9; the frozen predictions were generated from
    exactly these rounded constants, so the agreement should be bit-exact.
    """
    cfg = load_config(CONFIG, name)
    got = cfg.model_prediction()
    for key in ("phi_body_V", "f_beam_nN", "exhaust_ke_eV"):
        frozen = float(cfg.predicted[key])
        assert got[key] == pytest.approx(frozen, rel=1e-12, abs=1e-12)


def test_the_two_scenarios_bracket_the_anchors_chi():
    """The point of the pair: different binding constraints, different chi."""
    a = load_config(CONFIG, "A_day_p95")
    b = load_config(CONFIG, "B_night_worst")
    import opmodel
    chi_a = opmodel.chi(float(a.predicted["phi_body_V"]), a.Te_K)
    chi_b = opmodel.chi(float(b.predicted["phi_body_V"]), b.Te_K)
    assert 190.0 < chi_a < 210.0
    assert 375.0 < chi_b < 395.0
    assert a.predicted["binding"] != b.predicted["binding"]
    assert a.predicted["binding"] == "gamma_cl"
    assert b.predicted["binding"] == "phi_max"


def test_the_anchor_matches_the_capstone_reference_metrics():
    """The frozen constants must re-derive from the committed capstone run --
    the same algebra cross_stage.py repeats every suite run."""
    import json
    import opmodel
    cfg = load_config(CONFIG, "A_day_p95")
    root = STAGE_DIR.parents[3]
    metrics_path = root / cfg.law_anchor["anchored_to"]
    assert metrics_path.is_file(), f"anchor {metrics_path} not in tree"
    doc = json.loads(metrics_path.read_text(encoding="utf-8"))
    m = {x["id"]: x["value"] for x in doc["metrics"] if x["status"] == "OK"}
    got = opmodel.measured_constants(
        f_beam_nN=m["f_beam_nN"], phi_body_V=m["phi_body_V"],
        escape_fraction_pct=m["escape_fraction_pct"],
        exhaust_ke_eV=m["exhaust_ke_mean_eV"], i_beam_A=0.342e-3,
        v_drive=200.0, n_e=1.627e12, Te_K=1318.8,
        area_m2=float(cfg.law_anchor["area_m2"]))
    assert got["k_meas"] == pytest.approx(float(cfg.law_anchor["k"]), rel=2e-6)
    assert got["ke_ledger_meas"] == pytest.approx(
        float(cfg.law_anchor["ke_ledger"]), rel=2e-6)
    assert got["beta_meas"] == pytest.approx(float(cfg.law_anchor["beta"]), rel=2e-6)


# ----------------------------------------------------------------------
# derived numerics, pinned per scenario
# ----------------------------------------------------------------------

@pytest.mark.parametrize("name,dt,steps,t_end_ns,lam_mm", [
    ("A_day_p95", 4.1354e-12, 193440, 800.0, 1.845),
    ("B_night_worst", 4.1372e-12, 314200, 1300.0, 6.028),
])
def test_derived_numerics(name, dt, steps, t_end_ns, lam_mm):
    cfg = load_config(CONFIG, name)
    assert cfg.dt == pytest.approx(dt, rel=1e-4)
    assert cfg.max_steps == steps
    assert cfg.t_end * 1e9 == pytest.approx(t_end_ns)
    assert cfg.lamD * 1e3 == pytest.approx(lam_mm, rel=1e-3)
    assert cfg.nr == 200 and cfg.nz == 440
    assert cfg.V_GAP == 300.0
    assert cfg.cfl < 0.5
    assert cfg.wpe * cfg.dt < 0.2
    assert cfg.dx < cfg.lamD
    assert cfg.max_steps % cfg.diag_period == 0


def test_the_run_is_long_enough_for_the_float_to_settle():
    """Each scenario is sized by ITS OWN settle time, not a shared duration."""
    taus = {}
    for name in scenario_names(CONFIG):
        cfg = load_config(CONFIG, name)
        tau = cfg.predicted_settle_time_s()
        taus[name] = cfg.t_end / tau
        assert cfg.t_end >= 3.0 * tau, f"{name}: t_end is only {cfg.t_end/tau:.1f} tau"
    # the two durations differ precisely because the settle times differ by ~11x
    assert taus["A_day_p95"] > 30.0
    assert taus["B_night_worst"] > 5.0


def test_the_night_run_leaves_current_balance_margin():
    """t_end for B is set BY the current_balance gate, so pin the reasoning.

    current_balance = C*(dphi/dt)/I_escape, and the tail window is the last 20 %
    of the record.  Under the model's exponential approach the residual must sit
    well under the 0.05 gate, or the run fails for a finite-time reason rather
    than a physical one.
    """
    import math
    cfg = load_config(CONFIG, "B_night_worst")
    tau = cfg.predicted_settle_time_s()
    phi_eq = float(cfg.predicted["phi_body_V"])
    lo, hi = 0.8 * cfg.t_end - cfg.t_on, cfg.t_end - cfg.t_on   # tail window
    mean_dphidt = phi_eq * (math.exp(-lo / tau) - math.exp(-hi / tau)) / (hi - lo)
    i_escape = float(cfg.law_anchor["f_esc"]) * cfg.i_beam
    balance = float(cfg.law_anchor["capacitance_F"]) * mean_dphidt / i_escape
    assert balance < 0.02, f"predicted current_balance {balance:.4f} is too close to 0.05"


def test_a_t_end_that_does_not_settle_is_refused(tmp_path):
    """The reason t_end is 1 us rather than the capstone's 800 ns."""
    from dataclasses import replace
    cfg = load_config(CONFIG, "B_night_worst")
    short = replace(cfg, t_end=600e-9)
    with pytest.raises(ConfigError, match="under 3 settle times"):
        short.validate()
    short.validate_smoke()      # a declared smoke run may be short


def test_a_max_steps_cap_that_truncates_t_end_is_refused(tmp_path):
    """The capstone's 160000 cap would have silently shortened this run."""
    doc = _raw()
    doc["run"]["max_steps"] = 160000
    with pytest.raises(ConfigError, match="truncates scenario"):
        load_config(_write(tmp_path, doc), "A_day_p95")


def test_night_scenario_is_the_domain_risk():
    """rmax/lambda_D is what the smoke run's domain decision is about."""
    a = load_config(CONFIG, "A_day_p95")
    b = load_config(CONFIG, "B_night_worst")
    assert a.rmax / a.lamD > 15.0        # comfortable
    assert 4.0 < b.rmax / b.lamD < 6.0   # tight -- the documented risk
    # both stay inside OML's validity window (r_p/lambda_D <~ 3)
    assert a.r_probe / a.lamD < 3.0
    assert b.r_probe / b.lamD < 3.0


# ----------------------------------------------------------------------
# the deck is the capstone's deck
# ----------------------------------------------------------------------

def test_geometry_is_identical_to_the_capstone_rung():
    cap = yaml.safe_load(
        (STAGE_DIR.parent / "2_chipsat_thruster" / "config.yaml").read_text())
    assert _raw()["geometry"] == cap["geometry"]
    assert _raw()["numerics"]["dx"] == cap["numerics"]["dx"]
    assert _raw()["numerics"]["ppc"] == cap["numerics"]["ppc"]
    assert _raw()["reservoir"] == cap["reservoir"]
    assert _raw()["domain"] == cap["domain"]


def test_geometry_invariants_still_hold():
    cfg = load_config(CONFIG, "A_day_p95")
    g = cfg.geometry()
    assert isinstance(g, Geometry)
    assert g.d_gap == pytest.approx(4.7e-3, rel=1e-9)
    assert g.d_gap >= 7.0 * cfg.dx
    assert g.we < g.r_slit and g.we < g.r_cath


def test_capacitance_matches_the_frozen_anchor():
    cfg = load_config(CONFIG, "A_day_p95")
    assert analytic_capacitance(cfg.r_probe) == pytest.approx(
        float(cfg.law_anchor["capacitance_F"]), rel=1e-5)


def test_research_knobs_are_still_rejected(tmp_path):
    doc = _raw()
    doc["shroud"] = {"enabled": True}
    with pytest.raises(ConfigError, match="not migrated"):
        load_config(_write(tmp_path, doc), "A_day_p95")


def test_an_unknown_top_level_key_is_rejected(tmp_path):
    doc = _raw()
    doc["typo_section"] = {}
    with pytest.raises(ConfigError, match="unknown top-level"):
        load_config(_write(tmp_path, doc), "A_day_p95")


def test_a_positive_cathode_offset_is_rejected(tmp_path):
    doc = _raw()
    doc["scenarios"][0]["cathode_offset"] = 300.0
    with pytest.raises(ConfigError, match="must be negative"):
        load_config(_write(tmp_path, doc), "A_day_p95")


def test_duplicate_scenario_names_are_rejected(tmp_path):
    doc = _raw()
    doc["scenarios"][1]["name"] = doc["scenarios"][0]["name"]
    with pytest.raises(ConfigError, match="duplicate scenario names"):
        load_config(_write(tmp_path, doc), "A_day_p95")
