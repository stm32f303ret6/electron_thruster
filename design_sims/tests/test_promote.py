"""promote.py's job is the REFUSAL: a number the ladder rejected must not
calibrate the model the ladder validates."""

import json
from pathlib import Path

import pytest
import yaml

import promote
import refit_laws
from promote import PromotionRefused

DESIGN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DESIGN_ROOT.parent
REFERENCE = (REPO_ROOT / "pic_sims/validation_cases/capstone/2_chipsat_thruster"
             / "reference_results/20260801T142601Z_2f822a95")

_METRICS = [
    {"id": "f_beam_nN", "status": "OK", "value": 13.65},
    {"id": "phi_body_V", "status": "OK", "value": 16.98},
    {"id": "escape_fraction_pct", "status": "OK", "value": 98.44},
    {"id": "exhaust_ke_mean_eV", "status": "OK", "value": 147.52},
]

_CONFIG = {
    "stage_id": "capstone.floating_body",
    "electrical": {"cathode_offset": -200.0},
    "beam": {"i_beam": 0.342e-3},
    "plasma": {"n0": 1.627e12, "Te_K": 1318.8, "Ti_K": 936.2, "ion_mass_me": 400.0},
    "geometry": {"r_probe": 0.005, "z_bot": -0.005, "z_top": 0.0005,
                 "emit_radius": 0.0005},
}


