#!/usr/bin/env python3
"""Shared machinery for the current_collection validation cases.

A conducting sphere (embedded boundary) at fixed bias sits at the origin of an
RZ domain filled with the electron_contactor capstone plasma -- the SAME
n0/Te/Ti/reduced-ion-mass, cell size (0.15 mm), and ppc the chipsat case uses,
so these gates validate the chipsat's physics configuration, not just the
code.  The ambient plasma is maintained by one-sided Maxwellian flux injection
from the three open faces (bulk fill at t=0), the legacy run_probe.py recipe
ported into the YAML architecture.

Analytic references:
  I_th   = n0 * e * <v>/4 * 4*pi*a^2       exact at 0 V for ANY convex probe
                                           (no field -> straight orbits)
  I_OML  = I_th * (1 + e*V/kTe)            small-sphere ceiling, a/lambda_De << 1
  I_e/I_i = sqrt((mi/me)*(Te/Ti))          species ratio, area/density-free

Each case folder holds inputs/<case>.yaml plus thin zero-argument wrappers::

    python run_<case>.py        # -> outputs/diags/  (+ config_used.yaml)
    python analyze_<case>.py    # -> results/  + gate verdict (exit 0/1)
    python animate_<case>.py    # -> results/<case>_fields.mp4
"""

from __future__ import annotations

import glob
import json
import math
import os
import shutil
from pathlib import Path

import numpy as np
import yaml
from scipy import constants as scc

ELECTRONS, IONS = "electrons", "ions"


class Config:
    """Typed view of one case YAML plus derived plasma/probe quantities.

    Every numeric leaf is coerced with float()/int(): PyYAML is a YAML 1.1
    parser, so floats written without a decimal point or with an unsigned
    exponent (1e19) silently load as strings.
    """

    def __init__(self, case_dir: Path, path: Path | None = None):
        self.case_dir = Path(case_dir)
        self.case_name = self.case_dir.name
        self.source_path = Path(
            path or self.case_dir / "inputs" / f"{self.case_name}.yaml"
        )
        raw = yaml.safe_load(self.source_path.read_text())

        pro = raw["probe"]
        self.probe_radius = float(pro["radius"])
        self.bias = float(pro["bias"])

        pla = raw["plasma"]
        self.n0 = float(pla["n0"])
        self.Te_K = float(pla["Te_K"])
        self.Ti_K = float(pla["Ti_K"])
        self.ion_mass_me = float(pla["ion_mass_me"])

        geo = raw["geometry"]
        self.r_max = float(geo["r_max"])
        self.z_half = float(geo["z_half"])
        self.n_r = int(geo["n_r"])
        self.n_z = int(geo["n_z"])
        self.d_r = self.r_max / self.n_r
        self.d_z = 2.0 * self.z_half / self.n_z

        num = raw["numerics"]
        self.time_step = float(num["time_step"])
        self.max_steps = int(num["max_steps"])
        self.ppc = int(num["ppc"])
        self.random_seed = int(num["random_seed"])

        dia = raw["diagnostics"]
        self.field_period = int(dia["field_period"])
        self.scrape_period = int(dia["scrape_period"])
        self.reduced_period = int(dia["reduced_period"])
        self.steady_window_frac = float(dia["steady_window_frac"])

        self.gpu_arena_bytes = int(raw["compute"]["gpu_arena_bytes"])

        paths = raw["paths"]
        self.diags_dir = (self.case_dir / str(paths["diags"])).resolve()
        self.results_dir = (self.case_dir / str(paths["results"])).resolve()

        self.video_fps = float(raw["video"]["fps"])

        # Gate tolerances (analysis only; absent block -> no gates evaluated).
        self.validation = {
            k: float(v) for k, v in (raw.get("validation") or {}).items()
        }

        # ----- derived plasma/probe quantities (all SI unless noted) -----
        self.m_ion = self.ion_mass_me * scc.m_e
        self.kTe_J = scc.k * self.Te_K
        self.kTi_J = scc.k * self.Ti_K
        self.kTe_eV = self.kTe_J / scc.e
        self.kTi_eV = self.kTi_J / scc.e
        self.vth_e = math.sqrt(self.kTe_J / scc.m_e)
        self.vth_i = math.sqrt(self.kTi_J / self.m_ion)
        self.vbar_e = math.sqrt(8.0 * self.kTe_J / (math.pi * scc.m_e))
        self.vbar_i = math.sqrt(8.0 * self.kTi_J / (math.pi * self.m_ion))
        self.flux_e = self.n0 * self.vbar_e / 4.0  # one-sided Maxwellian flux
        self.flux_i = self.n0 * self.vbar_i / 4.0
        self.debye = math.sqrt(
            scc.epsilon_0 * self.kTe_J / (self.n0 * scc.e**2)
        )
        self.wpe = math.sqrt(self.n0 * scc.e**2 / (scc.m_e * scc.epsilon_0))

        area = 4.0 * math.pi * self.probe_radius**2
        self.I_th_e = scc.e * self.flux_e * area
        self.I_th_i = scc.e * self.flux_i * area
        self.species_ratio_theory = math.sqrt(
            self.ion_mass_me * self.Te_K / self.Ti_K
        )
        self.chi = self.bias / self.kTe_eV  # e*V/kTe
        self.I_oml_e = self.I_th_e * (1.0 + max(self.chi, 0.0))
        # Repelled-species Boltzmann factor (ions for a positive bias).
        self.ion_boltzmann = math.exp(-max(self.bias, 0.0) / self.kTi_eV)


