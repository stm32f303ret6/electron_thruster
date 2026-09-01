#!/usr/bin/env python3
"""Cohort analysis for characterization.magnetized_transverse.

Takes one COMPLETE run per scenario (any subset for a look, all three for a
verdict), verifies they share this stage and source study, computes each
scenario's steady-state metrics from its frozen evidence (contactor_log.csv
ledger, openPMD field/scrape dumps, calibration.json), the cross-scenario
deltas against the unmagnetized control, and evaluates the policy through the
shared contract.  Exit 0 all required gates pass / 1 a gate fails / 2 analysis
error or incomplete cohort (a missing scenario leaves its required gates
unevaluable, which is ERROR, never PASS).

    python analyze.py --runs outputs/<b0> outputs/<1x> outputs/<10x> --policy acceptance.yaml
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
_pic_root = CASE_DIR  # walk up to pic_sims/ (ladder_contract, shared plumbing)
while not (_pic_root / "ladder_contract.py").is_file():
    _pic_root = _pic_root.parent
sys.path.insert(0, str(_pic_root))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc  # noqa: E402
from helpers import (  # noqa: E402
    AMB_E, AMB_I, BEAM, E, ME, STAGE_ID, Config, load_config, scenario_names,
)

DEFAULT_POLICY = CASE_DIR / "acceptance.yaml"
DEFAULT_CONFIG = CASE_DIR / "config.yaml"
RESULTS_ROOT = CASE_DIR / "results"

CONTROL = "b0_control"
FACES = ("xlo", "xhi", "ylo", "yhi", "zlo", "zhi")


def delta_suffix(scenario: str) -> str:
    """transverse_1x -> 1x (the label of the cross-scenario delta metrics)."""
    return scenario.replace("transverse_", "")


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
    """Linear-fit slope of phi_body over the last `window_s` [V/s]."""
    t = np.atleast_1d(d["t"])
    phi = np.atleast_1d(d["phi_body"])
    m = t >= (t[-1] - window_s)
    if m.sum() < 3:
        return float("nan")
    return float(np.polyfit(t[m], phi[m], 1)[0])


def csv_charge(d, col: str, dt: float) -> float:
    """Reconstruct the cumulative charge [C] behind a CSV current column."""
    steps = np.atleast_1d(d["step"]).astype(float)
    I = np.atleast_1d(d[col])
    wins = np.diff(np.concatenate([[0.0], steps])) * dt
    return float(np.nansum(I * wins))


def field_iterations(diags: Path) -> list[int]:
    import openpmd_api as io
    series = io.Series(os.path.join(str(diags), "fields", "openpmd_%T.h5"),
                       io.Access.read_only)
    its = sorted(int(i) for i in series.iterations)
    series.close()
    return its


def read_field_xyz(diags: Path, field: str, iteration: int):
    """A nodal scalar mesh as F[x, y, z] with its node coordinates, whatever
    axis order the file stores (openPMD axis labels decide)."""
    import openpmd_api as io
    series = io.Series(os.path.join(str(diags), "fields", "openpmd_%T.h5"),
                       io.Access.read_only)
    mesh = series.iterations[iteration].meshes[field]
    rc = mesh[io.Mesh_Record_Component.SCALAR]
    chunk = rc.load_chunk()
    series.flush()
    arr = np.asarray(chunk) * rc.unit_SI
    labels = [str(a) for a in mesh.axis_labels]
    spacing = np.asarray(mesh.grid_spacing, dtype=float) * mesh.grid_unit_SI
    offset = np.asarray(mesh.grid_global_offset, dtype=float) * mesh.grid_unit_SI
    pos = np.asarray(rc.position, dtype=float)
    coords = {}
    for k, lab in enumerate(labels):
        n = arr.shape[k]
        coords[lab] = offset[k] + (np.arange(n) + pos[k]) * spacing[k]
    series.close()
    perm = [labels.index(a) for a in ("x", "y", "z")]
    return np.transpose(arr, perm), coords["x"], coords["y"], coords["z"]


def edge_phi(phi, inset: int = 3) -> float:
    """Max |phi| a few nodes inside the six open faces (containment)."""
    p = np.abs(phi)
    return float(max(p[inset, :, :].max(), p[-1 - inset, :, :].max(),
                     p[:, inset, :].max(), p[:, -1 - inset, :].max(),
                     p[:, :, inset].max(), p[:, :, -1 - inset].max()))


def phi_on_axis(phi, x, y, z, z_probe: float) -> float:
    """phi at (0, 0, z_probe): nearest transverse node column, linear in z."""
    ix = int(np.argmin(np.abs(x)))
    iy = int(np.argmin(np.abs(y)))
    return float(np.interp(z_probe, z, phi[ix, iy, :]))


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


def read_calibration(diags: Path) -> dict:
    path = diags / "calibration.json"
    if not path.exists():
        raise lc.ContractError(f"no {path} in the run evidence")
    return lc.read_json_strict(path)


def reduced_momentum(diags: Path):
    """The ParticleMomentum reduced diagnostic: (t, {species: (Px, Py, Pz)})."""
    path = diags / "reducedfiles" / "particle_momentum.txt"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        header = fh.readline()
    cols = [c.split("]", 1)[1].split("(")[0] for c in header.lstrip("#").split()]
    data = np.atleast_2d(np.loadtxt(path))
    if data.size == 0:
        return None
    t = data[:, cols.index("time")]
    out = {}
    for name in (BEAM, AMB_E, AMB_I):
        keys = [f"{name}_x", f"{name}_y", f"{name}_z"]
        if all(k in cols for k in keys):
            out[name] = tuple(data[:, cols.index(k)] for k in keys)
    return t, out


# ======================================================================
# per-scenario metrics
# ======================================================================

def scenario_metrics(cfg: Config, evidence: lc.LoadedRun, tail_frac: float):
    """All measured quantities for one scenario run (values, not Metrics)."""
    diags = evidence.diags_dir
    d = load_ledger(diags)
    n_rows = len(np.atleast_1d(d["t"]))
    i0 = max(0, int(n_rows * (1.0 - tail_frac)))
    window = {"start_iteration": int(np.atleast_1d(d["step"])[i0]),
              "end_iteration": int(np.atleast_1d(d["step"])[-1])}
    s = {k: steady(d, k, tail_frac) for k in
         ("phi_body", "pct_escape", "pct_body", "pct_inflight", "I_emit",
          "I_body", "I_escape", "I_amb_e", "I_amb_i", "F_beam_N", "F_beam_y_N",
          "F_net_N", "F_lorentz_z_N", "F_lorentz_y_N", "F_lorentz_beam_z_N",
          "F_thrust_N", "beam_escape_KE_mean")}

    m: dict[str, tuple] = {}   # id -> (value, unit, source)
    m["escape_fraction_pct"] = (s["pct_escape"], "%",
                                "contactor_log.csv pct_escape (cumulative beam fate), tail mean")
    m["f_beam_nN"] = (s["F_beam_N"] * 1e9, "nN",
                      "contactor_log.csv F_beam_N (escaped-beam z-momentum flux, the anchor readout)")
    m["f_thrust_nN"] = (s["F_thrust_N"] * 1e9, "nN",
                        "contactor_log.csv F_thrust_N = F_beam - F_lorentz_z (momentum-conservation thrust on the body)")
    m["f_lorentz_z_nN"] = (s["F_lorentz_z_N"] * 1e9, "nN",
                           "contactor_log.csv F_lorentz_z_N (q v x B on all in-box particles, z)")
    m["f_lorentz_beam_z_nN"] = (s["F_lorentz_beam_z_N"] * 1e9, "nN",
                                "contactor_log.csv F_lorentz_beam_z_N (beam-only Lorentz term)")
    corr = ((s["F_thrust_N"] / s["F_beam_N"] - 1.0) * 100.0
            if s["F_beam_N"] else float("nan"))
    m["lorentz_correction_pct"] = (corr, "%",
                                   "(F_thrust / F_beam - 1) x 100: what the exit flux alone misses")
    m["phi_body_V"] = (s["phi_body"], "V", "contactor_log.csv phi_body, tail mean")
    net_amb = s["I_amb_e"] - s["I_amb_i"]
    balance = (abs(s["I_escape"] - net_amb) / abs(s["I_escape"])
               if s["I_escape"] else float("nan"))
    m["current_balance"] = (balance, "-",
                            "|I_escape - (I_amb_e - I_amb_i)| / I_escape, tail means")
    fn_over_fb = (abs(s["F_net_N"]) / abs(s["F_beam_N"])
                  if s["F_beam_N"] else float("nan"))
    m["f_net_over_f_beam"] = (fn_over_fb, "-", "|F_net| / |F_beam| momentum sanity bound")
    m["emitted_current_ratio"] = (s["I_emit"] / cfg.i_beam, "-",
                                  "contactor_log.csv I_emit tail mean / beam.i_beam (source fidelity)")

    # containment + injection-plane potential from the tail field dumps
    its = field_iterations(diags)
    tail = [i for i in its if i >= its[-1] * (1.0 - tail_frac)] or its[-1:]
    phi_axis = []
    for it in tail:
        phi, x, y, z = read_field_xyz(diags, "phi", it)
        phi_axis.append(phi_on_axis(phi, x, y, z, cfg.geometry().z_emit))
    edge = edge_phi(phi)                       # the last dump
    m["edge_phi_max_V"] = (edge, "V",
                           "max |phi| three nodes inside the six open faces, last dump")
    m["phi_inject_axis_V"] = (float(np.mean(phi_axis)), "V",
                              "phi at the source plane on axis, tail field dumps (REPORTED)")
    m["ke_predicted_eV"] = (cfg.ke_inject_eV - float(np.mean(phi_axis)), "eV",
                            "ke_inject_eV - phi(source plane): the exhaust energy the sheath returns (REPORTED)")

    # ledger-vs-dump charge consistency (the anchor's G5 gates)
    totals = scraped_weight_totals(diags)
    q_pmd = E * totals.get((AMB_E, "eb"), 0.0)
    q_csv = csv_charge(d, "I_amb_e", cfg.dt)
    consistency = (abs(q_csv - q_pmd) / q_pmd) if q_pmd > 0 else float("nan")
    m["scrape_charge_consistency"] = (consistency, "-",
                                      "ambient-e EB charge: CSV ledger integral vs openPMD scrape total")
    q_pmd_beam = E * sum(totals.get((BEAM, b), 0.0) for b in FACES)
    q_csv_beam = csv_charge(d, "I_escape", cfg.dt)
    beam_consistency = (abs(q_csv_beam - q_pmd_beam) / q_pmd_beam
                        if q_pmd_beam > 0 else float("nan"))
    m["scrape_charge_consistency_beam_escape"] = (
        beam_consistency, "-",
        "beam-escape charge: CSV ledger I_escape integral vs openPMD six-face scrape total")

    # capacitance calibration (the Gauss-law measurement the float rides on)
    calib = read_calibration(diags)
    m["c_float_pF"] = (float(calib["C_float_F"]) * 1e12, "pF",
                       "calibration.json C_float (Gauss law on the box faces at the 1 V init solve)")

    # reported-only honesty lines
    m["exhaust_ke_mean_eV"] = (s["beam_escape_KE_mean"], "eV",
                               "contactor_log.csv beam_escape_KE_mean (REPORTED, not gated)")
    m["late_dphidt_V_per_ns"] = (late_slope(d) * 1e-9, "V/ns",
                                 "phi_body linear slope over the last 50 ns (REPORTED: finite-time equilibrium)")

    # Lorentz ledger vs the ParticleMomentum reduced diagnostic (independent
    # samples of the same in-box momentum), magnetized scenarios only
    lorentz_check = None
    if cfg.Bx_T is not None:
        red = reduced_momentum(diags)
        if red is not None:
            t_red, P = red
            charges = {BEAM: -E, AMB_E: -E, AMB_I: E}
            masses = {BEAM: ME, AMB_E: ME, AMB_I: cfg.m_ion}
            fz = np.zeros_like(t_red)
            for name, (px, py, pz) in P.items():
                fz += -charges[name] * cfg.Bx_T * py / masses[name]
            t_led = np.atleast_1d(d["t"])
            mask_red = t_red >= t_led[i0]
            if mask_red.sum() >= 3 and s["F_lorentz_z_N"]:
                lorentz_check = (abs(float(fz[mask_red].mean()) - s["F_lorentz_z_N"])
                                 / abs(s["F_lorentz_z_N"]))
    if lorentz_check is not None:
        m["lorentz_reduced_consistency"] = (
            lorentz_check, "-",
            "|<F_lorentz_z> reduced-diag samples - ledger| / |ledger|, tail (REPORTED)")

    extra = dict(d=d, s=s, window=window, n_tail=n_rows - i0, totals=totals,
                 q_csv=q_csv, q_pmd=q_pmd, q_csv_beam=q_csv_beam,
                 q_pmd_beam=q_pmd_beam, phi_axis=phi_axis, calib=calib)
    return m, extra


def cross_metrics(per: dict[str, dict]) -> dict[str, tuple]:
    """Deltas of every magnetized scenario against the unmagnetized control."""
    out: dict[str, tuple] = {}
    ctrl = per.get(CONTROL)
    if ctrl is None:
        return out
    for scn, m in per.items():
        if scn == CONTROL:
            continue
        sfx = delta_suffix(scn)
        out[f"dphi_{sfx}_V"] = (m["phi_body_V"][0] - ctrl["phi_body_V"][0], "V",
                                f"phi_body({scn}) - phi_body({CONTROL}), tail means")
        f0 = ctrl["f_thrust_nN"][0]
        out[f"dthrust_{sfx}_pct"] = (
            ((m["f_thrust_nN"][0] / f0 - 1.0) * 100.0) if f0 else float("nan"), "%",
            f"(F_thrust({scn}) / F_thrust({CONTROL}) - 1) x 100")
        out[f"descape_{sfx}_pp"] = (
            m["escape_fraction_pct"][0] - ctrl["escape_fraction_pct"][0], "pp",
            f"escape({scn}) - escape({CONTROL}), percentage points")
    return out


def build_metrics(per: dict[str, dict], per_window: dict[str, dict]) -> dict[str, lc.Metric]:
    metrics: dict[str, lc.Metric] = {}
    for scn, m in per.items():
        for mid, (value, unit, source) in m.items():
            key = f"{scn}__{mid}"
            metrics[key] = lc.Metric.measure(key, value, unit, source=source,
                                             window=per_window.get(scn))
    for mid, (value, unit, source) in cross_metrics(per).items():
        metrics[mid] = lc.Metric.measure(mid, value, unit, source=source)
    return metrics


# ======================================================================
# figures
# ======================================================================

def write_figures(analysis, cfgs: dict, extras: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figs = analysis.figures_dir
    for scn, ex in extras.items():
        d = ex["d"]
        t_ns = np.atleast_1d(d["t"]) * 1e9
        t_on_ns = cfgs[scn].t_on * 1e9

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(t_ns, d["pct_escape"], label="% escaped (thrust)", color="tab:green", lw=2)
        ax.plot(t_ns, d["pct_body"], label="% back on body", color="tab:orange")
        ax.plot(t_ns, d["pct_inflight"], label="% in flight", color="tab:gray", ls=":")
        ax.axvline(t_on_ns, color="k", ls="--", lw=0.8, label=f"gun on ({t_on_ns:.0f} ns)")
        ax.set_xlabel("time [ns]"); ax.set_ylabel("cumulative fraction of emitted beam [%]")
        ax.set_title(f"{scn}: fate of the emitted electrons"); ax.set_ylim(-2, 102)
        ax.legend(loc="center right"); ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(figs / f"{scn}_fates_vs_time.png", dpi=130)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(t_ns, d["I_escape"] * 1e3, label="I_escape (beam leaves the box)")
        ax.plot(t_ns, d["I_emit"] * 1e3, label="I_emit (source)", ls="--")
        ax.plot(t_ns, d["I_body"] * 1e3, label="I_body (beam back on body)")
        ax.plot(t_ns, d["I_amb_e"] * 1e3, label="I_amb_e (ambient e- collected)", ls=":")
        ax.plot(t_ns, d["I_amb_i"] * 1e3, label="I_amb_i (ambient ions collected)", ls=":")
        ax.axvline(t_on_ns, color="k", ls="--", lw=0.8)
        ax.set_xlabel("time [ns]"); ax.set_ylabel("current [mA]")
        ax.set_title(f"{scn}: per-channel currents"); ax.legend(); ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(figs / f"{scn}_currents_vs_time.png", dpi=130)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(t_ns, d["F_beam_N"] * 1e9, color="tab:green", label="F_beam (exit flux)")
        ax.plot(t_ns, d["F_thrust_N"] * 1e9, color="tab:blue", label="F_thrust = F_beam - F_L,z")
        ax.plot(t_ns, d["F_lorentz_z_N"] * 1e9, color="tab:purple", label="F_L,z (Lorentz, in-box)")
        ax.plot(t_ns, d["F_net_N"] * 1e9, color="tab:red", alpha=0.7, label="F_net (body impacts)")
        ax.axvline(t_on_ns, color="k", ls="--", lw=0.8); ax.axhline(0, color="k", lw=0.5)
        ax.set_xlabel("time [ns]"); ax.set_ylabel("force [nN]")
        ax.set_title(f"{scn}: thrust ledger"); ax.legend(loc="upper left"); ax.grid(alpha=0.3)
        ax2 = ax.twinx()
        ax2.plot(t_ns, d["beam_escape_KE_mean"], color="tab:brown", alpha=0.5)
        ax2.set_ylabel("mean escaped-beam KE [eV]", color="tab:brown")
        fig.tight_layout(); fig.savefig(figs / f"{scn}_thrust_vs_time.png", dpi=130)
        plt.close(fig)

    # cohort overlays
    for col, ylabel, fname in (("phi_body", "phi_body [V]", "phi_overlay.png"),
                               ("F_thrust_N", "F_thrust [nN]", "thrust_overlay.png")):
        fig, ax = plt.subplots(figsize=(8, 5))
        for scn, ex in extras.items():
            d = ex["d"]
            scale = 1e9 if col.endswith("_N") else 1.0
            ax.plot(np.atleast_1d(d["t"]) * 1e9, d[col] * scale, label=scn)
        ax.set_xlabel("time [ns]"); ax.set_ylabel(ylabel); ax.grid(alpha=0.3)
        ax.legend(); ax.set_title("transverse-B cohort")
        fig.tight_layout(); fig.savefig(figs / fname, dpi=130)
        plt.close(fig)


# ======================================================================
# driver
# ======================================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="transverse-B cohort analysis")
    ap.add_argument("--runs", type=Path, nargs="+", required=True,
                    help="COMPLETE run directories (one per scenario; all three "
                         "for a verdict, any subset for a look)")
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                    help="source study (for the canonical scenario order)")
    ap.add_argument("--tail-frac", type=float, default=0.2,
                    help="fraction of the record treated as the plateau")
    return ap.parse_args(argv)


def _print_summary(verdict: lc.Verdict, per: dict, extras: dict) -> None:
    print("\n" + "=" * 72)
    print("STEADY-STATE SUMMARY (reported)")
    for scn, m in per.items():
        ex = extras[scn]
        print(f"  [{scn}] phi={m['phi_body_V'][0]:.2f} V  F_beam={m['f_beam_nN'][0]:.3f} nN  "
              f"F_thrust={m['f_thrust_nN'][0]:.3f} nN  F_L,z={m['f_lorentz_z_nN'][0]:+.4f} nN  "
              f"escape={m['escape_fraction_pct'][0]:.2f}%  C={m['c_float_pF'][0]:.3f} pF  "
              f"KE_exh={m['exhaust_ke_mean_eV'][0]:.1f} eV (pred {m['ke_predicted_eV'][0]:.1f})")
        print(f"      ledger-vs-dump ambient-e: CSV {ex['q_csv']:.4e} C vs openPMD {ex['q_pmd']:.4e} C; "
              f"beam-escape: CSV {ex['q_csv_beam']:.4e} C vs openPMD {ex['q_pmd_beam']:.4e} C")
    for mid, (value, unit, _) in cross_metrics(per).items():
        print(f"  {mid} = {value:+.3f} {unit}")
    print("=" * 72)
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
            raise lc.ContractError(
                f"policy stage {policy.stage_id} != expected {STAGE_ID}")
    except lc.ContractError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return lc.EXIT_ERROR

    analysis = lc.begin_analysis(cohort, policy, results_root=RESULTS_ROOT,
                                 analyzer_source=__file__)
    print(f"ANALYSIS_ID={analysis.analysis_id}", flush=True)
    try:
        per, extras, windows = {}, {}, {}
        for r in cohort:
            m, ex = scenario_metrics(cfgs[r.scenario], r, args.tail_frac)
            per[r.scenario], extras[r.scenario] = m, ex
            windows[r.scenario] = ex["window"]
        metrics = build_metrics(per, windows)
        verdict = lc.evaluate_gates(metrics, policy)
        lc.write_metrics(analysis, metrics)
        lc.write_verdict(analysis, verdict)
        write_figures(analysis, cfgs, extras)
        lc.complete_analysis(analysis, verdict)
        _print_summary(verdict, per, extras)
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