def _fake_analysis(tmp_path, status="PASS", metrics=None, prefix="",
                   monkeypatch=None):
    """A minimal analysis directory. ``monkeypatch`` re-roots promote.py at
    tmp_path so the in-tree provenance check is satisfied by the fake."""
    if monkeypatch is not None:
        monkeypatch.setattr(promote, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(promote, "RUNS_DIR", tmp_path / "runs")
    d = tmp_path / "analysis"
    d.mkdir()
    (d / "verdict.json").write_text(json.dumps(
        {"status": status, "policy_id": "test.v1"}), encoding="utf-8")
    ms = [dict(m, id=prefix + m["id"]) for m in (metrics or _METRICS)]
    (d / "metrics.json").write_text(json.dumps(
        {"analysis_id": "TESTID", "metrics": ms}), encoding="utf-8")
    (d / "config_used.yaml").write_text(yaml.safe_dump(_CONFIG), encoding="utf-8")
    return d


# ----------------------------------------------------------------------
# the refusals
# ----------------------------------------------------------------------

def test_a_failing_analysis_is_refused(tmp_path):
    d = _fake_analysis(tmp_path, status="FAIL")
    with pytest.raises(PromotionRefused, match="not 'PASS'"):
        promote.main(["--analysis", str(d), "--name", "x", "--dry-run"])


def test_an_errored_analysis_is_refused(tmp_path):
    d = _fake_analysis(tmp_path, status="ERROR")
    with pytest.raises(PromotionRefused, match="not 'PASS'"):
        promote.main(["--analysis", str(d), "--name", "x", "--dry-run"])


def test_force_without_a_reason_is_refused(tmp_path):
    d = _fake_analysis(tmp_path, status="FAIL")
    with pytest.raises(PromotionRefused, match="--force requires --reason"):
        promote.main(["--analysis", str(d), "--name", "x", "--force", "--dry-run"])


def test_missing_required_metrics_are_refused(tmp_path, monkeypatch):
    d = _fake_analysis(tmp_path, metrics=_METRICS[:2], monkeypatch=monkeypatch)
    with pytest.raises(PromotionRefused, match="no OK metric"):
        promote.main(["--analysis", str(d), "--name", "x", "--dry-run"])


def test_an_errored_metric_does_not_count_as_present(tmp_path, monkeypatch):
    broken = [dict(m) for m in _METRICS]
    broken[0] = dict(broken[0], status="ERROR", value=None)
    d = _fake_analysis(tmp_path, metrics=broken, monkeypatch=monkeypatch)
    with pytest.raises(PromotionRefused, match="no OK metric"):
        promote.main(["--analysis", str(d), "--name", "x", "--dry-run"])


def test_an_out_of_tree_analysis_is_refused(tmp_path):
    """A record must anchor to in-tree evidence or a fresh clone cannot check it."""
    d = _fake_analysis(tmp_path)
    with pytest.raises(PromotionRefused, match="outside this repository"):
        promote.main(["--analysis", str(d), "--name", "x", "--dry-run"])


# ----------------------------------------------------------------------
# the successful paths
# ----------------------------------------------------------------------

def test_forcing_records_the_reason_in_the_record(tmp_path, monkeypatch):
    d = _fake_analysis(tmp_path, status="FAIL", monkeypatch=monkeypatch)
    assert promote.main(["--analysis", str(d), "--name", "forced_x", "--force",
                         "--reason", "unrelated gate"]) == 0
    rec = yaml.safe_load((tmp_path / "runs" / "forced_x.yaml").read_text())
    assert rec["forced"]["reason"] == "unrelated gate"
    assert rec["forced"]["refused_verdict"] == "FAIL"
    assert rec["source"]["verdict_status"] == "FAIL"


def test_a_passing_analysis_promotes_with_full_provenance(tmp_path, monkeypatch):
    d = _fake_analysis(tmp_path, monkeypatch=monkeypatch)
    assert promote.main(["--analysis", str(d), "--name", "ok_x"]) == 0
    rec = yaml.safe_load((tmp_path / "runs" / "ok_x.yaml").read_text())
    assert "forced" not in rec
    assert rec["source"]["verdict_status"] == "PASS"
    assert len(rec["source"]["metrics_sha256"]) == 64
    assert rec["drive"]["voltage_V"] == 200.0
    assert rec["measured"]["f_beam_nN"] == 13.65


def test_scenario_prefixes_are_stripped(tmp_path, monkeypatch):
    """A cohort analysis names its metrics '<scenario>__<id>'."""
    d = _fake_analysis(tmp_path, prefix="A_day_p95__", monkeypatch=monkeypatch)
    assert promote.main(["--analysis", str(d), "--name", "scn",
                         "--scenario", "A_day_p95"]) == 0
    rec = yaml.safe_load((tmp_path / "runs" / "scn.yaml").read_text())
    assert rec["measured"]["phi_body_V"] == 16.98
    assert rec["scenario"] is None or rec["scenario"] == "A_day_p95"


def test_asking_for_the_wrong_scenario_finds_nothing(tmp_path, monkeypatch):
    d = _fake_analysis(tmp_path, prefix="A_day_p95__", monkeypatch=monkeypatch)
    with pytest.raises(PromotionRefused, match="no OK metric"):
        promote.main(["--analysis", str(d), "--name", "scn",
                      "--scenario", "B_night_worst", "--dry-run"])


# ----------------------------------------------------------------------
# the round trip: promote -> refit -> the committed constants
# ----------------------------------------------------------------------

def test_the_committed_reference_is_what_laws_yaml_was_fitted_from():
    """Re-derive the constants straight from the committed record and check
    laws.yaml agrees -- the same check the ladder makes every suite run."""
    from calibration import load_laws, load_runs
    laws = load_laws()
    rec = load_runs()["capstone_float200"]
    got = refit_laws.constants_from_record(rec)
    assert got["k"] == pytest.approx(laws.k, rel=1e-5)
    assert got["ke_ledger"] == pytest.approx(laws.ke_ledger, rel=1e-5)
    assert got["f_esc"] == pytest.approx(laws.f_esc, rel=1e-5)
    assert got["beta"] == pytest.approx(laws.beta, rel=1e-5)
    assert got["area_m2"] == pytest.approx(laws.area_m2, rel=1e-5)


def test_laws_yaml_is_not_stale():
    """--check must pass, or the committed constants no longer match the records."""
    assert refit_laws.main(["--check"]) == 0


def test_the_promoted_record_points_at_the_real_reference_bundle():
    from calibration import load_runs
    rec = load_runs()["capstone_float200"]
    assert (REPO_ROOT / rec["source"]["metrics_path"]).is_file()
    assert rec["source"]["analysis_dir"] == str(REFERENCE.relative_to(REPO_ROOT))
    assert rec["source"]["policy_id"] == "capstone.floating_body.v2"


def test_hull_area_matches_the_frozen_geometry():
    """3.2987 cm^2: side wall + both caps of the 5 mm can, 5.5 mm tall."""
    assert refit_laws.hull_area_m2(0.005, -0.005, 0.0005) == pytest.approx(
        3.29867e-4, rel=1e-5)