def banner(cfg: Config) -> None:
    print("=" * 72)
    print(f"CURRENT COLLECTION [{cfg.case_name}]: sphere a = "
          f"{cfg.probe_radius * 1e3:.2f} mm at {cfg.bias:+.1f} V  (RZ, ES)")
    print(f"  plasma: n0={cfg.n0:.3e} m^-3, Te={cfg.Te_K:.1f} K "
          f"({cfg.kTe_eV * 1e3:.1f} meV), Ti={cfg.Ti_K:.1f} K, "
          f"mi={cfg.ion_mass_me:.0f} me (chipsat capstone plasma)")
    print(f"  lambda_De={cfg.debye * 1e3:.3f} mm -> a/lambda_De="
          f"{cfg.probe_radius / cfg.debye:.3f}, "
          f"cells/lambda_De={cfg.debye / cfg.d_r:.1f}, "
          f"cells/a={cfg.probe_radius / cfg.d_r:.1f}")
    print(f"  domain: r=[0,{cfg.r_max * 1e3:.1f}] mm "
          f"({cfg.r_max / cfg.debye:.1f} lambda_De), z=+-"
          f"{cfg.z_half * 1e3:.1f} mm, grid {cfg.n_r}x{cfg.n_z}, "
          f"dx={cfg.d_r * 1e3:.2f} mm")
    print(f"  theory: I_th_e={cfg.I_th_e * 1e6:.5f} uA, "
          f"I_th_i={cfg.I_th_i * 1e9:.3f} nA, "
          f"I_e/I_i={cfg.species_ratio_theory:.3f}")
    if cfg.bias > 0:
        print(f"  chi=e*V/kTe={cfg.chi:.2f} -> OML ceiling "
              f"I_OML={cfg.I_oml_e * 1e6:.4f} uA "
              f"(= I_th * {1 + cfg.chi:.3f}); "
              f"ion Boltzmann factor exp(-eV/kTi)={cfg.ion_boltzmann:.2e}")
    v_fall = math.sqrt(2.0 * scc.e * max(cfg.bias, 0.0) / scc.m_e)
    vmax = v_fall + 4.0 * cfg.vth_e
    cfl = cfg.time_step * vmax / min(cfg.d_r, cfg.d_z)
    print(f"  dt={cfg.time_step:.2e} s (CFL {cfl:.2f}, "
          f"wpe*dt={cfg.wpe * cfg.time_step:.2e}), steps={cfg.max_steps} "
          f"-> t_end={cfg.max_steps * cfg.time_step * 1e6:.2f} us")
    print(f"  ppc={cfg.ppc}/species, output: {cfg.diags_dir}")
    print("=" * 72)
    assert cfl < 1.0, f"dt too large: CFL={cfl:.2f}"
    assert max(cfg.d_r, cfg.d_z) < cfg.debye, "grid must resolve lambda_De"


