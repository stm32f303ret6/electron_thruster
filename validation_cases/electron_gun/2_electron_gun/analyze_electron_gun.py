#!/usr/bin/env python3
"""Analysis for the electron_gun validation case (see run_electron_gun.py).

Per scenario (config snapshot read from outputs/diags_<name>/config_used.yaml):

  current_<name>.png / .csv   -- collected current vs time per boundary
  energy_<name>.png           -- arrival-energy spectra per boundary
  fields_<name>.png           -- potential phi + electron density (mirrored +-r)
  phi_axis_<name>.png         -- on-axis phi(z), t=0 vs t_end
  + a fate ledger with a particle-budget closure check on stdout.

Then the cross-scenario demonstration table and validation gates:

  A  low current, small hole  -> ~all current passes (matches case 1)
  B  20x current, small hole  -> radial space-charge blowup; the hole clips it
  C  20x current, big hole    -> transmission restored

  transmission_electron_gun.png / summary_electron_gun.json

No command line arguments::

    python analyze_electron_gun.py
"""

import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpmd_api as io
from matplotlib.patches import Rectangle
from openpmd_viewer import OpenPMDTimeSeries
from scipy import constants as scc

from run_electron_gun import SPECIES_NAME, Config

m_e, e, c = scc.m_e, scc.e, scc.c

KE_BIN_EV = 0.5  # arrival-energy histogram bin width [eV]


def load_finished_scenarios():
    """One Config per scenario whose finished-run snapshot exists."""
    base = Config()
    cfgs = []
    for name in base.scenarios:
        snap = base.diags_base / f"diags_{name}" / "config_used.yaml"
        if not snap.exists():
            raise SystemExit(
                f"{snap} not found -- run run_electron_gun.py to completion first"
            )
        cfgs.append(Config(snap, scenario=name))
    return cfgs


def targets(cfg):
    """The four absorbing surfaces, main collector first."""
    return [
        dict(key="collector", bnd="zhi",
             label=f"collector ({cfg.v_collector:.0f} V)", color="tab:green"),
        dict(key="anode", bnd="eb",
             label=f"anode plate ({cfg.v_anode:.0f} V, hole "
                   f"r<{cfg.hole_radius * 1e3:.1f}mm)", color="tab:orange"),
        dict(key="cathode", bnd="zlo",
             label=f"cathode ({cfg.v_cathode:.0f} V)", color="tab:red"),
        dict(key="radial", bnd="xhi",
             label=f"radial wall (r={cfg.r_max * 1e3:.0f}mm)", color="tab:blue"),
    ]


def ke_eV(px, py, pz):
    """Relativistic kinetic energy [eV] from momentum [kg m/s]."""
    p2 = px * px + py * py + pz * pz
    gamma = np.sqrt(1.0 + p2 / (m_e * c) ** 2)
    return (gamma - 1.0) * m_e * c * c / e


def field_rz(ts, field, iteration):
    """Reconstruct the (r>=0, z) half-plane, robust to axis order."""
    F, info = ts.get_field(field=field, iteration=iteration, m="all", theta=0.0)
    r, z = np.asarray(info.r), np.asarray(info.z)
    raxis = next(k for k, v in dict(info.axes).items() if v == "r")
    if raxis == 1:
        F = F.T  # -> [r, z]
    pos = r >= 0
    return F[pos], r[pos], z


