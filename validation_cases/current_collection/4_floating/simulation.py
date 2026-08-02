#!/usr/bin/env python3
"""collector.floating: passive sphere floating via the charge pump (WarpX).

The complete PIC model: the collector rungs' conducting sphere in the ambient
capstone plasma (bulk fill + one-sided Maxwellian flux from the three open
faces -- the deck is the thermal stage's, duplicated per the ladder's
convention), with the sphere's potential computed every step by the chipsat
capstone's charge-pump mechanism, transcribed from chipsat/simulation.py:

  - the EB starts at a uniform 1 V so the init solve calibrates the
    self-capacitance C by Gauss' law on the domain faces;
  - every step, the scraped-this-step weights of both species are read from
    the particle boundary buffers, dQ = e*(w_i - w_e) accumulates into Q,
    and ``set_potential_on_eb`` rewrites phi = phi_init + Q/C;
  - a CSV ledger (floating_log.csv) records windowed phi, Q, I_e, I_i.

With no beam, the pump must drive the sphere to the analytic floating
potential (helpers.py: thermal-ion -0.360 V, OML-ion -0.213 V); analyze.py
gates the bracket, the current balance, the C calibration, and the
ledger-vs-dump charge consistency.

Each execution creates a fresh, immutable run directory under ``outputs/``.

    python simulation.py                 # uses ./config.yaml
    python analyze.py --run outputs/<run-id> --policy acceptance.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parents[1]))  # validation_cases/ (ladder_contract)
sys.path.insert(0, str(CASE_DIR))             # this stage's helpers.py

import ladder_contract as lc  # noqa: E402
from helpers import ELECTRONS, IONS, STAGE_ID, Config, load_config  # noqa: E402

DEFAULT_CONFIG = CASE_DIR / "config.yaml"
OUTPUTS_ROOT = CASE_DIR / "outputs"

E = scc.e
EPS0 = scc.epsilon_0


class FloatingProbeDiverged(RuntimeError):
    """phi went non-finite: the pump lost its footing (run is FAILED)."""


def _warpx_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("pywarpx")
    except Exception:  # noqa: BLE001
        return None


# ======================================================================
# charge pump (chipsat/simulation.py, transcribed for a one-node sphere)
# ======================================================================

def _asnumpy(a):
    """Pull a pywarpx array (CuPy on GPU, NumPy on CPU) to host NumPy."""
    get = getattr(a, "get", None)
    return get() if callable(get) else np.asarray(a)


def _get_field(sim, name: str, level: int = 0):
    """Fetch a registered MultiFab as an indexable wrapper (26.5 fallback)."""
    registry = sim.fields
    get = getattr(registry, "get", None)
    if callable(get):
        return get(name, level=level)
    from pywarpx import fields as f
    if name == "phi_fp":
        return f.PhiFPWrapper(level)
    if name == "rho_fp":
        return f.RhoFPWrapper(level)
    raise KeyError(f"no wrapper fallback for MultiFab {name!r}")


def self_capacitance(sim, rmax: float, nz: int) -> float:
    """Float-node self-capacitance via Gauss' law on the domain faces, valid
    while the EB is held at a uniform 1 V (chipsat/simulation.py, verbatim)."""
    warpx = sim.extension.warpx
    rho = np.asarray(_get_field(sim, "rho_fp")[:, :])
    phi = np.asarray(_get_field(sim, "phi_fp")[:, :])
    dr, dz = warpx.Geom(lev=0).data().CellSize()
    nr = phi.shape[0]
    r = np.linspace(0.0, rmax, nr, endpoint=False) + rmax / (2 * nr)
    face_z0 = 2 * np.pi / dz * ((phi[:, 0] - phi[:, 1]) * r).sum() * dr
    face_zend = 2 * np.pi / dz * ((phi[:, -1] - phi[:, -2]) * r).sum() * dr
    face_rend = 2 * np.pi / dr * ((phi[-1, :] - phi[-2, :]) * rmax).sum() * dz
    grad_phi_integral = face_z0 + face_zend + face_rend
    rho_integral = ((rho[1:nr - 1, 1:nz - 1] * r[1:nr - 1, np.newaxis]).sum()
                    * 2 * np.pi * dr * dz)
    return float(-rho_integral - EPS0 * grad_phi_integral)


class FloatingProbe:
    """The self-consistent charge pump that owns the sphere's potential."""

    def __init__(self, sim, cfg: Config):
        self.sim = sim
        self.phi0 = cfg.phi_init
        self.rmax, self.nz = cfg.r_max, cfg.n_z
        self.C: float | None = None
        self.Q = 0.0
        self.phi = self.phi0
        self.calibrated = False

    def calibrate_fresh(self) -> None:
        """Measure C from the uniform-1 V init solve, then impose phi_init."""
        warpx = self.sim.extension.warpx
        self.C = self_capacitance(self.sim, self.rmax, self.nz)
        self.phi = self.phi0
        warpx.set_potential_on_eb(f"{self.phi:.10g}")
        self.calibrated = True

    def step(self, w_e_coll: float, w_i_coll: float, step_count: int) -> float:
        """Advance the pump one step and rewrite the EB potential.

        The capstone's ambient accounting, verbatim minus the beam terms:
        collecting an electron adds -e, collecting an ion adds +e."""
        dQ = -E * w_e_coll + E * w_i_coll
        self.Q += dQ
        phi_new = self.phi0 + self.Q / self.C
        if not np.isfinite(phi_new):
            raise FloatingProbeDiverged(
                f"phi is not finite at step {step_count} "
                f"(Q={self.Q:.3e} C, C={self.C:.3e} F, dQ={dQ:.3e})")
        self.phi = phi_new
        self.sim.extension.warpx.set_potential_on_eb(f"{self.phi:.10g}")
        return self.phi


