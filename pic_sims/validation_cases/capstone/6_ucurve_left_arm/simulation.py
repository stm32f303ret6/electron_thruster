#!/usr/bin/env python3
"""capstone.ucurve_left_arm: the chipsat thruster at 92.4 V, fixed 13.65 nN demand (WarpX PICMI, RZ electrostatic).

The complete PIC model for the top rung, migrated from the validated
electron_contactor float200 baseline: a conducting can floats electrically in
the capstone ionospheric plasma; an enclosed electron gun (cathode held a fixed
supply offset below the body) fires a prescribed beam through the lid hole.
Everything that makes this stage what it is lives in this one file:

  - the deck (grid, solver, piecewise two-node EB, three species, diagnostics);
  - the FLOATING-BODY CHARGE PUMP: self-capacitance C measured once from the
    uniform-1 V init solve (Gauss's law on the domain faces); every step the
    net scraped charge integrates into Q and phi_body = phi0 + Q/C, and the
    EB potential string (BODY = phi_body, CATHODE = phi_body + offset once the
    supply is on) is rewritten via set_potential_on_eb;
  - the RESERVOIR: every EB-collected ambient particle is banked and
    re-injected as a fresh Maxwellian in the outer radial shell -- the floating
    equilibrium is a current balance and must not deplete the finite domain;
  - the per-step OBSERVER: scrape-buffer harvest, beam-fate classification by
    electrode, F_beam / F_net momentum accounting, exhaust-KE spectrum, and the
    contactor_log.csv ledger every 100 steps.

The dQ accounting and the Gauss-law C are transcribed verbatim from the
validated deck -- do not "simplify" them.  Checkpoint/restart is deliberately
not migrated (an interrupted run is FAILED and rerun; see MIGRATION_PLAN.md).

Each execution creates a fresh immutable run directory under ``outputs/`` and
is COMPLETE only after artifact and final-iteration verification:

    python simulation.py                 # uses ./config.yaml (GPU-scale run)
    python analyze.py --run outputs/<run-id> --policy acceptance.yaml

Run ONE WarpX case at a time on this machine.
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
from helpers import (  # noqa: E402
    AMB_E, AMB_I, BEAM, STAGE_ID, Config, Geometry, analytic_capacitance,
    load_config,
)

DEFAULT_CONFIG = CASE_DIR / "config.yaml"
OUTPUTS_ROOT = CASE_DIR / "outputs"

E = scc.e
ME = scc.m_e
EPS0 = scc.epsilon_0
CC = scc.c

RANDOM_SEED = 42          # the validated capstone's seed (hardcoded there too)
RESERVOIR_SEED = 2024     # reservoir re-injection RNG (contactor value)
LOG_EVERY = 100           # CSV ledger cadence [steps]
MAX_GRID_SIZE = 1024      # single box (single-GPU)

CSV_HEADER = ("step,t,phi_body,V_cathode,Q_body,I_cathode,I_body,I_escape,"
              "I_amb_e,I_amb_i,F_beam_N,F_net_N,pct_cathode,pct_body,"
              "pct_escape,pct_inflight,beam_escape_KE_mean\n")


class FloatingBodyDiverged(RuntimeError):
    """phi_body went non-finite; the run is FAILED (never silently diverge)."""


class ChokedRun(RuntimeError):
    """phi_body stayed above run.phi_ceiling for choke_sustain; the ionosphere
    cannot neutralize this current here -- the run is FAILED early."""


def _warpx_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("pywarpx")
    except Exception:  # noqa: BLE001
        return None


# ======================================================================
# floating body (electron_contactor floating_body.py, transcribed)
# ======================================================================

def _get_field(sim, name: str, level: int = 0):
    """Fetch a registered MultiFab as an indexable wrapper.

    Newer pywarpx exposes ``sim.fields.get(name, level=...)``; the 26.5 registry
    binding has no ``get``, so fall back to the classic fields-module wrappers
    (same global-index ``[...]``/``.shape`` semantics)."""
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
    while the EB is held at a uniform 1 V (spacecraft_charging example)."""
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