def build_simulation(cfg: Config):
    """Assemble and return the PICMI Simulation (WarpX is not stepped here)."""
    from pywarpx import amrex as amrex_params
    from pywarpx import picmi

    # AMReX defaults to pre-allocating ~3/4 of TOTAL GPU memory; cap the arena
    # so the run coexists with other GPU users.
    amrex_params.the_arena_init_size = cfg.gpu_arena_bytes

    grid = picmi.CylindricalGrid(
        number_of_cells=[cfg.n_r, cfg.n_z],
        n_azimuthal_modes=1,
        lower_bound=[0.0, -cfg.z_half],
        upper_bound=[cfg.r_max, cfg.z_half],
        lower_boundary_conditions=["none", "dirichlet"],
        upper_boundary_conditions=["dirichlet", "dirichlet"],
        lower_boundary_conditions_particles=["none", "absorbing"],
        upper_boundary_conditions_particles=["absorbing", "absorbing"],
        warpx_max_grid_size=1024,
    )

    solver = picmi.ElectrostaticSolver(
        grid=grid,
        method="Multigrid",
        required_precision=1.0e-5,
        # The 0 V case is grounded EVERYWHERE (walls and probe): the relative
        # criterion can then never converge, so give MLMG an absolute one.
        warpx_absolute_tolerance=1.0e-3,
        maximum_iterations=500,
        warpx_self_fields_verbosity=0,
    )

    # Conducting sphere at the origin.  In RZ the EB parser is evaluated with
    # (x -> r, y -> 0, z -> z), so this is a true sphere.
    embedded_boundary = picmi.EmbeddedBoundary(
        implicit_function="-(x**2+y**2+z**2-a**2)",
        potential=cfg.bias,
        a=cfg.probe_radius,
    )

    # Bulk Maxwellian fill at t=0 plus one-sided Maxwellian influx from the
    # three open faces.  Flux-layout macroweight is matched to the bulk's via
    # nu = flux*dt*ppc/(n0*dx) macroparticles per boundary cell per step.
    def make_species(name, vth, flux, kw):
        bulk = picmi.UniformDistribution(
            density=cfg.n0, rms_velocity=[vth, vth, vth])
        flux_r = picmi.UniformFluxDistribution(
            flux=flux, surface_flux_position=cfg.r_max,
            flux_normal_axis="r", flux_direction=-1,
            gaussian_flux_momentum_distribution=True,
            rms_velocity=[vth, vth, vth])
        flux_zlo = picmi.UniformFluxDistribution(
            flux=flux, surface_flux_position=-cfg.z_half,
            flux_normal_axis="z", flux_direction=+1,
            gaussian_flux_momentum_distribution=True,
            rms_velocity=[vth, vth, vth])
        flux_zhi = picmi.UniformFluxDistribution(
            flux=flux, surface_flux_position=cfg.z_half,
            flux_normal_axis="z", flux_direction=-1,
            gaussian_flux_momentum_distribution=True,
            rms_velocity=[vth, vth, vth])
        return picmi.Species(
            name=name,
            initial_distribution=[bulk, flux_r, flux_zlo, flux_zhi],
            warpx_save_particles_at_eb=1, **kw)

    electrons = make_species(ELECTRONS, cfg.vth_e, cfg.flux_e,
                             kw=dict(particle_type="electron"))
    ions = make_species(IONS, cfg.vth_i, cfg.flux_i,
                        kw=dict(charge=scc.e, mass=cfg.m_ion))

    sim = picmi.Simulation(
        solver=solver,
        time_step_size=cfg.time_step,
        max_steps=cfg.max_steps,
        particle_shape=1,
        warpx_embedded_boundary=embedded_boundary,
        warpx_random_seed=cfg.random_seed,
        warpx_used_inputs_file=str(cfg.diags_dir / "used_inputs.txt"),
    )

    bulk_layout = picmi.PseudoRandomLayout(
        n_macroparticles_per_cell=cfg.ppc, grid=grid)

    def flux_layout(flux):
        nu = flux * cfg.time_step * cfg.ppc / (cfg.n0 * cfg.d_z)
        return picmi.PseudoRandomLayout(n_macroparticles_per_cell=nu, grid=grid)

    sim.add_species(electrons,
                    layout=[bulk_layout] + [flux_layout(cfg.flux_e)] * 3)
    sim.add_species(ions,
                    layout=[bulk_layout] + [flux_layout(cfg.flux_i)] * 3)

    # NOTE: no ParticleDiagnostic -- millions of ambient macroparticles per
    # dump would dominate disk; fields + EB scrape + reduced cover the gates.
    sim.add_diagnostic(
        picmi.ParticleBoundaryScrapingDiagnostic(
            name="scrape",
            period=cfg.scrape_period,
            species=[electrons, ions],
            warpx_format="openpmd",
            warpx_openpmd_backend="h5",
            warpx_dump_last_timestep=True,
            write_dir=str(cfg.diags_dir),
        )
    )
    sim.add_diagnostic(
        picmi.FieldDiagnostic(
            name="fields",
            grid=grid,
            period=cfg.field_period,
            data_list=["phi", "rho", "rho_electrons", "rho_ions"],
            warpx_format="openpmd",
            warpx_openpmd_backend="h5",
            write_dir=str(cfg.diags_dir),
        )
    )
    sim.add_diagnostic(
        picmi.ReducedDiagnostic(
            diag_type="ParticleNumber",
            name="particle_number",
            period=cfg.reduced_period,
            path=f"{cfg.diags_dir / 'reducedfiles'}/",
        )
    )
    return sim


