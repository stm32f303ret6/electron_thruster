#!/usr/bin/env python3
"""Render the paper's dimensioned geometry and slender-body PIC dashboard.

Run in the warpx-cpu-mpich-dev environment from any directory:
    python paper/figs/make_submission_figs.py

Geometry uses frozen reference configs and the README's isometric drawing
primitives. The dashboard uses the same 200 V slender run as the README GIF;
its local openPMD field dumps and current ledger are required. Pass
--geometry-only to regenerate the vector geometry from committed files alone.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

from make_device_figs import dashboard

ROOT = Path(__file__).resolve().parents[2]
IMGS = ROOT / "paper" / "imgs"
COMPACT = ROOT / "pic_sims/ladder/capstone/2_chipsat_thruster"
SLENDER = ROOT / "pic_sims/characterization/slender_body"
COMPACT_ID = "20260801T142601Z_2f822a95"
SLENDER_ID = "20260806T011847Z_5670e54c"


def geometry_comparison():
    sys.path.insert(0, str(SLENDER / "viz"))
    from size_comparison import derive, draw_can
    from schematic import C30, S30, dim_line, iso, leader

    fig, ax = plt.subplots(figsize=(7.0, 3.25))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-14, 53)
    ax.set_ylim(-23, 10)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    perp = np.array([S30, -C30])

    for case, run_id, off, name in (
        (COMPACT, COMPACT_ID, (0.0, 0.0), "(a) Compact reference"),
        (SLENDER, SLENDER_ID, (39.0, 0.0), "(b) Slender main case"),
    ):
        cfg = yaml.safe_load((case / "reference_results" / run_id
                              / "config_used.yaml").read_text())
        geom = derive(cfg["geometry"])
        draw_can(ax, geom, off)
        ax.text(off[0] - 2, 9, name, ha="center", fontsize=9)
        p1 = np.array(iso(geom["zb"], -geom["rp"], 0)) + off
        p2 = np.array(iso(geom["zt"], -geom["rp"], 0)) + off
        dim_line(ax, p1, p2, f'{geom["L"]:.1f} mm', perp * 1.7,
                 fontsize=8)
        g1 = np.array(iso(geom["zfloort"], 2.8, 0)) + off
        g2 = np.array(iso(geom["zlidb"], 2.8, 0)) + off
        gap = geom["zlidb"] - geom["zfloort"]
        dim_line(ax, g1, g2, f"{gap:.1f} mm", perp * -0.7, fontsize=7)
        if case == COMPACT:
            a = np.array(iso(geom["zfloort"], 0, 0)) + off
            leader(ax, a, "cathode", (-2.2, -5), fontsize=8, color="#1a5276")
            a = np.array(iso(geom["zt"], -geom["r_slit"], 0)) + off
            leader(ax, a, "aperture", (4, 2.3), fontsize=8)
            ax.text(-11, -12, f'Diameter: {2 * geom["rp"]:.0f} mm\n(both bodies)',
                    fontsize=8)
        else:
            a = np.array(iso((geom["zb"] + geom["zt"]) / 2,
                             -geom["rp"], 0)) + off
            leader(ax, a, "collecting body", (6, -1.5), fontsize=8,
                   color="#a93226")

    # Dimension labels must remain readable where projection lines cross them.
    for label in ax.texts:
        label.set_bbox(dict(facecolor="white", edgecolor="none", pad=0.5))
        label.set_zorder(20)
    out = IMGS / "device_geometry.pdf"
    fig.savefig(out, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry-only", action="store_true")
    parser.add_argument("--run", type=Path,
                        default=SLENDER / "outputs" / SLENDER_ID)
    args = parser.parse_args()
    IMGS.mkdir(exist_ok=True)
    geometry_comparison()
    if not args.geometry_only:
        dashboard(args.run, IMGS / "dashboard_slender_200v.png")