class FloatingBody:
    """The self-consistent charge pump that owns phi_body (two-node EB)."""

    def __init__(self, sim, geom: Geometry, cfg: Config):
        self.sim = sim
        self.geom = geom
        self.dt = cfg.dt
        self.phi0 = cfg.phi_body_init
        self.cathode_offset = cfg.cathode_offset
        self.t_supply = cfg.t_supply
        self.rmax, self.nz = cfg.rmax, cfg.nz
        self.C: float | None = None
        self.Q = 0.0
        self.phi = self.phi0
        self.calibrated = False

    def cathode_value(self, phi_body: float, t: float) -> float:
        """Cathode EB potential: tracks the body at the fixed supply offset once
        the supply is on; equipotential with the body before that."""
        return phi_body + self.cathode_offset if t >= self.t_supply else phi_body

    def _eb_string(self, phi_body: float, t: float) -> str:
        return self.geom.potential_string(phi_body,
                                          self.cathode_value(phi_body, t))

    def calibrate_fresh(self) -> None:
        """Measure C from the uniform-1 V init solve, then impose the float
        string (body = phi0, cathode = phi0 before the supply turns on)."""
        warpx = self.sim.extension.warpx
        self.C = self_capacitance(self.sim, self.rmax, self.nz)
        self.phi = self.phi0
        warpx.set_potential_on_eb(self._eb_string(self.phi, 0.0))
        self.calibrated = True
        c_an = analytic_capacitance(self.geom.r_p)
        print(f"[calib] C_float = {self.C*1e12:.4f} pF (ref 4*pi*eps0*r_p = "
              f"{c_an*1e12:.4f} pF); cathode offset {self.cathode_offset:+.0f} V, "
              f"supply on at t={self.t_supply*1e9:.0f} ns", flush=True)
        if not (0.3e-12 < self.C < 5e-12):
            print(f"[calib] WARNING: C={self.C*1e12:.3f} pF far from analytic -- "
                  f"check the 1 V init solve before trusting phi_body.", flush=True)

    def step(self, dW_beam: float, beam_escape: float, amb_e_coll: float,
             amb_i_coll: float, step_count: int) -> float:
        """Advance the charge pump one step and rewrite the EB potential.

        --- the validated charge accounting (float200 deck, verbatim) ---
        The supply is an internal EMF, so beam returning to ANY surface is
        captured by dW_beam dropping -> no separate body/cathode term.  Only
        beam_escape is a permanent loss (+e).  amb_e_coll/amb_i_coll are the
        all-EB-surface ambient totals."""
        dQ = E * (dW_beam + beam_escape) - E * amb_e_coll + E * amb_i_coll
        self.Q += dQ
        phi_new = self.phi0 + self.Q / self.C
        if not np.isfinite(phi_new):
            raise FloatingBodyDiverged(
                f"phi_body is not finite at step {step_count} "
                f"(Q={self.Q:.3e} C, C={self.C:.3e} F, dQ={dQ:.3e})")
        self.phi = phi_new
        # re-impose every step: phi moves, and the cathode offset flips at t_supply
        t = step_count * self.dt
        self.sim.extension.warpx.set_potential_on_eb(self._eb_string(self.phi, t))
        return self.phi


# ======================================================================
# observer (electron_contactor diagnostics.py, transcribed; no restart)
# ======================================================================

def _asnumpy(a):
    """Pull a pywarpx array (CuPy on GPU, NumPy on CPU) to host NumPy."""
    get = getattr(a, "get", None)
    return get() if callable(get) else np.asarray(a)


def _sum_tiles(arrs) -> float:
    return float(sum(_asnumpy(a).sum() for a in arrs)) if arrs else 0.0


