#!/usr/bin/env python3
"""Three-panel animation: electron density | collector current | median KE.

Reads a COMPLETE run and renders a single-row MP4 with:
  1. Electron density n_e(r,z) [mirrored RZ]
  2. Collector current vs time [mA], building up frame-by-frame
  3. Median kinetic energy of electrons arriving at the collector vs time

    python animate_dashboard.py --run outputs/<run-id> [--out PATH] [--fps 10]
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path

import numpy as np
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parents[1]))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc
from analyze import field_rz, ke_eV

SPECIES_NAME = "electrons"
ANIM_ROOT = CASE_DIR / "animations"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="negative_cathode 3-panel animation")
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--fps", type=float, default=10.0)
    return ap.parse_args(argv)


def read_scrape_by_iteration(diags: str):
    """Read collector (zhi) scrape data grouped by iteration.

    Returns dict mapping iteration -> (ke_eV_array, weight_array).
    """
    import openpmd_api as io

    sub = os.path.join(diags, "scrape", "particles_at_zhi")
    if not glob.glob(os.path.join(sub, "*.h5")):
        return {}

    result = {}
    series = io.Series(os.path.join(sub, "openpmd_%T.h5"), io.Access.read_only)
    for it in series.iterations:
        parts = series.iterations[it].particles
        if SPECIES_NAME not in parts:
            continue
        p = parts[SPECIES_NAME]

        mxh = p["momentum"]["x"]
        myh = p["momentum"]["y"]
        mzh = p["momentum"]["z"]
        dmx = mxh.load_chunk()
        dmy = myh.load_chunk()
        dmz = mzh.load_chunk()
        wh = p["weighting"][io.Mesh_Record_Component.SCALAR]
        dw = wh.load_chunk()
        series.flush()

        n = np.asarray(dw).size
        if n == 0:
            continue

        px = np.asarray(dmx) * mxh.unit_SI
        py = np.asarray(dmy) * myh.unit_SI
        pz = np.asarray(dmz) * mzh.unit_SI
        w = np.asarray(dw) * wh.unit_SI
        ke = ke_eV(px, py, pz)
        result[it] = (ke, w)
    series.close()
    return result


def main(argv=None) -> int:
    args = parse_args(argv)
    evidence = lc.load_run(args.run)
    out = args.out or (ANIM_ROOT / f"{evidence.run_id}_dashboard.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    cfg_path = evidence.dir / "config_used.yaml"
    from helpers import load_config
    cfg = load_config(cfg_path)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter, FuncAnimation
    from openpmd_viewer import OpenPMDTimeSeries

    diags = str(evidence.diags_dir)
    ts = OpenPMDTimeSeries(os.path.join(diags, "fields"), check_all_files=False)
    its = ts.iterations
    print(f"[dashboard] {len(its)} field frames: {its[0]}..{its[-1]}")

    scrape_data = read_scrape_by_iteration(diags)
    scrape_iters = sorted(scrape_data.keys())
    print(f"[dashboard] {len(scrape_iters)} collector scrape dumps")

    dt = cfg.time_step
    scrape_period = cfg.scrape_period

    # Precompute current and median KE at each scrape iteration
    scrape_steps = np.arange(scrape_period, cfg.max_steps + 1, scrape_period)
    current_mA = np.zeros(len(scrape_steps))
    median_ke = np.full(len(scrape_steps), np.nan)
    cum_ke = []
    cum_w = []

    for idx, step in enumerate(scrape_steps):
        if step in scrape_data:
            ke_arr, w_arr = scrape_data[step]
            I = w_arr.sum() * scc.e / (scrape_period * dt)
            current_mA[idx] = I * 1e3
            cum_ke.append(ke_arr)
            cum_w.append(w_arr)
        if cum_ke:
            all_ke = np.concatenate(cum_ke)
            all_w = np.concatenate(cum_w)
            sort_idx = np.argsort(all_ke)
            sorted_ke = all_ke[sort_idx]
            sorted_w = all_w[sort_idx]
            cum_weight = np.cumsum(sorted_w)
            half = cum_weight[-1] / 2.0
            median_ke[idx] = sorted_ke[np.searchsorted(cum_weight, half)]

    scrape_times_ns = scrape_steps * dt * 1e9
    max_time_ns = cfg.max_steps * dt * 1e9

    # Precompute final frame for axis limits
    def get_ne(it):
        rho, r, z = field_rz(ts, "rho", it)
        ne = np.abs(rho) / scc.e
        rr = np.concatenate([-r[::-1], r]) * 1e3
        NE = np.vstack([ne[::-1], ne])
        return NE, rr, z * 1e3

    NE_last, rr, zmm = get_ne(its[-1])
    ne_vmax = max(1.0, np.percentile(NE_last, 99))
    ext = [zmm.min(), zmm.max(), rr.min(), rr.max()]

    current_max = max(current_mA.max() * 1.15, cfg.beam_current * 1e3 * 1.15) if current_mA.max() > 0 else cfg.beam_current * 1e3 * 1.3
    ke_valid = median_ke[np.isfinite(median_ke)]
    ke_ylim = (0, max(ke_valid.max() * 1.15, 1.0)) if len(ke_valid) else (0, cfg.ke_max_ev)

    # Set up figure
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 5))
    fig.subplots_adjust(wspace=0.35, left=0.05, right=0.97, top=0.88, bottom=0.13)

    # Panel 1: electron density
    NE0, _, _ = get_ne(its[0])
    im = ax1.imshow(NE0, origin="lower", extent=ext, aspect="auto",
                    cmap="inferno", vmin=0, vmax=ne_vmax)
    fig.colorbar(im, ax=ax1, label=r"$n_e$ [m$^{-3}$]", shrink=0.9)
    ax1.set_xlabel("z [mm]")
    ax1.set_ylabel("r [mm] (mirrored)")
    ax1.set_title("Electron density")

    # Panel 2: collector current
    line_curr, = ax2.plot([], [], "-o", ms=2, color="tab:green", lw=1.2)
    ax2.axhline(cfg.beam_current * 1e3, color="gray", ls="--", lw=1,
                label=f"emitted = {cfg.beam_current*1e3:.3f} mA")
    ax2.set_xlim(0, max_time_ns)
    ax2.set_ylim(-current_max * 0.05, current_max)
    ax2.set_xlabel("time [ns]")
    ax2.set_ylabel("current [mA]")
    ax2.set_title("Collector current")
    ax2.legend(fontsize=7, loc="upper left")
    ax2.grid(alpha=0.3)

    # Panel 3: median KE
    line_ke, = ax3.plot([], [], "-s", ms=2, color="tab:orange", lw=1.2)
    expected_ke = cfg.expected_collector_ke_eV()
    ax3.axhline(expected_ke, color="gray", ls="--", lw=1,
                label=f"analytic = {expected_ke:.1f} eV")
    ax3.set_xlim(0, max_time_ns)
    ax3.set_ylim(*ke_ylim)
    ax3.set_xlabel("time [ns]")
    ax3.set_ylabel("median KE [eV]")
    ax3.set_title("Median arrival KE (collector)")
    ax3.legend(fontsize=7, loc="lower right")
    ax3.grid(alpha=0.3)

    sup = fig.suptitle("")

    def update(frame_idx):
        it = its[frame_idx]
        t_ns = it * dt * 1e9

        # Panel 1: update density
        NE, _, _ = get_ne(it)
        im.set_data(NE)

        # Panel 2: current up to this iteration
        mask = scrape_steps <= it
        if mask.any():
            line_curr.set_data(scrape_times_ns[mask], current_mA[mask])
        else:
            line_curr.set_data([], [])

        # Panel 3: median KE up to this iteration
        if mask.any():
            t_plot = scrape_times_ns[mask]
            ke_plot = median_ke[mask]
            valid = np.isfinite(ke_plot)
            line_ke.set_data(t_plot[valid], ke_plot[valid])
        else:
            line_ke.set_data([], [])

        sup.set_text(f"negative_cathode   step {it}   t = {t_ns:.2f} ns")
        return im, line_curr, line_ke

    anim = FuncAnimation(fig, update, frames=len(its), blit=False)
    try:
        anim.save(str(out), writer=FFMpegWriter(fps=args.fps, bitrate=4000))
        print(f"wrote {out}")
    except Exception as exc:
        print(f"ffmpeg failed ({exc})", file=sys.stderr)
        return 1
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