def run_case(case_dir: Path) -> None:
    cfg = Config(case_dir)
    banner(cfg)
    if cfg.diags_dir.exists() and any(cfg.diags_dir.iterdir()):
        print("[warning] diags directory is not empty; stale openPMD "
              "iterations from a previous run may mix with this one.")
    cfg.diags_dir.mkdir(parents=True, exist_ok=True)
    sim = build_simulation(cfg)
    sim.step(cfg.max_steps)
    # Snapshot the config the run actually used.  Written only after step()
    # returns, so its presence also marks a finished run; the analysis and
    # animation scripts read THIS copy, immune to later edits of inputs/.
    shutil.copy2(cfg.source_path, cfg.diags_dir / "config_used.yaml")
    print(f"done: {cfg.max_steps} steps -> {cfg.diags_dir}")


# ======================================================================
# analysis
# ======================================================================

def load_used_config(case_dir: Path) -> Config:
    """Config snapshot of the finished run (paths located via inputs/)."""
    used = Config(case_dir).diags_dir / "config_used.yaml"
    if not used.exists():
        raise SystemExit(
            f"{used} not found -- run the run_ script to completion first")
    return Config(case_dir, used)


def read_eb_scraped(cfg: Config):
    """Weighted EB hits per species: dict name -> (it, w, ke_eV) arrays."""
    import openpmd_api as io

    out = {}
    sub = os.path.join(str(cfg.diags_dir), "scrape", "particles_at_eb")
    if not glob.glob(os.path.join(sub, "*.h5")):
        return out
    series = io.Series(os.path.join(sub, "openpmd_%T.h5"), io.Access.read_only)
    masses = {ELECTRONS: scc.m_e, IONS: cfg.m_ion}
    cols = {n: {"it": [], "w": [], "ke": []} for n in masses}
    for it in series.iterations:
        parts = series.iterations[it].particles
        for name, mass in masses.items():
            if name not in parts:
                continue
            p = parts[name]
            wh = p["weighting"][io.Mesh_Record_Component.SCALAR]
            dw = wh.load_chunk()
            handles = {c: p["momentum"][c] for c in ("x", "y", "z")}
            data = {c: h.load_chunk() for c, h in handles.items()}
            series.flush()
            w = np.asarray(dw) * wh.unit_SI
            if w.size == 0:
                continue
            p2 = sum((np.asarray(data[c]) * handles[c].unit_SI) ** 2
                     for c in ("x", "y", "z"))
            gamma = np.sqrt(1.0 + p2 / (mass * scc.c) ** 2)
            ke = (gamma - 1.0) * mass * scc.c**2 / scc.e
            cols[name]["it"].append(np.full(w.size, it))
            cols[name]["w"].append(w)
            cols[name]["ke"].append(ke)
    series.close()
    for name, c in cols.items():
        out[name] = tuple(
            np.concatenate(v) if v else np.array([]) for v in
            (c["it"], c["w"], c["ke"]))
    return out


def current_history(cfg: Config, scraped):
    """Collected current per species at each scrape dump.

    Returns (t_us, {species: I[A]}).  A dump holds the weight collected since
    the previous dump (the scrape buffer is cleared every dump), so
    I = sum(w)*e/(scrape_period*dt).  Dump steps are taken from the union of
    both species so zero-collection dumps stay as zeros.
    """
    steps = np.unique(np.concatenate(
        [scraped[n][0] for n in scraped if scraped[n][0].size]
    )) if scraped else np.array([])
    steps = steps[steps > 0]
    t_us = steps * cfg.time_step * 1e6
    hist = {}
    for name, (it, w, _ke) in scraped.items():
        hist[name] = np.array([
            w[it == k].sum() * scc.e / (cfg.scrape_period * cfg.time_step)
            for k in steps])
    return t_us, hist


def steady_stats(cfg: Config, t_us, I, n_blocks: int = 5):
    """Mean and block-std of I over the last steady_window_frac of the run."""
    if len(I) == 0:
        return float("nan"), float("nan")
    i0 = int((1.0 - cfg.steady_window_frac) * len(I))
    win = I[i0:]
    blocks = [b.mean() for b in np.array_split(win, n_blocks) if b.size]
    return float(win.mean()), float(np.std(blocks, ddof=1) / math.sqrt(len(blocks)))


def field_rz(ts, field, iteration):
    """Reconstruct the (r>=0, z) half-plane, robust to axis order."""
    F, info = ts.get_field(field=field, iteration=iteration, m="all", theta=0.0)
    r, z = np.asarray(info.r), np.asarray(info.z)
    raxis = next(k for k, v in dict(info.axes).items() if v == "r")
    if raxis == 1:
        F = F.T  # -> [r, z]
    pos = r >= 0
    return F[pos], r[pos], z


