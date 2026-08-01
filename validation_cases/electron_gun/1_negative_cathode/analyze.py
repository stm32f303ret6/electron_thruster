#!/usr/bin/env python3
"""Analysis for emitter.negative_cathode.

Reads a COMPLETE run's frozen evidence (never the live config.yaml), computes
every gated metric, evaluates the acceptance policy through the shared contract,
and writes an immutable analysis directory (metrics.json, verdict.json, CSVs,
figures).  Exit codes: 0 all required gates pass; 1 valid evidence but a gate
fails; 2 analysis error / missing evidence / invalid policy.

    python analyze.py --run outputs/<run-id> --policy acceptance.yaml
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path

import numpy as np
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parents[1]))  # validation_cases/ (ladder_contract)
sys.path.insert(0, str(CASE_DIR))             # this stage's helpers.py

import ladder_contract as lc  # noqa: E402
from helpers import STAGE_ID, SPECIES_NAME, load_config  # noqa: E402

DEFAULT_POLICY = CASE_DIR / "acceptance.yaml"
RESULTS_ROOT = CASE_DIR / "results"

m_e, e, c = scc.m_e, scc.e, scc.c
KE_BIN_EV = 0.5  # arrival-energy histogram bin width [eV]

# The three absorbing boundaries, main collector first.
_TARGETS = [
    ("collector", "zhi"),
    ("cathode", "zlo"),
    ("radial", "xhi"),
]


# ======================================================================
# raw-evidence readers (openPMD)
# ======================================================================

def ke_eV(px, py, pz):
    """Relativistic kinetic energy [eV] from momentum [kg m/s]."""
    p2 = px * px + py * py + pz * pz
    gamma = np.sqrt(1.0 + p2 / (m_e * c) ** 2)
    return (gamma - 1.0) * m_e * c * c / e


def field_rz(ts, field, iteration):
    """Reconstruct the (r>=0, z) half-plane, robust to axis order."""
    F, info = ts.get_field(field=field, iteration=iteration, m="all", theta=0.0)
    r, z = np.asarray(info.r), np.asarray(info.z)
    raxis = next(k for k, v in dict(info.axes).items() if v == "r")
    if raxis == 1:
        F = F.T  # -> [r, z]
    pos = r >= 0
    return F[pos], r[pos], z


def read_scraped(diags: str) -> dict:
    """Per-particle arrays concatenated over all boundary subdirs:
    px/py/pz [kg m/s], w [weight], bnd [str], it [dump step]."""
    import openpmd_api as io

    cols = {k: [] for k in ("px", "py", "pz", "w", "bnd", "it")}
    for sub in sorted(glob.glob(os.path.join(diags, "scrape", "particles_at_*"))):
        if not glob.glob(os.path.join(sub, "*.h5")):
            continue
        bnd = os.path.basename(sub).replace("particles_at_", "")
        series = io.Series(os.path.join(sub, "openpmd_%T.h5"),
                           io.Access.read_only)
        for it in series.iterations:
            parts = series.iterations[it].particles
            if SPECIES_NAME not in parts:
                continue
            p = parts[SPECIES_NAME]

            def load(rec, comp):
                h = p[rec][comp]
                return h, h.load_chunk()

            (mxh, dmx) = load("momentum", "x")
            (myh, dmy) = load("momentum", "y")
            (mzh, dmz) = load("momentum", "z")
            wh = p["weighting"][io.Mesh_Record_Component.SCALAR]
            dw = wh.load_chunk()
            series.flush()
            n = np.asarray(dw).size
            if n == 0:
                continue
            cols["px"].append(np.asarray(dmx) * mxh.unit_SI)
            cols["py"].append(np.asarray(dmy) * myh.unit_SI)
            cols["pz"].append(np.asarray(dmz) * mzh.unit_SI)
            cols["w"].append(np.asarray(dw) * wh.unit_SI)
            cols["bnd"].append(np.array([bnd] * n))
            cols["it"].append(np.full(n, it))
        series.close()
    return {k: (np.concatenate(v) if v else np.array([])) for k, v in cols.items()}


def in_domain_weight(diags: str):
    """Beam weight still inside the domain from the last ParticleNumber row.
    Single-species columns: [0]step [1]time [2]total_macro [3]e_macro
    [4]total_weight [5]e_weight."""
    f = os.path.join(diags, "reducedfiles", "beam_n.txt")
    if not os.path.exists(f):
        return None
    row = np.atleast_2d(np.loadtxt(f))[-1]
    return float(row[5])


# ======================================================================
# measurements -> metrics
# ======================================================================

def current_history(s, cfg):
    """(dump_steps, {key: I[A]}) over the union of dump steps holding hits."""
    if s["w"].size == 0:
        return np.array([]), {k: np.array([]) for k, _ in _TARGETS}
    steps = np.unique(s["it"])
    steps = steps[steps > 0]
    hist = {}
    for key, bnd in _TARGETS:
        m = s["bnd"] == bnd
        hist[key] = np.array([
            s["w"][m & (s["it"] == k)].sum() * e / (cfg.scrape_period * cfg.time_step)
            for k in steps])
    return steps, hist


def steady_mean(I):
    """Mean over the last 40% of dumps (the baseline steady window)."""
    if len(I) == 0:
        return float("nan"), (None, None)
    i0 = int(0.6 * len(I))
    return float(np.mean(I[i0:])), i0


def compute_metrics(cfg, evidence: lc.LoadedRun):
    """Compute every gated metric plus the arrays needed for figures/CSVs."""
    from openpmd_viewer import OpenPMDTimeSeries

    diags = str(evidence.diags_dir)
    metrics: dict[str, lc.Metric] = {}
    extra: dict = {}

    # ----- fields: vacuum ramp, space-charge depression -----
    ts = OpenPMDTimeSeries(os.path.join(diags, "fields"), check_all_files=False)
    its = ts.iterations
    phi_vac, r, z = field_rz(ts, "phi", its[0])   # t=0, geometry only
    phi_end, _, _ = field_rz(ts, "phi", its[-1])  # t_end, with beam
    p0f, p0l = phi_vac[0], phi_end[0]             # r~0 column
    iz = int(np.argmin(np.abs(z)))
    vac_err = float(np.max(np.abs(p0f - cfg.laplace_ramp(z))))
    depression = float(p0f[iz] - p0l[iz])
    extra.update(z=z, phi_vac_axis=p0f, phi_end_axis=p0l, ts=ts,
                 iz=iz, phi_z0=float(p0l[iz]))

    metrics["vacuum_ramp_max_abs_error_V"] = lc.Metric.measure(
        "vacuum_ramp_max_abs_error_V", vac_err, "V",
        source="fields/phi[it0] vs Laplace ramp")
    metrics["space_charge_depression_V"] = lc.Metric.measure(
        "space_charge_depression_V", depression, "V",
        source="fields/phi[it0]-phi[itN] on axis at z~0")

    # ----- scraped weight/current/energy -----
    s = read_scraped(diags)
    steps, hist = current_history(s, cfg)
    Icoll = hist["collector"]
    coll_steady, i0 = steady_mean(Icoll)
    window = ({"start_iteration": int(steps[i0]),
               "end_iteration": int(steps[-1])} if len(steps) else None)

    total = float(s["w"].sum()) if s["w"].size else 0.0
    weights = {}
    for key, bnd in _TARGETS:
        m = s["bnd"] == bnd if s["w"].size else np.array([], dtype=bool)
        weights[key] = float(s["w"][m].sum()) if m.any() else 0.0

    n_emit = cfg.emitted_number()
    metrics["collector_current_over_emitted"] = lc.Metric.measure(
        "collector_current_over_emitted", coll_steady / cfg.beam_current, "-",
        window=window, sample_count=(len(Icoll) - i0 if i0 is not None else None),
        source="scrape/particles_at_zhi steady current / emitted")
    metrics["cathode_return_fraction"] = lc.Metric.measure(
        "cathode_return_fraction", weights["cathode"] / n_emit, "-",
        source="scrape/particles_at_zlo weight / emitted")
    metrics["radial_wall_fraction"] = lc.Metric.measure(
        "radial_wall_fraction", weights["radial"] / n_emit, "-",
        source="scrape/particles_at_xhi weight / emitted")

    # collector mean arrival KE and its residual from the analytic prediction
    coll_mask = s["bnd"] == "zhi" if s["w"].size else np.array([], dtype=bool)
    if coll_mask.any():
        ke = ke_eV(s["px"][coll_mask], s["py"][coll_mask], s["pz"][coll_mask])
        mean_ke = float(np.average(ke, weights=s["w"][coll_mask]))
    else:
        mean_ke = float("nan")
    ke_expect = cfg.expected_collector_ke_eV()
    metrics["collector_ke_error_eV"] = lc.Metric.measure(
        "collector_ke_error_eV", mean_ke - ke_expect, "eV",
        source=f"scrape/zhi weighted mean KE minus analytic {ke_expect:.3f} eV")

    # ----- particle-budget closure -----
    n_dom = in_domain_weight(diags)
    closure = (100.0 * ((total + n_dom) - n_emit) / n_emit
               if n_dom is not None else float("nan"))
    metrics["budget_closure_pct"] = lc.Metric.measure(
        "budget_closure_pct", closure, "%",
        source="reducedfiles/beam_n.txt last row + scraped weight")

    extra.update(steps=steps, hist=hist, s=s, weights=weights, total=total,
                 n_emit=n_emit, n_dom=n_dom, mean_ke=mean_ke,
                 ke_expect=ke_expect, coll_steady=coll_steady)
    return metrics, extra


# ======================================================================
# figures + CSVs (records, never the sole evidence of a measurement)
# ======================================================================

def write_outputs(analysis, cfg, metrics, extra):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figs = analysis.figures_dir
    steps, hist = extra["steps"], extra["hist"]
    dt = cfg.time_step

    # current CSV (complete dump grid) + figure
    if len(steps):
        t_ns = steps * dt * 1e9
        csv = analysis.dir / "current.csv"
        with open(csv, "w") as fh:
            fh.write("t_ns,collector_uA,cathode_uA,radial_uA\n")
            for k in range(len(steps)):
                fh.write(f"{t_ns[k]:.4f},{hist['collector'][k]*1e6:.6e},"
                         f"{hist['cathode'][k]*1e6:.6e},"
                         f"{hist['radial'][k]*1e6:.6e}\n")
        fig, ax = plt.subplots(figsize=(8.2, 4.8))
        ax.axhline(cfg.beam_current * 1e6, color="gray", ls="--",
                   label=f"emitted = {cfg.beam_current*1e6:.1f} uA")
        for key, color in (("collector", "tab:green"), ("cathode", "tab:red"),
                           ("radial", "tab:blue")):
            ax.plot(t_ns, hist[key] * 1e6, "-o", ms=3, color=color, label=key)
        ax.set_xlabel("time [ns]"); ax.set_ylabel("collected current [uA]")
        ax.set_title("collected current vs time  [negative_cathode]")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(figs / "current.png", dpi=140)
        plt.close(fig)

    # on-axis phi(z): vacuum ramp vs end-state
    z = extra["z"]
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.plot(z * 1e3, extra["phi_vac_axis"], "--", color="gray", lw=1.6,
            label="t=0, geometry only")
    ax.plot(z * 1e3, extra["phi_end_axis"], "-o", ms=3, color="tab:purple",
            label="t_end, with beam")
    ax.plot(z * 1e3, cfg.laplace_ramp(z), ":", color="k", lw=1.0,
            label="analytic Laplace ramp")
    ax.axhline(0.0, color="gray", lw=0.8); ax.grid(alpha=0.3)
    ax.set_xlabel("z [mm]"); ax.set_ylabel("on-axis phi [V]")
    ax.set_title(f"on-axis phi(z)  [negative_cathode]  phi(0)~{extra['phi_z0']:.2f} V")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(figs / "phi_axis.png", dpi=140)
    plt.close(fig)

    # fields: potential + electron density (mirrored)
    ts = extra["ts"]
    last = ts.iterations[-1]
    phi, r, zz = field_rz(ts, "phi", last)
    rho, _, _ = field_rz(ts, "rho", last)
    ne = np.abs(rho) / e
    rr = np.concatenate([-r[::-1], r]) * 1e3
    PHI = np.vstack([phi[::-1], phi]); NE = np.vstack([ne[::-1], ne])
    fig, axs = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    vlim = max(abs(PHI.min()), abs(PHI.max()), 1.0)
    p0 = axs[0].pcolormesh(zz * 1e3, rr, PHI, cmap="RdBu_r", shading="auto",
                           vmin=-vlim, vmax=vlim)
    fig.colorbar(p0, ax=axs[0], label="phi [V]")
    axs[0].set_title(f"potential phi (step {last})")
    p1 = axs[1].pcolormesh(zz * 1e3, rr, NE, cmap="inferno", shading="auto",
                           vmin=0, vmax=(NE.max() if NE.max() > 0 else 1.0))
    fig.colorbar(p1, ax=axs[1], label="n_e [m^-3]")
    axs[1].set_title("electron density n_e")
    for ax in axs:
        ax.set_xlabel("z [mm]")
    axs[0].set_ylabel("r [mm] (mirrored)")
    fig.tight_layout(); fig.savefig(figs / "fields.png", dpi=140)
    plt.close(fig)


# ======================================================================
# driver
# ======================================================================

def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="negative_cathode analysis")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", type=Path, help="a COMPLETE run directory")
    g.add_argument("--runs", type=Path, nargs="+",
                   help="rejected: negative_cathode is single-run")
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    return ap.parse_args(argv)


def _print_verdict(verdict: lc.Verdict) -> None:
    print("\n" + "=" * 72)
    print(f"VALIDATION GATES  [{verdict.stage_id}]  policy {verdict.policy_id}")
    print("=" * 72)
    for g in verdict.gates:
        print(f"[{g.status:4s}] {g.id}\n       {g.detail}")
    print("=" * 72)
    print(f"VERDICT: {verdict.status}  (exit {verdict.exit_code}) -- {verdict.detail}")
    print("=" * 72)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        run_dirs = [args.run] if args.run else args.runs
        if len(run_dirs) != 1:
            raise lc.ContractError("negative_cathode is a single-run stage")
        evidence = lc.load_complete_runs(run_dirs)[0]
        cfg = load_config(evidence.dir / "config_used.yaml")
        policy = lc.load_policy(args.policy)
        if policy.stage_id != STAGE_ID or evidence.stage_id != STAGE_ID:
            raise lc.ContractError(
                f"stage mismatch: policy={policy.stage_id}, "
                f"run={evidence.stage_id}, expected={STAGE_ID}")
    except lc.ContractError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return lc.EXIT_ERROR

    analysis = lc.begin_analysis([evidence], policy, results_root=RESULTS_ROOT,
                                 analyzer_source=__file__)
    print(f"ANALYSIS_ID={analysis.analysis_id}", flush=True)
    try:
        metrics, extra = compute_metrics(cfg, evidence)
        verdict = lc.evaluate_gates(metrics, policy)
        lc.write_metrics(analysis, metrics)
        lc.write_verdict(analysis, verdict)
        write_outputs(analysis, cfg, metrics, extra)
        lc.complete_analysis(analysis, verdict)
        _print_verdict(verdict)
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
