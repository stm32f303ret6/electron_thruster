#!/usr/bin/env python3
"""B&W isometric schematic for the biased +3 V collection case.

Sphere probe biased above plasma potential inside a cylindrical domain.
Sheath ≈ 3 λ_D.

    python schematic.py [--dpi 300]
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import yaml
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent.parent
S = 1e3  # m -> mm
C30 = np.cos(np.radians(30))
S30 = np.sin(np.radians(30))
SIL_TOP = np.pi / 4
SIL_BOT = np.pi + np.pi / 4

# shared across all current_collection cases so images are to scale
AX_LIMS = (-42.4, 42.4, -39.9, 39.9)

SHEATH_DEBYE = 3.0


# ── isometric projection ──────────────────────────────────────────────

def iso(x, y, z):
    x, y, z = np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)
    return C30 * (x - y), S30 * (x + y) + z


def ell(a, r, t0=0.0, t1=2 * np.pi, n=300):
    t = np.linspace(t0, t1, n)
    return iso(a, r * np.cos(t), r * np.sin(t))


def sil(a, r, angle):
    return iso(a, r * np.cos(angle), r * np.sin(angle))


# ── drawing primitives ────────────────────────────────────────────────

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
    d1, d2 = p1 + n, p2 + n
    ax.annotate("", xy=(d2[0], d2[1]), xytext=(d1[0], d1[1]),
                arrowprops=dict(arrowstyle="<->", color="black", lw=0.6,
                                shrinkA=0, shrinkB=0), clip_on=False)
    mid = (d1 + d2) / 2
    ax.text(mid[0], mid[1], label, fontsize=fontsize, ha="center", va="center",
            color="black", clip_on=False,
            bbox=dict(facecolor="white", edgecolor="none", pad=2))


def leader(ax, anchor, text, offset, fontsize=12, **kw):
    anchor = np.array(anchor)
    tip = anchor + np.array(offset)
    ax.plot([anchor[0], tip[0]], [anchor[1], tip[1]], "k-", lw=0.5,
            clip_on=False)
    ax.plot(*anchor, "k.", ms=3, clip_on=False)
    ha = "left" if offset[0] > 0 else "right"
    pad = 0.15 if offset[0] > 0 else -0.15
    ax.text(tip[0] + pad, tip[1], text, fontsize=fontsize, ha=ha, va="center",
            color="black", clip_on=False, **kw)


# ── main drawing ──────────────────────────────────────────────────────

def read_config():
    raw = yaml.safe_load((CASE_DIR / "config.yaml").read_text())
    probe_r = float(raw["probe"]["radius"])
    r_max = float(raw["geometry"]["r_max"])
    z_half = float(raw["geometry"]["z_half"])
    n0 = float(raw["plasma"]["n0"])
    Te_K = float(raw["plasma"]["Te_K"])
    kTe_J = scc.k * Te_K
    debye = math.sqrt(scc.epsilon_0 * kTe_J / (n0 * scc.e**2))
    return dict(probe_r=probe_r, r_max=r_max, z_half=z_half,
                n0=n0, Te_K=Te_K, kTe_J=kTe_J, debye=debye)


def draw(cfg, dpi):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    a = cfg["probe_r"] * S
    rm = cfg["r_max"] * S
    zh = cfg["z_half"] * S
    lam = cfg["debye"] * S
    n0 = cfg["n0"]
    kTe_eV = cfg["kTe_J"] / scc.e

    fig, ax = plt.subplots(figsize=(16, 10), facecolor="white")
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(AX_LIMS[0], AX_LIMS[1])
    ax.set_ylim(AX_LIMS[2], AX_LIMS[3])

    # center axis
    u0, v0 = iso(AX_LIMS[0] / C30 * 0.4, 0, 0)
    u1, v1 = iso(AX_LIMS[1] / C30 * 0.8, 0, 0)
    ax.plot([u0, u1], [v0, v1], "k-.", lw=0.35, dashes=(8, 3, 2, 3), zorder=0)

    # cylinder domain
    draw_cylinder(ax, -zh, zh, rm)

    # sphere probe
    cx, cy = 0.0, 0.0
    ax.add_patch(Circle((cx, cy), a, facecolor="white", edgecolor="black",
                        lw=1.8, hatch="\\\\\\\\", zorder=10))

    # sheath circle
    sr = a + SHEATH_DEBYE * lam
    theta = np.linspace(0, 2 * np.pi, 300)
    ax.plot(sr * np.cos(theta) + cx, sr * np.sin(theta) + cy,
            "k--", lw=0.7, dashes=(5, 4), zorder=9)
    sx = cx + sr * np.cos(np.pi / 4)
    sy = cy + sr * np.sin(np.pi / 4)
    leader(ax, (sx, sy),
           f"sheath ≈ {SHEATH_DEBYE:.0f} λ_D\n({sr:.1f} mm)",
           (2.0, 1.5), fontsize=10, fontstyle="italic")

    # ── labels ────────────────────────────────────────────────────────

    leader(ax, (cx - a, cy), "PROBE\nV = +3 V",
           (-5, -3), fontsize=13, fontweight="bold")

    pu, pv = iso(zh * 0.5, rm * 0.5, 0)
    ax.text(pu, pv,
            f"Plasma\nn₀ = {n0:.3e} m⁻³\nkTe = {kTe_eV * 1e3:.1f} meV",
            fontsize=10, ha="center", va="center", color="black",
            bbox=dict(facecolor="white", edgecolor="black", lw=0.4, pad=4),
            zorder=11)

    ua, va = iso(zh + 1.5, 0, 0)
    ax.text(ua + 0.3, va, "axis of\nsymmetry", fontsize=9, ha="left",
            va="center", color="black", alpha=0.5, clip_on=False)

    # ── dimensions ────────────────────────────────────────────────────

    p1 = np.array(iso(zh, 0, 0))
    p2 = np.array(iso(zh, 0, rm))
    dim_line(ax, p1, p2, f"r = {rm:.1f} mm", np.array([1.5, 0.0]),
             fontsize=11)

    p1 = np.array(iso(-zh, -rm, 0))
    p2 = np.array(iso(zh, -rm, 0))
    perp = np.array([S30, -C30])
    dim_line(ax, p1, p2, f"{2 * zh:.1f} mm", perp * 2.0, fontsize=12)

    p1 = np.array([cx, cy])
    p2 = np.array([cx, cy + a])
    dim_line(ax, p1, p2, f"a = {a:.2f} mm", np.array([1.5, 0]), fontsize=10)

    # λ_D scale bar
    bar_x = AX_LIMS[0] + 2
    bar_y = AX_LIMS[2] + 3
    ax.plot([bar_x, bar_x + lam], [bar_y, bar_y], "k-", lw=1.5)
    ax.plot([bar_x, bar_x], [bar_y - 0.5, bar_y + 0.5], "k-", lw=0.8)
    ax.plot([bar_x + lam, bar_x + lam], [bar_y - 0.5, bar_y + 0.5],
            "k-", lw=0.8)
    ax.text(bar_x + lam / 2, bar_y - 0.8,
            f"λ_D = {lam:.2f} mm    a/λ_D = {cfg['probe_r'] / cfg['debye']:.2f}",
            fontsize=10, ha="center", va="top", color="black")

    fig.text(0.5, 0.97, "Biased Collection (+3 V)",
             fontsize=18, fontweight="bold", ha="center", va="top",
             color="black")

    out = CASE_DIR / "viz" / "schematic_2_biased_3v.png"
    fig.savefig(str(out), dpi=dpi, facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B&W isometric schematic")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args(argv)
    draw(read_config(), args.dpi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