def far_field_densities(ts, cfg: Config, iteration):
    """Volume-weighted n_e, n_i over the far shell 0.65..0.85 of the domain.

    The shell is far from the probe (>= 4 lambda_De) and clear of the open
    boundaries; RZ cell volume is proportional to r, hence the r-weighting.
    """
    rho_e, r, z = field_rz(ts, "rho_electrons", iteration)
    rho_i, _, _ = field_rz(ts, "rho_ions", iteration)
    R, Z = np.meshgrid(r, z, indexing="ij")
    s = np.hypot(R, Z)
    smax = min(cfg.r_max, cfg.z_half)
    mask = (s > 0.65 * smax) & (s < 0.85 * smax)
    wgt = np.where(mask, R, 0.0)
    n_e = float((np.abs(rho_e) / scc.e * wgt).sum() / wgt.sum())
    n_i = float((np.abs(rho_i) / scc.e * wgt).sum() / wgt.sum())
    return n_e, n_i


def edge_phi(ts, cfg: Config, iteration, inset: int = 3):
    """Max |phi| a few cells inside the three open boundaries (containment)."""
    phi, r, z = field_rz(ts, "phi", iteration)
    return float(max(np.abs(phi[-1 - inset, :]).max(),
                     np.abs(phi[:, inset]).max(),
                     np.abs(phi[:, -1 - inset]).max()))


def sheath_profile(ts, cfg: Config, iteration):
    """Midplane radial phi profile: (r, phi(r, z~0))."""
    phi, r, z = field_rz(ts, "phi", iteration)
    iz = int(np.argmin(np.abs(z)))
    return r, phi[:, iz]


def sheath_radius(r, phi, threshold):
    """Outermost radius where |phi| >= threshold (linear interpolation)."""
    a = np.abs(phi)
    above = np.where(a >= threshold)[0]
    if above.size == 0:
        return float("nan")
    i = above[-1]
    if i + 1 >= len(r):
        return float(r[i])
    f = (a[i] - threshold) / max(a[i] - a[i + 1], 1e-30)
    return float(r[i] + f * (r[i + 1] - r[i]))