class Diagnostics:
    """Observe the run, never mutate it.  Single reader of the scrape buffers;
    returns the four charge-pump terms and writes the CSV ledger."""

    def __init__(self, geom: Geometry, cfg: Config, diags_dir: Path):
        from pywarpx.particle_containers import (
            ParticleBoundaryBufferWrapper, ParticleContainerWrapper)

        self.geom = geom
        self.dt = cfg.dt
        self.m_ion = cfg.m_ion
        self.buf = ParticleBoundaryBufferWrapper()
        self.beam_pc = ParticleContainerWrapper(BEAM)
        self.W_beam_last: float | None = None
        self._acc = self._zero_acc()
        self._acc_steps = 0
        self._ke_hist: list = []           # (KE_eV, w) of beam ESCAPED via z_hi
        self.cum_emitted = 0.0             # cumulative beam fate (real weight)
        self.cum_cathode = 0.0
        self.cum_body = 0.0
        self.cum_escape = 0.0
        self._report_last_t = -1.0
        self.logf = open(diags_dir / "contactor_log.csv", "w")
        self.logf.write(CSV_HEADER)
        self.logf.flush()

    @staticmethod
    def _zero_acc() -> dict:
        # charge per electrode [C] + escaped z-momentum (F_beam) + all-EB impact
        # z-momentum (F_net), reset every LOG_EVERY
        return dict(cathode=0.0, body=0.0, escape=0.0, amb_e=0.0, amb_i=0.0,
                    pz_escape=0.0, pz_impact=0.0)

    # ---- scrape-buffer readers ----
    def _comp(self, species: str, comp: str, boundary: str = "eb"):
        """This-step scraped component at `boundary`, concatenated over tiles."""
        try:
            arrs = self.buf.get_particle_scraped_this_step(
                species, boundary, comp, 0)
        except Exception:  # noqa: BLE001  (comp/boundary may not exist)
            return np.zeros(0)
        return np.concatenate([_asnumpy(a) for a in arrs]) if arrs else np.zeros(0)

    def _scraped_rz_w(self, species: str):
        return (self._comp(species, "r"), self._comp(species, "z"),
                self._comp(species, "w"))

    def _pz_eb(self, species: str, mass: float, w_eb) -> float:
        """z-momentum of `species` absorbed on the EB this step: mass*sum(w*uz)."""
        uz = self._comp(species, "uz", "eb")
        if w_eb.size and uz.size == w_eb.size:
            return mass * float((w_eb * uz).sum())
        return 0.0

    @staticmethod
    def _ke_eV(ux, uy, uz):               # u = gamma*v (proper velocity)
        u2 = ux * ux + uy * uy + uz * uz
        g = np.sqrt(1.0 + u2 / CC**2)
        return (g - 1.0) * ME * CC**2 / E

    @staticmethod
    def _msum(w, masks, keys) -> float:
        if w.size == 0:
            return 0.0
        m = np.zeros(w.shape, dtype=bool)
        for k in keys:
            m |= masks[k]
        return float(w[m].sum())

    # ---- per-step harvest; returns the charge-pump terms ----
    def collect(self) -> dict:
        g = self.geom

        # in-domain beam weight -> dW_beam (net created minus scraped this step)
        W_beam = _sum_tiles(self.beam_pc.get_particle_weight(0))
        if self.W_beam_last is None:
            self.W_beam_last = W_beam
        dW_beam = W_beam - self.W_beam_last
        self.W_beam_last = W_beam

        # beam EB scrapes, classified by electrode
        rb, zb, wb = self._scraped_rz_w(BEAM)
        reb = g.regions(rb, zb) if wb.size else None
        beam_cathode = self._msum(wb, reb, ("cathode",)) if reb else 0.0
        beam_body = self._msum(wb, reb, ("wall", "lid", "floor_ann")) if reb else 0.0

        # ALL ambient collected on the EB -> reservoir bank + charge pump
        we_eb = self._comp(AMB_E, "w", "eb")
        wi_eb = self._comp(AMB_I, "w", "eb")
        amb_e_coll = float(we_eb.sum()) if we_eb.size else 0.0
        amb_i_coll = float(wi_eb.sum()) if wi_eb.size else 0.0

        # beam that LEFT the domain this step (ESCAPED -> thrust) + z-momentum
        w_zhi = self._comp(BEAM, "w", "z_hi")
        w_zlo = self._comp(BEAM, "w", "z_lo")
        w_xhi = self._comp(BEAM, "w", "x_hi")
        beam_escape = float(w_zhi.sum() + w_zlo.sum() + w_xhi.sum())
        uz_zhi = self._comp(BEAM, "uz", "z_hi")
        uz_xhi = self._comp(BEAM, "uz", "x_hi")
        pz_escape = ME * (float((w_zhi * uz_zhi).sum())
                          if w_zhi.size and uz_zhi.size == w_zhi.size else 0.0)
        pz_escape += ME * (float((w_xhi * uz_xhi).sum())
                           if w_xhi.size and uz_xhi.size == w_xhi.size else 0.0)

        # F_net: z-momentum of ALL species absorbed on the craft's EB surfaces
        pz_impact = (self._pz_eb(BEAM, ME, wb)
                     + self._pz_eb(AMB_E, ME, we_eb)
                     + self._pz_eb(AMB_I, self.m_ion, wi_eb))

        # cumulative beam fate since gun-on
        self.cum_emitted += dW_beam + beam_cathode + beam_body + beam_escape
        self.cum_cathode += beam_cathode
        self.cum_body += beam_body
        self.cum_escape += beam_escape

        # averaged-log accumulators
        self._acc["cathode"] += E * beam_cathode
        self._acc["body"] += E * beam_body
        self._acc["escape"] += E * beam_escape
        self._acc["amb_e"] += E * amb_e_coll
        self._acc["amb_i"] += E * amb_i_coll
        self._acc["pz_escape"] += pz_escape
        self._acc["pz_impact"] += pz_impact
        self._acc_steps += 1

        # exhaust KE spectrum of the escaped beam (mean exhaust energy)
        if w_zhi.size:
            ux = self._comp(BEAM, "ux", "z_hi")
            uy = self._comp(BEAM, "uy", "z_hi")
            if ux.size == w_zhi.size and uy.size == w_zhi.size:
                self._ke_hist.append((self._ke_eV(ux, uy, uz_zhi), w_zhi))

        return dict(dW_beam=dW_beam, beam_escape=beam_escape,
                    amb_e_coll=amb_e_coll, amb_i_coll=amb_i_coll)

    # ---- averaged CSV row every LOG_EVERY steps ----
    def log(self, step_count: int, phi_body: float, Q_body: float,
            v_cathode: float, force: bool = False) -> bool:
        """Write one averaged row per full window; ``force=True`` flushes a
        final partial window at end-of-run so the CSV ledger covers every step
        (the charge-consistency gate compares it against the openPMD dumps)."""
        if self._acc_steps < LOG_EVERY and not (force and self._acc_steps > 0):
            return False
        win = self._acc_steps * self.dt
        t = step_count * self.dt
        ke_mean = np.nan
        if self._ke_hist:
            kes = np.concatenate([k for k, _ in self._ke_hist])
            wts = np.concatenate([w for _, w in self._ke_hist])
            ke_mean = float(np.average(kes, weights=wts)) if wts.sum() > 0 else np.nan
        a = self._acc
        ce = self.cum_emitted
        pct_cathode = 100.0 * self.cum_cathode / ce if ce > 0 else 0.0
        pct_body = 100.0 * self.cum_body / ce if ce > 0 else 0.0
        pct_escape = 100.0 * self.cum_escape / ce if ce > 0 else 0.0
        pct_inflight = max(0.0, 100.0 - pct_cathode - pct_body - pct_escape)
        f_beam = a["pz_escape"] / win     # N (directed-beam thrust)
        f_net = a["pz_impact"] / win      # N (all-EB impact momentum on craft)
        self.logf.write(
            f"{step_count},{t:.6e},{phi_body:.6e},{v_cathode:.6e},{Q_body:.6e},"
            f"{a['cathode']/win:.6e},{a['body']/win:.6e},{a['escape']/win:.6e},"
            f"{a['amb_e']/win:.6e},{a['amb_i']/win:.6e},{f_beam:.6e},{f_net:.6e},"
            f"{pct_cathode:.4f},{pct_body:.4f},{pct_escape:.4f},{pct_inflight:.4f},"
            f"{ke_mean:.6e}\n")
        self.logf.flush()
        if ce > 0 and (t - self._report_last_t) >= 10e-9:
            self._report_last_t = t
            print(f"[fate t={t*1e9:7.1f} ns] body={phi_body:+.1f}V "
                  f"cath={v_cathode:+.0f}V | ESCAPE={pct_escape:5.1f}% "
                  f"body={pct_body:5.1f}% cathode={pct_cathode:4.1f}% "
                  f"inflight={pct_inflight:4.1f}% | F_beam={f_beam*1e9:+.3f} nN "
                  f"F_net={f_net*1e9:+.3f} nN exhaustKE={ke_mean:.1f} eV",
                  flush=True)
        self._acc = self._zero_acc()
        self._acc_steps = 0
        self._ke_hist = []
        return True

    def close(self) -> None:
        if self.logf is not None:
            self.logf.close()
            self.logf = None


