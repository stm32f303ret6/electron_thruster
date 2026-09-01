#!/usr/bin/env python3
"""Cohort analysis for characterization.transverse_b_numerics.

Reads each scenario's BeamRelevant trace (mean position/momentum of the one
test electron every step) and compares with the closed forms:

  gyro_*:  omega from the rotation of (py, pz); r_g from an algebraic circle
           fit to (y, z); energy conservation from gamma(t).
  exb_*:   the y-drift from a least-squares fit y(t) = y0 + v t + A cos(w t)
           + B sin(w t) at the known omega_c, against Ez/Bx.

    python analyze.py --runs outputs/<gyro_1x> outputs/<gyro_10x> outputs/<exb_10x>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent
_pic_root = CASE_DIR
while not (_pic_root / "ladder_contract.py").is_file():
    _pic_root = _pic_root.parent
sys.path.insert(0, str(_pic_root))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc  # noqa: E402
from helpers import STAGE_ID, Config, load_config, scenario_names  # noqa: E402

DEFAULT_POLICY = CASE_DIR / "acceptance.yaml"
DEFAULT_CONFIG = CASE_DIR / "config.yaml"
RESULTS_ROOT = CASE_DIR / "results"
E, ME, CC = scc.e, scc.m_e, scc.c


def load_trace(diags: Path):
    """BeamRelevant columns -> dict of arrays (t, x, y, z, px, py, pz, gamma)."""
    path = diags / "reducedfiles" / "beam_relevant.txt"
    if not path.exists():
        raise lc.ContractError(f"no {path} in the run evidence")
    with open(path, encoding="utf-8") as fh:
        header = fh.readline()
    cols = [c.split("]", 1)[1].split("(")[0] for c in header.lstrip("#").split()]
    data = np.atleast_2d(np.loadtxt(path))
    if data.shape[0] < 10:
        raise lc.ContractError(f"{path}: too few rows ({data.shape[0]})")
    out = {}
    for key, col in (("t", "time"), ("x", "x_mean"), ("y", "y_mean"), ("z", "z_mean"),
                     ("px", "px_mean"), ("py", "py_mean"), ("pz", "pz_mean"),
                     ("gamma", "gamma_mean")):
        out[key] = data[:, cols.index(col)]
    # keep only rows while the particle is in the box (charge column != 0)
    if "charge" in cols:
        alive = data[:, cols.index("charge")] != 0.0
        if alive.sum() >= 10:
            out = {k: v[alive] for k, v in out.items()}
    return out


def fit_circle(y, z):
    """Algebraic (Kasa) circle fit: returns radius."""
    A = np.column_stack([2 * y, 2 * z, np.ones_like(y)])
    b = y * y + z * z
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cy, cz, c = sol
    return float(np.sqrt(max(c + cy * cy + cz * cz, 0.0)))


def gyro_metrics(cfg: Config, tr) -> dict:
    theta = np.unwrap(np.arctan2(tr["py"], tr["pz"]))
    omega = abs(float(np.polyfit(tr["t"], theta, 1)[0]))
    r_fit = fit_circle(tr["y"], tr["z"])
    ke = (tr["gamma"] - 1.0) * ME * CC**2 / E
    ke_drift = float(np.max(np.abs(ke - ke[0])) / ke[0]) if ke[0] > 0 else float("nan")
    return {"omega_ratio": omega / cfg.omega_c, "rg_ratio": r_fit / cfg.r_gyro,
            "ke_drift": ke_drift, "arc_deg": float(np.degrees(theta[-1] - theta[0]))}


def exb_metrics(cfg: Config, tr) -> dict:
    t = tr["t"]
    w = cfg.omega_c
    A = np.column_stack([np.ones_like(t), t, np.cos(w * t), np.sin(w * t)])
    sol, *_ = np.linalg.lstsq(A, tr["y"], rcond=None)
    v_fit = float(sol[1])
    # z must not drift on average (E x B has no z component)
    solz, *_ = np.linalg.lstsq(A, tr["z"], rcond=None)
    return {"vd_ratio": v_fit / cfg.v_exb,
            "vz_over_vd": float(solz[1]) / cfg.v_exb,
            "gyroperiods": float((t[-1] - t[0]) / cfg.T_c)}


def build_metrics(per: dict[str, dict]) -> dict[str, lc.Metric]:
    metrics = {}
    for scn, m in per.items():
        for mid, value in m.items():
            key = f"{scn}__{mid}"
            metrics[key] = lc.Metric.measure(key, value, "-",
                                             source="BeamRelevant trace vs closed form")
    return metrics


def write_figures(analysis, cfgs, traces) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for scn, tr in traces.items():
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(tr["y"] * 1e3, tr["z"] * 1e3, lw=1.5)
        ax.set_xlabel("y [mm]"); ax.set_ylabel("z [mm]"); ax.set_aspect("equal")
        ax.set_title(f"{scn}: trajectory in the gyration plane"); ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(analysis.figures_dir / f"{scn}_orbit.png", dpi=130)
        plt.close(fig)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="transverse-B numerics analysis")
    ap.add_argument("--runs", type=Path, nargs="+", required=True)
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        order = scenario_names(args.config)
        cohort = lc.load_complete_runs(args.runs)
        lc.check_cohort(cohort, stage_id=STAGE_ID)
        unknown = [r.scenario for r in cohort if r.scenario not in order]
        if unknown:
            raise lc.ContractError(f"runs carry scenarios not in the study: {unknown}")
        cohort = sorted(cohort, key=lambda r: order.index(r.scenario))
        cfgs = {r.scenario: load_config(r.dir / "config_used.yaml") for r in cohort}
        policy = lc.load_policy(args.policy)
        if policy.stage_id != STAGE_ID:
            raise lc.ContractError(f"policy stage {policy.stage_id} != {STAGE_ID}")
    except lc.ContractError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return lc.EXIT_ERROR

    analysis = lc.begin_analysis(cohort, policy, results_root=RESULTS_ROOT,
                                 analyzer_source=__file__)
    print(f"ANALYSIS_ID={analysis.analysis_id}", flush=True)
    try:
        per, traces = {}, {}
        for r in cohort:
            cfg = cfgs[r.scenario]
            tr = load_trace(r.diags_dir)
            traces[r.scenario] = tr
            per[r.scenario] = (exb_metrics(cfg, tr) if cfg.ke_eV == 0.0
                               else gyro_metrics(cfg, tr))
        metrics = build_metrics(per)
        verdict = lc.evaluate_gates(metrics, policy)
        lc.write_metrics(analysis, metrics)
        lc.write_verdict(analysis, verdict)
        write_figures(analysis, cfgs, traces)
        lc.complete_analysis(analysis, verdict)
        print("\n" + "=" * 72)
        for scn, m in per.items():
            print(f"  [{scn}] " + "  ".join(f"{k}={v:.6g}" for k, v in m.items()))
        print("=" * 72)
        for g in verdict.gates:
            print(f"[{g.status:4s}] {g.id}\n       {g.detail}")
        print(f"VERDICT: {verdict.status}  (exit {verdict.exit_code}) -- {verdict.detail}")
        print(f"analysis -> {analysis.dir}")
        return verdict.exit_code
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001
        lc.fail_analysis(analysis, exc)
        print(f"[ERROR] analysis failed: {exc!r}", file=sys.stderr)
        return lc.EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
