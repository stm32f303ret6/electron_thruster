#!/usr/bin/env python3
"""To-scale cutaway pair: the capstone anchor can next to the slender can.

The figure that opens the README: same Ø10 mm can, same lid, same hole,
same gun -- only the wall stretched (5.5 -> 30.5 mm, L/r ~ 1.1 -> 6).
Lids align because the gun assembly sits at IDENTICAL z in both decks:
the slender floor rides a pedestal (`geometry.cathode_standoff`) so the
accelerating gap never stretches (the 2026-08-06 design rule: grow the
body around the gun, never the gun).

Data-driven like the other figures: geometry from the two config.yaml
files, measured float/thrust from the reference run's metrics.json,
anchor reference values from acceptance.yaml's reported-gate targets.

    python size_comparison.py [--dpi 300]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import yaml

from palette import BEAM, BODY_EDGE, BODY_FILL, CATH_EDGE, CATH_FILL
from schematic import C30, S30, S, SIL_BOT, SIL_TOP, dim_line, ell, iso, iso_dir, leader, sil

CASE_DIR = Path(__file__).resolve().parent.parent
ANCHOR_CONFIG = (CASE_DIR.parent.parent
                 / "ladder" / "capstone" / "2_chipsat_thruster" / "config.yaml")
REFERENCE_RUN = "20260806T011847Z_5670e54c"

DU_SLENDER = 41.0   # screen-x offset of the slender can [mm-equivalents]
DX_MM = 0.15        # numerics.dx * S (cathode/floor-annulus clearance)


# ── geometry derivation (mirrors helpers.CanGeometry, in mm) ─────────

def derive(geo: dict) -> dict:
    rp = geo["r_probe"] * S
    tw = geo["wall_thickness"] * S
    tfloor = geo["floor_thickness"] * S
    tlid = geo["lid_thickness"] * S
    zb = geo["z_bot"] * S
    zt = geo["z_top"] * S
    zlidb = zt - tlid
    standoff = geo.get("cathode_standoff")
    if standoff is None:                    # baseline: floor at the can bottom
        zfloort = zb + tfloor
        zfloorb = zb
        cap = None
    else:                                   # elongated: floor on a pedestal
        zfloort = zlidb - standoff * S
        zfloorb = zfloort - tfloor
        cap = (zb, zb + tfloor)             # sealed bottom cap (BODY)
    r_cath = geo["r_cathode"] * S
    L = zt - zb
    skin_cm2 = (2 * np.pi * rp * L + 2 * np.pi * rp ** 2
                - np.pi * (geo["r_slit"] * S) ** 2) / 100.0
    return dict(rp=rp, ri=rp - tw, zb=zb, zt=zt, zlidb=zlidb,
                zfloort=zfloort, zfloorb=zfloorb, cap=cap,
                r_slit=geo["r_slit"] * S, r_cath=r_cath,
                r_cath_out=r_cath + 2 * DX_MM, L=L, skin_cm2=skin_cm2)


# ── one can, isometric cutaway at a screen offset ────────────────────

def draw_can(ax, D: dict, off: tuple[float, float]) -> None:
    from matplotlib.patches import Polygon

    ou, ov = off
    LW, LW_THICK = 0.8, 1.2

    def P(x, y, z=0.0):
        u, v = iso(x, y, z)
        return float(u) + ou, float(v) + ov

    def arc(a, r, t0, t1, **kw):
        u, v = ell(a, r, t0, t1)
        ax.plot(u + ou, v + ov, **kw)

    def rect(z0, z1, r0, r1, **kw):
        ax.add_patch(Polygon([P(z0, r0), P(z0, r1), P(z1, r1), P(z1, r0)],
                             closed=True, **kw))

    rp, ri = D["rp"], D["ri"]
    zb, zt = D["zb"], D["zt"]

    # center axis
    u0, v0 = P(zb - 2.5, 0)
    u1, v1 = P(zt + 4.5, 0)
    ax.plot([u0, u1], [v0, v1], "k-.", lw=0.35, dashes=(8, 3, 2, 3), zorder=0)

    # back half of the outer wall
    for z_pos in (zb, zt):
        arc(z_pos, rp, SIL_TOP, SIL_BOT, color=BODY_EDGE, lw=LW)
    for angle in (SIL_TOP, SIL_BOT):
        for r, lw, al in ((rp, LW, 1.0), (ri, 0.5, 0.4)):
            us, vs = sil(zb, r, angle)
            ue, ve = sil(zt, r, angle)
            ax.plot([us + ou, ue + ou], [vs + ov, ve + ov],
                    color=BODY_EDGE, lw=lw, alpha=al, zorder=4)

    # cut face: wall, lid washer, floor annulus (BODY), cathode disk (CATHODE)
    for sign in (1.0, -1.0):
        rect(zb, zt, sign * ri, sign * rp, facecolor=BODY_FILL,
             edgecolor=BODY_EDGE, lw=LW_THICK, zorder=5)
        rect(D["zlidb"], zt, sign * D["r_slit"], sign * ri,
             facecolor=BODY_FILL, edgecolor=BODY_EDGE, lw=LW_THICK, zorder=5)
        rect(D["zfloorb"], D["zfloort"], sign * D["r_cath_out"], sign * ri,
             facecolor=BODY_FILL, edgecolor=BODY_EDGE, lw=LW, zorder=5)
    rect(D["zfloorb"], D["zfloort"], -D["r_cath"], D["r_cath"],
         facecolor=CATH_FILL, edgecolor=CATH_EDGE, lw=LW_THICK, hatch="////",
         zorder=5)
    if D["cap"] is not None:
        rect(D["cap"][0], D["cap"][1], -ri, ri, facecolor=BODY_FILL,
             edgecolor=BODY_EDGE, lw=LW, zorder=5)

    # front (cut-plane) half arcs
    for z_pos in (zb, zt):
        arc(z_pos, rp, SIL_BOT, SIL_TOP + 2 * np.pi,
            color=BODY_EDGE, lw=LW_THICK, zorder=6)
        arc(z_pos, ri, SIL_BOT, SIL_TOP + 2 * np.pi,
            color=BODY_EDGE, lw=LW, zorder=6)
    arc(zt, D["r_slit"], SIL_BOT, SIL_TOP + 2 * np.pi,
        color=BODY_EDGE, lw=LW, zorder=6)
    arc(D["zlidb"], D["r_slit"], SIL_BOT, SIL_TOP + 2 * np.pi,
        color=BODY_EDGE, lw=LW, zorder=6, alpha=0.5)
    arc(D["zfloort"], D["r_cath"], SIL_BOT, SIL_TOP + 2 * np.pi,
        color=CATH_EDGE, lw=LW, zorder=6)
    if D["cap"] is not None:
        arc(D["cap"][1], ri, SIL_BOT, SIL_TOP + 2 * np.pi,
            color=BODY_EDGE, lw=LW, zorder=6, alpha=0.5)

    # beam out of the lid hole
    d = iso_dir()
    for frac in (0.35, 0.75):
        z_a = zt + 0.7 + 2.4 * frac
        u_a, v_a = P(z_a, 0)
        ax.annotate("", xy=(u_a + d[0] * 0.6, v_a + d[1] * 0.6),
                    xytext=(u_a, v_a),
                    arrowprops=dict(arrowstyle="-|>", color=BEAM, lw=1.3),
                    zorder=7)


# ── main drawing ─────────────────────────────────────────────────────

def draw(anchor: dict, slender: dict, measured: dict, refs: dict,
         dpi: int, fmt: str = "png") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=(16, 8.85), facecolor="white")
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-16.0, 55.5)
    ax.set_ylim(-23.5, 16.0)
    fig.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)

    OFF_A, OFF_S = (0.0, 0.0), (DU_SLENDER, 0.0)
    perp = np.array([S30, -C30])

    # dotted guides: lid plane and gun-floor plane align across both cans
    for z_plane in (anchor["zt"], anchor["zfloorb"]):
        uL, vL = iso(z_plane, -anchor["rp"], 0)
        ax.plot([uL + 2.0, uL + DU_SLENDER - 1.5], [vL, vL],
                color="0.62", ls=":", lw=0.7, zorder=0)
    ax.text(-3.5, -11.0,
            "gun assembly at identical z in both decks (dotted planes) —\n"
            "the extra 24.5 mm is sealed, field-free body",
            fontsize=10, ha="center", va="center", color="0.4",
            fontstyle="italic")

    for D, off in ((anchor, OFF_A), (slender, OFF_S)):
        draw_can(ax, D, off)

        # can length along the -y silhouette
        p1 = np.array(iso(D["zb"], -D["rp"], 0)) + off
        p2 = np.array(iso(D["zt"], -D["rp"], 0)) + off
        dim_line(ax, p1, p2, f'{D["L"]:.1f} mm', perp * 1.5, fontsize=11)

        # gun gap on the cut face (between floor annulus and lid washer)
        g1 = np.array(iso(D["zfloort"], 2.8, 0)) + off
        g2 = np.array(iso(D["zlidb"], 2.8, 0)) + off
        dim_line(ax, g1, g2, f'gap {D["zlidb"] - D["zfloort"]:.1f} mm',
                 perp * -0.7, fontsize=9)

    # radius: identical, dimension it once per can
    p1 = np.array(iso(anchor["zt"], 0, 0))
    p2 = np.array(sil(anchor["zt"], anchor["rp"], SIL_TOP))
    dim_line(ax, p1, p2, f'r = {anchor["rp"]:.0f} mm',
             np.array([0.3, 1.2]), fontsize=10)
    p1 = np.array(iso(slender["zt"], 0, 0)) + OFF_S
    p2 = np.array(sil(slender["zt"], slender["rp"], SIL_TOP)) + OFF_S
    dim_line(ax, p1, p2, f'r = {slender["rp"]:.0f} mm (unchanged)',
             np.array([0.3, 1.2]), fontsize=10)

    # slender-only anatomy
    a = np.array(iso(slender["zfloort"], 3.2, 0)) + OFF_S
    leader(ax, a, "raised floor on a pedestal —\n"
                  "grow the body, never stretch the gun",
           (-3.0, 2.6), fontsize=10, color=BODY_EDGE)
    cav_mid = (slender["zfloorb"] + slender["cap"][1]) / 2
    uc, vc = iso(cav_mid, 0, 0)
    ax.text(uc + OFF_S[0], vc, "sealed dead cavity\n(no plasma, no fields)",
            fontsize=10, ha="center", va="center", color="0.35",
            bbox=dict(facecolor="white", edgecolor="none", pad=2))
    a = np.array(iso(slender["zb"] + 0.2, 0, 0)) + OFF_S
    leader(ax, a, "bottom cap (body metal)", (-3.6, -2.4), fontsize=10,
           color=BODY_EDGE)

    # anchor-only labels (shared anatomy, named once)
    a = np.array(iso((anchor["zfloorb"] + anchor["zfloort"]) / 2, 0.8, 0))
    leader(ax, a, "cathode (emitter)", (-2.5, -5.5), fontsize=10,
           color=CATH_EDGE)
    a = np.array(iso(anchor["zt"], -anchor["r_slit"] * 0.7, 0))
    leader(ax, a, "lid hole (exhaust)", (2.6, 1.9), fontsize=10)

    # per-can titles
    for D, off, name, sub in (
            (anchor, OFF_A, "ANCHOR — capstone baseline",
             f'floats to ≈ +{refs["phi_V"]:.0f} V · {refs["f_nN"]:.1f} nN'),
            (slender, OFF_S, "SLENDER — this spoke",
             f'floats to ≈ +{measured["phi_V"]:.1f} V · '
             f'{measured["f_nN"]:.1f} nN'),
    ):
        u_mid = C30 * (D["zb"] + D["zt"]) / 2 + off[0]
        ax.text(u_mid, 10.9,
                f'{name}\nØ{2 * D["rp"]:.0f} × {D["L"]:.1f} mm · '
                f'L/r ≈ {D["L"] / D["rp"]:.3g} · skin {D["skin_cm2"]:.3g} cm²',
                fontsize=12.5, ha="center", va="center", color="black",
                linespacing=1.5,
                fontweight="bold")
        ax.text(u_mid, 8.4, sub, fontsize=11, ha="center", va="center",
                color="0.35")

    handles = [
        Patch(facecolor=BODY_FILL, edgecolor=BODY_EDGE,
              label="Body / chassis (floats)"),
        Patch(facecolor=CATH_FILL, edgecolor=CATH_EDGE, hatch="///",
              label="Cathode (body − 200 V)"),
        Line2D([0], [0], color=BEAM, lw=1.5,
               label="e⁻ beam (0.342 mA, both)"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=10, frameon=True,
              framealpha=0.95, edgecolor="0.7")

    fig.text(0.5, 0.985, "The geometry axis — anchor vs slender body, to scale",
             fontsize=18, fontweight="bold", ha="center", va="top")
    fig.text(0.5, 0.938,
             "Same gun, lid hole, plasma and numerics; only the can length "
             f'changes.  Measured at identical drive: body float '
             f'+{refs["phi_V"]:.0f} V → +{measured["phi_V"]:.1f} V, '
             f'thrust {refs["f_nN"]:.1f} → {measured["f_nN"]:.1f} nN.',
             fontsize=12, ha="center", va="top", color="0.4")

    out = CASE_DIR / "viz" / f"size_comparison_anchor_vs_slender.{fmt}"
    fig.savefig(str(out), dpi=dpi, facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="to-scale anchor vs slender cutaway")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--format", choices=("png", "pdf", "svg"), default="png")
    args = ap.parse_args(argv)

    slender_geo = yaml.safe_load((CASE_DIR / "config.yaml").read_text())["geometry"]
    anchor_geo = yaml.safe_load(ANCHOR_CONFIG.read_text())["geometry"]

    metrics = json.loads((CASE_DIR / "reference_results" / REFERENCE_RUN
                          / "metrics.json").read_text())
    by_id = {m["id"]: m["value"] for m in metrics["metrics"]}
    measured = {"phi_V": by_id["phi_body_V"], "f_nN": by_id["f_beam_nN"]}

    # anchor float200 reference values = the reported gates' targets
    acc = yaml.safe_load((CASE_DIR / "acceptance.yaml").read_text())
    targets = {g["metric"]: g["target"] for g in acc["gates"] if "target" in g}
    refs = {"phi_V": targets["phi_body_V"], "f_nN": targets["f_beam_nN"]}

    draw(derive(anchor_geo), derive(slender_geo), measured, refs,
         args.dpi, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
