#!/usr/bin/env python3
"""Color isometric cutaway of the chipsat thruster can (capstone.floating_body).

CAD-style drawing: conducting can with lid hole, cathode disk, beam arrow,
dimension lines, and electrical labels.  The two conductors are color-coded
(red = floating body/chassis, blue = cathode) and joined only through the
drawn 200 V supply; the thrust vector and the ambient return current that
closes the circuit are annotated.  Regression anchors (thrust, phi_body)
are read from acceptance.yaml.

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

# shared across all capstone cases so images are to scale
AX_LIMS = (-12.0, 12.0, -12.0, 12.0)

from palette import AMBIENT, BEAM, BODY_EDGE, BODY_FILL, CATH_EDGE, CATH_FILL

EXHAUST_EV = 146.0  # float200 anchor, reported (not gated) -- see README


# ── isometric projection ─────────────────────────────────────────────

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


# ── drawing primitives ───────────────────────────────────────────────

def draw_can_cutaway(ax, geo):
    """Draw the conducting can as an isometric cutaway.

    Back half shown solid, front half cut away to expose the interior.
    Body metal is red, the cathode disk blue.  geo is a dict with keys
    from config.yaml geometry section.
    """
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

    LW = 0.8
    LW_THICK = 1.2

    def _pt(x_mm, y_mm, z_mm):
        u, v = iso(x_mm, y_mm, z_mm)
        return (float(u), float(v))

    def _rect(corners, **kw):
        ax.add_patch(Polygon(corners, closed=True, **kw))

    # ── back half of outer wall (visible arc: SIL_TOP → SIL_BOT through π)
    for z_pos in (zb, zt):
        u, v = ell(z_pos, rp, SIL_TOP, SIL_BOT)
        ax.plot(u, v, color=BODY_EDGE, lw=LW)
    for angle in (SIL_TOP, SIL_BOT):
        u0, v0 = sil(zb, rp, angle)
        u1, v1 = sil(zt, rp, angle)
        ax.plot([u0, u1], [v0, v1], color=BODY_EDGE, lw=LW)

    # ── cut-face: show the RZ cross-section on the front plane (y=0, z>=0)
    # Wall cross-section (right and left side) -- body metal
    for r_lo, r_hi in [(ri, rp), (-rp, -ri)]:
        _rect([_pt(zb, r_lo, 0), _pt(zb, r_hi, 0),
               _pt(zt, r_hi, 0), _pt(zt, r_lo, 0)],
              facecolor=BODY_FILL, edgecolor=BODY_EDGE, lw=LW_THICK, zorder=5)

    # Cathode disk -- the separate electrode
    _rect([_pt(zb, -r_cath, 0), _pt(zb, r_cath, 0),
           _pt(zfloort, r_cath, 0), _pt(zfloort, -r_cath, 0)],
          facecolor=CATH_FILL, edgecolor=CATH_EDGE, lw=LW_THICK, hatch="////",
          zorder=5)

    # Floor annulus — both sides (body metal)
    dx = 0.15  # mm (numerics.dx * S)
    r_cath_out = r_cath + 2 * dx
    for sign in (1.0, -1.0):
        rin_s, rout_s = sorted([sign * r_cath_out, sign * ri])
        _rect([_pt(zb, rin_s, 0), _pt(zb, rout_s, 0),
               _pt(zfloort, rout_s, 0), _pt(zfloort, rin_s, 0)],
              facecolor=BODY_FILL, edgecolor=BODY_EDGE, lw=LW, zorder=5)

    # Lid cross-section (washer from r_slit to ri on each side, body metal)
    for sign in (1.0, -1.0):
        rin_s, rout_s = sorted([sign * r_slit, sign * ri])
        _rect([_pt(zlidb, rin_s, 0), _pt(zlidb, rout_s, 0),
               _pt(zt, rout_s, 0), _pt(zt, rin_s, 0)],
              facecolor=BODY_FILL, edgecolor=BODY_EDGE, lw=LW_THICK, zorder=5)

    # ── front ellipses at cut plane (half arcs, bottom half only)
    # Outer wall — front half arc (bottom visible)
    for z_pos in (zb, zt):
        u, v = ell(z_pos, rp, SIL_BOT, SIL_TOP + 2 * np.pi)
        ax.plot(u, v, color=BODY_EDGE, lw=LW_THICK, zorder=6)
    # Inner wall — front half arc
    for z_pos in (zb, zt):
        u, v = ell(z_pos, ri, SIL_BOT, SIL_TOP + 2 * np.pi)
        ax.plot(u, v, color=BODY_EDGE, lw=LW, zorder=6)
    # Lid hole — front half
    u, v = ell(zt, r_slit, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, color=BODY_EDGE, lw=LW, zorder=6)
    u, v = ell(zlidb, r_slit, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, color=BODY_EDGE, lw=LW, zorder=6, alpha=0.5)
    # Cathode disk — front half
    u, v = ell(zfloort, r_cath, SIL_BOT, SIL_TOP + 2 * np.pi)
    ax.plot(u, v, color=CATH_EDGE, lw=LW, zorder=6)

    # Silhouette lines for inner wall (front half, connecting top to bottom)
    for angle in (SIL_TOP, SIL_BOT):
        u0, v0 = sil(zb, ri, angle)
        u1, v1 = sil(zt, ri, angle)
        ax.plot([u0, u1], [v0, v1], color=BODY_EDGE, lw=0.5, zorder=4,
                alpha=0.4)

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


def leader(ax, anchor, text, offset, fontsize=11, color="black", **kw):
    anchor = np.array(anchor)
    tip = anchor + np.array(offset)
    ax.plot([anchor[0], tip[0]], [anchor[1], tip[1]], color=color, lw=0.5,
            clip_on=False)
    ax.plot(*anchor, ".", color=color, ms=3, clip_on=False)
    ha = "left" if offset[0] > 0 else "right"
    pad = 0.15 if offset[0] > 0 else -0.15
    ax.text(tip[0] + pad, tip[1], text, fontsize=fontsize, ha=ha, va="center",
            color=color, clip_on=False, **kw)


def draw_supply_circuit(ax, dims, v_supply):
    """Wire the cathode to the body through the supply, below the can.

    The point of the drawing: the two conductors touch nowhere -- the
    ONLY link is the supply EMF.  Cathode side of the loop is blue, body
    side red; wires get a white halo so they read as passing in front of
    the can outline.
    """
    zb = dims["zb"]
    ri = dims["ri"]
    rp = dims["rp"]
    A = np.array(iso(zb, 0, 0))                    # cathode disk, bottom face
    B = np.array(iso(zb, -(ri + rp) / 2, 0))       # body wall foot (cut face)
    y_bus = -9.3
    gap_l, gap_r = -2.75, -2.05                    # battery terminal gap

    def wire(pts, color):
        pts = np.array(pts, float)
        ax.plot(pts[:, 0], pts[:, 1], color="white", lw=4.5, zorder=8,
                solid_capstyle="round")
        ax.plot(pts[:, 0], pts[:, 1], color=color, lw=1.8, zorder=9,
                solid_capstyle="round")

    wire([A, (A[0], y_bus), (gap_l, y_bus)], CATH_EDGE)
    wire([(gap_r, y_bus), (B[0], y_bus), B], BODY_EDGE)

    # battery symbol: short/thick = − (cathode side), long/thin = + (body)
    ax.plot([gap_l, gap_l], [y_bus - 0.28, y_bus + 0.28], color=CATH_EDGE,
            lw=3.5, zorder=9)
    ax.plot([gap_r, gap_r], [y_bus - 0.55, y_bus + 0.55], color=BODY_EDGE,
            lw=1.6, zorder=9)
    ax.text(gap_l - 0.35, y_bus + 0.65, "−", fontsize=13, ha="center",
            va="center", color=CATH_EDGE, fontweight="bold")
    ax.text(gap_r + 0.35, y_bus + 0.65, "+", fontsize=13, ha="center",
            va="center", color=BODY_EDGE, fontweight="bold")

    # terminal dots on the electrodes
    ax.plot(*A, "o", color=CATH_EDGE, ms=5, zorder=10)
    ax.plot(*B, "o", color=BODY_EDGE, ms=5, zorder=10)

    mid = (gap_l + gap_r) / 2
    ax.text(mid, y_bus - 0.95, f"POWER SUPPLY  {v_supply:.0f} V",
            fontsize=12, ha="center", va="top", color="black",
            fontweight="bold")
    ax.text(mid, y_bus - 1.65,
            "the only electrical link between cathode and body",
            fontsize=9, ha="center", va="top", color="0.4")


# ── main drawing ─────────────────────────────────────────────────────

def draw(geo, elec, beam, anchors, dpi, fmt="png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=(16, 10), facecolor="white")
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(AX_LIMS[0], AX_LIMS[1])
    ax.set_ylim(AX_LIMS[2], AX_LIMS[3])

    # center axis
    u0, v0 = iso(-8, 0, 0)
    u1, v1 = iso(5, 0, 0)
    ax.plot([u0, u1], [v0, v1], "k-.", lw=0.35, dashes=(8, 3, 2, 3), zorder=0)

    # draw the can
    dims = draw_can_cutaway(ax, geo)
    rp = dims["rp"]
    zb = dims["zb"]
    zt = dims["zt"]
    zfloort = dims["zfloort"]
    r_slit = dims["r_slit"]
    r_cath = dims["r_cath"]

    cathode_offset = elec["cathode_offset"]          # -200 V
    v_supply = abs(cathode_offset)
    phi_body = anchors["phi_body_V"]                 # +16 V float anchor
    phi_cath = phi_body + cathode_offset             # ≈ -184 V
    f_beam_nN = anchors["f_beam_nN"]                 # 13.6 nN anchor
    i_beam_mA = beam["i_beam"] * 1e3

    # ── beam (blue, through lid hole) ────────────────────────────────
    d = iso_dir()
    beam_start_z = zfloort + 0.3
    beam_end_z = zt + 3.0
    r_emit = geo["emit_radius"] * S

    # beam envelope lines
    for sign in (1.0, -1.0):
        us, vs = iso(beam_start_z, sign * r_emit, 0)
        ue, ve = iso(beam_end_z, sign * r_emit * 1.3, 0)
        ax.plot([us, ue], [vs, ve], color=BEAM, ls="--", lw=0.8,
                dashes=(5, 3), zorder=7)

    # beam axis arrows
    for frac in (0.3, 0.6, 0.85):
        z_a = beam_start_z + (beam_end_z - beam_start_z) * frac
        u_a, v_a = iso(z_a, 0, 0)
        ax.annotate("", xy=(u_a + d[0] * 0.5, v_a + d[1] * 0.5),
                    xytext=(u_a, v_a),
                    arrowprops=dict(arrowstyle="-|>", color=BEAM, lw=1.3),
                    zorder=7)

    # ── thrust vector (red, −z reaction on the body) ─────────────────
    corner = np.array(sil(zb, rp, SIL_TOP))          # back-left wall foot
    t0 = corner + np.array([-0.35, -0.35])
    t1 = t0 - d * 3.8
    ax.annotate("", xy=(t1[0], t1[1]), xytext=(t0[0], t0[1]),
                arrowprops=dict(arrowstyle="-|>", color=BODY_EDGE, lw=3.2,
                                mutation_scale=28), zorder=7)
    ax.text(t1[0] - 0.4, t1[1],
            f"THRUST\nF ≈ {f_beam_nN:.1f} nN (−z)\n"
            "reaction to the escaping e⁻ beam",
            fontsize=11, ha="right", va="center", color=BODY_EDGE,
            fontweight="bold", clip_on=False)

    # ── supply circuit ───────────────────────────────────────────────
    draw_supply_circuit(ax, dims, v_supply)

    # ── labels ───────────────────────────────────────────────────────

    # cathode (blue electrode)
    uc, vc = iso((zb + zfloort) / 2, 1.0, 0)
    leader(ax, (uc, vc),
           f"CATHODE (emitter, {i_beam_mA:.3f} mA)\n"
           f"φ_body − {v_supply:.0f} V ≈ −{-phi_cath:.0f} V\n"
           "no direct contact with the body",
           (-2.7, -1.5), fontsize=11, color=CATH_EDGE, fontweight="bold")

    # insulating gap between cathode disk and body floor
    ug, vg = iso(zfloort, r_cath + 0.15, 0)
    leader(ax, (ug, vg), "insulating gap —\ncathode isolated from body",
           (-2.2, -0.2), fontsize=9, color="0.25")

    # body (red, floats)
    uw, vw = sil(zt, rp, SIL_BOT)
    leader(ax, (uw, vw),
           f"BODY = spacecraft chassis\nfloats to φ_body ≈ {phi_body:+.0f} V",
           (2.8, -1.5), fontsize=12, color=BODY_EDGE, fontweight="bold")

    # lid hole
    uh, vh = iso(zt, -r_slit * 0.7, 0)
    leader(ax, (uh, vh), "Lid hole\n(exhaust)", (3.0, -1.2), fontsize=10)

    # beam label, with the energy budget of the acceleration gap
    ub, vb = iso(beam_end_z, r_emit * 1.3, 0)
    leader(ax, (ub, vb),
           f"e⁻ beam exhaust (+z)\n~{EXHAUST_EV:.0f} eV per electron\n"
           f"(~{v_supply:.0f} eV gained cathode→lid,\n"
           "less the climb out of the body's well)",
           (0.8, 2.2), fontsize=11, color=BEAM, fontstyle="italic")

    # ambient return current (closes the circuit through the plasma)
    ax.annotate("", xy=(3.3, -3.7), xytext=(7.0, -2.5),
                arrowprops=dict(arrowstyle="-|>", color=AMBIENT, lw=1.2,
                                ls="--"), zorder=7)
    ax.text(7.15, -2.5,
            "ambient plasma e⁻ collected by the body\n"
            "(return current — closes the circuit)",
            fontsize=9, ha="left", va="center", color=AMBIENT, clip_on=False)

    # axis label
    ua, va = iso(5, 0, 0)
    ax.text(ua + 0.3, va, "axis of\nsymmetry (RZ)", fontsize=8, ha="left",
            va="center", color="black", alpha=0.5, clip_on=False)

    # ── dimensions ───────────────────────────────────────────────────

    # can height (z_bot to z_top)
    p1 = np.array(iso(zb, -rp, 0))
    p2 = np.array(iso(zt, -rp, 0))
    perp = np.array([S30, -C30])
    dim_line(ax, p1, p2, f"{(zt - zb):.1f} mm", perp * 1.5, fontsize=10)

    # r_probe (on lid face)
    p1 = np.array(iso(zt, 0, 0))
    p2 = np.array(sil(zt, rp, SIL_TOP))
    dim_line(ax, p1, p2, f"r = {rp:.0f} mm", np.array([0.3, 1.2]),
             fontsize=10)

    # r_slit (lid hole radius, measured on the lid toward +y)
    p1 = np.array(iso(zt, 0, 0))
    p2 = np.array(iso(zt, r_slit, 0))
    dim_line(ax, p1, p2, f"r_slit = {r_slit:.0f} mm",
             np.array([0.4, 0.7]), fontsize=9)

    # r_cathode
    p1 = np.array(iso(zfloort, 0, 0))
    p2 = np.array(iso(zfloort, 0, -r_cath))
    dim_line(ax, p1, p2, f"r_cath = {r_cath:.1f} mm",
             np.array([1.6, 0.0]), fontsize=9)

    # ── legend ───────────────────────────────────────────────────────
    handles = [
        Patch(facecolor=BODY_FILL, edgecolor=BODY_EDGE,
              label=f"Body / chassis (floats to ≈ {phi_body:+.0f} V)"),
        Patch(facecolor=CATH_FILL, edgecolor=CATH_EDGE, hatch="///",
              label=f"Cathode (φ_body − {v_supply:.0f} V ≈ −{-phi_cath:.0f} V)"),
        Line2D([0], [0], color=BEAM, lw=1.5, ls="--",
               label=f"e⁻ beam ({i_beam_mA:.3f} mA)"),
        Line2D([0], [0], color=BODY_EDGE, lw=3,
               label=f"Thrust ≈ {f_beam_nN:.1f} nN"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=10, frameon=True,
              framealpha=0.95, edgecolor="0.7")

    fig.text(0.5, 0.97, f"Chipsat Thruster ({v_supply:.0f} V baseline)",
             fontsize=18, fontweight="bold", ha="center", va="top",
             color="black")
    fig.text(0.5, 0.93,
             "Floating body, charge-pump equilibrium — cathode tied to the "
             "chassis only through the supply",
             fontsize=12, ha="center", va="top", color="0.4")

    out = CASE_DIR / "viz" / f"schematic_2_chipsat_thruster.{fmt}"
    fig.savefig(str(out), dpi=dpi, facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="color isometric schematic")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--format", choices=("png", "pdf", "svg"), default="png",
                    help="output format (pdf/svg are vector, for papers)")
    args = ap.parse_args(argv)
    raw = yaml.safe_load((CASE_DIR / "config.yaml").read_text())
    acc = yaml.safe_load((CASE_DIR / "acceptance.yaml").read_text())
    targets = {g["metric"]: g.get("target")
               for g in acc["gates"] if "target" in g}
    anchors = {"f_beam_nN": targets["f_beam_nN"],
               "phi_body_V": targets["phi_body_V"]}
    draw(raw["geometry"], raw["electrical"], raw["beam"], anchors, args.dpi,
         args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
