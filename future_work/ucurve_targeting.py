#!/usr/bin/env python3
"""
ucurve_targeting.py -- commanded currents for the fixed-thrust throttle stages

Solves the calibrated laws of minimal_model.py at FIXED thrust demand
(the 200 V anchor's measured 13.65 nN) for the throttle-curve voltages
below the committed frontier: 125 V (predicted specific-power valley),
92.4 V (left arm), 78 V (floor).  The output table is the pre-registration
source for `future_work/UCURVE_PLAN.md` and the
`i_beam` provenance for the three `capstone.ucurve_*` stage configs.

THE DELIBERATE OPTIMISM, stated once and inherited by the plan: the escape
fraction entering the solve is the FRONTIER-PATH interpolation esc(V)
(96.12 / 98.44 / 98.99 % at 100 / 200 / 300 V, clamped below 100 V).  That
path holds perveance fixed at I/I_CL = 1.46; the fixed-thrust slice does
not.  If beam optics degrade as I/I_CL grows -- the left-arm-tax
hypothesis -- the delivered thrust falls SHORT of the 13.65 nN demand and
the shortfall itself is the measurement.  This script therefore predicts
the H1 ("frontier optimism") branch exactly and quantifies, per stage, how
far outside the validated perveance envelope the commanded current sits.

Model contract (MODEL.md section 9) applies: nothing here feeds an
acceptance gate.  The commanded current is a config input like any other;
the gates that certify the runs live in each stage's acceptance.yaml.

USAGE
  python model/ucurve_targeting.py            # table on stdout
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from minimal_model import Calibration, K_PER_EV, R_EMIT, i_cl_mA  # noqa: E402

F_DEMAND_NN = 13.65          # the 200 V anchor's measured thrust (metrics.json)
VOLTAGES_V = (125.0, 92.4, 78.0)
ANCHOR_V = 200.0             # shown for orientation only


def fixed_thrust_point(cal: Calibration, V: float, F_nN: float = F_DEMAND_NN,
                       iters: int = 400, damp: float = 0.35) -> dict:
    """Damped fixed-point solve: I from the thrust law, phi from collection."""
    phi = 5.0
    esc = float(cal.esc_of_V(V))
    for _ in range(iters):
        I_mA = F_nN / (cal.cF * math.sqrt(cal.kappa * max(V - phi, 1.0)))
        phi_new = float(cal.phi_of_Iesc(esc * I_mA * 1e-3, cal.n0, cal.Te0_K))
        step = phi_new - phi
        phi += damp * step
        if abs(step) < 1e-6:
            break
    I_mA = F_nN / (cal.cF * math.sqrt(cal.kappa * max(V - phi, 1.0)))
    KE_eV = cal.kappa * (V - phi)
    P_mW = I_mA * V
    icl = float(i_cl_mA(V))
    return dict(V=V, I_mA=I_mA, phi_V=phi, chi=phi / cal.kTe0_eV, KE_eV=KE_eV,
                esc=esc, P_mW=P_mW, P_over_F=P_mW / F_nN,
                I_CL_mA=icl, perveance=I_mA / icl,
                over_ceiling=I_mA / (R_EMIT * icl))


def main() -> None:
    cal = Calibration()
    print(f"fixed-thrust targeting at F = {F_DEMAND_NN} nN "
          f"(alpha = {cal.alpha:.4f}, c_F = {cal.cF:.4f}, "
          f"kappa = {cal.kappa:.4f}, betaA = {cal.betaA*1e4:.3f} cm^2)")
    print(f"escape model: frontier-path interpolation, clamped to "
          f"{100*cal.esc_f[0]:.2f} % below {cal.esc_V[0]:.0f} V  "
          f"(H1 branch; see module docstring)")
    print()
    hdr = (f"{'V [V]':>7} {'I [mA]':>8} {'phi [V]':>8} {'chi':>6} "
           f"{'KE [eV]':>8} {'P [mW]':>7} {'P/F':>6} {'I_CL':>7} "
           f"{'I/I_CL':>7} {'I/ceil':>7}")
    print(hdr)
    for V in VOLTAGES_V + (ANCHOR_V,):
        p = fixed_thrust_point(cal, V)
        tag = "  <- committed anchor (orientation)" if V == ANCHOR_V else ""
        print(f"{p['V']:7.1f} {p['I_mA']:8.4f} {p['phi_V']:8.2f} "
              f"{p['chi']:6.0f} {p['KE_eV']:8.1f} {p['P_mW']:7.1f} "
              f"{p['P_over_F']:6.2f} {p['I_CL_mA']:7.4f} "
              f"{p['perveance']:7.2f} {p['over_ceiling']:7.2f}{tag}")
    print()
    print("I/I_CL is the planar Child-Langmuir perveance ratio; the validated")
    print("frontier path holds it at 1.46 (the measured non-planar ratio's")
    print("ceiling).  'I/ceil' is the commanded current over that measured")
    print("ceiling r_emit*I_CL -- above 1.0 the emitter is commanded past the")
    print("only regime any committed run has validated.")


if __name__ == "__main__":
    main()
