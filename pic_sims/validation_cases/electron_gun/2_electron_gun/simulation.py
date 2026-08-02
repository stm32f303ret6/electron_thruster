#!/usr/bin/env python3
"""emitter.holed_anode: holed-anode RZ gun (WarpX PICMI).

The complete PIC model for this stage: emitter.negative_cathode plus a grounded
plate across the midplane with a hole on axis (an embedded boundary).  A
prescribed beam is emitted one cell inside the -100 V cathode; whatever clears
the hole drifts to the grounded collector.

ONE scenario runs per process -- libwarpx cannot re-initialize inside a process,
so ``run_ladder.py`` (or you) launch this once per scenario.  Each scenario run
is a separate immutable run whose config_used.yaml carries only that scenario's
effective physics; the manifest also records the SHA-256 of the full source
study so a cohort can be checked for compatibility.

    python simulation.py --scenario A_low_current_small_hole
    python simulation.py --scenario B_high_current_small_hole
    python simulation.py --scenario C_high_current_big_hole
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parents[1]))  # validation_cases/ (ladder_contract)
sys.path.insert(0, str(CASE_DIR))             # this stage's helpers.py

import ladder_contract as lc  # noqa: E402
from helpers import STAGE_ID, SPECIES_NAME, Config, load_config  # noqa: E402

DEFAULT_CONFIG = CASE_DIR / "config.yaml"
OUTPUTS_ROOT = CASE_DIR / "outputs"


def _warpx_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("pywarpx")
    except Exception:  # noqa: BLE001
        return None


def build_simulation(cfg: Config, run: lc.Run):
    """Assemble and return the PICMI Simulation (WarpX is not stepped here)."""
    from pywarpx import amrex as amrex_params
    from pywarpx import picmi

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
        n_macroparticles_per_cell=cfg.beam_ppc, grid=grid)

    sim = picmi.Simulation(
        solver=solver,
        time_step_size=cfg.time_step,
        max_steps=cfg.max_steps,
        particle_shape=1,
        warpx_embedded_boundary=embedded_boundary,
        warpx_random_seed=cfg.random_seed,
        warpx_used_inputs_file=str(run.diags_dir / "used_inputs.txt"),
    )
    sim.add_species(electrons, layout=layout)

    reduced_path = f"{run.diags_dir / 'reducedfiles'}/"
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
    # No full phase-space ParticleDiagnostic (see negative_cathode): fields +
    # boundary/EB scrape + reduced cover every gate and the animation.
    sim.add_diagnostic(picmi.ParticleBoundaryScrapingDiagnostic(
        name="scrape", period=cfg.scrape_period, species=[electrons],
        warpx_format="openpmd", warpx_openpmd_backend="h5",
        warpx_dump_last_timestep=True, write_dir=str(run.diags_dir)))

    return sim


def observed_final_iteration(run: lc.Run) -> int | None:
    iters = []
    for p in (run.diags_dir / "fields").glob("*.h5"):
        m = re.findall(r"\d+", p.stem)
        if m:
            iters.append(int(m[-1]))
    return max(iters) if iters else None


def banner(cfg: Config, run: lc.Run) -> None:
    i_cl = cfg.child_langmuir_uA()
    print("=" * 72)
    print(f"HOLED GUN [{run.run_id}] scenario={cfg.scenario}: "
          f"{cfg.v_cathode:.0f} V cathode -> {cfg.v_anode:.0f} V holed anode "
          f"-> {cfg.v_collector:.0f} V collector   (RZ, ES)")
    print(f"  anode: z=[{cfg.anode_z_front * 1e3:.2f},"
          f"{(cfg.anode_z_front + cfg.anode_thickness) * 1e3:.2f}] mm, "
          f"hole r<{cfg.hole_radius * 1e3:.2f} mm (spot r<{cfg.emit_radius * 1e3:.2f} mm)")
    print(f"  current: {cfg.beam_current * 1e6:.1f} uA "
          f"= {100 * cfg.beam_current * 1e6 / i_cl:.1f}% of planar I_CL "
          f"({i_cl:.0f} uA, a rough scale only)")
    print(f"  dt={cfg.time_step:.2e} s, steps={cfg.max_steps}, "
          f"t_end={cfg.t_end * 1e9:.2f} ns")
    print(f"  output: {run.dir}")
    print("=" * 72)


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="holed electron gun PIC run")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--scenario", required=True,
                    help="scenario name from config.yaml (one per process)")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config, scenario=args.scenario)

    run = lc.begin_run(
        run_root=OUTPUTS_ROOT, stage_id=STAGE_ID, config=cfg.effective_config(),
        scenario=cfg.scenario, study_config=cfg.study_config(),
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
    except BaseException as exc:  # noqa: BLE001
        lc.fail_run(run, exc)
        raise
    print(f"done: {cfg.scenario} -> {run.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
