"""Unit tests for the shared ladder contract (section 14.1 of the plan).

These are the tests written ONCE at the root; they cover the plumbing every
stage relies on -- hashing, immutable run/analysis lifecycles, strict JSON, and
the fail-closed gate algebra -- so that lifecycle bugs are caught here rather
than five times over.
"""

import pytest
import yaml

import ladder_contract as lc


# ----------------------------------------------------------------------
# canonical serialization and hashing
# ----------------------------------------------------------------------

def test_canonical_hash_is_key_order_independent():
    a = {"b": 2, "a": 1, "nested": {"y": [1, 2], "x": 3}}
    b = {"a": 1, "nested": {"x": 3, "y": [1, 2]}, "b": 2}
    assert lc.config_sha256(a) == lc.config_sha256(b)


def test_canonical_hash_changes_with_value():
    base = {"a": 1.0, "b": 2.0}
    changed = {"a": 1.0, "b": 2.0001}
    assert lc.config_sha256(base) != lc.config_sha256(changed)


def test_canonical_hash_rejects_nonfinite():
    with pytest.raises(lc.ContractError):
        lc.config_sha256({"x": float("nan")})
    with pytest.raises(lc.ContractError):
        lc.config_sha256({"x": float("inf")})


def test_canonical_json_is_stable_string():
    obj = {"z": 1, "a": {"c": 3, "b": 2}}
    assert lc.canonical_json(obj) == '{"a":{"b":2,"c":3},"z":1}'


# ----------------------------------------------------------------------
# strict JSON
# ----------------------------------------------------------------------

def test_strict_dumps_rejects_nan():
    with pytest.raises(lc.ContractError):
        lc.dumps_strict({"x": float("nan")})


def test_read_json_strict_rejects_nan_infinity(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"x": NaN}')
    with pytest.raises(lc.ContractError):
        lc.read_json_strict(p)
    p.write_text('{"x": Infinity}')
    with pytest.raises(lc.ContractError):
        lc.read_json_strict(p)


def test_write_json_atomic_roundtrip(tmp_path):
    p = tmp_path / "sub" / "m.json"
    lc.write_json_atomic(p, {"a": 1, "b": [1, 2, 3]})
    assert lc.read_json_strict(p) == {"a": 1, "b": [1, 2, 3]}
    assert not (p.with_name(p.name + ".tmp")).exists()  # temp cleaned up


# ----------------------------------------------------------------------
# IDs
# ----------------------------------------------------------------------

def test_run_id_format():
    rid = lc.new_run_id("a81d19c2ff", None,
                        now=lc.datetime(2026, 8, 1, 18, 30, 45,
                                        tzinfo=lc.timezone.utc))
    assert rid == "20260801T183045Z_a81d19c2"


def test_run_id_inserts_scenario():
    rid = lc.new_run_id("a81d19c2ff", "B_high",
                        now=lc.datetime(2026, 8, 1, 18, 30, 45,
                                        tzinfo=lc.timezone.utc))
    assert rid == "20260801T183045Z_B_high_a81d19c2"


def test_analysis_id_format():
    aid = lc.new_analysis_id("p42e91a7bb",
                             now=lc.datetime(2026, 8, 1, 21, 4, 12,
                                             tzinfo=lc.timezone.utc))
    assert aid == "20260801T210412Z_p42e91a7"


# ----------------------------------------------------------------------
# run lifecycle
# ----------------------------------------------------------------------

def _begin(tmp_path, **kw):
    defaults = dict(
        run_root=tmp_path / "outputs", stage_id="test.stage",
        config={"a": 1.0, "b": 2}, expected_final_iteration=100)
    defaults.update(kw)
    return lc.begin_run(**defaults)


