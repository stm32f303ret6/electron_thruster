#!/usr/bin/env python3
r"""promote.py — turn a PASSING ladder analysis into a calibration record.

    python3 promote.py --analysis ../pic_sims/validation_cases/capstone/2_chipsat_thruster/reference_results/20260801T142601Z_2f822a95 \
                       --name capstone_float200
    python3 promote.py --analysis <dir> --name <n> --scenario A_day_p95

THE REFUSAL IS THE POINT. A measurement is only allowed into
``calibration/runs/`` if the analysis that produced it recorded
``verdict.json: status == PASS``. Promoting a FAILED or ERRORED run would put a
number the ladder rejected into the model the ladder is supposed to validate,
and the loop would close on itself. ``--force`` exists for the rare deliberate
case (promoting a run whose failure is in an unrelated gate) and it is recorded
IN THE RECORD, with the reason, so a reader of the YAML sees it without going
back to the shell history.

This is the ONLY writer of ``calibration/runs/``.

Depends on: PyYAML.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

DESIGN_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DESIGN_ROOT.parent
sys.path.insert(0, str(DESIGN_ROOT))

import yaml  # noqa: E402

from calibration import sha256_of  # noqa: E402

RUNS_DIR = DESIGN_ROOT / "calibration" / "runs"

#: Metrics copied into every record, with the key they get.  A metric that is
#: absent is simply omitted -- different stages measure different things -- but
#: the four REQUIRED ones below must be present or the promotion is refused,
#: because refit_laws.py cannot derive a single constant without them.
_METRIC_MAP = {
    "f_beam_nN": "f_beam_nN",
    "phi_body_V": "phi_body_V",
    "escape_fraction_pct": "escape_pct",
    "exhaust_ke_mean_eV": "exhaust_ke_eV",
    "current_balance": "current_balance",
    "edge_phi_max_V": "edge_phi_max_V",
    "late_dphidt_V_per_ns": "late_dphidt_V_per_ns",
    "ke_predicted_eV": "ke_predicted_eV",
}
_REQUIRED = ("f_beam_nN", "phi_body_V", "escape_pct", "exhaust_ke_eV")


class PromotionRefused(SystemExit):
    """The analysis is not fit to calibrate anything."""


def _read_json(path: Path):
    if not path.is_file():
        raise PromotionRefused(f"no {path.name} in {path.parent}")
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError as exc:
        raise PromotionRefused(
            f"{path} is outside this repository. A calibration record must "
            f"anchor to in-tree evidence, or its provenance cannot be checked "
            f"in a fresh clone.") from exc


def read_verdict(analysis_dir: Path) -> dict:
    """The verdict alone. Read first, so the promotion is refused on the ground
    that matters (the ladder rejected this run) before any path bookkeeping."""
    return _read_json(Path(analysis_dir) / "verdict.json")


def read_analysis(analysis_dir: Path, scenario: str | None,
                  verdict: dict | None = None) -> dict:
    """Pull the measured values, the run config and the verdict out of one
    completed analysis directory."""
    analysis_dir = Path(analysis_dir)
    verdict = verdict if verdict is not None else read_verdict(analysis_dir)
    metrics_doc = _read_json(analysis_dir / "metrics.json")

    prefix = f"{scenario}__" if scenario else ""
    measured: dict[str, float] = {}
    for m in metrics_doc["metrics"]:
        if m.get("status") != "OK" or m.get("value") is None:
            continue
        mid = str(m["id"])
        if prefix and mid.startswith(prefix):
            mid = mid[len(prefix):]
        elif prefix:
            continue
        if mid in _METRIC_MAP:
            measured[_METRIC_MAP[mid]] = float(m["value"])

    missing = [k for k in _REQUIRED if k not in measured]
    if missing:
        raise PromotionRefused(
            f"{analysis_dir} has no OK metric for {missing} "
            f"{'(scenario ' + scenario + ')' if scenario else ''}-- "
            f"refit_laws.py cannot derive the thrust or collection constants "
            f"without them")

    used = analysis_dir / "acceptance_used.yaml"
    return {
        "verdict": verdict,
        "measured": measured,
        "metrics_path": _repo_relative(analysis_dir / "metrics.json"),
        "metrics_sha256": sha256_of(analysis_dir / "metrics.json"),
        "policy_id": verdict.get("policy_id"),
        "policy_sha256": sha256_of(used) if used.is_file() else None,
        "analysis_id": metrics_doc.get("analysis_id"),
    }


def read_run_config(analysis_dir: Path, run_dir: Path | None) -> tuple[dict, str]:
    """The frozen physics config of the run this analysis read.

    Prefer an explicit ``--run``; otherwise look for the sibling ``outputs/``
    entry named in the analysis manifest. Committed reference bundles keep a
    copy of the acceptance policy but not always the run, so a reference bundle
    may need ``--run`` pointed at the reference directory itself.
    """
    if run_dir is not None:
        cfg_path = Path(run_dir) / "config_used.yaml"
    else:
        cfg_path = Path(analysis_dir) / "config_used.yaml"
        if not cfg_path.is_file():
            manifest = analysis_dir / "run_manifests.json"
            if manifest.is_file():
                doc = json.loads(manifest.read_text(encoding="utf-8"))
                entries = doc if isinstance(doc, list) else doc.get("runs", [])
                for entry in entries:
                    rid = entry.get("run_id")
                    if not rid:
                        continue
                    guess = analysis_dir.parents[1] / "outputs" / rid / "config_used.yaml"
                    if guess.is_file():
                        cfg_path = guess
                        break
    if not cfg_path.is_file():
        raise PromotionRefused(
            f"cannot find the frozen config_used.yaml for {analysis_dir}; "
            f"pass --run <run-dir> explicitly")
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8")), _repo_relative(cfg_path)


def build_record(*, name: str, analysis_dir: Path, info: dict, config: dict,
                 config_path: str, forced_reason: str | None,
                 now: _dt.datetime) -> dict:
    plasma = config["plasma"]
    geo = config["geometry"]
    rec = {
        "run": name,
        "status": "measured",
        "stage_id": config.get("stage_id"),
        "scenario": config.get("scenario"),
        "promoted_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": {
            "analysis_dir": _repo_relative(analysis_dir),
            "analysis_id": info["analysis_id"],
            "metrics_path": info["metrics_path"],
            "metrics_sha256": info["metrics_sha256"],
            "config_path": config_path,
            "policy_id": info["policy_id"],
            "policy_sha256": info["policy_sha256"],
            "verdict_status": info["verdict"].get("status"),
        },
        "drive": {
            "voltage_V": abs(float(config["electrical"]["cathode_offset"])),
            "i_beam_A": float(config["beam"]["i_beam"]),
        },
        "plasma": {
            "n0_m3": float(plasma["n0"]),
            "Te_K": float(plasma["Te_K"]),
            "Ti_K": float(plasma["Ti_K"]),
            "ion_mass_me": float(plasma["ion_mass_me"]),
        },
        "geometry": {
            "r_probe_m": float(geo["r_probe"]),
            "z_bot_m": float(geo["z_bot"]),
            "z_top_m": float(geo["z_top"]),
            "emit_radius_m": float(geo["emit_radius"]),
        },
        "measured": {k: float(v) for k, v in sorted(info["measured"].items())},
    }
    if forced_reason is not None:
        rec["forced"] = {
            "reason": forced_reason,
            "refused_verdict": info["verdict"].get("status"),
            "warning": ("This record was promoted over a non-PASS verdict. Any "
                        "constant fitted from it inherits that caveat."),
        }
    return rec


HEADER = """\
# Promoted PIC measurement -- GENERATED by design_sims/promote.py.
#
# Do not hand-edit: refit_laws.py reads these records to fit laws.yaml, and the
# ladder's cross-stage check re-derives the same constants from the same
# metrics.json.  A hand-tuned number here would silently break that agreement.
#
# Every field under `source:` resolves against this repository, so the whole
# chain -- run config -> analysis -> verdict -> constant -- is checkable in a
# fresh clone.
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analysis", type=Path, required=True,
                    help="a completed analysis directory (has verdict.json + metrics.json)")
    ap.add_argument("--name", required=True, help="record name (file stem under runs/)")
    ap.add_argument("--run", type=Path, default=None,
                    help="the run directory whose config_used.yaml to freeze")
    ap.add_argument("--scenario", default=None,
                    help="for cohort analyses: strip this '<scenario>__' metric prefix")
    ap.add_argument("--force", action="store_true",
                    help="promote despite a non-PASS verdict (needs --reason)")
    ap.add_argument("--reason", default=None, help="why --force is justified")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    verdict = read_verdict(args.analysis)
    status = verdict.get("status")
    forced_reason = None
    if status != "PASS":
        if not args.force:
            raise PromotionRefused(
                f"REFUSED: {args.analysis} has verdict status {status!r}, not "
                f"'PASS'. A number the ladder rejected must not calibrate the "
                f"model the ladder validates. Use --force --reason '...' only "
                f"if you can justify it; the record will say so.")
        if not args.reason:
            raise PromotionRefused("--force requires --reason")
        forced_reason = args.reason
    elif args.force:
        print("[note] --force is unnecessary: the verdict is PASS", file=sys.stderr)

    info = read_analysis(args.analysis, args.scenario, verdict=verdict)
    config, config_path = read_run_config(args.analysis, args.run)
    record = build_record(
        name=args.name, analysis_dir=args.analysis, info=info, config=config,
        config_path=config_path, forced_reason=forced_reason,
        now=_dt.datetime.now(_dt.timezone.utc))

    text = HEADER + yaml.safe_dump(record, sort_keys=False, default_flow_style=False)
    out = RUNS_DIR / f"{args.name}.yaml"
    if args.dry_run:
        print(text)
        print(f"[dry-run] would write {out}", file=sys.stderr)
        return 0
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"promoted {status} analysis {info['analysis_id']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