def read_scraped(diags):
    """Per-particle arrays concatenated over all boundary subdirs."""
    cols = {k: [] for k in ("r", "z", "px", "py", "pz", "w", "bnd", "it")}
    for sub in sorted(glob.glob(os.path.join(diags, "scrape", "particles_at_*"))):
        if not glob.glob(os.path.join(sub, "*.h5")):
            continue
        bnd = os.path.basename(sub).replace("particles_at_", "")
        series = io.Series(os.path.join(sub, "openpmd_%T.h5"), io.Access.read_only)
        for it in series.iterations:
            parts = series.iterations[it].particles
            if SPECIES_NAME not in parts:
                continue
            p = parts[SPECIES_NAME]

            def load(rec, comp):
                h = p[rec][comp]
                return h, h.load_chunk()

            (xh, dx) = load("position", "x")
            (yh, dy) = load("position", "y")
            (zh, dz) = load("position", "z")
            (mxh, dmx) = load("momentum", "x")
            (myh, dmy) = load("momentum", "y")
            (mzh, dmz) = load("momentum", "z")
            wh = p["weighting"][io.Mesh_Record_Component.SCALAR]
            dw = wh.load_chunk()
            series.flush()
            n = np.asarray(dw).size
            if n == 0:
                continue
            xx = np.asarray(dx) * xh.unit_SI
            yy = np.asarray(dy) * yh.unit_SI
            cols["r"].append(np.hypot(xx, yy))
            cols["z"].append(np.asarray(dz) * zh.unit_SI)
            cols["px"].append(np.asarray(dmx) * mxh.unit_SI)
            cols["py"].append(np.asarray(dmy) * myh.unit_SI)
            cols["pz"].append(np.asarray(dmz) * mzh.unit_SI)
            cols["w"].append(np.asarray(dw) * wh.unit_SI)
            cols["bnd"].append(np.array([bnd] * n))
            cols["it"].append(np.full(n, it))
        series.close()
    return {k: (np.concatenate(v) if v else np.array([])) for k, v in cols.items()}


def draw_plate(ax, cfg, mirrored=True):
    """Anode plate cross-section (grey) on a (z [mm], r [mm]) plot."""
    z0 = cfg.anode_z_front * 1e3
    tw = cfg.anode_thickness * 1e3
    rh, rm = cfg.hole_radius * 1e3, cfg.r_max * 1e3
    ax.add_patch(Rectangle((z0, rh), tw, rm - rh, color="0.45", zorder=5))
    if mirrored:
        ax.add_patch(Rectangle((z0, -rm), tw, rm - rh, color="0.45", zorder=5))


def current_plot(s, cfg, tgts, outdir):
    """Collected current [uA] vs time at each boundary; returns steady means."""
    I_emit, dt, sp = cfg.beam_current, cfg.time_step, cfg.scrape_period
    name = cfg.scenario
    if s["w"].size == 0:
        print("  (no scraped electrons for current plot)")
        return {}
    steps = np.unique(s["it"])
    steps = steps[steps > 0]
    t_ns = steps * dt * 1e9

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.axhline(I_emit * 1e6, color="gray", ls="--",
               label=f"emitted = {I_emit*1e6:.1f} uA")
    steady, curves = {}, {}
    for tgt in tgts:
        m = s["bnd"] == tgt["bnd"]
        # current in a dump = weight collected since the previous dump (the
        # scrape buffer is cleared every dump) * e / (scrape_period * dt)
        I = np.array([s["w"][m & (s["it"] == k)].sum() * e / (sp * dt) for k in steps])
        ax.plot(t_ns, I * 1e6, "-o", ms=3, color=tgt["color"], label=tgt["label"])
        steady[tgt["key"]] = float(np.mean(I[int(0.6 * len(I)):])) if len(I) else 0.0
        curves[tgt["key"]] = I * 1e6
    ax.set_xlabel("time [ns]")
    ax.set_ylabel("collected current [uA]")
    ax.set_title(f"collected current vs time  [{name}]")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = os.path.join(outdir, f"current_{name}.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")

    csv = os.path.join(outdir, f"current_{name}.csv")
    keys = [t["key"] for t in tgts]
    with open(csv, "w") as fh:
        fh.write("t_ns," + ",".join(f"{k}_uA" for k in keys) + "\n")
        for i in range(len(t_ns)):
            fh.write(f"{t_ns[i]:.4f}," +
                     ",".join(f"{curves[k][i]:.6e}" for k in keys) + "\n")

    for tgt in tgts:
        v = steady[tgt["key"]]
        print(f"  {tgt['label']:38s} steady ~ {v*1e6:9.4f} uA "
              f"({100*v/I_emit:5.1f}% of emitted)")
    return steady


