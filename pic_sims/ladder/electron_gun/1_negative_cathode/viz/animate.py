#!/usr/bin/env python3
"""Presentation animation for emitter.negative_cathode (no gate logic).

Reads an explicitly selected COMPLETE run and renders a potential/density movie.
It never writes into a run or analysis directory -- output goes to
``animations/`` (git-ignored) by default.

    python animate.py --run outputs/<run-id> [--out PATH] [--fps 10]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent.parent
_pic_root = CASE_DIR  # walk up to pic_sims/ (ladder_contract, shared plumbing)
while not (_pic_root / "ladder_contract.py").is_file():
    _pic_root = _pic_root.parent
sys.path.insert(0, str(_pic_root))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc  # noqa: E402
from analyze import field_rz  # noqa: E402  (shared field reader, no gate logic)

ANIM_ROOT = CASE_DIR / "viz"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="negative_cathode animation")
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--fps", type=float, default=10.0)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    evidence = lc.load_run(args.run)  # raises unless COMPLETE
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
    print(f"[negative_cathode] {len(its)} frames: {its[0]}..{its[-1]}")

    def frame(it):
        phi, r, z = field_rz(ts, "phi", it)
        rho, _, _ = field_rz(ts, "rho", it)
        ne = np.abs(rho) / scc.e
        return (np.vstack([phi[::-1], phi]), np.vstack([ne[::-1], ne]),
                np.concatenate([-r[::-1], r]) * 1e3, z * 1e3)

    PHI, NE, rr, zmm = frame(its[-1])
    vlim = max(abs(PHI.min()), abs(PHI.max()), 1.0)
    ne_vmax = max(1.0, np.percentile(NE, 99))
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.5, 5.2), sharey=True)
    P0, N0, _, _ = frame(its[0])
    ext = [zmm.min(), zmm.max(), rr.min(), rr.max()]
    imP = axL.imshow(P0, origin="lower", extent=ext, aspect="auto",
                     cmap="RdBu_r", vmin=-vlim, vmax=vlim)
    fig.colorbar(imP, ax=axL, label="phi [V]"); axL.set_title("potential phi")
    imN = axR.imshow(N0, origin="lower", extent=ext, aspect="auto",
                     cmap="inferno", vmin=0, vmax=ne_vmax)
    fig.colorbar(imN, ax=axR, label="n_e [m^-3]")
    axR.set_title("electron density n_e")
    for ax in (axL, axR):
        ax.set_xlabel("z [mm]")
    axL.set_ylabel("r [mm] (mirrored)")
    sup = fig.suptitle("")

    def update(i):
        it = its[i]
        P, N, _, _ = frame(it)
        imP.set_data(P); imN.set_data(N)
        sup.set_text(f"negative_cathode   step {it}")
        return imP, imN

    anim = FuncAnimation(fig, update, frames=len(its), blit=False)
    try:
        anim.save(str(out), writer=FFMpegWriter(fps=args.fps, bitrate=2800))
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
