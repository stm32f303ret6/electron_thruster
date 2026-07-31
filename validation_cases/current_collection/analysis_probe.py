#!/usr/bin/env python3
"""
Post-processing for the Langmuir-probe WarpX runs (see run_probe.py).

Produces, in results_<case>/:
  - current_vs_time_<case>.png   : probe-collected current vs time (binned from
                                   the particles scraped at the embedded boundary)
  - electron_density_vs_time_<case>.png : volume-averaged ne(t)
  - sheath_profile_<case>.png    : spherically-averaged ne(s), ni(s) profiles
                                   with the sheath edge marked
  - maps_<case>.png              : final phi and ne maps (r,z)
  - summary_<case>.txt           : plateau current, sheath radius/area, checks

Usage:
  python analysis_probe.py --case min --diags diags_min
  python analysis_probe.py --case max --diags diags_max
"""

import argparse
import glob
import json
import math
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpmd_api as io
from openpmd_viewer import OpenPMDTimeSeries
from scipy import constants as scc

PROBE_RADIUS = 0.005  # m
PROBE_POTENTIAL = 10.0  # V
DT = 1.0e-10  # s (must match run_probe.py)

CASE_PARAMS = {
    "min": dict(bin_dt=0.1e-6, transient=2.0e-6, rmax=0.16, zmax=0.16),
    "max": dict(bin_dt=0.02e-6, transient=0.5e-6, rmax=0.10, zmax=0.10),
}


def find_openpmd_series(base_dir):
    """Return an openPMD series pattern ('.../prefix_%T.h5') found under base_dir."""
    files = sorted(glob.glob(os.path.join(base_dir, "**", "*.h5"), recursive=True))
    if not files:
        raise FileNotFoundError(f"no .h5 files under {base_dir}")
    sample = os.path.basename(files[0])
    pattern = re.sub(r"\d+(?=\.h5$)", "%T", sample)
    return os.path.join(os.path.dirname(files[0]), pattern)


def load_scraped(diags, species_hint):
    """Concatenate (timeScraped, weighting) of all scraped particles of a species."""
    pattern = find_openpmd_series(os.path.join(diags, "scrape"))
    series = io.Series(pattern, io.Access.read_only)
    times, weights = [], []
    for idx in series.iterations:
        it = series.iterations[idx]
        sp_names = [s for s in it.particles if species_hint in s]
        if not sp_names:
            continue
        p = it.particles[sp_names[0]]
        records = list(p)
        if "weighting" not in records:
            raise KeyError(f"'weighting' not in scraped records: {records}")
        w = p["weighting"][io.Record_Component.SCALAR].load_chunk()
        if "timeScraped" in records:
            t = p["timeScraped"][io.Record_Component.SCALAR].load_chunk()
            series.flush()
            t = np.asarray(t, dtype=np.float64)
        elif "stepScraped" in records:
            s = p["stepScraped"][io.Record_Component.SCALAR].load_chunk()
            series.flush()
            t = np.asarray(s, dtype=np.float64) * DT
        else:
            raise KeyError(f"no time record in scraped records: {records}")
        times.append(t)
        weights.append(np.asarray(w, dtype=np.float64))
    series.close()
    if not times:
        return np.array([]), np.array([])
    return np.concatenate(times), np.concatenate(weights)


def binned_current(times, weights, t_end, bin_dt):
    """Current I(t) = e * (collected physical particles per bin) / bin_dt."""
    nbins = max(1, int(round(t_end / bin_dt)))
    edges = np.linspace(0.0, nbins * bin_dt, nbins + 1)
    qsum, _ = np.histogram(times, bins=edges, weights=weights)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return centers, scc.e * qsum / bin_dt


def stabilization_check(t, current, transient):
    """Compare mean current over [0.6T,0.8T] vs [0.8T,T] (excluding transient)."""
    T = t[-1]
    m1_mask = (t >= 0.6 * T) & (t < 0.8 * T) & (t > transient)
    m2_mask = (t >= 0.8 * T) & (t > transient)
    m1, m2 = current[m1_mask].mean(), current[m2_mask].mean()
    rel = abs(m2 - m1) / abs(m2) if m2 != 0 else np.inf
    return m1, m2, rel, rel < 0.05


def read_particle_number(diags):
    """Parse the ParticleNumber reduced diagnostic text file."""
    path = os.path.join(diags, "reducedfiles", "particle_number.txt")
    with open(path) as f:
        header = f.readline()
    cols = {}
    for tok in header.lstrip("#").split():
        m = re.match(r"\[(\d+)\](.*)", tok)
        if m:
            cols[m.group(2)] = int(m.group(1))  # header indices are 0-based
    data = np.loadtxt(path, skiprows=1)
    time_col = next(c for name, c in cols.items() if name.startswith("time"))
    we_col = next(c for name, c in cols.items() if "electrons" in name and "weight" in name)
    return data[:, time_col], data[:, we_col]