class PumpObserver:
    """Single reader of the scrape buffers; writes the CSV ledger."""

    CSV_HEADER = "step,t,phi_V,Q_C,I_e_A,I_i_A\n"

    def __init__(self, cfg: Config, diags_dir: Path):
        from pywarpx.particle_containers import ParticleBoundaryBufferWrapper

        self.dt = cfg.time_step
        self.log_every = cfg.log_every
        self.buf = ParticleBoundaryBufferWrapper()
        self._acc_e = 0.0
        self._acc_i = 0.0
        self._acc_steps = 0
        self.logf = open(diags_dir / "floating_log.csv", "w")
        self.logf.write(self.CSV_HEADER)
        self.logf.flush()

    def _scraped_w(self, species: str) -> float:
        """This-step scraped weight at the EB, concatenated over tiles."""
        try:
            arrs = self.buf.get_particle_scraped_this_step(species, "eb", "w", 0)
        except Exception:  # noqa: BLE001  (species/boundary may not exist yet)
            return 0.0
        return float(sum(_asnumpy(a).sum() for a in arrs)) if arrs else 0.0

    def collect(self) -> tuple[float, float]:
        w_e = self._scraped_w(ELECTRONS)
        w_i = self._scraped_w(IONS)
        self._acc_e += w_e
        self._acc_i += w_i
        self._acc_steps += 1
        return w_e, w_i

    def log(self, step_count: int, phi: float, Q: float,
            force: bool = False) -> bool:
        """One averaged row per full window; ``force=True`` flushes a final
        partial window so the ledger covers every step (the charge-consistency
        gate compares it against the openPMD dumps)."""
        if self._acc_steps < self.log_every and not (force and self._acc_steps > 0):
            return False
        win = self._acc_steps * self.dt
        t = step_count * self.dt
        self.logf.write(
            f"{step_count},{t:.6e},{phi:.6e},{Q:.6e},"
            f"{E * self._acc_e / win:.6e},{E * self._acc_i / win:.6e}\n")
        self.logf.flush()
        self._acc_e = self._acc_i = 0.0
        self._acc_steps = 0
        return True

    def close(self) -> None:
        self.logf.close()


