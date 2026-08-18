#!/usr/bin/env python3
"""Frontier + collection-law discrimination figure.

Data comes from the committed calibration (model/minimal_model.py reads the
promoted reference_results metrics), so this figure regenerates from the repo
with no hand-typed numbers.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "model"))
from minimal_model import Calibration, R_EMIT, i_cl_mA, j_the, K_PER_EV

cal = Calibration()
A = cal.anchors
V_m = np.array([a["V"] for a in A])
F_m = np.array([a["F_nN"] for a in A])
phi_m = np.array([a["phi_V"] for a in A])
I_m = np.array([a["I_mA"] for a in A])

# The 350 V envelope extension (characterization.350V_400km, gated PASS
# 2026-08-17): plotted as a measured point but NOT used in the calibration,
# which stays fitted to the original three anchors.
import json as _json
_ext_dir = (Path(__file__).resolve().parents[2] / "pic_sims" / "characterization"
            / "350V_400km" / "reference_results" / "20260817T055536Z_acf6cf7b")
_ext = {m["id"]: m["value"]
        for m in _json.loads((_ext_dir / "metrics.json").read_text())["metrics"]}
V_m = np.append(V_m, 350.0)
F_m = np.append(F_m, _ext["f_beam_nN"])
phi_m = np.append(phi_m, _ext["phi_body_V"])
I_m = np.append(I_m, 0.793)            # frozen config: I_CL(350 V) * 1.46

P_m = I_m * V_m * 1e-3 * 1e3          # mW
FP_m = F_m / P_m                       # uN/W == nN/mW

kTe = cal.kTe0_eV
j0 = float(j_the(cal.n0, cal.Te0_K))
Iesc200 = A[1]["esc"] * A[1]["I_mA"] * 1e-3
chi200 = A[1]["phi_V"] / kTe

Vg = np.linspace(95, 370, 220)
esc_g = cal.esc_of_V(np.clip(Vg, 100, 300))
Iesc_g = esc_g * R_EMIT * i_cl_mA(Vg) * 1e-3   # frontier path current [A]


def phi_law(alpha):
    C = Iesc200 / (1 + chi200) ** alpha        # anchored at the 200 V point
    return kTe * ((Iesc_g / C) ** (1 / alpha) - 1)


fig, ax = plt.subplots(1, 3, figsize=(11.5, 3.4))

ax[0].plot(Vg, cal.cF * R_EMIT * i_cl_mA(Vg)
           * np.sqrt(cal.kappa * (Vg - phi_law(cal.alpha))), "-", c="0.6", lw=1,
           label=r"model, $I=1.46\,I_{\rm CL}$")
ax[0].plot(V_m, F_m, "o", c="tab:blue", ms=7, label="measured (gated PASS)")
ax[0].set_xlabel("supply voltage V [V]")
ax[0].set_ylabel(r"thrust $F_{\rm beam}$ [nN]")
ax[0].legend(fontsize=8, loc="upper left")

for alpha, style, lab in ((1.0, ":", r"$\alpha=1$ (linear, refuted)"),
                          (0.82, "-", r"$\alpha=0.82$ (pre-reg.\ winner)"),
                          (0.5, "--", r"$\alpha=0.5$ (refuted)")):
    ax[1].plot(Vg, phi_law(alpha), style, c="0.4", lw=1.2, label=lab)
ax[1].plot(V_m, phi_m, "o", c="tab:blue", ms=7, zorder=5, label="measured")
# settled-value extrapolation band at 300 V (late-slope decay, SCALING_LAWS 4)
ax[1].errorbar([300], [45], yerr=[[3], [3]], fmt="s", ms=4, c="tab:orange",
               capsize=3, zorder=4, label="300 V settled (extrap.)")
ax[1].axhline(50, c="tab:red", lw=0.8, ls="-.")
ax[1].text(102, 51.5, "benign-float design limit", fontsize=7, c="tab:red")
ax[1].set_ylim(0, 100)
ax[1].set_xlabel("supply voltage V [V]")
ax[1].set_ylabel(r"floating potential $\varphi$ [V]")
ax[1].legend(fontsize=7, loc="upper left")

ax[2].plot(Vg, FP_m[1] * np.sqrt(V_m[1] / Vg), "-", c="0.6", lw=1,
           label=r"$F/P \propto 1/\sqrt{V}$ (anchor 200 V)")
ax[2].plot(V_m, FP_m, "o", c="tab:blue", ms=7, label="measured")
ax[2].set_xlabel("supply voltage V [V]")
ax[2].set_ylabel(r"thrust per watt [$\mu$N/W]")
ax[2].legend(fontsize=8)

for a in ax:
    a.grid(alpha=0.25, lw=0.4)
fig.tight_layout()
fig.savefig(Path(__file__).parent / "frontier.pdf")
print("wrote frontier.pdf")