# ======================================================================
# reservoir (electron_contactor reservoir.py, transcribed)
# ======================================================================

class Reservoir:
    """The infinite-ionosphere refill: bank every EB-collected ambient particle
    and re-inject it as a fresh Maxwellian at n_inf into the outer radial shell.
    Without it the floating equilibrium measures reservoir depletion."""

    def __init__(self, geom: Geometry, cfg: Config):
        self.enabled = cfg.reservoir_enabled
        self.every = cfg.reservoir_every
        dx = geom.dx
        self.R_res = cfg.R_res
        self.r_hi = cfg.rmax - 2.0 * dx
        self.z_lo = cfg.zmin + 2.0 * dx
        self.z_hi = cfg.zmax - 2.0 * dx
        self.vth_e = cfg.vth_e
        self.vth_i = cfg.vth_i
        self._res_e = 0.0
        self._res_i = 0.0
        self.n_injected = 0
        # reference macro-weight so we inject a sensible macroparticle count
        r_mid = 0.5 * (self.R_res + cfg.rmax)
        self.w_ref = cfg.n0 * (2.0 * np.pi * r_mid * dx * dx) / cfg.ppc
        self.rng = np.random.default_rng(RESERVOIR_SEED)
        self.pc_e = None   # wrappers exist only once species are added
        self.pc_i = None

    def _wrappers(self):
        if self.pc_e is None:
            from pywarpx.particle_containers import ParticleContainerWrapper
            self.pc_e = ParticleContainerWrapper(AMB_E)
            self.pc_i = ParticleContainerWrapper(AMB_I)
        return self.pc_e, self.pc_i

    def bank(self, amb_e_coll: float, amb_i_coll: float) -> None:
        if not self.enabled:
            return
        self._res_e += amb_e_coll
        self._res_i += amb_i_coll

    def maybe_inject(self, step_count: int) -> None:
        if self.enabled and step_count % self.every == 0:
            self._inject()

    def _inject(self) -> None:
        """Spend the banked weight into the outer shell (RZ r-weighted radii
        keep the injected density uniform in area)."""
        pc_e, pc_i = self._wrappers()
        for pc, W, vth in ((pc_e, self._res_e, self.vth_e),
                           (pc_i, self._res_i, self.vth_i)):
            if W <= 0.0:
                continue
            N = int(min(max(round(W / self.w_ref), 50), 20000))
            w_each = W / N
            u = self.rng.random(N)
            r = np.sqrt(self.R_res**2 + u * (self.r_hi**2 - self.R_res**2))
            th = self.rng.random(N) * 2.0 * np.pi
            x = r * np.cos(th)
            y = r * np.sin(th)
            z = self.z_lo + self.rng.random(N) * (self.z_hi - self.z_lo)
            ux = self.rng.normal(0.0, vth, N)
            uy = self.rng.normal(0.0, vth, N)
            uz = self.rng.normal(0.0, vth, N)
            pc.add_particles(x=x, y=y, z=z, ux=ux, uy=uy, uz=uz,
                             w=np.full(N, w_each), unique_particles=False)
            self.n_injected += N
        self._res_e = 0.0
        self._res_i = 0.0


