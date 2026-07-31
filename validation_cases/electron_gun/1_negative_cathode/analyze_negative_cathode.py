#!/usr/bin/env python3
"""Analysis for the negative_cathode validation case (see run_negative_cathode.py).

Physics parameters are read from outputs/diags/config_used.yaml -- the snapshot
of the config the run actually used (written when the run finishes), immune to
later edits of inputs/.  Writes to results/:

  current_negative_cathode.png / .csv  -- collected current vs time per boundary
  energy_negative_cathode.png  / .csv  -- arrival-energy spectra
  fields_negative_cathode.png          -- potential phi + electron density (mirrored +-r)
  phi_axis_negative_cathode.png        -- on-axis phi(z) and E_z(z), t=0 vs t_end
  summary_negative_cathode.json        -- machine-readable per-boundary summary
  + a fate ledger with a particle-budget closure check on stdout.

No command line arguments::

    python analyze_negative_cathode.py
"""

import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpmd_api as io
from openpmd_viewer import OpenPMDTimeSeries
from scipy import constants as scc

from run_negative_cathode import SPECIES_NAME, Config

m_e, e, c = scc.m_e, scc.e, scc.c

KE_BIN_EV = 0.5  # arrival-energy histogram bin width [eV]


def load_used_config() -> Config:
    """Config snapshot of the finished run (paths located via inputs/)."""
    used = Config().diags_dir / "config_used.yaml"
    if not used.exists():
        raise SystemExit(
            f"{used} not found -- run run_negative_cathode.py to completion first"
        )
    return Config(used)


