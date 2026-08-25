#!/usr/bin/env python3
"""Figure: the PIC validation ladder and the characterization spokes.

Schematic (not data-encoded). Nine ladder stages climb a staircase from the
vacuum electron gun to the full floating thruster (the 200 V anchor). Eight
characterization spokes fan out from that anchor; each moves one physics axis
and keeps everything else verbatim. Numbers are the headline result of each
stage / spoke as reported in README.md and pic_sims/ladder/LADDER_SUMMARY.md.

    python3 paper/figs/make_ladder.py
    -> paper/imgs/ladder_characterization.png
"""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "imgs" / "ladder_characterization.png"

# group colours (kept from the previous version of this figure so the README reads the same)
BLUE = "#1F4FD8"     # electron gun
RED = "#C8281E"      # current collection
AMBER = "#E07B00"    # capstone
GREEN = "#1E8A2E"    # characterization
INK, MUTED = "#1A1C20", "#6A6F78"

# (label, headline result, group colour) -- bottom to top
LADDER = [
    ("negative cathode",   "35 µV error on 100 V",                BLUE),
    ("electron gun",       "κ = 0.97 / 0.90 / 1.00 as predicted",  BLUE),
    ("voltage bracket",    "0.006 pp spread, 200–300 V",           BLUE),
    ("thermal current",    "within 1 % of theory",                 RED),
    ("spacecraft biased 3 V",  "0.85 of OML ceiling",              RED),
    ("spacecraft biased 10 V", "0.81 of ceiling, sheath 4.1→6.9 mm", RED),
    ("spacecraft floating", "−0.251 V, inside two-model bracket",  RED),
    ("two-node Laplace",   "exact Laplace, 0.0 V violation",       AMBER),
]
ANCHOR = ("full thruster chipsat", "200 V  ·  13.65 nN")

# (label, axis changed, headline result) -- drawn left to right across the fan
SPOKES = [
    ("low_power",          "100 V",              "3.42 nN,  φ = 5.4 V"),
    ("high_thrust",        "300 V",              "30.13 nN,  φ = 36.3 V"),
    ("350V_400km",         "350 V",              "40.48 nN,  φ = 48.3 V (on 50 V limit)"),
    ("350V_400km_slender", "350 V, slender",    "43.33 nN,  φ = 14.0 V"),
    ("slender_body",       "slender body",       "14.22 nN,  φ = 4.4 V"),
    ("thin_plasma",        "n₀ / 3",       "12.39 nN,  φ = 42.5 V"),
    ("magnetized_1x",      "B = 30 µT", "13.64 nN — null, anchor unchanged"),
    ("magnetized_10x",     "B = 300 µT",         "−11 % thrust,  φ +33 V"),
]

fig, ax = plt.subplots(figsize=(14.0, 8.6))
ax.set_xlim(-0.8, 17.6)
ax.set_ylim(-0.4, 11.2)
ax.axis("off")

# ---------------------------------------------------------------- staircase
STEP_W, STEP_H = 1.05, 0.72
x0, y0 = 1.6, 0.0
xs, ys = [x0], [y0]
for i in range(len(LADDER) + 1):
    xs += [x0 + (i + 1) * STEP_W, x0 + (i + 1) * STEP_W]
    ys += [y0 + i * STEP_H, y0 + (i + 1) * STEP_H]
xs.append(xs[-1] + 0.5)
ys.append(ys[-1])
ax.plot(xs, ys, color=INK, lw=2.0, solid_joinstyle="miter", zorder=2)

for i, (label, result, colour) in enumerate(LADDER):
    # label sits on the tread of step i, just left of the riser that leads up to step i+1
    tx = x0 + (i + 1) * STEP_W - 0.08
    ty = y0 + i * STEP_H
    ax.text(tx, ty + 0.34, label, ha="right", va="center", fontsize=13, color=colour,
            fontweight="bold")

# anchor box on the top tread
n = len(LADDER)
ax_x = x0 + (n + 1) * STEP_W + 0.25
ax_y = y0 + n * STEP_H
box_w, box_h = 4.2, 1.0
box = FancyBboxPatch((ax_x - box_w / 2, ax_y + 0.10), box_w, box_h,
                     boxstyle="round,pad=0.04,rounding_size=0.14",
                     fc="#FFF4E5", ec=AMBER, lw=2.0, zorder=3)
ax.add_patch(box)
ax.text(ax_x, ax_y + 0.10 + box_h * 0.68, ANCHOR[0], ha="center", va="center", fontsize=14,
        color=AMBER, fontweight="bold", zorder=4)
ax.text(ax_x, ax_y + 0.10 + box_h * 0.27, ANCHOR[1], ha="center", va="center", fontsize=11,
        color=INK, zorder=4)

# ---------------------------------------------------------------- spokes (two columns)
hub = (ax_x, ax_y + 0.10 + box_h + 0.05)
ROW_DY, Y_BASE = 1.05, hub[1] + 0.55
COL_DX = 2.9   # dot offset from the hub, left column negative / right column positive
for k, (name, axis, result) in enumerate(SPOKES):
    col, row = divmod(k, 4)             # first four spokes left, last four right
    side = -1 if col == 0 else 1
    dx, dy = side * COL_DX, Y_BASE + row * ROW_DY
    ax.plot([hub[0], hub[0] + dx], [hub[1], dy], color=GREEN, lw=1.6, zorder=1)
    ax.plot(hub[0] + dx, dy, "o", ms=4.5, color=GREEN, zorder=2)
    tx = hub[0] + dx + side * 0.18
    ha = "right" if side < 0 else "left"
    ax.text(tx, dy + 0.06, name, ha=ha, va="bottom", fontsize=12.5, color=GREEN,
            fontweight="bold", family="monospace")
    ax.text(tx, dy - 0.08, axis, ha=ha, va="top", fontsize=10.5, color=INK)

# ---------------------------------------------------------------- legend / key
kx, ky = -0.6, 10.9
for label, colour in [("characterization (8 spokes)", GREEN),
                      ("capstone", AMBER),
                      ("current collection", RED),
                      ("electron gun", BLUE)]:
    ax.text(kx, ky, label, fontsize=13, color=colour, va="center")
    ky -= 0.55

fig.tight_layout()
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=170, facecolor="white")
print(f"wrote {OUT}")