# ======================================================================
# deck assembly (electron_contactor run.py, transcribed)
# ======================================================================

def build_species(cfg: Config, geom: Geometry, grid):
    """Return (species_list, layouts_list): the gated beam + two ambient species
    (bulk fill at t=0 plus one-sided Maxwellian influx from the three open faces,
    flux-layout macroweight nu-matched to the bulk's)."""
    from pywarpx import picmi

    rms = cfg.rms_velocity
    beam_flux = picmi.AnalyticFluxDistribution(
        flux=f"flux0*(sqrt(x*x+y*y)<we)*(t>{cfg.t_on:.10g})",
        flux_normal_axis="z", surface_flux_position=geom.z_emit,
        flux_direction=+1, gaussian_flux_momentum_distribution=True,
        rms_velocity=[rms, rms, rms], flux0=cfg.flux0_used, we=geom.we)
    beam = picmi.Species(
        name=BEAM, particle_type="electron", initial_distribution=beam_flux,
        warpx_save_particles_at_zlo=1, warpx_save_particles_at_zhi=1,
        warpx_save_particles_at_xhi=1, warpx_save_particles_at_eb=1)
    beam_layout = picmi.PseudoRandomLayout(
        n_macroparticles_per_cell=cfg.ppc_beam, grid=grid)

    def make_ambient(name, vth, flux, kw):
        bulk = picmi.UniformDistribution(
            density=cfg.n0, rms_velocity=[vth, vth, vth])
        flux_r = picmi.UniformFluxDistribution(
            flux=flux, surface_flux_position=cfg.rmax, flux_normal_axis="r",
            flux_direction=-1, gaussian_flux_momentum_distribution=True,
            rms_velocity=[vth, vth, vth])
        flux_zhi = picmi.UniformFluxDistribution(
            flux=flux, surface_flux_position=cfg.zmax, flux_normal_axis="z",
            flux_direction=-1, gaussian_flux_momentum_distribution=True,
            rms_velocity=[vth, vth, vth])
        flux_zlo = picmi.UniformFluxDistribution(
            flux=flux, surface_flux_position=cfg.zmin, flux_normal_axis="z",
            flux_direction=+1, gaussian_flux_momentum_distribution=True,
            rms_velocity=[vth, vth, vth])
        return picmi.Species(
            name=name, initial_distribution=[bulk, flux_r, flux_zhi, flux_zlo],
            warpx_save_particles_at_zlo=1, warpx_save_particles_at_zhi=1,
            warpx_save_particles_at_xhi=1, warpx_save_particles_at_eb=1, **kw)

    amb_e = make_ambient(AMB_E, cfg.vth_e, cfg.flux_e,
                         dict(particle_type="electron"))
    amb_i = make_ambient(AMB_I, cfg.vth_i, cfg.flux_i,
                         dict(charge=E, mass=cfg.m_ion))

    bulk_layout = picmi.PseudoRandomLayout(
        n_macroparticles_per_cell=cfg.ppc, grid=grid)

    def flux_layout(flux):
        nu = flux * cfg.dt * cfg.ppc / (cfg.n0 * cfg.dx)
        return picmi.PseudoRandomLayout(n_macroparticles_per_cell=nu, grid=grid)

    species = [beam, amb_e, amb_i]
    layouts = [beam_layout,
               [bulk_layout] + [flux_layout(cfg.flux_e)] * 3,
               [bulk_layout] + [flux_layout(cfg.flux_i)] * 3]
    return species, layouts, beam


