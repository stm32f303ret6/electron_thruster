#!/usr/bin/env python3
"""B&W isometric views of the holed_anode test geometry.

One PNG per scenario showing the assembled cathode–anode–collector
geometry with scenario-specific dimensions and labels.

    python schematic.py [--dpi 300]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR))
from helpers import load_config, scenario_names

S = 1e3  # m -> mm
C30 = np.cos(np.radians(30))
S30 = np.sin(np.radians(30))
SIL_TOP = np.pi / 4
SIL_BOT = np.pi + np.pi / 4

TITLES = {
    "A_low_current_small_hole": "Scenario A — Low Current, Small Hole",
    "B_high_current_small_hole": "Scenario B — High Current, Small Hole",
    "C_high_current_big_hole": "Scenario C — High Current, Big Hole",
}


# ── isometric projection helpers ──────────────────────────────────────

def iso(x, y, z):
    x, y, z = np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)
    return C30 * (x - y), S30 * (x + y) + z


def ell(a, r, t0=0.0, t1=2 * np.pi, n=300):
    t = np.linspace(t0, t1, n)
    return iso(a, r * np.cos(t), r * np.sin(t))


def sil(a, r, angle):
    return iso(a, r * np.cos(angle), r * np.sin(angle))


def iso_dir():
    d = np.array([C30, S30])
    return d / np.linalg.norm(d)


# ── drawing primitives ────────────────────────────────────────────────

def draw_plate(ax, cx, r, thick):
    front = cx + thick / 2
    back = cx - thick / 2

    u, v = ell(back, r, SIL_TOP, SIL_BOT)
    ax.plot(u, v, "k-", lw=1.0)
    u, v = ell(back, r, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, "k--", lw=0.4, dashes=(3, 3))
    for angle in (SIL_TOP, SIL_BOT):
        uf, vf = sil(front, r, angle)
        ub, vb = sil(back, r, angle)
        ax.plot([uf, ub], [vf, vb], "k-", lw=1.0)
    u, v = ell(front, r)
    ax.plot(u, v, "k-", lw=1.6, zorder=3)


def draw_annular_plate(ax, cx, r_outer, r_inner, thick):
    """Draw an annular plate (disk with central hole) in isometric."""
    from matplotlib.patches import Polygon

    front = cx + thick / 2
    back = cx - thick / 2

    # outer boundary
    u, v = ell(back, r_outer, SIL_TOP, SIL_BOT)
    ax.plot(u, v, "k-", lw=1.0, zorder=3)
    u, v = ell(back, r_outer, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, "k--", lw=0.4, dashes=(3, 3), zorder=2)
    for angle in (SIL_TOP, SIL_BOT):
        uf, vf = sil(front, r_outer, angle)
        ub, vb = sil(back, r_outer, angle)
        ax.plot([uf, ub], [vf, vb], "k-", lw=1.0, zorder=3)

    # front face: hatched annulus (outer polygon + white hole)
    u_out, v_out = ell(front, r_outer)
    pts_out = list(zip(u_out, v_out))
    ax.add_patch(Polygon(pts_out, closed=True, facecolor="white",
                         edgecolor="black", lw=1.4, hatch="////",
                         zorder=5))
    u_in, v_in = ell(front, r_inner)
    pts_in = list(zip(u_in, v_in))
    ax.add_patch(Polygon(pts_in, closed=True, facecolor="white",
                         edgecolor="black", lw=1.2, zorder=6))

    # inner bore: back inner ellipse visible through the hole
    u, v = ell(back, r_inner, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, "k-", lw=0.7, zorder=4)
    u, v = ell(back, r_inner, SIL_TOP, SIL_BOT)
    ax.plot(u, v, "k--", lw=0.4, dashes=(3, 3), zorder=4)
    for angle in (SIL_TOP, SIL_BOT):
        uf, vf = sil(front, r_inner, angle)
        ub, vb = sil(back, r_inner, angle)
        ax.plot([uf, ub], [vf, vb], "k-", lw=0.7, zorder=4)


def draw_cylinder(ax, x0, x1, r):
    u, v = ell(x0, r, SIL_TOP, SIL_BOT)
    ax.plot(u, v, "k-", lw=0.8)
    u, v = ell(x0, r, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, "k--", lw=0.4, dashes=(3, 3))
    u, v = ell(x1, r)
    ax.plot(u, v, "k-", lw=1.4, zorder=3)
    for angle in (SIL_TOP, SIL_BOT):
        u0, v0 = sil(x0, r, angle)
        u1, v1 = sil(x1, r, angle)
        ax.plot([u0, u1], [v0, v1], "k-", lw=0.8)


def dim_line(ax, p1, p2, label, offset, fontsize=13):
    p1, p2 = np.array(p1), np.array(p2)
    n = np.array(offset)
    for p in (p1, p2):
        tip = p + n * 1.15
        ax.plot([p[0], tip[0]], [p[1], tip[1]], "k-", lw=0.35, clip_on=False)
    d1 = p1 + n
    d2 = p2 + n
    ax.annotate("", xy=(d2[0], d2[1]), xytext=(d1[0], d1[1]),
                arrowprops=dict(arrowstyle="<->", color="black", lw=0.6,
                                shrinkA=0, shrinkB=0), clip_on=False)
    mid = (d1 + d2) / 2
    ax.text(mid[0], mid[1], label, fontsize=fontsize, ha="center", va="center",
            color="black", clip_on=False,
            bbox=dict(facecolor="white", edgecolor="none", pad=2))


def leader(ax, anchor, text, offset, fontsize=12, **text_kw):
    anchor = np.array(anchor)
    tip = anchor + np.array(offset)
    ax.plot([anchor[0], tip[0]], [anchor[1], tip[1]], "k-", lw=0.5,
            clip_on=False)
    ax.plot(*anchor, "k.", ms=3, clip_on=False)
    ha = "left" if offset[0] > 0 else "right"
    pad = 0.15 if offset[0] > 0 else -0.15
    ax.text(tip[0] + pad, tip[1], text, fontsize=fontsize, ha=ha, va="center",
            color="black", clip_on=False, **text_kw)


# ── per-scenario drawing ─────────────────────────────────────────────

def draw_scenario(cfg, name, out, dpi):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    z0 = cfg.z_min * S
    z1 = cfg.z_max * S
    rm = cfg.r_max * S
    re = cfg.emit_radius * S
    rh = cfg.hole_radius * S
    az_front = cfg.anode_z_front * S
    az_thick = cfg.anode_thickness * S
    az_mid = az_front + az_thick / 2

    thick = 0.25

    fig, ax = plt.subplots(figsize=(16, 10), facecolor="white")
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.axis("off")

    # center/axis line
    u0, v0 = iso(z0 - 1.5, 0, 0)
    u1, v1 = iso(z1 + 1.5, 0, 0)
    ax.plot([u0, u1], [v0, v1], "k-.", lw=0.35, dashes=(8, 3, 2, 3),
            zorder=0)

    # cylinder domain boundary
    draw_cylinder(ax, z0, z1, rm)

    # cathode plate
    draw_plate(ax, z0 + thick / 2, rm, thick)

    # emission spot
    eu, ev = ell(z0 + thick + 0.01, re)
    pts = list(zip(eu, ev))
    ax.add_patch(Polygon(pts, closed=True, facecolor="white",
                         edgecolor="black", lw=1.2, hatch="....",
                         zorder=4))

    # anode plate (annular, with hole)
    draw_annular_plate(ax, az_mid, rm, rh, az_thick)

    # collector plate
    draw_plate(ax, z1 - thick / 2, rm, thick)

    # beam envelope (dashed cone, cathode to anode hole)
    beam_start = z0 + thick
    beam_end = z1 - thick
    spread = re * 1.2

    for angle in (SIL_TOP, SIL_BOT):
        us, vs = sil(beam_start, re, angle)
        ue, ve = sil(beam_end, spread, angle)
        ax.plot([us, ue], [vs, ve], "k--", lw=0.7, dashes=(6, 4), zorder=1)

    # beam arrows
    d = iso_dir()
    for frac in (0.15, 0.45, 0.78):
        x_a = beam_start + (beam_end - beam_start) * frac
        u_a, v_a = iso(x_a, 0, 0)
        ax.annotate("", xy=(u_a + d[0] * 0.4, v_a + d[1] * 0.4),
                    xytext=(u_a, v_a),
                    arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
                    zorder=1)

    # ── labels ────────────────────────────────────────────────────────

    # cathode
    uc, vc = iso(z0, 0, -rm)
    leader(ax, (uc, vc), "CATHODE\nV = −100 V", (-1.5, -1.5),
           fontsize=13, fontweight="bold")

    # emission spot
    ue, ve = iso(z0 + thick, -re * 0.6, re * 0.6)
    leader(ax, (ue, ve),
           f"Emission spot\nI = {cfg.beam_current*1e6:.0f} μA",
           (-2.5, 1.5), fontsize=11)

    # anode
    ua, va = iso(az_mid, 0, rm)
    leader(ax, (ua, va),
           f"ANODE (holed)\nV = {cfg.v_anode:.0f} V",
           (-1.0, 1.5), fontsize=13, fontweight="bold")

    # collector
    uc, vc = iso(z1, 0, -rm)
    leader(ax, (uc, vc), "COLLECTOR\nV = 0 V", (1.5, -1.5),
           fontsize=13, fontweight="bold")

    # beam
    ub, vb = iso((z0 + az_front) / 2, 0, re * 0.8)
    leader(ax, (ub, vb), "e⁻ beam", (0.5, 1.0), fontsize=11,
           fontstyle="italic")

    # axis label
    ua, va = iso(z1 + 1.0, 0, 0)
    ax.text(ua + 0.2, va, "axis of\nsymmetry", fontsize=9, ha="left",
            va="center", color="black", alpha=0.5, clip_on=False)

    # ── dimensions ────────────────────────────────────────────────────

    # axial length
    p1 = np.array(iso(z0, -rm, 0))
    p2 = np.array(iso(z1, -rm, 0))
    perp = np.array([S30, -C30])
    dim_line(ax, p1, p2, f"{(cfg.z_max - cfg.z_min)*S:.1f} mm",
             perp * 1.2, fontsize=12)

    # r_max (on collector)
    p1 = np.array(iso(z1, 0, 0))
    p2 = np.array(iso(z1, 0, rm))
    dim_line(ax, p1, p2, f"r = {rm:.1f} mm", np.array([1.0, 0.0]),
             fontsize=10)

    # hole radius (on anode front face)
    p1 = np.array(iso(az_mid + az_thick / 2, 0, 0))
    p2 = np.array(iso(az_mid + az_thick / 2, 0, rh))
    dim_line(ax, p1, p2, f"r_hole = {rh:.1f} mm", np.array([0.8, 0.3]),
             fontsize=10)

    # r_emit (on cathode face)
    p1 = np.array(iso(z0 + thick, 0, 0))
    p2 = np.array(iso(z0 + thick, 0, re))
    dim_line(ax, p1, p2, f"r_emit = {re:.1f} mm", np.array([-0.8, 0.0]),
             fontsize=10)

    # title
    title = TITLES.get(name, name)
    fig.text(0.5, 0.97, title,
             fontsize=18, fontweight="bold", ha="center", va="top",
             color="black")

    ax.autoscale()
    fig.savefig(str(out), dpi=dpi, bbox_inches="tight",
                facecolor="white", pad_inches=0.4)
    plt.close(fig)
    print(f"wrote {out}")


# ── main ──────────────────────────────────────────────────────────────

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="B&W isometric schematics")
    ap.add_argument("--dpi", type=int, default=300)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    config_path = CASE_DIR / "config.yaml"
    names = scenario_names(config_path)

    for name in names:
        cfg = load_config(config_path, scenario=name)
        out = CASE_DIR / f"schematic_{name}.png"
        draw_scenario(cfg, name, out, args.dpi)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
