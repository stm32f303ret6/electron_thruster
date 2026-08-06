#!/usr/bin/env python3
"""Figure: the momentum-ledger control volume, at the measured operating point.

Schematic (not data-encoded): the craft + a control-volume boundary around it,
with every momentum-flux term drawn as an arrow crossing that boundary. Solid
arrows are PARTICLE momentum flux (measured directly from scraped-particle
sums); the dashed arrow is the FIELD force on the craft (computed from rho*E
and Maxwell stress) -- solid-vs-dashed is the primary encoding so the figure
reads correctly in black-and-white print; color is secondary reinforcement.

    conda activate tudat-sk
    python paper/figs/make_ledger.py
"""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = pathlib.Path(__file__).resolve()

BLUE = "#3557A7"     # particle momentum flux (matches iv_staircase.py)
AMBER = "#B5651D"    # field force -- CVD-safe against BLUE (hue + lightness both differ)
INK, MUTED = "#1A1C20", "#5A5F6A"
CV_GRAY = "#9AA0AA"

fig, ax = plt.subplots(figsize=(6.4, 3.6))
ax.set_xlim(0, 10); ax.set_ylim(0, 6.2)
ax.axis("off")

# control-volume boundary (dashed box around the craft + near-field)
cv = FancyBboxPatch((1.3, 1.0), 5.4, 4.0, boxstyle="round,pad=0.05,rounding_size=0.15",
                     fc="none", ec=CV_GRAY, lw=1.3, ls=(0, (5, 3)), zorder=1)
ax.add_patch(cv)
ax.annotate("control volume", xy=(1.5, 1.25), fontsize=8, color=CV_GRAY, style="italic")

# the craft body
body = FancyBboxPatch((2.6, 2.3), 2.6, 1.4, boxstyle="round,pad=0.02,rounding_size=0.12",
                       fc="#EDEFF3", ec=INK, lw=1.3, zorder=2)
ax.add_patch(body)
ax.annotate("craft\n(cold gun + aperture)", xy=(3.9, 3.0), ha="center", va="center",
            fontsize=8.5, color=INK)

def arrow(p0, p1, color, style, lw, label, label_xy, label_ha="left"):
    a = FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=14,
                        color=color, lw=lw, linestyle=style, zorder=3)
    ax.add_patch(a)
    ax.annotate(label, xy=label_xy, fontsize=8.3, color=INK, ha=label_ha, va="center")

# F_emit: gun reaction inside the craft (small, particle flux, solid)
arrow((3.1, 3.5), (3.7, 3.5), BLUE, "-", 1.4,
      "$F_\\mathrm{emit}=+0.40$ nN", (3.75, 3.55))

# F_out (escaped beam, dominant, solid, crosses the CV boundary to the right)
arrow((5.2, 3.0), (7.6, 3.0), BLUE, "-", 3.0,
      "$F_\\mathrm{out}=+17.53$ nN\n(escaped beam, all species)", (7.7, 3.0))

# F_dep (ambient impact channel, particle flux, solid, entering from outside plasma)
arrow((0.6, 4.4), (2.6, 3.35), BLUE, "-", 1.8,
      "$F_\\mathrm{dep}=+2.91$ nN\n(ambient e$^-$/ion impact)", (0.0, 5.35), label_ha="left")

# F_em(craft): field pull, dashed, drawn OUTSIDE the CV pointing at the craft
arrow((5.6, 1.7), (3.9, 2.3), AMBER, (0, (4, 2)), 2.2,
      "$F_\\mathrm{em}(\\mathrm{craft})=-20.0$ nN\n(field pull, from $\\rho E_z$ + stress)",
      (5.7, 1.35))

# resultant closed thrust, drawn as a bold outlined arrow below
res = FancyArrowPatch((3.9, 0.55), (1.3, 0.55), arrowstyle="-|>", mutation_scale=16,
                      color=INK, lw=2.4, zorder=4)
ax.add_patch(res)
ax.annotate("closed thrust $= 17.13$ nN $= F_\\mathrm{beam} - 2.3\\%$",
            xy=(1.2, 0.55), fontsize=9, color=INK, ha="right", va="center",
            fontweight="bold")

# legend (style, not color-only -- readable in grayscale)
ax.plot([], [], color=BLUE, lw=2, ls="-", label="particle momentum flux (measured)")
ax.plot([], [], color=AMBER, lw=2, ls=(0, (4, 2)), label="field force (computed)")
ax.legend(loc="lower right", frameon=False, fontsize=8, bbox_to_anchor=(1.02, 0.02))

ax.set_title("Momentum ledger at the measured operating point\n"
             "(0.217 mA / 800 V, tail-averaged)", fontsize=9.5, color=INK, pad=6)

out = HERE.parent / "ledger_diagram.pdf"
fig.savefig(out, bbox_inches="tight")
fig.savefig(out.with_suffix(".png"), dpi=180, bbox_inches="tight")
print("wrote", out)
