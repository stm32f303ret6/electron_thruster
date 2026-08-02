#!/usr/bin/env python3
"""capstone.two_node_laplace: the chipsat can's two-node EB in vacuum (WarpX).

The complete deck: the capstone's conducting-can embedded boundary on the
capstone's grid, ZERO particles, BODY pinned at phi_body and CATHODE at
phi_body + cathode_offset via the same piecewise potential string and the
same ``set_potential_on_eb`` per-step rewrite the capstone's charge pump
uses.  With no space charge every solve is Laplace's equation; analyze.py
gates the exact properties (assigned surface values, the maximum principle,
agreement with an independent solver, rewrite idempotency).

The EB starts at a uniform 1 V (mirroring the capstone's calibration solve);
the after-init callback imposes the two-node string, so field dumps at
iterations >= 1 hold the two-node solution.

Each execution creates a fresh, immutable run directory under ``outputs/``.

    python simulation.py                 # uses ./config.yaml
    python analyze.py --run outputs/<run-id> --policy acceptance.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parents[0]))  # validation_cases/ (ladder_contract)
sys.path.insert(0, str(CASE_DIR))             # this stage's helpers.py

import ladder_contract as lc  # noqa: E402
from helpers import STAGE_ID, Config, Geometry, load_config  # noqa: E402

DEFAULT_CONFIG = CASE_DIR / "config.yaml"
OUTPUTS_ROOT = CASE_DIR / "outputs"
RANDOM_SEED = 42  # recorded for the manifest; nothing stochastic runs here


def _warpx_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("pywarpx")
    except Exception:  # noqa: BLE001
        return None


def build_simulation(cfg: Config, geom: Geometry, run: lc.Run):
    """Assemble and return the PICMI Simulation (WarpX is not stepped here)."""
    from pywarpx import picmi

    grid = picmi.CylindricalGrid(
        number_of_cells=[cfg.nr, cfg.nz], n_azimuthal_modes=1,
        lower_bound=[0.0, cfg.zmin], upper_bound=[cfg.rmax, cfg.zmax],
        lower_boundary_conditions=["none", "dirichlet"],
        upper_boundary_conditions=["dirichlet", "dirichlet"],
        lower_boundary_conditions_particles=["none", "absorbing"],
        upper_boundary_conditions_particles=["absorbing", "absorbing"],
        warpx_max_grid_size=1024)
    solver = picmi.ElectrostaticSolver(
        grid=grid, method="Multigrid", required_precision=1e-6,
        # After the first two-node solve the field no longer changes, so the
        # relative criterion can never be met on a re-solve (the collector
        # stages hit the same wall at 0 V); give MLMG an absolute criterion.
        # Tight (1e-5) so re-solves cannot wander at the mV level -- the
        # rewrite-idempotency gate is 1 mV.
        warpx_absolute_tolerance=1.0e-5,
        maximum_iterations=500, warpx_self_fields_verbosity=0)
    # Start at a uniform 1 V exactly like the capstone's calibration solve;
    # the after-init callback then imposes the two-node string.
    embedded_boundary = picmi.EmbeddedBoundary(
        implicit_function=geom.implicit_function(), potential=1.0)

    sim = picmi.Simulation(
        solver=solver, time_step_size=cfg.dt, max_steps=cfg.max_steps,
        particle_shape=1, warpx_embedded_boundary=embedded_boundary,
        warpx_random_seed=RANDOM_SEED,
        warpx_used_inputs_file=str(run.diags_dir / "used_inputs.txt"))

    sim.add_diagnostic(picmi.FieldDiagnostic(
        name="fields", grid=grid, period=1, data_list=["phi"],
        warpx_format="openpmd", warpx_openpmd_backend="h5",
        write_dir=str(run.diags_dir)))
    return sim


def observed_final_iteration(run: lc.Run) -> int | None:
    iters = []
    for p in (run.diags_dir / "fields").glob("*.h5"):
        m = re.findall(r"\d+", p.stem)
        if m:
            iters.append(int(m[-1]))
    return max(iters) if iters else None


def banner(cfg: Config, geom: Geometry, run: lc.Run) -> None:
    print("=" * 72)
    print(f"TWO-NODE LAPLACE [{run.run_id}] {STAGE_ID}  (RZ, vacuum, no particles)")
    print(f"  nodes: BODY={cfg.phi_body:+.1f} V  CATHODE={cfg.phi_cathode:+.1f} V "
          f"(offset {cfg.cathode_offset:+.0f} V)")
    print("  geometry: " + geom.describe())
    print(f"  grid: r in [0,{cfg.rmax*1e3:.2f}] mm  z in [{cfg.zmin*1e3:.2f},"
          f"{cfg.zmax*1e3:.2f}] mm  {cfg.nr}x{cfg.nz}  dx={cfg.dx*1e3:.3f} mm")
    print(f"  steps: {cfg.max_steps} (re-imposing the EB string each step)")
    print(f"  output: {run.dir}")
    print("=" * 72)
    sys.stdout.flush()


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="two-node vacuum Laplace run")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--scenario", default=None,
                    help="unused (single-run stage); rejected if given")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config, scenario=args.scenario)
    geom = cfg.geometry()

    run = lc.begin_run(
        run_root=OUTPUTS_ROOT, stage_id=STAGE_ID, config=cfg.effective_config(),
        random_seed=RANDOM_SEED, expected_final_iteration=cfg.max_steps,
        source_files=[CASE_DIR / "simulation.py", CASE_DIR / "helpers.py"],
        provenance={"warpx_version": _warpx_version()})
    print(f"RUN_ID={run.run_id}", flush=True)
    banner(cfg, geom, run)

    try:
        from pywarpx.callbacks import installafterEsolve, installafterInitEsolve

        sim = build_simulation(cfg, geom, run)
        eb_string = geom.potential_string(cfg.phi_body, cfg.phi_cathode)

        def impose_two_node() -> None:
            # The capstone's per-step mechanism, verbatim: rewrite the piecewise
            # EB potential so the NEXT solve uses the two-node values.
            sim.extension.warpx.set_potential_on_eb(eb_string)

        installafterInitEsolve(impose_two_node)
        installafterEsolve(impose_two_node)

        sim.step(cfg.max_steps)
        lc.complete_run(
            run,
            expected_artifacts=["fields/*.h5"],
            observed_final_iteration=observed_final_iteration(run))
    except BaseException as exc:  # noqa: BLE001 -- record then re-raise
        lc.fail_run(run, exc)
        raise
    print(f"done: {cfg.max_steps} steps -> {run.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
