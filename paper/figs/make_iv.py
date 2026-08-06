#!/usr/bin/env python3
"""Figure: the measured design space — I–V staircase and thrust points.

Reads the three promoted registry records directly (reproducible from the
repo), renders paper/figs/iv_staircase.pdf: two stacked panels sharing the
current axis (one axis per quantity — never dual-axis).

    conda activate tudat-sk
    python paper/figs/make_iv.py
"""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[2]
RUNS = ROOT / "steps" / "_shared" / "calibration" / "runs"

BLUE = "#3557A7"      # single-series hue (CVD-safe against the gray fit line)
GRAY = "#8A8F98"
INK, MUTED = "#1A1C20", "#5A5F6A"

recs = [yaml.safe_load(open(RUNS / f"{n}.yaml"))
        for n in ("femtosat_500km_pic", "femtosat_500km_i029",
                  "femtosat_500km_i036")]
I = np.array([r["drive"]["i_beam_mA"] for r in recs])
phi = np.array([r["measured"]["phi_body_V"] for r in recs])
F = np.array([r["measured"]["f_beam_nN"] for r in recs])
F_CLOSED = 17.129     # momentum-ledger closed thrust at the operating point

fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(4.6, 5.2), sharex=True,
    gridspec_kw={"hspace": 0.12})

for ax in (ax1, ax2):
    ax.grid(True, color="#E3E5E8", lw=0.6, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)

# --- panel 1: floating potential vs emitted current -----------------------
coef = np.polyfit(phi, I, 1)          # I(phi): the ~8.5 uA/V collection slope
phi_fit = np.linspace(phi[0] - 3, phi[-1] + 3, 10)
ax1.plot(np.polyval(coef, phi_fit), phi_fit, color=GRAY, lw=1.4,
         ls=(0, (4, 3)), zorder=2)
ax1.plot(I, phi, "o", color=BLUE, ms=7, zorder=3)
ax1.set_ylabel("body floating potential  [V]", color=INK, fontsize=10)
ax1.annotate(f"{coef[0]*1e3:.1f} µA/V", xy=(0.30, 37.5), color=MUTED,
             fontsize=9, rotation=32)
for x, y in zip(I, phi):
    ax1.annotate(f"+{y:.1f} V", xy=(x, y), xytext=(6, -11),
                 textcoords="offset points", fontsize=8.5, color=MUTED)

# --- panel 2: thrust vs emitted current -----------------------------------
ax2.plot(I, F, "o", color=BLUE, ms=7, zorder=3, label="$F_\\mathrm{beam}$ (measured)")
ax2.plot([I[0]], [F_CLOSED], "s", mfc="white", mec=BLUE, mew=1.6, ms=8,
         zorder=4, label="closed-ledger thrust")
k = np.polyfit(I, F, 1)
ax2.plot(np.polyval(np.polyfit(F, I, 1), np.linspace(F[0]-2, F[-1]+2, 10)),
         np.linspace(F[0]-2, F[-1]+2, 10), color=GRAY, lw=1.4,
         ls=(0, (4, 3)), zorder=2)
ax2.set_xlabel("emitted beam current  [mA]", color=INK, fontsize=10)
ax2.set_ylabel("thrust  [nN]", color=INK, fontsize=10)
ax2.annotate(f"{k[0]:.0f} nN/mA", xy=(0.315, 26.6), color=MUTED,
             fontsize=9, rotation=30)
ax2.legend(frameon=False, fontsize=8.5, loc="upper left",
           handletextpad=0.4, borderaxespad=0.2)

ax1.set_title("Measured operating points — Ø14 mm body, 800 V, "
              "$n_e = 7.9\\times10^{11}\\,\\mathrm{m^{-3}}$",
              fontsize=9.5, color=INK, pad=10)
fig.align_ylabels()
out = HERE.parent / "iv_staircase.pdf"
fig.savefig(out, bbox_inches="tight")
fig.savefig(out.with_suffix(".png"), dpi=180, bbox_inches="tight")
print("wrote", out)