def energy_plot(s, cfg, tgts, outdir):
    """Arrival-energy spectra per boundary; returns per-boundary mean KE."""
    name = cfg.scenario
    if s["w"].size == 0:
        print("  (no scraped electrons for energy plot)")
        return {}
    ke_edges = np.arange(0.0, cfg.ke_max_ev + KE_BIN_EV, KE_BIN_EV)
    ke_centers = 0.5 * (ke_edges[:-1] + ke_edges[1:])
    fig, axs = plt.subplots(1, len(tgts), figsize=(4.4 * len(tgts), 4.4),
                            squeeze=False)
    axs = axs[0]
    means = {}
    for ax, tgt in zip(axs, tgts):
        m = s["bnd"] == tgt["bnd"]
        ax.set_xlabel("KE at impact [eV]")
        if not m.any():
            ax.set_title(f"{tgt['label']}: no hits", fontsize=9)
            means[tgt["key"]] = float("nan")
            continue
        ke, w = ke_eV(s["px"][m], s["py"][m], s["pz"][m]), s["w"][m]
        mean = float(np.average(ke, weights=w))
        h, _ = np.histogram(ke, bins=ke_edges, weights=w)
        means[tgt["key"]] = mean
        ax.bar(ke_centers, h, width=KE_BIN_EV, color=tgt["color"], alpha=0.85,
               align="center")
        ax.axvline(mean, color="k", ls=":", label=f"mean = {mean:.2f} eV")
        ax.set_xlim(0, cfg.ke_max_ev)
        ax.set_title(tgt["label"], fontsize=9)
        ax.legend(fontsize=8)
        print(f"  {tgt['label']:38s} KE mean {mean:8.2f} eV  N = {w.sum():.3e}")
    axs[0].set_ylabel("electrons (weighted)")
    fig.suptitle(f"electron arrival energy  [{name}]")
    fig.tight_layout()
    out = os.path.join(outdir, f"energy_{name}.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")
    return means


def field_plot(ts, cfg, outdir):
    name = cfg.scenario
    last = ts.iterations[-1]
    phi, r, z = field_rz(ts, "phi", last)
    rho, _, _ = field_rz(ts, "rho", last)  # single species: rho is electrons-only
    ne = np.abs(rho) / e

    rr = np.concatenate([-r[::-1], r])
    PHI = np.vstack([phi[::-1], phi])
    NE = np.vstack([ne[::-1], ne])
    zmm, rmm = z * 1e3, rr * 1e3

    fig, axs = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    vlim = max(abs(PHI.min()), abs(PHI.max()), 1.0)
    pcm0 = axs[0].pcolormesh(zmm, rmm, PHI, cmap="RdBu_r", shading="auto",
                             vmin=-vlim, vmax=vlim)
    axs[0].contour(zmm, rmm, PHI, levels=np.linspace(PHI.min(), PHI.max(), 11),
                   colors="k", linewidths=0.4, alpha=0.5)
    axs[0].set_title(f"potential phi [V]  (step {last})")
    fig.colorbar(pcm0, ax=axs[0], label="phi [V]")

    vmax = NE.max() if NE.max() > 0 else 1.0
    pcm1 = axs[1].pcolormesh(zmm, rmm, NE, cmap="inferno", vmin=0, vmax=vmax,
                             shading="auto")
    axs[1].set_title("electron number density n_e [m^-3]")
    fig.colorbar(pcm1, ax=axs[1], label="n_e [m^-3]")

    for ax in axs:
        draw_plate(ax, cfg)
        ax.axvline(cfg.z_min * 1e3, color="red", lw=4, alpha=0.85, zorder=5)
        ax.axvline(cfg.z_max * 1e3, color="deepskyblue", lw=4, alpha=0.85,
                   zorder=5)
        ax.axvline(cfg.emit_z * 1e3, color="lime", ls=":", lw=1.5, alpha=0.9,
                   zorder=6)
        ax.set_xlabel(f"z [mm]  ({cfg.v_cathode:.0f} V cathode -> holed anode "
                      f"{cfg.v_anode:.0f} V -> {cfg.v_collector:.0f} V collector)")
    axs[0].set_ylabel("r [mm]  (radial; mirrored)")
    fig.suptitle(f"electron_gun [{name}]: {cfg.beam_current*1e6:.0f} uA, "
                 f"hole r<{cfg.hole_radius*1e3:.1f} mm")
    fig.tight_layout()
    out = os.path.join(outdir, f"fields_{name}.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")


