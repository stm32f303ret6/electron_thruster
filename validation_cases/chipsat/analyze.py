#!/usr/bin/env python3
"""Analysis for capstone.floating_body (the chipsat capstone).

Reads one COMPLETE run's frozen evidence -- the contactor_log.csv ledger, the
openPMD field and scrape dumps -- computes the steady-state system metrics
(escape fraction, F_beam, phi_body, current balance, momentum sanity, sheath
containment, ledger-vs-dump charge consistency), and evaluates the float200
regression policy through the shared contract.  Exit 0 all required gates
pass / 1 a gate fails / 2 analysis error.

Reported but not gated (honesty lines): mean exhaust KE, the energy ledger
(injection-plane phi reconciliation), and the late dphi/dt of the plateau
(a finite-time equilibrium on the ion clock -- plan C6, Phase 5).

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
sys.path.insert(0, str(CASE_DIR.parents[0]))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc  # noqa: E402
from helpers import AMB_E, AMB_I, BEAM, STAGE_ID, Config, load_config  # noqa: E402

DEFAULT_POLICY = CASE_DIR / "acceptance.yaml"
RESULTS_ROOT = CASE_DIR / "results"

E = scc.e


# ======================================================================
# evidence readers
# ======================================================================

def load_ledger(diags: Path):
    """The per-window CSV ledger written by simulation.py's observer."""
    path = diags / "contactor_log.csv"
    if not path.exists():
        raise lc.ContractError(f"no {path} in the run evidence")
    d = np.atleast_1d(np.genfromtxt(path, delimiter=",", names=True))
    if d.size == 0:
        raise lc.ContractError(f"{path} has no data rows")
    return d


def steady(d, col: str, tail_frac: float) -> float:
    """Mean of `col` over the last tail_frac of the record (the plateau)."""
    n = len(d["t"])
    i0 = max(0, int(n * (1.0 - tail_frac)))
    v = np.atleast_1d(d[col])[i0:]
    v = v[np.isfinite(v)]
    return float(v.mean()) if v.size else float("nan")


def late_slope(d, window_s: float = 50e-9) -> float:
    """Linear-fit slope of phi_body over the last `window_s` [V/s]: how fast the
    tail is still moving, so finite-time equilibria are labelled honestly."""
    t = np.atleast_1d(d["t"])
    phi = np.atleast_1d(d["phi_body"])
    m = t >= (t[-1] - window_s)
    if m.sum() < 3:
        return float("nan")
    return float(np.polyfit(t[m], phi[m], 1)[0])


def field_rz(ts, field, iteration):
    """Reconstruct the (r>=0, z) half-plane, robust to axis order."""
    F, info = ts.get_field(field=field, iteration=iteration, m="all", theta=0.0)
    r, z = np.asarray(info.r), np.asarray(info.z)
    raxis = next(k for k, v in dict(info.axes).items() if v == "r")
    if raxis == 1:
        F = F.T
    pos = r >= 0
    return F[pos], r[pos], z


def edge_phi(ts, iteration, inset: int = 3) -> float:
    """Max |phi| a few cells inside the three open boundaries (containment)."""
    phi, r, z = field_rz(ts, "phi", iteration)
    return float(max(np.abs(phi[-1 - inset, :]).max(),
                     np.abs(phi[:, inset]).max(),
                     np.abs(phi[:, -1 - inset]).max()))


def scraped_weight_totals(diags: Path) -> dict:
    """Total scraped real-particle weight per (species, boundary) over the whole
    run, from the openPMD scrape dumps."""
    import openpmd_api as io

    out: dict[tuple[str, str], float] = {}
    for sub in sorted(glob.glob(os.path.join(str(diags), "scrape",
                                             "particles_at_*"))):
        if not glob.glob(os.path.join(sub, "*.h5")):
            continue
        bnd = os.path.basename(sub).replace("particles_at_", "")
        series = io.Series(os.path.join(sub, "openpmd_%T.h5"),
                           io.Access.read_only)
        for it in series.iterations:
            parts = series.iterations[it].particles
            for name in (BEAM, AMB_E, AMB_I):
                if name not in parts:
                    continue
                wh = parts[name]["weighting"][io.Mesh_Record_Component.SCALAR]
                dw = wh.load_chunk()
                series.flush()
                w = np.asarray(dw) * wh.unit_SI
                if w.size:
                    out[(name, bnd)] = out.get((name, bnd), 0.0) + float(w.sum())
        series.close()
    return out


