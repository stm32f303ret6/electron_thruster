#!/usr/bin/env python3
"""B&W isometric cutaway of the chipsat thruster can (capstone.ucurve_valley).

CAD-style drawing: conducting can with lid hole, cathode disk, beam arrow,
dimension lines, and electrical labels.  125 V fixed-thrust throttle point.

    python schematic.py [--dpi 300]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import yaml

CASE_DIR = Path(__file__).resolve().parent.parent
S = 1e3  # m -> mm
C30 = np.cos(np.radians(30))
S30 = np.sin(np.radians(30))
SIL_TOP = np.pi / 4
SIL_BOT = np.pi + np.pi / 4

AX_LIMS = (-12.0, 12.0, -12.0, 12.0)


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


def draw_can_cutaway(ax, geo):
    rp = geo["r_probe"] * S
    tw = geo["wall_thickness"] * S
    ri = rp - tw
    zb = geo["z_bot"] * S
    zt = geo["z_top"] * S
    tfloor = geo["floor_thickness"] * S
    tlid = geo["lid_thickness"] * S
    r_slit = geo["r_slit"] * S
    r_cath = geo["r_cathode"] * S
    zfloort = zb + tfloor
    zlidb = zt - tlid

    from matplotlib.patches import Polygon

    FILL = "0.85"
    EDGE = "black"
    LW = 0.8
    LW_THICK = 1.2

    def _pt(x_mm, y_mm, z_mm):
        u, v = iso(x_mm, y_mm, z_mm)
        return (float(u), float(v))

    def _rect(corners, **kw):
        ax.add_patch(Polygon(corners, closed=True, **kw))

    for z_pos in (zb, zt):
        u, v = ell(z_pos, rp, SIL_TOP, SIL_BOT)
        ax.plot(u, v, "k-", lw=LW)
    for angle in (SIL_TOP, SIL_BOT):
        u0, v0 = sil(zb, rp, angle)
        u1, v1 = sil(zt, rp, angle)
        ax.plot([u0, u1], [v0, v1], "k-", lw=LW)

    for r_lo, r_hi in [(ri, rp), (-rp, -ri)]:
        _rect([_pt(zb, r_lo, 0), _pt(zb, r_hi, 0),
               _pt(zt, r_hi, 0), _pt(zt, r_lo, 0)],
              facecolor=FILL, edgecolor=EDGE, lw=LW_THICK, zorder=5)

    _rect([_pt(zb, -r_cath, 0), _pt(zb, r_cath, 0),
           _pt(zfloort, r_cath, 0), _pt(zfloort, -r_cath, 0)],
          facecolor="0.70", edgecolor=EDGE, lw=LW_THICK, hatch="////",
          zorder=5)

    dx = 0.15
    r_cath_out = r_cath + 2 * dx
    for sign in (1.0, -1.0):
        rin_s, rout_s = sorted([sign * r_cath_out, sign * ri])
        _rect([_pt(zb, rin_s, 0), _pt(zb, rout_s, 0),
               _pt(zfloort, rout_s, 0), _pt(zfloort, rin_s, 0)],
              facecolor=FILL, edgecolor=EDGE, lw=LW, zorder=5)

    for sign in (1.0, -1.0):
        rin_s, rout_s = sorted([sign * r_slit, sign * ri])
        _rect([_pt(zlidb, rin_s, 0), _pt(zlidb, rout_s, 0),
               _pt(zt, rout_s, 0), _pt(zt, rin_s, 0)],
              facecolor=FILL, edgecolor=EDGE, lw=LW_THICK, zorder=5)

    for z_pos in (zb, zt):
        u, v = ell(z_pos, rp, SIL_BOT, SIL_TOP + 2 * np.pi)
        ax.plot(u, v, "k-", lw=LW_THICK, zorder=6)
    for z_pos in (zb, zt):
        u, v = ell(z_pos, ri, SIL_BOT, SIL_TOP + 2 * np.pi)
        ax.plot(u, v, "k-", lw=LW, zorder=6)
    u, v = ell(zt, r_slit, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, "k-", lw=LW, zorder=6)
    u, v = ell(zlidb, r_slit, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, "k-", lw=LW, zorder=6, alpha=0.5)
    u, v = ell(zfloort, r_cath, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, "k-", lw=LW, zorder=6)

    for angle in (SIL_TOP, SIL_BOT):
        u0, v0 = sil(zb, ri, angle)
        u1, v1 = sil(zt, ri, angle)
        ax.plot([u0, u1], [v0, v1], "k-", lw=0.5, zorder=4, alpha=0.4)

    return dict(rp=rp, ri=ri, zb=zb, zt=zt, zfloort=zfloort, zlidb=zlidb,
                r_slit=r_slit, r_cath=r_cath, tfloor=tfloor, tlid=tlid)


def dim_line(ax, p1, p2, label, offset, fontsize=11):
    p1, p2 = np.array(p1), np.array(p2)
    n = np.array(offset)
    for p in (p1, p2):
        tip = p + n * 1.15
        ax.plot([p[0], tip[0]], [p[1], tip[1]], "k-", lw=0.35, clip_on=False)
    d1, d2 = p1 + n, p2 + n
    ax.annotate("", xy=(d2[0], d2[1]), xytext=(d1[0], d1[1]),
                arrowprops=dict(arrowstyle="<->", color="black", lw=0.6,
                                shrinkA=0, shrinkB=0), clip_on=False)
    mid = (d1 + d2) / 2
    ax.text(mid[0], mid[1], label, fontsize=fontsize, ha="center", va="center",
            color="black", clip_on=False,
            bbox=dict(facecolor="white", edgecolor="none", pad=2))


def leader(ax, anchor, text, offset, fontsize=11, **kw):
    anchor = np.array(anchor)
    tip = anchor + np.array(offset)
    ax.plot([anchor[0], tip[0]], [anchor[1], tip[1]], "k-", lw=0.5,
            clip_on=False)
    ax.plot(*anchor, "k.", ms=3, clip_on=False)
    ha = "left" if offset[0] > 0 else "right"
    pad = 0.15 if offset[0] > 0 else -0.15
    ax.text(tip[0] + pad, tip[1], text, fontsize=fontsize, ha=ha, va="center",
            color="black", clip_on=False, **kw)


def draw(geo, elec, beam, dpi):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(16, 10), facecolor="white")
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(AX_LIMS[0], AX_LIMS[1])
    ax.set_ylim(AX_LIMS[2], AX_LIMS[3])

    u0, v0 = iso(-8, 0, 0)
    u1, v1 = iso(5, 0, 0)
    ax.plot([u0, u1], [v0, v1], "k-.", lw=0.35, dashes=(8, 3, 2, 3), zorder=0)

    dims = draw_can_cutaway(ax, geo)
    rp, zb, zt = dims["rp"], dims["zb"], dims["zt"]
    zfloort, r_slit, r_cath = dims["zfloort"], dims["r_slit"], dims["r_cath"]

    d = iso_dir()
    beam_start_z = zfloort + 0.3
    beam_end_z = zt + 3.0
    r_emit = geo["emit_radius"] * S

    for sign in (1.0, -1.0):
        us, vs = iso(beam_start_z, sign * r_emit, 0)
        ue, ve = iso(beam_end_z, sign * r_emit * 1.3, 0)
        ax.plot([us, ue], [vs, ve], "k--", lw=0.7, dashes=(5, 3), zorder=7)

    for frac in (0.3, 0.6, 0.85):
        z_a = beam_start_z + (beam_end_z - beam_start_z) * frac
        u_a, v_a = iso(z_a, 0, 0)
        ax.annotate("", xy=(u_a + d[0] * 0.5, v_a + d[1] * 0.5),
                    xytext=(u_a, v_a),
                    arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
                    zorder=7)

    cathode_offset = elec["cathode_offset"]
    i_beam_mA = beam["i_beam"] * 1e3

    uc, vc = iso(zb, 0, 0)
    leader(ax, (uc, vc - 0.3), f"CATHODE\nV_body {cathode_offset:+.0f} V",
           (-3.5, -2.5), fontsize=12, fontweight="bold")

    uw, vw = sil(zt, rp, SIL_BOT)
    leader(ax, (uw, vw), "BODY (floats)",
           (2.5, -2.0), fontsize=12, fontweight="bold")

    ue, ve = iso(zfloort, r_cath * 0.5, 0)
    leader(ax, (ue, ve), f"Emission spot\ni = {i_beam_mA:.3f} mA",
           (-4.0, 1.0), fontsize=10)

    uh, vh = iso(zt, r_slit * 0.7, 0)
    leader(ax, (uh, vh + 0.2), "Lid hole\n(exhaust)",
           (3.0, 2.0), fontsize=10)

    ub, vb = iso(beam_end_z - 0.5, 0, r_emit)
    leader(ax, (ub, vb), "e⁻ beam", (1.0, 1.5), fontsize=11,
           fontstyle="italic")

    ua, va = iso(5, 0, 0)
    ax.text(ua + 0.3, va, "axis of\nsymmetry (RZ)", fontsize=8, ha="left",
            va="center", color="black", alpha=0.5, clip_on=False)

    p1 = np.array(iso(zb, -rp, 0))
    p2 = np.array(iso(zt, -rp, 0))
    perp = np.array([S30, -C30])
    dim_line(ax, p1, p2, f"{(zt - zb):.1f} mm", perp * 1.5, fontsize=10)

    p1 = np.array(iso(zt, 0, 0))
    p2 = np.array(sil(zt, rp, SIL_TOP))
    dim_line(ax, p1, p2, f"r = {rp:.0f} mm", np.array([0.3, 1.2]),
             fontsize=10)

    p1 = np.array(iso(zt, 0, 0))
    p2 = np.array(iso(zt, 0, r_slit))
    dim_line(ax, p1, p2, f"r_slit = {r_slit:.0f} mm", np.array([1.0, 0.0]),
             fontsize=9)

    p1 = np.array(iso(zfloort, 0, 0))
    p2 = np.array(iso(zfloort, 0, -r_cath))
    dim_line(ax, p1, p2, f"r_cath = {r_cath:.1f} mm",
             np.array([-0.8, 0.0]), fontsize=9)

    fig.text(0.5, 0.97, "U-curve valley (125 V)",
             fontsize=18, fontweight="bold", ha="center", va="top",
             color="black")
    fig.text(0.5, 0.93,
             "Same geometry, driven at the hardware floor",
             fontsize=12, ha="center", va="top", color="0.4")

    out = CASE_DIR / "viz" / "schematic_5_ucurve_valley.png"
    fig.savefig(str(out), dpi=dpi, facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B&W isometric schematic")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args(argv)
    raw = yaml.safe_load((CASE_DIR / "config.yaml").read_text())
    draw(raw["geometry"], raw["electrical"], raw["beam"], args.dpi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
