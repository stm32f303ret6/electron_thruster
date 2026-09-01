#!/usr/bin/env python3
"""characterization.magnetized_transverse: the anchor body under a TRANSVERSE
external magnetic field (WarpX PICMI, Cartesian 3D electrostatic).

Tier M2 of the magnetized axis, the flight geometry: B = Bx x-hat, thrust
along +z.  The anchor's floating-body machinery is transcribed from the RZ
capstone deck (capstone.floating_body) into 3D:

  - the deck (cubic grid, Multigrid Poisson, ONE solid EB conductor, three
    species, diagnostics);
  - the FLOATING-BODY CHARGE PUMP: self-capacitance C measured once from the
    uniform-1 V init solve (Gauss's law on the six box faces); every step the
    net scraped charge integrates into Q and phi_body = phi0 + Q/C, and the EB
    potential is rewritten via set_potential_on_eb;
  - the RESERVOIR: every EB-collected ambient particle is banked and
    re-injected as a fresh Maxwellian in the outer shell of the box;
  - the per-step OBSERVER: scrape-buffer harvest (beam at the six faces and
    the body; ambient at the body), F_beam / F_net momentum accounting as in
    the anchor, PLUS the term the anchor never needed: the Lorentz force of
    the external field on every particle inside the box, summed on the GPU
    each step.  Momentum conservation for the open box in steady state gives
    the force on the body as

        F_body = -(net momentum flux out) + sum_particles q v x B

    so the thrust-positive ledger reads  F_thrust = F_beam - F_lorentz_z,
    where F_beam is the escaped-beam z-momentum flux (the anchor's readout)
    and F_lorentz_z is the z-component of the Lorentz force on the beam and
    ambient particles in flight.  With B = 0 the two coincide; with B != 0 the
    beam curls before it leaves and the exit flux alone under-reads the
    reaction the body already received at emission (README.md).

What is NOT here: the gun.  The body is solid and the escaped beam is a
prescribed flux source on the lid at the anchor's measured lid energy
(config.yaml).  The dQ accounting and the Gauss-law C follow the anchor deck
term by term.  Checkpoint/restart is deliberately absent (an interrupted run is
FAILED and rerun; see pic_sims/ARCHITECTURE.md).

Each execution creates a fresh immutable run directory under ``outputs/`` and
is COMPLETE only after artifact and final-iteration verification:

    python simulation.py --scenario b0_control      # or transverse_1x / transverse_10x
    python analyze.py --runs outputs/<b0> outputs/<1x> outputs/<10x> --policy acceptance.yaml

Run ONE WarpX case at a time on this machine.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy import constants as scc

CASE_DIR = Path(__file__).resolve().parent
_pic_root = CASE_DIR  # walk up to pic_sims/ (ladder_contract, shared plumbing)
while not (_pic_root / "ladder_contract.py").is_file():
    _pic_root = _pic_root.parent
sys.path.insert(0, str(_pic_root))
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

RANDOM_SEED = 42          # the validated capstone's seed
RESERVOIR_SEED = 2024     # reservoir re-injection RNG (anchor value)
LOG_EVERY = 100           # CSV ledger cadence [steps]
MAX_GRID_SIZE = 128       # one box per 128^3 (single-GPU)
BLOCKING_FACTOR = 8
FACES = ("x_lo", "x_hi", "y_lo", "y_hi", "z_lo", "z_hi")

CSV_HEADER = ("step,t,phi_body,Q_body,I_emit,I_body,I_escape,I_amb_e,I_amb_i,"
              "F_beam_N,F_beam_y_N,F_net_N,F_lorentz_z_N,F_lorentz_y_N,"
              "F_lorentz_beam_z_N,F_thrust_N,pct_body,pct_escape,pct_inflight,"
              "beam_escape_KE_mean\n")


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
# array helpers (CuPy on GPU, NumPy on CPU)
# ======================================================================

def _asnumpy(a):
    """Pull a pywarpx array (CuPy on GPU, NumPy on CPU) to host NumPy."""
    get = getattr(a, "get", None)
    return get() if callable(get) else np.asarray(a)


def _xp(a):
    """The array module (cupy or numpy) that owns ``a``."""
    if isinstance(a, np.ndarray):
        return np
    import cupy  # noqa: PLC0415 -- only reached on a GPU build
    return cupy.get_array_module(a)


def _dsum(arrs) -> float:
    """Sum a list of per-tile arrays where they live (no host copy)."""
    total = 0.0
    for a in arrs:
        if a.size:
            total += float(a.sum())
    return total


# ======================================================================
# floating body (charge pump, transcribed from the anchor; 3D Gauss law)
# ======================================================================

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


def self_capacitance(sim, cfg: Config) -> tuple[float, dict]:
    """Float-node self-capacitance via Gauss' law on the six box faces, valid
    while the EB is held at a uniform 1 V (spacecraft_charging example, 3D):

        Q_body = -int(rho) dV - eps0 * oint (dphi/dn) dA

    on the nodal phi/rho arrays; the outward normal derivative at each face is
    (phi_face - phi_inner)/dx and the faces are Dirichlet 0."""
    rho = np.asarray(_get_field(sim, "rho_fp")[:, :, :])
    phi = np.asarray(_get_field(sim, "phi_fp")[:, :, :])
    dx = cfg.dx
    flux = 0.0
    flux += ((phi[0, :, :] - phi[1, :, :]).sum() + (phi[-1, :, :] - phi[-2, :, :]).sum())
    flux += ((phi[:, 0, :] - phi[:, 1, :]).sum() + (phi[:, -1, :] - phi[:, -2, :]).sum())
    flux += ((phi[:, :, 0] - phi[:, :, 1]).sum() + (phi[:, :, -1] - phi[:, :, -2]).sum())
    flux *= dx                                   # (dphi/dx) * dA = dphi * dx^2 / dx
    rho_int = float(rho[1:-1, 1:-1, 1:-1].sum()) * dx**3
    C = float(-rho_int - EPS0 * flux)
    info = {"phi_shape": list(phi.shape), "rho_shape": list(rho.shape),
            "rho_integral_C": rho_int, "grad_phi_flux_Vm": float(flux)}
    return C, info


class FloatingBody:
    """The self-consistent charge pump that owns phi_body (one-node EB)."""

    def __init__(self, sim, geom: Geometry, cfg: Config):
        self.sim = sim
        self.geom = geom
        self.cfg = cfg
        self.dt = cfg.dt
        self.phi0 = cfg.phi_body_init
        self.C: float | None = None
        self.calib_info: dict = {}
        self.Q = 0.0
        self.phi = self.phi0
        self.calibrated = False

    def calibrate_fresh(self) -> None:
        """Measure C from the uniform-1 V init solve, then impose phi0."""
        warpx = self.sim.extension.warpx
        self.C, self.calib_info = self_capacitance(self.sim, self.cfg)
        self.phi = self.phi0
        warpx.set_potential_on_eb(self.geom.potential_string(self.phi))
        self.calibrated = True
        c_an = analytic_capacitance(self.geom.r_p)
        print(f"[calib] C_float = {self.C*1e12:.4f} pF (ref 4*pi*eps0*r_p = "
              f"{c_an*1e12:.4f} pF; anchor RZ deck 0.645 pF); nodal shapes "
              f"phi={self.calib_info['phi_shape']} rho={self.calib_info['rho_shape']}",
              flush=True)
        if not (0.3e-12 < self.C < 5e-12):
            print(f"[calib] WARNING: C={self.C*1e12:.3f} pF far from analytic -- "
                  f"check the 1 V init solve before trusting phi_body.", flush=True)

    def step(self, dW_beam: float, beam_escape: float, amb_e_coll: float,
             amb_i_coll: float, step_count: int) -> float:
        """Advance the charge pump one step and rewrite the EB potential.

        --- the validated charge accounting (anchor deck, verbatim) ---
        Every injected beam electron left the body (+e); beam returning to the
        body is captured by dW_beam dropping (the source is an internal EMF),
        so dW_beam + beam_escape == injected - returned.  amb_e_coll/amb_i_coll
        are the all-EB-surface ambient totals."""
        dQ = E * (dW_beam + beam_escape) - E * amb_e_coll + E * amb_i_coll
        self.Q += dQ
        phi_new = self.phi0 + self.Q / self.C
        if not np.isfinite(phi_new):
            raise FloatingBodyDiverged(
                f"phi_body is not finite at step {step_count} "
                f"(Q={self.Q:.3e} C, C={self.C:.3e} F, dQ={dQ:.3e})")
        self.phi = phi_new
        self.sim.extension.warpx.set_potential_on_eb(
            self.geom.potential_string(self.phi))
        return self.phi


# ======================================================================
# observer (anchor diagnostics + the Lorentz ledger; no restart)
# ======================================================================

class Diagnostics:
    """Observe the run, never mutate it.  Single reader of the scrape buffers;
    returns the four charge-pump terms and writes the CSV ledger."""

    def __init__(self, geom: Geometry, cfg: Config, diags_dir: Path):
        from pywarpx.particle_containers import (
            ParticleBoundaryBufferWrapper, ParticleContainerWrapper)

        self.geom = geom
        self.cfg = cfg
        self.dt = cfg.dt
        self.m_ion = cfg.m_ion
        self.Bx = 0.0 if cfg.Bx_T is None else cfg.Bx_T
        self.buf = ParticleBoundaryBufferWrapper()
        self.pcs = {BEAM: ParticleContainerWrapper(BEAM),
                    AMB_E: ParticleContainerWrapper(AMB_E),
                    AMB_I: ParticleContainerWrapper(AMB_I)}
        self.charges = {BEAM: -E, AMB_E: -E, AMB_I: +E}
        self.W_beam_last: float | None = None
        self._acc = self._zero_acc()
        self._acc_steps = 0
        self._ke_hist: list = []           # (KE_eV, w) of beam ESCAPED via a face
        self.cum_emitted = 0.0             # cumulative beam fate (real weight)
        self.cum_body = 0.0
        self.cum_escape = 0.0
        self._report_last_t = -1.0
        self.logf = open(diags_dir / "contactor_log.csv", "w")
        self.logf.write(CSV_HEADER)
        self.logf.flush()

    @staticmethod
    def _zero_acc() -> dict:
        # charge per channel [C], escaped beam momentum (F_beam), all-EB impact
        # z-momentum (F_net), Lorentz force sums; reset every LOG_EVERY
        return dict(emit=0.0, body=0.0, escape=0.0, amb_e=0.0, amb_i=0.0,
                    pz_escape=0.0, py_escape=0.0, pz_impact=0.0,
                    fLz=0.0, fLy=0.0, fLz_beam=0.0)

    # ---- scrape-buffer readers ----
    def _comp(self, species: str, comp: str, boundary: str = "eb"):
        """This-step scraped component at `boundary`, concatenated over tiles."""
        try:
            arrs = self.buf.get_particle_scraped_this_step(
                species, boundary, comp, 0)
        except Exception:  # noqa: BLE001  (comp/boundary may not exist)
            return np.zeros(0)
        return np.concatenate([_asnumpy(a) for a in arrs]) if arrs else np.zeros(0)

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

    # ---- in-domain Lorentz force, summed on the device ----
    def _lorentz(self, species: str) -> tuple[float, float]:
        """(F_z, F_y) of q v x B on every in-domain macroparticle of `species`
        for B = Bx x-hat:  F_z = -q Bx sum(w v_y),  F_y = +q Bx sum(w v_z)."""
        if self.Bx == 0.0:
            return 0.0, 0.0
        pc = self.pcs[species]
        ws = pc.get_particle_weight(0)
        uxs = pc.get_particle_ux(0)
        uys = pc.get_particle_uy(0)
        uzs = pc.get_particle_uz(0)
        Sy = 0.0
        Sz = 0.0
        for w, ux, uy, uz in zip(ws, uxs, uys, uzs):
            if w.size == 0:
                continue
            xp = _xp(w)
            inv_g = 1.0 / xp.sqrt(1.0 + (ux * ux + uy * uy + uz * uz) / CC**2)
            Sy += float((w * uy * inv_g).sum())
            Sz += float((w * uz * inv_g).sum())
        q = self.charges[species]
        return -q * self.Bx * Sy, q * self.Bx * Sz

    # ---- per-step harvest; returns the charge-pump terms ----
    def collect(self) -> dict:
        # in-domain beam weight -> dW_beam (net created minus scraped this step)
        W_beam = _dsum(self.pcs[BEAM].get_particle_weight(0))
        if self.W_beam_last is None:
            self.W_beam_last = W_beam
        dW_beam = W_beam - self.W_beam_last
        self.W_beam_last = W_beam

        # beam back on the body (the only EB electrode)
        wb = self._comp(BEAM, "w", "eb")
        beam_body = float(wb.sum()) if wb.size else 0.0

        # ALL ambient collected on the EB -> reservoir bank + charge pump
        we_eb = self._comp(AMB_E, "w", "eb")
        wi_eb = self._comp(AMB_I, "w", "eb")
        amb_e_coll = float(we_eb.sum()) if we_eb.size else 0.0
        amb_i_coll = float(wi_eb.sum()) if wi_eb.size else 0.0

        # beam that LEFT the box this step (ESCAPED -> thrust) + momentum flux
        beam_escape = 0.0
        pz_escape = 0.0
        py_escape = 0.0
        for face in FACES:
            w = self._comp(BEAM, "w", face)
            if not w.size:
                continue
            ux = self._comp(BEAM, "ux", face)
            uy = self._comp(BEAM, "uy", face)
            uz = self._comp(BEAM, "uz", face)
            beam_escape += float(w.sum())
            if uz.size == w.size:
                pz_escape += ME * float((w * uz).sum())
            if uy.size == w.size:
                py_escape += ME * float((w * uy).sum())
            if ux.size == w.size and uy.size == w.size and uz.size == w.size:
                self._ke_hist.append((self._ke_eV(ux, uy, uz), w))

        # F_net: z-momentum of ALL species absorbed on the body
        pz_impact = (self._pz_eb(BEAM, ME, wb)
                     + self._pz_eb(AMB_E, ME, we_eb)
                     + self._pz_eb(AMB_I, self.m_ion, wi_eb))

        # the Lorentz ledger: q v x B on everything inside the box
        fLz_beam, fLy_beam = self._lorentz(BEAM)
        fLz_e, fLy_e = self._lorentz(AMB_E)
        fLz_i, fLy_i = self._lorentz(AMB_I)

        # cumulative beam fate since gun-on
        injected = dW_beam + beam_body + beam_escape
        self.cum_emitted += injected
        self.cum_body += beam_body
        self.cum_escape += beam_escape

        # averaged-log accumulators
        a = self._acc
        a["emit"] += E * injected
        a["body"] += E * beam_body
        a["escape"] += E * beam_escape
        a["amb_e"] += E * amb_e_coll
        a["amb_i"] += E * amb_i_coll
        a["pz_escape"] += pz_escape
        a["py_escape"] += py_escape
        a["pz_impact"] += pz_impact
        a["fLz"] += (fLz_beam + fLz_e + fLz_i) * self.dt
        a["fLy"] += (fLy_beam + fLy_e + fLy_i) * self.dt
        a["fLz_beam"] += fLz_beam * self.dt
        self._acc_steps += 1

        return dict(dW_beam=dW_beam, beam_escape=beam_escape,
                    amb_e_coll=amb_e_coll, amb_i_coll=amb_i_coll)

    # ---- averaged CSV row every LOG_EVERY steps ----
    def log(self, step_count: int, phi_body: float, Q_body: float,
            force: bool = False) -> bool:
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
        pct_body = 100.0 * self.cum_body / ce if ce > 0 else 0.0
        pct_escape = 100.0 * self.cum_escape / ce if ce > 0 else 0.0
        pct_inflight = max(0.0, 100.0 - pct_body - pct_escape)
        f_beam = a["pz_escape"] / win     # N (escaped-beam z-momentum flux)
        f_beam_y = a["py_escape"] / win
        f_net = a["pz_impact"] / win      # N (all-EB impact momentum on craft)
        f_lz = a["fLz"] / win             # N (Lorentz force on in-domain particles)
        f_ly = a["fLy"] / win
        f_lz_beam = a["fLz_beam"] / win
        f_thrust = f_beam - f_lz          # N (momentum-conservation thrust on the body)
        self.logf.write(
            f"{step_count},{t:.6e},{phi_body:.6e},{Q_body:.6e},"
            f"{a['emit']/win:.6e},{a['body']/win:.6e},{a['escape']/win:.6e},"
            f"{a['amb_e']/win:.6e},{a['amb_i']/win:.6e},"
            f"{f_beam:.6e},{f_beam_y:.6e},{f_net:.6e},{f_lz:.6e},{f_ly:.6e},"
            f"{f_lz_beam:.6e},{f_thrust:.6e},"
            f"{pct_body:.4f},{pct_escape:.4f},{pct_inflight:.4f},{ke_mean:.6e}\n")
        self.logf.flush()
        if ce > 0 and (t - self._report_last_t) >= 10e-9:
            self._report_last_t = t
            print(f"[fate t={t*1e9:7.1f} ns] body={phi_body:+.1f}V | "
                  f"ESCAPE={pct_escape:5.1f}% body={pct_body:5.1f}% "
                  f"inflight={pct_inflight:4.1f}% | F_beam={f_beam*1e9:+.3f} nN "
                  f"F_L,z={f_lz*1e9:+.4f} nN F_thrust={f_thrust*1e9:+.3f} nN "
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
# reservoir (anchor reservoir, transcribed to the box shell)
# ======================================================================

class Reservoir:
    """The infinite-ionosphere refill: bank every EB-collected ambient particle
    and re-inject it as a fresh Maxwellian at n_inf into the outer shell of the
    box.  Without it the floating equilibrium measures reservoir depletion."""

    def __init__(self, cfg: Config):
        self.enabled = cfg.reservoir_enabled
        self.every = cfg.reservoir_every
        dx = cfg.dx
        self.inner = cfg.inner_box                     # (xh, yh, zlo, zhi)
        self.xo = cfg.xmax - 2.0 * dx
        self.yo = cfg.ymax - 2.0 * dx
        self.zlo_o = cfg.zmin + 2.0 * dx
        self.zhi_o = cfg.zmax - 2.0 * dx
        self.vth_e = cfg.vth_e
        self.vth_i = cfg.vth_i
        self._res_e = 0.0
        self._res_i = 0.0
        self.n_injected = 0
        self.w_ref = cfg.n0 * dx**3 / cfg.ppc         # bulk macro-weight
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

    def _shell_positions(self, N: int):
        """N points uniform in the box (inset 2 cells) minus the inner box."""
        xh, yh, zlo, zhi = self.inner
        xs, ys, zs = [], [], []
        got = 0
        while got < N:
            n = 2 * (N - got) + 16
            x = self.rng.uniform(-self.xo, self.xo, n)
            y = self.rng.uniform(-self.yo, self.yo, n)
            z = self.rng.uniform(self.zlo_o, self.zhi_o, n)
            keep = ~((np.abs(x) < xh) & (np.abs(y) < yh) & (z > zlo) & (z < zhi))
            xs.append(x[keep]); ys.append(y[keep]); zs.append(z[keep])
            got += int(keep.sum())
        x = np.concatenate(xs)[:N]
        y = np.concatenate(ys)[:N]
        z = np.concatenate(zs)[:N]
        return x, y, z

    def _inject(self) -> None:
        """Spend the banked weight into the outer shell."""
        pc_e, pc_i = self._wrappers()
        for pc, W, vth in ((pc_e, self._res_e, self.vth_e),
                           (pc_i, self._res_i, self.vth_i)):
            if W <= 0.0:
                continue
            N = int(min(max(round(W / self.w_ref), 50), 20000))
            w_each = W / N
            x, y, z = self._shell_positions(N)
            ux = self.rng.normal(0.0, vth, N)
            uy = self.rng.normal(0.0, vth, N)
            uz = self.rng.normal(0.0, vth, N)
            pc.add_particles(x=x, y=y, z=z, ux=ux, uy=uy, uz=uz,
                             w=np.full(N, w_each), unique_particles=False)
            self.n_injected += N
        self._res_e = 0.0
        self._res_i = 0.0


# ======================================================================
# deck assembly
# ======================================================================

def build_species(cfg: Config, geom: Geometry, grid):
    """Return (species_list, layouts_list, beam): the gated exhaust source + two
    ambient species (bulk fill at t=0 plus one-sided Maxwellian influx from the
    six open faces, flux-layout macroweight nu-matched to the bulk's)."""
    from pywarpx import picmi

    rms = cfg.rms_velocity
    beam_flux = picmi.AnalyticFluxDistribution(
        flux=f"flux0*((x*x+y*y)<(re*re))*(t>{cfg.t_on:.10g})",
        flux_normal_axis="z", surface_flux_position=geom.z_emit,
        flux_direction=+1, gaussian_flux_momentum_distribution=True,
        rms_velocity=[rms, rms, rms],
        directed_velocity=[0.0, 0.0, cfg.v_inject],
        flux0=cfg.flux0, re=geom.we)
    beam = picmi.Species(
        name=BEAM, particle_type="electron", initial_distribution=beam_flux,
        warpx_save_particles_at_xlo=1, warpx_save_particles_at_xhi=1,
        warpx_save_particles_at_ylo=1, warpx_save_particles_at_yhi=1,
        warpx_save_particles_at_zlo=1, warpx_save_particles_at_zhi=1,
        warpx_save_particles_at_eb=1)
    beam_layout = picmi.PseudoRandomLayout(
        n_macroparticles_per_cell=cfg.ppc_beam, grid=grid)

    faces = (("x", -cfg.xmax, +1), ("x", cfg.xmax, -1),
             ("y", -cfg.ymax, +1), ("y", cfg.ymax, -1),
             ("z", cfg.zmin, +1), ("z", cfg.zmax, -1))

    def make_ambient(name, vth, flux, kw):
        bulk = picmi.UniformDistribution(
            density=cfg.n0, rms_velocity=[vth, vth, vth])
        fluxes = [picmi.UniformFluxDistribution(
                      flux=flux, surface_flux_position=pos, flux_normal_axis=axis,
                      flux_direction=direction,
                      gaussian_flux_momentum_distribution=True,
                      rms_velocity=[vth, vth, vth])
                  for axis, pos, direction in faces]
        return picmi.Species(
            name=name, initial_distribution=[bulk, *fluxes],
            warpx_save_particles_at_eb=1, **kw)

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
               [bulk_layout] + [flux_layout(cfg.flux_e)] * len(faces),
               [bulk_layout] + [flux_layout(cfg.flux_i)] * len(faces)]
    return species, layouts, beam


