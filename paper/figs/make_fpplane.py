#!/usr/bin/env python3
"""Thrust-power plane: flight micropropulsion vs the empty nN/mW corner.
Data = the paper's comparison table (Table tab:comparison) ranges."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# (label, P_min W, P_max W, F_min N, F_max N, color)
SYSTEMS = [
    ("Cold gas",     1.0,   2.0,   1e-4,   1e-2,  "tab:gray"),
    ("PPT",          1.5,   2.5,   3e-5,   5e-5,  "tab:brown"),
    ("Electrospray", 16.5,  16.5,  2e-5,   8e-5,  "tab:green"),
    ("FEEP",         8.0,   40.0,  1e-5,   5e-4,  "tab:olive"),
    ("RF ion",       56.0,  80.0,  6.6e-4, 1.24e-3, "tab:purple"),
    ("Hall",         200.0, 250.0, 1.3e-2, 1.3e-2, "tab:red"),
]

fig, ax = plt.subplots(figsize=(7.2, 4.6))
for name, p0, p1, f0, f1, c in SYSTEMS:
    if p0 == p1:
        p0, p1 = p0 * 0.85, p1 * 1.15
    if f0 == f1:
        f0, f1 = f0 * 0.7, f1 * 1.4
    ax.fill([p0, p1, p1, p0], [f0, f0, f1, f1], color=c, alpha=0.35, lw=0)
    ax.text((p0 * p1) ** 0.5, f1 * 1.5, name, ha="center", fontsize=9, color=c)

# this work: chipsat frontier + predecessor point
ax.fill([12.1e-3, 189e-3, 189e-3, 12.1e-3],
        [3.42e-9, 3.42e-9, 30.13e-9, 30.13e-9],
        color="tab:blue", alpha=0.6, lw=0)
ax.plot([173.6e-3], [17.1e-9], "o", c="tab:blue", ms=6)
ax.text(5.0e-2, 6.5e-8, "this work\n(measured)", ha="center", fontsize=10,
        color="tab:blue", weight="bold")

# chipsat drag demand band
ax.axhspan(2e-9, 3.3e-8, color="k", alpha=0.06)
ax.text(1.1e-4, 6e-9, "gram-class drag demand\n(400-600 km)", fontsize=8,
        color="0.35", va="center")

ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlim(1e-4, 1e3); ax.set_ylim(1e-10, 1e-1)
ax.set_xlabel("power [W]")
ax.set_ylabel("thrust [N]")
ax.grid(alpha=0.2, which="both", lw=0.3)
fig.tight_layout()
fig.savefig(Path(__file__).parent / "fp_plane.pdf")
print("wrote fp_plane.pdf")
