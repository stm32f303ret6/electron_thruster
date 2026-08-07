#!/usr/bin/env python3
"""Three-panel dashboard animation for capstone.high_thrust (300 V ceiling).

    Panel 1: Thrust [nN] + Power [mW] vs time (twin axes)
    Panel 2: n_beam(r,z) — beam electron density with can outline
    Panel 3: beam fates — % escaped vs % returned to spacecraft

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
    ap = argparse.ArgumentParser(description="capstone.high_thrust dashboard")
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
    thrust_nN = np.atleast_1d(ledger["F_beam_N"]) * 1e9
    power_mW = np.abs(np.atleast_1d(ledger["V_cathode"])) * cfg.i_beam * 1e3
    pct_escape = np.atleast_1d(ledger["pct_escape"])
    pct_return = (np.atleast_1d(ledger["pct_body"])
                  + np.atleast_1d(ledger["pct_cathode"]))

    def get_fields(it):
        phi, r, z = field_rz(ts, "phi", it)
        rho, _, _ = field_rz(ts, "rho_beam_electrons", it)
        nb = np.abs(rho) / scc.e
        rr = np.concatenate([-r[::-1], r]) * 1e3
        return np.vstack([nb[::-1], nb]), rr, z * 1e3

    NB_last, rr, zmm = get_fields(its[-1])
    nb_vmax = max(1.0, np.percentile(NB_last, 99.5))
    ext = [zmm.min(), zmm.max(), rr.min(), rr.max()]

    t_end_ns = cfg.t_end * 1e9
    thrust_max = max(thrust_nN.max() if len(thrust_nN) else 1, 15) * 1.3
    power_max = max(power_mW.max() if len(power_mW) else 1, 70) * 1.3

    fps = args.fps
    fig = plt.figure(figsize=(20, 5.5))

    writer = FFMpegWriter(fps=fps, bitrate=4000)
    writer.setup(fig, str(out), dpi=150)
    fig.text(0.5, 0.55, "High Thrust (300 V ceiling)",
             fontsize=22, fontweight="bold", ha="center", va="center",
             color="#333333")
    fig.text(0.5, 0.40,
             "Same geometry at hardware ceiling (300 V)\n"
             "Thrust + power, beam density, electron fates",
             fontsize=13, ha="center", va="center", color="#555555",
             linespacing=1.5)
    for _ in range(int(round(2.0 * fps))):
        writer.grab_frame()
    fig.clf()

    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1], wspace=0.35,
                          left=0.05, right=0.97, top=0.85, bottom=0.12)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax3 = fig.add_subplot(gs[2])

    # Panel 1: thrust + power (twin y-axes)
    line_t, = ax1.plot([], [], color="tab:green", lw=1.5, label="Thrust")
    ax1.set_xlim(0, t_end_ns)
    ax1.set_ylim(-1, thrust_max)
    ax1.set_ylabel("Thrust [nN]", color="tab:green")
    ax1.set_xlabel("time [ns]")
    ax1.tick_params(axis="y", labelcolor="tab:green")
    ax1.grid(alpha=0.3)

    ax1p = ax1.twinx()
    line_p, = ax1p.plot([], [], color="tab:purple", lw=1.0, alpha=0.7,
                        label="Power")
    ax1p.set_ylim(0, power_max)
    ax1p.set_ylabel("Power [mW]", color="tab:purple")
    ax1p.tick_params(axis="y", labelcolor="tab:purple")

    lines_1 = [line_t, line_p]
    ax1.legend(lines_1, [l.get_label() for l in lines_1],
               fontsize=7, loc="center right")
    ax1.set_title("Thrust & Power")

    # Panel 2: beam density field
    NB0, _, _ = get_fields(its[0])
    imN = ax2.imshow(NB0, origin="lower", extent=ext, aspect="auto",
                     cmap="inferno", vmin=0, vmax=nb_vmax)
    fig.colorbar(imN, ax=ax2, label="n_beam [m⁻³]", shrink=0.85)
    ax2.set_title("Beam electron density")
    ax2.set_xlabel("z [mm]"); ax2.set_ylabel("r [mm] (mirrored)")
    _draw_can(ax2, geom)

    # Panel 3: beam fates
    line_esc, = ax3.plot([], [], color="tab:green", lw=1.5, label="% escaped")
    line_ret, = ax3.plot([], [], color="tab:red", lw=1.2, label="% returned")
    ax3.set_xlim(0, t_end_ns)
    ax3.set_ylim(-2, 105)
    ax3.set_ylabel("beam fraction [%]"); ax3.set_xlabel("time [ns]")
    ax3.legend(fontsize=8, loc="center right"); ax3.grid(alpha=0.3)
    ax3.set_title("Beam fates")

    sup = fig.suptitle("")

    for fi in range(len(its)):
        it = its[fi]
        t_ns = it * cfg.dt * 1e9
        NB, _, _ = get_fields(it)
        imN.set_data(NB)

        mask = steps_l <= it
        if mask.any():
            line_t.set_data(t_l_ns[mask], thrust_nN[mask])
            line_p.set_data(t_l_ns[mask], power_mW[mask])
            line_esc.set_data(t_l_ns[mask], pct_escape[mask])
            line_ret.set_data(t_l_ns[mask], pct_return[mask])
        else:
            line_t.set_data([], [])
            line_p.set_data([], [])
            line_esc.set_data([], [])
            line_ret.set_data([], [])

        sup.set_text(f"High Thrust 300 V    step {it}    t = {t_ns:.1f} ns")
        writer.grab_frame()

    for _ in range(int(round(fps))):
        writer.grab_frame()

    writer.finish()
    plt.close(fig)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
