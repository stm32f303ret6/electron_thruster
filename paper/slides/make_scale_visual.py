#!/usr/bin/env python3
"""Slide figure: size-cancellation visual.

Left panel: silhouettes of the slender Ø10mm body and a 3U CubeSat with
annotated dimensions and skin/ram ratios, showing they match.
Right panel: margin vs body at 600 km, highlighting that identical shape
ratios give identical margins regardless of absolute size.
"""
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "model"))
from minimal_model import Calibration
from scale_analysis import (BODIES, ALTITUDES, DRIVE_V,
                             SOLAR_CONSTANT, CELL_EFFICIENCY,
                             ILLUMINATION_DUTY, CELL_FRACTION_OF_SKIN,
                             drag_per_ram_area)

cal = Calibration()
KE = cal.kappa * (DRIVE_V - 3.0)
harvest_per_skin = SOLAR_CONSTANT * CELL_EFFICIENCY * ILLUMINATION_DUTY
fd = drag_per_ram_area()

INK = "#1A1C20"
MUTED = "#5A5F6A"
BLUE = "#3557A7"
GREEN = "#2A7F3F"

fig = plt.figure(figsize=(10.5, 4.2))
gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 1.0], wspace=0.35)

# --- Left panel: silhouettes ---
ax1 = fig.add_subplot(gs[0])
ax1.set_xlim(-1, 11)
ax1.set_ylim(-0.5, 7)
ax1.set_aspect("equal")
ax1.axis("off")

scale = 12.0

ax1.add_patch(Rectangle((1.5 - 0.005*scale/2, 0.5), 0.005*scale, 0.030*scale,
              fc=BLUE, alpha=0.25, ec=BLUE, lw=1.5))
ax1.annotate(r"$\varnothing$10 mm $\times$ 30 mm", xy=(1.5, 0.5 + 0.030*scale + 0.15),
             ha="center", fontsize=9, color=BLUE, fontweight="bold")
ax1.annotate("skin/ram = 14", xy=(1.5, 0.2), ha="center", fontsize=10,
             color=BLUE, fontweight="bold")
ax1.annotate("", xy=(1.5 - 0.005*scale/2 - 0.15, 0.5),
             xytext=(1.5 - 0.005*scale/2 - 0.15, 0.5 + 0.030*scale),
             arrowprops=dict(arrowstyle="<->", color=MUTED, lw=1))
ax1.text(1.5 - 0.005*scale/2 - 0.35, 0.5 + 0.015*scale, "30",
         fontsize=8, color=MUTED, ha="right", va="center", rotation=90)

cube_w = 0.10 * scale
cube_h = 0.30 * scale
ax1.add_patch(Rectangle((7.5 - cube_w/2, 0.5), cube_w, cube_h,
              fc=GREEN, alpha=0.25, ec=GREEN, lw=1.5))
ax1.annotate("10$\\times$10$\\times$30 cm", xy=(7.5, 0.5 + cube_h + 0.15),
             ha="center", fontsize=9, color=GREEN, fontweight="bold")
ax1.annotate("skin/ram = 14", xy=(7.5, 0.2), ha="center", fontsize=10,
             color=GREEN, fontweight="bold")
ax1.annotate("", xy=(7.5 - cube_w/2 - 0.15, 0.5),
             xytext=(7.5 - cube_w/2 - 0.15, 0.5 + cube_h),
             arrowprops=dict(arrowstyle="<->", color=MUTED, lw=1))
ax1.text(7.5 - cube_w/2 - 0.35, 0.5 + cube_h/2, "30",
         fontsize=8, color=MUTED, ha="right", va="center", rotation=90)

ax1.annotate("same ratio\n= same margin", xy=(4.5, 2.5), fontsize=11,
             ha="center", va="center", color=INK, fontweight="bold",
             bbox=dict(fc="white", ec="0.8", lw=0.8, pad=4))

ax1.set_title(r"$100\times$ scale difference, identical feasibility",
              fontsize=10, color=INK, pad=8)

# --- Right panel: margin by body at 600 km ---
ax2 = fig.add_subplot(gs[1])
names_short = [r"$\varnothing$10 squat", r"$\varnothing$10 slender",
               "1U face-on", "3U end-on", "6U end-on", "12U end-on"]
ratios = [sk/ar for _, ar, sk, _ in BODIES]
colors_bar = ["#888888", BLUE, "#888888", GREEN, "#B5651D", "#7A4FA0"]

margins_600 = []
for nm, ar, sk, _r in BODIES:
    I = (fd[600][0] * ar * 1e9) / (cal.cF * math.sqrt(KE))
    P = I * DRIVE_V * 1e-3
    avail = harvest_per_skin * sk * CELL_FRACTION_OF_SKIN
    margins_600.append(avail / P)

x = np.arange(len(BODIES))
bars = ax2.bar(x, margins_600, 0.6, color=colors_bar, alpha=0.5, edgecolor=colors_bar, lw=1.2)
ax2.axhline(1.0, color="tab:red", lw=1, ls="-", alpha=0.5)
ax2.text(5.35, 1.08, "closes", fontsize=8, color="tab:red", fontstyle="italic")

for i, (m, r) in enumerate(zip(margins_600, ratios)):
    ax2.text(i, m + 0.12, f"{m:.1f}×", ha="center", fontsize=9, color=INK, fontweight="bold")
    ax2.text(i, -0.35, f"s/r={r:.0f}", ha="center", fontsize=7.5, color=MUTED)

ax2.set_xticks(x)
ax2.set_xticklabels(names_short, fontsize=8, color=INK)
ax2.set_ylabel("margin at 600 km", fontsize=10, color=INK)
ax2.set_ylim(-0.6, 6.5)
ax2.grid(axis="y", alpha=0.2, lw=0.4)
for s in ("top", "right"):
    ax2.spines[s].set_visible(False)
ax2.tick_params(colors=MUTED, labelsize=9)
ax2.set_title("margin by shape (600 km, 100 V drive)", fontsize=10, color=INK, pad=8)

fig.tight_layout()
out = Path(__file__).parent / "figs2" / "scale_visual.pdf"
fig.savefig(out, bbox_inches="tight")
fig.savefig(out.with_suffix(".png"), dpi=180, bbox_inches="tight")
print(f"wrote {out}")
