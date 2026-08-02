#!/usr/bin/env python3
"""Cohort analysis for capstone.mission_envelope.

Takes one COMPLETE run per mission scenario, verifies they share this stage and
this configuration generation (rejecting mixed generations and smoke runs, whose
shortened t_end changes the study hash), computes each scenario's capstone
metrics, and then does the thing this stage exists for: **compares the
measurement against the prediction that was committed before the run**.

Three families of metric, per scenario S:

  theory / identity   inherited from the capstone policy -- current balance,
                      momentum sanity, sheath containment, ledger-vs-dump charge
                      consistency.  These say the RUN is sound.
  model validation    S__f_beam_over_pred, S__phi_body_over_pred,
                      S__escape_fraction_pct, S__phi_body_V, and
                      S__prediction_consistency (the anti-post-hoc guard: the
                      frozen predictions must be exactly what the frozen
                      constants imply).  These say the MODEL is right.
  refit outputs       k_meas / ke_ledger_meas / beta_meas per scenario, reported
                      not gated -- except through the cross-scenario
                      beta_log_spread, which IS the law-form test: beta must not
                      move between chi = 200 and chi = 386 if
                      I_return ~ (1 + chi) is the right shape.

    python analyze.py --runs outputs/<A-run> outputs/<B-run> --policy acceptance.yaml

Exit 0 all required gates pass / 1 a gate fails / 2 analysis error.
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
import opmodel  # noqa: E402
from helpers import (  # noqa: E402
    AMB_E, AMB_I, BEAM, STAGE_ID, Config, load_config, scenario_names,
)

DEFAULT_CONFIG = CASE_DIR / "config.yaml"
DEFAULT_POLICY = CASE_DIR / "acceptance.yaml"
RESULTS_ROOT = CASE_DIR / "results"

E = scc.e


# ======================================================================
# evidence readers (transcribed from capstone/2_chipsat_thruster/analyze.py)
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
    """Linear-fit slope of phi_body over the last `window_s` [V/s]."""
    t = np.atleast_1d(d["t"])
    phi = np.atleast_1d(d["phi_body"])
    m = t >= (t[-1] - window_s)
    if m.sum() < 3:
        return float("nan")
    return float(np.polyfit(t[m], phi[m], 1)[0])


def observed_settle_time_s(d, phi_final: float) -> float:
    """When phi_body first reached (1 - 1/e) of its plateau value [s].

    Reported, never gated -- but it is the direct check on the settle-time model
    that chose t_end, and on the guard that chose scenario B.
    """
    t = np.atleast_1d(d["t"])
    phi = np.atleast_1d(d["phi_body"])
    if not np.isfinite(phi_final) or phi_final <= 0:
        return float("nan")
    target = (1.0 - 1.0 / math.e) * phi_final
    hit = np.nonzero(phi >= target)[0]
    return float(t[hit[0]]) if hit.size else float("nan")


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
    """Total scraped real-particle weight per (species, boundary) over the run."""
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
    """Reconstruct the cumulative charge [C] behind a CSV current column."""
    steps = np.atleast_1d(d["step"]).astype(float)
    I = np.atleast_1d(d[col])
    wins = np.diff(np.concatenate([[0.0], steps])) * dt
    return float(np.nansum(I * wins))


# ======================================================================
# per-scenario measurement
# ======================================================================

def scenario_measurements(cfg: Config, evidence: lc.LoadedRun,
                          tail_frac: float) -> dict:
    """Everything one run contributes, measured before any gate is applied."""
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

    ts = OpenPMDTimeSeries(os.path.join(str(diags), "fields"),
                           check_all_files=False)
    last = ts.iterations[-1]

    totals = scraped_weight_totals(diags)
    q_pmd = E * totals.get((AMB_E, "eb"), 0.0)
    q_csv = csv_charge(d, "I_amb_e", cfg.dt)
    q_pmd_beam = E * sum(totals.get((BEAM, b), 0.0) for b in ("zhi", "zlo", "xhi"))
    q_csv_beam = csv_charge(d, "I_escape", cfg.dt)

    # --- the model side -------------------------------------------------
    frozen = {k: float(cfg.predicted[k])
              for k in ("phi_body_V", "f_beam_nN", "exhaust_ke_eV")}
    recomputed = cfg.model_prediction()
    consistency = max(
        abs(recomputed[k] - frozen[k]) / max(abs(frozen[k]), 1.0)
        for k in frozen)

    refit = opmodel.measured_constants(
        f_beam_nN=s["F_beam_N"] * 1e9, phi_body_V=s["phi_body"],
        escape_fraction_pct=s["pct_escape"],
        exhaust_ke_eV=s["beam_escape_KE_mean"], i_beam_A=cfg.i_beam,
        v_drive=cfg.V_GAP, n_e=cfg.n0, Te_K=cfg.Te_K,
        area_m2=float(cfg.law_anchor["area_m2"]))

    net_amb = s["I_amb_e"] - s["I_amb_i"]
    return dict(
        d=d, ts=ts, s=s, window=window, n_tail=n_rows - i0,
        frozen=frozen, recomputed=recomputed, prediction_consistency=consistency,
        refit=refit,
        edge_phi_max=edge_phi(ts, last),
        current_balance=(abs(s["I_escape"] - net_amb) / abs(s["I_escape"])
                         if s["I_escape"] else float("nan")),
        f_net_over_f_beam=(abs(s["F_net_N"]) / abs(s["F_beam_N"])
                           if s["F_beam_N"] else float("nan")),
        scrape_consistency=(abs(q_csv - q_pmd) / q_pmd if q_pmd > 0 else float("nan")),
        scrape_consistency_beam=(abs(q_csv_beam - q_pmd_beam) / q_pmd_beam
                                 if q_pmd_beam > 0 else float("nan")),
        late_dphidt=late_slope(d),
        settle_observed_s=observed_settle_time_s(d, s["phi_body"]),
        q_csv=q_csv, q_pmd=q_pmd, q_csv_beam=q_csv_beam, q_pmd_beam=q_pmd_beam,
    )


# ======================================================================
# metrics
# ======================================================================

def build_metrics(order: list[str], cfgs: dict, meas: dict) -> dict:
    metrics: dict[str, lc.Metric] = {}

    def add(mid, value, unit, **kw):
        metrics[mid] = lc.Metric.measure(mid, value, unit, **kw)

    for name in order:
        cfg, m = cfgs[name], meas[name]
        s, w = m["s"], m["window"]
        p = f"{name}__"

        # ---- theory / identity: is the RUN sound? ----------------------
        add(p + "current_balance", m["current_balance"], "-", window=w,
            source="|I_escape - (I_amb_e - I_amb_i)| / I_escape, tail means")
        add(p + "f_net_over_f_beam", m["f_net_over_f_beam"], "-", window=w,
            source="|F_net| / |F_beam| momentum sanity bound")
        add(p + "edge_phi_max_V", m["edge_phi_max"], "V",
            source="max |phi| a few cells inside the open boundaries, last dump")
        add(p + "scrape_charge_consistency", m["scrape_consistency"], "-",
            source="ambient-e EB charge: CSV ledger integral vs openPMD scrape total")
        add(p + "scrape_charge_consistency_beam_escape", m["scrape_consistency_beam"],
            "-", source="beam-escape charge: CSV ledger I_escape integral vs "
                        "openPMD zhi+zlo+xhi scrape total")

        # ---- model validation: is the MODEL right? ---------------------
        add(p + "phi_body_V", s["phi_body"], "V", window=w,
            source="contactor_log.csv phi_body, tail mean")
        add(p + "f_beam_nN", s["F_beam_N"] * 1e9, "nN", window=w,
            source="contactor_log.csv F_beam_N (escaped-beam z-momentum flux)")
        add(p + "escape_fraction_pct", s["pct_escape"], "%", window=w,
            sample_count=m["n_tail"],
            source="contactor_log.csv pct_escape (cumulative beam fate), tail mean")
        add(p + "f_beam_over_pred", s["F_beam_N"] * 1e9 / m["frozen"]["f_beam_nN"],
            "-", window=w,
            source=f"measured F_beam / pre-registered "
                   f"{m['frozen']['f_beam_nN']:.4f} nN")
        add(p + "phi_body_over_pred", s["phi_body"] / m["frozen"]["phi_body_V"],
            "-", window=w,
            source=f"measured phi_body / pre-registered "
                   f"{m['frozen']['phi_body_V']:.4f} V")
        add(p + "prediction_consistency", m["prediction_consistency"], "-",
            source="frozen predicted: block vs the same block recomputed from the "
                   "frozen law_anchor constants (anti-post-hoc guard; catches "
                   "drift between this stage's opmodel and design_sims')")

        # ---- reported, never gated ------------------------------------
        add(p + "exhaust_ke_mean_eV", s["beam_escape_KE_mean"], "eV", window=w,
            source="contactor_log.csv beam_escape_KE_mean (REPORTED)")
        add(p + "exhaust_ke_over_pred",
            s["beam_escape_KE_mean"] / m["frozen"]["exhaust_ke_eV"], "-", window=w,
            source="measured exhaust KE / pre-registered (REPORTED)")
        add(p + "late_dphidt_V_per_ns", m["late_dphidt"] * 1e-9, "V/ns",
            source="phi_body linear slope over the last 50 ns (REPORTED: "
                   "finite-time-equilibrium honesty line)")
        add(p + "settle_time_observed_ns", m["settle_observed_s"] * 1e9, "ns",
            source="first time phi_body reached (1-1/e) of its plateau (REPORTED)")
        add(p + "settle_time_predicted_ns",
            cfg.predicted_settle_time_s() * 1e9, "ns",
            source="tau = C*phi_pred/I from the frozen capacitance (REPORTED)")
        add(p + "p_supply_mW", cfg.i_beam * cfg.V_GAP * 1e3, "mW",
            source="I*V at the frozen operating point (REPORTED)")
        add(p + "i_over_i_cl", cfg.i_beam / cfg.I_CL, "-",
            source="beam current / planar Child-Langmuir scale (REPORTED)")
        add(p + "chi_measured", m["refit"]["chi_meas"], "-",
            source="e*phi_body/kTe at the measured float (REPORTED)")
        add(p + "k_meas", m["refit"]["k_meas"], "nN/(mA*sqrt(eV))",
            source="thrust law inverted at this run (REPORTED refit output)")
        add(p + "ke_ledger_meas", m["refit"]["ke_ledger_meas"], "-",
            source="energy ledger inverted at this run (REPORTED refit output)")
        add(p + "beta_meas", m["refit"]["beta_meas"], "-",
            source="collection law inverted at this run (REPORTED refit output; "
                   "the cross-scenario spread of these IS the law-form test)")
        add(p + "drag_target_nN", cfg.drag_target_N * 1e9, "nN",
            source="the mission row's drag demand (REPORTED)")
        add(p + "thrust_over_demand",
            s["F_beam_N"] * 1e9 / (cfg.drag_target_N * 1e9)
            if cfg.drag_target_N > 0 else float("nan"), "-",
            source="measured thrust / this row's drag demand (REPORTED)")

    # ---- cross-scenario: the law-form test proper ----------------------
    a, b = order[0], order[1]
    f_a = meas[a]["s"]["F_beam_N"] * 1e9
    f_b = meas[b]["s"]["F_beam_N"] * 1e9
    add("day_minus_night_f_beam_nN", f_a - f_b, "nN",
        source=f"{a} minus {b} measured thrust: the two operating points must "
               f"actually be distinguishable")

    beta_a = meas[a]["refit"]["beta_meas"]
    beta_b = meas[b]["refit"]["beta_meas"]
    spread = (abs(math.log(beta_a / beta_b))
              if beta_a > 0 and beta_b > 0 else float("nan"))
    add("beta_log_spread", spread, "-",
        source=f"|ln(beta_{a}/beta_{b})| at chi = "
               f"{meas[a]['refit']['chi_meas']:.0f} vs "
               f"{meas[b]['refit']['chi_meas']:.0f} -- if I_return ~ (1+chi) is "
               f"the right law form, beta must not move between them")
    add("chi_ratio", (meas[b]["refit"]["chi_meas"] / meas[a]["refit"]["chi_meas"]
                      if meas[a]["refit"]["chi_meas"] else float("nan")), "-",
        source="how far apart in chi the two scenarios actually are (REPORTED: "
               "the leverage the beta_log_spread gate has)")
    return metrics


# ======================================================================
# figures
# ======================================================================

def write_outputs(analysis, order, cfgs, meas):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figs = analysis.figures_dir
    colors = {order[0]: "tab:orange", order[1]: "tab:blue"}

    # 1: the float, measured vs pre-registered
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, name in zip(axes, order):
        d, m, cfg = meas[name]["d"], meas[name], cfgs[name]
        t_ns = np.atleast_1d(d["t"]) * 1e9
        ax.plot(t_ns, d["phi_body"], color=colors[name], lw=1.5, label="measured")
        ax.axhline(m["frozen"]["phi_body_V"], color="k", ls="--", lw=1.2,
                   label=f"pre-registered {m['frozen']['phi_body_V']:.2f} V")
        ax.axvline(cfg.t_on * 1e9, color="gray", ls=":", lw=0.8)
        tau = cfg.predicted_settle_time_s() * 1e9
        ax.axvline(cfg.t_on * 1e9 + tau, color="tab:green", ls=":", lw=1.0,
                   label=f"gun-on + tau ({tau:.0f} ns)")
        ax.set_title(f"{name}\nn_e={cfg.n0:.2e} m^-3, Te={cfg.Te_K:.0f} K, "
                     f"V={cfg.V_GAP:.0f} V, I={cfg.i_beam*1e3:.4f} mA")
        ax.set_xlabel("time [ns]")
        ax.set_ylabel("phi_body [V]")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.suptitle("Floating potential: measurement vs the prediction committed "
                 "before the run")
    fig.tight_layout()
    fig.savefig(figs / "phi_vs_prediction.png", dpi=130)
    plt.close(fig)

    # 2: thrust and fate
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for col, name in enumerate(order):
        d, m, cfg = meas[name]["d"], meas[name], cfgs[name]
        t_ns = np.atleast_1d(d["t"]) * 1e9
        ax = axes[0][col]
        ax.plot(t_ns, d["F_beam_N"] * 1e9, color=colors[name], label="F_beam")
        ax.axhline(m["frozen"]["f_beam_nN"], color="k", ls="--", lw=1.2,
                   label=f"pre-registered {m['frozen']['f_beam_nN']:.2f} nN")
        ax.axhline(cfg.drag_target_N * 1e9, color="tab:red", ls=":", lw=1.2,
                   label=f"drag demand {cfg.drag_target_N*1e9:.1f} nN")
        ax.set_title(f"{name}: thrust")
        ax.set_xlabel("time [ns]"); ax.set_ylabel("thrust [nN]")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)

        ax = axes[1][col]
        ax.plot(t_ns, d["pct_escape"], color="tab:green", lw=2, label="% escaped")
        ax.plot(t_ns, d["pct_body"], color="tab:orange", label="% on body")
        ax.plot(t_ns, d["pct_cathode"], color="tab:red", label="% back to cathode")
        ax.plot(t_ns, d["pct_inflight"], color="tab:gray", ls=":", label="% in flight")
        ax.set_ylim(-2, 102)
        ax.set_title(f"{name}: beam fate")
        ax.set_xlabel("time [ns]"); ax.set_ylabel("cumulative fraction [%]")
        ax.legend(fontsize=8, loc="center right"); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(figs / "thrust_and_fate.png", dpi=130)
    plt.close(fig)

    # 3: the law-form test -- beta vs chi
    fig, ax = plt.subplots(figsize=(7, 5))
    for name in order:
        r = meas[name]["refit"]
        ax.plot([r["chi_meas"]], [r["beta_meas"]], "o", ms=12,
                color=colors[name], label=f"{name} (chi={r['chi_meas']:.0f})")
    anchor_beta = float(cfgs[order[0]].law_anchor["beta"])
    ax.axhline(anchor_beta, color="k", ls="--", lw=1.2,
               label=f"anchored beta = {anchor_beta:.4f} (chi=149)")
    ax.axhline(anchor_beta * 1.5, color="gray", ls=":", lw=0.9)
    ax.axhline(anchor_beta / 1.5, color="gray", ls=":", lw=0.9,
               label="+/- a factor 1.5 (the gate)")
    ax.set_xscale("log")
    ax.set_xlabel("chi = e*phi/kTe at the measured float")
    ax.set_ylabel("beta measured by inverting the collection law")
    ax.set_title("The law-form test: does beta stay put across chi?\n"
                 "(if I_return ~ (1+chi) is right, these lie on one line)")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(figs / "beta_vs_chi.png", dpi=130)
    plt.close(fig)


# ======================================================================
# driver
# ======================================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="mission-envelope cohort analysis")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--runs", type=Path, nargs="+",
                   help="one COMPLETE run directory per scenario")
    g.add_argument("--run", type=Path,
                   help="rejected: this stage is a cohort of scenarios")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    ap.add_argument("--tail-frac", type=float, default=0.2,
                    help="fraction of the record treated as the plateau")
    return ap.parse_args(argv)


def _print_verdict(verdict: lc.Verdict, order, cfgs, meas) -> None:
    print("\n" + "=" * 78)
    print("MODEL VS MEASUREMENT (the claim under test)")
    for name in order:
        m, cfg = meas[name], cfgs[name]
        s = m["s"]
        print(f"  {name}  (n_e={cfg.n0:.3e} m^-3, Te={cfg.Te_K:.0f} K, "
              f"V={cfg.V_GAP:.0f} V, I={cfg.i_beam*1e3:.4f} mA)")
        print(f"    phi_body    predicted {m['frozen']['phi_body_V']:+8.3f} V   "
              f"measured {s['phi_body']:+8.3f} V   "
              f"ratio {s['phi_body']/m['frozen']['phi_body_V']:.4f}")
        print(f"    F_beam      predicted {m['frozen']['f_beam_nN']:8.3f} nN  "
              f"measured {s['F_beam_N']*1e9:8.3f} nN  "
              f"ratio {s['F_beam_N']*1e9/m['frozen']['f_beam_nN']:.4f}")
        print(f"    exhaust KE  predicted {m['frozen']['exhaust_ke_eV']:8.2f} eV  "
              f"measured {s['beam_escape_KE_mean']:8.2f} eV")
        print(f"    escape {s['pct_escape']:.2f} %   "
              f"settle tau: predicted {cfg.predicted_settle_time_s()*1e9:.0f} ns, "
              f"observed {m['settle_observed_s']*1e9:.0f} ns")
        print(f"    refit: k={m['refit']['k_meas']:.4f} "
              f"ke_ledger={m['refit']['ke_ledger_meas']:.4f} "
              f"beta={m['refit']['beta_meas']:.4f} at chi={m['refit']['chi_meas']:.0f}"
              f"   (anchored: k={float(cfg.law_anchor['k']):.4f} "
              f"ke_ledger={float(cfg.law_anchor['ke_ledger']):.4f} "
              f"beta={float(cfg.law_anchor['beta']):.4f} at chi=149)")
        print(f"    thrust vs this row's drag demand: "
              f"{s['F_beam_N']*1e9:.3f} / {cfg.drag_target_N*1e9:.3f} nN")
    print("=" * 78)
    print(f"VALIDATION GATES  [{verdict.stage_id}]  policy {verdict.policy_id}")
    print("=" * 78)
    for g in verdict.gates:
        print(f"[{g.status:4s}] {g.id}\n       {g.detail}")
    print("=" * 78)
    print(f"VERDICT: {verdict.status}  (exit {verdict.exit_code}) -- {verdict.detail}")
    print("=" * 78)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.run:
            raise lc.ContractError(
                "capstone.mission_envelope is a cohort stage: pass --runs with "
                "one COMPLETE run per scenario")
        order = scenario_names(args.config)
        if len(order) != 2:
            raise lc.ContractError(
                f"mission_envelope expects exactly 2 scenarios, got {order}")
        cohort = lc.load_complete_runs(args.runs)
        # This is what rejects a smoke run: its shortened t_end changes the
        # study hash, so it cannot share a cohort with a real run.
        lc.check_cohort(cohort, stage_id=STAGE_ID, require_scenarios=order)
        policy = lc.load_policy(args.policy)
        if policy.stage_id != STAGE_ID:
            raise lc.ContractError(
                f"policy stage {policy.stage_id} != {STAGE_ID}")
        by_scn = {r.scenario: r for r in cohort}
        cfgs = {name: load_config(by_scn[name].dir / "config_used.yaml", name)
                for name in order}
    except lc.ContractError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return lc.EXIT_ERROR

    analysis = lc.begin_analysis(cohort, policy, results_root=RESULTS_ROOT,
                                 analyzer_source=__file__)
    print(f"ANALYSIS_ID={analysis.analysis_id}", flush=True)
    try:
        meas = {name: scenario_measurements(cfgs[name], by_scn[name],
                                            args.tail_frac)
                for name in order}
        metrics = build_metrics(order, cfgs, meas)
        verdict = lc.evaluate_gates(metrics, policy)
        lc.write_metrics(analysis, metrics)
        lc.write_verdict(analysis, verdict)
        write_outputs(analysis, order, cfgs, meas)
        lc.complete_analysis(analysis, verdict)
        _print_verdict(verdict, order, cfgs, meas)
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