def phi_axis_plot(ts, cfg, outdir):
    """On-axis phi(z) at t=0 (geometry only) and t_end (with beam).  Returns
    (z, phi_vacuum, phi_end) for the energy-conservation gate."""
    name = cfg.scenario
    first, last = ts.iterations[0], ts.iterations[-1]
    phi_f, r, z = field_rz(ts, "phi", first)
    phi_l, _, _ = field_rz(ts, "phi", last)
    p0f, p0l = phi_f[0], phi_l[0]  # r ~ 0 column
    zmm = z * 1e3

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.plot(zmm, p0f, "--", color="gray", lw=1.6,
            label=f"t = 0, geometry only (step {first})")
    ax.plot(zmm, p0l, "-o", ms=3, color="tab:purple",
            label=f"t_end, with beam (step {last})")
    ax.axhline(0.0, color="gray", lw=0.8)
    ax.axvspan(cfg.anode_z_front * 1e3,
               (cfg.anode_z_front + cfg.anode_thickness) * 1e3,
               color="0.75", alpha=0.6,
               label=f"anode plane (hole r<{cfg.hole_radius*1e3:.1f} mm)")
    ax.axvline(cfg.z_min * 1e3, color="red", lw=2, alpha=0.6,
               label=f"cathode {cfg.v_cathode:.0f} V")
    ax.axvline(cfg.z_max * 1e3, color="deepskyblue", lw=2, alpha=0.6,
               label=f"collector {cfg.v_collector:.0f} V")
    ax.grid(alpha=0.3)
    ax.set_xlabel("z [mm]")
    ax.set_ylabel("on-axis potential phi [V]")
    ax.set_title(f"On-axis phi(z)  [{name}]")
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    out = os.path.join(outdir, f"phi_axis_{name}.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")
    return z, p0f, p0l


def in_domain_weight(diags):
    """Beam weight still inside the domain, from the last ParticleNumber row.
    Columns for a single species: [0]step [1]time [2]total_macroparticles
    [3]electrons_macroparticles [4]total_weight [5]electrons_weight."""
    f = os.path.join(diags, "reducedfiles", "beam_n.txt")
    if not os.path.exists(f):
        return None
    row = np.atleast_2d(np.loadtxt(f))[-1]
    return float(row[5])


def ledger(s, cfg, tgts, steady):
    """Fate ledger + particle-budget closure; returns the scenario summary."""
    I_emit = cfg.beam_current
    total = float(s["w"].sum()) if s["w"].size else 0.0
    print(f"  --- fate ledger [{cfg.scenario}] (weighted) ---")
    weights = {}
    for tgt in tgts:
        m = s["bnd"] == tgt["bnd"] if s["w"].size else np.array([], dtype=bool)
        N = float(s["w"][m].sum()) if m.any() else 0.0
        weights[tgt["key"]] = N
        pct = 100 * N / total if total else 0.0
        print(f"  {tgt['label']:38s}  N = {N:.4e}  ({pct:5.1f}% of absorbed)")

    t_end = cfg.max_steps * cfg.time_step
    n_emit = (I_emit / e) * t_end
    n_dom = in_domain_weight(str(cfg.diags_dir))
    closure = None
    if n_dom is not None:
        closure = 100 * ((total + n_dom) - n_emit) / n_emit
        print(f"  BUDGET: emitted={n_emit:.4e} absorbed={total:.4e} "
              f"in-domain={n_dom:.4e} -> closes {closure:+.3f}%")

    return {
        "scenario": cfg.scenario,
        "I_emit_uA": I_emit * 1e6,
        "hole_radius_mm": cfg.hole_radius * 1e3,
        "pct_of_child_langmuir": 100 * I_emit * 1e6 / cfg.child_langmuir_uA(),
        "weights": weights,
        "emitted_weight": n_emit,
        "closure_pct": closure,
    }


