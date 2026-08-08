#!/usr/bin/env python3
"""Three-scenario dashboard animation for emitter.holed_anode.

For each scenario (A, B, C) renders a 2-second title card followed by a
3-panel animation (electron density | collector current | median arrival KE),
all concatenated into a single MP4.

    python animate_dashboard.py \
        --runs outputs/<A-run> outputs/<B-run> outputs/<C-run> \
        [--out PATH] [--fps 10]
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path

import numpy as np
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CASE_DIR.parents[1]))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc
from analyze import field_rz, ke_eV
from helpers import SPECIES_NAME, load_config, scenario_names

ANIM_ROOT = CASE_DIR / "viz"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="holed_anode 3-scenario dashboard")
    ap.add_argument("--runs", type=Path, nargs="+", required=True)
    ap.add_argument("--config", type=Path,
                    default=CASE_DIR / "config.yaml")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--fps", type=float, default=10.0)
    return ap.parse_args(argv)


def read_collector_scrape(diags: str):
    """Collector (zhi) scrape data grouped by iteration."""
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
        mxh = p["momentum"]["x"]; dmx = mxh.load_chunk()
        myh = p["momentum"]["y"]; dmy = myh.load_chunk()
        mzh = p["momentum"]["z"]; dmz = mzh.load_chunk()
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


# ── per-scenario data bundle ──────────────────────────────────────────

def load_scenario(evidence, cfg):
    """Precompute everything needed for the animation of one scenario."""
    from openpmd_viewer import OpenPMDTimeSeries

    diags = str(evidence.diags_dir)
    ts = OpenPMDTimeSeries(os.path.join(diags, "fields"), check_all_files=False)
    its = ts.iterations
    scrape = read_collector_scrape(diags)

    scrape_steps = np.arange(cfg.scrape_period, cfg.max_steps + 1,
                             cfg.scrape_period)
    current_mA = np.zeros(len(scrape_steps))
    median_ke = np.full(len(scrape_steps), np.nan)
    cum_ke, cum_w = [], []

    for idx, step in enumerate(scrape_steps):
        if step in scrape:
            ke_arr, w_arr = scrape[step]
            current_mA[idx] = (w_arr.sum() * scc.e
                               / (cfg.scrape_period * cfg.time_step) * 1e3)
            cum_ke.append(ke_arr)
            cum_w.append(w_arr)
        if cum_ke:
            all_ke = np.concatenate(cum_ke)
            all_w = np.concatenate(cum_w)
            si = np.argsort(all_ke)
            cw = np.cumsum(all_w[si])
            median_ke[idx] = all_ke[si][np.searchsorted(cw, cw[-1] / 2.0)]

    # final-frame limits
    rho_last, r, z = field_rz(ts, "rho", its[-1])
    ne_last = np.abs(rho_last) / scc.e
    NE_last = np.vstack([ne_last[::-1], ne_last])
    ne_vmax = max(1.0, np.percentile(NE_last, 99))
    rr = np.concatenate([-r[::-1], r]) * 1e3
    zmm = z * 1e3
    ext = [zmm.min(), zmm.max(), rr.min(), rr.max()]

    return dict(ts=ts, its=its, r=r, z=z, rr=rr, zmm=zmm, ext=ext,
                ne_vmax=ne_vmax,
                scrape_steps=scrape_steps, current_mA=current_mA,
                median_ke=median_ke,
                scrape_times_ns=scrape_steps * cfg.time_step * 1e9,
                max_time_ns=cfg.max_steps * cfg.time_step * 1e9)


# ── title-card descriptions ──────────────────────────────────────────

SCENARIO_INFO = {
    "A_low_current_small_hole": {
        "title": "Scenario A: Low Current, Small Hole",
        "desc": (
            "10 uA beam through a 0.7 mm aperture\n"
            "Stiff beam, negligible space charge\n"
            "Expected: ~all current transmits; only the thermal tail clips"
        ),
    },
    "B_high_current_small_hole": {
        "title": "Scenario B: High Current, Small Hole",
        "desc": (
            "400 uA beam through a 0.7 mm aperture\n"
            "Strong radial space charge blows the beam up\n"
            "Expected: significant current lost on the anode plate"
        ),
    },
    "C_high_current_big_hole": {
        "title": "Scenario C: High Current, Big Hole",
        "desc": (
            "400 uA beam through a 1.4 mm aperture\n"
            "Wider hole restores transmission despite space charge\n"
            "Expected: transmission recovered, proving aperture was the limiter"
        ),
    },
}

STAGE_INFO = {
    "title": "Holed-Anode Electron Gun (emitter.holed_anode)",
    "desc": (
        "Aperture transmission vs radial space charge\n\n"
        "A grounded anode plate with a hole on axis sits at the midplane.\n"
        "Three scenarios demonstrate that space charge widens the beam\n"
        "and that a larger hole restores transmission."
    ),
}


def main(argv=None) -> int:
    args = parse_args(argv)
    order = scenario_names(args.config)
    cohort = lc.load_complete_runs(args.runs)
    lc.check_cohort(cohort, stage_id="emitter.holed_anode",
                    require_scenarios=order)
    by_scn = {r.scenario: r for r in cohort}
    cfgs = {n: load_config(by_scn[n].dir / "config_used.yaml") for n in order}

    joint_id = "_".join(r.run_id[:8] for r in cohort)
    out = args.out or (ANIM_ROOT / f"{joint_id}_dashboard.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter
    from matplotlib.patches import Rectangle

    fps = args.fps

    # preload all scenario data
    data = {}
    for name in order:
        print(f"[dashboard] loading {name} ...")
        data[name] = load_scenario(by_scn[name], cfgs[name])

    # KE axis shared across scenarios (all arrive at ~the gap energy); density
    # and current axes are PER-SCENARIO — A runs at 10 uA vs B/C's 400 uA, so
    # a shared linear scale would render A's beam and current invisible.
    all_ke_valid = np.concatenate([
        data[n]["median_ke"][np.isfinite(data[n]["median_ke"])] for n in order])
    all_ke_max = max(all_ke_valid.max() * 1.15, 1.0) if len(all_ke_valid) else 120.0

    # figure setup
    fig = plt.figure(figsize=(14, 10))

    writer = FFMpegWriter(fps=fps, bitrate=4000)
    writer.setup(fig, str(out), dpi=150)

    def write_title_card(title, desc, n_frames):
        fig.clf()
        t1 = fig.text(0.5, 0.6, title, ha="center", va="center",
                      fontsize=18, fontweight="bold", color="#333333")
        t2 = fig.text(0.5, 0.32, desc, ha="center", va="center",
                      fontsize=12, color="#555555", linespacing=1.5)
        for _ in range(n_frames):
            writer.grab_frame()
        t1.remove()
        t2.remove()

    title_frames = int(round(2.0 * fps))

    write_title_card(STAGE_INFO["title"], STAGE_INFO["desc"], title_frames)

    # ── per-scenario animation ────────────────────────────────────────
    for name in order:
        cfg = cfgs[name]
        d = data[name]
        its = d["its"]
        info = SCENARIO_INFO.get(name, {"title": name, "desc": ""})

        # title card
        write_title_card(info["title"], info["desc"], title_frames)

        # set up panels: density on top row (full width), current + KE on bottom
        gs = fig.add_gridspec(2, 2, hspace=0.32, wspace=0.30,
                              left=0.08, right=0.95, top=0.90, bottom=0.07)
        ax1 = fig.add_subplot(gs[0, :])
        ax2 = fig.add_subplot(gs[1, 0])
        ax3 = fig.add_subplot(gs[1, 1])

        # panel 1: electron density
        rho0, r0, z0 = field_rz(d["ts"], "rho", its[0])
        ne0 = np.abs(rho0) / scc.e
        NE0 = np.vstack([ne0[::-1], ne0])
        ax1.set_anchor('C')
        im = ax1.imshow(NE0, origin="lower", extent=d["ext"], aspect="equal",
                        cmap="inferno", vmin=0, vmax=d["ne_vmax"])
        fig.colorbar(im, cax=ax1.inset_axes([1.02, 0.1, 0.015, 0.8]),
                     label=r"$n_e$ [m$^{-3}$]")
        ax1.set_xlabel("z [mm]"); ax1.set_ylabel("r [mm] (mirrored)")
        ax1.set_title("Electron density")
        # draw anode plate
        z0p = cfg.anode_z_front * 1e3
        tw = cfg.anode_thickness * 1e3
        rh = cfg.hole_radius * 1e3
        rm = cfg.r_max * 1e3
        ax1.add_patch(Rectangle((z0p, rh), tw, rm - rh,
                                color="0.45", zorder=6))
        ax1.add_patch(Rectangle((z0p, -rm), tw, rm - rh,
                                color="0.45", zorder=6))

        # panel 2: collector current
        ax2.axhline(cfg.beam_current * 1e3, color="gray", ls="--", lw=1,
                    label=f"emitted = {cfg.beam_current*1e3:.3f} mA")
        line_curr, = ax2.plot([], [], "-o", ms=2, color="tab:green", lw=1.2)
        curr_max = max(d["current_mA"].max(), cfg.beam_current * 1e3) * 1.15
        ax2.set_xlim(0, d["max_time_ns"])
        ax2.set_ylim(-curr_max * 0.05, curr_max)
        ax2.set_xlabel("time [ns]"); ax2.set_ylabel("current [mA]")
        ax2.set_title("Collector current")
        ax2.legend(fontsize=7, loc="upper left"); ax2.grid(alpha=0.3)

        # panel 3: median KE
        line_ke, = ax3.plot([], [], "-s", ms=2, color="tab:orange", lw=1.2)
        ax3.set_xlim(0, d["max_time_ns"])
        ax3.set_ylim(0, all_ke_max)
        ax3.set_xlabel("time [ns]"); ax3.set_ylabel("median KE [eV]")
        ax3.set_title("Median arrival KE (collector)")
        ax3.grid(alpha=0.3)

        sup = fig.suptitle("")

        for fi in range(len(its)):
            it = its[fi]
            t_ns = it * cfg.time_step * 1e9

            # density
            rho_f, _, _ = field_rz(d["ts"], "rho", it)
            ne_f = np.abs(rho_f) / scc.e
            NE_f = np.vstack([ne_f[::-1], ne_f])
            im.set_data(NE_f)

            # current
            mask = d["scrape_steps"] <= it
            if mask.any():
                line_curr.set_data(d["scrape_times_ns"][mask],
                                   d["current_mA"][mask])
            else:
                line_curr.set_data([], [])

            # KE
            if mask.any():
                t_plot = d["scrape_times_ns"][mask]
                ke_plot = d["median_ke"][mask]
                valid = np.isfinite(ke_plot)
                line_ke.set_data(t_plot[valid], ke_plot[valid])
            else:
                line_ke.set_data([], [])

            sup.set_text(
                f"{info['title']}    step {it}    t = {t_ns:.2f} ns")
            writer.grab_frame()

        # hold final frame for 1 second
        for _ in range(int(round(fps))):
            writer.grab_frame()

    writer.finish()
    plt.close(fig)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
