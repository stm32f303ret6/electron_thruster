#!/usr/bin/env python3
"""Self-consistent potential map phi(r,z) from a run's last field dump.

Two panels sharing the red/blue electrode convention of schematic.py:
left, the full domain on a +-20 V scale (sheath + plume containment);
right, a zoom on the can with the full -200..+16 V range (acceleration
gap and floating-body sheath).

    python potential_map.py [--run outputs/<run-id>] [--dpi 300]
                            [--format png|pdf|svg]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

CASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CASE_DIR.parents[1]))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc
from analyze import field_rz, load_ledger
from helpers import load_config
from palette import BODY_EDGE, CATH_EDGE


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="phi(r,z) potential map")
    ap.add_argument("--run", type=Path, default=None,
                    help="run directory (default: outputs/LATEST)")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--format", choices=("png", "pdf", "svg"), default="png")
    return ap.parse_args(argv)


def draw_can(ax, geom):
    """Can cross-section overlay, electrode-colored (body red, cathode blue)."""
    from matplotlib.patches import Rectangle

    def both(zlo, zhi, rin, rout, color):
        for sign in (1.0, -1.0):
            r0, r1 = sorted((sign * rin, sign * rout))
            ax.add_patch(Rectangle((zlo * 1e3, r0 * 1e3), (zhi - zlo) * 1e3,
                                   (r1 - r0) * 1e3, facecolor=color,
                                   edgecolor="none", zorder=6))

    both(geom.z_bot, geom.z_top, geom.r_in, geom.r_p, BODY_EDGE)
    both(geom.z_floorb, geom.zfloort, geom.r_cath_out, geom.r_p, BODY_EDGE)
    both(geom.zlidb, geom.z_top, geom.r_slit, geom.r_p, BODY_EDGE)
    both(geom.z_floorb, geom.zfloort, 0.0, geom.r_cath, CATH_EDGE)


def main(argv=None) -> int:
    args = parse_args(argv)
    run = args.run
    if run is None:
        latest = (CASE_DIR / "outputs" / "LATEST").read_text().strip()
        run = CASE_DIR / "outputs" / latest
    evidence = lc.load_run(run)
    cfg = load_config(evidence.dir / "config_used.yaml")
    geom = cfg.geometry()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm
    from openpmd_viewer import OpenPMDTimeSeries

    ts = OpenPMDTimeSeries(os.path.join(str(evidence.diags_dir), "fields"),
                           check_all_files=False)
    it = ts.iterations[-1]
    t_ns = ts.t[-1] * 1e9
    phi, r, z = field_rz(ts, "phi", it)
    rr = np.concatenate([-r[::-1], r]) * 1e3
    zmm = z * 1e3
    PHI = np.vstack([phi[::-1], phi])

    ledger = load_ledger(evidence.diags_dir)
    phi_body = float(np.atleast_1d(ledger["phi_body"])[-1])

    fig, (axL, axR) = plt.subplots(
        1, 2, figsize=(15, 6.2), facecolor="white",
        gridspec_kw=dict(width_ratios=[1.35, 1.0], wspace=0.28))

    # left: full domain, clipped to +-20 V so sheath and plume are visible
    normL = TwoSlopeNorm(vmin=-20.0, vcenter=0.0, vmax=20.0)
    imL = axL.imshow(PHI, origin="lower", cmap="RdBu_r", norm=normL,
                     extent=[zmm.min(), zmm.max(), rr.min(), rr.max()],
                     aspect="equal", interpolation="nearest")
    axL.contour(zmm, rr, PHI, levels=[-5.0, -1.0, 1.0, 5.0, 10.0],
                colors="0.3", linewidths=0.5)
    draw_can(axL, geom)
    fig.colorbar(imL, ax=axL, label="φ [V]  (clipped to ±20 V)", shrink=0.9)
    axL.set_title(f"full domain — sheath & plume (t = {t_ns:.0f} ns)")
    axL.set_xlabel("z [mm]")
    axL.set_ylabel("r [mm]")

    # right: zoom on the can, full voltage range
    normR = TwoSlopeNorm(vmin=min(PHI.min(), -1.0), vcenter=0.0,
                         vmax=max(PHI.max(), 1.0))
    imR = axR.imshow(PHI, origin="lower", cmap="RdBu_r", norm=normR,
                     extent=[zmm.min(), zmm.max(), rr.min(), rr.max()],
                     aspect="equal", interpolation="nearest")
    axR.contour(zmm, rr, PHI, levels=[-150.0, -100.0, -50.0, -20.0, -5.0],
                colors="0.3", linewidths=0.5)
    draw_can(axR, geom)
    axR.set_xlim(-8.0, 6.0)
    axR.set_ylim(-8.0, 8.0)
    fig.colorbar(imR, ax=axR, label="φ [V]  (full range)", shrink=0.9)
    axR.set_title("zoom: acceleration gap inside the can")
    axR.set_xlabel("z [mm]")
    axR.set_ylabel("r [mm]")

    fig.suptitle(
        f"Self-consistent potential φ(r,z) — run {evidence.run_id}\n"
        f"body (red) at φ_body ≈ {phi_body:+.1f} V, cathode (blue) at "
        f"φ_body − {abs(cfg.cathode_offset):.0f} V",
        fontsize=13, fontweight="bold")

    out = CASE_DIR / "viz" / f"potential_map_2_chipsat_thruster.{args.format}"
    fig.savefig(str(out), dpi=args.dpi, facecolor="white",
                bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
