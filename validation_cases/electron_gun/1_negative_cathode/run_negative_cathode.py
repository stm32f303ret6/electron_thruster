#!/usr/bin/env python3
"""negative_cathode validation case: two-plate RZ plane diode (WarpX PICMI).

A 10 microamp electron beam is emitted one cell inside a -100 V cathode on the
left boundary (z = -2 mm) and travels rightward (+z) to a grounded collector
(z = +2 mm).  The electron space charge is included self-consistently in the
Poisson solve.  The emitted current is prescribed; there is no thermionic or
field-emission model.  RZ z-normal flux injection reproduces the requested
current to ~0.01% (measured in the parent electron_two_plate study), so no
calibration factor is applied.

All parameters live in inputs/negative_cathode.yaml -- there are no command
line arguments.  Run from anywhere::

    python run_negative_cathode.py

Diagnostics are written to outputs/diags/ (relative to this file).  Then::

    python analyze_negative_cathode.py    # plots + CSVs + summary -> results/
    python animate_negative_cathode.py    # density/KE video       -> results/
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import yaml
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = CASE_DIR / "inputs" / "negative_cathode.yaml"

SPECIES_NAME = "electrons"


class Config:
    """Typed view of the YAML file plus derived quantities.

    Every numeric leaf is coerced with float()/int(): PyYAML is a YAML 1.1
    parser, so floats written without a decimal point or with an unsigned
    exponent (1e19) silently load as strings.
    """

    def __init__(self, path: Path = CONFIG_FILE):
        self.source_path = Path(path)
        raw = yaml.safe_load(self.source_path.read_text())
        self.case_name = str(raw["case_name"])

        geo = raw["geometry"]
        self.r_max = float(geo["r_max"])
        self.z_min = float(geo["z_min"])
        self.z_max = float(geo["z_max"])
        self.n_r = int(geo["n_r"])
        self.n_z = int(geo["n_z"])
        self.d_r = self.r_max / self.n_r
        self.d_z = (self.z_max - self.z_min) / self.n_z

        ele = raw["electrodes"]
        self.v_cathode = float(ele["v_cathode"])
        self.v_collector = float(ele["v_collector"])

        emi = raw["emission"]
        self.emit_radius = float(emi["radius"])
        self.beam_current = float(emi["current"])
        self.u_th = float(emi["u_th"])
        self.flux = self.beam_current / (
            math.pi * self.emit_radius**2 * scc.elementary_charge
        )
        self.rms_velocity = self.u_th * scc.speed_of_light
        # The source plane sits one cell inside the cathode boundary so
        # particles spawn in a regular cell, never on the Dirichlet face.
        self.emit_z = self.z_min + self.d_z

        num = raw["numerics"]
        self.time_step = float(num["time_step"])
        self.max_steps = int(num["max_steps"])
        self.beam_ppc = int(num["beam_ppc"])
        self.random_seed = int(num["random_seed"])

        dia = raw["diagnostics"]
        self.field_period = int(dia["field_period"])
        self.reduced_period = int(dia["reduced_period"])
        self.scrape_period = int(dia["scrape_period"])
        self.ke_max_ev = float(dia["ke_max_ev"])

        self.gpu_arena_bytes = int(raw["compute"]["gpu_arena_bytes"])

        paths = raw["paths"]
        self.diags_dir = (CASE_DIR / str(paths["diags"])).resolve()
        self.results_dir = (CASE_DIR / str(paths["results"])).resolve()

        self.video_fps = float(raw["video"]["fps"])

        # Gate tolerances (analysis only; absent block -> no gates evaluated).
        self.validation = {
            k: float(v) for k, v in (raw.get("validation") or {}).items()
        }


def build_simulation(cfg: Config):
    """Assemble and return the PICMI Simulation (WarpX is not stepped here)."""
    from pywarpx import amrex as amrex_params
    from pywarpx import picmi

    # AMReX defaults to pre-allocating ~3/4 of TOTAL GPU memory, which collides
    # with anything else on the card; cap the arena so the run coexists with
    # other GPU users.
    amrex_params.the_arena_init_size = cfg.gpu_arena_bytes

    grid = picmi.CylindricalGrid(
        number_of_cells=[cfg.n_r, cfg.n_z],
        n_azimuthal_modes=1,
        lower_bound=[0.0, cfg.z_min],
        upper_bound=[cfg.r_max, cfg.z_max],
        lower_boundary_conditions=["none", "dirichlet"],
        upper_boundary_conditions=["neumann", "dirichlet"],
        lower_boundary_conditions_particles=["none", "absorbing"],
        upper_boundary_conditions_particles=["absorbing", "absorbing"],
        warpx_potential_lo_z=cfg.v_cathode,
        warpx_potential_hi_z=cfg.v_collector,
    )

    solver = picmi.ElectrostaticSolver(
        grid=grid,
        method="Multigrid",
        required_precision=1.0e-6,
        warpx_absolute_tolerance=1.0e-2,
        maximum_iterations=500,
        warpx_self_fields_verbosity=0,
    )

    # Emission is gated in the flux EXPRESSION only -- never via distribution
    # bounds in RZ (a y-bound there culls in theta, in radians).
    source = picmi.AnalyticFluxDistribution(
        flux="flux0*(sqrt(x*x+y*y)<rc)",
        flux_normal_axis="z",
        surface_flux_position=cfg.emit_z,
        flux_direction=+1,
        gaussian_flux_momentum_distribution=True,
        rms_velocity=[cfg.rms_velocity] * 3,
        flux0=cfg.flux,
        rc=cfg.emit_radius,
    )
    electrons = picmi.Species(
        name=SPECIES_NAME,
        particle_type="electron",
        initial_distribution=source,
        warpx_save_particles_at_zlo=1,   # cathode plane
        warpx_save_particles_at_zhi=1,   # collector plane
        warpx_save_particles_at_xhi=1,   # radial wall
    )
    layout = picmi.PseudoRandomLayout(
        n_macroparticles_per_cell=cfg.beam_ppc, grid=grid
    )

    sim = picmi.Simulation(
        solver=solver,
        time_step_size=cfg.time_step,
        max_steps=cfg.max_steps,
        particle_shape=1,
        warpx_random_seed=cfg.random_seed,
        warpx_used_inputs_file=str(cfg.diags_dir / "used_inputs.txt"),
    )
    sim.add_species(electrons, layout=layout)

    reduced_path = f"{cfg.diags_dir / 'reducedfiles'}/"
    sim.add_diagnostic(
        picmi.ReducedDiagnostic(
            diag_type="ParticleNumber",
            name="beam_n",
            period=cfg.reduced_period,
            path=reduced_path,
        )
    )
    sim.add_diagnostic(
        picmi.ReducedDiagnostic(
            diag_type="ParticleEnergy",
            name="beam_e",
            period=cfg.reduced_period,
            path=reduced_path,
        )
    )
    sim.add_diagnostic(
        picmi.FieldDiagnostic(
            name="fields",
            grid=grid,
            period=cfg.field_period,
            data_list=["phi", "rho"],
            warpx_format="openpmd",
            warpx_openpmd_backend="h5",
            write_dir=str(cfg.diags_dir),
        )
    )
    sim.add_diagnostic(
        picmi.ParticleDiagnostic(
            name="particles",
            period=cfg.field_period,
            species=[electrons],
            data_list=["position", "momentum", "weighting"],
            warpx_format="openpmd",
            warpx_openpmd_backend="h5",
            write_dir=str(cfg.diags_dir),
        )
    )
    sim.add_diagnostic(
        picmi.ParticleBoundaryScrapingDiagnostic(
            name="scrape",
            period=cfg.scrape_period,
            species=[electrons],
            warpx_format="openpmd",
            warpx_openpmd_backend="h5",
            warpx_dump_last_timestep=True,
            write_dir=str(cfg.diags_dir),
        )
    )

    return sim


def main() -> None:
    cfg = Config()

    print("=" * 72)
    print(
        f"NEGATIVE CATHODE [{cfg.case_name}]: {cfg.v_cathode:.0f} V cathode "
        f"(z={cfg.z_min * 1e3:.0f} mm) -> {cfg.v_collector:.0f} V collector "
        f"(z=+{cfg.z_max * 1e3:.0f} mm)   (RZ, ES)"
    )
    print(
        f"  domain: r=[0,{cfg.r_max * 1e3:.1f}] mm, "
        f"z=[{cfg.z_min * 1e3:.1f},{cfg.z_max * 1e3:.1f}] mm, "
        f"grid={cfg.n_r}x{cfg.n_z}, dr={cfg.d_r * 1e6:.0f} um, "
        f"dz={cfg.d_z * 1e6:.0f} um"
    )
    print(
        f"  source: r<{cfg.emit_radius * 1e3:.2f} mm at "
        f"z={cfg.emit_z * 1e3:.2f} mm, current={cfg.beam_current * 1e6:.1f} uA, +z"
    )
    print(
        f"  dt={cfg.time_step:.2e} s, steps={cfg.max_steps}, "
        f"t_end={cfg.max_steps * cfg.time_step * 1e9:.2f} ns"
    )
    print(f"  output: {cfg.diags_dir}")
    print("=" * 72)

    if cfg.diags_dir.exists() and any(cfg.diags_dir.iterdir()):
        print(
            "[warning] diags directory is not empty; stale openPMD iterations "
            "from a previous run may mix with this one."
        )

    cfg.diags_dir.mkdir(parents=True, exist_ok=True)
    sim = build_simulation(cfg)
    sim.step(cfg.max_steps)
    # Snapshot the config the run actually used.  Written only after step()
    # returns, so its presence also marks a finished run; the analysis and
    # animation scripts read THIS copy, immune to later edits of inputs/.
    shutil.copy2(cfg.source_path, cfg.diags_dir / "config_used.yaml")
    print(f"done: {cfg.max_steps} steps -> {cfg.diags_dir}")


if __name__ == "__main__":
    main()
