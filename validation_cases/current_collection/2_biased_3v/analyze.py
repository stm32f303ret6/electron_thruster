#!/usr/bin/env python3
"""Analysis for a current_collection stage (sphere at fixed bias).

Reads one COMPLETE run's frozen evidence, computes the full set of collection
metrics (thermal/OML currents, species ratio, far-field density,
quasineutrality, sheath containment), and evaluates whichever subset this
stage's acceptance.yaml gates.  Immutable analysis output; strict JSON; exit 0
all required gates pass / 1 a gate fails / 2 analysis error.

    python analyze.py --run outputs/<run-id> --policy acceptance.yaml
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parents[1]))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc  # noqa: E402
from helpers import ELECTRONS, IONS, Config, load_config  # noqa: E402

DEFAULT_POLICY = CASE_DIR / "acceptance.yaml"
RESULTS_ROOT = CASE_DIR / "results"


# ======================================================================
# raw-evidence readers (openPMD)
# ======================================================================

def field_rz(ts, field, iteration):
    F, info = ts.get_field(field=field, iteration=iteration, m="all", theta=0.0)
    r, z = np.asarray(info.r), np.asarray(info.z)
    raxis = next(k for k, v in dict(info.axes).items() if v == "r")
    if raxis == 1:
        F = F.T
    pos = r >= 0
    return F[pos], r[pos], z


def read_eb_scraped(cfg: Config, diags: str):
    """Weighted EB hits per species: dict name -> (it, w, ke_eV) arrays."""
    import openpmd_api as io

    out = {}
    sub = os.path.join(diags, "scrape", "particles_at_eb")
    if not glob.glob(os.path.join(sub, "*.h5")):
        return out
    series = io.Series(os.path.join(sub, "openpmd_%T.h5"), io.Access.read_only)
    masses = {ELECTRONS: scc.m_e, IONS: cfg.m_ion}
    cols = {n: {"it": [], "w": [], "ke": []} for n in masses}
    for it in series.iterations:
        parts = series.iterations[it].particles
        for name, mass in masses.items():
            if name not in parts:
                continue
            p = parts[name]
            wh = p["weighting"][io.Mesh_Record_Component.SCALAR]
            dw = wh.load_chunk()
            handles = {c: p["momentum"][c] for c in ("x", "y", "z")}
            data = {c: h.load_chunk() for c, h in handles.items()}
            series.flush()
            w = np.asarray(dw) * wh.unit_SI
            if w.size == 0:
                continue
            p2 = sum((np.asarray(data[c]) * handles[c].unit_SI) ** 2
                     for c in ("x", "y", "z"))
            gamma = np.sqrt(1.0 + p2 / (mass * scc.c) ** 2)
            ke = (gamma - 1.0) * mass * scc.c**2 / scc.e
            cols[name]["it"].append(np.full(w.size, it))
            cols[name]["w"].append(w)
            cols[name]["ke"].append(ke)
    series.close()
    for name, c in cols.items():
        out[name] = tuple(
            np.concatenate(v) if v else np.array([]) for v in
            (c["it"], c["w"], c["ke"]))
    return out


def current_history(cfg: Config, scraped):
    """(dump_steps, {species: I[A]}).  A dump holds the weight collected since
    the previous dump; steps come from the union of both species so zero-
    collection dumps stay as zeros."""
    steps = np.unique(np.concatenate(
        [scraped[n][0] for n in scraped if scraped[n][0].size]
    )) if scraped else np.array([])
    steps = steps[steps > 0]
    hist = {}
    for name, (it, w, _ke) in scraped.items():
        hist[name] = np.array([
            w[it == k].sum() * scc.e / (cfg.scrape_period * cfg.time_step)
            for k in steps])
    return steps, hist


def steady_stats(cfg: Config, I, n_blocks: int = 5):
    """Mean and block-std uncertainty of I over the last steady_window_frac."""
    if len(I) == 0:
        return float("nan"), float("nan"), 0, None
    i0 = int((1.0 - cfg.steady_window_frac) * len(I))
    win = I[i0:]
    blocks = [b.mean() for b in np.array_split(win, n_blocks) if b.size]
    err = float(np.std(blocks, ddof=1) / math.sqrt(len(blocks))) if len(blocks) > 1 else float("nan")
    return float(win.mean()), err, len(win), i0


def far_field_densities(ts, cfg: Config, iteration):
    """Volume-weighted n_e, n_i over the far shell 0.65..0.85 of the domain."""
    rho_e, r, z = field_rz(ts, "rho_electrons", iteration)
    rho_i, _, _ = field_rz(ts, "rho_ions", iteration)
    R, Z = np.meshgrid(r, z, indexing="ij")
    s = np.hypot(R, Z)
    smax = min(cfg.r_max, cfg.z_half)
    mask = (s > 0.65 * smax) & (s < 0.85 * smax)
    wgt = np.where(mask, R, 0.0)  # RZ cell volume ~ r
    n_e = float((np.abs(rho_e) / scc.e * wgt).sum() / wgt.sum())
    n_i = float((np.abs(rho_i) / scc.e * wgt).sum() / wgt.sum())
    return n_e, n_i


def edge_phi(ts, cfg: Config, iteration, inset: int = 3):
    """Max |phi| a few cells inside the three open boundaries (containment)."""
    phi, r, z = field_rz(ts, "phi", iteration)
    return float(max(np.abs(phi[-1 - inset, :]).max(),
                     np.abs(phi[:, inset]).max(),
                     np.abs(phi[:, -1 - inset]).max()))


def sheath_profile(ts, cfg: Config, iteration):
    phi, r, z = field_rz(ts, "phi", iteration)
    iz = int(np.argmin(np.abs(z)))
    return r, phi[:, iz]


def sheath_radius(r, phi, threshold):
    """Outermost radius where |phi| >= threshold (linear interpolation)."""
    a = np.abs(phi)
    above = np.where(a >= threshold)[0]
    if above.size == 0:
        return float("nan")
    i = above[-1]
    if i + 1 >= len(r):
        return float(r[i])
    f = (a[i] - threshold) / max(a[i] - a[i + 1], 1e-30)
    return float(r[i] + f * (r[i + 1] - r[i]))


# ======================================================================
# metrics
# ======================================================================

def compute_metrics(cfg: Config, evidence: lc.LoadedRun):
    from openpmd_viewer import OpenPMDTimeSeries

    diags = str(evidence.diags_dir)
    metrics: dict[str, lc.Metric] = {}
    extra: dict = {}

    scraped = read_eb_scraped(cfg, diags)
    steps, hist = current_history(cfg, scraped)
    I_e = hist.get(ELECTRONS, np.array([]))
    I_i = hist.get(IONS, np.array([]))
    Ie, Ie_err, ne_n, i0 = steady_stats(cfg, I_e)
    Ii, Ii_err, ni_n, _ = steady_stats(cfg, I_i)
    window = ({"start_iteration": int(steps[i0]),
               "end_iteration": int(steps[-1])}
              if (len(steps) and i0 is not None) else None)

    metrics["electron_current_A"] = lc.Metric.measure(
        "electron_current_A", Ie, "A", uncertainty=Ie_err, sample_count=ne_n,
        window=window, source="scrape/particles_at_eb electrons")
    metrics["ion_current_A"] = lc.Metric.measure(
        "ion_current_A", Ii, "A", uncertainty=Ii_err, sample_count=ni_n,
        window=window, source="scrape/particles_at_eb ions")
    metrics["electron_current_over_th"] = lc.Metric.measure(
        "electron_current_over_th", Ie / cfg.I_th_e, "-", window=window,
        source="I_e / I_th_e (exact thermal-flux law)")
    metrics["electron_current_over_oml"] = lc.Metric.measure(
        "electron_current_over_oml", Ie / cfg.I_oml_e, "-", window=window,
        source="I_e / OML ceiling")
    metrics["ion_current_over_th"] = lc.Metric.measure(
        "ion_current_over_th", Ii / cfg.I_th_i, "-", window=window,
        source="I_i / I_th_i")
    ratio = (Ie / Ii) if (np.isfinite(Ii) and Ii != 0) else float("nan")
    metrics["species_ratio_over_theory"] = lc.Metric.measure(
        "species_ratio_over_theory", ratio / cfg.species_ratio_theory, "-",
        source=f"(I_e/I_i)/sqrt((mi/me)(Te/Ti)); theory={cfg.species_ratio_theory:.3f}")

    # ----- fields: densities, containment, sheath -----
    ts = OpenPMDTimeSeries(os.path.join(diags, "fields"), check_all_files=False)
    its = ts.iterations
    last = its[-1]
    n_e_far, n_i_far = far_field_densities(ts, cfg, last)
    phi_edge = edge_phi(ts, cfg, last)
    rp, pp = sheath_profile(ts, cfg, last)
    r_sheath = sheath_radius(rp, pp, cfg.kTe_eV)

    metrics["far_density_e_over_n0"] = lc.Metric.measure(
        "far_density_e_over_n0", n_e_far / cfg.n0, "-",
        source="volume-weighted n_e over the far shell / n0")
    metrics["quasineutrality"] = lc.Metric.measure(
        "quasineutrality", abs(n_e_far - n_i_far) / cfg.n0, "-",
        source="far-shell |n_e - n_i| / n0")
    metrics["edge_phi_max_V"] = lc.Metric.measure(
        "edge_phi_max_V", phi_edge, "V",
        source="max |phi| a few cells inside the open boundaries")
    metrics["sheath_radius_mm"] = lc.Metric.measure(
        "sheath_radius_mm", (r_sheath * 1e3 if np.isfinite(r_sheath) else float("nan")),
        "mm", source="outermost r where |phi| = kTe/e at the midplane")

    extra.update(steps=steps, I_e=I_e, I_i=I_i, Ie=Ie, Ii=Ii, ts=ts, its=its,
                 n_e_far=n_e_far, n_i_far=n_i_far, phi_edge=phi_edge,
                 r_sheath=r_sheath)
    return metrics, extra


# ======================================================================
# figures + CSVs
# ======================================================================

def write_outputs(analysis, cfg, metrics, extra):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figs = analysis.figures_dir
    steps, I_e, I_i = extra["steps"], extra["I_e"], extra["I_i"]

    if len(steps):
        t_us = steps * cfg.time_step * 1e6
        with open(analysis.dir / "current.csv", "w") as fh:
            fh.write("t_us,I_e_A,I_i_A\n")
            for k in range(len(steps)):
                ie = I_e[k] if k < len(I_e) else 0.0
                ii = I_i[k] if k < len(I_i) else 0.0
                fh.write(f"{t_us[k]:.4f},{ie:.6e},{ii:.6e}\n")
        fig, (axe, axi) = plt.subplots(2, 1, figsize=(8.4, 7.2), sharex=True)
        axe.plot(t_us, I_e * 1e6, color="tab:blue", lw=1.2, label="collected I_e")
        axe.axhline(cfg.I_th_e * 1e6, color="gray", ls="--",
                    label=f"I_th = {cfg.I_th_e*1e6:.4f} uA")
        if cfg.bias > 0:
            axe.axhline(cfg.I_oml_e * 1e6, color="tab:red", ls="--",
                        label=f"I_OML = {cfg.I_oml_e*1e6:.3f} uA (ceiling)")
        axe.set_ylabel("electron current [uA]"); axe.legend(fontsize=8)
        axe.grid(alpha=0.3)
        axi.plot(t_us, I_i * 1e9, color="tab:orange", lw=1.2, label="collected I_i")
        axi.axhline(cfg.I_th_i * 1e9, color="gray", ls="--",
                    label=f"I_th_i = {cfg.I_th_i*1e9:.3f} nA")
        axi.set_ylabel("ion current [nA]"); axi.set_xlabel("time [us]")
        axi.legend(fontsize=8); axi.grid(alpha=0.3)
        fig.suptitle(f"collected current  [{cfg.stage_id}]  sphere "
                     f"{cfg.probe_radius*1e3:.2f} mm at {cfg.bias:+.1f} V")
        fig.tight_layout(); fig.savefig(figs / "current.png", dpi=140)
        plt.close(fig)

    # fields: phi + n_e mirrored
    ts, last = extra["ts"], extra["its"][-1]
    phi, r, z = field_rz(ts, "phi", last)
    rho_e, _, _ = field_rz(ts, "rho_electrons", last)
    ne = np.abs(rho_e) / scc.e
    rr = np.concatenate([-r[::-1], r]) * 1e3
    PHI = np.vstack([phi[::-1], phi]); NE = np.vstack([ne[::-1], ne])
    fig, axs = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    vlim = max(abs(PHI.min()), abs(PHI.max()), 0.05)
    p0 = axs[0].pcolormesh(z * 1e3, rr, PHI, cmap="RdBu_r", shading="auto",
                           vmin=-vlim, vmax=vlim)
    fig.colorbar(p0, ax=axs[0], label="phi [V]")
    axs[0].set_title(f"potential phi (step {last})")
    p1 = axs[1].pcolormesh(z * 1e3, rr, NE, cmap="inferno", shading="auto",
                           vmin=0, vmax=max(1.5 * cfg.n0, NE.max() * 0.5))
    fig.colorbar(p1, ax=axs[1], label="n_e [m^-3]")
    axs[1].set_title("electron density n_e")
    for ax in axs:
        ax.add_patch(plt.Circle((0.0, 0.0), cfg.probe_radius * 1e3,
                                color="0.4", zorder=6))
        ax.set_xlabel("z [mm]")
    axs[0].set_ylabel("r [mm] (mirrored)")
    fig.suptitle(f"{cfg.stage_id}: sphere {cfg.probe_radius*1e3:.2f} mm at "
                 f"{cfg.bias:+.1f} V")
    fig.tight_layout(); fig.savefig(figs / "fields.png", dpi=140)
    plt.close(fig)

    # sheath: midplane |phi|(r) at several times + edge-radius history
    its = extra["its"]
    thr = cfg.kTe_eV
    picks = its[:: max(1, len(its) // 6)]
    fig, (axp, axs_) = plt.subplots(2, 1, figsize=(8.4, 7.2))
    rs_hist = []
    for it in its:
        rp, pp = sheath_profile(ts, cfg, it)
        rs_hist.append(sheath_radius(rp, pp, thr))
        if it in picks or it == last:
            axp.plot(rp * 1e3, np.abs(pp), lw=1.2,
                     label=f"t={it*cfg.time_step*1e6:.2f} us")
    axp.axhline(thr, color="gray", ls=":", label=f"kTe/e = {thr*1e3:.0f} mV")
    axp.axvline(cfg.probe_radius * 1e3, color="0.4", lw=2, alpha=0.7)
    axp.set_yscale("log"); axp.set_xlabel("r [mm] (midplane)")
    axp.set_ylabel("|phi| [V]"); axp.set_title(f"midplane potential  [{cfg.stage_id}]")
    axp.legend(fontsize=7); axp.grid(alpha=0.3)
    t_all = np.array(its) * cfg.time_step * 1e6
    axs_.plot(t_all, np.array(rs_hist) * 1e3, "-o", ms=3, color="tab:purple")
    axs_.axhline(cfg.debye * 1e3, color="gray", ls="--", label="lambda_De")
    axs_.axhline(cfg.probe_radius * 1e3, color="0.4", lw=2, alpha=0.7,
                 label="probe radius")
    axs_.set_xlabel("time [us]"); axs_.set_ylabel("sheath radius [mm]")
    axs_.set_title("sheath growth"); axs_.legend(fontsize=8); axs_.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(figs / "sheath.png", dpi=140)
    plt.close(fig)


# ======================================================================
# driver
# ======================================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="current_collection analysis")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", type=Path, help="a COMPLETE run directory")
    g.add_argument("--runs", type=Path, nargs="+",
                   help="rejected: current_collection stages are single-run")
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
            raise lc.ContractError("current_collection stages are single-run")
        evidence = lc.load_complete_runs(run_dirs)[0]
        cfg = load_config(evidence.dir / "config_used.yaml")
        policy = lc.load_policy(args.policy)
        if policy.stage_id != cfg.stage_id or evidence.stage_id != cfg.stage_id:
            raise lc.ContractError(
                f"stage mismatch: policy={policy.stage_id}, "
                f"run={evidence.stage_id}, config={cfg.stage_id}")
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
