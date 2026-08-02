#!/usr/bin/env python3
"""Presentation animation for a capstone.floating_body run (no gate logic).

Reads one explicitly selected COMPLETE run and renders a potential/density
movie with the can cross-section drawn and a phi_body/escape HUD from the CSV
ledger.  Never writes into a run or analysis directory.

    python animate.py --run outputs/<run-id> [--out PATH] [--fps 10]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parents[1]))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc  # noqa: E402
from analyze import field_rz, load_ledger  # noqa: E402
from helpers import load_config  # noqa: E402

ANIM_ROOT = CASE_DIR / "animations"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="chipsat capstone animation")
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--fps", type=float, default=10.0)
    return ap.parse_args(argv)


def _draw_can(ax, geom):
    """Fill the can's conductor cross-section (mirrored +-r) in grey."""
    from matplotlib.patches import Rectangle

    def both(zlo, zhi, rin, rout):
        for sign in (1.0, -1.0):
            r0, r1 = sorted((sign * rin, sign * rout))
            ax.add_patch(Rectangle((zlo * 1e3, r0 * 1e3), (zhi - zlo) * 1e3,
                                   (r1 - r0) * 1e3, color="0.45", zorder=6))

    both(geom.z_bot, geom.z_top, geom.r_in, geom.r_p)          # wall
    both(geom.z_bot, geom.zfloort, 0.0, geom.r_cath)           # cathode disk
    both(geom.z_bot, geom.zfloort, geom.r_cath_out, geom.r_p)  # floor annulus
    both(geom.zlidb, geom.z_top, geom.r_slit, geom.r_p)        # lid


def main(argv=None) -> int:
    args = parse_args(argv)
    evidence = lc.load_run(args.run)
    cfg = load_config(evidence.dir / "config_used.yaml")
    geom = cfg.geometry()
    out = args.out or (ANIM_ROOT / f"{evidence.run_id}_fields.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
    from openpmd_viewer import OpenPMDTimeSeries

    ts = OpenPMDTimeSeries(os.path.join(str(evidence.diags_dir), "fields"),
                           check_all_files=False)
    its = ts.iterations
    ledger = load_ledger(evidence.diags_dir)
    steps_l = np.atleast_1d(ledger["step"]).astype(float)
    print(f"[capstone] {len(its)} frames: {its[0]}..{its[-1]}")

    def frame(it):
        phi, r, z = field_rz(ts, "phi", it)
        rho, _, _ = field_rz(ts, "rho_beam_electrons", it)
        nb = np.abs(rho) / scc.e
        return (np.vstack([phi[::-1], phi]), np.vstack([nb[::-1], nb]),
                np.concatenate([-r[::-1], r]) * 1e3, z * 1e3)

    PHI, NB, rr, zmm = frame(its[-1])
    vlim = max(abs(PHI.min()), abs(PHI.max()), 1.0)
    nb_vmax = max(1.0, np.percentile(NB, 99.5))
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.4), sharey=True)
    P0, N0, _, _ = frame(its[0])
    ext = [zmm.min(), zmm.max(), rr.min(), rr.max()]
    imP = axL.imshow(P0, origin="lower", extent=ext, aspect="auto",
                     cmap="RdBu_r", vmin=-vlim, vmax=vlim)
    fig.colorbar(imP, ax=axL, label="phi [V]")
    axL.set_title("potential phi")
    imN = axR.imshow(N0, origin="lower", extent=ext, aspect="auto",
                     cmap="inferno", vmin=0, vmax=nb_vmax)
    fig.colorbar(imN, ax=axR, label="n_beam [m^-3]")
    axR.set_title("beam electron density")
    for ax in (axL, axR):
        _draw_can(ax, geom)
        ax.set_xlabel("z [mm]")
    axL.set_ylabel("r [mm] (mirrored)")
    sup = fig.suptitle("")

    def hud(it):
        """phi_body / escape% from the nearest ledger row at or before `it`."""
        k = np.searchsorted(steps_l, it, side="right") - 1
        if k < 0:
            return ""
        return (f"phi_body={ledger['phi_body'][k]:+.1f} V   "
                f"escape={ledger['pct_escape'][k]:.1f} %")

    def update(i):
        it = its[i]
        P, N, _, _ = frame(it)
        imP.set_data(P)
        imN.set_data(N)
        sup.set_text(f"capstone.floating_body   t={it*cfg.dt*1e9:.1f} ns "
                     f"(step {it})   {hud(it)}")
        return imP, imN

    anim = FuncAnimation(fig, update, frames=len(its), blit=False)
    try:
        anim.save(str(out), writer=FFMpegWriter(fps=args.fps, bitrate=3000))
        print(f"wrote {out}")
    except Exception as exc:  # noqa: BLE001
        gif = out.with_suffix(".gif")
        print(f"ffmpeg failed ({exc}); writing {gif}")
        anim.save(str(gif), writer=PillowWriter(fps=args.fps))
        print(f"wrote {gif}")
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
