#!/usr/bin/env python3
"""
feasibility_model.py -- concept-level power predictions for the electron thruster

The feasibility question: for a given thrust demand at each orbit altitude,
what beam-supply power does the thruster consume?

MODEL (two measured constants, one equation)

    P [mW] = F [nN] * sqrt(V [V]) / c_eff

    c_eff = c_F * sqrt(kappa) = 2.934

    c_F   = 3.2675 nN/(mA*sqrt(eV))   thrust slope (PIC-measured, 3 anchors, <1% spread)
    kappa = 0.8063                     energy fraction KE/(V-phi) (PIC-measured)

    This is the phi << V limit of F = c_F * I * sqrt(kappa*(V-phi)), P = V*I.
    Accuracy vs measured frontier: 3-7% across 100-350 V (the float tax).

EMISSION CEILING

    Maximum current at voltage V:  I_max = 1.46 * I_CL(V)
    Maximum thrust at voltage V:   F_max(V) = c_eff * I_max = A * V^2
    Minimum voltage for thrust F:  V_min(F) = sqrt(F / A)

    A = c_eff * 1.46 * K_CL = 3.554e-4 nN/V^2

WHAT THIS IS NOT

    This is not a flight controller or a validated optimal operating point.
    It predicts ideal beam-supply power (V*I) under the assumption that
    escape is near-unity and phi << V. Real power adds gate/converter
    overheads. Controller optimization is future engineering work.

USAGE
    python model/feasibility_model.py                  # mission predictions
    python model/feasibility_model.py --validate       # validate vs U-curve PIC data
    python model/feasibility_model.py --all            # both + write results
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
QE = 1.602176634e-19
ME = 9.1093837015e-31
EPS0 = 8.8541878128e-12

REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Measured constants from PIC frontier (3 anchors, all gates PASS)
# ---------------------------------------------------------------------------
C_F = 3.2675        # nN/(mA*sqrt(eV)), thrust slope
KAPPA = 0.8063       # energy fraction KE/(V-phi)
C_EFF = C_F * math.sqrt(KAPPA)  # = 2.934

# Emission geometry (frozen: r_spot 0.5 mm, gap 4.7 mm)
EMIT_GAP_M = 4.7e-3
EMIT_R_M = 0.5e-3
R_EMIT = 1.46        # non-planar emission ratio

# Child-Langmuir scale constant: I_CL [mA] = K_CL * V^1.5
_k = (4.0 / 9.0) * EPS0 * math.sqrt(2.0 * QE / ME) / EMIT_GAP_M**2
K_CL = _k * math.pi * EMIT_R_M**2 * 1e3  # 8.298e-5

# Thrust ceiling coefficient: F_max [nN] = A_CEIL * V^2
A_CEIL = C_EFF * R_EMIT * K_CL  # 3.554e-4

V_HW = (100.0, 350.0)

# ---------------------------------------------------------------------------
# The four PIC-validated frontier operating points
# ---------------------------------------------------------------------------
FRONTIER = [
    dict(V=100, I_mA=0.121, phi_V=5.40, F_nN=3.42,  esc_pct=96.12, KE_eV=77.2),
    dict(V=200, I_mA=0.342, phi_V=16.98, F_nN=13.65, esc_pct=98.44, KE_eV=147.5),
    dict(V=300, I_mA=0.630, phi_V=36.30, F_nN=30.13, esc_pct=98.99, KE_eV=210.1),
    dict(V=350, I_mA=0.793, phi_V=48.29, F_nN=40.48, esc_pct=99.11, KE_eV=237.0),
]

# U-curve measured data (geometry-specific, used for validation only)
UCURVE = [
    dict(V=78,   I_mA=0.840, phi_V=23.84, F_nN=10.38, esc_pct=57.43, KE_eV=45.1),
    dict(V=92.4, I_mA=0.601, phi_V=23.72, F_nN=11.59, esc_pct=79.95, KE_eV=55.2),
    dict(V=125,  I_mA=0.464, phi_V=21.25, F_nN=13.09, esc_pct=93.78, KE_eV=83.1),
]


# ---------------------------------------------------------------------------
# Simple power model
# ---------------------------------------------------------------------------
def power_mW(F_nN, V):
    """Beam-supply power [mW] for thrust F [nN] at voltage V [V].

    Uses the simplified law (phi << V):
        I = F / (c_eff * sqrt(V))
        P = V * I = F * sqrt(V) / c_eff
    """
    return np.asarray(F_nN, float) * np.sqrt(np.asarray(V, float)) / C_EFF


def power_corrected_mW(F_nN, V, phi_V):
    """Beam-supply power with explicit float correction."""
    V = np.asarray(V, float)
    phi = np.asarray(phi_V, float)
    I = np.asarray(F_nN, float) / (C_F * np.sqrt(KAPPA * np.maximum(V - phi, 1.0)))
    return V * I


def current_mA(F_nN, V):
    """Required beam current [mA] for thrust F at voltage V (simplified)."""
    return np.asarray(F_nN, float) / (C_EFF * np.sqrt(np.asarray(V, float)))


def i_cl_mA(V):
    """Planar Child-Langmuir current [mA] at voltage V."""
    return K_CL * np.asarray(V, float)**1.5


def max_thrust_nN(V):
    """Maximum thrust [nN] at voltage V, limited by emission ceiling."""
    return A_CEIL * np.asarray(V, float)**2


def min_voltage(F_nN):
    """Minimum voltage [V] to deliver thrust F, set by emission ceiling."""
    return np.sqrt(np.asarray(F_nN, float) / A_CEIL)


def thrust_to_power_ratio(V):
    """F/P [nN/mW] = c_eff / sqrt(V).  Higher at low V: slow & many > fast & few."""
    return C_EFF / np.sqrt(np.asarray(V, float))


# ---------------------------------------------------------------------------
# Calibration report
# ---------------------------------------------------------------------------
def calibration_report() -> str:
    L = [
        "CALIBRATION (concept-level simple model)",
        "",
        f"  thrust slope        c_F   = {C_F:.4f} nN/(mA*sqrt(eV))",
        f"  energy fraction     kappa = {KAPPA:.4f}",
        f"  effective constant  c_eff = c_F*sqrt(kappa) = {C_EFF:.4f}",
        f"  emission ceiling    I_max = {R_EMIT} * {K_CL:.4e} * V^1.5 mA",
        f"  thrust ceiling      F_max = {A_CEIL:.4e} * V^2 nN",
        "",
        "  POWER LAW:  P [mW] = F [nN] * sqrt(V [V]) / {:.4f}".format(C_EFF),
        "",
        "  Validation against PIC frontier:",
    ]
    for pt in FRONTIER:
        P_model = power_mW(pt["F_nN"], pt["V"])
        P_meas = pt["V"] * pt["I_mA"]
        err = (P_model - P_meas) / P_meas * 100
        L.append(f"    {pt['V']:3.0f} V: model {P_model:.1f} mW, "
                 f"measured {P_meas:.1f} mW, error {err:+.1f}% "
                 f"(float tax V/(V-phi) = {pt['V']/(pt['V']-pt['phi_V']):.3f})")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# U-curve validation
# ---------------------------------------------------------------------------
def ucurve_validation() -> str:
    L = [
        "",
        "U-CURVE VALIDATION (geometry-specific PIC data vs simple model)",
        "",
        "  The simple model predicts power assuming near-unity escape.",
        "  Where escape collapses (low V, high perveance), the model",
        "  underestimates power -- that divergence IS the geometry-specific",
        "  loss that belongs in future engineering work, not the concept paper.",
        "",
        "  | V [V] | escape | F_del [nN] | P_meas [mW] | P_model [mW] | "
        "ratio | note |",
        "  |---:|---:|---:|---:|---:|---:|---|",
    ]
    all_pts = FRONTIER + UCURVE
    all_pts.sort(key=lambda p: p["V"])
    for pt in all_pts:
        P_meas = pt["V"] * pt["I_mA"]
        P_model = power_mW(pt["F_nN"], pt["V"])
        ratio = P_meas / P_model
        esc = pt["esc_pct"]
        if esc > 95:
            note = "validated regime"
        elif esc > 80:
            note = "mild escape loss"
        else:
            note = "escape collapsed -- geometry-specific"
        L.append(f"  | {pt['V']:5.1f} | {esc:5.1f}% | {pt['F_nN']:5.2f} | "
                 f"{P_meas:6.1f} | {P_model:6.1f} | {ratio:.2f}x | {note} |")

    L += [
        "",
        "  In the validated regime (escape > 95%), the simple model agrees",
        "  to within 8%. Below ~100 V, escape collapses due to beam",
        "  self-scrape inside the capstone can geometry -- the measured",
        "  power diverges from the model because the emitter must push",
        "  more current to compensate for lost electrons. This loss is",
        "  geometry-specific (isolated-gun tests at 92 V show 99.99%",
        "  transmission) and is deferred to controller optimization.",
    ]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Mission power predictions
# ---------------------------------------------------------------------------
def sweep_missions() -> tuple[str, list[dict]]:
    csv_dir = REPO / "orbit_sims" / "validation_cases"
    paths = sorted(csv_dir.glob("*/results/station_keeping.csv"))
    if not paths:
        return "No mission CSVs found.", []

    L = [
        "",
        "MISSION POWER PREDICTIONS (simple model)",
        "",
        "  For each altitude, the model predicts beam-supply power at the",
        "  minimum feasible voltage (emission-ceiling limited) and at",
        "  representative fixed voltages.",
        "",
        "  Power demand is the deliverable; supplying it is mission design.",
        "  For scale only: body-mounted cells on the anchor body harvest",
        "  roughly 10-30 mW depending on coverage (30% cells, 25% duty).",
        "",
    ]

    summaries = []
    for p in paths:
        name = p.parent.parent.name
        F_list = []
        with open(p) as f:
            for row in csv.DictReader(f):
                F_list.append(float(row["drag_N"]) * 1e9)
        F = np.array(F_list)
        F_mean, F_max, F_p95 = float(F.mean()), float(F.max()), float(np.percentile(F, 95))

        V_min_mean = float(min_voltage(F_mean))
        V_min_max = float(min_voltage(F_max))

        feas_at_cap = bool(F_max <= max_thrust_nN(V_HW[1]))
        feas_at_200 = bool(F_max <= max_thrust_nN(200))

        s = dict(
            mission=name,
            rows=len(F),
            F_mean_nN=F_mean,
            F_max_nN=F_max,
            F_p95_nN=F_p95,
            V_min_mean=V_min_mean,
            V_min_max=V_min_max,
            feasible_at_350V=feas_at_cap,
        )

        L.append(f"  {name}")
        L.append(f"    drag: mean {F_mean:.2f} nN, 95th {F_p95:.2f} nN, max {F_max:.2f} nN")
        L.append(f"    V_min for mean drag: {V_min_mean:.0f} V")
        L.append(f"    V_min for max drag:  {V_min_max:.0f} V  "
                 f"{'(within hardware)' if V_min_max <= V_HW[1] else f'(EXCEEDS {V_HW[1]:.0f} V -- infeasible)'}")

        hdr = "    {:>8s}  {:>10s}  {:>10s}  {:>10s}  {:>8s}".format(
            "V [V]", "P_mean", "P_95th", "P_max", "F/P")
        L.append(hdr)

        voltages = [100, 150, 200, 300, 350]
        for V in voltages:
            P_mean = float(power_mW(F_mean, V))
            P_p95 = float(power_mW(F_p95, V))
            P_max = float(power_mW(F_max, V))
            fp = float(thrust_to_power_ratio(V) * 1e3)  # uN/W
            feas_flag = "" if F_max <= max_thrust_nN(V) else "  (max drag exceeds ceiling)"
            L.append(f"    {V:>8.0f}  {P_mean:>8.1f} mW  {P_p95:>8.1f} mW  "
                     f"{P_max:>8.1f} mW  {fp:>5.0f} uN/W{feas_flag}")
            s[f"P_mean_{V}V_mW"] = P_mean
            s[f"P_max_{V}V_mW"] = P_max

        L.append("")
        summaries.append(s)

    # Summary table
    L += [
        "SUMMARY TABLE (beam-supply power at minimum feasible voltage)",
        "",
        "  | mission | drag mean (nN) | drag max (nN) | V_min (mean) | "
        f"P_mean (mW) | P_max (mW) | inside {V_HW[1]:.0f} V envelope |",
        "  |---|---:|---:|---:|---:|---:|---|",
    ]
    for s in summaries:
        V_use = max(s["V_min_mean"], V_HW[0])
        P_mean = float(power_mW(s["F_mean_nN"], V_use))
        P_max = float(power_mW(s["F_max_nN"], V_use))
        verdict = "yes" if s["V_min_mean"] <= V_HW[1] else "no (V_min above ceiling)"
        L.append(f"  | {s['mission']} | {s['F_mean_nN']:.1f} | {s['F_max_nN']:.1f} "
                 f"| {V_use:.0f} V | {P_mean:.1f} | {P_max:.1f} | {verdict} |")
        s["P_mean_Vmin_mW"] = P_mean
        s["P_max_Vmin_mW"] = P_max

    return "\n".join(L), summaries


# ---------------------------------------------------------------------------
# Per-row mission CSV output
# ---------------------------------------------------------------------------
def write_mission_csvs(summaries: list[dict], out_dir: Path):
    csv_dir = REPO / "orbit_sims" / "validation_cases"
    out_dir.mkdir(parents=True, exist_ok=True)

    for s in summaries:
        name = s["mission"]
        matches = list(csv_dir.glob(f"{name}/results/station_keeping.csv"))
        if not matches:
            continue
        src = matches[0]

        out_csv = out_dir / f"{name}_feasibility.csv"
        with open(src) as fin, open(out_csv, "w", newline="") as fout:
            reader = csv.DictReader(fin)
            w = csv.writer(fout)
            w.writerow(["timestamp_utc", "F_drag_nN",
                        "V_min_V", "P_at_Vmin_mW",
                        "P_at_100V_mW", "P_at_200V_mW", "P_at_300V_mW",
                        "P_at_350V_mW", "feasible_at_350V"])
            for row in reader:
                F = float(row["drag_N"]) * 1e9
                Vm = max(float(min_voltage(F)), V_HW[0])
                w.writerow([
                    row["timestamp_utc"],
                    f"{F:.4f}",
                    f"{Vm:.1f}",
                    f"{float(power_mW(F, Vm)):.3f}",
                    f"{float(power_mW(F, 100)):.3f}",
                    f"{float(power_mW(F, 200)):.3f}",
                    f"{float(power_mW(F, 300)):.3f}",
                    f"{float(power_mW(F, 350)):.3f}",
                    int(F <= max_thrust_nN(350)),
                ])
        s["out_csv"] = str(out_csv.relative_to(REPO))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--validate", action="store_true",
                    help="validate simple model against U-curve PIC data")
    ap.add_argument("--all", action="store_true",
                    help="full output: calibration + validation + missions + write results")
    ap.add_argument("--out", type=Path, default=REPO / "model" / "results")
    args = ap.parse_args(argv)

    print(calibration_report())

    if args.validate or args.all:
        print(ucurve_validation())

    mission_text, summaries = sweep_missions()
    print(mission_text)

    if args.all and summaries:
        write_mission_csvs(summaries, args.out)

        md_path = args.out / "FEASIBILITY_POWER.md"
        md = ("# Feasibility power predictions: simple model\n\n"
              "Generated by `model/feasibility_model.py --all`.\n"
              "See the `model/feasibility_model.py` docstring for the model.\n\n"
              "## Calibration\n\n```\n" + calibration_report() + "\n```\n\n"
              "## U-curve validation\n\n```\n" + ucurve_validation() + "\n```\n\n"
              "## Mission predictions\n\n```\n" + mission_text + "\n```\n")
        md_path.write_text(md)

        json_path = args.out / "feasibility_power.json"
        with open(json_path, "w") as f:
            json.dump(summaries, f, indent=2)

        print(f"\nResults written to:")
        print(f"  {md_path.relative_to(REPO)}")
        print(f"  {json_path.relative_to(REPO)}")
        for s in summaries:
            if "out_csv" in s:
                print(f"  {s['out_csv']}")


if __name__ == "__main__":
    main()
