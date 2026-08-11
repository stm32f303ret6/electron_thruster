#!/usr/bin/env python3
"""Analysis for collector.floating (passive sphere on the charge pump).

Reads one COMPLETE run's frozen evidence -- the floating_log.csv ledger, the
pump.json calibration record, and the openPMD field and scrape dumps --
computes the floating equilibrium metrics, and evaluates the acceptance
policy through the shared contract.  Exit 0 all required gates pass / 1 a
gate fails / 2 analysis error.

Reported but not gated (honesty lines): the Boltzmann-retardation
cross-check phi = kTe/e * ln(I_e/I_th_e), the currents against their 0-V
thermal values, and the late dphi/dt of the plateau.

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
_pic_root = CASE_DIR  # walk up to pic_sims/ (ladder_contract, shared plumbing)
while not (_pic_root / "ladder_contract.py").is_file():
    _pic_root = _pic_root.parent
sys.path.insert(0, str(_pic_root))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc  # noqa: E402
from helpers import ELECTRONS, IONS, Config, load_config  # noqa: E402

DEFAULT_POLICY = CASE_DIR / "acceptance.yaml"
RESULTS_ROOT = CASE_DIR / "results"

E = scc.e


# ======================================================================
# evidence readers
# ======================================================================

def load_ledger(diags: Path):
    """The per-window CSV ledger written by simulation.py's observer."""
    path = diags / "floating_log.csv"
    if not path.exists():
        raise lc.ContractError(f"no {path} in the run evidence")
    d = np.atleast_1d(np.genfromtxt(path, delimiter=",", names=True))
    if d.size == 0:
        raise lc.ContractError(f"{path} has no data rows")
    return d


def load_pump(diags: Path) -> dict:
    path = diags / "pump.json"
    if not path.exists():
        raise lc.ContractError(f"no {path} in the run evidence")
    return lc.read_json_strict(path)


def steady(d, col: str, tail_frac: float) -> float:
    """Mean of `col` over the last tail_frac of the record (the plateau)."""
    n = len(d["t"])
    i0 = max(0, int(n * (1.0 - tail_frac)))
    v = np.atleast_1d(d[col])[i0:]
    v = v[np.isfinite(v)]
    return float(v.mean()) if v.size else float("nan")


def late_slope(d, window_frac: float = 0.2) -> float:
    """Linear-fit slope of phi over the last window_frac of the record [V/s]."""
    t = np.atleast_1d(d["t"])
    phi = np.atleast_1d(d["phi_V"])
    m = t >= t[-1] - window_frac * (t[-1] - t[0])
    if m.sum() < 3:
        return float("nan")
    return float(np.polyfit(t[m], phi[m], 1)[0])


def csv_charge(d, col: str, dt: float) -> float:
    """Reconstruct the cumulative charge [C] behind a CSV current column
    (each row records acc/win over its window; I*win re-sums exactly)."""
    steps = np.atleast_1d(d["step"]).astype(float)
    I = np.atleast_1d(d[col])
    wins = np.diff(np.concatenate([[0.0], steps])) * dt
    return float(np.nansum(I * wins))


def field_rz(ts, field, iteration):
    F, info = ts.get_field(field=field, iteration=iteration, m="all", theta=0.0)
    r, z = np.asarray(info.r), np.asarray(info.z)
    raxis = next(k for k, v in dict(info.axes).items() if v == "r")
    if raxis == 1:
        F = F.T
    pos = r >= 0
    return F[pos], r[pos], z


def scraped_weight_totals(cfg: Config, diags: str) -> dict:
    """Total scraped real-particle weight per species at the EB over the whole
    run, from the openPMD scrape dumps."""
    import openpmd_api as io

    out: dict[str, float] = {}
    sub = os.path.join(diags, "scrape", "particles_at_eb")
    if not glob.glob(os.path.join(sub, "*.h5")):
        return out
    series = io.Series(os.path.join(sub, "openpmd_%T.h5"), io.Access.read_only)
    for it in series.iterations:
        parts = series.iterations[it].particles
        for name in (ELECTRONS, IONS):
            if name not in parts:
                continue
            wh = parts[name]["weighting"][io.Mesh_Record_Component.SCALAR]
            dw = wh.load_chunk()
            series.flush()
            w = np.asarray(dw) * wh.unit_SI
            if w.size:
                out[name] = out.get(name, 0.0) + float(w.sum())
    series.close()
    return out


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


