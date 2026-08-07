#!/usr/bin/env python3
"""current_collection: conducting sphere at fixed bias in ambient plasma (WarpX).

The complete PIC model for this stage: a conducting sphere (embedded boundary)
at the origin of an RZ domain filled with the capstone
plasma.  The ambient plasma is maintained by one-sided Maxwellian flux injection
from the three open faces on top of a bulk fill at t=0.  This deck is duplicated
verbatim across the three collector stages; only config.yaml (bias, domain, dt)
and acceptance.yaml differ -- read one folder and you see the whole model.

Each execution creates a fresh, immutable run directory under ``outputs/`` and
is marked COMPLETE only after its artifacts and final iteration are verified.

    python simulation.py                 # uses ./config.yaml
    python analyze.py --run outputs/<run-id> --policy acceptance.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parents[1]))  # validation_cases/ (ladder_contract)
sys.path.insert(0, str(CASE_DIR))             # this stage's helpers.py

import ladder_contract as lc  # noqa: E402
from helpers import ELECTRONS, IONS, Config, load_config  # noqa: E402

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
        warpx_used_inputs_file=str(run.diags_dir / "used_inputs.txt"),
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

    # No full phase-space ParticleDiagnostic: millions of ambient macroparticles
    # per dump would dominate disk; fields + EB scrape + reduced cover the gates.
    sim.add_diagnostic(picmi.ParticleBoundaryScrapingDiagnostic(
        name="scrape", period=cfg.scrape_period, species=[electrons, ions],
        warpx_format="openpmd", warpx_openpmd_backend="h5",
        warpx_dump_last_timestep=True, write_dir=str(run.diags_dir)))
    sim.add_diagnostic(picmi.FieldDiagnostic(
        name="fields", grid=grid, period=cfg.field_period,
        data_list=["phi", "rho", "rho_electrons", "rho_ions"],
        warpx_format="openpmd", warpx_openpmd_backend="h5",
        write_dir=str(run.diags_dir)))
    # ParticleNumber heartbeat at the scrape cadence (lets analysis tell a
    # genuine zero-collection interval from a lost dump).
    sim.add_diagnostic(picmi.ReducedDiagnostic(
        diag_type="ParticleNumber", name="particle_number",
        period=cfg.reduced_period,
        path=f"{run.diags_dir / 'reducedfiles'}/"))
    return sim


def observed_final_iteration(run: lc.Run) -> int | None:
    iters = []
    for p in (run.diags_dir / "fields").glob("*.h5"):
        m = re.findall(r"\d+", p.stem)
        if m:
            iters.append(int(m[-1]))
    return max(iters) if iters else None


def banner(cfg: Config, run: lc.Run) -> None:
    print("=" * 72)
    print(f"CURRENT COLLECTION [{run.run_id}] {cfg.stage_id}: sphere a="
          f"{cfg.probe_radius * 1e3:.2f} mm at {cfg.bias:+.1f} V  (RZ, ES)")
    print(f"  plasma: n0={cfg.n0:.3e} m^-3, kTe={cfg.kTe_eV*1e3:.1f} meV, "
          f"mi={cfg.ion_mass_me:.0f} me;  lambda_De={cfg.debye*1e3:.3f} mm "
          f"-> a/lambda_De={cfg.a_over_debye:.3f}, "
          f"cells/lambda_De={cfg.debye/cfg.d_r:.1f}")
    print(f"  theory: I_th_e={cfg.I_th_e*1e6:.5f} uA, I_th_i={cfg.I_th_i*1e9:.3f} nA"
          + (f", chi={cfg.chi:.2f} -> I_OML={cfg.I_oml_e*1e6:.4f} uA"
             if cfg.bias > 0 else ""))
    print(f"  dt={cfg.time_step:.2e} s, steps={cfg.max_steps} "
          f"-> t_end={cfg.max_steps*cfg.time_step*1e6:.2f} us")
    print(f"  output: {run.dir}")
    print("=" * 72)


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="current_collection PIC run")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--scenario", default=None,
                    help="unused (single-run stage); rejected if given")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config, scenario=args.scenario)

    run = lc.begin_run(
        run_root=OUTPUTS_ROOT, stage_id=cfg.stage_id,
        config=cfg.effective_config(), random_seed=cfg.random_seed,
        expected_final_iteration=cfg.max_steps,
        source_files=[CASE_DIR / "simulation.py", CASE_DIR / "helpers.py"],
        provenance={"warpx_version": _warpx_version()})
    print(f"RUN_ID={run.run_id}", flush=True)
    banner(cfg, run)

    try:
        sim = build_simulation(cfg, run)
        sim.step(cfg.max_steps)
        lc.complete_run(
            run,
            expected_artifacts=["fields/*.h5", "reducedfiles/*.txt"],
            observed_final_iteration=observed_final_iteration(run))
    except BaseException as exc:  # noqa: BLE001
        lc.fail_run(run, exc)
        raise
    print(f"done: {cfg.max_steps} steps -> {run.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
