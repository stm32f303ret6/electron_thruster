#!/usr/bin/env python3
"""Shared, physics-free plumbing for the validation ladder.

This is the ONLY code shared between validation stages (see
``ARCHITECTURE.md``).  A stage duplicates its physics deliberately
so a reviewer can read one folder and see the whole model; the lifecycle
plumbing -- run/analysis IDs, immutable directories, manifests, strict JSON,
gate evaluation -- lives here so it is written and tested exactly once.

Hard rules this module obeys, and every future edit must keep:

- It never imports ``pywarpx``, PICMI, matplotlib, or an openPMD reader.
- It contains no physical formula.  A ratio, a Debye length, a sheath radius --
  all belong to a stage's ``helpers.py``.  This module only knows about IDs,
  directories, JSON, hashes, and the fail-closed gate algebra.
- JSON it writes is strict (``allow_nan=False``); JSON it reads rejects NaN/Inf.
  A missing or non-finite measurement can never be laundered into a PASS.

The public surface, grouped:

  hashing/serialization : canonical_json, config_sha256, sha256_text,
                          dumps_strict, write_json_atomic, read_json_strict
  ids/time              : utc_now, new_run_id, new_analysis_id
  run lifecycle         : begin_run, complete_run, fail_run, invalidate_run, Run
  loading evidence      : load_run, load_complete_runs, check_cohort, LoadedRun
  policy/gates          : load_policy, evaluate_gates, Policy, GateSpec,
                          Metric, Gate, Verdict
  analysis lifecycle    : begin_analysis, complete_analysis, fail_analysis,
                          Analysis
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import yaml

SCHEMA_VERSION = 1

# Run states (section 8.2).  RUNNING is written before WarpX initializes;
# COMPLETE only after artifacts and the final iteration are verified.
NEW, RUNNING, COMPLETE, FAILED, INVALID = (
    "NEW", "RUNNING", "COMPLETE", "FAILED", "INVALID")
_TERMINAL_RUN_STATES = frozenset({COMPLETE, FAILED, INVALID})

# Gate statuses (section 9.2).
GATE_PASS, GATE_FAIL, GATE_ERROR, GATE_SKIP = "PASS", "FAIL", "ERROR", "SKIP"
# Verdict statuses.
V_PASS, V_FAIL, V_ERROR = "PASS", "FAIL", "ERROR"
# Process exit codes: 0 all required pass; 1 valid evidence, gate(s) fail;
# 2 analysis error / missing evidence / incompatible runs / invalid policy.
EXIT_PASS, EXIT_FAIL, EXIT_ERROR = 0, 1, 2

_COMPARISONS = ("within_range", "at_most", "at_least", "abs_within")


class ContractError(Exception):
    """A ladder-contract violation that should map to exit code 2.

    Raised for invalid policies, incompatible or incomplete evidence, and
    malformed manifests -- never for a plain gate FAIL (that is a Verdict, not
    an exception).
    """


class RunInvalid(ContractError):
    """A run returned but its artifacts / final iteration are missing or wrong.

    The run directory is transitioned to INVALID before this is raised, so a
    caller's generic ``except`` handler must not relabel it FAILED.
    """


# ======================================================================
# canonical serialization and hashing
# ======================================================================

def _canonicalize(obj: Any) -> Any:
    """Recursively coerce ``obj`` into plain JSON types with stable ordering.

    Numeric leaves must be finite: NaN/Inf in a config or metric is a bug, not a
    value to be silently hashed.  numpy scalars are accepted via ``.item()`` so
    a stage need not strip them by hand, but arbitrary objects are rejected.
    """
    if isinstance(obj, Mapping):
        return {str(k): _canonicalize(obj[k]) for k in obj}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(v) for v in obj]
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ContractError(f"non-finite float in payload: {obj!r}")
        return obj
    item = getattr(obj, "item", None)  # numpy scalar -> python scalar
    if callable(item):
        return _canonicalize(item())
    raise ContractError(f"cannot serialize object of type {type(obj).__name__}")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, no NaN/Inf."""
    return json.dumps(
        _canonicalize(obj), sort_keys=True, separators=(",", ":"),
        allow_nan=False, ensure_ascii=True)


