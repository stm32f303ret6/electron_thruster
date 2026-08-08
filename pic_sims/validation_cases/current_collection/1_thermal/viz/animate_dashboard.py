#!/usr/bin/env python3
"""Three-panel dashboard animation for collector.thermal.

    Panel 1: phi(r,z) — electrostatic potential (sheath structure)
    Panel 2: n_e(r,z) — electron density
    Panel 3: I_e vs time — collected electron current approaching theory

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
from analyze import current_history, field_rz, read_eb_scraped, sheath_profile, sheath_radius
from helpers import load_config

ANIM_ROOT = CASE_DIR / "viz"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="collector.thermal dashboard")
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--fps", type=float, default=10.0)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    evidence = lc.load_run(args.run)
    cfg = load_config(evidence.dir / "config_used.yaml")
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

    # precompute current history
    scraped = read_eb_scraped(cfg, diags)
    steps, hist = current_history(cfg, scraped)
    I_e = hist.get("electrons", np.array([]))
    t_scrape_us = steps * cfg.time_step * 1e6

    # precompute field limits from final frame
    def get_fields(it):
        phi, r, z = field_rz(ts, "phi", it)
        rho_e, _, _ = field_rz(ts, "rho_electrons", it)
        ne = np.abs(rho_e) / scc.e
        rr = np.concatenate([-r[::-1], r]) * 1e3
        PHI = np.vstack([phi[::-1], phi])
        NE = np.vstack([ne[::-1], ne])
        return PHI, NE, rr, z * 1e3

    PHI_last, NE_last, rr, zmm = get_fields(its[-1])
    vlim = max(abs(PHI_last.min()), abs(PHI_last.max()), 0.05)
    ne_vmax = max(1.5 * cfg.n0, np.percentile(NE_last, 99))
    ext = [zmm.min(), zmm.max(), rr.min(), rr.max()]

    Ie_max = max(I_e.max() * 1e6 if len(I_e) else 1, cfg.I_th_e * 1e6) * 1.3
    t_max_us = cfg.max_steps * cfg.time_step * 1e6

    fps = args.fps
    fig = plt.figure(figsize=(14, 10))

    # title card (on blank figure, before any axes/colorbars)
    writer = FFMpegWriter(fps=fps, bitrate=4000)
    writer.setup(fig, str(out), dpi=150)
    fig.text(0.5, 0.55, "Thermal Collection",
             fontsize=22, fontweight="bold", ha="center", va="center",
             color="#333333")
    fig.text(0.5, 0.40,
             "Sphere probe at plasma potential (V = 0)\n"
             "Pure thermal current collection — no sheath",
             fontsize=13, ha="center", va="center", color="#555555",
             linespacing=1.5)
    for _ in range(int(round(2.0 * fps))):
        writer.grab_frame()
    fig.clf()

    # build panels: electron density on top (full width), phi + current on bottom
    gs = fig.add_gridspec(2, 2, hspace=0.32, wspace=0.30,
                          left=0.08, right=0.95, top=0.90, bottom=0.07)
    ax1 = fig.add_subplot(gs[0, :])
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[1, 1])

    PHI0, NE0, _, _ = get_fields(its[0])
    imN = ax1.imshow(NE0, origin="lower", extent=ext, aspect="equal",
                     cmap="inferno", vmin=0, vmax=ne_vmax)
    fig.colorbar(imN, ax=ax1, label="n_e [m⁻³]", shrink=0.75)
    ax1.set_title("Electron density n_e")
    ax1.set_xlabel("z [mm]")
    ax1.set_ylabel("r [mm] (mirrored)")
    ax1.add_patch(plt.Circle((0.0, 0.0), cfg.probe_radius * 1e3,
                              color="0.4", zorder=6))

    imP = ax2.imshow(PHI0, origin="lower", extent=ext, aspect="auto",
                     cmap="RdBu_r", vmin=-vlim, vmax=vlim)
    fig.colorbar(imP, ax=ax2, label="φ [V]", shrink=0.85)
    ax2.set_title("Potential φ")
    ax2.set_xlabel("z [mm]")
    ax2.set_ylabel("r [mm] (mirrored)")
    ax2.add_patch(plt.Circle((0.0, 0.0), cfg.probe_radius * 1e3,
                              color="0.4", zorder=6))

    line_e, = ax3.plot([], [], color="tab:blue", lw=1.2, label="I_e")
    ax3.axhline(cfg.I_th_e * 1e6, color="gray", ls="--", lw=0.8,
                label=f"I_th = {cfg.I_th_e*1e6:.4f} μA")
    ax3.set_xlim(0, t_max_us)
    ax3.set_ylim(0, Ie_max)
    ax3.set_ylabel("I_e [μA]")
    ax3.set_xlabel("time [μs]")
    ax3.legend(fontsize=7, loc="lower right")
    ax3.grid(alpha=0.3)

    sup = fig.suptitle("")

    # animation frames
    for fi in range(len(its)):
        it = its[fi]
        t_us = it * cfg.time_step * 1e6

        PHI, NE, _, _ = get_fields(it)
        imP.set_data(PHI)
        imN.set_data(NE)

        mask = steps <= it
        if mask.any():
            line_e.set_data(t_scrape_us[mask], I_e[mask] * 1e6)
        else:
            line_e.set_data([], [])

        sup.set_text(f"Thermal Collection    step {it}    t = {t_us:.2f} μs")
        writer.grab_frame()

    for _ in range(int(round(fps))):
        writer.grab_frame()

    writer.finish()
    plt.close(fig)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
