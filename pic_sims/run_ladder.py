#!/usr/bin/env python3
"""Root ladder orchestrator: subprocess-only, verdict-driven.

Runs each requested stage through fresh subprocesses (never importing a stage's
WarpX/simulation code -- libwarpx cannot initialize twice in one process),
verifies every emitted run and analysis against its manifest on disk, advances
only when dependencies passed, applies the cross-stage checks, and writes one
auditable suite verdict.

    python run_ladder.py --check                 # validate contract + topology only
    python run_ladder.py                         # run + analyze the ladder group
    python run_ladder.py --stages characterization.slender_body   # a spoke
    python run_ladder.py --stages emitter.negative_cathode emitter.holed_anode
    python run_ladder.py --analyze-only          # re-analyze existing LATEST runs

A stage is complete only when its verdict says so; there is no marker-file or
snapshot-as-completion path.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

VALIDATION_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(VALIDATION_ROOT))

import ladder_contract as lc  # noqa: E402
from stages import STAGE_BY_ID, STAGES, Stage, topological_order  # noqa: E402
import cross_stage  # noqa: E402

SUITE_ROOT = VALIDATION_ROOT / "suite_results"

# Files every stage folder must contain (the directory contract, section 5.2).
_REQUIRED_FILES = ("config.yaml", "acceptance.yaml", "simulation.py",
                   "helpers.py", "analyze.py", "README.md")


# ======================================================================
# folder contract
# ======================================================================

def check_folder_contract(stage: Stage) -> list[str]:
    """Return a list of contract violations for one stage (empty == ok)."""
    problems = []
    if not stage.path.is_dir():
        return [f"{stage.id}: directory {stage.directory} is missing"]
    for name in _REQUIRED_FILES:
        if not (stage.path / name).is_file():
            problems.append(f"{stage.id}: missing {name}")
    if not (stage.path / "tests").is_dir():
        problems.append(f"{stage.id}: missing tests/ directory")
    return problems


def check_all_contracts() -> list[str]:
    problems = []
    for stage in STAGES:
        problems += check_folder_contract(stage)
    return problems


# ======================================================================
# subprocess helpers
# ======================================================================

def _run(cmd: list[str], cwd: Path, logfh) -> tuple[int, list[str]]:
    """Run a subprocess, tee combined output to logfh, return (rc, lines)."""
    logfh.write(f"\n$ (cd {cwd}) {' '.join(cmd)}\n")
    logfh.flush()
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)
    lines: list[str] = []
    for line in proc.stdout:  # type: ignore[union-attr]
        logfh.write(line)
        logfh.flush()
        lines.append(line.rstrip("\n"))
    proc.wait()
    return proc.returncode, lines


def _find_prefixed(lines: list[str], prefix: str) -> str | None:
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


# ======================================================================
# per-stage run + analyze
# ======================================================================

def run_stage_sims(stage: Stage, logfh) -> list[Path]:
    """Launch simulation.py once per scenario; return verified COMPLETE run dirs.

    Never trusts the exit code or the RUN_ID line alone -- it opens and verifies
    the manifest via ladder_contract.load_run.
    """
    scenarios = stage.scenarios or (None,)
    run_dirs: list[Path] = []
    for scn in scenarios:
        cmd = [sys.executable, "simulation.py"]
        if scn is not None:
            cmd += ["--scenario", scn]
        rc, lines = _run(cmd, stage.path, logfh)
        run_id = _find_prefixed(lines, "RUN_ID=")
        if rc != 0 or run_id is None:
            raise RuntimeError(
                f"{stage.id} scenario={scn}: simulation exited {rc} "
                f"(run_id={run_id})")
        run_dir = stage.path / "outputs" / run_id
        lc.load_run(run_dir)  # raises unless COMPLETE
        run_dirs.append(run_dir)
    return run_dirs


def analyze_stage(stage: Stage, run_dirs: list[Path], logfh) -> dict:
    """Launch analyze.py and verify the emitted analysis + strict verdict JSON."""
    rel = [str(p.relative_to(stage.path)) for p in run_dirs]
    if stage.scenarios:
        cmd = [sys.executable, "analyze.py", "--runs", *rel,
               "--policy", "acceptance.yaml"]
    else:
        cmd = [sys.executable, "analyze.py", "--run", rel[0],
               "--policy", "acceptance.yaml"]
    rc, lines = _run(cmd, stage.path, logfh)
    analysis_id = _find_prefixed(lines, "ANALYSIS_ID=")
    if analysis_id is None:
        raise RuntimeError(f"{stage.id}: analyze.py emitted no ANALYSIS_ID")

    # Locate and verify the analysis directory (single or joint cohort).
    analysis_dir = _locate_analysis(stage, run_dirs, analysis_id)
    manifest = lc.read_json_strict(analysis_dir / "analysis_manifest.json")
    verdict = lc.read_json_strict(analysis_dir / "verdict.json")
    if manifest["status"] != lc.COMPLETE:
        raise RuntimeError(f"{stage.id}: analysis {analysis_id} not COMPLETE")
    if verdict["exit_code"] != rc:
        raise RuntimeError(
            f"{stage.id}: analyze.py exit {rc} != verdict exit_code "
            f"{verdict['exit_code']}")
    return {
        "stage_id": stage.id,
        "run_ids": [p.name for p in run_dirs],
        "run_manifest_sha256": [
            lc.config_sha256(lc.read_json_strict(p / "manifest.json"))
            for p in run_dirs],
        "analysis_id": analysis_id,
        "analysis_dir": str(analysis_dir.relative_to(VALIDATION_ROOT)),
        "policy_id": verdict["policy_id"],
        "verdict_status": verdict["status"],
        "exit_code": verdict["exit_code"],
        "metrics_path": str((analysis_dir / "metrics.json")
                            .relative_to(VALIDATION_ROOT)),
    }


def _locate_analysis(stage: Stage, run_dirs: list[Path], analysis_id: str) -> Path:
    results = stage.path / "results"
    if len(run_dirs) == 1:
        cand = results / run_dirs[0].name / analysis_id
        if cand.is_dir():
            return cand
    # cohort: results/joint_<hash>/<analysis-id>/
    for joint in sorted(results.glob("joint_*")):
        cand = joint / analysis_id
        if cand.is_dir():
            return cand
    raise RuntimeError(
        f"{stage.id}: could not locate analysis {analysis_id} under {results}")


# ======================================================================
# suite driver
# ======================================================================

def run_suite(stage_ids: list[str] | None, *, analyze_only: bool) -> int:
    problems = check_all_contracts()
    if problems:
        for p in problems:
            print(f"[CONTRACT] {p}", file=sys.stderr)
        return lc.EXIT_ERROR

    order = topological_order(stage_ids)
    SUITE_ROOT.mkdir(parents=True, exist_ok=True)
    suite_id = lc._stamp(lc.utc_now())  # noqa: SLF001 -- shared stamp format
    suite_dir = lc._exclusive_dir(SUITE_ROOT, suite_id)  # noqa: SLF001
    log_path = suite_dir / "suite.log"

    results: dict[str, dict] = {}
    with open(log_path, "w", encoding="utf-8") as logfh:
        logfh.write(f"suite {suite_dir.name}: stages "
                    f"{[s.id for s in order]}\n")
        for stage in order:
            unmet = [d for d in stage.requires
                     if results.get(d, {}).get("verdict_status") != lc.V_PASS]
            if unmet:
                print(f"[SKIP] {stage.id}: unmet dependencies {unmet}")
                results[stage.id] = {"stage_id": stage.id,
                                     "verdict_status": "SKIP",
                                     "reason": f"unmet dependencies {unmet}"}
                continue
            try:
                if analyze_only:
                    run_dirs = _latest_runs(stage)
                else:
                    print(f"[RUN] {stage.id} ...")
                    run_dirs = run_stage_sims(stage, logfh)
                print(f"[ANALYZE] {stage.id} ...")
                res = analyze_stage(stage, run_dirs, logfh)
                results[stage.id] = res
                print(f"[{res['verdict_status']}] {stage.id} "
                      f"(exit {res['exit_code']}) -> {res['analysis_dir']}")
            except Exception as exc:  # noqa: BLE001
                print(f"[ERROR] {stage.id}: {exc}", file=sys.stderr)
                logfh.write(f"[ERROR] {stage.id}: {exc}\n")
                results[stage.id] = {"stage_id": stage.id,
                                     "verdict_status": lc.V_ERROR,
                                     "reason": str(exc)}

        cross = cross_stage.evaluate(results, VALIDATION_ROOT)
        for c in cross:
            logfh.write(f"[CROSS {c['status']}] {c['id']}: {c['detail']}\n")

    passed = all(r.get("verdict_status") == lc.V_PASS for r in results.values())
    cross_ok = all(c["status"] in (lc.GATE_PASS, lc.GATE_SKIP) for c in cross)
    suite_status = lc.V_PASS if (passed and cross_ok) else lc.V_FAIL
    suite_verdict = {
        "schema_version": lc.SCHEMA_VERSION,
        "suite_id": suite_dir.name,
        "created_at_utc": lc._iso(lc.utc_now()),  # noqa: SLF001
        "stages_requested": [s.id for s in order],
        "status": suite_status,
        "stage_results": list(results.values()),
        "cross_stage_checks": cross,
    }
    lc.write_json_atomic(suite_dir / "suite_verdict.json", suite_verdict)

    print("\n" + "=" * 72)
    print(f"SUITE {suite_dir.name}: {suite_status}")
    for c in cross:
        print(f"  [CROSS {c['status']}] {c['id']}: {c['detail']}")
    print(f"  -> {suite_dir / 'suite_verdict.json'}")
    print("=" * 72)
    _print_disk_usage()
    return lc.EXIT_PASS if suite_status == lc.V_PASS else lc.EXIT_FAIL


def _latest_runs(stage: Stage) -> list[Path]:
    """For --analyze-only: the newest COMPLETE run per scenario."""
    outputs = stage.path / "outputs"
    scenarios = stage.scenarios or (None,)
    picked = []
    for scn in scenarios:
        candidates = []
        for d in sorted(outputs.glob("2*")):
            if not (d / "manifest.json").is_file():
                continue
            try:
                loaded = lc.load_run(d)
            except lc.ContractError:
                continue
            if scn is None or loaded.scenario == scn:
                candidates.append(d)
        if not candidates:
            raise RuntimeError(f"{stage.id}: no COMPLETE run for scenario {scn}")
        picked.append(sorted(candidates)[-1])
    return picked


def _print_disk_usage() -> None:
    total = 0
    for stage in STAGES:
        out = stage.path / "outputs"
        if out.is_dir():
            total += sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"outputs/ disk usage: {total / 1e9:.2f} GB "
          f"(deleting any outputs/<run-id>/ is safe; no auto-GC)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="validation ladder orchestrator")
    ap.add_argument("--check", action="store_true",
                    help="validate the folder contract + topology, run nothing")
    ap.add_argument("--stages", nargs="+", default=None,
                    help="stage IDs to run (default: all)")
    ap.add_argument("--analyze-only", action="store_true",
                    help="re-analyze the newest COMPLETE runs, do not simulate")
    args = ap.parse_args(argv)

    if args.check:
        problems = check_all_contracts()
        try:
            topological_order(args.stages)
        except ValueError as exc:
            problems.append(f"topology: {exc}")
        if problems:
            for p in problems:
                print(f"[CONTRACT] {p}", file=sys.stderr)
            return lc.EXIT_ERROR
        print(f"OK: {len(STAGES)} stages satisfy the folder contract; "
              f"ladder is acyclic with all dependencies present.")
        return lc.EXIT_PASS

    return run_suite(args.stages, analyze_only=args.analyze_only)


if __name__ == "__main__":
    raise SystemExit(main())
