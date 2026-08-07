#!/usr/bin/env python3
"""Cohort analysis for emitter.voltage_bracket (the voltage-axis cohort).

Takes one COMPLETE run per scenario, verifies they share this stage and source
study (rejecting mixed configuration generations), computes each scenario's
transmission/energy/budget metrics, then evaluates the cross-scenario
demonstration gates.  The analysis manifest records the member run IDs and their
manifest hashes -- that IS the cohort record; there is no separate cohort dir.

    python analyze.py --runs outputs/<A-run> outputs/<B-run> outputs/<C-run> \\
        --policy acceptance.yaml
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
sys.path.insert(0, str(CASE_DIR.parents[1]))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc  # noqa: E402
from helpers import STAGE_ID, SPECIES_NAME, load_config, scenario_names  # noqa: E402

DEFAULT_CONFIG = CASE_DIR / "config.yaml"
DEFAULT_POLICY = CASE_DIR / "acceptance.yaml"
RESULTS_ROOT = CASE_DIR / "results"

m_e, e, c = scc.m_e, scc.e, scc.c
KE_BIN_EV = 0.5

# The four absorbing surfaces, main collector first.
_TARGETS = [("collector", "zhi"), ("anode", "eb"),
            ("cathode", "zlo"), ("radial", "xhi")]


# ======================================================================
# raw-evidence readers
# ======================================================================

def ke_eV(px, py, pz):
    p2 = px * px + py * py + pz * pz
    gamma = np.sqrt(1.0 + p2 / (m_e * c) ** 2)
    return (gamma - 1.0) * m_e * c * c / e


def field_rz(ts, field, iteration):
    F, info = ts.get_field(field=field, iteration=iteration, m="all", theta=0.0)
    r, z = np.asarray(info.r), np.asarray(info.z)
    raxis = next(k for k, v in dict(info.axes).items() if v == "r")
    if raxis == 1:
        F = F.T
    pos = r >= 0
    return F[pos], r[pos], z


def read_scraped(diags: str) -> dict:
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
    f = os.path.join(diags, "reducedfiles", "beam_n.txt")
    if not os.path.exists(f):
        return None
    row = np.atleast_2d(np.loadtxt(f))[-1]
    return float(row[5])


# ======================================================================
# per-scenario measurements
# ======================================================================

def steady_currents(s, cfg):
    """(dump_steps, {key: I[A]}, {key: steady_A}) per boundary, over the
    complete configured scrape grid (plan section 10 rule 1), not just dumps
    that happened to hold a hit -- a genuinely empty interval is a recorded
    zero rather than a missing bin."""
    steps = np.arange(cfg.scrape_period, cfg.max_steps + 1, cfg.scrape_period)
    if s["w"].size == 0:
        z = np.zeros_like(steps, dtype=float)
        return steps, {k: z for k, _ in _TARGETS}, {k: 0.0 for k, _ in _TARGETS}
    hist, steady = {}, {}
    for key, bnd in _TARGETS:
        m = s["bnd"] == bnd
        I = np.array([
            s["w"][m & (s["it"] == k)].sum() * e / (cfg.scrape_period * cfg.time_step)
            for k in steps])
        hist[key] = I
        steady[key] = float(np.mean(I[int(0.6 * len(I)):])) if len(I) else float("nan")
    return steps, hist, steady


def scenario_measurements(cfg, evidence):
    """All measured quantities for one scenario run."""
    from openpmd_viewer import OpenPMDTimeSeries

    diags = str(evidence.diags_dir)
    ts = OpenPMDTimeSeries(os.path.join(diags, "fields"), check_all_files=False)
    phi_end, r, z = field_rz(ts, "phi", ts.iterations[-1])
    phi_end_axis = phi_end[0]
    # Energy conservation from the emission plane, self-consistent end-state phi
    # interpolated to emit_z (the plane sits between cell centres).
    ke_expect = ((cfg.v_collector - float(np.interp(cfg.emit_z, z, phi_end_axis)))
                 + 2.0 * cfg.kt_launch_eV)

    s = read_scraped(diags)
    steps, hist, steady = steady_currents(s, cfg)
    frac = {k: (steady[k] / cfg.beam_current if np.isfinite(steady[k]) else float("nan"))
            for k, _ in _TARGETS}

    coll_mask = s["bnd"] == "zhi" if s["w"].size else np.array([], dtype=bool)
    if coll_mask.any():
        ke = ke_eV(s["px"][coll_mask], s["py"][coll_mask], s["pz"][coll_mask])
        mean_ke = float(np.average(ke, weights=s["w"][coll_mask]))
    else:
        mean_ke = float("nan")

    total = float(s["w"].sum()) if s["w"].size else 0.0
    weights = {}
    for key, bnd in _TARGETS:
        m = s["bnd"] == bnd if s["w"].size else np.array([], dtype=bool)
        weights[key] = float(s["w"][m].sum()) if m.any() else 0.0
    n_emit = cfg.emitted_number()
    n_dom = in_domain_weight(diags)
    closure = (100.0 * ((total + n_dom) - n_emit) / n_emit
               if n_dom is not None else float("nan"))

    return {
        "frac": frac, "mean_ke": mean_ke, "ke_expect": ke_expect,
        "ke_err": mean_ke - ke_expect, "closure": closure,
        "steps": steps, "hist": hist, "ts": ts, "z": z,
        "phi_end_axis": phi_end_axis, "weights": weights, "total": total,
    }


# ======================================================================
# figures + CSVs
# ======================================================================

def write_outputs(analysis, order, cfgs, meas):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    figs = analysis.figures_dir
    for name in order:
        cfg, mz = cfgs[name], meas[name]
        steps, hist = mz["steps"], mz["hist"]
        if len(steps):
            t_ns = steps * cfg.time_step * 1e9
            with open(analysis.dir / f"current_{name}.csv", "w") as fh:
                fh.write("t_ns,collector_uA,anode_uA,cathode_uA,radial_uA\n")
                for k in range(len(steps)):
                    fh.write(f"{t_ns[k]:.4f}," + ",".join(
                        f"{hist[key][k]*1e6:.6e}"
                        for key, _ in _TARGETS) + "\n")
            fig, ax = plt.subplots(figsize=(8.2, 4.8))
            ax.axhline(cfg.beam_current * 1e6, color="gray", ls="--",
                       label=f"emitted = {cfg.beam_current*1e6:.1f} uA")
            for (key, _), color in zip(_TARGETS, ["tab:green", "tab:orange",
                                                  "tab:red", "tab:blue"]):
                ax.plot(t_ns, hist[key] * 1e6, "-o", ms=3, color=color, label=key)
            ax.set_xlabel("time [ns]"); ax.set_ylabel("collected current [uA]")
            ax.set_title(f"collected current  [{name}]")
            ax.legend(fontsize=8); ax.grid(alpha=0.3)
            fig.tight_layout(); fig.savefig(figs / f"current_{name}.png", dpi=140)
            plt.close(fig)

        # fields with the anode plate drawn
        ts = mz["ts"]; last = ts.iterations[-1]
        phi, r, z = field_rz(ts, "phi", last)
        rho, _, _ = field_rz(ts, "rho", last)
        ne = np.abs(rho) / e
        rr = np.concatenate([-r[::-1], r]) * 1e3
        PHI = np.vstack([phi[::-1], phi]); NE = np.vstack([ne[::-1], ne])
        fig, axs = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
        vlim = max(abs(PHI.min()), abs(PHI.max()), 1.0)
        p0 = axs[0].pcolormesh(z * 1e3, rr, PHI, cmap="RdBu_r", shading="auto",
                               vmin=-vlim, vmax=vlim)
        fig.colorbar(p0, ax=axs[0], label="phi [V]")
        axs[0].set_title(f"potential phi (step {last})")
        p1 = axs[1].pcolormesh(z * 1e3, rr, NE, cmap="inferno", shading="auto",
                               vmin=0, vmax=(NE.max() if NE.max() > 0 else 1.0))
        fig.colorbar(p1, ax=axs[1], label="n_e [m^-3]")
        axs[1].set_title("electron density n_e")
        z0, tw = cfg.anode_z_front * 1e3, cfg.anode_thickness * 1e3
        rh, rm = cfg.hole_radius * 1e3, cfg.r_max * 1e3
        for ax in axs:
            ax.add_patch(Rectangle((z0, rh), tw, rm - rh, color="0.45", zorder=5))
            ax.add_patch(Rectangle((z0, -rm), tw, rm - rh, color="0.45", zorder=5))
            ax.set_xlabel("z [mm]")
        axs[0].set_ylabel("r [mm] (mirrored)")
        fig.suptitle(f"voltage_bracket [{name}]: {abs(cfg.v_cathode):.0f} V, "
                     f"{cfg.beam_current*1e6:.0f} uA, "
                     f"hole r<{cfg.hole_radius*1e3:.1f} mm")
        fig.tight_layout(); fig.savefig(figs / f"fields_{name}.png", dpi=140)
        plt.close(fig)

    # transmission summary bar chart
    keys = ["collector", "anode", "cathode", "radial"]
    colors = ["tab:green", "tab:orange", "tab:red", "tab:blue"]
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    x = np.arange(len(order)); wbar = 0.2
    for j, (k, col) in enumerate(zip(keys, colors)):
        vals = [100 * meas[n]["frac"][k] for n in order]
        bars = ax.bar(x + (j - 1.5) * wbar, vals, wbar, color=col, label=k)
        ax.bar_label(bars, fmt="%.1f%%", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{n}\n{abs(cfgs[n].v_cathode):.0f} V, "
                        f"{cfgs[n].beam_current*1e6:.0f} uA" for n in order],
                       fontsize=8)
    ax.set_ylabel("% of emitted current (steady)")
    ax.set_title("voltage_bracket: transmission along the voltage axis")
    ax.legend(fontsize=9); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(figs / "transmission.png", dpi=140)
    plt.close(fig)


# ======================================================================
# driver
# ======================================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="voltage-bracket gun cohort analysis")
    ap.add_argument("--runs", type=Path, nargs="+", required=True,
                    help="one COMPLETE run directory per scenario")
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                    help="source study (for the canonical scenario order)")
    return ap.parse_args(argv)


def build_metrics(order, cfgs, meas):
    """Per-scenario + cross-scenario metrics keyed for the acceptance policy."""
    metrics: dict[str, lc.Metric] = {}
    for name in order:
        mz = meas[name]
        metrics[f"{name}__collector_fraction"] = lc.Metric.measure(
            f"{name}__collector_fraction", mz["frac"]["collector"], "-",
            source="scrape/zhi steady current / emitted")
        metrics[f"{name}__anode_fraction"] = lc.Metric.measure(
            f"{name}__anode_fraction", mz["frac"]["anode"], "-",
            source="scrape/eb steady current / emitted")
        metrics[f"{name}__ke_error_eV"] = lc.Metric.measure(
            f"{name}__ke_error_eV", mz["ke_err"], "eV",
            source=f"collector mean KE minus analytic {mz['ke_expect']:.2f} eV")
        metrics[f"{name}__budget_closure_pct"] = lc.Metric.measure(
            f"{name}__budget_closure_pct", mz["closure"], "%",
            source="reducedfiles/beam_n.txt + scraped weight")
        metrics[f"{name}__cathode_fraction"] = lc.Metric.measure(
            f"{name}__cathode_fraction", mz["frac"]["cathode"], "-",
            source="scrape/zlo steady current / emitted (space-charge return)")
    A, B, C = order
    metrics["transmission_spread_A_to_B"] = lc.Metric.measure(
        "transmission_spread_A_to_B",
        abs(meas[A]["frac"]["collector"] - meas[B]["frac"]["collector"]), "-",
        source="|A collector fraction - B collector fraction| (both at the "
               "frontier perveance fraction; the bracket claims V-independence)")
    metrics["C_collector_drop_vs_A"] = lc.Metric.measure(
        "C_collector_drop_vs_A",
        meas[A]["frac"]["collector"] - meas[C]["frac"]["collector"], "-",
        source="A collector fraction minus C collector fraction (over-ceiling "
               "current limiting at the ucurve_left_arm command)")
    return metrics


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
        order = scenario_names(args.config)  # canonical A, B, C order
        if len(order) != 3:
            raise lc.ContractError(
                f"voltage_bracket expects exactly 3 scenarios, got {order}")
        cohort = lc.load_complete_runs(args.runs)
        lc.check_cohort(cohort, stage_id=STAGE_ID, require_scenarios=order)
        policy = lc.load_policy(args.policy)
        if policy.stage_id != STAGE_ID:
            raise lc.ContractError(
                f"policy stage {policy.stage_id} != {STAGE_ID}")
        by_scn = {r.scenario: r for r in cohort}
        cfgs = {name: load_config(by_scn[name].dir / "config_used.yaml")
                for name in order}
    except lc.ContractError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return lc.EXIT_ERROR

    analysis = lc.begin_analysis(cohort, policy, results_root=RESULTS_ROOT,
                                 analyzer_source=__file__)
    print(f"ANALYSIS_ID={analysis.analysis_id}", flush=True)
    try:
        meas = {name: scenario_measurements(cfgs[name], by_scn[name])
                for name in order}
        metrics = build_metrics(order, cfgs, meas)
        verdict = lc.evaluate_gates(metrics, policy)
        lc.write_metrics(analysis, metrics)
        lc.write_verdict(analysis, verdict)
        write_outputs(analysis, order, cfgs, meas)
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
