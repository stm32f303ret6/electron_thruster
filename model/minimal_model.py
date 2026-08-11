#!/usr/bin/env python3
"""
minimal_model.py -- the executable form of SCALING_LAWS.md (one file, per its §9)

WHAT THIS IS
  The measured three-point voltage frontier (capstone 100/200/300 V, all gates
  PASS) turned into a predictive tool:

      inputs   : plasma density n_e, electron temperature Te (per orbit-CSV row)
                 and the thrust demand F_req (the drag column)
      controls : V (supply), I (beam current) -- chosen per row by the §7b
                 flight rule (a two-line servo on the floating potential)
      outputs  : operating point (V, I, phi, KE), power P = I*V, F/P,
                 feasibility + envelope flags per row, mission-level summaries

WHAT THIS IS NOT (the §9 contract)
  - It never feeds an acceptance gate: PIC stages stay self-contained; this is
    a targeting/analysis tool with no authority over evidence.
  - Fitted constants stay home; physics forms travel. Every constant below is
    derived at import time from the committed metrics.json files, with fit
    residuals printed, not hidden.
  - Every row outside the measured envelope (density, chi, perveance) is
    flagged: mission claims split into "measured-envelope rows" and
    "extrapolated rows, needing a targeted PIC run".

LAWS (SCALING_LAWS.md sections in brackets)
  thrust   [1] : F[nN] = c_F * I[mA] * sqrt(KE[eV]),  KE = kappa_KE*(V - phi)
  emission [3] : I_CL = K_CL * V^1.5 (planar scale), real ceiling = r_emit*I_CL
  float    [4] : I_esc = betaA * j_the(n,Te) * (1 + chi)^alpha,  chi = e*phi/kTe
                 j_the = e * n * sqrt(kTe / 2*pi*m_e)   [A/m^2, one-sided flux]
  control  [7b]: V = CTRL_FACTOR*phi (clamped to hardware [100,300] V and to
                 the emission-feasibility floor); I from the thrust demand;
                 guards I <= r_emit*I_CL(V) and phi <= 50 V.
                 CTRL_FACTOR = (2*alpha+1)/alpha evaluated from the fitted
                 alpha -- physics, not tuning.

USAGE
  python minimal_model.py --calibrate            # constants + residuals table
  python minimal_model.py --mission PATH.csv     # sweep one orbit CSV
  python minimal_model.py --all                  # sweep every station_keeping.csv
  Options: --out DIR (default model/results), --alpha-settled (sensitivity fit)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------
# Physical constants (SI)
# ----------------------------------------------------------------------
QE = 1.602176634e-19      # C
ME = 9.1093837015e-31     # kg
KB = 1.380649e-23         # J/K
EPS0 = 8.8541878128e-12   # F/m
K_PER_EV = QE / KB        # 11604.5 K per eV

REPO = Path(__file__).resolve().parent.parent
CAPSTONE = REPO / "pic_sims" / "ladder" / "capstone"
CHARACTERIZATION = REPO / "pic_sims" / "thruster_characterization"

# ----------------------------------------------------------------------
# Measured anchors -- the three committed frontier runs (provenance pinned).
# V and i_beam are read from each stage's frozen config; physics metrics from
# the committed metrics.json of the gated PASS analysis.
# ----------------------------------------------------------------------
ANCHORS = [
    dict(stage="capstone.low_power",
         config=CHARACTERIZATION / "low_power" / "config.yaml",
         metrics=CHARACTERIZATION / "low_power" / "reference_results"
                 / "20260804T230218Z_0adb478f" / "metrics.json",
         phi_settled_V=6.0),   # late-slope extrapolation (sensitivity band)
    dict(stage="capstone.floating_body",
         config=CAPSTONE / "2_chipsat_thruster" / "config.yaml",
         metrics=CAPSTONE / "2_chipsat_thruster" / "reference_results"
                 / "20260801T142601Z_2f822a95" / "metrics.json",
         phi_settled_V=18.5),
    dict(stage="capstone.high_thrust",
         config=CHARACTERIZATION / "high_thrust" / "config.yaml",
         metrics=CHARACTERIZATION / "high_thrust" / "reference_results"
                 / "20260804T154756Z_b854dcbe" / "metrics.json",
         phi_settled_V=45.0),
]

# Emission geometry (frozen in every capstone config: r_spot 0.5 mm, gap 4.7 mm)
EMIT_GAP_M = 4.7e-3
EMIT_R_M = 0.5e-3
# Measured non-planar emission ratio (SCALING_LAWS §3; held by all three stages)
R_EMIT = 1.46

# Design/hardware limits
V_HW = (100.0, 300.0)     # cathode supply range [V]
PHI_BENIGN_V = 50.0       # benign-float design limit (acceptance-gated)
PHI_CHOKE_V = 100.0       # choke ceiling (run-abort threshold in PIC)

# Measured-envelope band on the collection side: the committed runs share ONE
# plasma row; rows whose n*sqrt(Te) departs more than this factor extrapolate
# the collection law on its theory-only axis (SCALING_LAWS §8).
DENSITY_BAND = (0.7, 1.3)


def _scalar(pattern: str, text: str, path: Path) -> float:
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        raise ValueError(f"pattern {pattern!r} not found in {path}")
    return float(m.group(1))


def _load_anchor(a: dict) -> dict:
    cfg_path = a.get("config_override", a["config"])
    cfg = Path(cfg_path).read_text()
    met = json.loads(Path(a["metrics"]).read_text())
    vals = {m["id"]: m["value"] for m in met["metrics"]}
    V = abs(_scalar(r"^\s*cathode_offset:\s*(-?[0-9.eE+-]+)", cfg, cfg_path))
    return dict(
        stage=a["stage"],
        V=V,
        I_mA=_scalar(r"^\s*i_beam:\s*([0-9.eE+-]+)", cfg, cfg_path) * 1e3,
        n0=_scalar(r"^\s*n0:\s*([0-9.eE+-]+)", cfg, cfg_path),
        Te_K=_scalar(r"^\s*Te_K:\s*([0-9.eE+-]+)", cfg, cfg_path),
        phi_V=vals["phi_body_V"],
        phi_settled_V=a["phi_settled_V"],
        F_nN=vals["f_beam_nN"],
        esc=vals["escape_fraction_pct"] / 100.0,
        KE_eV=vals["exhaust_ke_mean_eV"],
        provenance=str(Path(a["metrics"]).relative_to(REPO)),
    )


def j_the(n_m3, Te_K):
    """One-sided thermal electron flux density [A/m^2] (SCALING_LAWS §4)."""
    return QE * n_m3 * np.sqrt(KB * Te_K / (2.0 * math.pi * ME))


def i_cl_mA(V):
    """Planar Child-Langmuir scale over the emission spot [mA] (§3)."""
    k = (4.0 / 9.0) * EPS0 * math.sqrt(2.0 * QE / ME) / EMIT_GAP_M**2
    return k * np.asarray(V, dtype=float)**1.5 * math.pi * EMIT_R_M**2 * 1e3


class Calibration:
    """All law constants, derived from the committed anchors at import time."""

    def __init__(self, use_settled_phi: bool = False):
        self.anchors = [_load_anchor(a) for a in ANCHORS]
        self.use_settled_phi = use_settled_phi
        A = self.anchors

        # Thrust slope c_F and energy fraction kappa_KE (per-anchor, then mean)
        self.cF_each = [a["F_nN"] / (a["I_mA"] * math.sqrt(a["KE_eV"])) for a in A]
        self.cF = float(np.mean(self.cF_each))
        self.kappa_each = [a["KE_eV"] / (a["V"] - a["phi_V"]) for a in A]
        self.kappa = float(np.mean(self.kappa_each))

        # Escape fraction vs V at the measured perveance path (interp inside)
        self.esc_V = np.array([a["V"] for a in A])
        self.esc_f = np.array([a["esc"] for a in A])

        # Collection-law fit: ln(I_esc) = ln(betaA * j_the0) + alpha*ln(1+chi)
        # All anchors share one plasma row -> j_the0 is common.
        self.n0 = A[0]["n0"]
        self.Te0_K = A[0]["Te_K"]
        self.kTe0_eV = self.Te0_K / K_PER_EV
        j0 = float(j_the(self.n0, self.Te0_K))
        phi_key = "phi_settled_V" if use_settled_phi else "phi_V"
        chi = np.array([a[phi_key] / self.kTe0_eV for a in A])
        Iesc = np.array([a["esc"] * a["I_mA"] * 1e-3 for a in A])  # [A]
        x, y = np.log1p(chi), np.log(Iesc)
        self.alpha, b = np.polyfit(x, y, 1)
        self.alpha = float(self.alpha)
        self.betaA = float(math.exp(b) / j0)          # [m^2] effective area
        self.fit_resid_pct = 100.0 * (np.exp(np.polyval([self.alpha, b], x)) - Iesc) / Iesc
        # phi predicted back at each anchor (for the residuals table)
        self.phi_resid = []
        for a, Ie in zip(A, Iesc):
            self.phi_resid.append(self.phi_of_Iesc(Ie, self.n0, self.Te0_K) - a[phi_key])

        # chi range actually measured (envelope on the chi axis)
        self.chi_lo, self.chi_hi = float(chi.min()), float(chi.max())

    # ---- law evaluations -------------------------------------------------
    def phi_of_Iesc(self, Iesc_A, n_m3, Te_K):
        """Invert the collection law for the float [V]. Vector-safe."""
        kTe_eV = np.asarray(Te_K, dtype=float) / K_PER_EV
        ratio = np.asarray(Iesc_A, dtype=float) / (self.betaA * j_the(n_m3, Te_K))
        chi = np.maximum(ratio, 1e-12)**(1.0 / self.alpha) - 1.0
        return np.maximum(chi, 0.0) * kTe_eV

    def esc_of_V(self, V):
        return np.interp(V, self.esc_V, self.esc_f)

    def thrust_nN(self, I_mA, V, phi_V):
        KE = self.kappa * np.maximum(V - phi_V, 1e-6)
        return self.cF * I_mA * np.sqrt(KE)

    def report(self) -> str:
        A = self.anchors
        L = ["CALIBRATION -- derived from committed metrics.json (residuals shown)",
             ""]
        for a in A:
            L.append(f"  anchor {a['V']:.0f} V  {a['I_mA']:.3f} mA  "
                     f"phi={a['phi_V']:.2f} V  F={a['F_nN']:.2f} nN  "
                     f"esc={100*a['esc']:.2f} %  KE={a['KE_eV']:.1f} eV")
            L.append(f"    <- {a['provenance']}")
        phi_used = "settled-extrapolated" if self.use_settled_phi else "tail-averaged (policy)"
        L += ["",
              f"  thrust slope   c_F      = {self.cF:.4f} nN/(mA*sqrt(eV))  "
              f"(per-anchor {', '.join(f'{c:.4f}' for c in self.cF_each)}; ideal 3.372)",
              f"  energy fraction kappa_KE = {self.kappa:.4f}              "
              f"(per-anchor {', '.join(f'{k:.4f}' for k in self.kappa_each)})",
              f"  collection law (phi input: {phi_used}):",
              f"    alpha  = {self.alpha:.4f}   (pre-registered winner 0.82 +/- 0.06)",
              f"    beta*A = {self.betaA*1e4:.3f} cm^2  (geometric can ~3.3 cm^2 -> beta~{self.betaA/3.3e-4:.2f})",
              f"    current residuals at anchors: "
              f"{', '.join(f'{r:+.1f} %' for r in self.fit_resid_pct)}",
              f"    phi residuals (model - measured): "
              f"{', '.join(f'{r:+.2f} V' for r in self.phi_resid)}",
              f"  emission scale I_CL = {i_cl_mA(1.0)*1e0:.4g} mA * V^1.5;  "
              f"at 100/200/300 V: "
              f"{i_cl_mA(100):.3f} / {i_cl_mA(200):.3f} / {i_cl_mA(300):.3f} mA "
              f"(quoted 0.083 / 0.235 / 0.431); ceiling = {R_EMIT} * I_CL",
              f"  measured chi range: {self.chi_lo:.0f} - {self.chi_hi:.0f}",
              f"  plasma anchor row: n = {self.n0:.3e} m^-3, Te = {self.Te0_K:.1f} K "
              f"(collection-side envelope band {DENSITY_BAND[0]}-{DENSITY_BAND[1]}x on n*sqrt(Te))",
              ]
        return "\n".join(L)


# ----------------------------------------------------------------------
# Per-row operating point: the flight rule, solved self-consistently
# ----------------------------------------------------------------------
def operating_point(cal: Calibration, F_req_nN, n_m3, Te_K,
                    iters: int = 200, damp: float = 0.35):
    """
    Simple power-law operating point: find the minimum voltage that
    satisfies the emission ceiling, then self-consistently solve for phi.

    Returns dict of arrays: V, I_mA, phi_V, KE_eV, F_nN, P_mW, flags...
    """
    F = np.asarray(F_req_nN, dtype=float) * 1.0
    n = np.asarray(n_m3, dtype=float)
    Te = np.asarray(Te_K, dtype=float)

    c_eff = cal.cF * math.sqrt(cal.kappa)
    K_CL = float(i_cl_mA(1.0))
    A_coeff = c_eff * R_EMIT * K_CL
    V_min = np.sqrt(F / A_coeff)
    V = np.clip(V_min, V_HW[0], V_HW[1])

    phi = np.full_like(F, 5.0)
    for _ in range(iters):
        I = F / (cal.cF * np.sqrt(cal.kappa * np.maximum(V - phi, 1.0)))
        over = I > R_EMIT * i_cl_mA(V)
        if np.any(over):
            V[over] = np.minimum(V[over] * 1.05, V_HW[1])
            I = F / (cal.cF * np.sqrt(cal.kappa * np.maximum(V - phi, 1.0)))
        infeasible = I > R_EMIT * i_cl_mA(V) * 1.0001
        I_run = np.minimum(I, R_EMIT * i_cl_mA(V))
        phi_new = cal.phi_of_Iesc(cal.esc_of_V(V) * I_run * 1e-3, n, Te)
        step = phi_new - phi
        phi = phi + damp * step
        if np.max(np.abs(step)) < 1e-4:
            break

    esc = cal.esc_of_V(V)
    KE = cal.kappa * np.maximum(V - phi, 0.0)
    F_out = cal.thrust_nN(I_run, V, phi)
    P_mW = I_run * V * 1e-3 * 1e3
    chi = phi / (Te / K_PER_EV)
    nsq = n * np.sqrt(Te) / (cal.n0 * math.sqrt(cal.Te0_K))

    flags = dict(
        infeasible_emission=infeasible,
        phi_over_benign=phi > PHI_BENIGN_V,
        choke_region=phi > PHI_CHOKE_V,
        extrap_chi=(chi < cal.chi_lo) | (chi > cal.chi_hi),
        extrap_density=(nsq < DENSITY_BAND[0]) | (nsq > DENSITY_BAND[1]),
    )
    flags["in_envelope"] = ~(flags["infeasible_emission"] | flags["phi_over_benign"]
                             | flags["extrap_chi"] | flags["extrap_density"])
    return dict(V=V, I_mA=I_run, phi_V=phi, KE_eV=KE, esc=esc,
                F_nN=F_out, F_req_nN=F, P_mW=P_mW, flags=flags)


def capability_nN(cal: Calibration, n_m3, Te_K):
    """Max benign thrust per row: V=300 V, I at min(emission ceiling,
    collection limit at phi=50 V). Used for duty-cycle closure."""
    n = np.asarray(n_m3, dtype=float)
    Te = np.asarray(Te_K, dtype=float)
    kTe_eV = Te / K_PER_EV
    V = V_HW[1]
    esc = float(cal.esc_of_V(V))
    I_cl_cap = R_EMIT * i_cl_mA(V)                          # mA
    Iesc_phi50 = cal.betaA * j_the(n, Te) * (1.0 + PHI_BENIGN_V / kTe_eV)**cal.alpha
    I_cap = np.minimum(I_cl_cap, Iesc_phi50 / esc * 1e3)    # mA
    phi = cal.phi_of_Iesc(esc * I_cap * 1e-3, n, Te)
    return cal.thrust_nN(I_cap, V, phi), I_cap * V * 1.0    # nN, mW


# ----------------------------------------------------------------------
# Mission sweep
# ----------------------------------------------------------------------
def sweep_mission(cal: Calibration, csv_path: Path, out_dir: Path) -> dict:
    name = csv_path.parent.parent.name
    cols = dict(t=[], n=[], Te=[], F=[])
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            cols["t"].append(row["timestamp_utc"])
            cols["n"].append(float(row["electron_density_m3"]))
            cols["Te"].append(float(row["electron_temperature_K"]))
            cols["F"].append(float(row["drag_N"]) * 1e9)
    n = np.array(cols["n"]); Te = np.array(cols["Te"]); F = np.array(cols["F"])

    op = operating_point(cal, F, n, Te)
    fl = op["flags"]
    F_cap, P_cap = capability_nN(cal, n, Te)
    feas = ~fl["infeasible_emission"] & ~fl["phi_over_benign"]

    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"{name}_model.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "n_e_m3", "Te_K", "F_req_nN", "V_V",
                    "I_mA", "phi_V", "KE_eV", "P_mW", "F_over_P_uN_per_W",
                    "F_capability_nN", "feasible", "in_envelope",
                    "extrap_density", "extrap_chi", "phi_over_benign",
                    "infeasible_emission"])
        for i in range(len(F)):
            w.writerow([cols["t"][i], f"{n[i]:.4e}", f"{Te[i]:.1f}",
                        f"{F[i]:.4f}", f"{op['V'][i]:.2f}", f"{op['I_mA'][i]:.5f}",
                        f"{op['phi_V'][i]:.3f}", f"{op['KE_eV'][i]:.2f}",
                        f"{op['P_mW'][i]:.4f}",
                        f"{op['F_nN'][i]/op['P_mW'][i]:.4f}" if op['P_mW'][i] > 0 else "",
                        f"{F_cap[i]:.3f}",
                        int(feas[i]), int(fl['in_envelope'][i]),
                        int(fl['extrap_density'][i]), int(fl['extrap_chi'][i]),
                        int(fl['phi_over_benign'][i]),
                        int(fl['infeasible_emission'][i])])

    s = dict(
        mission=name, rows=len(F),
        drag_mean_nN=float(F.mean()), drag_max_nN=float(F.max()),
        feasible_pct=100.0 * float(feas.mean()),
        in_envelope_pct=100.0 * float(fl["in_envelope"].mean()),
        extrap_density_pct=100.0 * float(fl["extrap_density"].mean()),
        extrap_chi_pct=100.0 * float(fl["extrap_chi"].mean()),
        phi_over_benign_pct=100.0 * float(fl["phi_over_benign"].mean()),
        infeasible_emission_pct=100.0 * float(fl["infeasible_emission"].mean()),
        P_mean_mW=float(op["P_mW"][feas].mean()) if feas.any() else float("nan"),
        P_max_mW=float(op["P_mW"][feas].max()) if feas.any() else float("nan"),
        phi_mean_V=float(op["phi_V"].mean()), phi_max_V=float(op["phi_V"].max()),
        V_mean=float(op["V"][feas].mean()) if feas.any() else float("nan"),
        duty_cycle_needed_pct=100.0 * float(F.mean() / F_cap.mean()),
        closure=float(F_cap.mean() / F.mean()),
        out_csv=str(out_csv.relative_to(REPO)),
    )
    return s


def summary_markdown(cal: Calibration, sums: list[dict]) -> str:
    L = ["| mission | drag mean/max (nN) | feasible % | in-envelope % | "
         "duty cycle needed | P mean/max (mW) | phi mean/max (V) |",
         "|---|---|---|---|---|---|---|"]
    for s in sums:
        L.append(f"| {s['mission']} | {s['drag_mean_nN']:.1f} / {s['drag_max_nN']:.1f} "
                 f"| {s['feasible_pct']:.1f} | {s['in_envelope_pct']:.1f} "
                 f"| {s['duty_cycle_needed_pct']:.0f} % "
                 f"| {s['P_mean_mW']:.1f} / {s['P_max_mW']:.1f} "
                 f"| {s['phi_mean_V']:.1f} / {s['phi_max_V']:.1f} |")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--mission", type=Path)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--alpha-settled", action="store_true",
                    help="fit the collection law on settled-extrapolated phi "
                         "instead of the tail-averaged policy values")
    ap.add_argument("--out", type=Path, default=REPO / "model" / "results")
    args = ap.parse_args(argv)

    cal = Calibration(use_settled_phi=args.alpha_settled)
    print(cal.report())

    paths = []
    if args.mission:
        paths = [args.mission]
    elif args.all:
        paths = sorted((REPO / "orbit_sims" / "validation_cases")
                       .glob("*/results/station_keeping.csv"))
        if not paths:
            sys.exit("no station_keeping.csv found")
    if not paths:
        return

    sums = []
    for p in paths:
        s = sweep_mission(cal, p, args.out)
        sums.append(s)
        print(f"\nMISSION {s['mission']}  ({s['rows']} rows) -> {s['out_csv']}")
        for k in ("drag_mean_nN", "drag_max_nN", "feasible_pct", "in_envelope_pct",
                  "extrap_density_pct", "extrap_chi_pct", "phi_over_benign_pct",
                  "infeasible_emission_pct", "P_mean_mW", "P_max_mW",
                  "phi_mean_V", "phi_max_V", "V_mean", "duty_cycle_needed_pct",
                  "closure"):
            print(f"  {k:26s} = {s[k]:.3f}" if isinstance(s[k], float) else
                  f"  {k:26s} = {s[k]}")

    (args.out / "MISSION_SUMMARY.md").write_text(
        "# Mission sweep -- minimal model output\n\n"
        "Generated by `model/minimal_model.py --all`. See `model/MODEL.md` for\n"
        "laws, calibration provenance, and envelope semantics.\n\n"
        + summary_markdown(cal, sums) + "\n\n"
        + "".join(f"- `{s['out_csv']}`\n" for s in sums))
    with open(args.out / "mission_summary.json", "w") as f:
        json.dump(sums, f, indent=2)
    print(f"\nsummary -> {args.out / 'MISSION_SUMMARY.md'}")


if __name__ == "__main__":
    main()