def csv_charge(d, col: str, dt: float) -> float:
    """Reconstruct the cumulative charge [C] behind a CSV current column.

    Each row records acc/win over its window, so I*win re-sums to the exact
    accumulated charge; window lengths come from the step-column differences."""
    steps = np.atleast_1d(d["step"]).astype(float)
    I = np.atleast_1d(d[col])
    wins = np.diff(np.concatenate([[0.0], steps])) * dt
    return float(np.nansum(I * wins))


def energy_ledger(cfg: Config, ts, tail_frac: float):
    """P0.7 energy bookkeeping: the beam is born at z_emit = cathode-top + 2*dx,
    so it skips part of the accelerating gap.  Sample phi at the injection plane
    over the tail field dumps:  predicted exhaust KE = -phi(r~0, z_emit)."""
    geom = cfg.geometry()
    its = list(ts.iterations)
    tail = [i for i in its if i >= its[-1] * (1.0 - tail_frac)] or its[-1:]
    nr_spot = int(np.floor(geom.we / cfg.dx)) + 1
    axis_v, spot_v = [], []
    for it in tail:
        phi, r, z = field_rz(ts, "phi", it)
        prof = np.empty(nr_spot)
        for j in range(nr_spot):        # linear interp in z at each radial column
            prof[j] = np.interp(geom.z_emit, z, phi[j, :])
        axis_v.append(prof[0])
        rr = r[:nr_spot]
        spot_v.append(float(np.trapezoid(prof * rr, rr) / np.trapezoid(rr, rr)))
    return dict(
        phi_inject_axis_V=float(np.mean(axis_v)),
        phi_inject_axis_std_V=float(np.std(axis_v)),
        phi_inject_spot_V=float(np.mean(spot_v)),
        ke_pred_eV=float(-np.mean(axis_v)),
        n_tail_dumps=len(tail))


# ======================================================================
# metrics
# ======================================================================