def build_simulation(cfg: Config, geom: Geometry, run: lc.Run):
    """Assemble and return the PICMI Simulation (WarpX is not stepped here)."""
    from pywarpx import amrex as amrex_params
    from pywarpx import picmi

    amrex_params.the_arena_init_size = cfg.gpu_arena_bytes

    grid = picmi.Cartesian3DGrid(
        number_of_cells=[cfg.nx, cfg.ny, cfg.nz],
        lower_bound=[-cfg.xmax, -cfg.ymax, cfg.zmin],
        upper_bound=[cfg.xmax, cfg.ymax, cfg.zmax],
        lower_boundary_conditions=["dirichlet"] * 3,
        upper_boundary_conditions=["dirichlet"] * 3,
        lower_boundary_conditions_particles=["absorbing"] * 3,
        upper_boundary_conditions_particles=["absorbing"] * 3,
        warpx_max_grid_size=MAX_GRID_SIZE, warpx_blocking_factor=BLOCKING_FACTOR)
    solver = picmi.ElectrostaticSolver(
        grid=grid, method="Multigrid", required_precision=1e-6,
        maximum_iterations=500, warpx_self_fields_verbosity=0)
    # FLOAT: the EB starts at a uniform 1 V so the init solve calibrates the
    # self-capacitance C (a clean Gauss-law measurement).
    embedded_boundary = picmi.EmbeddedBoundary(
        implicit_function=geom.implicit_function(), potential=1.0)

    species, layouts, beam = build_species(cfg, geom, grid)

    sim = picmi.Simulation(
        solver=solver, time_step_size=cfg.dt, max_steps=cfg.max_steps,
        particle_shape=1, warpx_embedded_boundary=embedded_boundary,
        warpx_random_seed=RANDOM_SEED,
        warpx_used_inputs_file=str(run.diags_dir / "used_inputs.txt"))

    # THE AXIS: uniform external B perpendicular to the thrust axis.  Absent ->
    # the unmagnetized control (no applied-field block at all).
    if cfg.Bx_T is not None:
        sim.add_applied_field(picmi.ConstantAppliedField(Bx=cfg.Bx_T))

    field_list = ["Ex", "Ey", "Ez", "phi", "rho",
                  "rho_beam_electrons", "rho_ambient_electrons",
                  "rho_ambient_ions"]
    sim.add_diagnostic(picmi.FieldDiagnostic(
        name="fields", grid=grid, period=cfg.diag_period, data_list=field_list,
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
    # Reduced diagnostics at the CSV cadence: ParticleNumber (budget
    # heartbeat) and ParticleMomentum (independent sample of the in-domain
    # momentum the Lorentz ledger integrates; the analysis cross-checks them).
    sim.add_diagnostic(picmi.ReducedDiagnostic(
        diag_type="ParticleNumber", name="particle_number", period=LOG_EVERY,
        path=f"{run.diags_dir / 'reducedfiles'}/"))
    sim.add_diagnostic(picmi.ReducedDiagnostic(
        diag_type="ParticleMomentum", name="particle_momentum", period=LOG_EVERY,
        path=f"{run.diags_dir / 'reducedfiles'}/"))

    for sp, layout in zip(species, layouts):
        sim.add_species(sp, layout=layout)
    return sim


def edge_phi_max(sim) -> float:
    """Sheath-containment watchdog: max |phi| a few nodes INSIDE the six open
    faces (the exact boundary nodes are Dirichlet-0 by construction)."""
    p = np.abs(np.asarray(_get_field(sim, "phi_fp")[:, :, :]))
    return float(max(p[1:4, :, :].max(), p[-4:-1, :, :].max(),
                     p[:, 1:4, :].max(), p[:, -4:-1, :].max(),
                     p[:, :, 1:4].max(), p[:, :, -4:-1].max()))


# ======================================================================
# per-step orchestration (anchor coordinator, transcribed; no restart)
# ======================================================================

class Coordinator:
    def __init__(self, cfg: Config, fb: FloatingBody, diag: Diagnostics,
                 res: Reservoir, diags_dir: Path):
        self.cfg = cfg
        self.fb = fb
        self.diag = diag
        self.res = res
        self.diags_dir = diags_dir
        self.step_count = 0
        self.ready = False
        self.choked = False
        self._choke_t0: float | None = None

    def on_init_esolve(self) -> None:
        """Fires once after the initial solve: C calibration."""
        self.fb.calibrate_fresh()
        lc.write_json_atomic(self.diags_dir / "calibration.json", {
            "C_float_F": self.fb.C,
            "C_analytic_sphere_F": analytic_capacitance(self.fb.geom.r_p),
            **self.fb.calib_info})
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
        self.diag.log(self.step_count, self.fb.phi, self.fb.Q)


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
    print(f"TRANSVERSE-B CHIPSAT [{run.run_id}] {STAGE_ID} scenario={cfg.scenario}"
          f"  (3D, ES, floating body)")
    print(f"  plasma: ne={cfg.n0:.3e} m^-3  kTe={cfg.kTe_eV*1e3:.1f} meV  "
          f"mi={cfg.ion_mass_me:.0f} me  lambda_D={cfg.lamD*1e3:.3f} mm  "
          f"wpe*dt={cfg.wpe*cfg.dt:.2e}")
    print(f"  exhaust: I_beam={cfg.i_beam*1e3:.3f} mA at KE_lid={cfg.ke_inject_eV:.1f} eV "
          f"(v={cfg.v_inject:.3e} m/s), gun on {cfg.t_on*1e9:.0f} ns")
    print("  geometry: " + geom.describe())
    if cfg.Bx_T is None:
        print("  field: B = 0 (unmagnetized control)")
    else:
        print(f"  field: Bx={cfg.Bx_T*1e6:.1f} uT  r_g(beam)={cfg.r_gyro_beam*1e3:.1f} mm  "
              f"r_g(thermal e)={cfg.r_gyro_thermal_e*1e3:.2f} mm  "
              f"omega_ce*dt={cfg.omega_ce*cfg.dt:.2e}")
    print(f"  grid: x,y in +-{cfg.xmax*1e3:.1f} mm  z in [{cfg.zmin*1e3:.1f},"
          f"{cfg.zmax*1e3:.1f}] mm  {cfg.nx}x{cfg.ny}x{cfg.nz}={cfg.n_cells:.3e} cells  "
          f"dx={cfg.dx*1e3:.3f} mm")
    print(f"  dt={cfg.dt:.3e} s  steps={cfg.max_steps}  "
          f"t_end={cfg.max_steps*cfg.dt*1e9:.1f} ns  CFL={cfg.cfl:.2f}")
    if cfg.reservoir_enabled:
        xh, yh, zlo, zhi = cfg.inner_box
        print(f"  reservoir: recycle EB-collected plasma outside |x|<{xh*1e3:.1f}, "
              f"|y|<{yh*1e3:.1f}, z in [{zlo*1e3:.1f},{zhi*1e3:.1f}] mm "
              f"every {cfg.reservoir_every} steps")
    print(f"  output: {run.dir}")
    print("=" * 78)
    sys.stdout.flush()


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="transverse-B chipsat PIC run")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--scenario", default=None,
                    help="scenario name from the source study (required unless "
                         "--config is a frozen single-scenario config)")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config, scenario=args.scenario)
    geom = cfg.geometry()

    run = lc.begin_run(
        run_root=OUTPUTS_ROOT, stage_id=STAGE_ID, config=cfg.effective_config(),
        scenario=cfg.scenario, study_config=cfg.study_config(),
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
        res = Reservoir(cfg)
        coord = Coordinator(cfg, fb, diag, res, run.diags_dir)

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
                          f"the open faces exceeds domain.edge_phi_max="
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
        diag.log(coord.step_count, fb.phi, fb.Q, force=True)
        diag.close()
        lc.complete_run(
            run,
            expected_artifacts=["fields/*.h5", "contactor_log.csv",
                                "calibration.json", "reducedfiles/*.txt"],
            observed_final_iteration=observed_final_iteration(run))
    except BaseException as exc:  # noqa: BLE001 -- record then re-raise
        lc.fail_run(run, exc)
        raise
    print(f"done: {cfg.max_steps} steps -> {run.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
