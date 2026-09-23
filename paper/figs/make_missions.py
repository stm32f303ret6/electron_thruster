#!/usr/bin/env python3
"""Mission figure: free fall vs station keeping, and the power to hold altitude.

(a) The slender can (3.1 g) on the sun-synchronous orbit in 2024, thruster off:
    daily-mean altitude until re-entry, from the orbit_sims free-fall runs; the
    dashed lines are the same orbits held by the thruster, labelled with the
    year-mean beam power.
(b) Year-mean beam power to hold altitude, solar maximum (2024) and minimum
    (2019): line = median of the three orbit families, band = their range.

Reads the committed model/results/{mission_summary,altitude_hold}.json and the
free-fall CSVs (regenerable: python3 orbit_sims/run_station_keeping.py <case>).
Writes missions.pdf (paper) and ../imgs/missions.png (README).
"""
import csv
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
CASES = REPO / "orbit_sims" / "validation_cases"
S = {s["mission"]: s for s in json.loads((REPO / "model/results/mission_summary.json").read_text())}
HOLD = json.loads((REPO / "model/results/altitude_hold.json").read_text())

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
RAMP = {400: "#86b6ef", 500: "#3987e5", 550: "#1c5cab", 600: "#0d366b"}   # ordinal blue
MAX_C, MIN_C = "#2a78d6", "#eb6834"                                        # categorical 1, 2
ALTS = (400, 500, 550, 600, 650, 700)
SUF = {"eq": "", "iss": "_iss", "sso": "_sso"}

plt.rcParams.update({"font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.linewidth": 0.6})


def daily_altitude(case):
    rows = list(csv.DictReader(open(CASES / case / "results" / "free_fall.csv")))
    t0 = datetime.fromisoformat(rows[0]["timestamp_utc"])
    t = np.array([(datetime.fromisoformat(r["timestamp_utc"]) - t0).total_seconds() for r in rows])
    h = np.array([float(r["altitude_km"]) for r in rows])
    day = (t // 86400).astype(int)
    n = np.bincount(day)
    keep = n > 0
    return (np.arange(len(n))[keep] + 0.5) / 365.25, (np.bincount(day, h)[keep] / n[keep])


fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.1, 2.75), gridspec_kw={"width_ratios": [1.15, 1]})

# (a) free fall vs held -------------------------------------------------------
FF = {f["case"]: f for f in HOLD["free_fall"]}
for alt, c in RAMP.items():
    case = f"{alt}km_free_fall_slender_sso"
    yr, h = daily_altitude(case)
    ax.plot(yr, h, color=c, lw=1.6, label=f"{alt} km")
    ax.plot(yr[-1], h[-1], "o", color=c, ms=4.5, mec="white", mew=0.8)
    s = S[f"{alt}km_station_keeping_slender_sso"]
    if s["V_over_tested_pct"] < 5.0:          # held inside the tested envelope
        # the held orbit is this orbit: its mean altitude, not the nominal one
        # (a circular SSO sits ~15 km higher on average over the oblate Earth)
        ax.hlines(h[0], 0, 2.5, colors=c, linestyles=(0, (4, 2)), lw=1.0)
        ax.text(2.48, h[0] + 6, f"held, {s['P_mean_mW']:.0f} mW", ha="right", va="bottom",
                fontsize=6.5, color=INK2)
    days = FF[case]["lifetime_days"]
    ax.text(yr[-1] + 0.04, 150 if alt != 600 else 190,
            f"{days:.0f} d" if days < 365 else f"{days/365.25:.1f} yr",
            fontsize=6.5, color=INK, ha="left")
ax.set_xlim(0, 2.5)
ax.set_ylim(100, 660)
ax.set_xlabel("years from 1 Jan 2024")
ax.set_ylabel("daily-mean altitude [km]")
ax.set_title("(a) 3.1 g slender can, sun-synchronous, 2024", fontsize=8, color=INK, loc="left")
ax.legend(title="start, thruster off", fontsize=6.5, title_fontsize=6.5, frameon=False,
          loc="lower left", bbox_to_anchor=(0.46, 0.02))

# (b) power to hold, solar max vs min ------------------------------------------
for ep, es, c, name in (("2024", "", MAX_C, "2024 (solar max)"), ("2019", "_2019", MIN_C, "2019 (solar min)")):
    P = np.array([[S[f"{a}km_station_keeping_slender{SUF[o]}{es}"]["P_mean_mW"] for o in SUF] for a in ALTS])
    bx.fill_between(ALTS, P.min(1), P.max(1), color=c, alpha=0.18, lw=0)
    bx.plot(ALTS, np.median(P, 1), "-o", color=c, lw=1.6, ms=4.5, mec="white", mew=0.8, label=name)
    bx.text(652, np.median(P[ALTS.index(650)]) * (2.0 if ep == "2024" else 0.36), ep,
            fontsize=6.5, color=INK, ha="center")
    over = [a for a in ALTS if max(S[f"{a}km_station_keeping_slender{SUF[o]}{es}"]["duty_cycle_needed_pct"]
                                   for o in SUF) > 95.0]
    for a in over:
        bx.plot(a, np.median(P[ALTS.index(a)]), "o", ms=7, mfc="none", mec=INK, mew=0.8)
budget = HOLD["budget_mW"]
bx.axhline(budget, color=INK2, lw=0.8, ls=(0, (1, 2)))
bx.text(702, budget * 1.12, f"body-mounted solar, {budget:.0f} mW", ha="right", fontsize=6.5, color=INK2)
bx.text(404, 470, "needs >350 V", fontsize=6.5, color=INK, ha="left")
bx.set_yscale("log")
bx.set_ylim(0.05, 1000)
bx.set_xlabel("altitude [km]")
bx.set_ylabel("year-mean beam power [mW]")
bx.set_title("(b) power to hold altitude, three orbit families", fontsize=8, color=INK, loc="left")
bx.legend(fontsize=6.5, frameon=False, loc="lower left")

for a in (ax, bx):
    a.grid(color=GRID, lw=0.5)
    a.set_axisbelow(True)
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
fig.tight_layout(w_pad=1.5)
out = Path(__file__).parent
fig.savefig(out / "missions.pdf")
fig.savefig(out.parent / "imgs" / "missions.png", dpi=200)
print("wrote missions.pdf and ../imgs/missions.png")