def analyze_case(case_dir: Path) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from openpmd_viewer import OpenPMDTimeSeries

    cfg = load_used_config(case_dir)
    results = str(cfg.results_dir)
    os.makedirs(results, exist_ok=True)
    name = cfg.case_name
    print(f"Analyzing {name} in {cfg.diags_dir} ...")
    banner(cfg)

    # ----- collected current vs time + steady stats -----
    scraped = read_eb_scraped(cfg)
    t_us, hist = current_history(cfg, scraped)
    I_e = hist.get(ELECTRONS, np.array([]))
    I_i = hist.get(IONS, np.array([]))
    Ie_mean, Ie_err = steady_stats(cfg, t_us, I_e)
    Ii_mean, Ii_err = steady_stats(cfg, t_us, I_i)
    I_pred_e = cfg.I_oml_e if cfg.bias > 0 else cfg.I_th_e

    fig, (axe, axi) = plt.subplots(2, 1, figsize=(8.4, 7.2), sharex=True)
    axe.plot(t_us, I_e * 1e6, color="tab:blue", lw=1.2, label="collected I_e")
    axe.axhline(cfg.I_th_e * 1e6, color="gray", ls="--",
                label=f"I_th = {cfg.I_th_e * 1e6:.4f} uA (exact at 0 V)")
    if cfg.bias > 0:
        axe.axhline(cfg.I_oml_e * 1e6, color="tab:red", ls="--",
                    label=f"I_OML = {cfg.I_oml_e * 1e6:.3f} uA (ceiling)")
    axe.set_ylabel("electron current [uA]")
    axi.plot(t_us, I_i * 1e9, color="tab:orange", lw=1.2, label="collected I_i")
    ref_i = cfg.I_th_i * (cfg.ion_boltzmann if cfg.bias > 0 else 1.0)
    axi.axhline(ref_i * 1e9, color="gray", ls="--",
                label=(f"I_th_i*exp(-eV/kTi) = {ref_i * 1e9:.2e} nA"
                       if cfg.bias > 0 else
                       f"I_th_i = {cfg.I_th_i * 1e9:.3f} nA"))
    axi.set_ylabel("ion current [nA]")
    axi.set_xlabel("time [us]")
    i0 = int((1.0 - cfg.steady_window_frac) * len(t_us)) if len(t_us) else 0
    for ax in (axe, axi):
        if len(t_us):
            ax.axvspan(t_us[i0], t_us[-1], color="green", alpha=0.08,
                       label="steady window")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle(f"collected current  [{name}]  sphere "
                 f"{cfg.probe_radius * 1e3:.2f} mm at {cfg.bias:+.1f} V")
    fig.tight_layout()
    out = os.path.join(results, f"current_{name}.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")
    if len(t_us):
        csv = os.path.join(results, f"current_{name}.csv")
        with open(csv, "w") as fh:
            fh.write("t_us,I_e_A,I_i_A\n")
            for k in range(len(t_us)):
                fh.write(f"{t_us[k]:.4f},{I_e[k]:.6e},{I_i[k]:.6e}\n")

    # ----- fields: 2D map, sheath growth, far-field density, edge check -----
    ts = OpenPMDTimeSeries(os.path.join(str(cfg.diags_dir), "fields"),
                           check_all_files=False)
    its = ts.iterations
    last = its[-1]

    phi, r, z = field_rz(ts, "phi", last)
    rho_e, _, _ = field_rz(ts, "rho_electrons", last)
    ne = np.abs(rho_e) / scc.e
    rr = np.concatenate([-r[::-1], r]) * 1e3
    zmm = z * 1e3
    PHI = np.vstack([phi[::-1], phi])
    NE = np.vstack([ne[::-1], ne])
    fig, axs = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    vlim = max(abs(PHI.min()), abs(PHI.max()), 0.05)
    p0 = axs[0].pcolormesh(zmm, rr, PHI, cmap="RdBu_r", shading="auto",
                           vmin=-vlim, vmax=vlim)
    fig.colorbar(p0, ax=axs[0], label="phi [V]")
    axs[0].set_title(f"potential phi (step {last})")
    p1 = axs[1].pcolormesh(zmm, rr, NE, cmap="inferno", shading="auto",
                           vmin=0, vmax=max(1.5 * cfg.n0, NE.max() * 0.5))
    fig.colorbar(p1, ax=axs[1], label="n_e [m^-3]")
    axs[1].set_title("electron density n_e")
    for ax in axs:
        ax.add_patch(plt.Circle((0.0, 0.0), cfg.probe_radius * 1e3,
                                color="0.4", zorder=6))
        ax.set_xlabel("z [mm]")
    axs[0].set_ylabel("r [mm] (mirrored)")
    fig.suptitle(f"{name}: sphere {cfg.probe_radius * 1e3:.2f} mm at "
                 f"{cfg.bias:+.1f} V in capstone plasma")
    fig.tight_layout()
    out = os.path.join(results, f"fields_{name}.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")

    # sheath: midplane |phi|(r) at several times + edge radius history
    thr = cfg.kTe_eV  # sheath edge at e*|phi| = kTe
    picks = its[:: max(1, len(its) // 6)]
    fig, (axp, axs_) = plt.subplots(2, 1, figsize=(8.4, 7.2))
    rs_hist = []
    for it in its:
        rp, pp = sheath_profile(ts, cfg, it)
        rs_hist.append(sheath_radius(rp, pp, thr))
        if it in picks or it == last:
            axp.plot(rp * 1e3, np.abs(pp), lw=1.2,
                     label=f"t = {it * cfg.time_step * 1e6:.2f} us")
    axp.axhline(thr, color="gray", ls=":",
                label=f"kTe/e = {thr * 1e3:.0f} mV (sheath-edge def.)")
    axp.axvline(cfg.probe_radius * 1e3, color="0.4", lw=2, alpha=0.7)
    axp.set_yscale("log")
    axp.set_xlabel("r [mm] (midplane z~0)")
    axp.set_ylabel("|phi| [V]")
    axp.set_title(f"midplane potential profile  [{name}]")
    axp.legend(fontsize=7)
    axp.grid(alpha=0.3)
    t_all = np.array(its) * cfg.time_step * 1e6
    axs_.plot(t_all, np.array(rs_hist) * 1e3, "-o", ms=3, color="tab:purple")
    axs_.axhline(cfg.debye * 1e3, color="gray", ls="--", label="lambda_De")
    axs_.axhline(cfg.probe_radius * 1e3, color="0.4", lw=2, alpha=0.7,
                 label="probe radius")
    axs_.set_xlabel("time [us]")
    axs_.set_ylabel("sheath radius r(|phi|=kTe/e) [mm]")
    axs_.set_title("sheath growth")
    axs_.legend(fontsize=8)
    axs_.grid(alpha=0.3)
    fig.tight_layout()
    out = os.path.join(results, f"sheath_{name}.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")

    n_e_far, n_i_far = far_field_densities(ts, cfg, last)
    phi_edge = edge_phi(ts, cfg, last)
    r_sheath = rs_hist[-1]

    # ----- report -----
    print("\n" + "=" * 72)
    print(f"MEASUREMENTS  [{name}]  (steady window = last "
          f"{100 * cfg.steady_window_frac:.0f}%)")
    print("=" * 72)
    print(f"I_e = {Ie_mean * 1e6:.5f} +- {Ie_err * 1e6:.5f} uA   "
          f"pred {I_pred_e * 1e6:.5f} uA  -> ratio "
          f"{Ie_mean / I_pred_e:.4f}")
    print(f"I_i = {Ii_mean * 1e9:.4f} +- {Ii_err * 1e9:.4f} nA   "
          f"I_th_i {cfg.I_th_i * 1e9:.4f} nA  -> ratio "
          f"{Ii_mean / cfg.I_th_i:.4f}"
          + (f"  (Boltzmann pred {cfg.ion_boltzmann:.2e}; measured excess = "
             f"ion-clock start-up bias, see README)" if cfg.bias > 0 else ""))
    if cfg.bias <= 0 and Ii_mean > 0:
        print(f"species ratio I_e/I_i = {Ie_mean / Ii_mean:.3f}  "
              f"theory {cfg.species_ratio_theory:.3f}")
    print(f"far-field n_e/n0 = {n_e_far / cfg.n0:.4f}, "
          f"n_i/n0 = {n_i_far / cfg.n0:.4f}, "
          f"|n_e-n_i|/n0 = {abs(n_e_far - n_i_far) / cfg.n0:.4f}")
    print(f"sheath radius (|phi|=kTe/e) = "
          f"{r_sheath * 1e3 if np.isfinite(r_sheath) else float('nan'):.2f} mm"
          f" = {r_sheath / cfg.debye if np.isfinite(r_sheath) else float('nan'):.2f}"
          f" lambda_De;  edge max|phi| = {phi_edge:.3f} V")

    # ----- gates -----
    # Each gate carries (name, |err| value, tolerance-check callable, detail).
    # A NaN measurement must surface as SKIPPED, never as a silent pass/fail:
    # a broad "except -> NaN" once converted 2 missing chipsat gates into an
    # apparent PASS, so the verdict line always prints the skipped count.
    val = cfg.validation
    gates = []

    def add_gate(gname, value, check, detail):
        gates.append((gname, value, check, detail))

    if val:
        if "i_e_rel_tol" in val:
            add_gate("I_e == I_th (exact thermal-flux law)",
                     abs(Ie_mean / cfg.I_th_e - 1.0),
                     lambda v: v <= val["i_e_rel_tol"],
                     f"ratio {Ie_mean / cfg.I_th_e:.4f} "
                     f"(tol {val['i_e_rel_tol']:.2f})")
        if "i_i_rel_tol" in val:
            add_gate("I_i == I_th_i",
                     abs(Ii_mean / cfg.I_th_i - 1.0),
                     lambda v: v <= val["i_i_rel_tol"],
                     f"ratio {Ii_mean / cfg.I_th_i:.4f} "
                     f"(tol {val['i_i_rel_tol']:.2f})")
        if "ratio_rel_tol" in val:
            m = Ie_mean / Ii_mean if Ii_mean else float("nan")
            add_gate("I_e/I_i == sqrt((mi/me)(Te/Ti))",
                     abs(m / cfg.species_ratio_theory - 1.0),
                     lambda v: v <= val["ratio_rel_tol"],
                     f"{m:.3f} vs {cfg.species_ratio_theory:.3f} "
                     f"(tol {val['ratio_rel_tol']:.2f})")
        if "i_e_over_oml_min" in val:
            ratio = Ie_mean / cfg.I_oml_e
            add_gate("I_e vs OML ceiling (a/lambda_De = "
                     f"{cfg.probe_radius / cfg.debye:.2f})",
                     ratio,
                     lambda v: val["i_e_over_oml_min"] <= v
                     <= val["i_e_over_oml_max"],
                     f"ratio {ratio:.4f} in "
                     f"[{val['i_e_over_oml_min']:.2f}, "
                     f"{val['i_e_over_oml_max']:.2f}]")
        if "far_density_rel_tol" in val:
            add_gate("far-field n_e == n0",
                     abs(n_e_far / cfg.n0 - 1.0),
                     lambda v: v <= val["far_density_rel_tol"],
                     f"ratio {n_e_far / cfg.n0:.4f} "
                     f"(tol {val['far_density_rel_tol']:.2f})")
        if "quasineutrality_tol" in val:
            add_gate("far-field quasineutrality",
                     abs(n_e_far - n_i_far) / cfg.n0,
                     lambda v: v <= val["quasineutrality_tol"],
                     f"|n_e-n_i|/n0 = "
                     f"{abs(n_e_far - n_i_far) / cfg.n0:.4f} "
                     f"(tol {val['quasineutrality_tol']:.2f})")
        if "edge_phi_max" in val:
            add_gate("sheath contained (edge |phi| small)",
                     phi_edge,
                     lambda v: v <= val["edge_phi_max"],
                     f"max|phi| {phi_edge:.3f} V <= "
                     f"{val['edge_phi_max']:.2f} V")

    print("\n" + "=" * 72)
    print(f"VALIDATION GATES  [{name}]")
    print("=" * 72)
    ok, skipped = True, []
    for gname, value, check, detail in gates:
        if not np.isfinite(value):
            skipped.append(gname)
            print(f"[SKIP] {gname}\n       measurement is NaN -- not evaluated")
            continue
        passed = bool(check(value))
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {gname}\n       {detail}")
    print("=" * 72)
    verdict = "PASS" if ok else "FAIL"
    print(f"VERDICT: {verdict} ({len(gates) - len(skipped)} gates evaluated"
          + (f", {len(skipped)} SKIPPED -- this verdict does NOT cover them"
             if skipped else "") + ")")
    print("=" * 72)

    summary = {
        "case": name,
        "bias_V": cfg.bias,
        "a_over_debye": cfg.probe_radius / cfg.debye,
        "I_th_e_uA": cfg.I_th_e * 1e6,
        "I_oml_e_uA": cfg.I_oml_e * 1e6,
        "I_e_uA": Ie_mean * 1e6, "I_e_err_uA": Ie_err * 1e6,
        "I_i_nA": Ii_mean * 1e9, "I_i_err_nA": Ii_err * 1e9,
        "I_e_over_pred": Ie_mean / I_pred_e,
        "species_ratio": (Ie_mean / Ii_mean) if Ii_mean else None,
        "species_ratio_theory": cfg.species_ratio_theory,
        "n_e_far_over_n0": n_e_far / cfg.n0,
        "n_i_far_over_n0": n_i_far / cfg.n0,
        "sheath_radius_mm": r_sheath * 1e3 if np.isfinite(r_sheath) else None,
        "edge_phi_V": phi_edge,
        "gates_pass": ok,
    }
    spath = os.path.join(results, f"summary_{name}.json")
    with open(spath, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"wrote {spath}\nplots -> {results}/")
    return ok


# ======================================================================
# animation
# ======================================================================

def animate_case(case_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
    from openpmd_viewer import OpenPMDTimeSeries

    cfg = load_used_config(case_dir)
    results = str(cfg.results_dir)
    os.makedirs(results, exist_ok=True)
    name = cfg.case_name
    out = os.path.join(results, f"{name}_fields.mp4")

    ts = OpenPMDTimeSeries(os.path.join(str(cfg.diags_dir), "fields"),
                           check_all_files=False)
    its = ts.iterations
    print(f"[{name}] {len(its)} frames: {its[0]}..{its[-1]}")

    def frame(it):
        phi, r, z = field_rz(ts, "phi", it)
        rho_e, _, _ = field_rz(ts, "rho_electrons", it)
        ne = np.abs(rho_e) / scc.e
        return (np.vstack([phi[::-1], phi]), np.vstack([ne[::-1], ne]),
                np.concatenate([-r[::-1], r]) * 1e3, z * 1e3)

    PHI, NE, rr, zmm = frame(its[-1])
    vlim = max(abs(PHI.min()), abs(PHI.max()), 0.05)
    ne_vmax = max(1.5 * cfg.n0, np.percentile(NE, 99))

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.5, 5.2), sharey=True)
    P0, N0, _, _ = frame(its[0])
    imP = axL.imshow(P0, origin="lower", extent=[zmm.min(), zmm.max(),
                                                 rr.min(), rr.max()],
                     aspect="auto", cmap="RdBu_r", vmin=-vlim, vmax=vlim)
    fig.colorbar(imP, ax=axL, label="phi [V]")
    axL.set_title("potential phi")
    imN = axR.imshow(N0, origin="lower", extent=[zmm.min(), zmm.max(),
                                                 rr.min(), rr.max()],
                     aspect="auto", cmap="inferno", vmin=0, vmax=ne_vmax)
    fig.colorbar(imN, ax=axR, label="n_e [m^-3]")
    axR.set_title("electron density n_e")
    for ax in (axL, axR):
        ax.add_patch(plt.Circle((0.0, 0.0), cfg.probe_radius * 1e3,
                                color="0.4", zorder=6))
        ax.set_xlabel("z [mm]")
    axL.set_ylabel("r [mm] (mirrored)")
    sup = fig.suptitle("")

    def update(i):
        it = its[i]
        P, N, _, _ = frame(it)
        imP.set_data(P)
        imN.set_data(N)
        sup.set_text(f"{name}: sphere {cfg.probe_radius * 1e3:.2f} mm at "
                     f"{cfg.bias:+.1f} V    t = "
                     f"{it * cfg.time_step * 1e6:.2f} us   (step {it})")
        return imP, imN

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