def compute_metrics(cfg: Config, evidence: lc.LoadedRun, tail_frac: float):
    from openpmd_viewer import OpenPMDTimeSeries

    diags = evidence.diags_dir
    d = load_ledger(diags)
    n_rows = len(np.atleast_1d(d["t"]))
    i0 = max(0, int(n_rows * (1.0 - tail_frac)))
    window = {"start_iteration": int(np.atleast_1d(d["step"])[i0]),
              "end_iteration": int(np.atleast_1d(d["step"])[-1])}
    s = {k: steady(d, k, tail_frac) for k in
         ("phi_body", "pct_escape", "pct_body", "pct_cathode", "pct_inflight",
          "I_escape", "I_amb_e", "I_amb_i", "F_beam_N", "F_net_N",
          "beam_escape_KE_mean")}

    metrics: dict[str, lc.Metric] = {}
    metrics["escape_fraction_pct"] = lc.Metric.measure(
        "escape_fraction_pct", s["pct_escape"], "%", window=window,
        sample_count=n_rows - i0,
        source="contactor_log.csv pct_escape (cumulative beam fate), tail mean")
    metrics["f_beam_nN"] = lc.Metric.measure(
        "f_beam_nN", s["F_beam_N"] * 1e9, "nN", window=window,
        source="contactor_log.csv F_beam_N (escaped-beam z-momentum flux)")
    metrics["phi_body_V"] = lc.Metric.measure(
        "phi_body_V", s["phi_body"], "V", window=window,
        source="contactor_log.csv phi_body, tail mean")
    net_amb = s["I_amb_e"] - s["I_amb_i"]
    balance = (abs(s["I_escape"] - net_amb) / abs(s["I_escape"])
               if s["I_escape"] else float("nan"))
    metrics["current_balance"] = lc.Metric.measure(
        "current_balance", balance, "-", window=window,
        source="|I_escape - (I_amb_e - I_amb_i)| / I_escape, tail means")
    fn_over_fb = (abs(s["F_net_N"]) / abs(s["F_beam_N"])
                  if s["F_beam_N"] else float("nan"))
    metrics["f_net_over_f_beam"] = lc.Metric.measure(
        "f_net_over_f_beam", fn_over_fb, "-", window=window,
        source="|F_net| / |F_beam| momentum sanity bound")

    # sheath/plume containment from the last field dump
    ts = OpenPMDTimeSeries(os.path.join(str(diags), "fields"),
                           check_all_files=False)
    last = ts.iterations[-1]
    metrics["edge_phi_max_V"] = lc.Metric.measure(
        "edge_phi_max_V", edge_phi(ts, last), "V",
        source="max |phi| a few cells inside the open boundaries, last dump")

    # ledger-vs-dump charge consistency (closes VALIDATION_GAPS.md G5): the
    # charge pump trusts per-step scrape buffers; the openPMD dumps accumulate
    # the same scrapes independently.  Check the largest ambient channel
    # (electrons on the EB) and, separately, the beam-escape channel -- the
    # dominant term in phi_body's charge budget (~98.5% of the pump signal)
    # and the most complex telescoping accounting (dW_beam/beam_escape vs.
    # amb_e_coll/amb_i_coll in FloatingBody.step), so it is the one most
    # likely to hide a bug if left unchecked.  The CSV misses at most the
    # final partial window (< LOG_EVERY steps ~ 0.06% of the run), far
    # inside the gate.
    totals = scraped_weight_totals(diags)
    q_pmd = E * totals.get((AMB_E, "eb"), 0.0)
    q_csv = csv_charge(d, "I_amb_e", cfg.dt)
    consistency = (abs(q_csv - q_pmd) / q_pmd) if q_pmd > 0 else float("nan")
    metrics["scrape_charge_consistency"] = lc.Metric.measure(
        "scrape_charge_consistency", consistency, "-",
        source="ambient-e EB charge: CSV ledger integral vs openPMD scrape total")

    q_pmd_beam = E * sum(totals.get((BEAM, b), 0.0) for b in ("zhi", "zlo", "xhi"))
    q_csv_beam = csv_charge(d, "I_escape", cfg.dt)
    beam_consistency = (abs(q_csv_beam - q_pmd_beam) / q_pmd_beam
                        if q_pmd_beam > 0 else float("nan"))
    metrics["scrape_charge_consistency_beam_escape"] = lc.Metric.measure(
        "scrape_charge_consistency_beam_escape", beam_consistency, "-",
        source="beam-escape charge: CSV ledger I_escape integral vs "
               "openPMD zhi+zlo+xhi scrape total")

    # ----- reported-only quantities (never gated here) -----
    ledger = energy_ledger(cfg, ts, tail_frac)
    ke_ideal = cfg.V_GAP - s["phi_body"]
    metrics["exhaust_ke_mean_eV"] = lc.Metric.measure(
        "exhaust_ke_mean_eV", s["beam_escape_KE_mean"], "eV", window=window,
        source="contactor_log.csv beam_escape_KE_mean (REPORTED, not gated)")
    metrics["late_dphidt_V_per_ns"] = lc.Metric.measure(
        "late_dphidt_V_per_ns", late_slope(d) * 1e-9, "V/ns",
        source="phi_body linear slope over the last 50 ns (REPORTED: "
               "finite-time-equilibrium honesty line, plan C6)")
    metrics["ke_predicted_eV"] = lc.Metric.measure(
        "ke_predicted_eV", ledger["ke_pred_eV"], "eV",
        source="-phi(injection plane) from tail field dumps (REPORTED)")

    extra = dict(d=d, s=s, ledger=ledger, ke_ideal=ke_ideal, ts=ts,
                 totals=totals, q_csv=q_csv, q_pmd=q_pmd,
                 q_csv_beam=q_csv_beam, q_pmd_beam=q_pmd_beam)
    return metrics, extra


# ======================================================================
# figures
# ======================================================================

