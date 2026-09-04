#!/usr/bin/env python3
"""
mission_model.py -- the executable form of paper/SCALING_LAWS.md (one file, per its §9)

WHAT THIS IS
  The measured three-point voltage frontier (capstone 100/200/300 V, all gates
  PASS) turned into a predictive tool:

      inputs   : plasma density n_e, electron temperature Te (per orbit-CSV row)
                 and the thrust demand F_req (the drag column)
      controls : V (supply), I (beam current) -- chosen per row as the
                 minimum-power operating point that delivers the demand
      outputs  : operating point (V, I, phi, KE), power P = I*V, F/P,
                 envelope flags per row, mission-level summaries

WHAT THIS IS NOT (the §9 contract)
  - It never feeds an acceptance gate: PIC stages stay self-contained; this is
    a targeting/analysis tool with no authority over evidence.
  - Fitted constants stay home; physics forms travel. Every constant below is
    derived at import time from the committed metrics.json files, with fit
    residuals printed, not hidden.
  - Every row outside the measured envelope (density, chi, perveance) is
    flagged: mission claims split into "measured-envelope rows" and
    "extrapolated rows, needing a targeted PIC run".

LAWS (paper/SCALING_LAWS.md sections in brackets)
  thrust   [1] : F[nN] = c_F * I[mA] * sqrt(KE[eV]),  KE = kappa_KE*(V - phi)
  emission [3] : I_CL = K_CL * V^1.5 (planar scale), real ceiling = r_emit*I_CL
  float    [4] : I_esc = betaA * j_the(n,Te) * (1 + chi)^alpha,  chi = e*phi/kTe
                 j_the = e * n * sqrt(kTe / 2*pi*m_e)   [A/m^2, one-sided flux]
  closed   [2] : P = F*sqrt(V)/c_eff with c_eff = c_F*sqrt(kappa): the phi << V
                 limit of the thrust law, the one-equation form the paper's
                 theory section states.  --closed-form validates it against the
                 four frontier points and the three fixed-thrust U-curve stages.
  control  [2,7]: per row, V is the supply voltage that MINIMIZES P = V*I
                 subject to (i) the thrust demand, with phi solved
                 self-consistently from the collection law, (ii) the beam
                 keeping energy to leave (V > phi), and (iii) the emission
                 ceiling I <= r_emit*I_CL(V).  SCALING_LAWS §2 puts the
                 untaxed optimum at V = 2*phi; this solves the taxed one
                 numerically on a voltage grid.

  The float is a TAX, never a gate: neither 50 V nor 350 V is a design limit.
  Both were exploration placeholders (2026-08) from before the first runs.
  What the model reports instead is where a row leaves the SIMULATED
  envelope: V above 350 V (gun laws extrapolated), phi above ~100 V (no
  committed run has equilibrated there), n*sqrt(Te) outside the measured
  band (collection law extrapolated).  A supply-voltage cap, if the mission
  has one, is a parameter (--vmax); rows that cannot close under it are
  reported as such, not silently clipped.

USAGE
  python mission_model.py --calibrate            # constants + residuals table
  python mission_model.py --mission PATH.csv     # sweep one orbit CSV
  python mission_model.py --all                  # sweep every station_keeping.csv
  python mission_model.py --closed-form          # phi << V law + validation tables
  Options: --out DIR (default model/results), --alpha-settled (sensitivity fit),
           --vmax V (supply cap; default none), --vcap V (capability voltage
           for the duty-cycle closure; default 350, the tested maximum)
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
CHARACTERIZATION = REPO / "pic_sims" / "characterization"

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

# Envelope markers -- NOT limits.  They say where a row leaves what the PIC
# campaign has measured; the physics laws are evaluated beyond them.
V_FLOOR_V = 100.0         # lowest tested drive; escape collapses below ~100 V in the
                          # can geometry (future_work U-curve), so the search starts here
V_TESTED_MAX_V = 350.0    # top of the tested voltage envelope (350 V measured 2026-08-17)
PHI_SIM_MAX_V = 100.0     # largest float region any committed run equilibrated in
                          # (66.5 V at 800 ns, 3D 10x); the RZ decks abort above 100 V
V_GRID_MAX_V = 6000.0     # search ceiling when no --vmax is given (never binds in 2024)
V_GRID_N = 96             # geometric grid, ~4.4 % steps -> P resolved to < 1 %
KE_MIN_V = 1.0            # the beam must keep at least this much drive to leave [V]

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
# Per-row operating point: minimum power that delivers the demand
# ----------------------------------------------------------------------
def _self_consistent(cal: Calibration, F_nN, V, n_m3, Te_K, esc,
                     iters: int = 80, damp: float = 0.5):
    """(phi, I, converged) at one supply voltage V for every row.

    Fixed point of  I = F / (c_F sqrt(kappa (V - phi)))  and
                    phi = phi_of_Iesc(esc * I).
    A row whose float overtakes the supply (phi -> V) runs away here; that
    is detected by the caller as V - phi < KE_MIN_V, never clamped into a
    fake operating point.
    """
    F = np.asarray(F_nN, dtype=float)
    phi = np.zeros_like(F)
    I = np.zeros_like(F)
    for _ in range(iters):
        dV = np.maximum(V - phi, 1e-3)
        I = F / (cal.cF * np.sqrt(cal.kappa * dV))
        phi_new = np.minimum(cal.phi_of_Iesc(esc * I * 1e-3, n_m3, Te_K), 1e6)
        step = phi_new - phi
        phi = phi + damp * step
    converged = np.abs(step) <= 1e-3 * np.maximum(1.0, np.abs(phi))
    return phi, I, converged


def operating_point(cal: Calibration, F_req_nN, n_m3, Te_K,
                    vmax: float | None = None):
    """Per row: the supply voltage that minimizes P = V*I while delivering
    F_req with a self-consistent float, V - phi >= KE_MIN_V, and
    I <= R_EMIT*I_CL(V).  V is searched on a geometric grid from V_FLOOR_V
    to `vmax` (default V_GRID_MAX_V).  Rows with no admissible V are flagged
    `no_solution` (with a cap, that means "needs more than vmax").

    Returns dict of arrays: V, I_mA, phi_V, KE_eV, esc, F_nN, F_req_nN,
    P_mW, flags.
    """
    F = np.asarray(F_req_nN, dtype=float)
    n = np.asarray(n_m3, dtype=float)
    Te = np.asarray(Te_K, dtype=float)
    R = len(F)
    v_top = V_GRID_MAX_V if vmax is None else float(vmax)
    if v_top <= V_FLOOR_V:
        raise ValueError(f"vmax must exceed the {V_FLOOR_V:g} V floor")
    n_grid = max(8, int(round(V_GRID_N * math.log(v_top / V_FLOOR_V)
                              / math.log(V_GRID_MAX_V / V_FLOOR_V))))
    grid = np.geomspace(V_FLOOR_V, v_top, n_grid)

    best = dict(P=np.full(R, np.inf), V=np.full(R, np.nan),
                phi=np.full(R, np.nan), I=np.full(R, np.nan))
    for V in grid:
        esc = float(cal.esc_of_V(V))
        cap = R_EMIT * float(i_cl_mA(V))
        phi, I, conv = _self_consistent(cal, F, V, n, Te, esc)
        ok = conv & ((V - phi) >= KE_MIN_V) & (I <= cap)
        P = V * I
        upd = ok & (P < best["P"])
        best["P"][upd] = P[upd]
        best["V"][upd] = V
        best["phi"][upd] = phi[upd]
        best["I"][upd] = I[upd]

    no_solution = ~np.isfinite(best["P"])
    V = best["V"]; phi = best["phi"]; I = best["I"]
    esc = cal.esc_of_V(np.where(no_solution, V_FLOOR_V, V))
    KE = cal.kappa * np.maximum(V - phi, 0.0)
    F_out = np.where(no_solution, np.nan, cal.thrust_nN(I, V, phi))
    P_mW = np.where(no_solution, np.nan, best["P"])
    chi = phi / (Te / K_PER_EV)
    nsq = n * np.sqrt(Te) / (cal.n0 * math.sqrt(cal.Te0_K))

    flags = dict(
        no_solution=no_solution,
        extrap_voltage=(V > V_TESTED_MAX_V) & ~no_solution,
        extrap_phi=(phi > PHI_SIM_MAX_V) & ~no_solution,
        extrap_chi=((chi < cal.chi_lo) | (chi > cal.chi_hi)) & ~no_solution,
        extrap_density=(nsq < DENSITY_BAND[0]) | (nsq > DENSITY_BAND[1]),
    )
    flags["in_envelope"] = ~(no_solution | flags["extrap_voltage"]
                             | flags["extrap_phi"] | flags["extrap_chi"]
                             | flags["extrap_density"])
    return dict(V=V, I_mA=I, phi_V=phi, KE_eV=KE, esc=esc,
                F_nN=F_out, F_req_nN=F, P_mW=P_mW, flags=flags, grid=grid)


def capability_nN(cal: Calibration, n_m3, Te_K, V: float = V_TESTED_MAX_V,
                  n_pts: int = 48):
    """Maximum deliverable thrust per row at supply voltage V, and its power.

    Thrust at fixed V rises with current until the float it induces eats the
    drive: F(I) = c_F I sqrt(kappa (V - phi(I))), phi increasing in I.  The
    maximum over I in (0, R_EMIT*I_CL(V)] is found on a grid; no float gate.
    Used for the duty-cycle closure: mean demand / mean capability.
    """
    n = np.asarray(n_m3, dtype=float)
    Te = np.asarray(Te_K, dtype=float)
    esc = float(cal.esc_of_V(V))
    I_cap = R_EMIT * float(i_cl_mA(V))
    best_F = np.zeros_like(n); best_P = np.zeros_like(n)
    for frac in np.geomspace(0.02, 1.0, n_pts):
        I = I_cap * frac
        phi = cal.phi_of_Iesc(esc * I * 1e-3, n, Te)
        F = np.where(V - phi >= KE_MIN_V, cal.thrust_nN(I, V, phi), 0.0)
        upd = F > best_F
        best_F[upd] = F[upd]; best_P[upd] = I * V
    return best_F, best_P


# ----------------------------------------------------------------------
# The closed-form limit (phi << V): the one-equation law of the paper
# ----------------------------------------------------------------------
UCURVE = REPO / "future_work" / "ucurve_pic_stages"
# Committed points the closed-form law is validated against.  The first four
# are the voltage frontier at fixed I/I_CL = 1.46; the last three are the
# fixed-thrust (13.65 nN) U-curve stages where escape collapses below ~100 V.
VALIDATION_POINTS = [
    ("capstone.low_power", CHARACTERIZATION / "low_power" / "config.yaml",
     CHARACTERIZATION / "low_power" / "reference_results"
     / "20260804T230218Z_0adb478f" / "metrics.json"),
    ("capstone.floating_body", CAPSTONE / "2_chipsat_thruster" / "config.yaml",
     CAPSTONE / "2_chipsat_thruster" / "reference_results"
     / "20260801T142601Z_2f822a95" / "metrics.json"),
    ("capstone.high_thrust", CHARACTERIZATION / "high_thrust" / "config.yaml",
     CHARACTERIZATION / "high_thrust" / "reference_results"
     / "20260804T154756Z_b854dcbe" / "metrics.json"),
    ("characterization.350V_400km", CHARACTERIZATION / "350V_400km" / "config.yaml",
     CHARACTERIZATION / "350V_400km" / "reference_results"
     / "20260817T055536Z_acf6cf7b" / "metrics.json"),
    ("ucurve.valley_125V", UCURVE / "5_ucurve_valley" / "config.yaml",
     UCURVE / "5_ucurve_valley" / "reference_results"
     / "20260807T212500Z_3b73998e" / "metrics.json"),
    ("ucurve.left_arm_92V", UCURVE / "6_ucurve_left_arm" / "config.yaml",
     UCURVE / "6_ucurve_left_arm" / "reference_results"
     / "20260808T023756Z_fc7f1ec6" / "metrics.json"),
    ("ucurve.floor_78V", UCURVE / "7_ucurve_floor" / "config.yaml",
     UCURVE / "7_ucurve_floor" / "reference_results"
     / "20260808T070147Z_ea2cf8d9" / "metrics.json"),
]


def _load_point(stage: str, cfg_path: Path, met_path: Path) -> dict:
    cfg = Path(cfg_path).read_text()
    vals = {m["id"]: m["value"] for m in json.loads(Path(met_path).read_text())["metrics"]}
    return dict(stage=stage,
                V=abs(_scalar(r"^\s*cathode_offset:\s*(-?[0-9.eE+-]+)", cfg, cfg_path)),
                I_mA=_scalar(r"^\s*i_beam:\s*([0-9.eE+-]+)", cfg, cfg_path) * 1e3,
                phi_V=vals["phi_body_V"], F_nN=vals["f_beam_nN"],
                esc=vals["escape_fraction_pct"] / 100.0, KE_eV=vals["exhaust_ke_mean_eV"],
                provenance=str(Path(met_path).relative_to(REPO)))


def c_eff(cal: Calibration) -> float:
    """c_F * sqrt(kappa): the constant of the phi << V power law [nN/(mA sqrt(V))]."""
    return cal.cF * math.sqrt(cal.kappa)


def a_ceiling(cal: Calibration) -> float:
    """F_max = A * V^2 on the emission ceiling in the phi << V limit [nN/V^2]."""
    return c_eff(cal) * R_EMIT * float(i_cl_mA(1.0))


def power_closed_form_mW(cal: Calibration, F_nN, V):
    """P = F * sqrt(V) / c_eff: beam power at thrust F and voltage V, phi neglected."""
    return np.asarray(F_nN, dtype=float) * np.sqrt(np.asarray(V, dtype=float)) / c_eff(cal)


def max_thrust_closed_form_nN(cal: Calibration, V):
    return a_ceiling(cal) * np.asarray(V, dtype=float) ** 2


def min_voltage_closed_form(cal: Calibration, F_nN):
    """Lowest voltage whose emission ceiling delivers F, phi neglected [V]."""
    return np.sqrt(np.asarray(F_nN, dtype=float) / a_ceiling(cal))


def thrust_per_watt_closed_form(cal: Calibration, V):
    """F/P = c_eff / sqrt(V) [nN/mW == uN/W]."""
    return c_eff(cal) / np.sqrt(np.asarray(V, dtype=float))


def closed_form_report(cal: Calibration) -> str:
    ce, A = c_eff(cal), a_ceiling(cal)
    pts = [_load_point(*t) for t in VALIDATION_POINTS]
    L = ["# The closed-form limit of the mission model",
         "",
         "Generated by `python model/mission_model.py --closed-form`. The phi << V",
         "limit of the thrust law, with the two constants fitted in `Calibration`:",
         "",
         "```",
         f"P [mW]   = F [nN] * sqrt(V [V]) / c_eff        c_eff = c_F * sqrt(kappa) = {ce:.4f}",
         f"I_max    = {R_EMIT} * {float(i_cl_mA(1.0)):.4e} * V^1.5 mA   (planar Child-Langmuir scale x measured ratio)",
         f"F_max    = {A:.4e} * V^2 nN                      V_min(F) = sqrt(F / {A:.4e})",
         f"F/P      = {ce:.3f} / sqrt(V)  uN/W               ({1e3*ce/10:.0f} uN/W at 100 V, {1e3*ce/math.sqrt(200):.0f} at 200 V, {1e3*ce/math.sqrt(300):.0f} at 300 V)",
         "```",
         "",
         "Its only approximation is neglecting the float; the error is the float tax",
         "V/(V - phi), which grows with voltage. Validation against the committed",
         "voltage frontier (all gates PASS; provenance in the last column):",
         "",
         "| V | P closed-form (mW) | P measured (mW) | error | float tax V/(V-phi) | source |",
         "|---|---|---|---|---|---|"]
    for pt in pts[:4]:
        Pm = float(power_closed_form_mW(cal, pt["F_nN"], pt["V"])); Pmeas = pt["V"] * pt["I_mA"]
        L.append(f"| {pt['V']:.0f} | {Pm:.1f} | {Pmeas:.1f} | {100*(Pm-Pmeas)/Pmeas:+.1f} % "
                 f"| {pt['V']/(pt['V']-pt['phi_V']):.3f} | `{pt['provenance']}` |")
    L += ["",
          "Against the fixed-thrust U-curve stages the law holds where escape is near",
          "unity and diverges where escape collapses inside the can below ~100 V; that",
          "divergence is the geometry-specific loss deferred to `future_work/`:",
          "",
          "| V | escape | F delivered (nN) | P measured (mW) | P closed-form (mW) | ratio | regime |",
          "|---|---|---|---|---|---|---|"]
    for pt in sorted(pts, key=lambda q: q["V"]):
        Pmeas = pt["V"] * pt["I_mA"]; Pm = float(power_closed_form_mW(cal, pt["F_nN"], pt["V"]))
        esc = 100 * pt["esc"]
        regime = ("validated regime" if esc > 95 else
                  "mild escape loss" if esc > 80 else "escape collapsed, geometry-specific")
        L.append(f"| {pt['V']:.1f} | {esc:.1f} % | {pt['F_nN']:.2f} | {Pmeas:.1f} | {Pm:.1f} "
                 f"| {Pmeas/Pm:.2f}x | {regime} |")
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------
# Mission sweep
# ----------------------------------------------------------------------
def _pct(x, q):
    return float(np.percentile(x, q)) if len(x) else float("nan")


def sweep_mission(cal: Calibration, csv_path: Path, out_dir: Path,
                  vmax: float | None = None,
                  vcap: float = V_TESTED_MAX_V) -> dict:
    name = csv_path.parent.parent.name
    cols = dict(t=[], n=[], Te=[], F=[])
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            cols["t"].append(row["timestamp_utc"])
            cols["n"].append(float(row["electron_density_m3"]))
            cols["Te"].append(float(row["electron_temperature_K"]))
            cols["F"].append(float(row["drag_N"]) * 1e9)
    n = np.array(cols["n"]); Te = np.array(cols["Te"]); F = np.array(cols["F"])

    op = operating_point(cal, F, n, Te, vmax=vmax)
    fl = op["flags"]
    F_cap, P_cap = capability_nN(cal, n, Te, V=vcap)
    sol = ~fl["no_solution"]

    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"{name}_model.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "n_e_m3", "Te_K", "F_req_nN", "V_V",
                    "I_mA", "phi_V", "KE_eV", "P_mW", "F_over_P_uN_per_W",
                    "F_capability_nN", "in_envelope", "extrap_density",
                    "extrap_chi", "extrap_voltage", "extrap_phi", "no_solution"])
        for i in range(len(F)):
            if sol[i]:
                num = (f"{op['V'][i]:.2f}", f"{op['I_mA'][i]:.5f}",
                       f"{op['phi_V'][i]:.3f}", f"{op['KE_eV'][i]:.2f}",
                       f"{op['P_mW'][i]:.4f}",
                       f"{op['F_nN'][i]/op['P_mW'][i]:.4f}")
            else:
                num = ("", "", "", "", "", "")
            w.writerow([cols["t"][i], f"{n[i]:.4e}", f"{Te[i]:.1f}", f"{F[i]:.4f}",
                        *num, f"{F_cap[i]:.3f}",
                        int(fl["in_envelope"][i]), int(fl["extrap_density"][i]),
                        int(fl["extrap_chi"][i]), int(fl["extrap_voltage"][i]),
                        int(fl["extrap_phi"][i]), int(fl["no_solution"][i])])

    P = op["P_mW"][sol]; V = op["V"][sol]; phi = op["phi_V"][sol]
    meas = sol & ~fl["extrap_density"]
    s = dict(
        mission=name, rows=len(F), vmax_V=vmax, capability_V=vcap,
        drag_mean_nN=float(F.mean()), drag_max_nN=float(F.max()),
        P_closed_form_mean_drag_mW=float(power_closed_form_mW(
            cal, F.mean(), max(float(min_voltage_closed_form(cal, F.mean())), V_FLOOR_V))),
        no_solution_pct=100.0 * float(fl["no_solution"].mean()),
        P_mean_mW=float(P.mean()), P_median_mW=_pct(P, 50),
        P_p99_mW=_pct(P, 99), P_max_mW=float(P.max()),
        P_mean_measured_density_mW=(float(op["P_mW"][meas].mean())
                                    if meas.any() else float("nan")),
        P_mean_extrap_density_mW=(float(op["P_mW"][sol & fl["extrap_density"]].mean())
                                  if (sol & fl["extrap_density"]).any() else float("nan")),
        V_median=_pct(V, 50), V_p99=_pct(V, 99), V_max=float(V.max()),
        V_over_tested_pct=100.0 * float(fl["extrap_voltage"].mean()),
        phi_median_V=_pct(phi, 50), phi_p99_V=_pct(phi, 99), phi_max_V=float(phi.max()),
        phi_over_sim_pct=100.0 * float(fl["extrap_phi"].mean()),
        extrap_density_pct=100.0 * float(fl["extrap_density"].mean()),
        extrap_chi_pct=100.0 * float(fl["extrap_chi"].mean()),
        in_envelope_pct=100.0 * float(fl["in_envelope"].mean()),
        duty_cycle_needed_pct=100.0 * float(F.mean() / F_cap.mean()),
        closure=float(F_cap.mean() / F.mean()),
        out_csv=str(out_csv.relative_to(REPO)),
    )
    return s


def summary_markdown(cal: Calibration, sums: list[dict]) -> str:
    vmax = sums[0]["vmax_V"] if sums else None
    vcap = sums[0]["capability_V"] if sums else V_TESTED_MAX_V
    L = [f"Supply voltage: {'unconstrained' if vmax is None else f'capped at {vmax:g} V'}; "
         f"per-row operating point = minimum beam power V*I that delivers the drag with the "
         f"float solved self-consistently (V > phi, I <= {R_EMIT} I_CL). "
         f"Envelope columns mark extrapolation, not infeasibility: V > {V_TESTED_MAX_V:g} V "
         f"(gun laws), phi > {PHI_SIM_MAX_V:g} V (no committed equilibrium), density outside "
         f"{DENSITY_BAND[0]}-{DENSITY_BAND[1]}x the PIC row (collection law). "
         f"Duty cycle = mean drag / mean capability at {vcap:g} V. The closed-form column is "
         f"the phi << V law at the mean drag, the paper's one-equation limit (CLOSED_FORM.md).",
         "",
         "| mission | drag mean / max (nN) | P mean / median / p99 / max (mW) | "
         "P mean, measured-density rows (mW) | closed-form P at mean drag (mW) | V median / p99 / max (V) | "
         f"rows V > {V_TESTED_MAX_V:g} V | phi median / p99 / max (V) | "
         f"rows phi > {PHI_SIM_MAX_V:g} V | rows outside density band | "
         f"duty @ {vcap:g} V | no solution |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in sums:
        L.append(
            f"| {s['mission']} | {s['drag_mean_nN']:.1f} / {s['drag_max_nN']:.1f} "
            f"| {s['P_mean_mW']:.1f} / {s['P_median_mW']:.1f} / {s['P_p99_mW']:.0f} / {s['P_max_mW']:.0f} "
            f"| {s['P_mean_measured_density_mW']:.1f} | {s['P_closed_form_mean_drag_mW']:.1f} "
            f"| {s['V_median']:.0f} / {s['V_p99']:.0f} / {s['V_max']:.0f} "
            f"| {s['V_over_tested_pct']:.1f} % "
            f"| {s['phi_median_V']:.1f} / {s['phi_p99_V']:.0f} / {s['phi_max_V']:.0f} "
            f"| {s['phi_over_sim_pct']:.1f} % | {s['extrap_density_pct']:.1f} % "
            f"| {s['duty_cycle_needed_pct']:.0f} % | {s['no_solution_pct']:.1f} % |")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--mission", type=Path)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--alpha-settled", action="store_true",
                    help="fit the collection law on settled-extrapolated phi "
                         "instead of the tail-averaged policy values")
    ap.add_argument("--closed-form", action="store_true",
                    help="print the phi << V law and its validation tables and write "
                         "results/CLOSED_FORM.md")
    ap.add_argument("--vmax", type=float, default=None,
                    help="supply-voltage cap [V]; default none (the voltage is a "
                         "mission parameter, not a limit)")
    ap.add_argument("--vcap", type=float, default=V_TESTED_MAX_V,
                    help="voltage at which per-row capability (duty-cycle closure) "
                         f"is evaluated [V]; default {V_TESTED_MAX_V:g}, the tested maximum")
    ap.add_argument("--out", type=Path, default=REPO / "model" / "results")
    args = ap.parse_args(argv)

    cal = Calibration(use_settled_phi=args.alpha_settled)
    print(cal.report())
    if args.closed_form:
        rep_cf = closed_form_report(cal)
        print("\n" + rep_cf)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "CLOSED_FORM.md").write_text(rep_cf)
        print(f"closed-form -> {args.out / 'CLOSED_FORM.md'}")

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
        s = sweep_mission(cal, p, args.out, vmax=args.vmax, vcap=args.vcap)
        sums.append(s)
        print(f"\nMISSION {s['mission']}  ({s['rows']} rows) -> {s['out_csv']}")
        for k in ("drag_mean_nN", "drag_max_nN", "P_closed_form_mean_drag_mW", "no_solution_pct",
                  "P_mean_mW", "P_median_mW", "P_p99_mW", "P_max_mW",
                  "P_mean_measured_density_mW", "P_mean_extrap_density_mW",
                  "V_median", "V_p99", "V_max", "V_over_tested_pct",
                  "phi_median_V", "phi_p99_V", "phi_max_V", "phi_over_sim_pct",
                  "extrap_density_pct", "extrap_chi_pct", "in_envelope_pct",
                  "duty_cycle_needed_pct", "closure"):
            print(f"  {k:28s} = {s[k]:.3f}" if isinstance(s[k], float) else
                  f"  {k:28s} = {s[k]}")

    (args.out / "MISSION_SUMMARY.md").write_text(
        "# Mission sweep: mission_model.py output\n\n"
        "Generated by `model/mission_model.py --all`. See `model/MODEL.md` for\n"
        "laws, calibration provenance, and envelope semantics.\n\n"
        + summary_markdown(cal, sums) + "\n\nPer-row output files:\n\n"
        + "".join(f"- `{s['out_csv']}`\n" for s in sums))
    with open(args.out / "mission_summary.json", "w") as f:
        json.dump(sums, f, indent=2)
    print(f"\nsummary -> {args.out / 'MISSION_SUMMARY.md'}")


if __name__ == "__main__":
    main()
