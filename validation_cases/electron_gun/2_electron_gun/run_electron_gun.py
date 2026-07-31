#!/usr/bin/env python3
"""electron_gun validation case: holed-anode RZ gun (WarpX PICMI).

1_negative_cathode plus one new element: a grounded plate across the midplane
with a hole on axis (embedded boundary).  A prescribed-current beam is emitted
one cell inside the -100 V cathode (z_min); whatever clears the hole drifts to
the grounded collector (z_max).  Three scenarios (see inputs/electron_gun.yaml)
demonstrate aperture transmission vs space charge.

Each scenario runs in its OWN WarpX process (libwarpx cannot re-initialize
inside one process); the parent loop spawns `python run_electron_gun.py` with
XD_EGUN_SCENARIO set.  A scenario whose diags directory already holds a
config_used.yaml snapshot is considered finished and is skipped, so relaunching
after an interruption is safe.

All parameters live in inputs/electron_gun.yaml -- there are no command line
arguments.  Run from anywhere::

    python run_electron_gun.py            # runs all pending scenarios
    python analyze_electron_gun.py        # per-scenario plots + gate verdict
    python animate_electron_gun.py        # density/KE video per scenario
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = CASE_DIR / "inputs" / "electron_gun.yaml"

SPECIES_NAME = "electrons"
SCENARIO_ENV = "XD_EGUN_SCENARIO"


class Config:
    """Typed view of the YAML file plus derived quantities for ONE scenario.

    Every numeric leaf is coerced with float()/int(): PyYAML is a YAML 1.1
    parser, so floats written without a decimal point or with an unsigned
    exponent (1e19) silently load as strings.
    """

    def __init__(self, path: Path = CONFIG_FILE, scenario: str | None = None):
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
        self.v_anode = float(ele["v_anode"])

        ano = raw["anode"]
        self.anode_z_front = float(ano["z_front"])
        self.anode_thickness = float(ano["thickness"])

        emi = raw["emission"]
        self.emit_radius = float(emi["radius"])
        self.u_th = float(emi["u_th"])
        self.rms_velocity = self.u_th * scc.speed_of_light
        # The source plane sits one cell inside the cathode boundary so
        # particles spawn in a regular cell, never on the Dirichlet face.
        self.emit_z = self.z_min + self.d_z

        self.scenarios = [str(s["name"]) for s in raw["scenarios"]]
        self.scenario = scenario
        if scenario is not None:
            sc = next(s for s in raw["scenarios"] if str(s["name"]) == scenario)
            self.beam_current = float(sc["current"])
            self.hole_radius = float(sc["hole_radius"])
            self.flux = self.beam_current / (
                math.pi * self.emit_radius**2 * scc.elementary_charge
            )

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
        self.diags_base = (CASE_DIR / str(paths["diags_base"])).resolve()
        self.results_dir = (CASE_DIR / str(paths["results"])).resolve()
        if scenario is not None:
            self.diags_dir = self.diags_base / f"diags_{scenario}"

        self.video_fps = float(raw["video"]["fps"])

        # Gate tolerances (analysis only; absent block -> no gates evaluated).
        self.validation = {
            k: float(v) for k, v in (raw.get("validation") or {}).items()
        }

    # ----- analytic references (printed at launch, used by the analysis) -----

    def child_langmuir_uA(self) -> float:
        """Planar Child-Langmuir current [uA] for the accel gap over the spot."""
        d = self.anode_z_front - self.z_min
        v = abs(self.v_anode - self.v_cathode)
        j_cl = (4.0 * scc.epsilon_0 / 9.0) * math.sqrt(
            2.0 * scc.e / scc.m_e) * v**1.5 / d**2
        return j_cl * math.pi * self.emit_radius**2 * 1e6


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

    # Holed plate: conductor where z_front < z < z_front+thickness AND r > rh.
    # In RZ the EB parser is evaluated with (x -> r, y -> 0, z -> z).
    embedded_boundary = picmi.EmbeddedBoundary(
        implicit_function="min(z-za, min(za+ta-z, x-rh))",
        potential=cfg.v_anode,
        za=cfg.anode_z_front,
        ta=cfg.anode_thickness,
        rh=cfg.hole_radius,
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
        warpx_save_particles_at_zlo=1,   # cathode plane (reflected current)
        warpx_save_particles_at_zhi=1,   # collector plane (transmitted beam)
        warpx_save_particles_at_xhi=1,   # radial wall
        warpx_save_particles_at_eb=1,    # anode plate (aperture interception)
    )
    layout = picmi.PseudoRandomLayout(
        n_macroparticles_per_cell=cfg.beam_ppc, grid=grid
    )

    sim = picmi.Simulation(
        solver=solver,
        time_step_size=cfg.time_step,
        max_steps=cfg.max_steps,
        particle_shape=1,
        warpx_embedded_boundary=embedded_boundary,
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


def run_one(scenario: str) -> None:
    cfg = Config(scenario=scenario)
    i_cl = cfg.child_langmuir_uA()

    print("=" * 72)
    print(
        f"ELECTRON GUN [{scenario}]: {cfg.v_cathode:.0f} V cathode "
        f"-> {cfg.v_anode:.0f} V holed anode -> {cfg.v_collector:.0f} V "
        f"collector   (RZ, ES)"
    )
    print(
        f"  domain: r=[0,{cfg.r_max * 1e3:.1f}] mm, "
        f"z=[{cfg.z_min * 1e3:.1f},{cfg.z_max * 1e3:.1f}] mm, "
        f"grid={cfg.n_r}x{cfg.n_z}"
    )
    print(
        f"  anode: z=[{cfg.anode_z_front * 1e3:.2f},"
        f"{(cfg.anode_z_front + cfg.anode_thickness) * 1e3:.2f}] mm, "
        f"hole r<{cfg.hole_radius * 1e3:.2f} mm "
        f"(spot r<{cfg.emit_radius * 1e3:.2f} mm)"
    )
    print(
        f"  current: {cfg.beam_current * 1e6:.1f} uA = "
        f"{100 * cfg.beam_current * 1e6 / i_cl:.1f}% of planar "
        f"Child-Langmuir ({i_cl:.0f} uA for the "
        f"{(cfg.anode_z_front - cfg.z_min) * 1e3:.1f} mm gap)"
    )
    print(
        f"  dt={cfg.time_step:.2e} s, steps={cfg.max_steps}, "
        f"t_end={cfg.max_steps * cfg.time_step * 1e9:.2f} ns"
    )
    print(f"  output: {cfg.diags_dir}")
    print("=" * 72)

    cfg.diags_dir.mkdir(parents=True, exist_ok=True)
    sim = build_simulation(cfg)
    sim.step(cfg.max_steps)
    # Snapshot the config the run actually used.  Written only after step()
    # returns, so its presence also marks a finished scenario; the analysis
    # and animation scripts read THIS copy, immune to later edits of inputs/.
    shutil.copy2(cfg.source_path, cfg.diags_dir / "config_used.yaml")
    print(f"done: {scenario} -> {cfg.diags_dir}")


def main() -> None:
    picked = os.environ.get(SCENARIO_ENV)
    if picked:
        run_one(picked)
        return

    cfg = Config()
    for scenario in cfg.scenarios:
        done = cfg.diags_base / f"diags_{scenario}" / "config_used.yaml"
        if done.exists():
            print(f"[skip] {scenario}: finished snapshot already at {done}")
            continue
        print(f"\n[launch] {scenario} (fresh WarpX process)")
        env = dict(os.environ, **{SCENARIO_ENV: scenario})
        res = subprocess.run([sys.executable, __file__], env=env)
        if res.returncode != 0:
            raise SystemExit(
                f"scenario {scenario} failed with rc={res.returncode}"
            )
    print("\nall scenarios finished")


if __name__ == "__main__":
    main()
