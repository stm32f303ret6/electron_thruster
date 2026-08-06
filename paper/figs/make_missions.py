#!/usr/bin/env python3
"""Mission-corridor figure from the committed model/results/mission_summary.json."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sums = json.loads((REPO / "model" / "results" / "mission_summary.json").read_text())

order = ["400km_station_keeping_chipsat", "400km_lateral_station_keeping_chipsat",
         "500km_station_keeping_chipsat", "550km_station_keeping_chipsat",
         "600km_station_keeping_chipsat"]
labels = ["400 axial", "400 lateral", "500", "550", "600"]
S = {s["mission"]: s for s in sums}
duty = [S[m]["duty_cycle_needed_pct"] for m in order]
pmean = [S[m]["P_mean_mW"] for m in order]
feas = [S[m]["feasible_pct"] for m in order]

x = np.arange(len(order))
fig, ax = plt.subplots(1, 2, figsize=(9.0, 3.2))

b = ax[0].bar(x, duty, 0.6, color=["tab:red" if d > 100 else "tab:blue" for d in duty])
ax[0].axhline(100, c="k", lw=0.8, ls="--")
ax[0].text(-0.35, 104, "impulse budget closes below this line", fontsize=7)
for xi, d, f in zip(x, duty, feas):
    ax[0].text(xi, d + 3, f"{f:.0f}%\nfeas.", ha="center", fontsize=7)
ax[0].set_xticks(x, labels)
ax[0].set_ylabel("duty cycle needed [%]")
ax[0].set_xlabel("altitude [km] / pose")
ax[0].set_ylim(0, 165)

ax[1].bar(x, pmean, 0.6, color=["tab:red" if p > 30 else "tab:green" for p in pmean])
ax[1].axhline(30, c="k", lw=0.8, ls="--")
ax[1].text(1.6, 33, "body-mounted solar harvest (~30 mW)", fontsize=7)
ax[1].set_xticks(x, labels)
ax[1].set_ylabel("mean power at demanded thrust [mW]")
ax[1].set_xlabel("altitude [km] / pose")

for a in ax:
    a.grid(alpha=0.25, lw=0.4, axis="y")
fig.tight_layout()
fig.savefig(Path(__file__).parent / "missions.pdf")
print("wrote missions.pdf")
