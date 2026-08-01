"""Repository-level tests for the ladder (section 14.3 of the plan)."""

import ast
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

import ladder_contract as lc
import run_ladder
from ladder import STAGE_BY_ID, STAGES, Stage, topological_order

VALIDATION_ROOT = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------------
# folder contract + topology
# ----------------------------------------------------------------------

def test_every_stage_satisfies_folder_contract():
    assert run_ladder.check_all_contracts() == []


def test_ladder_is_acyclic_and_dependencies_exist():
    order = topological_order()
    seen = set()
    for stage in order:              # every dependency appears before its dependents
        for dep in stage.requires:
            assert dep in STAGE_BY_ID, f"{stage.id} requires unknown {dep}"
            assert dep in seen, f"{stage.id} placed before its dependency {dep}"
        seen.add(stage.id)
    assert len(order) == len(STAGES)


def test_topology_detects_cycle(monkeypatch):
    a = Stage("x.a", Path("electron_gun/1_negative_cathode"), requires=("x.b",))
    b = Stage("x.b", Path("electron_gun/2_electron_gun"), requires=("x.a",))
    monkeypatch.setattr("ladder.STAGE_BY_ID", {"x.a": a, "x.b": b})
    import ladder
    monkeypatch.setattr(ladder, "STAGE_BY_ID", {"x.a": a, "x.b": b})
    with pytest.raises(ValueError):
        ladder.topological_order(["x.a"])


def test_declared_scenarios_match_stage_configs():
    # The holed gun's ladder scenarios must equal its config.yaml scenarios.
    stage = STAGE_BY_ID["emitter.holed_anode"]
    raw = yaml.safe_load((stage.path / "config.yaml").read_text())
    names = tuple(str(s["name"]) for s in raw["scenarios"])
    assert stage.scenarios == names


# ----------------------------------------------------------------------
# the runner is subprocess-only (never imports a stage's WarpX code)
# ----------------------------------------------------------------------

def test_runner_uses_subprocess_not_stage_imports():
    src = (VALIDATION_ROOT / "run_ladder.py").read_text()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    # The runner may import only root modules -- never a stage's simulation or
    # helpers (libwarpx cannot initialize twice in one process).
    assert "simulation" not in imported
    assert "helpers" not in imported
    assert "subprocess" in imported


# ----------------------------------------------------------------------
# a clean checkout never mistakes reference artifacts for completed runs
# ----------------------------------------------------------------------

def test_clean_checkout_reports_no_completed_runs(tmp_path):
    stage = Stage("collector.thermal", Path("current_collection/1_thermal"))
    fake = replace(stage)
    # Point the stage at a tmp dir holding only a reference_results/ (no runs).
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (tmp_path / "reference_results").mkdir()
    (tmp_path / "reference_results" / "summary.json").write_text("{}")

    class _S:
        id = "collector.thermal"
        path = tmp_path
        scenarios = ()
    with pytest.raises(RuntimeError):
        run_ladder._latest_runs(_S())


def test_reference_dir_without_manifest_is_not_loadable(tmp_path):
    ref = tmp_path / "reference_results"
    ref.mkdir()
    (ref / "summary.json").write_text("{}")
    with pytest.raises(lc.ContractError):
        lc.load_run(ref)  # no manifest.json -> not a completed run


# ----------------------------------------------------------------------
# incompatible --runs sets are rejected
# ----------------------------------------------------------------------

def _complete_run(tmp_path, stage_id, scenario, study):
    run = lc.begin_run(run_root=tmp_path / "o", stage_id=stage_id,
                       config={"x": 1.0}, scenario=scenario, study_config=study)
    (run.diags_dir / "f.h5").parent.mkdir(parents=True, exist_ok=True)
    (run.diags_dir / "f.h5").write_bytes(b"x")
    lc.complete_run(run, expected_artifacts=["*.h5"])
    return lc.load_run(run.dir)


def test_incompatible_cohort_rejected(tmp_path):
    a = _complete_run(tmp_path, "emitter.holed_anode", "A", {"gen": 1})
    b = _complete_run(tmp_path, "emitter.holed_anode", "B", {"gen": 2})  # diff study
    with pytest.raises(lc.ContractError):
        lc.check_cohort([a, b])


# ----------------------------------------------------------------------
# editing the live config cannot change analysis of a frozen run
# ----------------------------------------------------------------------

def test_frozen_config_is_immune_to_live_edit(tmp_path):
    live = {"stage_id": "s", "value": 1.0}
    run = lc.begin_run(run_root=tmp_path / "o", stage_id="s", config=live)
    (run.diags_dir / "f.h5").write_bytes(b"x")
    lc.complete_run(run, expected_artifacts=["*.h5"])
    # A later edit to the (separate) live config must not touch the frozen copy.
    live["value"] = 999.0
    loaded = lc.load_run(run.dir)
    assert loaded.config["value"] == 1.0


# ----------------------------------------------------------------------
# re-analysis with a new policy creates a new dir and preserves the old
# ----------------------------------------------------------------------

def test_reanalysis_new_policy_preserves_old(tmp_path):
    run = lc.begin_run(run_root=tmp_path / "o", stage_id="s", config={"a": 1.0})
    (run.diags_dir / "f.h5").write_bytes(b"x")
    lc.complete_run(run, expected_artifacts=["*.h5"])
    loaded = lc.load_run(run.dir)

    def policy(pid, tol):
        doc = {"schema_version": 1, "policy_id": pid, "stage_id": "s",
               "evidence_kind": "test",
               "gates": [{"id": "g", "required": True, "metric": "m",
                          "comparison": "abs_within", "target": 0.0,
                          "tolerance": tol}]}
        p = tmp_path / f"{pid}.yaml"
        p.write_text(yaml.safe_dump(doc))
        return lc.load_policy(p)

    a1 = lc.begin_analysis([loaded], policy("s.v1", 1.0),
                           results_root=tmp_path / "r")
    lc.complete_analysis(a1, lc.evaluate_gates(
        {"m": lc.Metric.measure("m", 0.5, "-")}, a1.policy))
    a2 = lc.begin_analysis([loaded], policy("s.v2", 2.0),
                           results_root=tmp_path / "r")
    assert a1.dir != a2.dir
    assert a1.manifest_path.exists()
    assert lc.read_json_strict(a1.manifest_path)["status"] == lc.COMPLETE