def _touch(path, content=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_begin_run_writes_running_and_freezes_config(tmp_path):
    run = _begin(tmp_path)
    m = lc.read_json_strict(run.manifest_path)
    assert m["status"] == lc.RUNNING
    assert m["stage_id"] == "test.stage"
    assert m["expected_final_iteration"] == 100
    frozen = yaml.safe_load((run.dir / "config_used.yaml").read_text())
    assert frozen == {"a": 1.0, "b": 2}
    assert m["case_sha256"] == lc.config_sha256({"a": 1.0, "b": 2})


def test_begin_run_copies_sources(tmp_path):
    src = tmp_path / "simulation.py"
    src.write_text("print('hi')\n")
    run = _begin(tmp_path, source_files=[src])
    assert (run.dir / "sources_used" / "simulation.py").read_text() == "print('hi')\n"


def test_complete_run_verifies_artifacts_and_iteration(tmp_path):
    run = _begin(tmp_path)
    _touch(run.diags_dir / "fields" / "openpmd_000100.h5")
    lc.complete_run(run, expected_artifacts=["fields/*.h5"],
                    observed_final_iteration=100)
    m = lc.read_json_strict(run.manifest_path)
    assert m["status"] == lc.COMPLETE
    assert m["observed_final_iteration"] == 100
    assert m["artifacts"][0]["files"] == 1


def test_complete_run_missing_artifact_is_invalid(tmp_path):
    run = _begin(tmp_path)
    with pytest.raises(lc.RunInvalid):
        lc.complete_run(run, expected_artifacts=["fields/*.h5"],
                        observed_final_iteration=100)
    assert lc.read_json_strict(run.manifest_path)["status"] == lc.INVALID


def test_complete_run_empty_artifact_is_invalid(tmp_path):
    run = _begin(tmp_path)
    _touch(run.diags_dir / "fields" / "openpmd_000100.h5", content=b"")
    with pytest.raises(lc.RunInvalid):
        lc.complete_run(run, expected_artifacts=["fields/*.h5"],
                        observed_final_iteration=100)
    assert lc.read_json_strict(run.manifest_path)["status"] == lc.INVALID


def test_complete_run_wrong_final_iteration_is_invalid(tmp_path):
    run = _begin(tmp_path)
    _touch(run.diags_dir / "fields" / "openpmd_000080.h5")
    with pytest.raises(lc.RunInvalid):
        lc.complete_run(run, expected_artifacts=["fields/*.h5"],
                        observed_final_iteration=80)
    assert lc.read_json_strict(run.manifest_path)["status"] == lc.INVALID


def test_fail_run_does_not_relabel_invalid(tmp_path):
    run = _begin(tmp_path)
    with pytest.raises(lc.RunInvalid):
        lc.complete_run(run, expected_artifacts=["fields/*.h5"],
                        observed_final_iteration=100)
    lc.fail_run(run, RuntimeError("boom"))  # generic handler after complete_run
    assert lc.read_json_strict(run.manifest_path)["status"] == lc.INVALID


def test_fail_run_marks_failed(tmp_path):
    run = _begin(tmp_path)
    lc.fail_run(run, RuntimeError("kaboom"))
    m = lc.read_json_strict(run.manifest_path)
    assert m["status"] == lc.FAILED
    assert "kaboom" in m["error"]


def test_exclusive_dir_never_reuses(tmp_path):
    # Two runs with identical config must land in distinct immutable dirs.
    r1 = lc.begin_run(run_root=tmp_path / "o", stage_id="s",
                      config={"a": 1.0})
    r2 = lc.begin_run(run_root=tmp_path / "o", stage_id="s",
                      config={"a": 1.0})
    assert r1.dir != r2.dir


def test_study_hash_recorded_for_scenarios(tmp_path):
    run = _begin(tmp_path, scenario="A", study_config={"scenarios": [1, 2, 3]})
    m = lc.read_json_strict(run.manifest_path)
    assert m["scenario"] == "A"
    assert m["study_sha256"] == lc.config_sha256({"scenarios": [1, 2, 3]})


# ----------------------------------------------------------------------
# loading evidence
# ----------------------------------------------------------------------

def _complete(tmp_path, **kw):
    run = _begin(tmp_path, **kw)
    _touch(run.diags_dir / "fields" / "f.h5")
    lc.complete_run(run, expected_artifacts=["fields/*.h5"],
                    observed_final_iteration=run.expected_final_iteration)
    return run


def test_load_run_requires_complete(tmp_path):
    run = _begin(tmp_path)  # still RUNNING
    with pytest.raises(lc.ContractError):
        lc.load_run(run.dir)


def test_load_run_ok_when_complete(tmp_path):
    run = _complete(tmp_path)
    loaded = lc.load_run(run.dir)
    assert loaded.stage_id == "test.stage"
    assert loaded.config == {"a": 1.0, "b": 2}


def test_check_cohort_rejects_mixed_study_hash(tmp_path):
    a = _complete(tmp_path, scenario="A", study_config={"gen": 1})
    b = _complete(tmp_path, scenario="B", study_config={"gen": 2})
    la, lb = lc.load_run(a.dir), lc.load_run(b.dir)
    with pytest.raises(lc.ContractError):
        lc.check_cohort([la, lb])


def test_check_cohort_requires_scenarios(tmp_path):
    a = _complete(tmp_path, scenario="A", study_config={"gen": 1})
    b = _complete(tmp_path, scenario="B", study_config={"gen": 1})
    la, lb = lc.load_run(a.dir), lc.load_run(b.dir)
    lc.check_cohort([la, lb], stage_id="test.stage",
                    require_scenarios=["A", "B"])
    with pytest.raises(lc.ContractError):
        lc.check_cohort([la, lb], require_scenarios=["A", "B", "C"])


# ----------------------------------------------------------------------
# metrics
# ----------------------------------------------------------------------

def test_metric_nonfinite_becomes_error():
    m = lc.Metric.measure("x", float("nan"), "A")
    assert m.status == "ERROR" and m.value is None and not m.usable
    m2 = lc.Metric.measure("x", 3.0, "A")
    assert m2.status == "OK" and m2.usable


# ----------------------------------------------------------------------
# gate evaluation (fail-closed)
# ----------------------------------------------------------------------

def _policy(tmp_path, gates, policy_id="p.v1", stage_id="s"):
    doc = {"schema_version": 1, "policy_id": policy_id, "stage_id": stage_id,
           "evidence_kind": "test", "gates": gates}
    p = tmp_path / "acceptance.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return lc.load_policy(p)


def test_gate_pass(tmp_path):
    pol = _policy(tmp_path, [
        {"id": "g1", "required": True, "metric": "m", "comparison": "within_range",
         "minimum": 0.0, "maximum": 1.0}])
    v = lc.evaluate_gates({"m": lc.Metric.measure("m", 0.5, "-")}, pol)
    assert v.status == lc.V_PASS and v.exit_code == 0


def test_gate_fail(tmp_path):
    pol = _policy(tmp_path, [
        {"id": "g1", "required": True, "metric": "m", "comparison": "at_most",
         "maximum": 1.0}])
    v = lc.evaluate_gates({"m": lc.Metric.measure("m", 2.0, "-")}, pol)
    assert v.status == lc.V_FAIL and v.exit_code == 1


def test_required_missing_metric_is_error(tmp_path):
    pol = _policy(tmp_path, [
        {"id": "g1", "required": True, "metric": "absent",
         "comparison": "at_least", "minimum": 0.0}])
    v = lc.evaluate_gates({}, pol)
    assert v.status == lc.V_ERROR and v.exit_code == 2
    assert v.gates[0].status == lc.GATE_ERROR


def test_required_nonfinite_metric_is_error(tmp_path):
    pol = _policy(tmp_path, [
        {"id": "g1", "required": True, "metric": "m", "comparison": "at_least",
         "minimum": 0.0}])
    v = lc.evaluate_gates({"m": lc.Metric.measure("m", float("nan"), "-")}, pol)
    assert v.status == lc.V_ERROR and v.exit_code == 2


def test_optional_missing_metric_is_skip_not_fail(tmp_path):
    pol = _policy(tmp_path, [
        {"id": "req", "required": True, "metric": "m", "comparison": "at_most",
         "maximum": 1.0},
        {"id": "opt", "required": False, "metric": "absent",
         "comparison": "at_most", "maximum": 1.0}])
    v = lc.evaluate_gates({"m": lc.Metric.measure("m", 0.5, "-")}, pol)
    assert v.status == lc.V_PASS and v.exit_code == 0
    opt = next(g for g in v.gates if g.id == "opt")
    assert opt.status == lc.GATE_SKIP


def test_empty_policy_is_error(tmp_path):
    pol = _policy(tmp_path, [])
    v = lc.evaluate_gates({}, pol)
    assert v.status == lc.V_ERROR and v.exit_code == 2


def test_zero_required_gates_is_error(tmp_path):
    pol = _policy(tmp_path, [
        {"id": "opt", "required": False, "metric": "m", "comparison": "at_most",
         "maximum": 1.0}])
    v = lc.evaluate_gates({"m": lc.Metric.measure("m", 0.5, "-")}, pol)
    assert v.status == lc.V_ERROR and v.exit_code == 2


def test_duplicate_required_gate_id_is_error(tmp_path):
    pol = _policy(tmp_path, [
        {"id": "dup", "required": True, "metric": "m", "comparison": "at_most",
         "maximum": 1.0},
        {"id": "dup", "required": True, "metric": "m", "comparison": "at_least",
         "minimum": 0.0}])
    v = lc.evaluate_gates({"m": lc.Metric.measure("m", 0.5, "-")}, pol)
    assert v.status == lc.V_ERROR and v.exit_code == 2


def test_abs_within_comparison(tmp_path):
    pol = _policy(tmp_path, [
        {"id": "g", "required": True, "metric": "m", "comparison": "abs_within",
         "target": 99.25, "tolerance": 0.5}])
    assert lc.evaluate_gates(
        {"m": lc.Metric.measure("m", 99.4, "eV")}, pol).status == lc.V_PASS
    assert lc.evaluate_gates(
        {"m": lc.Metric.measure("m", 98.0, "eV")}, pol).status == lc.V_FAIL


def test_unknown_comparison_rejected_at_load(tmp_path):
    with pytest.raises(lc.ContractError):
        _policy(tmp_path, [
            {"id": "g", "required": True, "metric": "m",
             "comparison": "made_up", "maximum": 1.0}])


def test_missing_bound_rejected_at_load(tmp_path):
    with pytest.raises(lc.ContractError):
        _policy(tmp_path, [
            {"id": "g", "required": True, "metric": "m",
             "comparison": "within_range", "minimum": 0.0}])  # no maximum


# ----------------------------------------------------------------------
# analysis lifecycle
# ----------------------------------------------------------------------

def test_analysis_lifecycle_single_run(tmp_path):
    run = _complete(tmp_path)
    loaded = lc.load_run(run.dir)
    pol = _policy(tmp_path, [
        {"id": "g1", "required": True, "metric": "m", "comparison": "at_most",
         "maximum": 1.0}], stage_id="test.stage")
    analysis = lc.begin_analysis([loaded], pol,
                                 results_root=tmp_path / "results")
    assert run.run_id in str(analysis.dir)
    m = lc.read_json_strict(analysis.manifest_path)
    assert m["status"] == lc.RUNNING
    assert m["members"][0]["run_id"] == run.run_id
    assert (analysis.dir / "acceptance_used.yaml").exists()

    metrics = {"m": lc.Metric.measure("m", 0.5, "-")}
    verdict = lc.evaluate_gates(metrics, pol)
    lc.write_metrics(analysis, metrics)
    lc.write_verdict(analysis, verdict)
    lc.complete_analysis(analysis, verdict)

    m = lc.read_json_strict(analysis.manifest_path)
    assert m["status"] == lc.COMPLETE
    assert m["exit_code"] == 0
    assert (analysis.dir / "metrics.json").exists()
    assert (analysis.dir / "verdict.json").exists()


def test_reanalysis_new_policy_new_dir_preserves_old(tmp_path):
    run = _complete(tmp_path)
    loaded = lc.load_run(run.dir)
    pol1 = _policy(tmp_path / "p1", [
        {"id": "g", "required": True, "metric": "m", "comparison": "at_most",
         "maximum": 1.0}], policy_id="p.v1", stage_id="test.stage")
    a1 = lc.begin_analysis([loaded], pol1, results_root=tmp_path / "results")
    lc.complete_analysis(a1, lc.evaluate_gates(
        {"m": lc.Metric.measure("m", 0.5, "-")}, pol1))

    pol2 = _policy(tmp_path / "p2", [
        {"id": "g", "required": True, "metric": "m", "comparison": "at_most",
         "maximum": 2.0}], policy_id="p.v2", stage_id="test.stage")
    a2 = lc.begin_analysis([loaded], pol2, results_root=tmp_path / "results")

    assert a1.dir != a2.dir            # different policy -> different analysis dir
    assert a1.manifest_path.exists()   # old analysis preserved
    assert lc.read_json_strict(a1.manifest_path)["status"] == lc.COMPLETE


def test_joint_analysis_dir_for_cohort(tmp_path):
    a = _complete(tmp_path, scenario="A", study_config={"gen": 1})
    b = _complete(tmp_path, scenario="B", study_config={"gen": 1})
    la, lb = lc.load_run(a.dir), lc.load_run(b.dir)
    pol = _policy(tmp_path, [
        {"id": "g", "required": True, "metric": "m", "comparison": "at_most",
         "maximum": 1.0}], stage_id="test.stage")
    analysis = lc.begin_analysis([la, lb], pol,
                                 results_root=tmp_path / "results")
    assert "joint_" in analysis.dir.parent.name