def build_simulation(cfg: Config, geom: Geometry, run: lc.Run):
    """Assemble and return the PICMI Simulation (WarpX is not stepped here)."""
    from pywarpx import amrex as amrex_params
    from pywarpx import picmi

    amrex_params.the_arena_init_size = cfg.gpu_arena_bytes

    grid = picmi.CylindricalGrid(
        number_of_cells=[cfg.nr, cfg.nz], n_azimuthal_modes=1,
        lower_bound=[0.0, cfg.zmin], upper_bound=[cfg.rmax, cfg.zmax],
        lower_boundary_conditions=["none", "dirichlet"],
        upper_boundary_conditions=["dirichlet", "dirichlet"],
        lower_boundary_conditions_particles=["none", "absorbing"],
        upper_boundary_conditions_particles=["absorbing", "absorbing"],
        warpx_max_grid_size=MAX_GRID_SIZE)
    solver = picmi.ElectrostaticSolver(
        grid=grid, method="Multigrid", required_precision=1e-6,
        maximum_iterations=500, warpx_self_fields_verbosity=0)
    # FLOAT: the EB starts at a uniform 1 V so the init solve calibrates the
    # self-capacitance C (a clean Gauss-law measurement with the offset absent).
    embedded_boundary = picmi.EmbeddedBoundary(
        implicit_function=geom.implicit_function(), potential=1.0)

    species, layouts, beam = build_species(cfg, geom, grid)

    sim = picmi.Simulation(
        solver=solver, time_step_size=cfg.dt, max_steps=cfg.max_steps,
        particle_shape=1, warpx_embedded_boundary=embedded_boundary,
        warpx_random_seed=RANDOM_SEED,
        warpx_used_inputs_file=str(run.diags_dir / "used_inputs.txt"))

    rho_list = ["Er", "Ez", "phi", "rho",
                "rho_beam_electrons", "rho_ambient_electrons",
                "rho_ambient_ions"]
    sim.add_diagnostic(picmi.FieldDiagnostic(
        name="fields", grid=grid, period=cfg.diag_period, data_list=rho_list,
        warpx_format="openpmd", warpx_openpmd_backend="h5",
        write_dir=str(run.diags_dir)))
    sim.add_diagnostic(picmi.ParticleDiagnostic(
        name="particles", period=cfg.diag_period, species=[beam],
        data_list=["position", "momentum", "weighting"],
        warpx_format="openpmd", warpx_openpmd_backend="h5",
        write_dir=str(run.diags_dir)))
    sim.add_diagnostic(picmi.ParticleBoundaryScrapingDiagnostic(
        name="scrape", period=cfg.diag_period, species=species,
        warpx_format="openpmd", warpx_openpmd_backend="h5",
        warpx_dump_last_timestep=True, write_dir=str(run.diags_dir)))
    # ParticleNumber heartbeat at the CSV cadence (observer-side addition;
    # gives in-domain weights for budget cross-checks).
    sim.add_diagnostic(picmi.ReducedDiagnostic(
        diag_type="ParticleNumber", name="particle_number", period=LOG_EVERY,
        path=f"{run.diags_dir / 'reducedfiles'}/"))

    for sp, layout in zip(species, layouts):
        sim.add_species(sp, layout=layout)
    return sim