def transmission_plot(rows, outdir):
    """Grouped-bar summary of the demonstration: fraction of emitted current
    reaching each surface, per scenario."""
    keys = ["collector", "anode", "cathode", "radial"]
    colors = ["tab:green", "tab:orange", "tab:red", "tab:blue"]
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    x = np.arange(len(rows))
    wbar = 0.2
    for j, (k, col) in enumerate(zip(keys, colors)):
        vals = [100 * r["frac"][k] for r in rows]
        bars = ax.bar(x + (j - 1.5) * wbar, vals, wbar, color=col, label=k)
        ax.bar_label(bars, fmt="%.1f%%", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['scenario']}\n{r['I_emit_uA']:.0f} uA, "
                        f"hole {r['hole_radius_mm']:.1f} mm" for r in rows],
                       fontsize=9)
    ax.set_ylabel("% of emitted current (steady state)")
    ax.set_title("electron_gun: aperture transmission vs space charge")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    out = os.path.join(outdir, "transmission_electron_gun.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"\n  wrote {out}")


def evaluate_gates(val, rows):
    """The demonstration narrative as executable gates; True if all pass.

    `val` comes from the CURRENT inputs/ YAML, not the per-run snapshot: the
    snapshot freezes the physics the run used, but gate tolerances are an
    analysis-time policy and must be re-tunable without rerunning.
    """
    if not val:
        print("(no validation block in the YAML -- gates skipped)")
        return True
    A, B, C = rows  # ordered as in the YAML scenarios list

    gates = [
        ("A: collector fraction >= min",
         A["frac"]["collector"] >= val["a_collector_min_frac"],
         f"{100*A['frac']['collector']:.2f}% >= {100*val['a_collector_min_frac']:.0f}%"),
        ("A: anode interception <= max",
         A["frac"]["anode"] <= val["a_anode_max_frac"],
         f"{100*A['frac']['anode']:.2f}% <= {100*val['a_anode_max_frac']:.0f}%"),
        ("B: collector drops by >= 5 pp vs A",
         A["frac"]["collector"] - B["frac"]["collector"] >= val["b_drop_min_frac"],
         f"{100*A['frac']['collector']:.2f}% -> {100*B['frac']['collector']:.2f}%"),
        ("B: loss lands ON the anode plate",
         B["frac"]["anode"] >= val["b_anode_min_frac"],
         f"anode {100*B['frac']['anode']:.2f}% >= {100*val['b_anode_min_frac']:.0f}%"),
        ("C: big hole restores transmission",
         C["frac"]["collector"] >= val["c_collector_min_frac"],
         f"{100*C['frac']['collector']:.2f}% >= {100*val['c_collector_min_frac']:.0f}%"),
        ("C: anode interception below B's",
         C["frac"]["anode"] < B["frac"]["anode"],
         f"{100*C['frac']['anode']:.2f}% < {100*B['frac']['anode']:.2f}%"),
    ]
    for r in rows:
        gates.append((f"{r['scenario'][:1]}: KE == energy conservation "
                      f"from emit plane",
                      abs(r["ke_err_eV"]) <= val["ke_tol_ev"],
                      f"{r['ke_coll_eV']:.2f} eV vs analytic "
                      f"{r['ke_expect_eV']:.2f} eV (|err| "
                      f"{abs(r['ke_err_eV']):.2f} <= {val['ke_tol_ev']:.1f})"))
        gates.append((f"{r['scenario'][:1]}: particle-budget closure",
                      abs(r["closure_pct"] or 0.0) <= val["closure_pct_max"],
                      f"{r['closure_pct']:+.3f}% (tol "
                      f"{val['closure_pct_max']:.1f}%)"))

    print("\n" + "=" * 72)
    print("VALIDATION GATES  [electron_gun]")
    print("=" * 72)
    ok = True
    for name, passed, detail in gates:
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name}\n       {detail}")
    print("=" * 72)
    print(f"VERDICT: {'PASS' if ok else 'FAIL'} ({len(gates)} gates evaluated)")
    print("=" * 72)
    return ok


