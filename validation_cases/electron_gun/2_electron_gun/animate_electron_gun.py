#!/usr/bin/env python3
"""Animate the electron_gun validation case (see run_electron_gun.py).

One video per finished scenario, two panels (z axial, r vertical mirrored):
  LEFT  : electron number density n_e [m^-3]  (|rho|/e -- single species)
  RIGHT : electrons coloured by kinetic energy [eV]
The holed anode plate is drawn in grey.

Output: results/electron_gun_<scenario>.mp4 (gif fallback).

No command line arguments::

    python animate_electron_gun.py
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpmd_api as io
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from openpmd_viewer import OpenPMDTimeSeries
from scipy import constants as scc

from analyze_electron_gun import draw_plate, ke_eV, load_finished_scenarios
from run_electron_gun import SPECIES_NAME

e = scc.e


def field_rz_full(ts, field, it):
    """Field on a full mirrored (-r..+r, z) plane; returns F[r,z], z[mm], r[mm]."""
    F, info = ts.get_field(field=field, iteration=it, m="all", theta=0.0)
    r, z = np.asarray(info.r), np.asarray(info.z)
    raxis = next(k for k, v in dict(info.axes).items() if v == "r")
    if raxis == 1:
        F = F.T  # -> [r, z]
    pos = r >= 0
    F, r = F[pos], r[pos]
    rr = np.concatenate([-r[::-1], r])
    FF = np.vstack([F[::-1], F])
    return FF, z * 1e3, rr * 1e3


def ne_field(ts, it):
    F, zmm, rmm = field_rz_full(ts, "rho", it)
    return np.abs(F) / e, zmm, rmm


def read_particles(series, it):
    """Per-particle r [m], z [m], KE [eV] for one dump."""
    parts = series.iterations[it].particles
    if SPECIES_NAME not in parts:
        return np.array([]), np.array([]), np.array([])
    p = parts[SPECIES_NAME]

    def load(rec, comp):
        h = p[rec][comp]
        return h, h.load_chunk()

    xh, dx = load("position", "x")
    yh, dy = load("position", "y")
    zh, dz = load("position", "z")
    mxh, dmx = load("momentum", "x")
    myh, dmy = load("momentum", "y")
    mzh, dmz = load("momentum", "z")
    series.flush()
    if np.asarray(dz).size == 0:
        return np.array([]), np.array([]), np.array([])
    r = np.hypot(np.asarray(dx) * xh.unit_SI, np.asarray(dy) * yh.unit_SI)
    z = np.asarray(dz) * zh.unit_SI
    ke = ke_eV(np.asarray(dmx) * mxh.unit_SI, np.asarray(dmy) * myh.unit_SI,
               np.asarray(dmz) * mzh.unit_SI)
    return r, z, ke


def animate_one(cfg):
    diags, results = str(cfg.diags_dir), str(cfg.results_dir)
    os.makedirs(results, exist_ok=True)
    out = os.path.join(results, f"electron_gun_{cfg.scenario}.mp4")

    ts = OpenPMDTimeSeries(os.path.join(diags, "fields"), check_all_files=False)
    its = ts.iterations
    pseries = io.Series(os.path.join(diags, "particles", "openpmd_%T.h5"),
                        io.Access.read_only)
    print(f"[{cfg.scenario}] {len(its)} frames: {its[0]}..{its[-1]}")

    late, zmm, rmm = ne_field(ts, its[len(its) * 3 // 4])
    ne_vmax = np.percentile(late[late > 0], 99) if (late > 0).any() else 1.0
    xext = (zmm.min(), zmm.max())
    yext = (rmm.min(), rmm.max())

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.5, 5.2), sharey=True)
    ne0, _, _ = ne_field(ts, its[0])
    im = axL.imshow(ne0, origin="lower", extent=[*xext, *yext],
                    aspect="auto", cmap="inferno", vmin=0, vmax=ne_vmax)
    fig.colorbar(im, ax=axL, label="n_e [m^-3]")
    axL.set_title("electron number density")

    sc = axR.scatter([], [], c=[], s=4, cmap="turbo", vmin=0, vmax=cfg.ke_max_ev)
    fig.colorbar(sc, ax=axR, label="kinetic energy [eV]")
    axR.set_title("electrons, coloured by KE")
    axR.set_xlim(*xext)
    axR.set_ylim(*yext)

    for ax in (axL, axR):
        draw_plate(ax, cfg)
        ax.axvline(cfg.z_min * 1e3, color="red", lw=4, alpha=0.85, zorder=6)
        ax.axvline(cfg.z_max * 1e3, color="deepskyblue", lw=4, alpha=0.85,
                   zorder=6)
        ax.axvline(cfg.emit_z * 1e3, color="lime", ls=":", lw=1.4, alpha=0.9,
                   zorder=7)
        ax.set_xlabel(f"z [mm]   {cfg.v_cathode:.0f}V cathode -> holed anode "
                      f"-> {cfg.v_collector:.0f}V collector")
    axL.set_ylabel("r [mm]  (radial; mirrored)")
    sup = fig.suptitle("")

    def update(i):
        it = its[i]
        ne, _, _ = ne_field(ts, it)
        im.set_data(ne)
        r, z, ke = read_particles(pseries, it)
        if r.size:
            zz = np.concatenate([z, z]) * 1e3
            rr = np.concatenate([r, -r]) * 1e3
            kk = np.concatenate([ke, ke])
            if zz.size > 9000:
                idx = np.linspace(0, zz.size - 1, 9000).astype(int)
                zz, rr, kk = zz[idx], rr[idx], kk[idx]
            sc.set_offsets(np.column_stack([zz, rr]))
            sc.set_array(kk)
        else:
            sc.set_offsets(np.empty((0, 2)))
            sc.set_array(np.array([]))
        sup.set_text(f"electron_gun [{cfg.scenario}]: "
                     f"{cfg.beam_current*1e6:.0f} uA, hole "
                     f"r<{cfg.hole_radius*1e3:.1f} mm    "
                     f"t = {it * cfg.time_step * 1e9:.2f} ns   (step {it})")
        return im, sc

    anim = FuncAnimation(fig, update, frames=len(its), blit=False)
    try:
        anim.save(out, writer=FFMpegWriter(fps=cfg.video_fps, bitrate=2800))
        print(f"wrote {out}")
    except Exception as exc:  # noqa: BLE001
        gif = os.path.splitext(out)[0] + ".gif"
        print(f"ffmpeg failed ({exc}); writing {gif}")
        anim.save(gif, writer=PillowWriter(fps=cfg.video_fps))
        print(f"wrote {gif}")
    plt.close(fig)
    pseries.close()


def main():
    for cfg in load_finished_scenarios():
        animate_one(cfg)


if __name__ == "__main__":
    main()