# ======================================================================
# metrics
# ======================================================================

def compute_metrics(cfg: Config, evidence: lc.LoadedRun):
    from openpmd_viewer import OpenPMDTimeSeries

    diags = evidence.diags_dir
    d = load_ledger(diags)
    pump = load_pump(diags)
    tail = cfg.steady_window_frac
    n_rows = len(np.atleast_1d(d["t"]))
    i0 = max(0, int(n_rows * (1.0 - tail)))
    window = {"start_iteration": int(np.atleast_1d(d["step"])[i0]),
              "end_iteration": int(np.atleast_1d(d["step"])[-1])}

    phi_f = steady(d, "phi_V", tail)
    I_e = steady(d, "I_e_A", tail)
    I_i = steady(d, "I_i_A", tail)
    balance = abs(I_e - I_i) / I_i if (np.isfinite(I_i) and I_i != 0) \
        else float("nan")
    c_meas = float(pump["C_measured_F"])
    c_ratio = c_meas / cfg.analytic_capacitance

    metrics: dict[str, lc.Metric] = {}
    metrics["phi_float_V"] = lc.Metric.measure(
        "phi_float_V", phi_f, "V", window=window, sample_count=n_rows - i0,
        source=f"floating_log.csv phi_V tail mean; theory bracket "
               f"[{cfg.phi_float_thermal_ion:+.3f}, {cfg.phi_float_oml_ion:+.3f}] V")
    metrics["current_balance"] = lc.Metric.measure(
        "current_balance", balance, "-", window=window,
        source="|I_e - I_i| / I_i, tail means (equilibrium: net current -> 0)")
    metrics["capacitance_over_analytic"] = lc.Metric.measure(
        "capacitance_over_analytic", c_ratio, "-",
        source=f"Gauss-law C {c_meas*1e15:.2f} fF / 4*pi*eps0*a "
               f"{cfg.analytic_capacitance*1e15:.2f} fF")

    # ledger-vs-dump charge consistency (electron channel, the largest)
    totals = scraped_weight_totals(cfg, str(diags))
    q_pmd = E * totals.get(ELECTRONS, 0.0)
    q_csv = csv_charge(d, "I_e_A", cfg.time_step)
    consistency = (abs(q_csv - q_pmd) / q_pmd) if q_pmd > 0 else float("nan")
    metrics["scrape_charge_consistency"] = lc.Metric.measure(
        "scrape_charge_consistency", consistency, "-",
        source="electron EB charge: CSV ledger integral vs openPMD scrape total")

    # plasma health from the last field dump (collector.thermal's checks)
    ts = OpenPMDTimeSeries(os.path.join(str(diags), "fields"),
                           check_all_files=False)
    last = ts.iterations[-1]
    n_e_far, n_i_far = far_field_densities(ts, cfg, last)
    metrics["far_density_e_over_n0"] = lc.Metric.measure(
        "far_density_e_over_n0", n_e_far / cfg.n0, "-",
        source="volume-weighted n_e over the far shell / n0")
    metrics["quasineutrality"] = lc.Metric.measure(
        "quasineutrality", abs(n_e_far - n_i_far) / cfg.n0, "-",
        source="far-shell |n_e - n_i| / n0")
    metrics["edge_phi_max_V"] = lc.Metric.measure(
        "edge_phi_max_V", edge_phi(ts, cfg, last), "V",
        source="max |phi| a few cells inside the open boundaries")

    # ----- reported-only quantities (never gated) -----
    retard = (cfg.kTe_eV * math.log(I_e / cfg.I_th_e)
              if (np.isfinite(I_e) and I_e > 0) else float("nan"))
    metrics["phi_from_retardation_V"] = lc.Metric.measure(
        "phi_from_retardation_V", retard, "V",
        source="kTe/e * ln(I_e/I_th_e): Boltzmann cross-check of phi_f "
               "(REPORTED, not gated)")
    metrics["electron_current_over_th"] = lc.Metric.measure(
        "electron_current_over_th", I_e / cfg.I_th_e, "-", window=window,
        source="I_e / I_th_e (0 V thermal law; retarded here -- REPORTED)")
    metrics["ion_current_over_th"] = lc.Metric.measure(
        "ion_current_over_th", I_i / cfg.I_th_i, "-", window=window,
        source="I_i / I_th_i (attracted here, OML-enhanced -- REPORTED)")
    metrics["late_dphidt_V_per_us"] = lc.Metric.measure(
        "late_dphidt_V_per_us", late_slope(d) * 1e-6, "V/us",
        source="phi linear slope over the last 20% (REPORTED equilibrium check)")

    extra = dict(d=d, ts=ts, phi_f=phi_f, I_e=I_e, I_i=I_i, i0=i0)
    return metrics, extra


