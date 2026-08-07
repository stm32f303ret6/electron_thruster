#!/usr/bin/env python3
"""Three-panel dashboard animation for capstone.floating_body (200 V baseline).

    Panel 1: phi(r,z) — electrostatic potential
    Panel 2: n_beam(r,z) — beam electron density
    Panel 3: phi_body vs time — charge-pump oscillation settling to equilibrium

    python animate_dashboard.py --run outputs/<run-id> [--out PATH] [--fps 10]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CASE_DIR.parents[1]))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc
from analyze import field_rz, load_ledger
from helpers import load_config

ANIM_ROOT = CASE_DIR / "viz"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="capstone.floating_body dashboard")
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--fps", type=float, default=10.0)
    return ap.parse_args(argv)


def _draw_can(ax, geom):
    from matplotlib.patches import Rectangle

    def both(zlo, zhi, rin, rout):
        for sign in (1.0, -1.0):
            r0, r1 = sorted((sign * rin, sign * rout))
            ax.add_patch(Rectangle((zlo * 1e3, r0 * 1e3), (zhi - zlo) * 1e3,
                                   (r1 - r0) * 1e3, color="0.45", zorder=6))

    both(geom.z_bot, geom.z_top, geom.r_in, geom.r_p)
    both(geom.z_bot, geom.zfloort, 0.0, geom.r_cath)
    both(geom.z_bot, geom.zfloort, geom.r_cath_out, geom.r_p)
    both(geom.zlidb, geom.z_top, geom.r_slit, geom.r_p)


def main(argv=None) -> int:
    args = parse_args(argv)
    evidence = lc.load_run(args.run)
    cfg = load_config(evidence.dir / "config_used.yaml")
    geom = cfg.geometry()
    out = args.out or (ANIM_ROOT / f"{evidence.run_id}_dashboard.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter
    from openpmd_viewer import OpenPMDTimeSeries

    diags = str(evidence.diags_dir)
    ts = OpenPMDTimeSeries(os.path.join(diags, "fields"), check_all_files=False)
    its = ts.iterations
    print(f"[dashboard] {len(its)} field frames: {its[0]}..{its[-1]}")

    ledger = load_ledger(evidence.diags_dir)
    steps_l = np.atleast_1d(ledger["step"]).astype(float)
    t_l_ns = np.atleast_1d(ledger["t"]) * 1e9
    phi_body_l = np.atleast_1d(ledger["phi_body"])

    def get_fields(it):
        phi, r, z = field_rz(ts, "phi", it)
        rho, _, _ = field_rz(ts, "rho_beam_electrons", it)
        nb = np.abs(rho) / scc.e
        rr = np.concatenate([-r[::-1], r]) * 1e3
        return np.vstack([phi[::-1], phi]), np.vstack([nb[::-1], nb]), rr, z * 1e3

    PHI_last, NB_last, rr, zmm = get_fields(its[-1])
    vlim = max(abs(PHI_last.min()), abs(PHI_last.max()), 1.0)
    nb_vmax = max(1.0, np.percentile(NB_last, 99.5))
    ext = [zmm.min(), zmm.max(), rr.min(), rr.max()]

    t_end_ns = cfg.t_end * 1e9
    phi_lo = min(phi_body_l.min(), -5) - 2
    phi_hi = max(phi_body_l.max(), 20) + 2

    fps = args.fps
    fig = plt.figure(figsize=(20, 5.5))

    writer = FFMpegWriter(fps=fps, bitrate=4000)
    writer.setup(fig, str(out), dpi=150)
    fig.text(0.5, 0.55, "Chipsat Thruster (200 V baseline)",
             fontsize=22, fontweight="bold", ha="center", va="center",
             color="#333333")
    fig.text(0.5, 0.40,
             "Floating body charge-pump equilibrium\n"
             "Panel 3: body potential settling to steady state",
             fontsize=13, ha="center", va="center", color="#555555",
             linespacing=1.5)
    for _ in range(int(round(2.0 * fps))):
        writer.grab_frame()
    fig.clf()

    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1], wspace=0.30,
                          left=0.04, right=0.97, top=0.85, bottom=0.12)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharey=ax1)
    ax3 = fig.add_subplot(gs[2])

    PHI0, NB0, _, _ = get_fields(its[0])
    imP = ax1.imshow(PHI0, origin="lower", extent=ext, aspect="auto",
                     cmap="RdBu_r", vmin=-vlim, vmax=vlim)
    fig.colorbar(imP, ax=ax1, label="φ [V]", shrink=0.85)
    ax1.set_title("Potential φ")
    ax1.set_xlabel("z [mm]"); ax1.set_ylabel("r [mm] (mirrored)")

    imN = ax2.imshow(NB0, origin="lower", extent=ext, aspect="auto",
                     cmap="inferno", vmin=0, vmax=nb_vmax)
    fig.colorbar(imN, ax=ax2, label="n_beam [m⁻³]", shrink=0.85)
    ax2.set_title("Beam electron density")
    ax2.set_xlabel("z [mm]")

    for ax in (ax1, ax2):
        _draw_can(ax, geom)

    line_phi, = ax3.plot([], [], color="tab:blue", lw=1.2, label="φ_body")
    ax3.axhline(0.0, color="k", lw=0.5)
    ax3.set_xlim(0, t_end_ns)
    ax3.set_ylim(phi_lo, phi_hi)
    ax3.set_ylabel("φ_body [V]"); ax3.set_xlabel("time [ns]")
    ax3.legend(fontsize=8, loc="lower right"); ax3.grid(alpha=0.3)

    sup = fig.suptitle("")

    for fi in range(len(its)):
        it = its[fi]
        t_ns = it * cfg.dt * 1e9
        PHI, NB, _, _ = get_fields(it)
        imP.set_data(PHI); imN.set_data(NB)

        mask = steps_l <= it
        if mask.any():
            line_phi.set_data(t_l_ns[mask], phi_body_l[mask])
        else:
            line_phi.set_data([], [])

        sup.set_text(f"Chipsat 200 V    step {it}    t = {t_ns:.1f} ns")
        writer.grab_frame()

    for _ in range(int(round(fps))):
        writer.grab_frame()

    writer.finish()
    plt.close(fig)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