def edge_phi_max(sim) -> float:
    """Sheath-containment watchdog: max |phi| a few nodes INSIDE the open
    boundaries (the exact boundary nodes are Dirichlet-0 by construction)."""
    p = np.abs(np.asarray(_get_field(sim, "phi_fp")[:, :]))
    return float(max(p[-4:-1, :].max(),      # radial shell inside r = rmax
                     p[:, 1:4].max(),        # slab inside z = zmin
                     p[:, -4:-1].max()))     # slab inside z = zmax


# ======================================================================
# per-step orchestration (electron_contactor Coordinator; no restart)
# ======================================================================

class Coordinator:
    def __init__(self, cfg: Config, fb: FloatingBody, diag: Diagnostics,
                 res: Reservoir):
        self.cfg = cfg
        self.fb = fb
        self.diag = diag
        self.res = res
        self.step_count = 0
        self.ready = False
        self.choked = False
        self._choke_t0: float | None = None

    def on_init_esolve(self) -> None:
        """Fires once after the initial solve: C calibration."""
        self.fb.calibrate_fresh()
        self.ready = True

    def on_esolve(self) -> None:
        if not self.ready:
            return
        self.step_count += 1
        terms = self.diag.collect()
        self.res.bank(terms["amb_e_coll"], terms["amb_i_coll"])
        self.res.maybe_inject(self.step_count)
        self.fb.step(terms["dW_beam"], terms["beam_escape"],
                     terms["amb_e_coll"], terms["amb_i_coll"], self.step_count)
        ceiling = self.cfg.phi_ceiling
        if ceiling is not None:
            t = self.step_count * self.cfg.dt
            if self.fb.phi > ceiling:
                if self._choke_t0 is None:
                    self._choke_t0 = t
                if (t - self._choke_t0) >= self.cfg.choke_sustain:
                    self.choked = True
            else:
                self._choke_t0 = None

    def on_step(self) -> None:
        if not self.ready:
            return
        t = self.step_count * self.cfg.dt
        v_cath = self.fb.cathode_value(self.fb.phi, t)
        self.diag.log(self.step_count, self.fb.phi, self.fb.Q, v_cath)


# ======================================================================
# main
# ======================================================================

def observed_final_iteration(run: lc.Run) -> int | None:
    """Largest iteration actually written to the field diagnostic on disk."""
    iters = []
    for p in (run.diags_dir / "fields").glob("*.h5"):
        m = re.findall(r"\d+", p.stem)
        if m:
            iters.append(int(m[-1]))
    return max(iters) if iters else None


