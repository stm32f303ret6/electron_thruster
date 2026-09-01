#!/usr/bin/env python3
"""characterization.transverse_b_numerics: single test electrons in uniform
E and B on the transverse-B measurement grid (WarpX PICMI, 3D electrostatic).

One scenario per process.  The particle's mean position and momentum are
written every step by the BeamRelevant reduced diagnostic; analyze.py fits
the gyration (omega_c, r_g, energy conservation) and the E x B drift against
the closed forms.  Periodic in x and y, Dirichlet in z (the z-face potentials
impose the uniform Ez of the drift scenario; 0 V otherwise).

    python simulation.py --scenario gyro_10x
    python analyze.py --runs outputs/<gyro_1x> outputs/<gyro_10x> outputs/<exb_10x>

Run ONE WarpX case at a time on this machine.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

CASE_DIR = Path(__file__).resolve().parent
_pic_root = CASE_DIR
while not (_pic_root / "ladder_contract.py").is_file():
    _pic_root = _pic_root.parent
sys.path.insert(0, str(_pic_root))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc  # noqa: E402
from helpers import SPECIES, STAGE_ID, Config, load_config  # noqa: E402

DEFAULT_CONFIG = CASE_DIR / "config.yaml"
OUTPUTS_ROOT = CASE_DIR / "outputs"
RANDOM_SEED = 42
MAX_GRID_SIZE = 128
BLOCKING_FACTOR = 8


def _warpx_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("pywarpx")
    except Exception:  # noqa: BLE001
        return None


def build_simulation(cfg: Config, run: lc.Run):
    from pywarpx import amrex as amrex_params
    from pywarpx import picmi

    amrex_params.the_arena_init_size = cfg.gpu_arena_bytes

    grid = picmi.Cartesian3DGrid(
        number_of_cells=[cfg.nx, cfg.ny, cfg.nz],
        lower_bound=[-cfg.xmax, -cfg.ymax, cfg.zmin],
        upper_bound=[cfg.xmax, cfg.ymax, cfg.zmax],
        lower_boundary_conditions=["periodic", "periodic", "dirichlet"],
        upper_boundary_conditions=["periodic", "periodic", "dirichlet"],
        lower_boundary_conditions_particles=["periodic", "periodic", "absorbing"],
        upper_boundary_conditions_particles=["periodic", "periodic", "absorbing"],
        warpx_potential_lo_z=0.0, warpx_potential_hi_z=cfg.phi_hi_z,
        warpx_max_grid_size=MAX_GRID_SIZE, warpx_blocking_factor=BLOCKING_FACTOR)
    solver = picmi.ElectrostaticSolver(
        grid=grid, method="Multigrid", required_precision=1e-8,
        maximum_iterations=500, warpx_self_fields_verbosity=0)

    # one electron, unit weight (its own field is negligible), launched along +z
    dist = picmi.ParticleListDistribution(
        x=[cfg.x0], y=[cfg.y0], z=[cfg.z0],
        ux=[0.0], uy=[0.0], uz=[cfg.gamma0 * cfg.v0], weight=[1.0])
    electron = picmi.Species(name=SPECIES, particle_type="electron",
                             initial_distribution=dist)

    sim = picmi.Simulation(
        solver=solver, time_step_size=cfg.dt, max_steps=cfg.max_steps,
        particle_shape=1, warpx_random_seed=RANDOM_SEED,
        warpx_used_inputs_file=str(run.diags_dir / "used_inputs.txt"))
    sim.add_applied_field(picmi.ConstantAppliedField(Bx=cfg.Bx_T))
    sim.add_species(electron, layout=None)
    sim.add_diagnostic(picmi.ReducedDiagnostic(
        diag_type="BeamRelevant", name="beam_relevant", species=electron, period=1,
        path=f"{run.diags_dir / 'reducedfiles'}/"))
    return sim


def observed_final_iteration(run: lc.Run) -> int | None:
    path = run.diags_dir / "reducedfiles" / "beam_relevant.txt"
    if not path.exists():
        return None
    data = np.atleast_2d(np.loadtxt(path))
    return int(data[-1, 0]) if data.size else None


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="transverse-B numerics test particle")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--scenario", default=None)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config, scenario=args.scenario)
    run = lc.begin_run(
        run_root=OUTPUTS_ROOT, stage_id=STAGE_ID, config=cfg.effective_config(),
        scenario=cfg.scenario, study_config=cfg.study_config(),
        random_seed=RANDOM_SEED, expected_final_iteration=cfg.max_steps,
        source_files=[CASE_DIR / "simulation.py", CASE_DIR / "helpers.py"],
        provenance={"warpx_version": _warpx_version()})
    print(f"RUN_ID={run.run_id}", flush=True)
    print(f"TRANSVERSE-B NUMERICS [{run.run_id}] scenario={cfg.scenario}: "
          f"Bx={cfg.Bx_T*1e6:.1f} uT Ez={cfg.Ez_V_per_m:g} V/m KE={cfg.ke_eV:g} eV "
          f"r_g={cfg.r_gyro*1e3:.2f} mm T_c={cfg.T_c*1e9:.2f} ns omega_c*dt={cfg.omega_c*cfg.dt:.2e} "
          f"steps={cfg.max_steps} (t_run={cfg.t_run*1e9:.1f} ns) v_ExB={cfg.v_exb:.3e} m/s",
          flush=True)
    try:
        sim = build_simulation(cfg, run)
        sim.step(cfg.max_steps)
        lc.complete_run(run, expected_artifacts=["reducedfiles/beam_relevant.txt"],
                        observed_final_iteration=observed_final_iteration(run))
    except BaseException as exc:  # noqa: BLE001
        lc.fail_run(run, exc)
        raise
    print(f"done: {cfg.max_steps} steps -> {run.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
