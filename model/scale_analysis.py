#!/usr/bin/env python3
"""Scale analysis: is the feasibility condition a function of SIZE or of SHAPE?

Reads only committed evidence -- the calibration in `mission_model.py` (fitted
to `reference_results/`) and the mission CSVs in `model/results/` -- and asks
what changes when the same device is built at CubeSat scale instead of
chipsat scale.

The result is that size cancels.  Drag charges for the drag area S_ref (ram
face plus grazing friction on the walls parallel to the flow) and any
body-mounted power supply pays from the skin, and both the thrust demand and
the supply scale with area, so the closure condition depends on the SHAPE
ratio (skin / S_ref) and the altitude, not on how big the craft is.  The power
source is not part of the thruster; body-mounted solar cells are used below
only as a worked example of a skin-areal supply.

Run:  python model/scale_analysis.py [--out model/results]
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np

import mission_model as M

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "orbit_sims"))
from constants import MU_EARTH, R_EARTH  # noqa: E402  (orbit_sims/constants.py)
from spacecraft import grazing_cd  # noqa: E402  (the orbit sims' own wall-friction law)

# ---------------------------------------------------------------- assumptions
# Stated here, not buried: these are engineering inputs, NOT measurements.
CELL_EFFICIENCY = 0.30        # triple-junction, end of life
ILLUMINATION_DUTY = 0.25      # orbit-average, body-mounted, no sun tracking
CELL_FRACTION_OF_SKIN = 1/3   # rest of the skin is bare collector + structure
SOLAR_CONSTANT = 1361.0       # W/m^2
DRIVE_V = 100.0               # V; F/P ~ 1/sqrt(V), so the frontier's low end

# Drag = rho v^2/2 * Cd * S_ref with S_ref = A_ram + (Cd_side/Cd) * A_parallel:
# the ram face plus grazing friction on the walls parallel to the flow, the
# same bookkeeping as orbit_sims/spacecraft.py.  The wall term is small on the
# squat can (+6 %) but not on end-on bodies with long walls (+37 % at L/r = 6),
# so ram area alone underestimates exactly the bodies this analysis is about.
# Drag per unit S_ref is spacecraft-independent (altitude is held), which is
# what lets the chipsat mission CSVs be rescaled to any body.
CD = 2.2
SIGMA_T, EXO_T_K, MEAN_AMU = 0.9, 1000.0, 16.0       # orbit_sims defaults
R_CHIPSAT, H_CHIPSAT = 0.005, 0.005                  # orbit_sims chipsat cases

# Mass is not a demand input (station-keeping thrust = drag), only the inertia
# that sets how fast a craft sinks while thrust falls short.  Every body gets
# the density of a 4 kg, 3000 cm^3 3U, so mass follows volume.
DENSITY_KG_M3 = 4.0 / 3.0e-3


def can(name, r, L, skin):
    """A measured PIC can flown axial.  Skin as quoted by the stage (exhaust
    hole removed); the side wall is parallel to the flow."""
    return dict(name=name, ram=math.pi * r**2, parallel=2 * math.pi * r * L, skin=skin,
                r_eff=r, mass=DENSITY_KG_M3 * math.pi * r**2 * L)


def box(name, w, d, L, r_eff):
    """A w x d x L box flown end-on: the w x d face meets the flow."""
    return dict(name=name, ram=w * d, parallel=2 * (w + d) * L,
                skin=2 * w * d + 2 * (w + d) * L, r_eff=r_eff, mass=DENSITY_KG_M3 * w * d * L)


BODIES = [
    can("squat can O10x5.5mm (measured)", 0.005, 5.5e-3, 3.17e-4),
    can("slender O10x30.5mm (measured)", 0.005, 30.5e-3, 11.0e-4),
    box("1U cube, face-on", 0.1, 0.1, 0.1, 0.050),
    box("3U end-on (10x10x30 cm)", 0.1, 0.1, 0.3, 0.100),
    box("6U end-on (10x20x30 cm)", 0.1, 0.2, 0.3, 0.120),
    box("12U end-on (20x20x30 cm)", 0.2, 0.2, 0.3, 0.140),
]
ALTITUDES = (400, 500, 550, 600)


def wall_ratio(alt: int) -> float:
    """Cd_side / Cd: the weight of a parallel wall relative to the ram face."""
    return grazing_cd(SIGMA_T, EXO_T_K, MEAN_AMU, alt) / CD


def s_ref(b: dict, alt: int) -> float:
    return b["ram"] + wall_ratio(alt) * b["parallel"]


def drag_per_sref() -> dict[int, tuple[float, float]]:
    """(mean, max) drag force per m^2 of S_ref, from the committed chipsat CSVs."""
    out = {}
    for alt in ALTITUDES:
        p = REPO / "model" / "results" / f"{alt}km_station_keeping_chipsat_model.csv"
        F = np.array([float(r["F_req_nN"]) for r in csv.DictReader(open(p))]) * 1e-9
        s = math.pi * R_CHIPSAT**2 + wall_ratio(alt) * 2 * math.pi * R_CHIPSAT * H_CHIPSAT
        out[alt] = (F.mean() / s, F.max() / s)
    return out


def sink_m_per_day(F_N: float, mass_kg: float, alt_km: float) -> float:
    """Circular-orbit decay rate if thrust stops: da/dt = 2 a F / (m v)."""
    a = R_EARTH + alt_km * 1e3
    v = math.sqrt(MU_EARTH / a)
    return 2.0 * a * F_N / (mass_kg * v) * 86400.0


def thick_sheath_phi(boost: float, r_eff: float, lamD: float, kTe_eV: float):
    """Float estimate for r >> lambda_D, where the OML exponent does NOT apply.

    A large body collects through a sheath that GROWS with phi rather than
    through an orbital-motion fan, so the enhancement is an area ratio,
    (r_sheath/r)^2, with a Child-Langmuir sheath r_s - r ~ lambda_D * (2*chi)^(3/4).

    ESTIMATE, not calibration: no committed run sits in this regime.  It is
    reported so the extrapolation direction is explicit and checkable.
    """
    if boost <= 1.0:
        return 0.0, 0.0
    x = (math.sqrt(boost) - 1.0) * r_eff / lamD
    chi = 0.5 * x ** (4.0 / 3.0)
    return chi * kTe_eV, chi


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "model" / "results")
    args = ap.parse_args()

    cal = M.Calibration()
    n0, Te = 1.627e12, 1318.8                      # the committed plasma row
    K_B, Q_E, EPS0 = 1.380649e-23, 1.602176634e-19, 8.8541878128e-12
    kTe = K_B * Te / Q_E                                   # eV
    lamD = math.sqrt(EPS0 * kTe * Q_E / (n0 * Q_E**2))     # m
    j_the = M.j_the(n0, Te)
    KE = cal.kappa * (DRIVE_V - 3.0)               # phi is small for large skin
    harvest = SOLAR_CONSTANT * CELL_EFFICIENCY * ILLUMINATION_DUTY
    fd = drag_per_sref()

    def current_mA(b, alt):
        """Beam current that cancels the body's mean drag at this altitude."""
        return fd[alt][0] * s_ref(b, alt) * 1e9 / (cal.cF * math.sqrt(KE))

    L = []
    w = L.append
    w("# Scale analysis: does feasibility depend on size, or on shape?\n")
    w("Generated by `model/scale_analysis.py` from committed calibration and")
    w("mission CSVs. See `model/README.md` for the laws and `paper/SCALING_LAWS.md`")
    w("§8c for the argument.\n")
    w("## The question\n")
    w("Every committed PIC run is a Ø10 mm body. The paper's mission table is a")
    w("Ø10 mm chipsat. Neither is a useful spacecraft. If the concept only works")
    w("at gram scale it is a curiosity; if the feasibility condition is")
    w("scale-free it is a propulsion option for CubeSats.\n")
    w("## Assumptions (engineering inputs, not measurements)\n")
    w("The power source is not part of the thruster. Body-mounted solar cells")
    w("appear here only as a worked example of a supply that scales with")
    w("skin area; any other skin-areal source changes the margin, not the")
    w("size-cancellation.\n")
    w(f"- solar cells {CELL_EFFICIENCY:.0%} efficient, {ILLUMINATION_DUTY:.0%} "
      f"orbit-average illumination → {harvest:.0f} W/m² of cell area")
    w(f"- cells cover {CELL_FRACTION_OF_SKIN:.0%} of skin (rest is bare collector + structure)")
    w(f"- drive {DRIVE_V:.0f} V (F/P ∝ 1/√V, so the frontier's low end)")
    w(f"- drag area S_ref = ram face + (C_d,side/C_d) × walls parallel to the flow,")
    w(f"  C_d = {CD}, the orbit sims' bookkeeping (C_d,side/C_d = "
      f"{wall_ratio(500):.3f} at 500 km)")
    w(f"- mass at 3U density ({DENSITY_KG_M3/1e3:.2f} g/cm³); it enters only the")
    w(f"  sink rate of Step 6, never the thrust demand\n")

    w("## Step 1: demand and supply are both areal\n")
    w("Drag charges for the drag area S_ref: the ram face plus grazing friction")
    w("on the walls parallel to the flow. Any body-mounted supply pays from the")
    w("skin (solar cells as the example). Thrust demand, hence current, hence")
    w("power, all scale with S_ref, so power per unit S_ref is a property of")
    w("altitude and drive alone:\n")
    w("| altitude | drag (mean) | P required |")
    w("|---|---|---|")
    for alt in ALTITUDES:
        I_per = (fd[alt][0] * 1e9) / (cal.cF * math.sqrt(KE))     # mA per m^2
        w(f"| {alt} km | {fd[alt][0]*1e6:.1f} µN/m² | "
          f"**{I_per*DRIVE_V*1e-3:.0f} W per m² of S_ref** |")
    w("\nHarvest per unit skin area is likewise size-free. Size cancels from")
    w("both sides. What survives is the shape ratio skin/S_ref.\n")

    w("## Step 2: closure by shape, at every size\n")
    w("Margin = example supply / demand. The point is that the ratio is")
    w("size-free; the absolute number is secondary. The wall term makes")
    w("S_ref larger than the ram face, most on long end-on bodies:\n")
    w("| body | ram | S_ref/ram | skin/S_ref | cells | "
      + " | ".join(f"{a} km" for a in ALTITUDES) + " |")
    w("|---|---|---|---|---|" + "---|" * len(ALTITUDES))
    for b in BODIES:
        avail = harvest * b["skin"] * CELL_FRACTION_OF_SKIN
        cells = []
        for alt in ALTITUDES:
            P = current_mA(b, alt) * DRIVE_V * 1e-3
            cells.append(f"{avail/P:.1f}×" if avail >= P else f"_{avail/P:.1f}×_")
        sr = s_ref(b, 500)
        w(f"| {b['name']} | {b['ram']*1e4:.2g} cm² | {sr/b['ram']:.2f} | "
          f"**{b['skin']/sr:.1f}** | {avail:.2f} W | " + " | ".join(cells) + " |")
    w("\nThe slender chipsat and the 3U CubeSat return near-identical margins")
    w("because they have near-identical shape ratios. Feasibility is a shape")
    w("property.")
    w("The 400 km demand exceeds the example supply at every size. Supplying")
    w("it is a mission-design question, and it too is size-free.\n")

    w("## Step 3: what a useful spacecraft needs\n")
    w(f"At {DRIVE_V:.0f} V, KE = {KE:.0f} eV:\n")
    w("| body | altitude | thrust | current | power |")
    w("|---|---|---|---|---|")
    for b in BODIES[2:]:
        for alt in (500, 550, 600):
            F = fd[alt][0] * s_ref(b, alt)
            I = current_mA(b, alt)
            w(f"| {b['name']} | {alt} km | {F*1e6:.2f} µN | {I:.1f} mA | "
              f"{I*DRIVE_V*1e-3:.2f} W |")

    w("\n## Step 4: collection gets easier with size\n")
    w(f"Bare thermal collection is `I = A_skin · j_the`, validated to ±1 % at rung")
    w(f"`collector.thermal`. At the committed plasma row j_the gives:\n")
    w("| body | skin | I_thermal | boost needed @600 km | regime r/λ_D |")
    w("|---|---|---|---|---|")
    for b in BODIES:
        Ith = b["skin"] * j_the * 1e3
        I = current_mA(b, 600)
        w(f"| {b['name']} | {b['skin']*1e4:.3g} cm² | {Ith:.3f} mA | {I/Ith:.1f}× "
          f"| {b['r_eff']/lamD:.1f} |")
    w("\nThe chipsat must run at χ ≈ 150–320, deep in the extrapolated")
    w("enhancement regime. A 3U needs only a few × over bare thermal, so its")
    w("float depends on the ±1 %-validated thermal flux plus a small correction.")
    w("Larger bodies need less extrapolation, not more.\n")

    w("## Step 5: the caveat, a different sheath regime\n")
    w(f"Every committed run is at r/λ_D ≈ {0.005/lamD:.1f}. CubeSat radii are")
    w("25–60 λ_D, where the OML exponent does not apply at all: the sheath is")
    w("thin and grows with φ, so enhancement is an area ratio rather than an")
    w("orbital-motion fan. Using that (Child-sheath) model instead gives an")
    w("estimate, not a calibration, since no run sits in this regime:\n")
    w(f"| body | altitude | boost | φ estimate | float tax at {DRIVE_V:.0f} V |")
    w("|---|---|---|---|---|")
    phi_3u = {}
    for b in BODIES[2:]:
        for alt in (500, 550, 600):
            Ith = b["skin"] * j_the * 1e3
            I = current_mA(b, alt)
            phi, _chi = thick_sheath_phi(I / Ith, b["r_eff"], lamD, kTe)
            if b["name"].startswith("3U"):
                phi_3u[alt] = phi
            w(f"| {b['name']} | {alt} km | {I/Ith:.1f}× | {phi:.0f} V | {phi/DRIVE_V:.0%} |")
    w("\nThe float is a tax on the drive, not a gate (no float value is a design")
    w(f"limit): the 3U's {phi_3u[600]:.0f} V float at 600 km costs "
      f"{phi_3u[600]/DRIVE_V:.0%} of a {DRIVE_V:.0f} V drive,")
    w(f"its {phi_3u[500]:.0f} V float at 500 km costs {phi_3u[500]/DRIVE_V:.0%}, "
      f"and the minimum-power operating point moves to a")
    w("higher drive (SCALING_LAWS §2: optimum near V = 2φ). Unmeasured, but the")
    w("direction is favourable, and a large-body PIC run is inexpensive: lower χ")
    w("settles faster than anything already run.\n")

    w("## Step 6: mass sets the tolerance, not the demand\n")
    w("Holding altitude takes thrust equal to the drag force, and the drag force")
    w("has no mass in it, so none of the numbers above depend on mass. Mass")
    w("decides what happens while thrust falls short of drag (drag peaks above")
    w("capability, duty-cycled operation): the craft sinks at")
    w("da/dt = 2aF/(mv) until thrust catches up. Sink rate at the mean drag")
    w("with the thruster off:\n")
    w("| body | mass | ballistic coeff. @500 km | 500 km | 550 km | 600 km |")
    w("|---|---|---|---|---|---|")
    for b in BODIES:
        m = b["mass"]
        sinks = [sink_m_per_day(fd[alt][0] * s_ref(b, alt), m, alt) for alt in (500, 550, 600)]
        mass = f"{m*1e3:.2g} g" if m < 1.0 else f"{m:.3g} kg"
        w(f"| {b['name']} | {mass} | {m/(CD*s_ref(b, 500)):.0f} kg/m² | "
          + " | ".join(f"{s:.0f} m/day" for s in sinks) + " |")
    w("\nMass grows with volume and drag with area, so the ballistic coefficient")
    w("grows with size: at equal density a 3U sinks about 10× more slowly than")
    w("the slender can for the same shortfall. This is the one quantity that is")
    w("not scale-free, and it favours the CubeSat.\n")

    w("## Conclusion\n")
    w("The measured device is a Ø10 mm can, but the result is not about a")
    w("Ø10 mm can. Demand and supply are both areal, so the feasibility")
    w("condition reduces to a shape ratio and an altitude. CubeSat-class craft")
    w("in their natural end-on configurations sit at more favourable shape")
    w("ratios and less extrapolated collection physics than the chipsat that")
    w("was measured. The 400 km demand is scale-free too: it exceeds the")
    w("example body-mounted supply at every size.")

    out = args.out / "SCALE_ANALYSIS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