def banner(cfg: Config, geom: Geometry, run: lc.Run) -> None:
    print("=" * 78)
    print(f"CHIPSAT CAPSTONE [{run.run_id}] {STAGE_ID}  (RZ, ES, floating body)")
    print(f"  plasma: ne={cfg.n0:.3e} m^-3  kTe={cfg.kTe_eV*1e3:.1f} meV  "
          f"mi={cfg.ion_mass_me:.0f} me  lambda_D={cfg.lamD*1e3:.3f} mm  "
          f"wpe*dt={cfg.wpe*cfg.dt:.2e}")
    print(f"  gun: gap={cfg.V_GAP:.0f} V  I_beam={cfg.i_beam*1e3:.3f} mA "
          f"({100*cfg.i_beam/cfg.I_CL:.0f}% of planar I_CL "
          f"{cfg.I_CL*1e3:.3f} mA -- a rough scale)  supply on {cfg.t_supply*1e9:.0f} ns, "
          f"gun on {cfg.t_on*1e9:.0f} ns")
    print("  geometry: " + geom.describe())
    print(f"  grid: r in [0,{cfg.rmax*1e3:.2f}] mm  z in [{cfg.zmin*1e3:.2f},"
          f"{cfg.zmax*1e3:.2f}] mm  {cfg.nr}x{cfg.nz}  dx={cfg.dx*1e3:.3f} mm")
    print(f"  dt={cfg.dt:.3e} s  steps={cfg.max_steps}  "
          f"t_end={cfg.max_steps*cfg.dt*1e9:.1f} ns  CFL={cfg.cfl:.2f}")
    if cfg.reservoir_enabled:
        print(f"  reservoir: recycle EB-collected plasma into r>{cfg.R_res*1e3:.1f} mm "
              f"every {cfg.reservoir_every} steps")
    print(f"  output: {run.dir}")
    print("=" * 78)
    sys.stdout.flush()


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="chipsat capstone PIC run")
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
        from pywarpx.callbacks import (
            installafterEsolve, installafterInitEsolve, installafterstep)

        sim = build_simulation(cfg, geom, run)
        fb = FloatingBody(sim, geom, cfg)
        diag = Diagnostics(geom, cfg, run.diags_dir)
        res = Reservoir(geom, cfg)
        coord = Coordinator(cfg, fb, diag, res)

        installafterInitEsolve(coord.on_init_esolve)
        installafterEsolve(coord.on_esolve)
        installafterstep(coord.on_step)

        # One chunked loop: between chunks we watch sheath containment and the
        # choke ceiling.  Chunking does not change the physics.
        nsteps = cfg.max_steps
        seg = max(500, nsteps // 60)
        edge_warned = False
        done = 0
        while done < nsteps:
            chunk = min(seg, nsteps - done)
            sim.step(chunk)
            done += chunk
            wx_step = sim.extension.warpx.getistep(0)
            if coord.step_count != wx_step:
                print(f"[warn] coordinator step {coord.step_count} != warpx "
                      f"istep {wx_step} (bookkeeping drift)", flush=True)
            if cfg.edge_phi_max is not None:
                e_phi = edge_phi_max(sim)
                if e_phi > cfg.edge_phi_max and not edge_warned:
                    edge_warned = True
                    print(f"[sheath] WARNING: |phi|={e_phi:.2f} V just inside "
                          f"the open boundaries exceeds domain.edge_phi_max="
                          f"{cfg.edge_phi_max:g} V -- sheath/plume clipped by "
                          f"the grounded box (the analysis gates this).",
                          flush=True)
            if coord.choked:
                raise ChokedRun(
                    f"phi_body={fb.phi:+.1f} V > {cfg.phi_ceiling:g} V "
                    f"sustained {cfg.choke_sustain*1e9:.0f} ns at step "
                    f"{coord.step_count}: the ionosphere cannot neutralize "
                    f"this current here")

        # flush the final partial CSV window so the ledger covers every step,
        # then close (the charge-consistency gate needs full coverage)
        t_final = coord.step_count * cfg.dt
        diag.log(coord.step_count, fb.phi, fb.Q,
                 fb.cathode_value(fb.phi, t_final), force=True)
        diag.close()
        lc.complete_run(
            run,
            expected_artifacts=["fields/*.h5", "contactor_log.csv",
                                "reducedfiles/*.txt"],
            observed_final_iteration=observed_final_iteration(run))
    except BaseException as exc:  # noqa: BLE001 -- record then re-raise
        lc.fail_run(run, exc)
        raise
    print(f"done: {cfg.max_steps} steps -> {run.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
