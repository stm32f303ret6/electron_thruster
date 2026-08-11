#!/usr/bin/env python3
"""B&W isometric view of the negative_cathode test geometry.

Two-color (black on white) CAD-style drawing: assembled cathode–collector
cylinder with emission spot, beam envelope, dimensions, and labels.

    python schematic.py [--out PATH] [--dpi 300]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

CASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CASE_DIR))
from helpers import load_config

S = 1e3  # m -> mm
C30 = np.cos(np.radians(30))
S30 = np.sin(np.radians(30))
SIL_TOP = np.pi / 4          # silhouette angle (upper tangent)
SIL_BOT = np.pi + np.pi / 4  # silhouette angle (lower tangent)


# ── isometric projection helpers ──────────────────────────────────────

def iso(x, y, z):
    """Project (x=beam axis, y,z=radial) to 2D isometric."""
    x, y, z = np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)
    return C30 * (x - y), S30 * (x + y) + z


def ell(a, r, t0=0.0, t1=2 * np.pi, n=300):
    """Isometric ellipse arc for a circle of radius r at axial pos a."""
    t = np.linspace(t0, t1, n)
    return iso(a, r * np.cos(t), r * np.sin(t))


def sil(a, r, angle):
    """Single silhouette point."""
    return iso(a, r * np.cos(angle), r * np.sin(angle))


def iso_dir():
    """Unit direction vector along the beam axis in 2D isometric."""
    d = np.array([C30, S30])
    return d / np.linalg.norm(d)


# ── drawing primitives ────────────────────────────────────────────────

def draw_plate(ax, cx, r, thick, *, hatch_front=None):
    """Draw a thin disk (plate) in isometric."""
    front = cx + thick / 2
    back = cx - thick / 2

    # back ellipse — visible arc (top, from SIL_TOP to SIL_BOT through pi)
    u, v = ell(back, r, SIL_TOP, SIL_BOT)
    ax.plot(u, v, "k-", lw=1.0)

    # back ellipse — hidden arc
    u, v = ell(back, r, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, "k--", lw=0.4, dashes=(3, 3))

    # side tangent lines
    for angle in (SIL_TOP, SIL_BOT):
        uf, vf = sil(front, r, angle)
        ub, vb = sil(back, r, angle)
        ax.plot([uf, ub], [vf, vb], "k-", lw=1.0)

    # front ellipse (on top of everything)
    u, v = ell(front, r)
    if hatch_front:
        from matplotlib.patches import Polygon
        pts = list(zip(u, v))
        ax.add_patch(Polygon(pts, closed=True, facecolor="white",
                             edgecolor="black", lw=1.6, hatch=hatch_front,
                             zorder=3))
    else:
        ax.plot(u, v, "k-", lw=1.6, zorder=3)


def draw_cylinder(ax, x0, x1, r):
    """Draw the cylindrical domain boundary (wireframe)."""
    # back ellipse (at x0) — visible arc
    u, v = ell(x0, r, SIL_TOP, SIL_BOT)
    ax.plot(u, v, "k-", lw=0.8)
    # back ellipse — hidden arc
    u, v = ell(x0, r, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, "k--", lw=0.4, dashes=(3, 3))

    # front ellipse (at x1)
    u, v = ell(x1, r)
    ax.plot(u, v, "k-", lw=1.4, zorder=3)

    # silhouette tangent lines
    for angle in (SIL_TOP, SIL_BOT):
        u0, v0 = sil(x0, r, angle)
        u1, v1 = sil(x1, r, angle)
        ax.plot([u0, u1], [v0, v1], "k-", lw=0.8)


def dim_line(ax, p1, p2, label, offset, fontsize=13):
    """Engineering dimension line between two 2D points."""
    p1, p2 = np.array(p1), np.array(p2)
    n = np.array(offset)

    # extension lines
    for p in (p1, p2):
        tip = p + n * 1.15
        ax.plot([p[0], tip[0]], [p[1], tip[1]], "k-", lw=0.35, clip_on=False)

    # dimension line with arrows
    d1 = p1 + n
    d2 = p2 + n
    ax.annotate("", xy=(d2[0], d2[1]), xytext=(d1[0], d1[1]),
                arrowprops=dict(arrowstyle="<->", color="black", lw=0.6,
                                shrinkA=0, shrinkB=0),
                clip_on=False)

    # label
    mid = (d1 + d2) / 2
    ax.text(mid[0], mid[1], label, fontsize=fontsize, ha="center", va="center",
            color="black", clip_on=False,
            bbox=dict(facecolor="white", edgecolor="none", pad=2))


def leader(ax, anchor, text, offset, fontsize=12, **text_kw):
    """Label with a leader line from anchor point."""
    anchor = np.array(anchor)
    tip = anchor + np.array(offset)
    ax.plot([anchor[0], tip[0]], [anchor[1], tip[1]], "k-", lw=0.5,
            clip_on=False)
    ax.plot(*anchor, "k.", ms=3, clip_on=False)
    ha = "left" if offset[0] > 0 else "right"
    pad = 0.15 if offset[0] > 0 else -0.15
    ax.text(tip[0] + pad, tip[1], text, fontsize=fontsize, ha=ha, va="center",
            color="black", clip_on=False, **text_kw)


# ── main drawing ──────────────────────────────────────────────────────

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="B&W isometric schematic")
    ap.add_argument("--out", type=Path,
                    default=CASE_DIR / "viz" / "schematic_negative_cathode.png")
    ap.add_argument("--dpi", type=int, default=300)
    return ap.parse_args(argv)


def draw(cfg, out: Path, dpi: int):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    z0 = cfg.z_min * S   # -2
    z1 = cfg.z_max * S   # +2
    rm = cfg.r_max * S   # 2
    re = cfg.emit_radius * S  # 0.5

    thick = 0.25          # plate display thickness [mm]

    fig, ax = plt.subplots(figsize=(16, 10), facecolor="white")
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.axis("off")

    # ── center/axis line (dash-dot) ───────────────────────────────────
    u0, v0 = iso(z0 - 1.5, 0, 0)
    u1, v1 = iso(z1 + 1.5, 0, 0)
    ax.plot([u0, u1], [v0, v1], "k-.", lw=0.35, dashes=(8, 3, 2, 3),
            zorder=0)

    # ── cylinder domain boundary ──────────────────────────────────────
    draw_cylinder(ax, z0, z1, rm)

    # ── cathode plate (at z0, inner face points +x) ───────────────────
    draw_plate(ax, z0 + thick / 2, rm, thick)

    # emission spot on cathode inner face
    from matplotlib.patches import Polygon
    eu, ev = ell(z0 + thick + 0.01, re)
    pts = list(zip(eu, ev))
    ax.add_patch(Polygon(pts, closed=True, facecolor="white",
                         edgecolor="black", lw=1.2, hatch="....",
                         zorder=4))

    # ── collector plate (at z1, inner face points -x) ─────────────────
    draw_plate(ax, z1 - thick / 2, rm, thick)

    # ── beam envelope (dashed cone) ───────────────────────────────────
    beam_start = z0 + thick
    beam_end = z1 - thick
    spread = re * 1.2

    for angle in (SIL_TOP, SIL_BOT):
        us, vs = sil(beam_start, re, angle)
        ue, ve = sil(beam_end, spread, angle)
        ax.plot([us, ue], [vs, ve], "k--", lw=0.7, dashes=(6, 4), zorder=2)

    # beam arrows along axis
    d = iso_dir()
    for frac in (0.25, 0.55, 0.82):
        x_a = beam_start + (beam_end - beam_start) * frac
        u_a, v_a = iso(x_a, 0, 0)
        ax.annotate("", xy=(u_a + d[0] * 0.4, v_a + d[1] * 0.4),
                    xytext=(u_a, v_a),
                    arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
                    zorder=2)

    # ── labels ────────────────────────────────────────────────────────

    # cathode
    uc, vc = iso(z0, 0, -rm)
    leader(ax, (uc, vc), "CATHODE\nV = −100 V", (-1.5, -1.5),
           fontsize=14, fontweight="bold")

    # emission spot
    ue, ve = iso(z0 + thick, -re * 0.6, re * 0.6)
    leader(ax, (ue, ve),
           f"Emission spot\nI = {cfg.beam_current*1e6:.0f} μA",
           (-2.5, 1.5), fontsize=11)

    # collector
    uc, vc = iso(z1, 0, -rm)
    leader(ax, (uc, vc), "COLLECTOR\nV = 0 V", (1.5, -1.5),
           fontsize=14, fontweight="bold")

    # beam
    ub, vb = iso((z0 + z1) / 2, 0, re * 0.8)
    leader(ax, (ub, vb), "e⁻ beam", (0.5, 1.2), fontsize=12,
           fontstyle="italic")

    # axis label
    ua, va = iso(z1 + 1.0, 0, 0)
    ax.text(ua + 0.2, va, "axis of\nsymmetry", fontsize=9, ha="left",
            va="center", color="black", alpha=0.5, clip_on=False)

    # ── dimensions ────────────────────────────────────────────────────

    # axial length (cathode to collector)
    p1 = np.array(iso(z0, -rm, 0))
    p2 = np.array(iso(z1, -rm, 0))
    perp = np.array([S30, -C30])
    dim_line(ax, p1, p2, f"{(cfg.z_max - cfg.z_min)*S:.1f} mm",
             perp * 1.2, fontsize=13)

    # r_max (on collector face)
    p1 = np.array(iso(z1, 0, 0))
    p2 = np.array(iso(z1, 0, rm))
    dim_line(ax, p1, p2, f"r = {rm:.1f} mm", np.array([1.0, 0.0]),
             fontsize=11)

    # r_emit (on cathode face)
    p1 = np.array(iso(z0 + thick, 0, 0))
    p2 = np.array(iso(z0 + thick, 0, re))
    dim_line(ax, p1, p2, f"r_emit = {re:.1f} mm", np.array([-0.8, 0.0]),
             fontsize=10)

    fig.text(0.5, 0.97, "Negative Cathode",
             fontsize=18, fontweight="bold", ha="center", va="top",
             color="black")

    ax.autoscale()
    fig.savefig(str(out), dpi=dpi, bbox_inches="tight",
                facecolor="white", pad_inches=0.4)
    plt.close(fig)
    print(f"wrote {out}")


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(CASE_DIR / "config.yaml")
    draw(cfg, args.out, args.dpi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