def targets(cfg):
    """The three absorbing boundaries, main collector first."""
    return [
        dict(key="collector", bnd="zhi",
             label=f"collector ({cfg.v_collector:.0f} V)", color="tab:green"),
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
    """Per-particle arrays concatenated over all boundary subdirs:
    r,z [m], px/py/pz [kg m/s], w [weight], bnd [str], it [dump step]."""
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

            (xh, dx) = load("position", "x")  # Cartesian x = r*cos(theta)
            (yh, dy) = load("position", "y")  # Cartesian y = r*sin(theta)
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


def current_plot(s, cfg, tgts, outdir):
    """Collected current [uA] vs time at each boundary; returns steady means."""
    I_emit, dt, sp = cfg.beam_current, cfg.time_step, cfg.scrape_period
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
    ax.set_title("collected current vs time  [negative_cathode, RZ]")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = os.path.join(outdir, "current_negative_cathode.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")

    csv = os.path.join(outdir, "current_negative_cathode.csv")
    keys = [t["key"] for t in tgts]
    with open(csv, "w") as fh:
        fh.write("t_ns," + ",".join(f"{k}_uA" for k in keys) + "\n")
        for i in range(len(t_ns)):
            fh.write(f"{t_ns[i]:.4f}," +
                     ",".join(f"{curves[k][i]:.6e}" for k in keys) + "\n")
    print(f"  wrote {csv}")

    for tgt in tgts:
        v = steady[tgt["key"]]
        print(f"  {tgt['label']:24s} steady current ~ {v*1e6:8.4f} uA "
              f"({100*v/I_emit:5.1f}% of emitted {I_emit*1e6:.1f} uA)")
    return steady


def energy_plot(s, cfg, tgts, outdir):
    """Arrival-energy spectra per boundary; returns per-boundary mean KE."""
    if s["w"].size == 0:
        print("  (no scraped electrons for energy plot)")
        return {}
    ke_edges = np.arange(0.0, cfg.ke_max_ev + KE_BIN_EV, KE_BIN_EV)
    ke_centers = 0.5 * (ke_edges[:-1] + ke_edges[1:])
    fig, axs = plt.subplots(1, len(tgts), figsize=(5.2 * len(tgts), 4.6),
                            squeeze=False)
    axs = axs[0]
    means, hists = {}, {}
    for ax, tgt in zip(axs, tgts):
        m = s["bnd"] == tgt["bnd"]
        if not m.any():
            ax.set_title(f"{tgt['label']}: no hits")
            ax.set_xlabel("kinetic energy at impact [eV]")
            hists[tgt["key"]] = np.zeros_like(ke_centers)
            means[tgt["key"]] = float("nan")
            continue
        ke, w = ke_eV(s["px"][m], s["py"][m], s["pz"][m]), s["w"][m]
        mean = float(np.average(ke, weights=w))
        h, _ = np.histogram(ke, bins=ke_edges, weights=w)
        hists[tgt["key"]] = h
        means[tgt["key"]] = mean
        xmax = min(cfg.ke_max_ev, max(5.0, np.percentile(ke, 99.5) * 1.15))
        ax.bar(ke_centers, h, width=KE_BIN_EV, color=tgt["color"], alpha=0.85,
               align="center")
        ax.axvline(mean, color="k", ls=":", label=f"mean = {mean:.2f} eV")
        ax.set_xlim(0, xmax)
        ax.set_xlabel("kinetic energy at impact [eV]")
        ax.set_ylabel("electrons (weighted)")
        ax.set_title(tgt["label"])
        ax.legend()
        print(f"  {tgt['label']:24s} KE mean {mean:8.2f} eV  "
              f"median {np.median(ke):8.2f} eV  N = {w.sum():.3e}")
    fig.suptitle("electron arrival energy  [negative_cathode, RZ]")
    fig.tight_layout()
    out = os.path.join(outdir, "energy_negative_cathode.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")

    csv = os.path.join(outdir, "energy_negative_cathode.csv")
    keys = [t["key"] for t in tgts]
    with open(csv, "w") as fh:
        fh.write("ke_eV," + ",".join(keys) + "\n")
        for i in range(len(ke_centers)):
            fh.write(f"{ke_centers[i]:.3f}," +
                     ",".join(f"{hists[k][i]:.6e}" for k in keys) + "\n")
    print(f"  wrote {csv}")
    return means


def _draw_electrodes(axs, cfg):
    for ax in np.atleast_1d(axs):
        ax.axvline(cfg.z_min * 1e3, color="red", lw=4, alpha=0.85, zorder=5)
        ax.axvline(cfg.z_max * 1e3, color="deepskyblue", lw=4, alpha=0.85, zorder=5)
        ax.axvline(cfg.emit_z * 1e3, color="lime", ls=":", lw=1.5, alpha=0.9,
                   zorder=6)


def field_plot(ts, cfg, outdir):
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

    _draw_electrodes(axs, cfg)
    for ax in axs:
        ax.set_xlabel(f"z [mm]  ({cfg.v_cathode:.0f} V cathode  ->  "
                      f"{cfg.v_collector:.0f} V collector)")
    axs[0].set_ylabel("r [mm]  (radial; mirrored)")
    fig.suptitle(f"negative_cathode [RZ]: cathode {cfg.v_cathode:.0f} V | "
                 f"collector {cfg.v_collector:.0f} V")
    fig.tight_layout()
    out = os.path.join(outdir, "fields_negative_cathode.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")


def phi_axis_plot(ts, cfg, outdir):
    """On-axis phi(z) and E_z(z) = -dphi/dz at t=0 (geometry only) and t_end
    (with beam space charge).  Returns phi on axis at z~0, t_end."""
    first, last = ts.iterations[0], ts.iterations[-1]
    phi_f, r, z = field_rz(ts, "phi", first)
    phi_l, _, _ = field_rz(ts, "phi", last)
    p0f, p0l = phi_f[0], phi_l[0]  # r ~ 0 column
    zmm = z * 1e3
    ez_f = -np.gradient(p0f, z)
    ez_l = -np.gradient(p0l, z)

    fig, (axp, axe) = plt.subplots(2, 1, figsize=(8.2, 7.8), sharex=True)
    axp.plot(zmm, p0f, "--", color="gray", lw=1.6,
             label=f"t = 0, geometry only (step {first})")
    axp.plot(zmm, p0l, "-o", ms=3, color="tab:purple",
             label=f"t_end, with beam (step {last})")
    axp.axhline(0.0, color="gray", lw=0.8)
    axe.plot(zmm, ez_f / 1e3, "--", color="gray", lw=1.6, label="t = 0")
    axe.plot(zmm, ez_l / 1e3, "-", color="tab:red", lw=1.4, label="t_end")
    axe.axhline(0.0, color="gray", lw=0.8)

    for ax in (axp, axe):
        ax.axvline(cfg.z_min * 1e3, color="red", lw=2, alpha=0.6,
                   label=(f"cathode {cfg.v_cathode:.0f} V" if ax is axp else None))
        ax.axvline(cfg.z_max * 1e3, color="deepskyblue", lw=2, alpha=0.6,
                   label=(f"collector {cfg.v_collector:.0f} V" if ax is axp
                          else None))
        ax.grid(alpha=0.3)

    iz = int(np.argmin(np.abs(zmm)))
    phi_z0 = float(p0l[iz])
    axp.annotate(f"phi(0) ~ {phi_z0:.1f} V", xy=(0.0, phi_z0),
                 xytext=(0.3, phi_z0 + 0.12 * (max(p0l) - min(p0l) + 1)),
                 fontsize=10, arrowprops=dict(arrowstyle="->", color="black"))
    axp.set_ylabel("on-axis potential phi [V]")
    axp.set_title("On-axis phi(z) and E_z(z)  [negative_cathode, RZ]")
    axp.legend(fontsize=8, loc="best")
    axe.set_xlabel(f"z [mm]   ({cfg.v_cathode:.0f} V cathode  ->  "
                   f"{cfg.v_collector:.0f} V collector)")
    axe.set_ylabel("on-axis E_z [V/mm]")
    axe.legend(fontsize=8, loc="best")
    fig.tight_layout()
    out = os.path.join(outdir, "phi_axis_negative_cathode.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}   (phi(0) ~ {phi_z0:.2f} V on axis at t_end)")
    return phi_z0, z, p0f, p0l


def in_domain_weight(diags):
    """Beam weight still inside the domain, from the last ParticleNumber row.
    Columns for a single species: [0]step [1]time [2]total_macroparticles
    [3]electrons_macroparticles [4]total_weight [5]electrons_weight."""
    f = os.path.join(diags, "reducedfiles", "beam_n.txt")
    if not os.path.exists(f):
        return None
    row = np.atleast_2d(np.loadtxt(f))[-1]
    return float(row[5])


def ledger(s, cfg, tgts, steady, means, phi0, outdir):
    """Fate ledger + particle-budget closure; writes the summary JSON."""
    I_emit = cfg.beam_current
    total = float(s["w"].sum()) if s["w"].size else 0.0
    print("\n" + "=" * 72)
    print("ELECTRON FATE LEDGER  [negative_cathode, RZ]  (weighted)")
    print("=" * 72)
    print(f"total absorbed at all boundaries = {total:.4e}\n")
    weights = {}
    for tgt in tgts:
        m = s["bnd"] == tgt["bnd"] if s["w"].size else np.array([], dtype=bool)
        N = float(s["w"][m].sum()) if m.any() else 0.0
        weights[tgt["key"]] = N
        pct = 100 * N / total if total else 0.0
        print(f"{tgt['label']:26s}  N = {N:.4e}  ({pct:5.1f}% of absorbed)")

    t_end = cfg.max_steps * cfg.time_step
    n_emit = (I_emit / e) * t_end
    n_dom = in_domain_weight(str(cfg.diags_dir))
    print("-" * 72)
    closure = None
    msg = f"PARTICLE BUDGET: emitted={n_emit:.4e}  absorbed={total:.4e}"
    if n_dom is not None:
        closure = 100 * ((total + n_dom) - n_emit) / n_emit
        msg += f"  in-domain={n_dom:.4e}  -> closes {closure:+.2f}%"
    print(msg)
    print("=" * 72)

    summary = {
        "case": "negative_cathode",
        "I_emit_uA": I_emit * 1e6,
        "phi0_on_axis": phi0,
        "boundaries": {
            tgt["key"]: {
                "bnd": tgt["bnd"], "label": tgt["label"],
                "steady_uA": steady.get(tgt["key"], 0.0) * 1e6,
                "pct_emitted": 100 * steady.get(tgt["key"], 0.0) / I_emit,
                "mean_keV": means.get(tgt["key"], float("nan")),
                "total_weight": weights[tgt["key"]],
            }
            for tgt in tgts
        },
        "ledger": {"emitted": n_emit, "absorbed": total,
                   "in_domain": n_dom, "closure_pct": closure},
    }
    spath = os.path.join(outdir, "summary_negative_cathode.json")
    with open(spath, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"wrote {spath}")
    return summary


def evaluate_gates(cfg, summary, z, phi_vac, phi_end):
    """Validate the run against analytic theory; returns True if all gates pass.

    Every reference here is either closed-form (linear Laplace ramp, energy
    conservation from the emission plane, budget closure) or an explicitly
    labelled regression value (the space-charge depression).  Gates compare
    fields AT THE SAMPLED cell centres -- never at nominal coordinates -- and
    stray-boundary hits as FRACTIONS of emitted weight, never exact zeros.
    """
    val = cfg.validation
    if not val:
        print("(no validation block in the YAML -- gates skipped)")
        return True

    kT_launch_eV = m_e * cfg.rms_velocity**2 / e  # per-axis launch temperature
    L = cfg.z_max - cfg.z_min
    dV = cfg.v_collector - cfg.v_cathode

    def ramp(zz):
        return cfg.v_cathode + dV * (zz - cfg.z_min) / L

    # Flux-weighted Maxwellian launch: <KE> = kT (normal) + 2 * kT/2 (transverse)
    ke_expect = (cfg.v_collector - ramp(cfg.emit_z)) + 2.0 * kT_launch_eV

    n_emit = summary["ledger"]["emitted"]
    b = summary["boundaries"]
    iz = int(np.argmin(np.abs(z)))
    vac_err = float(np.max(np.abs(phi_vac - ramp(z))))
    depression = float(phi_vac[iz] - phi_end[iz])

    gates = [
        ("collector current == emitted",
         abs(b["collector"]["steady_uA"] / (cfg.beam_current * 1e6) - 1.0),
         val["collector_current_rel_tol"],
         f"{b['collector']['steady_uA']:.4f} uA vs {cfg.beam_current*1e6:.4f} uA"),
        ("collector KE == e*[phi(coll)-phi_ramp(emit_z)] + 2kT",
         abs(b["collector"]["mean_keV"] - ke_expect),
         val["ke_tol_ev"],
         f"{b['collector']['mean_keV']:.3f} eV vs analytic {ke_expect:.3f} eV"),
        ("cathode-return fraction",
         b["cathode"]["total_weight"] / n_emit,
         val["stray_fraction_max"],
         f"{b['cathode']['total_weight']:.3e} of {n_emit:.3e} emitted"),
        ("radial-wall fraction",
         b["radial"]["total_weight"] / n_emit,
         val["stray_fraction_max"],
         f"{b['radial']['total_weight']:.3e} of {n_emit:.3e} emitted"),
        ("vacuum phi(t=0) == Laplace ramp at sampled z",
         vac_err,
         val["vacuum_phi_abs_tol"],
         f"max |dphi| = {vac_err:.2e} V on axis"),
        ("space-charge depression at z~0 [regression]",
         abs(depression - val["depression_v"]),
         val["depression_tol_v"],
         f"{depression:.3f} V vs {val['depression_v']:.3f} V"),
        ("particle-budget closure",
         abs(summary["ledger"]["closure_pct"] or 0.0),
         val["closure_pct_max"],
         f"{summary['ledger']['closure_pct']:+.3f}%"),
    ]

    print("\n" + "=" * 72)
    print("VALIDATION GATES  [negative_cathode]")
    print("=" * 72)
    ok = True
    for name, value, tol, detail in gates:
        passed = value <= tol
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name}\n"
              f"       {detail}   (|err| {value:.3e} <= tol {tol:.3e})")
    print("=" * 72)
    print(f"VERDICT: {'PASS' if ok else 'FAIL'} ({len(gates)} gates evaluated)")
    print("=" * 72)
    return ok


def main():
    cfg = load_used_config()
    diags, results = str(cfg.diags_dir), str(cfg.results_dir)
    tgts = targets(cfg)
    os.makedirs(results, exist_ok=True)
    print(f"Analyzing negative_cathode run in {diags} ...")

    ts = OpenPMDTimeSeries(os.path.join(diags, "fields"), check_all_files=False)
    field_plot(ts, cfg, results)
    phi0, z, phi_vac, phi_end = phi_axis_plot(ts, cfg, results)

    s = read_scraped(diags)
    steady = current_plot(s, cfg, tgts, results)
    means = energy_plot(s, cfg, tgts, results)
    summary = ledger(s, cfg, tgts, steady, means, phi0, results)
    ok = evaluate_gates(cfg, summary, z, phi_vac, phi_end)
    print(f"\nplots -> {results}/")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