def field_rz(ts, field, iteration):
    """Load a field as (r, z)-ordered array with positive-r rows only."""
    F, info = ts.get_field(field=field, iteration=iteration, m="all", theta=0.0)
    r, z = np.asarray(info.r), np.asarray(info.z)
    raxis = next(k for k, v in dict(info.axes).items() if v == "r")
    if raxis == 1:
        F = F.T  # (z, r) -> (r, z)
    pos = r > 0
    return F[pos], r[pos], z


def spherical_profiles(ts, iterations, fields, rmax, zmax, dr):
    """Spherically-binned, volume-weighted radial profiles around the probe.

    Averages over the given iterations. Returns (s_centers, {field: profile}).
    """
    smax = 0.95 * min(rmax, zmax)
    edges = np.arange(PROBE_RADIUS, smax, 1.0e-3)
    centers = 0.5 * (edges[:-1] + edges[1:])
    sums = {f: np.zeros(len(centers)) for f in fields}
    wsum = np.zeros(len(centers))
    for it in iterations:
        first = True
        for f in fields:
            Fp, rp, z = field_rz(ts, f, it)
            R, Z = np.meshgrid(rp, z, indexing="ij")
            if first:
                S = np.sqrt(R**2 + Z**2)
                mask = S > (PROBE_RADIUS + 2 * dr)
                idx = np.digitize(S[mask], edges) - 1
                valid = (idx >= 0) & (idx < len(centers))
                vol_w = R[mask][valid]  # 2*pi*dr*dz factors cancel
                ib = idx[valid]
                first = False
            sums[f] += np.bincount(ib, weights=Fp[mask][valid] * vol_w,
                                   minlength=len(centers))
        wsum += np.bincount(ib, weights=vol_w, minlength=len(centers))
    wsum[wsum == 0] = np.nan
    return centers, {f: sums[f] / (wsum / len(iterations)) / len(iterations)
                     for f in fields}


