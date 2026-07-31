#!/usr/bin/env python3
"""
Spherical Langmuir probe (radius 5 mm) at a fixed potential of +10 V,
immersed in ionospheric plasma, simulated with WarpX in RZ geometry.

The plasma parameters (ne, Te, Ti) are read from the plasma_environment.csv
dataset; --case selects the row with the minimum or maximum electron density.
The probe is a conducting sphere modeled as an embedded boundary held at a
fixed potential (no charging feedback: collected electrons do NOT change the
potential). The ambient plasma is maintained by thermal (Maxwellian) flux
injection from the open domain boundaries.

Diagnostics (all openPMD HDF5):
  - BoundaryScraping: particles absorbed by the probe (-> collected current)
  - FieldDiagnostic: phi, rho, rho_electrons, rho_ions, Er, Ez
  - ReducedDiagnostic ParticleNumber: total physical weight per species (-> ne(t))

Usage:
  python run_probe.py --case min          # lowest-density CSV row
  python run_probe.py --case max          # highest-density CSV row
"""

import argparse
import csv
import json
import math
import os
import re
import sys

import numpy as np
from scipy import constants as scc

from pywarpx import picmi

DEFAULT_CSV = "/home/rsc/Desktop/repos/warpequisd/build/bin/dataset/plasma_environment.csv"

PROBE_RADIUS = 0.005  # m (5 mm sphere)
PROBE_POTENTIAL = 10.0  # V, fixed (no charging feedback)
M_OXYGEN = 15.999 * scc.atomic_mass  # O+ ion mass [kg]

# Per-case numerical setup (dr = dz = 0.5 mm = probe_radius/10 in both cases)
CASE_SETUP = {
    "min": dict(
        rmax=0.16, zmax=0.16, nr=320, nz=640,
        max_steps=200_000,          # 20 us at dt = 1e-10 s
        scrape_period=5_000,
        field_period=10_000,
        ppc=16,
    ),
    "max": dict(
        rmax=0.10, zmax=0.10, nr=200, nz=400,
        max_steps=200_000,          # 20 us at dt = 1e-10 s
        scrape_period=2_000,
        field_period=4_000,
        ppc=32,
    ),
}
DT = 1.0e-10  # s
# Checkpoint cadence; must be a multiple of every scrape_period so that the
# (non-checkpointed) scrape buffer is always empty when a checkpoint is written.
CHECKPOINT_PERIOD = 20_000


