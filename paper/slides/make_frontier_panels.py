#!/usr/bin/env python3
"""Slide figures: three standalone frontier panels (one per slide).

Produces:
  figs2/frontier_thrust.pdf  — thrust vs supply voltage
  figs2/frontier_phi.pdf     — float discrimination (alpha test)
  figs2/frontier_fp.pdf      — thrust per watt vs voltage
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "model"))
from minimal_model import Calibration, R_EMIT, i_cl_mA, j_the, K_PER_EV

cal = Calibration()
A = cal.anchors
V_m = np.array([a["V"] for a in A])
F_m = np.array([a["F_nN"] for a in A])
phi_m = np.array([a["phi_V"] for a in A])
I_m = np.array([a["I_mA"] for a in A])
P_m = I_m * V_m * 1e-3 * 1e3   # mW
FP_m = F_m / P_m                # nN/mW = uN/W

kTe = cal.kTe0_eV
j0 = float(j_the(cal.n0, cal.Te0_K))
Iesc200 = A[1]["esc"] * A[1]["I_mA"] * 1e-3
chi200 = A[1]["phi_V"] / kTe

Vg = np.linspace(90, 320, 200)
esc_g = cal.esc_of_V(np.clip(Vg, 100, 300))
Iesc_g = esc_g * R_EMIT * i_cl_mA(Vg) * 1e-3

INK = "#1A1C20"
MUTED = "#5A5F6A"
BLUE = "#3557A7"
OUT = Path(__file__).parent / "figs2"


def style_ax(ax):
    ax.grid(alpha=0.2, lw=0.4)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=10)


def phi_law(alpha):
    C = Iesc200 / (1 + chi200) ** alpha
    return kTe * ((Iesc_g / C) ** (1 / alpha) - 1)


# --- Panel 1: thrust vs V ------------------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 4.0))
F_model = cal.cF * R_EMIT * i_cl_mA(Vg) * np.sqrt(cal.kappa * (Vg - phi_law(cal.alpha)))
ax.plot(Vg, F_model, "-", c="0.65", lw=1.8, label="model (two measured constants)")
ax.plot(V_m, F_m, "o", c=BLUE, ms=10, zorder=5, label="measured (all gates PASS)")
for v, f, p in zip(V_m, F_m, P_m):
    ax.annotate(f"{f:.1f} nN @ {p:.0f} mW",
                xy=(v, f), xytext=(8, -8), textcoords="offset points",
                fontsize=9, color=MUTED)
ax.set_xlabel("supply voltage  $V$  [V]", fontsize=11, color=INK)
ax.set_ylabel("beam thrust  $F$  [nN]", fontsize=11, color=INK)
ax.legend(fontsize=10, loc="upper left", frameon=False)
style_ax(ax)
fig.tight_layout()
fig.savefig(OUT / "frontier_thrust.pdf", bbox_inches="tight")
fig.savefig(OUT / "frontier_thrust.png", dpi=180, bbox_inches="tight")
print("wrote frontier_thrust.pdf")
plt.close()

# --- Panel 2: phi discrimination -----------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 4.0))
styles = [(1.0, ":", "#888888", r"$\alpha=1$ (linear)"),
          (0.82, "-", "#2A7F3F", r"$\alpha=0.82$ (pre-registered)"),
          (0.5, "--", "#888888", r"$\alpha=0.5$ (OML cylinder)")]
for alpha, ls, c, lab in styles:
    ax.plot(Vg, phi_law(alpha), ls, c=c, lw=1.8, label=lab)
ax.plot(V_m, phi_m, "o", c=BLUE, ms=10, zorder=5, label="measured")
ax.errorbar([300], [45], yerr=[[3], [3]], fmt="s", ms=6, c="tab:orange",
            capsize=4, zorder=4, label="300 V settled (extrapolated)")
ax.axhline(50, c="tab:red", lw=0.8, ls="-.")
ax.text(95, 52, "50 V benign-float limit", fontsize=9, c="tab:red")
for v, p in zip(V_m[:2], phi_m[:2]):
    ax.annotate(f"+{p:.1f} V", xy=(v, p), xytext=(8, 6),
                textcoords="offset points", fontsize=9, color=MUTED)
ax.annotate(f"+{phi_m[2]:.1f} V", xy=(V_m[2], phi_m[2]), xytext=(-35, 8),
            textcoords="offset points", fontsize=9, color=MUTED)
ax.set_ylim(0, 100)
ax.set_xlabel("supply voltage  $V$  [V]", fontsize=11, color=INK)
ax.set_ylabel(r"floating potential  $\varphi$  [V]", fontsize=11, color=INK)
ax.legend(fontsize=9, loc="upper left", frameon=False)
style_ax(ax)
fig.tight_layout()
fig.savefig(OUT / "frontier_phi.pdf", bbox_inches="tight")
fig.savefig(OUT / "frontier_phi.png", dpi=180, bbox_inches="tight")
print("wrote frontier_phi.pdf")
plt.close()

# --- Panel 3: F/P vs V ---------------------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 4.0))
FP_model = FP_m[1] * np.sqrt(V_m[1] / Vg)
ax.plot(Vg, FP_model, "-", c="0.65", lw=1.8,
        label=r"$F/P \propto 1/\sqrt{V}$ (anchored at 200 V)")
ax.plot(V_m, FP_m, "o", c=BLUE, ms=10, zorder=5, label="measured")
for v, fp in zip(V_m, FP_m):
    ax.annotate(f"{fp:.2f} " + r"$\mu$N/W",
                xy=(v, fp), xytext=(8, -8), textcoords="offset points",
                fontsize=9, color=MUTED)
ax.set_xlabel("supply voltage  $V$  [V]", fontsize=11, color=INK)
ax.set_ylabel(r"thrust per watt  [$\mu$N/W]", fontsize=11, color=INK)
ax.legend(fontsize=10, loc="upper right", frameon=False)
style_ax(ax)
fig.tight_layout()
fig.savefig(OUT / "frontier_fp.pdf", bbox_inches="tight")
fig.savefig(OUT / "frontier_fp.png", dpi=180, bbox_inches="tight")
print("wrote frontier_fp.pdf")
plt.close()
