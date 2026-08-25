#!/usr/bin/env python3
"""Paper figures for the device: the operating-sequence cartoon, a
paper-styled potential map and the static dashboard from the 200 V anchor run.
(schematic() is kept but no longer called: the cross-section figure was dropped
from the paper as redundant with the sequence figure.)

    conda activate warpx-cpu-mpich-dev
    python make_device_figs.py [--run <outputs/run-id>]

Writes ../imgs/concept_steps_mpl.pdf, ../imgs/potential_map_200v.png and
../imgs/dashboard_200v.png
(the map stays raster: it is a 2-D field image).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.colors import TwoSlopeNorm

HERE = Path(__file__).resolve().parent
IMGS = HERE.parent / "imgs"
CASE = HERE.parent.parent / "pic_sims" / "ladder" / "capstone" / "2_chipsat_thruster"
DEFAULT_RUN = CASE / "outputs" / "20260805T045954Z_b87fbefc"

BODY = "#a93226"
BODY_FILL = "#f5c6c0"
BODY_DARK = "0.15"
CATH = "#1a5276"
CATH_FILL = "#cfe3f5"
BEAM = "#2471a3"
AMB = "0.35"

plt.rcParams.update({
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
    "font.family": "serif", "mathtext.fontset": "cm",
})


# ----------------------------------------------------------------- schematic
def schematic(out: Path):
    # geometry from config.yaml (mm)
    r_p, wall, z_bot, z_top = 5.0, 0.4, -5.0, 0.5
    r_slit, r_cath, r_emit = 2.0, 1.5, 0.5
    cath_z0, cath_z1 = z_bot, z_bot + wall        # cathode disk shares floor thickness

    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    ax.set_aspect("equal")

    def rect(z0, z1, r0, r1, fc, ec):
        for s in (1, -1):
            a, b = sorted((s * r0, s * r1))
            ax.add_patch(Rectangle((z0, a), z1 - z0, b - a, fc=fc, ec=ec, lw=0.8, zorder=3))

    # body: side wall, floor annulus, lid annulus
    rect(z_bot, z_top, r_p - wall, r_p, BODY_FILL, BODY)
    rect(z_bot, z_bot + wall, r_cath + 0.4, r_p, BODY_FILL, BODY)
    rect(z_top - wall, z_top, r_slit, r_p, BODY_FILL, BODY)
    # cathode disk
    ax.add_patch(Rectangle((cath_z0, -r_cath), cath_z1 - cath_z0, 2 * r_cath,
                           fc=CATH_FILL, ec=CATH, lw=0.8, hatch="////", zorder=4))

    # beam: emitted from the spot, diverging slightly through the hole
    for r0 in np.linspace(-r_emit, r_emit, 5):
        ax.plot([cath_z1, z_top, 7.0], [r0, r0 * 1.6, r0 * 3.2],
                color=BEAM, lw=0.9, ls="--", zorder=5)
    ax.annotate("", xy=(9.0, 0.0), xytext=(7.0, 0.0),
                arrowprops=dict(arrowstyle="-|>", color=BEAM, lw=1.4))
    ax.text(7.2, 1.9, "e$^-$ beam\n$I$, KE $= \\kappa(V-\\varphi)$",
            color=BEAM, ha="left", va="bottom", fontsize=8)

    # thrust arrow (reaction, -z)
    ax.annotate("", xy=(-9.0, 0.0), xytext=(-5.6, 0.0),
                arrowprops=dict(arrowstyle="-|>", color=BODY, lw=2.0))
    ax.text(-9.0, 1.0, "thrust $F$", color=BODY, ha="left", va="bottom", fontsize=8)

    # ambient electrons collected on the skin
    for (z, r, dz, dr) in [(-3.5, 8.6, 0, -2.9), (-3.5, -8.6, 0, 2.9),
                           (-8.4, 4.6, 2.8, 0), (-8.4, -4.6, 2.8, 0)]:
        ax.annotate("", xy=(z + dz, r + dr), xytext=(z, r),
                    arrowprops=dict(arrowstyle="->", color=AMB, lw=0.9))
    ax.text(-10.3, 9.2, "ambient e$^-$\ncollected on the skin", color=AMB,
            ha="left", va="bottom", fontsize=8)

    # supply symbol between body and cathode (drawn below the can)
    zc, rc = (cath_z0 + cath_z1) / 2, -r_cath
    ax.plot([zc, zc, -1.0, -1.0], [rc, -7.2, -7.2, -r_p], color="k", lw=0.8, zorder=2)
    ax.plot([-1.25, -1.25], [-7.7, -6.7], color="k", lw=1.6)   # long plate (+)
    ax.plot([-0.75, -0.75], [-7.4, -7.0], color="k", lw=1.6)   # short plate (-)
    ax.text(-1.0, -8.0, "supply $V$", ha="center", va="top", fontsize=8)
    ax.text(-1.9, -7.2, "+", ha="right", va="center", fontsize=8)
    ax.text(-0.1, -7.2, "$-$", ha="left", va="center", fontsize=8)

    # labels
    ax.text(-1.5, 5.8, "body, floats at $+\\varphi$", color=BODY, ha="left", va="bottom", fontsize=8)
    ax.text(-5.4, -1.2, "cathode\n($\\varphi - V$)", color=CATH, ha="right", va="top", fontsize=8)
    ax.text(0.9, 2.5, "aperture", ha="left", va="bottom", fontsize=8)
    ax.annotate("", xy=(0.4, 2.0), xytext=(1.6, 2.6),
                arrowprops=dict(arrowstyle="-", color="k", lw=0.6))
    ax.plot([0, 0], [-10, 10], color="0.6", lw=0.5, ls="-.", zorder=1)
    ax.text(-10.3, -0.6, "axis", color="0.5", ha="left", va="top", fontsize=7)

    ax.set_xlim(-10.5, 10.5)
    ax.set_ylim(-10.0, 11.5)
    ax.set_xlabel("z [mm]")
    ax.set_ylabel("r [mm]")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


# ------------------------------------------------------------ concept steps
def concept_steps(out: Path):
    """Six-panel operating sequence (matplotlib redraw of imgs/concept_steps.png)."""
    steps = [
        ("1. initial state", dict(sw=False, beam=False, body=BODY_DARK, ambient=False)),
        ("2. supply switched on", dict(sw=True, beam=False, body=BODY_DARK, ambient=False)),
        ("3. cathode emits, beam accelerated out", dict(sw=True, beam=True, body=BODY_DARK, ambient=False)),
        ("4. body charges positive", dict(sw=True, beam=True, body=BODY, ambient=False)),
        ("5. positive body collects ambient e$^-$", dict(sw=True, beam=True, body=BODY, ambient=True)),
        ("6. steady state: collection = emission", dict(sw=True, beam=True, body=BODY, ambient=True)),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(7.0, 4.0))
    for ax, (title, o) in zip(axes.flat, steps):
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_xlim(-2.7, 3.4); ax.set_ylim(-2.2, 2.2)
        # body: rectangle with a gap (aperture) on the right wall
        c = o["body"]; lw = 2.2
        ax.plot([-2, -2, 2, 2], [-1.5, 1.5, 1.5, 0.35], c=c, lw=lw, solid_capstyle="round")
        ax.plot([2, 2, -2], [-0.35, -1.5, -1.5], c=c, lw=lw, solid_capstyle="round")
        # circuit: left wall -> supply -> switch -> cathode
        ax.plot([-2, -1.3], [0, 0], c="k", lw=0.9)
        ax.plot([-1.3, -1.3], [-0.35, 0.35], c="k", lw=1.8)      # long plate (+)
        ax.plot([-1.1, -1.1], [-0.18, 0.18], c="k", lw=1.8)      # short plate (-)
        ax.text(-1.2, 0.45, "HV supply $V$", fontsize=6.5, ha="center", va="bottom")
        ax.plot([-1.1, -0.3], [0, 0], c="k", lw=0.9)
        if o["sw"]:
            ax.plot([-0.3, 0.3], [0, 0], c="k", lw=0.9)
        else:
            ax.plot([-0.3, 0.25], [0, 0.32], c="k", lw=0.9)
        ax.plot([-0.3, 0.3], [0, 0], "k.", ms=3)
        ax.plot([0.3, 1.2], [0, 0], c="k", lw=0.9)
        ax.plot([1.2, 1.2], [-0.5, 0.5], c=CATH, lw=2.4)           # cathode
        ax.text(1.2, 0.58, "cathode", fontsize=6.5, ha="center", va="bottom", color=CATH)
        if o["beam"]:
            ax.annotate("", xy=(3.2, 0), xytext=(1.3, 0),
                        arrowprops=dict(arrowstyle="-|>", color=BEAM, lw=2.0, mutation_scale=12))
            ax.text(2.6, -0.2, "e$^-$ beam", fontsize=6.5, ha="center", va="top", color=BEAM)
        if o["body"] == BODY:
            ax.text(0.0, 1.38, "+   +   +   +", fontsize=7, ha="center", va="top", color=BODY)
            ax.text(0.0, -1.38, "+   +   +   +", fontsize=7, ha="center", va="bottom", color=BODY)
        if o["ambient"]:
            for (x0, y0, dx, dy) in [(-2.6, 0.9, 0.55, 0), (-2.6, -0.9, 0.55, 0),
                                     (-1.0, 2.1, 0, -0.55), (1.0, 2.1, 0, -0.55),
                                     (-1.0, -2.1, 0, 0.55), (1.0, -2.1, 0, 0.55)]:
                ax.annotate("", xy=(x0 + dx, y0 + dy), xytext=(x0, y0),
                            arrowprops=dict(arrowstyle="-|>", color=AMB, lw=1.0, mutation_scale=8))
            ax.text(-2.65, 1.75, "ambient e$^-$", fontsize=6, ha="left", va="bottom", color=AMB)
        if title.startswith("6."):
            ax.text(0.0, -0.75, "body floats at $+\\varphi$\n$I_{\\rm collected} = I_{\\rm beam}$",
                    fontsize=6.5, ha="center", va="center", color=BODY)
        ax.set_title(title, fontsize=7.5, loc="left", pad=8)
    fig.tight_layout(pad=0.3)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


# ------------------------------------------------------------- potential map
def potential_map(run: Path, out: Path):
    sys.path.insert(0, str(CASE))
    pic_root = CASE
    while not (pic_root / "ladder_contract.py").is_file():
        pic_root = pic_root.parent
    sys.path.insert(0, str(pic_root))
    import ladder_contract as lc
    from analyze import field_rz, load_ledger
    from helpers import load_config
    from openpmd_viewer import OpenPMDTimeSeries

    ev = lc.load_run(run)
    cfg = load_config(ev.dir / "config_used.yaml")
    g = cfg.geometry()
    ts = OpenPMDTimeSeries(os.path.join(str(ev.diags_dir), "fields"), check_all_files=False)
    it = ts.iterations[-1]
    t_ns = ts.t[-1] * 1e9
    phi, r, z = field_rz(ts, "phi", it)
    rr = np.concatenate([-r[::-1], r]) * 1e3
    zmm = z * 1e3
    PHI = np.vstack([phi[::-1], phi])
    led = load_ledger(ev.diags_dir)
    t_l, phi_l = np.atleast_1d(led["t"]), np.atleast_1d(led["phi_body"])
    phi_body = float(phi_l[t_l > t_l[-1] - 100e-9].mean())

    def can(ax):
        def both(z0, z1, r0, r1, c):
            for s in (1, -1):
                a, b = sorted((s * r0, s * r1))
                ax.add_patch(Rectangle((z0 * 1e3, a * 1e3), (z1 - z0) * 1e3, (b - a) * 1e3,
                                       fc=c, ec="none", zorder=6))
        both(g.z_bot, g.z_top, g.r_in, g.r_p, BODY)
        both(g.z_floorb, g.zfloort, g.r_cath_out, g.r_p, BODY)
        both(g.zlidb, g.z_top, g.r_slit, g.r_p, BODY)
        both(g.z_floorb, g.zfloort, 0.0, g.r_cath, CATH)

    fig, (aL, aR) = plt.subplots(1, 2, figsize=(7.0, 2.9),
                                 gridspec_kw=dict(width_ratios=[1.3, 1.0], wspace=0.35))
    ext = [zmm.min(), zmm.max(), rr.min(), rr.max()]
    imL = aL.imshow(PHI, origin="lower", cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-20, vcenter=0, vmax=20),
                    extent=ext, aspect="equal", interpolation="nearest")
    aL.contour(zmm, rr, PHI, levels=[-5, -1, 1, 5, 10], colors="0.3", linewidths=0.4)
    can(aL)
    cb = fig.colorbar(imL, ax=aL, shrink=0.85, pad=0.02)
    cb.set_label("$\\varphi$ [V], clipped to $\\pm$20 V")
    aL.set_title(f"(a) full domain, $t$ = {t_ns:.0f} ns, body at {phi_body:+.1f} V")
    aL.set_xlabel("z [mm]"); aL.set_ylabel("r [mm]")

    imR = aR.imshow(PHI, origin="lower", cmap="RdBu_r",
                    norm=TwoSlopeNorm(vmin=min(PHI.min(), -1), vcenter=0, vmax=max(PHI.max(), 1)),
                    extent=ext, aspect="equal", interpolation="nearest")
    aR.contour(zmm, rr, PHI, levels=[-150, -100, -50, -20, -5], colors="0.3", linewidths=0.4)
    can(aR)
    aR.set_xlim(-8, 6); aR.set_ylim(-8, 8)
    cb = fig.colorbar(imR, ax=aR, shrink=0.85, pad=0.02)
    cb.set_label("$\\varphi$ [V], full range")
    aR.set_title("(b) acceleration gap inside the can")
    aR.set_xlabel("z [mm]"); aR.set_ylabel("r [mm]")

    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out)


# ---------------------------------------------------------------- dashboard
def dashboard(run: Path, out: Path):
    """Static 2x2 version of viz/animate_dashboard.py at the final frame."""
    sys.path.insert(0, str(CASE))
    pic_root = CASE
    while not (pic_root / "ladder_contract.py").is_file():
        pic_root = pic_root.parent
    sys.path.insert(0, str(pic_root))
    import ladder_contract as lc
    from analyze import field_rz, load_ledger
    from helpers import load_config
    from openpmd_viewer import OpenPMDTimeSeries
    import scipy.constants as scc

    ev = lc.load_run(run)
    cfg = load_config(ev.dir / "config_used.yaml")
    g = cfg.geometry()
    ts = OpenPMDTimeSeries(os.path.join(str(ev.diags_dir), "fields"), check_all_files=False)
    it = ts.iterations[-1]
    rho, r, z = field_rz(ts, "rho_beam_electrons", it)
    nb = np.abs(rho) / scc.e
    rr = np.concatenate([-r[::-1], r]) * 1e3
    zmm = z * 1e3
    NB = np.vstack([nb[::-1], nb])

    led = load_ledger(ev.diags_dir)
    t = np.atleast_1d(led["t"]) * 1e9
    F = np.atleast_1d(led["F_beam_N"]) * 1e9
    P = np.abs(np.atleast_1d(led["V_cathode"])) * cfg.i_beam * 1e3
    esc = np.atleast_1d(led["pct_escape"])
    ret = np.atleast_1d(led["pct_body"]) + np.atleast_1d(led["pct_cathode"])
    phi = np.atleast_1d(led["phi_body"])

    fig, ax = plt.subplots(2, 2, figsize=(7.0, 4.6))
    (aD, aF), (aT, aP) = ax

    im = aD.imshow(NB / 1e13, origin="lower", extent=[zmm.min(), zmm.max(), rr.min(), rr.max()],
                   aspect="auto", cmap="inferno", vmin=0, vmax=np.percentile(NB, 99.5) / 1e13)
    cb = fig.colorbar(im, ax=aD, shrink=0.9, pad=0.02)
    cb.set_label("$n_{\\rm beam}$ [$10^{13}$ m$^{-3}$]")
    for s in (1, -1):
        for (z0, z1, r0, r1) in [(g.z_bot, g.z_top, g.r_in, g.r_p),
                                 (g.z_floorb, g.zfloort, g.r_cath_out, g.r_p),
                                 (g.zlidb, g.z_top, g.r_slit, g.r_p)]:
            a, b = sorted((s * r0, s * r1))
            aD.add_patch(Rectangle((z0 * 1e3, a * 1e3), (z1 - z0) * 1e3, (b - a) * 1e3,
                                   fc="0.75", ec="none", zorder=6))
    aD.set_title(f"(a) beam electron density, $t$ = {t[-1]:.0f} ns", loc="left")
    aD.set_xlabel("z [mm]"); aD.set_ylabel("r [mm]")

    aF.plot(t, esc, c="tab:green", lw=1.2, label="escaped")
    aF.plot(t, ret, c="tab:red", lw=1.0, label="returned to body")
    aF.set_ylim(-2, 105); aF.set_ylabel("beam fraction [%]")
    aF.legend(loc="center right"); aF.set_title("(b) beam fate", loc="left")

    aT.plot(t, F, c="tab:blue", lw=1.0)
    aT.set_ylim(0, 18); aT.set_ylabel("thrust $F_{\\rm beam}$ [nN]")
    aT.set_title("(c) thrust", loc="left")

    aP.plot(t, P, c="tab:red", lw=1.2)
    aP.set_ylim(0, 90); aP.set_ylabel("beam power $VI$ [mW]")
    aP.set_title("(d) power consumption", loc="left")

    for a in (aF, aT, aP):
        a.set_xlim(0, t[-1]); a.set_xlabel("time [ns]"); a.grid(alpha=0.3, lw=0.4)
    fig.tight_layout(pad=0.4)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--skip-map", action="store_true")
    a = ap.parse_args()
    IMGS.mkdir(exist_ok=True)
    concept_steps(IMGS / "concept_steps_mpl.pdf")
    if not a.skip_map:
        potential_map(a.run, IMGS / "potential_map_200v.png")
        dashboard(a.run, IMGS / "dashboard_200v.png")