def config_sha256(config: Mapping[str, Any]) -> str:
    """SHA-256 of a config's canonical serialization (hex)."""
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    """SHA-256 of a text blob (used for policy files, verbatim)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dumps_strict(obj: Any) -> str:
    """Pretty strict JSON; raises if any float is NaN/Inf."""
    return json.dumps(_canonicalize(obj), indent=2, allow_nan=False)


def write_json_atomic(path: Path | str, obj: Any) -> None:
    """Serialize strict JSON and publish it atomically (temp + fsync + replace).

    A reader therefore only ever sees a whole, valid document -- never a half
    written manifest from a crash mid-write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = dumps_strict(obj)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _reject_constant(token: str) -> float:
    raise ContractError(f"non-finite JSON constant not allowed: {token}")


def read_json_strict(path: Path | str) -> Any:
    """Read JSON, rejecting the ``NaN``/``Infinity`` extensions on the way in."""
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text, parse_constant=_reject_constant)


# ======================================================================
# time and identifiers
# ======================================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(dt: datetime) -> str:
    """Compact UTC stamp for directory/run IDs, e.g. 20260801T183045Z."""
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _iso(dt: datetime) -> str:
    """ISO-8601 UTC for manifest fields, e.g. 2026-08-01T18:30:45Z."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id(config_hash: str, scenario: Optional[str] = None,
               *, now: Optional[datetime] = None) -> str:
    """UTC stamp + optional scenario + first 8 hex of the config hash."""
    parts = [_stamp(now or utc_now())]
    if scenario:
        parts.append(str(scenario))
    parts.append(config_hash[:8])
    return "_".join(parts)


def new_analysis_id(policy_hash: str, *, now: Optional[datetime] = None) -> str:
    """UTC stamp + first 8 hex of the policy hash."""
    return f"{_stamp(now or utc_now())}_{policy_hash[:8]}"


# ======================================================================
# provenance (git / interpreter / package versions)
# ======================================================================

def _git(args: Sequence[str], cwd: Path) -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True,
            timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def git_commit(cwd: Path | str) -> Optional[str]:
    return _git(["rev-parse", "HEAD"], Path(cwd))


def git_dirty(cwd: Path | str) -> Optional[bool]:
    status = _git(["status", "--porcelain"], Path(cwd))
    if status is None:
        return None
    return bool(status)


def _default_provenance(cwd: Path) -> dict:
    threads = os.environ.get("OMP_NUM_THREADS")
    return {
        "git_commit": git_commit(cwd),
        "git_dirty": git_dirty(cwd),
        "python_version": platform.python_version(),
        "warpx_version": None,
        "mpi_ranks": 1,
        "omp_threads": int(threads) if threads and threads.isdigit() else None,
    }


# ======================================================================
# exclusive directory creation
# ======================================================================

def _exclusive_dir(parent: Path, name: str) -> Path:
    """Create ``parent/name`` with ``exist_ok=False``.

    On collision (a second run started inside the same UTC second) a numeric
    suffix is appended so the directory is still fresh and immutable; we never
    write into an existing run directory.
    """
    parent.mkdir(parents=True, exist_ok=True)
    candidate = parent / name
    suffix = 1
    while True:
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            candidate = parent / f"{name}-{suffix}"
            suffix += 1
            if suffix > 9999:
                raise ContractError(
                    f"could not create a fresh directory under {parent}")


# ======================================================================
# run lifecycle
# ======================================================================

@dataclass
class Run:
    """A live, RUNNING execution handle returned by :func:`begin_run`."""
    run_id: str
    stage_id: str
    scenario: Optional[str]
    dir: Path
    diags_dir: Path
    manifest_path: Path
    config: dict
    config_hash: str
    expected_final_iteration: Optional[int]
    created_at: datetime
    provenance_dir: Path


def begin_run(*, run_root: Path | str, stage_id: str, config: Mapping[str, Any],
              scenario: Optional[str] = None,
              study_config: Optional[Mapping[str, Any]] = None,
              random_seed: Optional[int] = None,
              expected_final_iteration: Optional[int] = None,
              source_files: Sequence[Path | str] = (),
              provenance: Optional[Mapping[str, Any]] = None) -> Run:
    """Open a fresh, immutable run directory and write its RUNNING manifest.

    ``config`` is the *effective* physics config of this run: it is frozen to
    ``config_used.yaml``, hashed for the run ID, and never re-read from the live
    stage YAML afterwards.  ``study_config`` (a scenario's full source study) is
    hashed into ``study_sha256`` so scenario runs can be checked for
    compatibility.  ``source_files`` (typically ``simulation.py`` and
    ``helpers.py``) are copied into ``sources_used/`` so the run is
    reconstructible regardless of git state.
    """
    run_root = Path(run_root)
    cfg = _canonicalize(config)
    config_hash = config_sha256(cfg)
    created = utc_now()
    run_id = new_run_id(config_hash, scenario, now=created)
    run_dir = _exclusive_dir(run_root, run_id)
    # The real run_id may have gained a collision suffix; keep them consistent.
    run_id = run_dir.name

    diags_dir = run_dir / "diags"
    diags_dir.mkdir()
    sources_dir = run_dir / "sources_used"
    sources_dir.mkdir()
    for src in source_files:
        src = Path(src)
        if src.is_file():
            shutil.copy2(src, sources_dir / src.name)

    (run_dir / "config_used.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    prov = dict(_default_provenance(run_root))
    if provenance:
        prov.update({k: v for k, v in provenance.items() if v is not None})

    study_hash = config_sha256(study_config) if study_config is not None else None

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "stage_id": stage_id,
        "scenario": scenario,
        "status": RUNNING,
        "created_at_utc": _iso(created),
        "completed_at_utc": None,
        "case_sha256": config_hash,
        "study_sha256": study_hash,
        "git_commit": prov["git_commit"],
        "git_dirty": prov["git_dirty"],
        "python_version": prov["python_version"],
        "warpx_version": prov["warpx_version"],
        "mpi_ranks": prov["mpi_ranks"],
        "omp_threads": prov["omp_threads"],
        "random_seed": random_seed,
        "expected_final_iteration": expected_final_iteration,
        "observed_final_iteration": None,
        "artifacts": [],
        "error": None,
    }
    manifest_path = run_dir / "manifest.json"
    write_json_atomic(manifest_path, manifest)
    _write_latest(run_root, run_id)

    return Run(
        run_id=run_id, stage_id=stage_id, scenario=scenario, dir=run_dir,
        diags_dir=diags_dir, manifest_path=manifest_path, config=dict(cfg),
        config_hash=config_hash,
        expected_final_iteration=expected_final_iteration, created_at=created,
        provenance_dir=sources_dir)


def _read_manifest(manifest_path: Path) -> dict:
    return read_json_strict(manifest_path)


def _verify_artifacts(run: Run, patterns: Sequence[str]) -> list[dict]:
    """Each pattern (glob relative to the run's diags dir) must match >= 1
    non-empty file.  Returns the artifact records for the manifest."""
    records = []
    for pattern in patterns:
        matches = [p for p in sorted(run.diags_dir.glob(pattern)) if p.is_file()]
        nonempty = [p for p in matches if p.stat().st_size > 0]
        if not nonempty:
            raise RunInvalid(
                f"required artifact '{pattern}' missing or empty under "
                f"{run.diags_dir}")
        total = sum(p.stat().st_size for p in nonempty)
        records.append({
            "path": f"diags/{pattern}",
            "bytes": total,
            "files": len(nonempty),
        })
    return records


def complete_run(run: Run, *, expected_artifacts: Sequence[str] = (),
                 observed_final_iteration: Optional[int] = None) -> None:
    """Verify artifacts and the final iteration, then publish COMPLETE.

    Any shortfall transitions the run to INVALID and raises :class:`RunInvalid`
    -- COMPLETE is written only when the evidence is actually there.
    """
    manifest = _read_manifest(run.manifest_path)
    try:
        artifacts = _verify_artifacts(run, expected_artifacts)
        expected = run.expected_final_iteration
        if expected is not None:
            if observed_final_iteration is None:
                raise RunInvalid(
                    "expected_final_iteration set but observed_final_iteration "
                    "was not provided")
            if int(observed_final_iteration) != int(expected):
                raise RunInvalid(
                    f"final iteration mismatch: expected {expected}, observed "
                    f"{observed_final_iteration}")
    except RunInvalid as exc:
        manifest["status"] = INVALID
        manifest["completed_at_utc"] = _iso(utc_now())
        manifest["observed_final_iteration"] = (
            None if observed_final_iteration is None
            else int(observed_final_iteration))
        manifest["error"] = str(exc)
        write_json_atomic(run.manifest_path, manifest)
        raise

    manifest["status"] = COMPLETE
    manifest["completed_at_utc"] = _iso(utc_now())
    manifest["observed_final_iteration"] = (
        None if observed_final_iteration is None
        else int(observed_final_iteration))
    manifest["artifacts"] = artifacts
    manifest["error"] = None
    write_json_atomic(run.manifest_path, manifest)


def _terminate_run(run: Run, status: str, error: str) -> None:
    manifest = _read_manifest(run.manifest_path)
    if manifest.get("status") in _TERMINAL_RUN_STATES:
        return  # already COMPLETE/FAILED/INVALID -- do not relabel
    manifest["status"] = status
    manifest["completed_at_utc"] = _iso(utc_now())
    manifest["error"] = error
    write_json_atomic(run.manifest_path, manifest)


def fail_run(run: Run, exc: BaseException | str) -> None:
    """Mark a run FAILED (process raised / exited unsuccessfully).

    Idempotent against terminal states so it will not clobber an INVALID set by
    :func:`complete_run`.
    """
    _terminate_run(run, FAILED, _describe(exc))


def invalidate_run(run: Run, reason: str) -> None:
    """Mark a run INVALID (returned but its evidence is unusable)."""
    _terminate_run(run, INVALID, reason)


def _describe(exc: BaseException | str) -> str:
    if isinstance(exc, str):
        return exc
    return f"{type(exc).__name__}: {exc}"


def _write_latest(run_root: Path, run_id: str) -> None:
    """Optional convenience pointer; readers must still verify the manifest."""
    try:
        (run_root / "LATEST").write_text(run_id + "\n", encoding="utf-8")
    except OSError:
        pass


# ======================================================================
# loading completed evidence
# ======================================================================

@dataclass(frozen=True)
class LoadedRun:
    """A verified-COMPLETE run, ready to analyze."""
    run_id: str
    stage_id: str
    scenario: Optional[str]
    dir: Path
    diags_dir: Path
    manifest: dict
    config: dict

    @property
    def manifest_sha256(self) -> str:
        return config_sha256(self.manifest)

    @property
    def study_sha256(self) -> Optional[str]:
        return self.manifest.get("study_sha256")


def load_run(run_dir: Path | str) -> LoadedRun:
    """Load a run directory, requiring a verified COMPLETE manifest.

    Raises :class:`ContractError` (exit 2) if the directory, manifest, or frozen
    config is missing, or the run is not COMPLETE.  Never trusts a ``LATEST``
    pointer or an exit code -- only the manifest on disk.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ContractError(f"no manifest at {manifest_path}")
    manifest = _read_manifest(manifest_path)
    status = manifest.get("status")
    if status != COMPLETE:
        raise ContractError(
            f"run {run_dir.name} is {status}, not COMPLETE -- refusing to "
            f"analyze incomplete evidence")
    cfg_path = run_dir / "config_used.yaml"
    if not cfg_path.is_file():
        raise ContractError(f"no frozen config_used.yaml at {cfg_path}")
    config = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return LoadedRun(
        run_id=manifest["run_id"], stage_id=manifest["stage_id"],
        scenario=manifest.get("scenario"), dir=run_dir,
        diags_dir=run_dir / "diags", manifest=manifest, config=config)


def load_complete_runs(run_dirs: Sequence[Path | str]) -> list[LoadedRun]:
    """Load several runs; every one must be COMPLETE."""
    if not run_dirs:
        raise ContractError("no runs given")
    return [load_run(d) for d in run_dirs]


def check_cohort(runs: Sequence[LoadedRun], *, stage_id: Optional[str] = None,
                 require_scenarios: Optional[Sequence[str]] = None) -> None:
    """Verify a multi-run cohort is mutually compatible.

    All members must share the stage ID and the source-study hash; if
    ``require_scenarios`` is given, each must appear exactly once.  Any mismatch
    is a :class:`ContractError` (exit 2) -- incompatible sets never analyze.
    """
    if not runs:
        raise ContractError("empty cohort")
    stage_ids = {r.stage_id for r in runs}
    if len(stage_ids) != 1:
        raise ContractError(f"cohort spans multiple stages: {sorted(stage_ids)}")
    if stage_id is not None and next(iter(stage_ids)) != stage_id:
        raise ContractError(
            f"cohort stage {next(iter(stage_ids))} != expected {stage_id}")
    study_hashes = {r.study_sha256 for r in runs}
    if len(study_hashes) != 1:
        raise ContractError(
            "cohort mixes configuration generations (study_sha256 differs): "
            f"{sorted(str(h) for h in study_hashes)}")
    scenarios = [r.scenario for r in runs]
    if len(set(scenarios)) != len(scenarios):
        raise ContractError(f"cohort has duplicate scenarios: {scenarios}")
    if require_scenarios is not None:
        want = set(require_scenarios)
        have = set(scenarios)
        if want != have:
            raise ContractError(
                f"cohort scenarios {sorted(str(s) for s in have)} != required "
                f"{sorted(want)}")


# ======================================================================
# metrics, gates, verdicts
# ======================================================================

@dataclass(frozen=True)
class Metric:
    """One measurement.  A missing/non-finite value is status ERROR, value
    ``None`` -- never a silent NaN.  Build with :meth:`measure` or :meth:`error`.
    """
    id: str
    value: Optional[float]
    unit: str
    status: str = "OK"
    uncertainty: Optional[float] = None
    sample_count: Optional[int] = None
    window: Optional[dict] = None
    source: Optional[str] = None

    @classmethod
    def measure(cls, id: str, value: Any, unit: str, *,
                uncertainty: Optional[float] = None,
                sample_count: Optional[int] = None,
                window: Optional[dict] = None,
                source: Optional[str] = None) -> "Metric":
        """A measured metric; coerced to ERROR if the value is missing/non-finite."""
        ok = value is not None and math.isfinite(float(value))
        unc = (uncertainty if (uncertainty is not None
                               and math.isfinite(float(uncertainty))) else None)
        return cls(
            id=id, value=(float(value) if ok else None), unit=unit,
            status=("OK" if ok else "ERROR"), uncertainty=unc,
            sample_count=sample_count, window=window, source=source)

    @classmethod
    def error(cls, id: str, unit: str, *, source: Optional[str] = None,
              sample_count: Optional[int] = None) -> "Metric":
        return cls(id=id, value=None, unit=unit, status="ERROR",
                   source=source, sample_count=sample_count)

    @property
    def usable(self) -> bool:
        return (self.status == "OK" and self.value is not None
                and math.isfinite(self.value))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "status": self.status, "value": self.value,
            "unit": self.unit, "uncertainty": self.uncertainty,
            "sample_count": self.sample_count, "window": self.window,
            "source": self.source,
        }


@dataclass(frozen=True)
class GateSpec:
    """One acceptance-policy gate, parsed from ``acceptance.yaml``."""
    id: str
    required: bool
    metric_id: str
    comparison: str
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    target: Optional[float] = None
    tolerance: Optional[float] = None

    def describe_bound(self) -> str:
        if self.comparison == "within_range":
            return f"in [{self.minimum:g}, {self.maximum:g}]"
        if self.comparison == "at_most":
            return f"<= {self.maximum:g}"
        if self.comparison == "at_least":
            return f">= {self.minimum:g}"
        if self.comparison == "abs_within":
            return f"|x - {self.target:g}| <= {self.tolerance:g}"
        return self.comparison


@dataclass(frozen=True)
class Gate:
    """The evaluated result of one :class:`GateSpec` against a metric."""
    id: str
    status: str
    required: bool
    metric_id: str
    comparison: str
    value: Optional[float]
    detail: str

    def to_dict(self) -> dict:
        return {
            "id": self.id, "status": self.status, "required": self.required,
            "metric": self.metric_id, "comparison": self.comparison,
            "value": self.value, "detail": self.detail,
        }


@dataclass(frozen=True)
class Verdict:
    """The stage-level roll-up of all gates, with its process exit code."""
    stage_id: str
    policy_id: str
    status: str
    exit_code: int
    gates: tuple[Gate, ...]
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "stage_id": self.stage_id, "policy_id": self.policy_id,
            "status": self.status, "exit_code": self.exit_code,
            "detail": self.detail,
            "gates": [g.to_dict() for g in self.gates],
        }