# ======================================================================
# figures + CSV
# ======================================================================

def write_outputs(analysis, cfg: Config, metrics, extra):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = extra["d"]
    figs = analysis.figures_dir
    t_us = np.atleast_1d(d["t"]) * 1e6

    # the ledger IS the current record; copy it into the analysis as current.csv
    with open(analysis.dir / "current.csv", "w") as fh:
        fh.write("t_us,phi_V,I_e_A,I_i_A\n")
        for k in range(len(t_us)):
            fh.write(f"{t_us[k]:.4f},{d['phi_V'][k]:.6e},"
                     f"{d['I_e_A'][k]:.6e},{d['I_i_A'][k]:.6e}\n")

    fig, (axp, axc) = plt.subplots(2, 1, figsize=(8.4, 7.2), sharex=True)
    axp.plot(t_us, d["phi_V"], color="tab:purple", lw=1.3, label="phi (pump)")
    axp.axhline(cfg.phi_float_thermal_ion, color="gray", ls="--",
                label=f"thermal-ion {cfg.phi_float_thermal_ion:+.3f} V")
    axp.axhline(cfg.phi_float_oml_ion, color="tab:red", ls="--",
                label=f"OML-ion {cfg.phi_float_oml_ion:+.3f} V")
    axp.axvspan(t_us[extra["i0"]], t_us[-1], color="tab:green", alpha=0.08,
                label="steady window")
    axp.set_ylabel("sphere potential [V]")
    axp.legend(fontsize=8)
    axp.grid(alpha=0.3)
    axc.plot(t_us, np.atleast_1d(d["I_e_A"]) * 1e9, color="tab:blue", lw=1.1,
             label="collected I_e")
    axc.plot(t_us, np.atleast_1d(d["I_i_A"]) * 1e9, color="tab:orange", lw=1.1,
             label="collected I_i")
    axc.axhline(cfg.I_th_i * 1e9, color="gray", ls="--",
                label=f"I_th_i = {cfg.I_th_i*1e9:.2f} nA")
    axc.set_ylabel("current [nA]")
    axc.set_xlabel("time [us]")
    axc.legend(fontsize=8)
    axc.grid(alpha=0.3)
    fig.suptitle(f"floating sphere  [{cfg.stage_id}]  a={cfg.probe_radius*1e3:.2f} mm"
                 f"  (charge pump, no beam)")
    fig.tight_layout()
    fig.savefig(figs / "floating.png", dpi=140)
    plt.close(fig)

    # fields: phi + n_e mirrored, last dump
    ts = extra["ts"]
    last = ts.iterations[-1]
    phi, r, z = field_rz(ts, "phi", last)
    rho_e, _, _ = field_rz(ts, "rho_electrons", last)
    ne = np.abs(rho_e) / scc.e
    rr = np.concatenate([-r[::-1], r]) * 1e3
    PHI = np.vstack([phi[::-1], phi])
    NE = np.vstack([ne[::-1], ne])
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
    fig.suptitle(f"{cfg.stage_id}: floating sphere a={cfg.probe_radius*1e3:.2f} mm")
    fig.tight_layout()
    fig.savefig(figs / "fields.png", dpi=140)
    plt.close(fig)


# ======================================================================
# driver
# ======================================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="collector.floating analysis")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", type=Path, help="a COMPLETE run directory")
    g.add_argument("--runs", type=Path, nargs="+",
                   help="rejected: collector.floating is single-run")
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
            raise lc.ContractError("collector.floating is single-run")
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
        print(f"\nphi_f = {extra['phi_f']:+.4f} V  "
              f"(thermal-ion {cfg.phi_float_thermal_ion:+.3f}, "
              f"OML-ion {cfg.phi_float_oml_ion:+.3f});  "
              f"I_e = {extra['I_e']*1e9:.3f} nA vs I_i = {extra['I_i']*1e9:.3f} nA")
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
