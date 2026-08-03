#!/usr/bin/env python3
r"""figures_of_merit.py — the numbers the thesis claim rests on.

    python3 figures_of_merit.py                # every committed operating point
    python3 figures_of_merit.py --markdown     # a table to paste into the README

WHAT THIS IS FOR. The claim is about a REGIME, and a regime is defined by
figures of merit, not by a mission envelope:

    eta   = P_jet / P_electrical     energy efficiency  -- ion-thruster class
    F/P                              thrust per watt    -- ~200x BELOW ion
    v_eff = F / mdot_effective       exhaust velocity

Both numbers have to be quoted together, always. Energy efficiency near 0.7 is
what makes this a real thruster; F/P two orders below gridded ion is what
confines it to the nN regime -- and that confinement is the claim, not a
weakness. A README that quoted only eta would be claiming parity it does not
have.

ZERO NET MASS FLUX. In steady state the craft emits exactly as many electrons
as it collects (that IS the current balance rung 8 measures to 3.2 %), so the
mass flow through the spacecraft boundary is identically zero and the total
impulse has no propellant limit. `v_eff` below is therefore reported against the
*emitted* electron flux -- a bookkeeping exhaust velocity, useful for comparing
with propellant thrusters, but it is not a mass the spacecraft has to carry.

THE IDENTITIES. Every quantity here is closed-form in the calibration constants,
so nothing can drift between this module, `laws.yaml` and the README:

    P_jet = f_esc * I * KE          KE = ke_ledger*(V - phi)   [eV -> J via e]
    eta   = P_jet/(I*V) = f_esc * ke_ledger * (V - phi)/V
    F/P   = k*sqrt(ke_ledger*(V-phi)) / V     [nN/mA/V -> uN/W]

`tests/test_figures_of_merit.py` pins both against the numerical path.

MEASURED vs MODELLED. Where a committed PIC run measured phi_body and F_beam,
this uses the MEASUREMENT (and says so). The model is used only to fill in what
was not measured. After rung 9 that distinction matters: the collection law is
known to be wrong, so any figure of merit that depended on a *predicted* phi
would inherit that error. eta and F/P depend on phi only through (V - phi),
which the runs measured directly.

Depends on: PyYAML, scipy.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

DESIGN_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DESIGN_ROOT.parent
sys.path.insert(0, str(DESIGN_ROOT))

from scipy import constants as scc  # noqa: E402

import opmodel as om  # noqa: E402
from calibration import load_laws  # noqa: E402

E = scc.e
ME = scc.m_e

#: Committed evidence this module reads. Nothing here is typed by hand.
RUNG8 = ("pic_sims/validation_cases/capstone/2_chipsat_thruster/reference_results"
         "/20260801T142601Z_2f822a95/metrics.json")
RUNG9 = ("pic_sims/validation_cases/capstone/3_mission_envelope/reference_results"
         "/20260803T091155Z_4fc9fd22/metrics.json")


@dataclass(frozen=True)
class Point:
    """One operating point and everything the claim quotes about it."""
    label: str
    source: str            # "measured (rung 8)" etc.
    v_drive: float         # [V]
    i_beam_mA: float       # [mA]
    phi_V: float           # [V]
    f_nN: float            # [nN]
    ke_eV: float           # [eV]
    f_esc: float           # [-]

    # ---- electrical ----
    @property
    def p_supply_mW(self) -> float:
        """The supply pays the full drive voltage for every emitted electron."""
        return self.i_beam_mA * self.v_drive

    @property
    def p_jet_mW(self) -> float:
        """Directed kinetic power carried out of the system by escaped beam."""
        return self.f_esc * self.i_beam_mA * self.ke_eV

    @property
    def eta(self) -> float:
        """Energy efficiency = jet power / electrical power."""
        return self.p_jet_mW / self.p_supply_mW if self.p_supply_mW else float("nan")

    @property
    def f_per_p_uN_per_W(self) -> float:
        """Thrust per watt [uN/W].  F[nN]/P[mW] == F[uN]/P[W]."""
        return self.f_nN / self.p_supply_mW if self.p_supply_mW else float("nan")

    @property
    def v_eff_km_s(self) -> float:
        """Effective exhaust speed [km/s] against the EMITTED electron flux.

        Bookkeeping only -- net mass flux through the spacecraft boundary is
        exactly zero in steady state.
        """
        mdot = self.f_esc * (self.i_beam_mA * 1e-3 / E) * ME      # [kg/s]
        return (self.f_nN * 1e-9 / mdot) * 1e-3 if mdot > 0 else float("nan")

    @property
    def v_from_energy_km_s(self) -> float:
        """sqrt(2*e*KE/m_e) -- the same speed from the energy side, as a check."""
        return math.sqrt(2.0 * E * self.ke_eV / ME) * 1e-3


# ----------------------------------------------------------------------
# the closed forms -- what the README is allowed to claim
# ----------------------------------------------------------------------

def eta_closed_form(v_drive: float, phi_V: float, f_esc: float,
                    ke_ledger: float) -> float:
    """``eta = f_esc * ke_ledger * (V - phi) / V``.

    Note what it does NOT contain: density, temperature, current, or beta. The
    energy efficiency of this device is a property of its ELECTRODE GEOMETRY and
    the float depth, nothing else -- which is why rung 9's collection-law failure
    does not touch it.
    """
    return f_esc * ke_ledger * (abs(v_drive) - phi_V) / abs(v_drive)


def f_per_p_closed_form(v_drive: float, phi_V: float, k: float,
                        ke_ledger: float) -> float:
    """``F/P = k*sqrt(ke_ledger*(V - phi))/V`` in uN/W.

    Falls as ``1/sqrt(V)`` at fixed float: a faster beam buys thrust more
    expensively, which is the whole reason this device owns the nN slot and
    nothing above it.
    """
    ke = ke_ledger * (abs(v_drive) - phi_V)
    return k * math.sqrt(ke) / abs(v_drive) if ke > 0 else float("nan")


# ----------------------------------------------------------------------
# committed evidence
# ----------------------------------------------------------------------

def _metrics(rel: str) -> dict:
    path = REPO_ROOT / rel
    if not path.is_file():
        raise SystemExit(f"missing committed evidence: {rel}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"]: m["value"] for m in doc["metrics"]
            if m["status"] == "OK" and m["value"] is not None}


def measured_points() -> list[Point]:
    """Every operating point a committed PIC run actually measured."""
    m8, m9 = _metrics(RUNG8), _metrics(RUNG9)
    pts = [Point(
        label="rung 8 anchor (400 km day, 200 V)",
        source="measured (capstone.floating_body)",
        v_drive=200.0, i_beam_mA=0.342,
        phi_V=m8["phi_body_V"], f_nN=m8["f_beam_nN"],
        ke_eV=m8["exhaust_ke_mean_eV"], f_esc=m8["escape_fraction_pct"] / 100.0)]
    for scn, label in (("A_day_p95", "rung 9 A: day p95 (400 km, 300 V)"),
                       ("B_night_worst", "rung 9 B: night worst (400 km, 300 V)")):
        i_mA = m9[f"{scn}__p_supply_mW"] / 300.0
        pts.append(Point(
            label=label, source="measured (capstone.mission_envelope)",
            v_drive=300.0, i_beam_mA=i_mA,
            phi_V=m9[f"{scn}__phi_body_V"], f_nN=m9[f"{scn}__f_beam_nN"],
            ke_eV=m9[f"{scn}__exhaust_ke_mean_eV"],
            f_esc=m9[f"{scn}__escape_fraction_pct"] / 100.0))
    return pts


def modelled_point(v_drive: float, phi_V: float, i_beam_mA: float, laws,
                   label: str) -> Point:
    """A point the model predicts, for filling in coverage the runs lack."""
    ke = om.exhaust_ke_eV(v_drive, phi_V, laws.ke_ledger)
    return Point(label=label, source="modelled (laws.yaml)", v_drive=v_drive,
                 i_beam_mA=i_beam_mA, phi_V=phi_V,
                 f_nN=om.thrust_nN(i_beam_mA, v_drive, phi_V, laws.k, laws.ke_ledger),
                 ke_eV=ke, f_esc=laws.f_esc)


# ----------------------------------------------------------------------
# reporting
# ----------------------------------------------------------------------

_LANDSCAPE = [
    # (system, F/P uN/W, min controllable thrust, propellant system, works at mW)
    ("gridded ion / Hall", "30-60", "~mN", "tank + feed + neutralizer", "no"),
    ("electrospray / FEEP", "10-30", "~5 uN (0.1 uN res.)", "tank + feed, ~kg class",
     "no (~0.1 W floor)"),
    ("photon (laser/LED)", "0.0033", "arbitrarily low", "none", "yes"),
]


def render(points: list[Point], markdown: bool) -> str:
    out: list[str] = []
    if markdown:
        out.append("| operating point | source | V | I [mA] | phi [V] | KE [eV] "
                   "| F [nN] | P [mW] | eta | F/P [uN/W] | v_eff [km/s] |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for p in points:
            out.append(
                f"| {p.label} | {p.source} | {p.v_drive:.0f} V | {p.i_beam_mA:.4f} "
                f"| {p.phi_V:+.2f} | {p.ke_eV:.1f} | {p.f_nN:.2f} | {p.p_supply_mW:.1f} "
                f"| **{p.eta:.3f}** | **{p.f_per_p_uN_per_W:.3f}** | {p.v_eff_km_s:.0f} |")
    else:
        out.append(f"{'operating point':44s} {'V':>5s} {'I[mA]':>7s} {'phi':>7s} "
                   f"{'KE[eV]':>8s} {'F[nN]':>7s} {'P[mW]':>7s} {'eta':>6s} "
                   f"{'F/P':>7s} {'v_eff':>8s}")
        out.append("-" * 118)
        for p in points:
            out.append(
                f"{p.label:44s} {p.v_drive:5.0f} {p.i_beam_mA:7.4f} {p.phi_V:+7.2f} "
                f"{p.ke_eV:8.1f} {p.f_nN:7.2f} {p.p_supply_mW:7.1f} {p.eta:6.3f} "
                f"{p.f_per_p_uN_per_W:7.3f} {p.v_eff_km_s:8.0f}")
    etas = [p.eta for p in points]
    fps = [p.f_per_p_uN_per_W for p in points]
    out.append("")
    out.append(f"across every committed operating point: "
               f"eta = {min(etas):.3f}-{max(etas):.3f}, "
               f"F/P = {min(fps):.3f}-{max(fps):.3f} uN/W")
    out.append("net mass flux through the spacecraft boundary is exactly zero "
               "(electrons in = electrons out); v_eff is bookkeeping against the "
               "emitted flux, not a propellant the craft carries.")
    return "\n".join(out)


def render_landscape(points: list[Point], markdown: bool) -> str:
    fps = [p.f_per_p_uN_per_W for p in points]
    ours = f"~{sum(fps)/len(fps):.2f}"
    rows = _LANDSCAPE + [("**this device**", f"**{ours}**", "**~nN**", "**none**",
                          "**yes**")]
    out = ["", "COMPETITIVE LANDSCAPE -- literature values, CONTEXT not measurement.",
           "(Only the last row comes from this repository's own runs.)", ""]
    if markdown:
        out.append("| system | F/P [uN/W] | min controllable thrust | propellant "
                   "system | works at mW |")
        out.append("|---|---|---|---|---|")
        out += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows]
    else:
        out.append(f"{'system':22s} {'F/P[uN/W]':>10s}  {'min thrust':22s} "
                   f"{'propellant':26s} {'mW?':>16s}")
        out += [f"{a:22s} {b:>10s}  {c:22s} {d:26s} {e:>16s}"
                for a, b, c, d, e in rows]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--markdown", action="store_true",
                    help="emit README-ready markdown tables")
    ap.add_argument("--no-landscape", action="store_true")
    args = ap.parse_args(argv)

    points = measured_points()
    print(render(points, args.markdown))
    if not args.no_landscape:
        print(render_landscape(points, args.markdown))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