class Coordinator:
    def __init__(self, cfg: Config, pump: FloatingProbe, obs: PumpObserver):
        self.cfg = cfg
        self.pump = pump
        self.obs = obs
        self.step_count = 0
        self.ready = False

    def on_init_esolve(self) -> None:
        self.pump.calibrate_fresh()
        self.ready = True

    def on_esolve(self) -> None:
        if not self.ready:
            return
        self.step_count += 1
        w_e, w_i = self.obs.collect()
        self.pump.step(w_e, w_i, self.step_count)

    def on_step(self) -> None:
        if not self.ready:
            return
        self.obs.log(self.step_count, self.pump.phi, self.pump.Q)


# ======================================================================
# deck (current_collection thermal stage, duplicated; EB starts at 1 V)
# ======================================================================

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
        # The floating potential is O(0.1 V) on grounded walls: give MLMG an
        # absolute criterion so near-converged re-solves cannot fail.
        warpx_absolute_tolerance=1.0e-3,
        maximum_iterations=500,
        warpx_self_fields_verbosity=0,
    )

    # Conducting sphere at the origin, starting at a uniform 1 V so the init
    # solve calibrates C; the pump rewrites the potential every step after.
    embedded_boundary = picmi.EmbeddedBoundary(
        implicit_function="-(x**2+y**2+z**2-a**2)",
        potential=1.0,
        a=cfg.probe_radius,
    )

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
    print(f"FLOATING SPHERE [{run.run_id}] {cfg.stage_id}: sphere a="
          f"{cfg.probe_radius * 1e3:.2f} mm, potential FLOATS (charge pump)")
    print(f"  plasma: n0={cfg.n0:.3e} m^-3, kTe={cfg.kTe_eV*1e3:.1f} meV, "
          f"mi={cfg.ion_mass_me:.0f} me;  lambda_De={cfg.debye*1e3:.3f} mm "
          f"-> a/lambda_De={cfg.a_over_debye:.3f}")
    print(f"  theory: phi_f(thermal-ion)={cfg.phi_float_thermal_ion:+.3f} V, "
          f"phi_f(OML-ion)={cfg.phi_float_oml_ion:+.3f} V; "
          f"C_analytic={cfg.analytic_capacitance*1e15:.2f} fF")
    print(f"  dt={cfg.time_step:.2e} s, steps={cfg.max_steps} "
          f"-> t_end={cfg.max_steps*cfg.time_step*1e6:.2f} us")
    print(f"  output: {run.dir}")
    print("=" * 72)
    sys.stdout.flush()


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="collector.floating PIC run")
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
        from pywarpx.callbacks import (
            installafterEsolve, installafterInitEsolve, installafterstep)

        sim = build_simulation(cfg, run)
        pump = FloatingProbe(sim, cfg)
        obs = PumpObserver(cfg, run.diags_dir)
        coord = Coordinator(cfg, pump, obs)

        installafterInitEsolve(coord.on_init_esolve)
        installafterEsolve(coord.on_esolve)
        installafterstep(coord.on_step)

        sim.step(cfg.max_steps)

        print(f"[calib] C = {pump.C*1e15:.3f} fF "
              f"(analytic 4*pi*eps0*a = {cfg.analytic_capacitance*1e15:.3f} fF); "
              f"final phi = {pump.phi:+.4f} V")
        # flush the final partial CSV window, record the calibration, close
        obs.log(coord.step_count, pump.phi, pump.Q, force=True)
        obs.close()
        lc.write_json_atomic(run.diags_dir / "pump.json", {
            "C_measured_F": pump.C,
            "C_analytic_F": cfg.analytic_capacitance,
            "phi_init_V": cfg.phi_init,
            "final_phi_V": pump.phi,
            "final_Q_C": pump.Q,
        })
        lc.complete_run(
            run,
            expected_artifacts=["fields/*.h5", "floating_log.csv", "pump.json",
                                "reducedfiles/*.txt"],
            observed_final_iteration=observed_final_iteration(run))
    except BaseException as exc:  # noqa: BLE001 -- record then re-raise
        lc.fail_run(run, exc)
        raise
    print(f"done: {cfg.max_steps} steps -> {run.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
