#!/usr/bin/env python3
"""Slide figure: margin (example solar supply / demand) vs altitude, one curve per body shape.

Replaces the two-panel mission bar chart with a single, immediately readable
plot: shapes above the margin=1 line close; below it, they don't.
"""
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "model"))
from minimal_model import Calibration, j_the, K_PER_EV
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

BODY_STYLES = [
    (r"$\varnothing$10 mm squat (measured)",  ":", "#888888", "v", 5),
    (r"$\varnothing$10 mm slender (measured)", "-", "#3557A7", "D", 7),
    ("1U cube, face-on",                       "--", "#7A7A7A", "^", 5),
    ("3U end-on",                              "-", "#2A7F3F", "s", 7),
    ("6U end-on",                              "-.", "#B5651D", "o", 5),
    ("12U end-on",                             "--", "#7A4FA0", "p", 5),
]

fig, ax = plt.subplots(figsize=(8.5, 4.5))

alts = np.array(sorted(ALTITUDES))
for (nm, ar, sk, _r), (label, ls, color, marker, ms) in zip(BODIES, BODY_STYLES):
    margins = []
    for alt in alts:
        I = (fd[alt][0] * ar * 1e9) / (cal.cF * math.sqrt(KE))
        P = I * DRIVE_V * 1e-3
        avail = harvest_per_skin * sk * CELL_FRACTION_OF_SKIN
        margins.append(avail / P)
    ax.plot(alts, margins, ls=ls, color=color, lw=2, marker=marker, ms=ms,
            label=label, zorder=3)

ax.axhline(1.0, color="tab:red", lw=1.2, ls="-", alpha=0.6, zorder=1)
ax.text(402, 1.08, "example supply covers demand above this line", fontsize=9,
        color="tab:red", fontstyle="italic")

ax.fill_between([395, 605], 0, 1, color="tab:red", alpha=0.04, zorder=0)
ax.fill_between([395, 605], 1, 7, color="tab:green", alpha=0.04, zorder=0)

ax.set_xlabel("altitude  [km]", fontsize=11, color=INK)
ax.set_ylabel("margin  (example solar supply / demand)", fontsize=11, color=INK)
ax.set_xlim(395, 605)
ax.set_ylim(0, 6)
ax.set_xticks([400, 450, 500, 550, 600])
ax.legend(fontsize=8.5, loc="upper left", frameon=False, ncol=2)
ax.grid(alpha=0.2, lw=0.4)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.tick_params(colors=MUTED, labelsize=10)

fig.tight_layout()
out = Path(__file__).parent / "figs2" / "margin_corridor.pdf"
fig.savefig(out, bbox_inches="tight")
fig.savefig(out.with_suffix(".png"), dpi=180, bbox_inches="tight")
print(f"wrote {out}")
