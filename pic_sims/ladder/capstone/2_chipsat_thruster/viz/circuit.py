#!/usr/bin/env python3
"""Equivalent-circuit diagram of the chipsat thruster current loop.

Pure schematic companion to schematic.py: cathode and body as circuit
nodes joined only by the supply, the e⁻ beam as a current source into
space, and the ambient plasma as the return path.  Makes the steady-state
current balance I_esc = I_amb,e − I_amb,i visually obvious.

    python circuit.py [--dpi 300] [--format png|pdf|svg]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from palette import AMBIENT, BEAM, BODY_EDGE, BODY_FILL, CATH_EDGE, CATH_FILL

CASE_DIR = Path(__file__).resolve().parent.parent

ESCAPE_PCT = 98.5  # float200 anchor (gate: >= 95 %) -- see acceptance.yaml


def draw(elec, beam, anchors, dpi, fmt="png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    v_supply = abs(elec["cathode_offset"])
    phi_body = anchors["phi_body_V"]
    phi_cath = phi_body - v_supply
    i_beam_mA = beam["i_beam"] * 1e3
    i_esc_mA = i_beam_mA * ESCAPE_PCT / 100.0
    p_mW = i_beam_mA * v_supply

    fig, ax = plt.subplots(figsize=(11, 8.5), facecolor="white")
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.9, 10)
    ax.set_aspect("equal")
    ax.axis("off")

    def box(x0, y0, x1, y1, fc, ec, title, sub):
        ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0,
                                    boxstyle="round,pad=0.08",
                                    facecolor=fc, edgecolor=ec, lw=1.8))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ax.text(cx, cy + 0.22, title, ha="center", va="center", fontsize=13,
                fontweight="bold", color=ec)
        ax.text(cx, cy - 0.28, sub, ha="center", va="center", fontsize=10,
                color=ec)

    # nodes
    box(1.5, 8.3, 8.5, 9.5, "0.93", "0.35",
        "AMBIENT IONOSPHERIC PLASMA", "φ ≈ 0 V (infinite reservoir)")
    box(0.8, 3.6, 3.8, 4.8, CATH_FILL, CATH_EDGE,
        "CATHODE", f"φ_body − {v_supply:.0f} V ≈ −{-phi_cath:.0f} V")
    box(6.2, 3.6, 9.2, 4.8, BODY_FILL, BODY_EDGE,
        "BODY / CHASSIS", f"floats to ≈ {phi_body:+.0f} V")

    xc, xb = 2.3, 7.7          # branch x-positions (cathode / body side)

    # beam branch: e⁻ leave the cathode into space
    ax.annotate("", xy=(xc, 8.22), xytext=(xc, 4.88),
                arrowprops=dict(arrowstyle="-|>", color=BEAM, lw=2.2,
                                ls="--", mutation_scale=25))
    ax.text(xc - 0.25, 6.55,
            f"e⁻ beam through the lid hole\n"
            f"I_esc ≈ {i_esc_mA:.2f} mA  (~{ESCAPE_PCT:.0f}% escapes)",
            ha="right", va="center", fontsize=10.5, color=BEAM,
            fontstyle="italic")

    # return branch: ambient electrons collected by the body
    ax.annotate("", xy=(xb, 4.88), xytext=(xb, 8.22),
                arrowprops=dict(arrowstyle="-|>", color=AMBIENT, lw=2.2,
                                ls="--", mutation_scale=25))
    ax.text(xb + 0.25, 6.55,
            "ambient e⁻ collected by the body\n"
            "I_ret = I_amb,e − I_amb,i",
            ha="left", va="center", fontsize=10.5, color=AMBIENT)

    # supply loop below: cathode -- battery -- body
    y_bus = 2.2
    gap_l, gap_r = 4.6, 5.4
    ax.plot([xc, xc, gap_l], [3.52, y_bus, y_bus], color=CATH_EDGE, lw=2.0,
            solid_capstyle="round")
    ax.plot([gap_r, xb, xb], [y_bus, y_bus, 3.52], color=BODY_EDGE, lw=2.0,
            solid_capstyle="round")
    # battery: short/thick = − (cathode side), long/thin = + (body side)
    ax.plot([gap_l, gap_l], [y_bus - 0.22, y_bus + 0.22], color=CATH_EDGE,
            lw=4.5)
    ax.plot([gap_r, gap_r], [y_bus - 0.45, y_bus + 0.45], color=BODY_EDGE,
            lw=1.8)
    ax.text(gap_l - 0.25, y_bus + 0.5, "−", fontsize=15, ha="center",
            color=CATH_EDGE, fontweight="bold")
    ax.text(gap_r + 0.25, y_bus + 0.5, "+", fontsize=15, ha="center",
            color=BODY_EDGE, fontweight="bold")
    ax.text(5.0, y_bus - 0.55,
            f"POWER SUPPLY  {v_supply:.0f} V   "
            f"(P = I_beam · {v_supply:.0f} V ≈ {p_mW:.0f} mW)",
            ha="center", va="top", fontsize=11.5, fontweight="bold")
    ax.text(5.0, y_bus - 1.1,
            "the only electrical link between cathode and body",
            ha="center", va="top", fontsize=9.5, color="0.4")

    # electron-flow direction markers on the supply loop (body → cathode)
    for x, y, dx, dy in ((6.4, y_bus, -0.01, 0.0), (3.4, y_bus, -0.01, 0.0),
                         (xb, 3.0, 0.0, -0.01), (xc, 2.9, 0.0, 0.01)):
        ax.annotate("", xy=(x + dx, y + dy), xytext=(x, y),
                    arrowprops=dict(arrowstyle="-|>", color="0.55", lw=1.0,
                                    mutation_scale=16))
    ax.text(5.0, 5.6, "electron flow\n(one closed loop)", ha="center",
            va="center", fontsize=10, color="0.55", fontstyle="italic")

    # the floating condition
    ax.text(5.0, -0.85,
            "steady state:  I_esc = I_amb,e − I_amb,i   (current balance "
            "gated ≤ 5%)\nthe body floats to the potential where the plasma "
            "return current matches the escaping beam",
            ha="center", va="bottom", fontsize=10.5, color="0.25",
            linespacing=1.6)

    fig.text(0.5, 0.97, "Chipsat Thruster — equivalent circuit",
             fontsize=17, fontweight="bold", ha="center", va="top")

    out = CASE_DIR / "viz" / f"circuit_2_chipsat_thruster.{fmt}"
    fig.savefig(str(out), dpi=dpi, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="equivalent-circuit diagram")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--format", choices=("png", "pdf", "svg"), default="png")
    args = ap.parse_args(argv)
    raw = yaml.safe_load((CASE_DIR / "config.yaml").read_text())
    acc = yaml.safe_load((CASE_DIR / "acceptance.yaml").read_text())
    targets = {g["metric"]: g.get("target")
               for g in acc["gates"] if "target" in g}
    anchors = {"phi_body_V": targets["phi_body_V"]}
    draw(raw["electrical"], raw["beam"], anchors, args.dpi, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
