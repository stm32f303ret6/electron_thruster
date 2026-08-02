"""The loader's whole job is refusing a constant that cannot prove its origin."""

import copy
from pathlib import Path

import pytest
import yaml

import calibration
from calibration import ProvenanceError, load_laws, load_runs, sha256_of

DESIGN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DESIGN_ROOT.parent
LAWS = DESIGN_ROOT / "calibration" / "laws.yaml"


# ----------------------------------------------------------------------
# the real file
# ----------------------------------------------------------------------

def test_committed_laws_load_and_verify():
    laws = load_laws()
    assert laws.k > 0 and laws.ke_ledger > 0 and laws.beta > 0
    assert 0.0 < laws.f_esc <= 1.0
    assert laws.area_m2 > 0 and laws.capacitance_F > 0
    assert laws.sha256 == sha256_of(LAWS)


def test_every_anchor_resolves_in_tree():
    """A fresh clone must be able to follow every constant to its evidence."""
    laws = load_laws()
    assert laws.anchors, "laws.yaml declared no anchors at all"
    for a in laws.anchors:
        path = a.resolve()
        assert path.is_file(), f"{a.constant} -> {a.anchored_to} missing"
        assert not Path(a.anchored_to).is_absolute()
        assert sha256_of(path) == a.sha256


def test_k_is_below_the_analytic_ideal():
    """The measured coefficient cannot beat the no-loss one."""
    laws = load_laws()
    assert laws.k < laws.k_ideal


def test_promoted_records_are_loadable():
    runs = load_runs()
    assert runs, "no promoted records"
    for name, rec in runs.items():
        assert rec["source"]["verdict_status"] == "PASS" or "forced" in rec, name
        assert isinstance(rec["plasma"]["n0_m3"], float), f"{name}: n0 not coerced"


# ----------------------------------------------------------------------
# the refusals
# ----------------------------------------------------------------------

def _write_variant(tmp_path, mutate) -> Path:
    doc = yaml.safe_load(LAWS.read_text(encoding="utf-8"))
    mutate(doc)
    out = tmp_path / "laws.yaml"
    out.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return out


def test_missing_provenance_entry_is_refused(tmp_path):
    path = _write_variant(tmp_path, lambda d: d["thrust"]["provenance"].pop("k"))
    with pytest.raises(ProvenanceError, match="no provenance entry"):
        load_laws(path)


def test_provenance_without_sha_is_refused(tmp_path):
    path = _write_variant(
        tmp_path, lambda d: d["thrust"]["provenance"]["k"].pop("sha256"))
    with pytest.raises(ProvenanceError, match="missing 'sha256'"):
        load_laws(path)


def test_missing_constant_is_refused(tmp_path):
    path = _write_variant(tmp_path, lambda d: d["collection"].pop("beta"))
    with pytest.raises(ProvenanceError, match="collection.beta is missing"):
        load_laws(path)


def test_missing_group_is_refused(tmp_path):
    path = _write_variant(tmp_path, lambda d: d.pop("body"))
    with pytest.raises(ProvenanceError, match="no 'body' group"):
        load_laws(path)


def test_vanished_anchor_is_refused(tmp_path):
    """The predecessor's exact failure mode: every cited run deleted."""
    path = _write_variant(
        tmp_path,
        lambda d: d["thrust"]["provenance"]["k"].update(
            anchored_to="pic_sims/validation_cases/deleted/metrics.json"))
    with pytest.raises(ProvenanceError, match="does not exist"):
        load_laws(path)


def test_changed_anchor_is_refused(tmp_path):
    path = _write_variant(
        tmp_path,
        lambda d: d["thrust"]["provenance"]["k"].update(sha256="00" * 32))
    with pytest.raises(ProvenanceError, match="has changed"):
        load_laws(path)


def test_verify_false_still_requires_structure(tmp_path):
    """Skipping the on-disk check must not skip the provenance requirement."""
    path = _write_variant(tmp_path, lambda d: d["beam"].pop("provenance"))
    with pytest.raises(ProvenanceError):
        load_laws(path, verify=False)


def test_absent_laws_file_is_a_clear_error(tmp_path):
    with pytest.raises(ProvenanceError, match="generated, never hand-written"):
        load_laws(tmp_path / "nope.yaml")


# ----------------------------------------------------------------------
# the YAML-1.1 float trap the loader exists to absorb
# ----------------------------------------------------------------------

def test_unsigned_exponent_is_coerced_to_float(tmp_path):
    """`1.627e12` is a STRING to PyYAML; a density that became text is a
    six-hours-in crash."""
    p = tmp_path / "x.yaml"
    p.write_text("plasma:\n  n0_m3: 1.627e12\n  Te_K: 1318.8\n", encoding="utf-8")
    doc = calibration.load_yaml(p)
    assert isinstance(doc["plasma"]["n0_m3"], float)
    assert doc["plasma"]["n0_m3"] == pytest.approx(1.627e12)


def test_real_strings_survive_coercion(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text("status: measured\nnote: 3 runs\n", encoding="utf-8")
    doc = calibration.load_yaml(p)
    assert doc["status"] == "measured"
    assert doc["note"] == "3 runs"


def test_anchor_paths_are_relative_to_the_repo_root(tmp_path):
    """The anchor must be repo-relative, not machine-absolute, or a fresh clone
    cannot check it."""
    laws = load_laws()
    for a in laws.anchors:
        assert a.resolve(REPO_ROOT).is_file()
        assert copy.copy(a).anchored_to.startswith("pic_sims/")