def smooth(y, n=3):
    if len(y) < n:
        return y
    return np.convolve(y, np.ones(n) / n, mode="same")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=["min", "max"])
    parser.add_argument("--diags", default=None)
    parser.add_argument("--tag", default="",
                        help="suffix matching run_probe.py --tag; selects "
                             "diags_<case><tag>/ and writes results_<case><tag>/")
    args = parser.parse_args()
    case = args.case
    diags = args.diags or f"diags_{case}{args.tag}"
    params = dict(CASE_PARAMS[case])
    outdir = f"results_{case}{args.tag}"
    os.makedirs(outdir, exist_ok=True)
    report = []

    def log(msg):
        print(msg)
        report.append(msg)

    # Prefer run metadata (actual domain/dt/ramp) over the hardcoded defaults.
    meta = {}
    meta_path = os.path.join(diags, "run_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        params["rmax"] = meta["rmax"]
        params["zmax"] = meta["zmax"]
        dt = meta["dt"]
        # keep ~same number of current bins regardless of run length
        params["bin_dt"] = max(meta["dt"] * 200, (meta["max_steps"] * dt) / 200)
        log(f"loaded run_meta.json: V={meta['V_probe']} V"
            + (f" ramped over {meta['ramp_us']} us" if meta.get("ramp_us") else "")
            + f", domain r<{meta['rmax']} z<±{meta['zmax']} m, dt={dt:.1e} s"
            + (f", ion={meta['ion_mass_me']} me" if meta.get("ion_mass_me") else "")
            + (f", Bz={meta['bz']:.2e} T" if meta.get("bz") else ""))
    V_probe = meta.get("V_probe", PROBE_POTENTIAL)
    ramp_us = meta.get("ramp_us")

    # ------------------------------------------------------------------
    # 1. Collected current vs time (from particles scraped at the probe)
    # ------------------------------------------------------------------
    te, we = load_scraped(diags, "electron")
    ti_, wi = load_scraped(diags, "ion")
    t_end = max(te.max() if te.size else 0.0, ti_.max() if ti_.size else 0.0)
    tb, Ie = binned_current(te, we, t_end, params["bin_dt"])
    _, Ii = binned_current(ti_, wi, t_end, params["bin_dt"])

    m1, m2, rel, ok = stabilization_check(tb, Ie, params["transient"])
    plateau_mask = (tb > params["transient"]) & (tb >= 0.6 * tb[-1])
    I_plateau = Ie[plateau_mask].mean()
    I_plateau_std = Ie[plateau_mask].std()

    log(f"=== case {case}: collected current ===")
    log(f"scraped electron macros: {len(te):,}  (physical: {we.sum():.4e})")
    log(f"scraped ion macros:      {len(ti_):,}  (physical: {wi.sum():.4e})")
    log(f"electron current plateau (t > {0.6 * tb[-1] * 1e6:.2f} us): "
        f"{I_plateau * 1e6:.4f} +- {I_plateau_std * 1e6:.4f} uA")
    log(f"ion current mean (same window): {Ii[plateau_mask].mean() * 1e6:.5f} uA")
    log(f"stabilization: mean[0.6-0.8T] = {m1 * 1e6:.4f} uA, "
        f"mean[0.8-1.0T] = {m2 * 1e6:.4f} uA, rel diff = {rel * 100:.2f}% "
        f"-> {'STABILIZED' if ok else 'NOT stabilized (rerun longer)'}")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(tb * 1e6, Ie * 1e6, label="electron current", lw=1.2)
    ax.plot(tb * 1e6, Ii * 1e6, label="ion current", lw=1.2)
    ax.axhline(I_plateau * 1e6, color="gray", ls="--",
               label=f"plateau = {I_plateau * 1e6:.2f} uA")
    ax.axvspan(0, params["transient"] * 1e6, color="orange", alpha=0.15,
               label="initial transient (excluded)")
    ax.set_xlabel("time [us]")
    ax.set_ylabel("collected current [uA]")
    bias_txt = (f"ramp 0->{V_probe:.0f} V over {ramp_us} us" if ramp_us
                else f"+{V_probe:.0f} V fixed")
    ax.set_title(f"Langmuir probe current, case '{case}' (a = 5 mm, {bias_txt})")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{outdir}/current_vs_time_{case}.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 1b. I-V characteristic (only for a ramped-potential run)
    # ------------------------------------------------------------------
    if ramp_us:
        # probe potential is V(t) = V_probe * min(t / t_ramp, 1)
        t_ramp = ramp_us * 1e-6
        V_of_t = V_probe * np.minimum(tb / t_ramp, 1.0)
        rising = tb <= t_ramp  # the part of the curve that sweeps voltage
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(V_of_t[rising], Ie[rising] * 1e6, lw=1.4)
        ax.set_xlabel("probe potential [V]")
        ax.set_ylabel("collected electron current [uA]")
        ax.set_title(f"I-V characteristic (swept), case '{case}'")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(f"{outdir}/iv_curve_{case}.png", dpi=150)
        plt.close(fig)
        log(f"I-V curve written (swept 0 -> {V_probe:.0f} V over {ramp_us} us); "
            "note: a ramp is only quasi-steady if slow vs ion relaxation.")

    # ------------------------------------------------------------------
    # 2. Electron density vs time (ParticleNumber reduced diagnostic)
    # ------------------------------------------------------------------
    rmax, zmax = params["rmax"], params["zmax"]
    t_pn, w_e = read_particle_number(diags)
    V_plasma = math.pi * rmax**2 * (2 * zmax) - (4 / 3) * math.pi * PROBE_RADIUS**3
    ne_t = w_e / V_plasma

    log(f"\n=== case {case}: electron density ===")
    log(f"ne(t=0)   = {ne_t[0]:.4e} m^-3")
    log(f"ne(t_end) = {ne_t[-1]:.4e} m^-3 "
        f"({100 * ne_t[-1] / ne_t[0]:.1f}% of initial)")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(t_pn * 1e6, ne_t, lw=1.2)
    ax.axhline(ne_t[0], color="gray", ls="--", label="initial (ambient)")
    ax.set_xlabel("time [us]")
    ax.set_ylabel(r"volume-averaged $n_e$ [m$^{-3}$]")
    ax.set_title(f"Electron density vs time, case '{case}'")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{outdir}/electron_density_vs_time_{case}.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 3. Sheath profile and sheath area (from the last field snapshots)
    # ------------------------------------------------------------------
    ts = OpenPMDTimeSeries(os.path.join(diags, "fields"))
    iters = ts.iterations[-3:] if len(ts.iterations) >= 3 else ts.iterations[-1:]
    dr = rmax / (len(ts.get_field("phi", iteration=ts.iterations[-1],
                                  m="all", theta=0.0)[1].r) // 2)
    s, prof = spherical_profiles(ts, iters, ["rho_electrons", "rho_ions"],
                                 rmax, zmax, dr)
    ne_s = -prof["rho_electrons"] / scc.e
    ni_s = prof["rho_ions"] / scc.e
    ne_sm, ni_sm = smooth(ne_s), smooth(ni_s)

    outer = s > s[0] + 0.8 * (s[-1] - s[0])
    n_inf = np.nanmean(ne_sm[outer])

    # criterion 1: ne recovers to 95% of ambient. Only meaningful if ne is
    # depleted near the probe; at a strongly electron-attracting probe ne is
    # *enhanced* everywhere (accelerated/orbiting electrons), so flag it n/a.
    above = np.where(ne_sm >= 0.95 * n_inf)[0]
    finite = np.where(np.isfinite(ne_sm))[0]
    if above.size and finite.size and above[0] <= finite[0]:
        rs_95 = np.nan  # ne never below ambient -> criterion not applicable
    else:
        rs_95 = s[above[0]] if above.size else np.nan
    # criterion 2: charge imbalance < 5% of ambient
    imbal = np.abs(ni_sm - ne_sm) / n_inf
    bad = np.where(imbal > 0.05)[0]
    rs_qn = s[bad[-1] + 1] if bad.size and bad[-1] + 1 < len(s) else (
        s[0] if not bad.size else np.nan)

    A_95 = 4 * math.pi * rs_95**2
    A_qn = 4 * math.pi * rs_qn**2

    log(f"\n=== case {case}: sheath (averaged over field iterations {list(iters)}) ===")
    log(f"ambient density n_inf (outer 20% of profile): {n_inf:.4e} m^-3")
    if np.isfinite(rs_95):
        log(f"criterion ne >= 0.95*n_inf : r_s = {rs_95 * 1e3:.2f} mm "
            f"({rs_95 / PROBE_RADIUS:.2f} a)  ->  A_sheath = {A_95 * 1e4:.3f} cm^2")
    else:
        log("criterion ne >= 0.95*n_inf : n/a (ne enhanced above ambient "
            "everywhere - electron-attracting sheath)")
    log(f"criterion |ni-ne| <= 5%    : r_s = {rs_qn * 1e3:.2f} mm "
        f"({rs_qn / PROBE_RADIUS:.2f} a)  ->  A_sheath = {A_qn * 1e4:.3f} cm^2"
        "   <- sheath edge")
    log(f"(probe area 4*pi*a^2 = {4 * math.pi * PROBE_RADIUS**2 * 1e4:.3f} cm^2)")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(s * 1e3, ne_sm, label=r"$n_e(s)$", lw=1.5)
    ax.plot(s * 1e3, ni_sm, label=r"$n_i(s)$ (O$^+$)", lw=1.5)
    ax.axhline(n_inf, color="gray", ls=":", label=r"$n_\infty$")
    if np.isfinite(rs_95):
        ax.axvline(rs_95 * 1e3, color="C2", ls="--",
                   label=f"sheath edge (95% $n_e$): {rs_95 * 1e3:.1f} mm")
    if np.isfinite(rs_qn):
        ax.axvline(rs_qn * 1e3, color="C3", ls="-.",
                   label=f"sheath edge (quasineutral): {rs_qn * 1e3:.1f} mm")
    ax.axvspan(0, PROBE_RADIUS * 1e3, color="k", alpha=0.15, label="probe")
    ax.set_xlabel("spherical radius s [mm]")
    ax.set_ylabel(r"density [m$^{-3}$]")
    ax.set_title(f"Sheath profile around the probe, case '{case}'")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{outdir}/sheath_profile_{case}.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 4. Bonus: final 2D maps of phi and ne
    # ------------------------------------------------------------------
    last = ts.iterations[-1]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for axi, (fname, label, scale) in zip(axes, [
            ("phi", r"$\phi$ [V]", 1.0),
            ("rho_electrons", r"$n_e$ [m$^{-3}$]", -1.0 / scc.e)]):
        Fp, rp, z = field_rz(ts, fname, last)
        pm = axi.pcolormesh(z * 1e3, rp * 1e3, Fp * scale, shading="auto",
                            cmap="viridis")
        axi.set_xlabel("z [mm]")
        axi.set_ylabel("r [mm]")
        axi.set_title(label)
        fig.colorbar(pm, ax=axi)
    fig.suptitle(f"Final snapshot (iteration {last}), case '{case}'")
    fig.tight_layout()
    fig.savefig(f"{outdir}/maps_{case}.png", dpi=150)
    plt.close(fig)

    with open(f"{outdir}/summary_{case}.txt", "w") as f:
        f.write("\n".join(report) + "\n")
    log(f"\nplots and summary written to {outdir}/")


if __name__ == "__main__":
    main()