def select_csv_row(csv_path, case):
    """Return (row_dict, csv_line_number) for the min/max ne_cm-3 row."""
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    ne = np.array([float(r["ne_cm-3"]) for r in rows])
    idx = int(np.argmin(ne)) if case == "min" else int(np.argmax(ne))
    # +2: 1-based counting plus the header line
    return rows[idx], idx + 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=["min", "max"])
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--max-steps", type=int, default=None,
                        help="override the default number of steps")
    parser.add_argument("--ppc", type=int, default=None,
                        help="bulk macroparticles per cell per species")
    parser.add_argument("--restart", default=None, metavar="CHK_DIR",
                        help="restart from a checkpoint directory "
                             "(e.g. diags_min/chk0120000)")
    # --- scaling knobs for the high-potential campaign (defaults = baseline) ---
    parser.add_argument("--potential", type=float, default=PROBE_POTENTIAL,
                        help="probe potential in V (default 10)")
    parser.add_argument("--ramp-us", type=float, default=None,
                        help="linearly ramp the probe potential from 0 to "
                             "--potential over this many microseconds")
    parser.add_argument("--dt", type=float, default=DT,
                        help="timestep in s (validate convergence if larger "
                             "than the CFL-safe default 1e-10)")
    parser.add_argument("--ion-mass-me", type=float, default=None,
                        help="use a fictitious ion with this mass in electron "
                             "masses instead of O+ (reduced-mass scaling; "
                             "shortens ion relaxation by sqrt(29164/M))")
    parser.add_argument("--rmax", type=float, default=None,
                        help="override domain radius in m (cell size kept)")
    parser.add_argument("--zmax", type=float, default=None,
                        help="override domain half-length in m (cell size kept)")
    parser.add_argument("--dx", type=float, default=None,
                        help="override cell size dr=dz in m (default 0.5 mm). "
                             "Coarsen for the large sheaths at high potential.")
    parser.add_argument("--bz", type=float, default=0.0,
                        help="uniform external magnetic field along z in Tesla "
                             "(e.g. 26e-6 for the geomagnetic field; preserves "
                             "RZ axisymmetry)")
    parser.add_argument("--tag", default="",
                        help="suffix for the output directory, e.g. '_m400' -> "
                             "diags_<case><tag>/ (keeps validation runs separate "
                             "from the baseline)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print derived parameters and exit")
    args = parser.parse_args()

    setup = CASE_SETUP[args.case]
    if args.max_steps is not None:
        setup["max_steps"] = args.max_steps
    if args.ppc is None:
        args.ppc = setup["ppc"]

    row, csv_line = select_csv_row(args.csv, args.case)

    # ----- plasma parameters from the CSV row -----
    ne = float(row["ne_cm-3"]) * 1.0e6  # m^-3
    Te = float(row["Te_K"])             # K
    Ti = float(row["Ti_K"])             # K
    V_probe = args.potential
    dt = args.dt
    m_ion = (args.ion_mass_me * scc.m_e if args.ion_mass_me is not None
             else M_OXYGEN)

    vth_e = math.sqrt(scc.k * Te / scc.m_e)
    vth_i = math.sqrt(scc.k * Ti / m_ion)
    flux_e = ne * vth_e / math.sqrt(2.0 * math.pi)  # one-sided Maxwellian flux
    flux_i = ne * vth_i / math.sqrt(2.0 * math.pi)

    debye = math.sqrt(scc.epsilon_0 * scc.k * Te / (ne * scc.e**2))
    wpe = math.sqrt(ne * scc.e**2 / (scc.m_e * scc.epsilon_0))
    kTe_eV = scc.k * Te / scc.e
    oml_current = (scc.e * flux_e * 4.0 * math.pi * PROBE_RADIUS**2
                   * (1.0 + V_probe / kTe_eV))

    # ----- grid (cell size from the per-case defaults; domain overridable) -----
    if args.dx is not None:
        dr = dz = args.dx
    else:
        dr = setup["rmax"] / setup["nr"]
        dz = 2.0 * setup["zmax"] / setup["nz"]
    rmax = args.rmax if args.rmax is not None else setup["rmax"]
    zmax = args.zmax if args.zmax is not None else setup["zmax"]
    nr = int(round(rmax / dr / 8.0)) * 8       # blocking factor 8
    nz = int(round(2.0 * zmax / dz / 8.0)) * 8
    rmax, zmax = nr * dr, nz * dz / 2.0

    # ----- sanity checks on the numerics -----
    v_fall = math.sqrt(2.0 * scc.e * V_probe / scc.m_e)  # full-bias electron
    vmax = v_fall + 4.0 * vth_e
    cfl = dt * vmax / min(dr, dz)
    if cfl >= 0.5:
        print(f"WARNING: dt*vmax/dx = {cfl:.2f} >= 0.5 — fast electrons near "
              "the probe cross >0.5 cell/step; validate dt convergence.")
    assert cfl < 4.0, f"dt far too large: dt*vmax/dx = {cfl:.2f}"
    assert max(dr, dz) < debye, (
        f"grid does not resolve the Debye length: dx={max(dr, dz)} >= {debye}")

    # flux-injection macroparticles per boundary cell per step, chosen so the
    # injected macro-weight matches the bulk macro-weight (nu = G*dt*ppc/(n*dx))
    nu_e = flux_e * dt * args.ppc / (ne * dz)
    nu_i = flux_i * dt * args.ppc / (ne * dz)

    print("=" * 70)
    print(f"Langmuir probe case '{args.case}': CSV line {csv_line} "
          f"(data row {csv_line - 1}, 1-based line count incl. header)")
    print(f"  datetime  = {row['datetime']}   alt = {float(row['alt_km']):.1f} km")
    print(f"  ne        = {row['ne_cm-3']} cm^-3 = {ne:.4e} m^-3")
    print(f"  Te        = {Te:.2f} K ({kTe_eV * 1e3:.2f} meV)")
    print(f"  Ti        = {Ti:.2f} K")
    ion_label = ("O+" if args.ion_mass_me is None
                 else f"fake ion {args.ion_mass_me:.0f} m_e")
    print(f"  V_probe   = {V_probe} V"
          + (f" (ramped over {args.ramp_us} us)" if args.ramp_us else " (fixed)"))
    print(f"  vth_e     = {vth_e:.4e} m/s   vth_i({ion_label}) = {vth_i:.1f} m/s")
    print(f"  lambda_D  = {debye * 1e3:.3f} mm   wpe = {wpe:.3e} rad/s "
          f"(wpe*dt = {wpe * dt:.2e})")
    print(f"  e*phi/kTe = {V_probe / kTe_eV:.1f}")
    print(f"  OML electron current bound = {oml_current * 1e6:.2f} uA")
    print(f"  domain: r in [0, {rmax}] m, z in [-{zmax}, {zmax}] m, "
          f"grid {nr}x{nz} (dr={dr * 1e3:.2f} mm, dz={dz * 1e3:.2f} mm)")
    print(f"  dt = {dt:.1e} s, steps = {setup['max_steps']} "
          f"-> t_end = {setup['max_steps'] * dt * 1e6:.2f} us, CFL = {cfl:.2f}")
    print(f"  bulk ppc = {args.ppc}/species, flux ppc/step: "
          f"e- {nu_e:.3e}, O+ {nu_i:.3e}")
    if args.bz:
        r_ce = scc.m_e * vth_e / (scc.e * abs(args.bz))
        print(f"  B_z = {args.bz:.3e} T  -> thermal e- gyroradius = "
              f"{r_ce * 1e3:.2f} mm (compare to sheath ~cm)")
    print(f"  output -> diags_{args.case}{args.tag}/")
    print("=" * 70)
    sys.stdout.flush()
    if args.dry_run:
        return

    outdir = f"diags_{args.case}{args.tag}"

    # Write run metadata so the analysis knows the (possibly non-default) domain,
    # timestep, ramp, etc. without hardcoded assumptions.
    os.makedirs(outdir, exist_ok=True)
    with open(f"{outdir}/run_meta.json", "w") as f:
        json.dump({
            "case": args.case, "csv_line": csv_line,
            "ne": ne, "Te": Te, "Ti": Ti,
            "V_probe": V_probe, "ramp_us": args.ramp_us,
            "dt": dt, "ion_mass_me": args.ion_mass_me, "bz": args.bz,
            "rmax": rmax, "zmax": zmax, "nr": nr, "nz": nz,
            "probe_radius": PROBE_RADIUS, "kTe_eV": kTe_eV,
            "oml_current": oml_current, "debye": debye,
            "max_steps": setup["max_steps"], "ppc": args.ppc,
        }, f, indent=2)

    # ----- grid and solver -----
    grid = picmi.CylindricalGrid(
        number_of_cells=[nr, nz],
        n_azimuthal_modes=1,
        lower_bound=[0.0, -zmax],
        upper_bound=[rmax, zmax],
        lower_boundary_conditions=["none", "dirichlet"],
        upper_boundary_conditions=["dirichlet", "dirichlet"],
        lower_boundary_conditions_particles=["none", "absorbing"],
        upper_boundary_conditions_particles=["absorbing", "absorbing"],
        warpx_max_grid_size=1024,
    )

    solver = picmi.ElectrostaticSolver(
        grid=grid,
        method="Multigrid",
        required_precision=1e-5,   # 0.1 mV on a 10 V problem; thermal scale is ~60 mV
        maximum_iterations=500,
        warpx_self_fields_verbosity=0,
    )

    # Conducting sphere at the origin held at a fixed potential. In RZ the
    # parser is evaluated with (x->r, y->0, z->z), so this is a true sphere.
    if args.ramp_us:
        # quasi-static linear ramp 0 -> V_probe (the parser supports min())
        eb_potential = f"{V_probe}*min(t/{args.ramp_us * 1e-6}, 1.0)"
    else:
        eb_potential = V_probe
    embedded_boundary = picmi.EmbeddedBoundary(
        implicit_function="-(x**2+y**2+z**2-radius**2)",
        potential=eb_potential,
        radius=PROBE_RADIUS,
    )

    # ----- species: initial Maxwellian plasma + reservoir flux injection -----
    def make_species(name, vth, flux, kw):
        bulk = picmi.UniformDistribution(
            density=ne, rms_velocity=[vth, vth, vth])
        flux_r = picmi.UniformFluxDistribution(
            flux=flux, surface_flux_position=rmax,
            flux_normal_axis="r", flux_direction=-1,
            gaussian_flux_momentum_distribution=True,
            rms_velocity=[vth, vth, vth])
        flux_zlo = picmi.UniformFluxDistribution(
            flux=flux, surface_flux_position=-zmax,
            flux_normal_axis="z", flux_direction=+1,
            gaussian_flux_momentum_distribution=True,
            rms_velocity=[vth, vth, vth])
        flux_zhi = picmi.UniformFluxDistribution(
            flux=flux, surface_flux_position=zmax,
            flux_normal_axis="z", flux_direction=-1,
            gaussian_flux_momentum_distribution=True,
            rms_velocity=[vth, vth, vth])
        return picmi.Species(
            name=name,
            initial_distribution=[bulk, flux_r, flux_zlo, flux_zhi],
            warpx_save_particles_at_eb=1, **kw)

    electrons = make_species("electrons", vth_e, flux_e,
                             kw=dict(particle_type="electron"))
    if args.ion_mass_me is None:
        ion_kw = dict(particle_type="O", charge_state=1)
    else:
        ion_kw = dict(charge=scc.e, mass=m_ion)
    ions = make_species("ions", vth_i, flux_i, kw=ion_kw)

    # ----- diagnostics (openPMD HDF5) -----
    scrape_diag = picmi.ParticleBoundaryScrapingDiagnostic(
        name="scrape",
        period=setup["scrape_period"],
        species=[electrons, ions],
        warpx_format="openpmd",
        warpx_openpmd_backend="h5",
        warpx_dump_last_timestep=True,
        write_dir=outdir,
    )
    field_diag = picmi.FieldDiagnostic(
        name="fields",
        grid=grid,
        period=setup["field_period"],
        data_list=["Er", "Ez", "phi", "rho", "rho_electrons", "rho_ions"],
        warpx_format="openpmd",
        warpx_openpmd_backend="h5",
        write_dir=outdir,
    )
    pnum_diag = picmi.ReducedDiagnostic(
        diag_type="ParticleNumber",
        name="particle_number",
        period=100,
        path=f"{outdir}/reducedfiles/",
    )
    checkpoint = picmi.Checkpoint(
        name="chk",
        period=CHECKPOINT_PERIOD,
        write_dir=outdir,
    )

    # ----- simulation -----
    sim = picmi.Simulation(
        solver=solver,
        time_step_size=dt,
        max_steps=setup["max_steps"],
        particle_shape=1,
        warpx_embedded_boundary=embedded_boundary,
        warpx_random_seed=42,
        warpx_used_inputs_file=f"used_inputs_{args.case}.txt",
        warpx_amr_restart=args.restart,
    )

    bulk_layout = picmi.PseudoRandomLayout(
        n_macroparticles_per_cell=args.ppc, grid=grid)

    def flux_layout(nu):
        return picmi.PseudoRandomLayout(n_macroparticles_per_cell=nu, grid=grid)

    sim.add_species(electrons,
                    layout=[bulk_layout] + [flux_layout(nu_e)] * 3)
    sim.add_species(ions,
                    layout=[bulk_layout] + [flux_layout(nu_i)] * 3)

    sim.add_diagnostic(scrape_diag)
    sim.add_diagnostic(field_diag)
    sim.add_diagnostic(pnum_diag)
    sim.add_diagnostic(checkpoint)

    # Optional uniform external B along z (the geomagnetic field). B || z keeps
    # the problem axisymmetric so it stays valid in RZ.
    if args.bz:
        sim.add_applied_field(picmi.ConstantAppliedField(Bz=args.bz))

    # sim.step(N) advances N steps from the current one, so when restarting
    # from a checkpoint only run the steps remaining up to max_steps.
    nsteps = setup["max_steps"]
    if args.restart:
        m = re.search(r"(\d+)/*$", args.restart)
        if m:
            nsteps = max(0, setup["max_steps"] - int(m.group(1)))
            print(f"restart from step {int(m.group(1))}: "
                  f"running {nsteps} more steps")
    sim.step(nsteps)


if __name__ == "__main__":
    main()
