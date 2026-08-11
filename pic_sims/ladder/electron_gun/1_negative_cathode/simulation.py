#!/usr/bin/env python3
"""emitter.negative_cathode: two-plate RZ plane diode (WarpX PICMI).

The complete PIC model for this stage lives in this one file: grid, boundaries,
solver, source, species, diagnostics, stepping.  A 10 uA electron beam is
emitted one cell inside a -100 V cathode on the left boundary (z = -2 mm) and
travels +z to a grounded collector (z = +2 mm); the electron space charge is
solved self-consistently.  The emitted current is prescribed (no thermionic or
field-emission model).

Each execution creates a fresh, immutable run directory under ``outputs/`` and
is marked COMPLETE only after its artifacts and final iteration are verified
(see ``ladder_contract``).  Run it directly::

    python simulation.py                 # uses ./config.yaml
    python simulation.py --config PATH    # an alternative config

then analyze the emitted run with ``analyze.py --run outputs/<run-id> --policy
acceptance.yaml``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Two lines of sys.path are the whole import mechanism (plan section 5.2).
CASE_DIR = Path(__file__).resolve().parent
_pic_root = CASE_DIR  # walk up to pic_sims/ (ladder_contract, shared plumbing)
while not (_pic_root / "ladder_contract.py").is_file():
    _pic_root = _pic_root.parent
sys.path.insert(0, str(_pic_root))
sys.path.insert(0, str(CASE_DIR))             # this stage's helpers.py

import ladder_contract as lc  # noqa: E402
from helpers import STAGE_ID, SPECIES_NAME, Config, load_config  # noqa: E402

DEFAULT_CONFIG = CASE_DIR / "config.yaml"
OUTPUTS_ROOT = CASE_DIR / "outputs"


def _warpx_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("pywarpx")
    except Exception:  # noqa: BLE001 -- provenance is best-effort
        return None


# ======================================================================
# PIC model
# ======================================================================

def build_simulation(cfg: Config, run: lc.Run):
    """Assemble and return the PICMI Simulation (WarpX is not stepped here)."""
    from pywarpx import amrex as amrex_params
    from pywarpx import picmi

    # AMReX defaults to pre-allocating ~3/4 of TOTAL GPU memory; cap the arena
    # so this small deck coexists with other GPU users.
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
        n_macroparticles_per_cell=cfg.beam_ppc, grid=grid)

    sim = picmi.Simulation(
        solver=solver,
        time_step_size=cfg.time_step,
        max_steps=cfg.max_steps,
        particle_shape=1,
        warpx_random_seed=cfg.random_seed,
        warpx_used_inputs_file=str(run.diags_dir / "used_inputs.txt"),
    )
    sim.add_species(electrons, layout=layout)

    reduced_path = f"{run.diags_dir / 'reducedfiles'}/"
    # ParticleNumber runs at the scrape cadence: it is the heartbeat that lets
    # analysis tell a genuine zero-collection interval from a lost dump.
    sim.add_diagnostic(picmi.ReducedDiagnostic(
        diag_type="ParticleNumber", name="beam_n",
        period=cfg.reduced_period, path=reduced_path))
    sim.add_diagnostic(picmi.ReducedDiagnostic(
        diag_type="ParticleEnergy", name="beam_e",
        period=cfg.reduced_period, path=reduced_path))
    sim.add_diagnostic(picmi.FieldDiagnostic(
        name="fields", grid=grid, period=cfg.field_period,
        data_list=["phi", "rho"], warpx_format="openpmd",
        warpx_openpmd_backend="h5", write_dir=str(run.diags_dir)))
    # No full phase-space ParticleDiagnostic: no gate or figure reads it and it
    # dominated run size (~3 GB).  Fields + EB/boundary scrape + reduced cover
    # every gate and the potential/density animation.
    sim.add_diagnostic(picmi.ParticleBoundaryScrapingDiagnostic(
        name="scrape", period=cfg.scrape_period, species=[electrons],
        warpx_format="openpmd", warpx_openpmd_backend="h5",
        warpx_dump_last_timestep=True, write_dir=str(run.diags_dir)))

    return sim


def observed_final_iteration(run: lc.Run) -> int | None:
    """Largest iteration actually written to the field diagnostic on disk."""
    iters = []
    for p in (run.diags_dir / "fields").glob("*.h5"):
        m = re.findall(r"\d+", p.stem)
        if m:
            iters.append(int(m[-1]))
    return max(iters) if iters else None


def banner(cfg: Config, run: lc.Run) -> None:
    print("=" * 72)
    print(f"NEGATIVE CATHODE [{run.run_id}]: {cfg.v_cathode:.0f} V cathode "
          f"(z={cfg.z_min * 1e3:.0f} mm) -> {cfg.v_collector:.0f} V collector "
          f"(z=+{cfg.z_max * 1e3:.0f} mm)   (RZ, ES)")
    print(f"  domain: r=[0,{cfg.r_max * 1e3:.1f}] mm, "
          f"z=[{cfg.z_min * 1e3:.1f},{cfg.z_max * 1e3:.1f}] mm, "
          f"grid={cfg.n_r}x{cfg.n_z}, dr={cfg.d_r * 1e6:.0f} um, "
          f"dz={cfg.d_z * 1e6:.0f} um")
    print(f"  source: r<{cfg.emit_radius * 1e3:.2f} mm at z={cfg.emit_z * 1e3:.2f} "
          f"mm, current={cfg.beam_current * 1e6:.1f} uA, +z")
    print(f"  dt={cfg.time_step:.2e} s, steps={cfg.max_steps}, "
          f"t_end={cfg.t_end * 1e9:.2f} ns")
    print(f"  output: {run.dir}")
    print("=" * 72)


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="negative_cathode PIC run")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--scenario", default=None,
                    help="unused (single-run stage); rejected if given")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config, scenario=args.scenario)

    run = lc.begin_run(
        run_root=OUTPUTS_ROOT, stage_id=STAGE_ID, config=cfg.effective_config(),
        random_seed=cfg.random_seed, expected_final_iteration=cfg.max_steps,
        source_files=[CASE_DIR / "simulation.py", CASE_DIR / "helpers.py"],
        provenance={"warpx_version": _warpx_version()})
    print(f"RUN_ID={run.run_id}", flush=True)
    banner(cfg, run)

    try:
        sim = build_simulation(cfg, run)
        sim.step(cfg.max_steps)
        lc.complete_run(
            run,
            expected_artifacts=["fields/*.h5", "reducedfiles/beam_n.txt"],
            observed_final_iteration=observed_final_iteration(run))
    except BaseException as exc:  # noqa: BLE001 -- record then re-raise
        lc.fail_run(run, exc)
        raise
    print(f"done: {cfg.max_steps} steps -> {run.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