def main():
    cfgs = load_finished_scenarios()
    results = str(cfgs[0].results_dir)
    os.makedirs(results, exist_ok=True)

    kT_launch_eV = m_e * cfgs[0].rms_velocity**2 / e  # per-axis launch temp

    # Cold-space-charge estimate of thermal-tail aperture clipping: over the
    # accelerated transit t = d*sqrt(2m/(eV)) an electron drifts sideways by
    # sigma = v_rms*t; clip fraction = area-weighted Gaussian tail beyond the
    # (hole - birth radius) margin.  Valid for the LOW-current scenario only.
    from math import erfc, sqrt
    c0 = cfgs[0]
    d_gap = c0.anode_z_front - c0.z_min
    t_transit = d_gap * np.sqrt(2 * m_e / (e * abs(c0.v_cathode)))
    sigma_r = c0.rms_velocity * t_transit
    rbirth = np.linspace(0, c0.emit_radius, 400)
    for cfg_ in cfgs:
        q = np.array([0.5 * erfc((cfg_.hole_radius - rb) / (sqrt(2) * sigma_r))
                      for rb in rbirth])
        clip = float(np.trapezoid(2 * rbirth * q, rbirth) / c0.emit_radius**2)
        print(f"thermal-tail clip estimate [{cfg_.scenario}]: sigma_r = "
              f"{sigma_r * 1e3:.3f} mm at the anode -> {100 * clip:.2f}% "
              f"intercepted (cold space charge)")

    rows = []
    for cfg in cfgs:
        diags = str(cfg.diags_dir)
        tgts = targets(cfg)
        print(f"\nAnalyzing scenario {cfg.scenario} "
              f"({cfg.beam_current*1e6:.0f} uA = "
              f"{100*cfg.beam_current*1e6/cfg.child_langmuir_uA():.1f}% of "
              f"I_CL, hole r<{cfg.hole_radius*1e3:.1f} mm) ...")

        ts = OpenPMDTimeSeries(os.path.join(diags, "fields"),
                               check_all_files=False)
        field_plot(ts, cfg, results)
        z, phi_vac, phi_end = phi_axis_plot(ts, cfg, results)

        s = read_scraped(diags)
        steady = current_plot(s, cfg, tgts, results)
        means = energy_plot(s, cfg, tgts, results)
        row = ledger(s, cfg, tgts, steady)

        # Energy conservation: electrons born ~at rest at the emission plane
        # arrive with e*[phi(collector) - phi(emit_z)] + flux-Maxwellian launch
        # energy 2kT.  phi is the SELF-CONSISTENT end-state field (space charge
        # included), INTERPOLATED to emit_z: the emission plane sits exactly
        # between two cell centres, and on the ~53 V/mm gap gradient the
        # nearest-cell ambiguity is worth +-1.3 eV.
        ke_expect = (cfg.v_collector
                     - float(np.interp(cfg.emit_z, z, phi_end))
                     ) + 2.0 * kT_launch_eV
        row["ke_expect_eV"] = ke_expect
        row["ke_coll_eV"] = means.get("collector", float("nan"))
        row["ke_err_eV"] = row["ke_coll_eV"] - ke_expect
        row["frac"] = {k: steady.get(k, 0.0) / cfg.beam_current
                       for k in ("collector", "anode", "cathode", "radial")}
        rows.append(row)

    print("\n" + "=" * 72)
    print("TRANSMISSION TABLE (steady current / emitted)")
    print("=" * 72)
    print(f"{'scenario':30s} {'I_emit':>8s} {'%CL':>6s} {'hole':>6s} "
          f"{'coll%':>7s} {'anode%':>7s} {'cath%':>6s} {'wall%':>6s}")
    for r in rows:
        print(f"{r['scenario']:30s} {r['I_emit_uA']:6.0f}uA "
              f"{r['pct_of_child_langmuir']:5.1f}% {r['hole_radius_mm']:5.1f}mm "
              f"{100*r['frac']['collector']:6.2f}% {100*r['frac']['anode']:6.2f}% "
              f"{100*r['frac']['cathode']:5.2f}% {100*r['frac']['radial']:5.2f}%")

    transmission_plot(rows, results)
    ok = evaluate_gates(Config().validation, rows)

    spath = os.path.join(results, "summary_electron_gun.json")
    with open(spath, "w") as fh:
        json.dump({"case": "electron_gun",
                   "I_CL_uA": cfgs[0].child_langmuir_uA(),
                   "scenarios": rows, "gates_pass": ok}, fh, indent=2)
    print(f"wrote {spath}\nplots -> {results}/")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
