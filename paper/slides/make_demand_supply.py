#!/usr/bin/env python3
"""Slide figure: drag demand vs thruster capability at each altitude.

Shows that drag is nN, this device produces nN, and it costs mW —
the core value proposition in one glance.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "model"))
from minimal_model import Calibration

cal = Calibration()
A = cal.anchors

sums = json.loads((REPO / "model" / "results" / "mission_summary.json").read_text())
S = {s["mission"]: s for s in sums}

altitudes = [600, 550, 500, 400]
keys = ["600km_station_keeping_chipsat",
        "550km_station_keeping_chipsat",
        "500km_station_keeping_chipsat",
        "400km_station_keeping_chipsat"]

drag_mean = [S[k]["drag_mean_nN"] for k in keys]
drag_max  = [S[k]["drag_max_nN"] for k in keys]

F_measured = np.array([a["F_nN"] for a in A])
P_measured = np.array([a["I_mA"] * a["V"] for a in A])  # mW (mA * V = mW)
V_measured = np.array([a["V"] for a in A])

INK  = "#1A1C20"
MUTED = "#5A5F6A"
DRAG_COLOR = "#B85450"
THRUST_COLOR = "#3557A7"

fig, ax = plt.subplots(figsize=(9.5, 4.0))

y = np.arange(len(altitudes))
h = 0.35

for i, (alt, dm, dx) in enumerate(zip(altitudes, drag_mean, drag_max)):
    ax.barh(i, dx, height=h, left=0, color=DRAG_COLOR, alpha=0.18, lw=0)
    ax.barh(i, dm, height=h, left=0, color=DRAG_COLOR, alpha=0.45, lw=0)
    ax.plot(dm, i, "|", color=DRAG_COLOR, ms=14, mew=2)
    ax.annotate(f"{dm:.1f} nN mean", xy=(dm, i + 0.22), fontsize=8,
                color=DRAG_COLOR, ha="center", va="bottom")
    if dx < 95:
        ax.annotate(f"{dx:.0f} nN peak", xy=(dx, i - 0.22), fontsize=7,
                    color=DRAG_COLOR, ha="center", va="top", alpha=0.7)

ax.axvspan(F_measured[0], F_measured[-1], color=THRUST_COLOR, alpha=0.10, zorder=0)
for f, p, v in zip(F_measured, P_measured, V_measured):
    marker = ax.plot(f, 1.5, "D", color=THRUST_COLOR, ms=8, zorder=5)[0]
    ax.annotate(f"{f:.1f} nN\n{p:.0f} mW\n({v:.0f} V)",
                xy=(f, 1.5), xytext=(0, -28), textcoords="offset points",
                fontsize=7.5, color=THRUST_COLOR, ha="center", va="top",
                fontweight="bold")

ax.annotate("this device\n(measured frontier)", xy=(12, 2.55),
            fontsize=10, color=THRUST_COLOR, ha="center", fontweight="bold")
ax.annotate("", xy=(F_measured[0], 2.35), xytext=(F_measured[-1], 2.35),
            arrowprops=dict(arrowstyle="<->", color=THRUST_COLOR, lw=1.5))

ax.set_yticks(y)
ax.set_yticklabels([f"{a} km" for a in altitudes], fontsize=11, color=INK)
ax.set_xlabel("force  [nN]", fontsize=11, color=INK)
ax.set_xscale("log")
ax.set_xlim(0.8, 150)
ax.set_ylim(-0.6, 3.3)

ax.text(0.98, 0.97, "drag demand", fontsize=9, color=DRAG_COLOR,
        transform=ax.transAxes, ha="right", va="top", fontstyle="italic")

ax.grid(axis="x", alpha=0.2, which="both", lw=0.4)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.tick_params(colors=MUTED, labelsize=9)

fig.tight_layout()
out = Path(__file__).parent / "figs2" / "demand_supply.pdf"
fig.savefig(out, bbox_inches="tight")
fig.savefig(out.with_suffix(".png"), dpi=180, bbox_inches="tight")
print(f"wrote {out}")