@dataclass(frozen=True)
class Policy:
    """A parsed, hashed ``acceptance.yaml``."""
    policy_id: str
    stage_id: str
    evidence_kind: str
    sha256: str
    gates: tuple[GateSpec, ...]
    path: Path
    text: str
    raw: dict


def load_policy(path: Path | str) -> Policy:
    """Parse and structurally validate an acceptance policy file.

    Structural problems (unknown comparison, missing bound, duplicate/absent
    fields) raise :class:`ContractError` -- an invalid policy is exit 2, distinct
    from a valid policy whose gates merely fail.  An empty ``gates`` list is
    *not* rejected here; :func:`evaluate_gates` turns "zero required gates" into
    an ERROR verdict.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if not isinstance(raw, Mapping):
        raise ContractError(f"policy {path} is not a mapping")
    for key in ("policy_id", "stage_id", "evidence_kind"):
        if key not in raw:
            raise ContractError(f"policy {path} missing '{key}'")
    gates_raw = raw.get("gates") or []
    if not isinstance(gates_raw, list):
        raise ContractError(f"policy {path}: 'gates' must be a list")
    gates = tuple(_parse_gate(g, path) for g in gates_raw)
    return Policy(
        policy_id=str(raw["policy_id"]), stage_id=str(raw["stage_id"]),
        evidence_kind=str(raw["evidence_kind"]), sha256=sha256_text(text),
        gates=gates, path=path, text=text, raw=dict(raw))


def _parse_gate(g: Mapping[str, Any], path: Path) -> GateSpec:
    if not isinstance(g, Mapping):
        raise ContractError(f"policy {path}: gate is not a mapping: {g!r}")
    for key in ("id", "metric", "comparison"):
        if key not in g:
            raise ContractError(f"policy {path}: gate missing '{key}': {g!r}")
    comparison = str(g["comparison"])
    if comparison not in _COMPARISONS:
        raise ContractError(
            f"policy {path}: gate '{g['id']}' has unknown comparison "
            f"'{comparison}' (allowed: {', '.join(_COMPARISONS)})")

    def _num(name: str) -> Optional[float]:
        if name not in g or g[name] is None:
            return None
        v = float(g[name])
        if not math.isfinite(v):
            raise ContractError(
                f"policy {path}: gate '{g['id']}' bound '{name}' is non-finite")
        return v

    minimum, maximum = _num("minimum"), _num("maximum")
    target, tolerance = _num("target"), _num("tolerance")
    required = bool(g.get("required", True))

    if comparison == "within_range" and (minimum is None or maximum is None):
        raise ContractError(
            f"policy {path}: gate '{g['id']}' within_range needs minimum+maximum")
    if comparison == "at_most" and maximum is None:
        raise ContractError(
            f"policy {path}: gate '{g['id']}' at_most needs maximum")
    if comparison == "at_least" and minimum is None:
        raise ContractError(
            f"policy {path}: gate '{g['id']}' at_least needs minimum")
    if comparison == "abs_within" and (target is None or tolerance is None):
        raise ContractError(
            f"policy {path}: gate '{g['id']}' abs_within needs target+tolerance")

    return GateSpec(
        id=str(g["id"]), required=required, metric_id=str(g["metric"]),
        comparison=comparison, minimum=minimum, maximum=maximum,
        target=target, tolerance=tolerance)


def _compare(spec: GateSpec, value: float) -> bool:
    if spec.comparison == "within_range":
        return spec.minimum <= value <= spec.maximum
    if spec.comparison == "at_most":
        return value <= spec.maximum
    if spec.comparison == "at_least":
        return value >= spec.minimum
    if spec.comparison == "abs_within":
        return abs(value - spec.target) <= spec.tolerance
    raise ContractError(f"unknown comparison: {spec.comparison}")


def evaluate_gates(metrics: Mapping[str, Metric], policy: Policy) -> Verdict:
    """Apply the fail-closed verdict rules of section 9.2.

    - Zero required gates -> ERROR (an empty policy never passes).
    - A required gate ID appearing more than once -> ERROR.
    - A required gate whose metric is missing or non-finite -> its gate is
      ERROR; an *optional* gate in that situation is SKIP.
    - Stage PASS iff every required gate is PASS.
    - Any required ERROR/SKIP -> exit 2; else any required FAIL -> exit 1.
    """
    gates: list[Gate] = []
    for spec in policy.gates:
        gates.append(_evaluate_one(spec, metrics))

    required = [g for g in gates if g.required]
    verdict_gates = tuple(gates)

    if not required:
        return Verdict(
            policy.stage_id, policy.policy_id, V_ERROR, EXIT_ERROR,
            verdict_gates, "policy has zero required gates")

    seen: dict[str, int] = {}
    for g in required:
        seen[g.id] = seen.get(g.id, 0) + 1
    dupes = sorted(gid for gid, n in seen.items() if n > 1)
    if dupes:
        return Verdict(
            policy.stage_id, policy.policy_id, V_ERROR, EXIT_ERROR,
            verdict_gates, f"duplicate required gate id(s): {dupes}")

    n_error = sum(1 for g in required if g.status in (GATE_ERROR, GATE_SKIP))
    n_fail = sum(1 for g in required if g.status == GATE_FAIL)
    n_pass = sum(1 for g in required if g.status == GATE_PASS)

    if n_error:
        return Verdict(
            policy.stage_id, policy.policy_id, V_ERROR, EXIT_ERROR,
            verdict_gates,
            f"{n_error} required gate(s) unevaluable (missing/non-finite)")
    if n_fail:
        return Verdict(
            policy.stage_id, policy.policy_id, V_FAIL, EXIT_FAIL,
            verdict_gates, f"{n_fail} required gate(s) failed")
    return Verdict(
        policy.stage_id, policy.policy_id, V_PASS, EXIT_PASS, verdict_gates,
        f"all {n_pass} required gate(s) passed")


def _evaluate_one(spec: GateSpec, metrics: Mapping[str, Metric]) -> Gate:
    metric = metrics.get(spec.metric_id)
    bound = spec.describe_bound()
    if metric is None or not metric.usable:
        status = GATE_ERROR if spec.required else GATE_SKIP
        why = "metric absent" if metric is None else f"metric {metric.status}"
        return Gate(spec.id, status, spec.required, spec.metric_id,
                    spec.comparison, None,
                    f"{why} for '{spec.metric_id}' ({bound})")
    try:
        passed = _compare(spec, metric.value)
    except ContractError as exc:
        return Gate(spec.id, GATE_ERROR, spec.required, spec.metric_id,
                    spec.comparison, metric.value, str(exc))
    status = GATE_PASS if passed else GATE_FAIL
    return Gate(spec.id, status, spec.required, spec.metric_id, spec.comparison,
                metric.value, f"{metric.value:g} {bound}")


# ======================================================================
# analysis lifecycle
# ======================================================================

@dataclass
class Analysis:
    """A live analysis handle returned by :func:`begin_analysis`."""
    analysis_id: str
    dir: Path
    figures_dir: Path
    manifest_path: Path
    members: tuple[LoadedRun, ...]
    policy: Policy


def _cohort_key(runs: Sequence[LoadedRun]) -> str:
    if len(runs) == 1:
        return runs[0].run_id
    joined = "\n".join(sorted(r.run_id for r in runs))
    return "joint_" + hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8]


def begin_analysis(evidence: Sequence[LoadedRun], policy: Policy, *,
                   results_root: Path | str,
                   analyzer_source: Optional[Path | str] = None) -> Analysis:
    """Open a fresh, immutable analysis directory and write its RUNNING manifest.

    Layout: ``results/<run-id>/<analysis-id>/`` for a single run, or
    ``results/joint_<hash>/<analysis-id>/`` for a cohort.  A changed policy or
    analyzer yields a new ``<analysis-id>``; nothing is ever overwritten.
    ``acceptance_used.yaml`` and a copy of the analyzer are stored alongside.
    """
    results_root = Path(results_root)
    parent = results_root / _cohort_key(evidence)
    created = utc_now()
    analysis_id = new_analysis_id(policy.sha256, now=created)
    adir = _exclusive_dir(parent, analysis_id)
    analysis_id = adir.name
    figures_dir = adir / "figures"
    figures_dir.mkdir()

    (adir / "acceptance_used.yaml").write_text(policy.text, encoding="utf-8")
    if analyzer_source is not None and Path(analyzer_source).is_file():
        shutil.copy2(analyzer_source, adir / Path(analyzer_source).name)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "analysis_id": analysis_id,
        "stage_id": policy.stage_id,
        "status": RUNNING,
        "created_at_utc": _iso(created),
        "completed_at_utc": None,
        "policy_id": policy.policy_id,
        "policy_sha256": policy.sha256,
        "evidence_kind": policy.evidence_kind,
        "members": [
            {"run_id": r.run_id, "scenario": r.scenario,
             "manifest_sha256": r.manifest_sha256} for r in evidence
        ],
        "analyzer_git_commit": git_commit(results_root),
        "analyzer_git_dirty": git_dirty(results_root),
        "verdict_status": None,
        "exit_code": None,
        "error": None,
    }
    manifest_path = adir / "analysis_manifest.json"
    write_json_atomic(manifest_path, manifest)

    return Analysis(
        analysis_id=analysis_id, dir=adir, figures_dir=figures_dir,
        manifest_path=manifest_path, members=tuple(evidence), policy=policy)


def complete_analysis(analysis: Analysis, verdict: Verdict) -> None:
    """Publish COMPLETE with the verdict status and exit code recorded."""
    manifest = _read_manifest(analysis.manifest_path)
    manifest["status"] = COMPLETE
    manifest["completed_at_utc"] = _iso(utc_now())
    manifest["verdict_status"] = verdict.status
    manifest["exit_code"] = verdict.exit_code
    manifest["error"] = None
    write_json_atomic(analysis.manifest_path, manifest)


def fail_analysis(analysis: Analysis, exc: BaseException | str) -> None:
    """Mark an analysis FAILED (the analyzer raised before a verdict)."""
    manifest = _read_manifest(analysis.manifest_path)
    if manifest.get("status") in _TERMINAL_RUN_STATES:
        return
    manifest["status"] = FAILED
    manifest["completed_at_utc"] = _iso(utc_now())
    manifest["exit_code"] = EXIT_ERROR
    manifest["error"] = _describe(exc)
    write_json_atomic(analysis.manifest_path, manifest)


def write_metrics(analysis: Analysis, metrics: Mapping[str, Metric]) -> Path:
    """Publish ``metrics.json`` (the machine-readable record of every measurement)."""
    path = analysis.dir / "metrics.json"
    write_json_atomic(path, {
        "analysis_id": analysis.analysis_id,
        "metrics": [m.to_dict() for m in metrics.values()],
    })
    return path


def write_verdict(analysis: Analysis, verdict: Verdict) -> Path:
    """Publish ``verdict.json`` (the gate roll-up and exit code)."""
    path = analysis.dir / "verdict.json"
    payload = verdict.to_dict()
    payload["analysis_id"] = analysis.analysis_id
    write_json_atomic(path, payload)
    return path


# Re-exported for stages that want the raw dataclass-to-dict.
__all__ = [
    "SCHEMA_VERSION", "NEW", "RUNNING", "COMPLETE", "FAILED", "INVALID",
    "GATE_PASS", "GATE_FAIL", "GATE_ERROR", "GATE_SKIP",
    "V_PASS", "V_FAIL", "V_ERROR", "EXIT_PASS", "EXIT_FAIL", "EXIT_ERROR",
    "ContractError", "RunInvalid",
    "canonical_json", "config_sha256", "sha256_text", "dumps_strict",
    "write_json_atomic", "read_json_strict",
    "utc_now", "new_run_id", "new_analysis_id",
    "git_commit", "git_dirty",
    "Run", "begin_run", "complete_run", "fail_run", "invalidate_run",
    "LoadedRun", "load_run", "load_complete_runs", "check_cohort",
    "Metric", "GateSpec", "Gate", "Verdict", "Policy",
    "load_policy", "evaluate_gates",
    "Analysis", "begin_analysis", "complete_analysis", "fail_analysis",
    "write_metrics", "write_verdict",
]