def write_outputs(analysis, cfg: Config, metrics, extra):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figs = analysis.figures_dir
    d = extra["d"]
    t_ns = np.atleast_1d(d["t"]) * 1e9
    t_on_ns = cfg.t_on * 1e9

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t_ns, d["pct_escape"], label="% escaped (thrust)",
            color="tab:green", lw=2)
    ax.plot(t_ns, d["pct_body"], label="% on body", color="tab:orange")
    ax.plot(t_ns, d["pct_cathode"], label="% back to cathode", color="tab:red")
    ax.plot(t_ns, d["pct_inflight"], label="% in flight", color="tab:gray",
            ls=":")
    ax.axvline(t_on_ns, color="k", ls="--", lw=0.8,
               label=f"gun on ({t_on_ns:.0f} ns)")
    ax.set_xlabel("time [ns]")
    ax.set_ylabel("cumulative fraction of emitted beam [%]")
    ax.set_title("Fate of the emitted electrons")
    ax.set_ylim(-2, 102)
    ax.legend(loc="center right"); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(figs / "fates_vs_time.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t_ns, d["phi_body"], color="tab:blue", label="phi_body (floating)")
    ax.axhline(0.0, color="k", lw=0.5)
    ax.axvline(t_on_ns, color="k", ls="--", lw=0.8)
    ax.set_xlabel("time [ns]"); ax.set_ylabel("phi_body [V]", color="tab:blue")
    ax.set_title("Emergent floating-body potential"); ax.grid(alpha=0.3)
    ax2 = ax.twinx()
    ax2.plot(t_ns, d["V_cathode"], color="tab:purple", alpha=0.5)
    ax2.set_ylabel("V_cathode [V]", color="tab:purple")
    fig.tight_layout(); fig.savefig(figs / "phi_vs_time.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t_ns, d["I_escape"] * 1e3, label="I_escape (beam leaves)")
    ax.plot(t_ns, d["I_body"] * 1e3, label="I_body (beam on body)")
    ax.plot(t_ns, d["I_cathode"] * 1e3, label="I_cathode (beam back)")
    ax.plot(t_ns, d["I_amb_e"] * 1e3, label="I_amb_e (ambient e- collected)",
            ls=":")
    ax.plot(t_ns, d["I_amb_i"] * 1e3, label="I_amb_i (ambient ions collected)",
            ls=":")
    ax.axvline(t_on_ns, color="k", ls="--", lw=0.8)
    ax.set_xlabel("time [ns]"); ax.set_ylabel("current [mA]")
    ax.set_title("Per-channel currents"); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(figs / "currents_vs_time.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t_ns, d["F_beam_N"] * 1e9, color="tab:green",
            label="F_beam (escaped beam)")
    ax.plot(t_ns, d["F_net_N"] * 1e9, color="tab:red", alpha=0.7,
            label="F_net (all-EB impact)")
    ax.axvline(t_on_ns, color="k", ls="--", lw=0.8)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xlabel("time [ns]"); ax.set_ylabel("thrust [nN]")
    ax.legend(loc="upper left")
    ax.set_title("Thrust (two accountings) and mean exhaust energy")
    ax.grid(alpha=0.3)
    ax2 = ax.twinx()
    ax2.plot(t_ns, d["beam_escape_KE_mean"], color="tab:brown", alpha=0.5)
    ax2.set_ylabel("mean escaped-beam KE [eV]", color="tab:brown")
    fig.tight_layout(); fig.savefig(figs / "thrust_vs_time.png", dpi=130)
    plt.close(fig)


# ======================================================================
# driver
# ======================================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="chipsat capstone analysis")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", type=Path, help="a COMPLETE run directory")
    g.add_argument("--runs", type=Path, nargs="+",
                   help="rejected: the capstone is single-run")
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    ap.add_argument("--tail-frac", type=float, default=0.2,
                    help="fraction of the record treated as the plateau")
    return ap.parse_args(argv)


def _print_verdict(verdict: lc.Verdict, extra) -> None:
    s, ledger = extra["s"], extra["ledger"]
    print("\n" + "=" * 72)
    print("STEADY-STATE SUMMARY (reported)")
    print(f"  exhaust KE mean = {s['beam_escape_KE_mean']:.2f} eV   "
          f"predicted (injection plane) = {ledger['ke_pred_eV']:.2f} eV   "
          f"ideal (V_GAP - phi_body) = {extra['ke_ideal']:.2f} eV")
    print(f"  ledger-vs-dump ambient-e charge: CSV {extra['q_csv']:.4e} C "
          f"vs openPMD {extra['q_pmd']:.4e} C")
    print(f"  ledger-vs-dump beam-escape charge: CSV {extra['q_csv_beam']:.4e} C "
          f"vs openPMD {extra['q_pmd_beam']:.4e} C")
    print("=" * 72)
    print(f"VALIDATION GATES  [{verdict.stage_id}]  policy {verdict.policy_id}")
    print("=" * 72)
    for g in verdict.gates:
        print(f"[{g.status:4s}] {g.id}\n       {g.detail}")
    print("=" * 72)
    print(f"VERDICT: {verdict.status}  (exit {verdict.exit_code}) -- "
          f"{verdict.detail}")
    print("=" * 72)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        run_dirs = [args.run] if args.run else args.runs
        if len(run_dirs) != 1:
            raise lc.ContractError("capstone.floating_body is single-run")
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
        metrics, extra = compute_metrics(cfg, evidence, args.tail_frac)
        verdict = lc.evaluate_gates(metrics, policy)
        lc.write_metrics(analysis, metrics)
        lc.write_verdict(analysis, verdict)
        write_outputs(analysis, cfg, metrics, extra)
        lc.complete_analysis(analysis, verdict)
        _print_verdict(verdict, extra)
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
